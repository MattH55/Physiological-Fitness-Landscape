"""
Phase 7 (Signature-transfer modifier x drug predictor build order):
hand-engineered mechanistic pathway features (synlethality/pathway_features.py,
real MSigDB Hallmark gene sets) + gradient-boosted trees, trained on the
same real Phase 4 corpus (2924 pairs, ALMANAC + DrugComb) Phases 5 and 6
used, validated the same way (leave-one-cell-line-out, leave-one-drug-out,
beat Bliss-independence RMSE on both).

Why try this after Phases 5 and 6 both failed: those used the raw 978-dim
signature vectors directly (flat features or a GCN over the PPI graph).
This instead follows the precedent in scripts/README (1).md's literature
review (TreeCombo: boosted trees on hand-built features beat deep nets at
modest label counts; MARSY, Cheng et al. 2019 Complementary Exposure:
pathway-level and geometric features carry synergy signal a flat
978-vector may not expose to a model with ~3000 real training rows). The
features themselves are new here -- built on real Hallmark gene sets, not
the cited papers' own feature sets, and not the synthetic 51-pathway
simulator scripts/npxp-model.tar.gz used.

Applies the same standing rule as Phase 6: this is a fourth (fifth,
counting the two Phase 5 tree/MLP variants separately) architecture
attempt on the same real, small, heterogeneous label set. A win here
would be a real, checkable result, not assumed going in.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from synlethality import config
from synlethality.crossval import leave_one_cell_line_out, leave_one_drug_out
from synlethality.pathway_features import PathwaySpace, pair_features

PAIRS_PATH = os.path.join(config.DATA_DIR, "lincs", "phase4", "pairs.jsonl")
FEATURES_PATH = os.path.join(config.DATA_DIR, "lincs", "phase4", "features.npz")
OUT_SUMMARY = os.path.join(config.DATA_DIR, "lincs", "phase7_summary.json")
REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PHASE_7_REPORT.md"
)


def load_corpus():
    rows = [json.loads(line) for line in open(PAIRS_PATH, encoding="utf-8")]
    pack = np.load(FEATURES_PATH)
    y = pack["score"].astype(np.float64)
    return rows, pack["signature_a"], pack["signature_b"], pack["baseline"], y


def build_feature_matrix(space, sig_a, sig_b, baseline):
    rows = []
    for i in range(len(sig_a)):
        rows.append(pair_features(space, baseline[i], sig_a[i], sig_b[i]))
    return np.asarray(rows, dtype=np.float64)


def _rmse(y, pred) -> float:
    err = np.asarray(y) - np.asarray(pred)
    return float(np.sqrt(np.mean(err * err)))


NOMINAL = 0.90


def _fit_predict(train_idx, test_idx, X, y):
    model = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0)
    model.fit(X[train_idx], y[train_idx])
    return model.predict(X[test_idx])


def _conformal(train_idx, test_idx, X, y, seed=0):
    """Same method as Phase 5's run_phase5.py: a 90% split-conformal band,
    with calibration rows cut from the training fold (never from test)."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(train_idx)
    cut = max(1, int(0.75 * len(order)))
    if cut >= len(order):
        cut = len(order) - 1
    fit_idx, cal_idx = order[:cut], order[cut:]
    pred_cal = _fit_predict(fit_idx, cal_idx, X, y)
    pred_test = _fit_predict(fit_idx, test_idx, X, y)
    resid = np.abs(y[cal_idx] - pred_cal)
    level = min(NOMINAL, (len(resid) - 1) / len(resid)) if len(resid) else NOMINAL
    q = float(np.quantile(resid, level)) if len(resid) else float("nan")
    covered = np.abs(y[test_idx] - pred_test) <= q
    return pred_test, float(covered.mean()), q


def run_split(name, splits, X, y):
    sse, n, covered_n = 0.0, 0, 0.0
    for label, train_idx, test_idx in splits:
        pred, cov, _q = _conformal(np.asarray(train_idx), np.asarray(test_idx), X, y)
        err = y[test_idx] - pred
        sse += float(np.dot(err, err))
        n += len(test_idx)
        covered_n += cov * len(test_idx)
    rmse = float(np.sqrt(sse / n)) if n else float("nan")
    coverage = covered_n / n if n else float("nan")
    print(f"  [{name}] {len(splits)} folds, {n} predictions, rmse={rmse:.4f}, coverage_90={coverage:.3f}")
    return {"rmse": rmse, "n_predictions": n, "n_folds": len(splits), "coverage_90": coverage}


def main() -> int:
    print("Loading real Phase 4 corpus")
    rows, sig_a, sig_b, baseline, y = load_corpus()
    print(f"  {len(rows)} real pairs")

    print("Loading real Hallmark pathway space")
    space = PathwaySpace()
    print(f"  {space.n_pathways} real Hallmark gene sets with landmark-gene coverage")

    print("Building real mechanistic pathway features for every pair "
          "(no synthetic data; missing genes drop out of pathway means)")
    X = build_feature_matrix(space, sig_a, sig_b, baseline)
    print(f"  feature matrix: {X.shape}")

    cells = [r["cell_line"] for r in rows]
    drug_a_names = [r["drug_a"] for r in rows]
    drug_b_names = [r["drug_b"] for r in rows]
    loco = list(leave_one_cell_line_out(cells))
    lodo = list(leave_one_drug_out(drug_a_names, drug_b_names))

    print("\nGBT on real pathway features, leave-one-cell-line-out:")
    loco_result = run_split("cell-line-out", loco, X, y)
    print("\nGBT on real pathway features, leave-one-drug-out:")
    lodo_result = run_split("drug-out", lodo, X, y)

    bliss_rmse = _rmse(y, np.zeros_like(y))
    beats_bliss = loco_result["rmse"] < bliss_rmse and lodo_result["rmse"] < bliss_rmse
    near_nominal = all(
        0.85 <= r["coverage_90"] <= 0.95 for r in (loco_result, lodo_result)
    )
    gate7 = beats_bliss

    summary = {
        "built": datetime.now(timezone.utc).isoformat(),
        "n_pairs": len(rows),
        "n_pathway_features": int(X.shape[1]),
        "architecture": "HistGradientBoostingRegressor on real MSigDB Hallmark "
                         "pathway-level features (synlethality/pathway_features.py)",
        "bliss_rmse": bliss_rmse,
        "gbt_rmse_cell_line_out": loco_result["rmse"],
        "gbt_rmse_drug_out": lodo_result["rmse"],
        "coverage_90_cell_line_out": loco_result["coverage_90"],
        "coverage_90_drug_out": lodo_result["coverage_90"],
        "near_nominal_90": near_nominal,
        "beats_bliss_both_splits": beats_bliss,
        "gate_7": {
            "passed": gate7,
            "criterion": "GBT-on-pathway-features RMSE < Bliss-independence RMSE under "
                         "both leave-one-cell-line-out and leave-one-drug-out",
        },
        "anchor_check": {
            "applicable": False,
            "reason": "The build order's Gate 6 acceptance test additionally requires "
                      "checking predictions against the real quantitative anchor labels "
                      "(synlethality/tests/test_seed.py's REAL_COMBINED_EFFECT_METRICS: "
                      "HIPEC/Kusumoto/stiffness TER and IC50-fold-shift values). Checked "
                      "2026-09-28: none of those anchor modifiers (MOD-HT-42C-60M-HIPEC, "
                      "MOD-STIFFNESS-53KPA-5G5P, MOD-HT-42.8C-30M-SIMUL/BEFORE, "
                      "MOD-HT-41C/43C-60M-HIPEC) have a real transcriptomic MIGEP in "
                      "data/modifier_signatures/library.json -- they are literature-only "
                      "curated modifiers with no matching GEO series. Separately, their "
                      "metric (TER / survival-slope ratio / IC50 fold-shift) is not the "
                      "same quantity as this model's training target (mean Bliss excess "
                      "of survival fraction). The anchor check is a real, structural gap "
                      "in what can be validated here, not a skipped step.",
        },
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nGATE 7: {'PASSED' if gate7 else 'FAILED'}")
    _write_report(summary)
    return 0 if gate7 else 2


def _write_report(summary: dict) -> None:
    gate = summary["gate_7"]["passed"]
    lines = [
        "# Phase 7 report — mechanistic pathway features + GBT",
        "",
        f"Built {summary['built']}.",
        "",
        f"Trained on the same real {summary['n_pairs']}-pair Phase 4 corpus (ALMANAC + "
        "DrugComb, mimetic-anchored) Phases 5 and 6 used, with the same "
        "leave-one-cell-line-out / leave-one-drug-out validation and the same "
        "Bliss-independence baseline. The features are new: "
        f"{summary['n_pathway_features']} real mechanistic features built from real "
        "MSigDB Hallmark gene sets (cell-context pathway activity, pooled-perturbation "
        "pathway summaries, signature geometry, Cheng-et-al.-2019 complementary "
        "exposure, survival-signed redundancy/buffering, cell x mechanism cross terms) "
        "-- see synlethality/pathway_features.py.",
        "",
        f"**Gate 7: {'PASSED' if gate else 'FAILED'}.** "
        f"Bliss-independence RMSE: {summary['bliss_rmse']:.4f}. "
        f"GBT RMSE, cell-line-out: {summary['gbt_rmse_cell_line_out']:.4f} "
        f"(90% interval coverage {summary['coverage_90_cell_line_out']:.3f}). "
        f"GBT RMSE, drug-out: {summary['gbt_rmse_drug_out']:.4f} "
        f"(90% interval coverage {summary['coverage_90_drug_out']:.3f}). "
        f"Beats Bliss on both splits: {summary['beats_bliss_both_splits']}. "
        f"Intervals near nominal (0.85-0.95): {summary['near_nominal_90']}.",
        "",
        "**This is not the same as the build order's full Gate 6 acceptance test.** "
        "That test also requires checking predictions against the real quantitative "
        "anchor labels (the HIPEC/Kusumoto/stiffness TER and IC50-fold-shift values "
        "in synlethality/tests/test_seed.py's REAL_COMBINED_EFFECT_METRICS). That "
        "check is not applicable here: none of those anchor modifiers have a real "
        "transcriptomic signature in data/modifier_signatures/library.json (they are "
        "literature-only curated modifiers, no matching GEO series), and their metric "
        "(TER / survival-slope ratio / IC50 fold-shift) is not the same quantity as "
        "this model's training target (mean Bliss excess of survival fraction). This "
        "is a real, structural gap in what can be validated here -- not a skipped "
        "step, and not grounds to write tier_2b_model_predicted rows on the strength "
        "of the RMSE result alone.",
        "",
    ]
    if not gate:
        lines += [
            "Hand-engineered mechanistic features did not beat Bliss independence "
            "under both cross-validation schemes either. That is the result, not a "
            "rerun condition. This is now the fourth distinct architecture (global "
            "mean / Bliss, gradient-boosted trees on raw signatures, dual-arm MLP, "
            "PPI-graph GCN, and now GBT on hand-engineered pathway features) to fail "
            "this bar on this real, ~3000-row, highly heterogeneous label set.",
            "",
        ]
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

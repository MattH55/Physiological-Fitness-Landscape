"""Phase 5 on the Phase 4 corpus.

Gate 4 failed (2,352 pairs). This run uses that corpus because it is the
one that was built. It does not treat Gate 4 as passed.

Baselines, in order:
  (a) training-fold mean
  (b) Bliss independence, which is 0 on this excess-over-Bliss target
  (c) gradient-boosted trees on hand-built pair features
  (d) a dual-arm network: a separate PCA per signature arm, then a small
      network on the two arms plus the cell-line baseline

A learned model counts as beating (b) only when its pooled RMSE is lower
under both leave-one-cell-line-out and leave-one-drug-out. Intervals are
split-conformal 90% residual bands. Near-nominal means empirical coverage
between 0.85 and 0.95.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synlethality import config
from synlethality.crossval import leave_one_cell_line_out, leave_one_drug_out

PAIRS = os.path.join(config.DATA_DIR, "lincs", "phase4", "pairs.jsonl")
FEATURES = os.path.join(config.DATA_DIR, "lincs", "phase4", "features.npz")
OUT = os.path.join(config.DATA_DIR, "lincs", "phase5_summary.json")
REPORT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "PHASE_5_REPORT.md",
)
NOMINAL = 0.90


def _load():
    rows = [json.loads(line) for line in open(PAIRS, encoding="utf-8")]
    pack = np.load(FEATURES)
    y = pack["score"].astype(np.float64)
    if len(rows) != len(y):
        raise ValueError("pairs.jsonl and features.npz differ in length")
    return rows, pack["signature_a"], pack["signature_b"], pack["baseline"], y


def _hand(a, b, base) -> np.ndarray:
    def col(x):
        z = np.nan_to_num(x, nan=0.0)
        return z
    aa, bb, cc = col(a), col(b), col(base)
    denom = np.linalg.norm(aa, axis=1) * np.linalg.norm(bb, axis=1)
    corr = np.divide(np.sum(aa * bb, axis=1), denom, out=np.zeros(len(aa)), where=denom > 0)
    return np.column_stack([
        corr,
        np.linalg.norm(aa, axis=1),
        np.linalg.norm(bb, axis=1),
        np.linalg.norm(cc, axis=1),
        aa.mean(axis=1),
        bb.mean(axis=1),
        cc.mean(axis=1),
        np.sum(aa * bb, axis=1),
    ])


def _rmse(y, pred) -> float:
    err = np.asarray(y) - np.asarray(pred)
    return float(np.sqrt(np.mean(err * err)))


def _fit_predict(kind, train, test, hand, arms, y):
    if kind == "a":
        return np.full(len(test), float(y[train].mean()))
    if kind == "b":
        return np.zeros(len(test))
    if kind == "c":
        model = HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.08, max_iter=200, random_state=0,
        )
        model.fit(hand[train], y[train])
        return model.predict(hand[test])
    # (d) dual arm. PCA is fit on the training rows only.
    pieces = []
    for block in arms:
        train_block = np.nan_to_num(block[train], nan=0.0)
        test_block = np.nan_to_num(block[test], nan=0.0)
        n_comp = min(16, train_block.shape[0] - 1, train_block.shape[1])
        pca = PCA(n_components=n_comp, random_state=0)
        pieces.append((pca.fit_transform(train_block), pca.transform(test_block)))
    x_train = np.hstack([p[0] for p in pieces])
    x_test = np.hstack([p[1] for p in pieces])
    net = MLPRegressor(
        hidden_layer_sizes=(32,), max_iter=80, random_state=0,
        early_stopping=True, validation_fraction=0.15,
    )
    net.fit(x_train, y[train])
    return net.predict(x_test)


def _conformal(kind, train, test, hand, arms, y):
    """90% split-conformal band. Calibration rows are cut from the training fold."""
    rng = np.random.default_rng(0)
    order = rng.permutation(train)
    cut = max(1, int(0.75 * len(order)))
    if cut >= len(order):
        cut = len(order) - 1
    fit_idx, cal_idx = order[:cut], order[cut:]
    pred_cal = _fit_predict(kind, fit_idx, cal_idx, hand, arms, y)
    pred_test = _fit_predict(kind, fit_idx, test, hand, arms, y)
    resid = np.abs(y[cal_idx] - pred_cal)
    level = min(NOMINAL, (len(resid) - 1) / len(resid)) if len(resid) else NOMINAL
    q = float(np.quantile(resid, level))
    covered = np.abs(y[test] - pred_test) <= q
    return pred_test, float(covered.mean()), q


def _pooled(splits, kind, hand, arms, y):
    sse = 0.0
    n = 0
    covered_n = 0.0
    for _name, train, test in splits:
        pred, cov, _q = _conformal(kind, train, test, hand, arms, y)
        err = y[test] - pred
        sse += float(np.dot(err, err))
        n += len(test)
        covered_n += cov * len(test)
    return {
        "rmse": float(np.sqrt(sse / n)) if n else float("nan"),
        "coverage_90": covered_n / n if n else float("nan"),
        "n_predictions": n,
    }


def main() -> int:
    rows, sig_a, sig_b, baseline, y = _load()
    hand = _hand(sig_a, sig_b, baseline)
    arms = (sig_a, sig_b, baseline)
    cells = [r["cell_line"] for r in rows]
    drug_a = [r["drug_a"] for r in rows]
    drug_b = [r["drug_b"] for r in rows]
    loco = list(leave_one_cell_line_out(cells))
    lodo = list(leave_one_drug_out(drug_a, drug_b))
    names = {
        "a_global_mean": "a",
        "b_bliss": "b",
        "c_gbt": "c",
        "d_dual_arm": "d",
    }
    results = {}
    for label, kind in names.items():
        print("fitting", label)
        results[label] = {
            "leave_one_cell_line_out": _pooled(loco, kind, hand, arms, y),
            "leave_one_drug_out": _pooled(lodo, kind, hand, arms, y),
        }
        cell = results[label]["leave_one_cell_line_out"]["rmse"]
        drug = results[label]["leave_one_drug_out"]["rmse"]
        print(f"  rmse cell {cell:.4f} drug {drug:.4f}")

    bliss = results["b_bliss"]
    contenders = []
    for label in ("c_gbt", "d_dual_arm"):
        beats = (
            results[label]["leave_one_cell_line_out"]["rmse"] < bliss["leave_one_cell_line_out"]["rmse"]
            and results[label]["leave_one_drug_out"]["rmse"] < bliss["leave_one_drug_out"]["rmse"]
        )
        contenders.append((label, beats, results[label]))
    winners = [item for item in contenders if item[1]]
    if winners:
        chosen = min(winners, key=lambda item: (
            item[2]["leave_one_cell_line_out"]["rmse"] + item[2]["leave_one_drug_out"]["rmse"]
        ))[0]
    else:
        chosen = "b_bliss"
    chosen_cov = results[chosen]
    near = all(
        0.85 <= chosen_cov[scheme]["coverage_90"] <= 0.95
        for scheme in ("leave_one_cell_line_out", "leave_one_drug_out")
    )
    beats_bliss = chosen in ("c_gbt", "d_dual_arm")
    gate = beats_bliss and near
    summary = {
        "built": datetime.now(timezone.utc).isoformat(),
        "n_pairs": len(rows),
        "n_cell_lines": len(set(cells)),
        "n_drugs": len(set(drug_a) | set(drug_b)),
        "gate_4_note": "Phase 4 gate failed at 2352 pairs. Phase 5 uses that corpus.",
        "target": "mean Bliss excess of survival fraction; 0 is independence",
        "models": results,
        "chosen": chosen,
        "beats_bliss_both_splits": beats_bliss,
        "near_nominal_90": near,
        "gate_5": {
            "passed": gate,
            "criterion": "chosen model beats Bliss RMSE on both splits, and 90% intervals cover 0.85-0.95",
        },
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    _report(summary)
    print(f"GATE 5: {'PASSED' if gate else 'FAILED'} chosen={chosen}")
    return 0 if gate else 2


def _report(summary: dict) -> None:
    gate = summary["gate_5"]["passed"]
    lines = [
        "# Phase 5 report — model and validation",
        "",
        f"Built {summary['built']}.",
        "",
        "Phase 4 did not pass its size gate. This comparison uses the "
        f"{summary['n_pairs']} pairs and {summary['n_cell_lines']} cell lines "
        "that were featurized. The target is mean Bliss excess. Predicting 0 "
        "is the Bliss independence baseline.",
        "",
        f"**Gate 5: {'PASSED' if gate else 'FAILED'}.** "
        f"Chosen model: `{summary['chosen']}`. "
        f"Beats Bliss on both splits: {summary['beats_bliss_both_splits']}. "
        f"90% intervals near nominal: {summary['near_nominal_90']}.",
        "",
        "| Model | Cell-line-out RMSE | Drug-out RMSE | Cell-line-out coverage | Drug-out coverage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    labels = {
        "a_global_mean": "(a) global mean",
        "b_bliss": "(b) Bliss independence",
        "c_gbt": "(c) gradient-boosted trees",
        "d_dual_arm": "(d) dual-arm network",
    }
    for key, title in labels.items():
        row = summary["models"][key]
        lines.append(
            f"| {title} | {row['leave_one_cell_line_out']['rmse']:.4f} | "
            f"{row['leave_one_drug_out']['rmse']:.4f} | "
            f"{row['leave_one_cell_line_out']['coverage_90']:.3f} | "
            f"{row['leave_one_drug_out']['coverage_90']:.3f} |"
        )
    if not summary["beats_bliss_both_splits"]:
        lines += [
            "",
            "The learned models did not beat Bliss independence under both "
            "cross-validation schemes. That is the result, not a rerun condition.",
        ]
    lines.append("")
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

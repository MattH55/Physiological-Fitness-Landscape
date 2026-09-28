"""
Phase 7 extension: score every real modifier x drug x cell-line
combination using the FULL real LINCS drug universe (6,204 Phase 1
compounds + 6 curated Phase 2 compounds, deduplicated preferring Phase 2
for its better QC), not just the 13 drugs curated in
synlethality/seed_data.py (9 of which had a real signature). Any real
drug signature works with this pipeline -- it was never drug-specific;
the whole point of the build order's design is that a perturbagen is
just a real signature, modifier or drug alike.

33 modifiers x ~6,210 drugs x 13 cell lines ~= 2.66M real combinations --
690x the earlier 3,861-row grid. Made tractable by synlethality.
pathway_features.pair_block/baseline_block (2026-09-28 refactor): blocks
2/3/5/7 depend only on the (modifier, drug) pair, so they're computed
once per pair (~205k, ~4.5 real minutes) and reused across all 13 cell
lines, instead of recomputed per triple (~2.66M, ~8+ hours). Benchmarked
and verified byte-identical to the original row-by-row pair_features
before this script was trusted with a full run -- see the refactor's own
docstrings in pathway_features.py.

Same honest status as phase7_finish.py, carried into every output row:
Gate 7 (RMSE) passed; full Gate 6 validation (calibration + real anchor
check) did not. validated=False. Nothing written to seed_data.py.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_phase4_corpus import norm_name
from phase7_pathway_gbt import load_corpus
from src.data.expression import load_genes_978
from src.data.loader import signatures_to_migeps
from synlethality import config
from synlethality.pathway_features import PathwaySpace, baseline_block, pair_block, pair_features
from synlethality.signature_space import normalize_z, to_canonical

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENES_PATH = os.path.join(ROOT, "data", "reference", "genes_978.txt")
LIBRARY_PATH = os.path.join(config.DATA_DIR, "modifier_signatures", "library.json")
PHASE1_REF = os.path.join(config.DATA_DIR, "lincs_phase1_raw", "phase1_mcf7_10uM_24h.json")
PHASE2_REF = os.path.join(config.DATA_DIR, "lincs", "curated_drug_signatures.json")
BASELINE_PATH = os.path.join(config.DATA_DIR, "depmap", "curated_cell_line_expression_l1000landmark.json")
OUT_PREDICTIONS_CSV = os.path.join(config.DATA_DIR, "lincs", "phase7_full_lincs_predictions.csv")
OUT_MANIFEST = os.path.join(config.DATA_DIR, "lincs", "phase7_full_lincs_manifest.json")

GATE_7_STATUS = {
    "gate_7_passed": True,
    "bliss_rmse": 0.11050645360928975,
    "gbt_rmse_cell_line_out": 0.10921456583700635,
    "gbt_rmse_drug_out": 0.10821259254578239,
    "coverage_90_cell_line_out": 0.884404924760602,
    "coverage_90_drug_out": 0.823358413132695,
    "near_nominal_90": False,
    "anchor_check_applicable": False,
}
VALIDATED = False
WARNING = (
    "Gate 7's RMSE bar passed (real, both splits), but this is NOT full Gate 6 "
    "validation: drug-out interval coverage (0.823) is below the 0.85 nominal floor, "
    "and the real quantitative anchor labels (HIPEC/Kusumoto/stiffness) cannot be "
    "checked at all -- no overlapping real modifier signatures, and a different "
    "metric type (TER vs. Bliss excess). This file additionally extrapolates to "
    "~6,200 real LINCS compounds this model never saw a single real synergy label "
    "for during training (training only covered ~50 real ALMANAC/DrugComb drugs) -- "
    "an even further extrapolation than the curated-13-drug grid. These are for "
    "prioritization/inspection only. NOT curated evidence. Never write these as "
    "tier_2b_model_predicted."
)


def load_all_real_drug_vectors() -> dict[str, dict]:
    """Every real drug with a usable signature, Phase 1 (6,204 compounds)
    plus Phase 2 (6 curated), deduplicated by normalized name preferring
    Phase 2 (better QC, matches this project's established convention
    from scripts/build_phase4_corpus.py)."""
    phase1 = json.load(open(PHASE1_REF, encoding="utf-8"))
    phase2 = json.load(open(PHASE2_REF, encoding="utf-8"))
    out: dict[str, dict] = {}
    for source in (phase1, phase2):  # phase2 second so it overwrites phase1
        for name, entry in source.items():
            projected = to_canonical(entry["gene_zscore"])
            if projected["coverage"] < 0.7:
                continue
            out[norm_name(name)] = {"name": name, "vector": normalize_z(projected["vector"])}
    return out


def main() -> int:
    t_start = time.time()
    print("Loading real Phase 4 corpus and training the deployment model")
    rows, sig_a, sig_b, baseline, y = load_corpus()
    space = PathwaySpace()
    X = np.asarray(
        [pair_features(space, baseline[i], sig_a[i], sig_b[i]) for i in range(len(rows))],
        dtype=np.float64,
    )
    model = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0)
    model.fit(X, y)
    print(f"  trained on {len(rows)} real pairs, {X.shape[1]} features")

    print("Loading real modifier MIGEPs, the full real LINCS drug universe, and cell-line baselines")
    migeps = signatures_to_migeps(LIBRARY_PATH, GENES_PATH, None)
    drug_vectors = load_all_real_drug_vectors()
    raw_baselines = json.load(open(BASELINE_PATH, encoding="utf-8"))
    baseline_vectors = {}
    for cid, raw in raw_baselines.items():
        projected = to_canonical(raw)
        if projected["coverage"] < 0.7:
            continue
        baseline_vectors[cid] = normalize_z(projected["vector"])
    print(f"  {len(migeps)} real modifier MIGEPs")
    print(f"  {len(drug_vectors)} real drug signatures (full LINCS Phase 1 + Phase 2)")
    print(f"  {len(baseline_vectors)} real cell-line baselines")

    n_pairs = len(migeps) * len(drug_vectors)
    print(f"\nComputing pair_block (modifier x drug, cell-line-independent) for "
          f"{n_pairs} real pairs -- the expensive part, done once per pair, "
          f"reused across all {len(baseline_vectors)} cell lines")
    t0 = time.time()
    pair_ids = []          # (modifier_id, drug_name)
    pair_mat = []           # block 2/3/5/7 vector, one row per pair
    combo_mat = []           # (pa+pb)/2, one row per pair -- reused for block 8 below
    for migep in migeps:
        for key, drec in drug_vectors.items():
            pvec, _names, pa, pb = pair_block(space, migep.vector, drec["vector"])
            pair_ids.append((migep.modifier_id, drec["name"]))
            pair_mat.append(pvec)
            combo_mat.append((pa + pb) / 2.0)
    pair_mat = np.asarray(pair_mat, dtype=np.float64)      # [n_pairs, 318]
    combo_mat = np.asarray(combo_mat, dtype=np.float64)    # [n_pairs, n_pathways]
    t1 = time.time()
    print(f"  done in {t1 - t0:.1f}s ({(t1-t0)/n_pairs*1000:.2f}ms/pair)")

    print(f"\nScoring {n_pairs} real pairs against each of {len(baseline_vectors)} "
          f"real cell lines ({n_pairs * len(baseline_vectors)} total real predictions), "
          "streamed to CSV")
    t0 = time.time()
    n_written = 0
    os.makedirs(os.path.dirname(OUT_PREDICTIONS_CSV), exist_ok=True)
    surv_pos = np.clip(space.survival, 0, None)              # [n_pathways]
    combo_neg_pos = np.clip(-combo_mat, 0, None)              # [n_pairs, n_pathways], reused per cell line
    with open(OUT_PREDICTIONS_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["modifier_signature_id", "drug_id", "cell_line_id", "predicted_bliss_excess"])
        for cell_id, bvec in baseline_vectors.items():
            # block 1 (ctx) computed ONCE per cell line, not once per pair
            # (the bug that made the earlier, killed run ~40x too slow:
            # baseline_block() recomputed space.activity(base) -- an
            # inner loop over 50 pathways -- inside the per-pair loop,
            # even though it only depends on the cell line).
            base = np.nan_to_num(np.array([np.nan if v is None else v for v in bvec], dtype=float), nan=0.0)
            ctx = space.activity(base)                        # [n_pathways]
            ctx_pos = np.clip(ctx, 0, None)
            # block 8, vectorized over all n_pairs at once: two
            # matrix-vector products replace n_pairs separate dot products.
            ctx_align = combo_mat @ ctx                         # [n_pairs]
            ctx_suppress_active = combo_neg_pos @ (ctx_pos * surv_pos)  # [n_pairs]
            ctx_block = np.tile(ctx, (n_pairs, 1))              # [n_pairs, n_pathways]
            feat_mat = np.column_stack([ctx_block, pair_mat, ctx_align, ctx_suppress_active])
            scores = model.predict(feat_mat)
            for (modifier_id, drug_name), score in zip(pair_ids, scores):
                writer.writerow([modifier_id, drug_name, cell_id, float(score)])
                n_written += 1
            print(f"    {cell_id}: {n_pairs} predictions written ({n_written} total so far)")
    t1 = time.time()
    print(f"  done in {t1 - t0:.1f}s")
    print(f"  {n_written} real-signature-backed predictions across the full LINCS drug universe")

    manifest = {
        "built": datetime.now(timezone.utc).isoformat(),
        "validated": VALIDATED,
        "warning": WARNING,
        **GATE_7_STATUS,
        "n_modifiers": len(migeps),
        "n_drugs": len(drug_vectors),
        "n_cell_lines": len(baseline_vectors),
        "n_predictions": n_written,
        "predictions_file": OUT_PREDICTIONS_CSV,
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\nWrote {OUT_PREDICTIONS_CSV}")
    print(f"Wrote {OUT_MANIFEST}")
    print(f"Total wall time: {time.time() - t_start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

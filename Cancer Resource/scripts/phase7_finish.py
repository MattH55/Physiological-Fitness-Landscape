"""
Phase 7 application: train the deployment GBT on the FULL real Phase 4
corpus (not a CV fold -- no held-out evaluation happens here, that
already ran for real in scripts/phase7_pathway_gbt.py, see
PHASE_7_REPORT.md), then score every real modifier x drug x cell-line
combination this project has real signatures for.

Honest status, carried into every output row:
  - Gate 7 (RMSE beats Bliss on both leave-one-cell-line-out and
    leave-one-drug-out): PASSED.
  - Full Gate 6 acceptance (calibrated intervals + real anchor check):
    NOT satisfied -- drug-out coverage is below the 0.85 nominal floor,
    and the anchor check is structurally inapplicable (see
    PHASE_7_REPORT.md). So `validated` is False here, matching Phase 6's
    posture, even though the RMSE bar (unlike Phase 6) really did pass.
    Nothing here is written into synlethality/seed_data.py.
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

from build_phase4_corpus import norm_name
from phase7_pathway_gbt import load_corpus
from src.data.expression import load_genes_978
from src.data.loader import signatures_to_migeps
from synlethality import config
from synlethality import seed_data as sd
from synlethality.pathway_features import PathwaySpace, pair_features
from synlethality.signature_space import normalize_z, to_canonical

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENES_PATH = os.path.join(ROOT, "data", "reference", "genes_978.txt")
LIBRARY_PATH = os.path.join(config.DATA_DIR, "modifier_signatures", "library.json")
PHASE1_REF = os.path.join(config.DATA_DIR, "lincs_phase1_raw", "phase1_mcf7_10uM_24h.json")
PHASE2_REF = os.path.join(config.DATA_DIR, "lincs", "curated_drug_signatures.json")
BASELINE_PATH = os.path.join(config.DATA_DIR, "depmap", "curated_cell_line_expression_l1000landmark.json")
OUT_PREDICTIONS = os.path.join(config.DATA_DIR, "lincs", "phase7_predictions.json")
SUMMARY_PATH = os.path.join(config.DATA_DIR, "lincs", "phase7_summary.json")

# Real result already obtained (scripts/phase7_pathway_gbt.py, completed
# 2026-09-28) -- not re-derived here, same convention as phase6_finish.py.
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
VALIDATED = False  # full Gate 6 bar not met -- see module docstring
WARNING = (
    "Gate 7's RMSE bar passed (real, both splits), but this is NOT full Gate 6 "
    "validation: drug-out interval coverage (0.823) is below the 0.85 nominal floor, "
    "and the real quantitative anchor labels (HIPEC/Kusumoto/stiffness) cannot be "
    "checked at all -- no overlapping real modifier signatures, and a different "
    "metric type (TER vs. Bliss excess). These are extrapolations from a model with "
    "a real but partial, unverified validation. NOT curated evidence. Never write "
    "these as tier_2b_model_predicted -- that tier is gated on the full Gate 6 bar, "
    "which this does not meet."
)


def drug_vector(name: str, phase1: dict, phase2: dict) -> list[float] | None:
    key = norm_name(name)
    entry = None
    for source in (phase2, phase1):  # phase2 preferred (better QC)
        for dname, drec in source.items():
            if norm_name(dname) == key:
                entry = drec
                break
        if entry:
            break
    if entry is None:
        return None
    projected = to_canonical(entry["gene_zscore"])
    if projected["coverage"] < 0.7:
        return None
    return normalize_z(projected["vector"])


def baseline_vector(raw_gene_dict: dict) -> list[float] | None:
    projected = to_canonical(raw_gene_dict)
    if projected["coverage"] < 0.7:
        return None
    return normalize_z(projected["vector"])


def main() -> int:
    print("Loading real Phase 4 corpus and building real pathway features")
    rows, sig_a, sig_b, baseline, y = load_corpus()
    space = PathwaySpace()
    X = np.asarray(
        [pair_features(space, baseline[i], sig_a[i], sig_b[i]) for i in range(len(rows))],
        dtype=np.float64,
    )
    print(f"  {len(rows)} real pairs, {X.shape[1]} real pathway features")

    print("Training the deployment model on the full real corpus "
          "(not a CV fold -- no held-out evaluation happens here)")
    model = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0)
    model.fit(X, y)

    print("Loading real modifier MIGEPs, drug signatures, and cell-line baselines")
    migeps = signatures_to_migeps(LIBRARY_PATH, GENES_PATH, None)
    phase1 = json.load(open(PHASE1_REF, encoding="utf-8"))
    phase2 = json.load(open(PHASE2_REF, encoding="utf-8"))
    raw_baselines = json.load(open(BASELINE_PATH, encoding="utf-8"))

    drug_ids = [d["drug_id"] for d in sd.DRUGS]
    drug_vectors = {d: drug_vector(d, phase1, phase2) for d in drug_ids}
    drug_vectors = {d: v for d, v in drug_vectors.items() if v is not None}
    baseline_vectors = {cid: baseline_vector(raw) for cid, raw in raw_baselines.items()}
    baseline_vectors = {cid: v for cid, v in baseline_vectors.items() if v is not None}
    print(f"  {len(drug_vectors)}/{len(drug_ids)} curated drugs have a real signature")
    print(f"  {len(migeps)} real modifier MIGEPs")
    print(f"  {len(baseline_vectors)}/{len(raw_baselines)} real cell-line baselines project cleanly")

    predictions = []
    for migep in migeps:
        mvec = migep.vector
        for drug_id, dvec in drug_vectors.items():
            for cell_id, bvec in baseline_vectors.items():
                feats = pair_features(space, bvec, mvec, dvec).reshape(1, -1)
                score = float(model.predict(feats)[0])
                predictions.append({
                    "modifier_signature_id": migep.modifier_id,
                    "drug_id": drug_id,
                    "cell_line_id": cell_id,
                    "predicted_bliss_excess": score,
                })
    print(f"  {len(predictions)} real-signature-backed modifier x drug x cell-line predictions")

    out = {
        "built": datetime.now(timezone.utc).isoformat(),
        "validated": VALIDATED,
        "warning": WARNING,
        **GATE_7_STATUS,
        "n_predictions": len(predictions),
        "predictions": predictions,
    }
    with open(OUT_PREDICTIONS, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"Wrote {OUT_PREDICTIONS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

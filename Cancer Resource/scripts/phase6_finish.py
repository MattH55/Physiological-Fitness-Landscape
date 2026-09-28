"""
Completes the Phase 6 run without repeating the expensive 146-fold
cross-validation, which already ran for real on 2026-09-27 and produced:

    GCN RMSE, cell-line-out: 0.1130   (Bliss: 0.1105 -- GCN is WORSE)
    GCN RMSE, drug-out:      0.1098   (Bliss: 0.1105 -- GCN is marginally better)
    GATE 6: FAILED (must beat Bliss on BOTH splits; only one)

(Full real per-fold log: all 56 cell-line folds + 90 drug folds printed
and completed before the run crashed on an unrelated real bug in the
grid-application step -- a baseline-JSON schema mismatch, fixed in
phase6_gcn_transfer.py. Re-running the 146-fold CV to get the same
numbers again would cost another ~2.6 real hours for no new information.)

This script only re-does the cheap part: one final fit on the FULL real
corpus (not a CV fold -- this is the deployment model), then applies it
across the real modifier x drug x cell-line grid, and writes
PHASE_6_REPORT.md / data/lincs/phase6_summary.json / phase6_predictions.json.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase6_gcn_transfer import (
    EPOCHS,
    OUT_SUMMARY,
    PPI_PATH,
    GENES_PATH,
    _apply_to_real_grid,
    _write_report,
    load_corpus,
)
from src.data.expression import load_genes_978
from src.ppi.graph import PPIGraph, load_ppi_edges

import json

REAL_CV_RESULT = {
    "bliss_rmse": 0.1105,
    "gcn_rmse_cell_line_out": 0.1130,
    "gcn_rmse_drug_out": 0.1098,
}


def main() -> int:
    print("Loading real Phase 4 corpus")
    rows, sig_a, sig_b, baseline, y = load_corpus()
    print(f"  {len(rows)} real pairs")

    print("Loading real PPI graph")
    gene_symbols = load_genes_978(GENES_PATH)
    edges = load_ppi_edges(PPI_PATH)
    graph = PPIGraph(gene_symbols=gene_symbols, edges=edges, n_genes=978, virtual_node_id=978)
    adj = torch.tensor(graph.adjacency_matrix(), dtype=torch.float32)

    beats_bliss = (
        REAL_CV_RESULT["gcn_rmse_cell_line_out"] < REAL_CV_RESULT["bliss_rmse"]
        and REAL_CV_RESULT["gcn_rmse_drug_out"] < REAL_CV_RESULT["bliss_rmse"]
    )
    gate6 = beats_bliss
    summary = {
        "built": datetime.now(timezone.utc).isoformat(),
        "n_pairs": len(rows),
        "architecture": "DrugsyncGCN (real STRING PPI graph, 3 GCN layers, "
                         "node features = [signature_A, signature_B], real "
                         "cell-line baseline concatenated before the FC head)",
        "note": "Real 146-fold CV (56 cell-line-out + 90 drug-out) completed "
                "2026-09-27; these numbers come from that completed run's own "
                "printed log, not a re-run (see this script's module docstring).",
        **REAL_CV_RESULT,
        "beats_bliss_both_splits": beats_bliss,
        "gate_6": {
            "passed": gate6,
            "criterion": "GCN RMSE < Bliss-independence RMSE under both leave-one-cell-line-out "
                         "and leave-one-drug-out (same bar as Phase 5's models)",
        },
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"GATE 6: {'PASSED' if gate6 else 'FAILED'}")
    _write_report(summary)

    print("\nApplying to the real modifier x drug x cell-line grid "
          f"({'validated' if gate6 else 'NOT validated -- Gate 6 failed'})...")
    _apply_to_real_grid(adj, gate6, sig_a, sig_b, baseline, y, rows)
    return 0 if gate6 else 2


if __name__ == "__main__":
    sys.exit(main())

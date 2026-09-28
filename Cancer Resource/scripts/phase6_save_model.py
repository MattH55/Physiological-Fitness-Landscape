"""
Persist the Phase 6 GCN (trained on the full real Phase 4 corpus -- the
same training call phase6_finish.py already made and then discarded) to
disk, plus a manifest carrying its real validation result. Nothing here
re-runs the 146-fold CV; see phase6_gcn_transfer.py / phase6_finish.py for
that. This just gives src/inference/predict_modifier_drug.py something
to load.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase6_gcn_transfer import EPOCHS, GENES_PATH, LR, PPI_PATH, build_model, fit, load_corpus
from src.data.expression import load_genes_978
from src.ppi.graph import PPIGraph, load_ppi_edges

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "models", "interaction")
MODEL_PATH = os.path.join(MODEL_DIR, "phase6_gcn.pt")
MANIFEST_PATH = os.path.join(MODEL_DIR, "phase6_gcn_manifest.json")

# Real, already-obtained result (scripts/phase6_gcn_transfer.py's completed
# 146-fold run, 2026-09-27) -- see PHASE_6_REPORT.md.
REAL_CV_RESULT = {
    "bliss_rmse": 0.1105,
    "gcn_rmse_cell_line_out": 0.1130,
    "gcn_rmse_drug_out": 0.1098,
    "gate_6_passed": False,
}


def main() -> int:
    print("Loading real Phase 4 corpus and PPI graph")
    rows, sig_a, sig_b, baseline, y = load_corpus()
    gene_symbols = load_genes_978(GENES_PATH)
    edges = load_ppi_edges(PPI_PATH)
    graph = PPIGraph(gene_symbols=gene_symbols, edges=edges, n_genes=978, virtual_node_id=978)
    adj = torch.tensor(graph.adjacency_matrix(), dtype=torch.float32)

    print(f"Training the deployment model on the full {len(rows)}-pair real corpus "
          f"(this is not a CV fold -- no held-out evaluation happens here)")
    model = build_model(adj)
    fit(model, sig_a, sig_b, baseline, y, list(range(len(rows))), epochs=EPOCHS, lr=LR)

    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    manifest = {
        "saved": datetime.now(timezone.utc).isoformat(),
        "architecture": {
            "class": "DrugsyncGCN", "n_nodes": 979, "gcn_input_dim": 2,
            "gcn_hidden_dim": 16, "gcn_n_layers": 3, "fc_hidden_dims": [16],
            "readout": "mean", "baseline_dim": 978,
        },
        "trained_on": f"{len(rows)} real pairs, data/lincs/phase4/ (ALMANAC + DrugComb, mimetic-anchored)",
        "gene_list": "data/reference/genes_978.txt (978 L1000 landmark genes)",
        "ppi_graph": "data/reference/ppi_edges.csv (real STRING v11.5, threshold 700)",
        "validation": REAL_CV_RESULT,
        "warning": (
            "Gate 6 FAILED (see PHASE_6_REPORT.md): this model does not beat "
            "Bliss independence under both leave-one-cell-line-out and "
            "leave-one-drug-out cross-validation. Predictions from this model "
            "are extrapolations, not validated forecasts. Never write a "
            "prediction from this model into synlethality/seed_data.py as "
            "tier_2b_model_predicted -- that tier is gated on Gate 6 passing."
        ),
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved manifest to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

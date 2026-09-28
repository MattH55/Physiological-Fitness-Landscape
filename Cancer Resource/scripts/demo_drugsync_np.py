"""
First-milestone demo for DRUGSYNC-NPxP, per the build spec's "First
milestone" section: real expression -> real MIGEP -> real PPI graph ->
DRUGSYNC GCN -> a predicted interaction score, on real data end to end.

This demonstrates the pipeline mechanics only. The GCN below has random,
untrained weights (Xavier init) -- there is no real modifier-pair
interaction label on disk yet to train against (data/modifier_pairs/ is
still empty; see this run's own printed note). Per the spec: "If no
pairwise experimental labels exist yet, implement the complete
inference/data pipeline but do not claim that the model has learned
interaction prediction." This script proves the pipeline runs correctly
on real data; it makes no claim about the number it prints meaning
anything biologically.

Uses this project's real Phase 1 modifier signature library (33 real
MIGEPs, synlethality/data/modifier_signatures/library.json) and the real
STRING-derived PPI graph built by scripts/build_drugsync_ppi_graph.py.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.expression import load_gene_index, load_genes_978
from src.data.loader import signatures_to_migeps
from src.models.gcn import DrugsyncGCN
from src.ppi.graph import PPIGraph, load_ppi_edges

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENES_PATH = os.path.join(ROOT, "data", "reference", "genes_978.txt")
GENE_INDEX_PATH = os.path.join(ROOT, "data", "reference", "gene_index.csv")
PPI_PATH = os.path.join(ROOT, "data", "reference", "ppi_edges.csv")
LIBRARY_PATH = os.path.join(ROOT, "data", "modifier_signatures", "library.json")
MODIFIER_PAIRS_PATH = os.path.join(ROOT, "data", "modifier_pairs", "modifier_pairs.csv")


def to_dense_vector(migep_vector: list[float | None]) -> np.ndarray:
    """0.0 fill only for this untrained forward-pass demo -- never written
    back to any stored MIGEP. A real training pipeline must not silently
    zero-fill missing genes; that is a display/compute convenience here."""
    return np.array([0.0 if v is None else v for v in migep_vector], dtype=np.float32)


def main() -> int:
    print("[1/5] Loading canonical gene space")
    gene_symbols = load_genes_978(GENES_PATH)
    gene_index = load_gene_index(GENE_INDEX_PATH)
    print(f"  {len(gene_symbols)} genes")

    print("[2/5] Loading real PPI graph (STRING v11.5, threshold 700)")
    edges = load_ppi_edges(PPI_PATH)
    graph = PPIGraph(gene_symbols=gene_symbols, edges=edges, n_genes=978, virtual_node_id=978)
    adj = torch.tensor(graph.adjacency_matrix(), dtype=torch.float32)
    print(f"  {len(edges)} edges, {graph.n_nodes} nodes")

    print("[3/5] Loading real modifier MIGEPs (this project's Phase 1 library)")
    migeps = signatures_to_migeps(LIBRARY_PATH, GENES_PATH, None)
    print(f"  {len(migeps)} real MIGEPs, e.g.:")
    for m in migeps[:5]:
        print(f"    {m.modifier_id}  (context={m.biological_context})")

    modifier_a, modifier_b = migeps[0], migeps[1]
    print(f"\n[4/5] Building GCN (Xavier-initialized, UNTRAINED) and running "
          f"a forward pass on:\n  A = {modifier_a.modifier_id}\n  B = {modifier_b.modifier_id}")
    model = DrugsyncGCN(n_nodes=979, gcn_input_dim=2, gcn_hidden_dim=256,
                         gcn_n_layers=3, fc_hidden_dims=[128, 64], output_dim=1)
    model.set_adjacency(adj)

    vec_a = to_dense_vector(modifier_a.vector)
    vec_b = to_dense_vector(modifier_b.vector)
    pred_ab = model.predict_pair(vec_a, vec_b).item()
    pred_ba = model.predict_pair(vec_b, vec_a).item()
    print(f"  predicted_interaction(A, B) = {pred_ab:.6f}")
    print(f"  predicted_interaction(B, A) = {pred_ba:.6f}")
    print(f"  |diff| = {abs(pred_ab - pred_ba):.6f} "
          f"(order-invariance tolerance from config: 0.01)")

    print("\n[5/5] Real modifier-pair labels")
    if os.path.isfile(MODIFIER_PAIRS_PATH) and os.path.getsize(MODIFIER_PAIRS_PATH) > 0:
        print(f"  Found {MODIFIER_PAIRS_PATH} -- training is possible.")
    else:
        print(f"  {MODIFIER_PAIRS_PATH} is empty or missing.")
        print("  No real, experimentally-observed modifier x modifier interaction")
        print("  labels exist on disk. This run proves the pipeline mechanics")
        print("  (MIGEP -> PPI graph -> GCN -> scalar) on real data end to end,")
        print("  with an untrained model. It is NOT a trained interaction")
        print("  predictor and the number above carries no biological meaning.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

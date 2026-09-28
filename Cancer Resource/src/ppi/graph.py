"""
PPI graph construction for DRUGSYNC-NPxP.
Result: 979 nodes (978 genes + 1 virtual node).
"""
from __future__ import annotations
import csv
import os
import random
from dataclasses import dataclass
import numpy as np


@dataclass
class PPIGraph:
    gene_symbols: list[str]
    edges: list[tuple[int, int, float]]
    n_genes: int = 978
    virtual_node_id: int = 978
    version: str = "human-STRING-v11.5"

    def __post_init__(self):
        if len(self.gene_symbols) != self.n_genes:
            raise ValueError(f"Expected {self.n_genes} genes, got {len(self.gene_symbols)}")
        self.n_nodes = self.n_genes + 1

    def adjacency_matrix(self) -> np.ndarray:
        A = np.zeros((self.n_nodes, self.n_nodes), dtype=np.float64)
        for src, tgt, w in self.edges:
            A[src, tgt] = w
            A[tgt, src] = w
        return A

    def to_pyg_data(self, x=None):
        import torch
        from torch_geometric.data import Data
        edge_index = [[src, tgt] for src, tgt, w in self.edges]
        edge_weight = [w for _, _, w in self.edges]
        ei = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        ew = torch.tensor(edge_weight, dtype=torch.float)
        if x is None:
            x = torch.zeros((self.n_nodes, 1), dtype=torch.float)
        else:
            x = torch.tensor(x, dtype=torch.float)
        return Data(x=x, edge_index=ei, edge_attr=ew)


def load_ppi_edges(path):
    edges = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            edges.append((int(row["source_index"]), int(row["target_index"]), float(row["weight"])))
    return edges
def build_ppi_graph(gene_symbols, string_data_path=None, threshold=700.0,
                    add_virtual_node=True, random_seed=42, protein_info_path=None):
    """`string_data_path` is STRING's real `9606.protein.links.v*.txt.gz`
    (`protein1 protein2 combined_score`, IDs like `9606.ENSP...`).
    `protein_info_path` is STRING's own `9606.protein.info.v*.txt.gz`
    (`#string_protein_id  preferred_name  ...`) -- required to resolve
    Ensembl protein IDs to gene symbols. Without it, every line's `s1`/`s2`
    would be an ENSP id, which never matches a gene symbol in
    `gene_symbols`, and the graph would silently end up with zero real
    edges (caught 2026-09-27: the previous version stripped STRING's
    species prefix and matched the *Ensembl protein ID* directly against
    gene symbols, and separately re-sorted `gene_symbols` internally
    rather than using the caller's actual order -- both bugs are fixed
    here, not routed around)."""
    if string_data_path and os.path.isfile(string_data_path):
        if not protein_info_path or not os.path.isfile(protein_info_path):
            raise FileNotFoundError(
                "string_data_path given but protein_info_path missing/not found -- "
                "STRING's protein.links file uses Ensembl protein IDs (9606.ENSP...), "
                "not gene symbols; the info file's preferred_name column is required "
                "to resolve them. Passing string_data_path without it would silently "
                "produce zero real edges."
            )
        ensp_to_symbol = _load_string_protein_info(protein_info_path, set(gene_symbols))
        symbol_to_idx = {sym: i for i, sym in enumerate(gene_symbols)}
        edges = _parse_string_file(string_data_path, ensp_to_symbol, symbol_to_idx, threshold)
    else:
        edges = _generate_demo_edges(gene_symbols, random_seed)
    if add_virtual_node:
        edges = edges + [(i, len(gene_symbols), 0.001) for i in range(len(gene_symbols))]
    return PPIGraph(gene_symbols=list(gene_symbols), edges=edges, n_genes=len(gene_symbols),
                    virtual_node_id=len(gene_symbols))


def _load_string_protein_info(path, genes_set):
    """Real STRING protein_id -> gene_symbol map, restricted to symbols in
    the canonical 978-gene set. `path` may be a plain-text or .gz file."""
    import gzip

    ensp_to_symbol = {}
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            protein_id, symbol = parts[0], parts[1]
            if symbol in genes_set:
                ensp_to_symbol[protein_id] = symbol
    return ensp_to_symbol


def _parse_string_file(path, ensp_to_symbol, symbol_to_idx, threshold):
    """`path` may be a plain-text or .gz file (STRING ships .txt.gz)."""
    import gzip

    edges = []
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            try:
                score = float(parts[2])
            except ValueError:
                continue
            if score <= threshold:
                continue
            sym1 = ensp_to_symbol.get(parts[0])
            sym2 = ensp_to_symbol.get(parts[1])
            if sym1 is None or sym2 is None:
                continue
            edges.append((symbol_to_idx[sym1], symbol_to_idx[sym2], score / 1000.0))
    return edges


def _generate_demo_edges(gene_symbols, random_seed=42):
    rng = random.Random(random_seed)
    n = len(gene_symbols)
    edges, seen = [], set()
    while len(edges) < 7800:
        a, b = rng.randrange(n), rng.randrange(n)
        if a == b or (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        edges.append((a, b, round(rng.uniform(0.7, 1.0), 4)))
    return edges


def save_ppi_edges(edges, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_index", "target_index", "weight"])
        for src, tgt, wt in edges:
            w.writerow([src, tgt, wt])
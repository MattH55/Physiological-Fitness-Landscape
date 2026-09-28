"""
Build the real DRUGSYNC-NPxP PPI graph (data/reference/ppi_edges.csv) from
the already-downloaded real STRING v11.5 human files on E:\\drucsync_ref\\
(9606.protein.links.v11.5.txt.gz + 9606.protein.info.v11.5.txt.gz, the
latter added 2026-09-27 specifically to fix a real bug: STRING's links
file uses Ensembl protein IDs, not gene symbols, and src/ppi/graph.py's
build_ppi_graph()/_parse_string_file() previously matched those IDs
directly against gene symbols -- silently zero real edges. See
src/ppi/graph.py's updated docstring for the fix.

Uses data/reference/genes_978.txt (already populated, reused from this
project's own synlethality.signature_space.CANONICAL_SYMBOLS -- the same
978 L1000 landmark genes, verified byte-for-byte identical as a set to
GSE92742's own landmark gene list) so PPI node indices line up with the
gene_index.csv already on disk.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.expression import load_genes_978
from src.ppi.graph import build_ppi_graph, save_ppi_edges

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENES_PATH = os.path.join(ROOT, "data", "reference", "genes_978.txt")
OUT_PATH = os.path.join(ROOT, "data", "reference", "ppi_edges.csv")
STRING_LINKS = r"E:\drucsync_ref\9606.protein.links.v11.5.txt.gz"
STRING_INFO = r"E:\drucsync_ref\9606.protein.info.v11.5.txt.gz"


def main() -> int:
    for path in (GENES_PATH, STRING_LINKS, STRING_INFO):
        if not os.path.isfile(path):
            print("missing", path)
            return 1
    gene_symbols = load_genes_978(GENES_PATH)
    print(f"{len(gene_symbols)} canonical genes loaded")
    graph = build_ppi_graph(
        gene_symbols,
        string_data_path=STRING_LINKS,
        protein_info_path=STRING_INFO,
        threshold=700.0,
        add_virtual_node=True,
    )
    n_real = sum(1 for s, t, w in graph.edges if s < 978 and t < 978)
    n_virtual = len(graph.edges) - n_real
    print(f"Built graph: {len(graph.edges)} total edges "
          f"({n_real} real STRING edges, {n_virtual} virtual-node edges)")
    save_ppi_edges(graph.edges, OUT_PATH)
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

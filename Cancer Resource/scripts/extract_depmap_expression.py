"""
One-time extraction: real DepMap 24Q4 expression values for the 14 curated
cell lines, into a small permanent local cache. Two independent modes,
writing two independent output files -- neither overwrites the other:

  --genes msigdb (default): the ~212 genes in the two gene sets already
    ingested by synlethality/ingest/msigdb.py (Hallmark ROS pathway, KEGG
    Hippo signaling) -- real expression-based cell-line similarity for
    Tier 2c nearest-neighbor prediction (synlethality/nearest_neighbor.py).
    Output: data/depmap/curated_cell_line_expression.json.

  --genes l1000_landmark: the real 978 L1000 landmark genes
    (synlethality/signature_space.py's canonical space) -- Phase 0 of the
    "Signature-transfer modifier x drug predictor" build order (2026-09-23):
    real cell-line baselines re-expressed in the same canonical space as
    LINCS drug signatures and modifier DEG signatures, for signature-
    transfer connectivity mapping. Output:
    data/depmap/curated_cell_line_expression_l1000landmark.json.

Source: DepMap 24Q4 Public (same Figshare+ release as ingest/depmap_prism.py,
article 27993248), file `OmicsExpressionProteinCodingGenesTPMLogp1.csv`
(506MB, log2(TPM+1) values, real). This script never keeps that full file
locally -- it streams it directly from Figshare's own download URL,
extracts only the 14 curated cell lines' rows (matched by their real
DepMap ModelID, from Model.csv) and only the requested gene set's columns.

Real outcome (2026-09-23, both modes): 13 of the 14 curated cell lines have
a real expression profile in this release. MCF-10A does not -- left absent,
not guessed or imputed (consistent with it being the one non-malignant,
immortalized line in the curated panel; DepMap's own omics profiling
coverage is not uniform across all catalogued models).

Usage: python scripts/extract_depmap_expression.py <figshare_download_url> [--genes msigdb|l1000_landmark]
The download URL for the current release's expression file (verified
2026-09-23): https://ndownloader.figshare.com/files/51065489
"""

import csv
import json
import re
import sys

from synlethality import config
from synlethality.ingest.depmap_prism import CELL_LINE_STRIPPED_NAME

MODEL_CSV = f"{config.DATA_DIR}/depmap/Model.csv"
GENE_SETS_CACHE = f"{config.DATA_DIR}/msigdb/gene_sets_cache.json"
OUT_PATHS = {
    "msigdb": f"{config.DATA_DIR}/depmap/curated_cell_line_expression.json",
    "l1000_landmark": f"{config.DATA_DIR}/depmap/curated_cell_line_expression_l1000landmark.json",
}


def real_ach_ids() -> dict[str, str]:
    """Our curated cell_line_id -> real DepMap ModelID, read directly from
    a real download of Model.csv (not hardcoded) -- reuses the same
    StrippedCellLineName mapping ingest/depmap_prism.py already verified."""
    stripped_to_ours = {v: k for k, v in CELL_LINE_STRIPPED_NAME.items()}
    ach_map = {}
    with open(MODEL_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stripped = row.get("StrippedCellLineName")
            if stripped in stripped_to_ours:
                ach_map[stripped_to_ours[stripped]] = row["ModelID"]
    return ach_map


def _wanted_genes(mode: str) -> set[str]:
    if mode == "msigdb":
        with open(GENE_SETS_CACHE, encoding="utf-8") as f:
            gene_sets = json.load(f)
        wanted = set()
        for rec in gene_sets.values():
            wanted.update(rec["genes"])
        return wanted
    if mode == "l1000_landmark":
        from synlethality.signature_space import CANONICAL_SYMBOLS
        return set(CANONICAL_SYMBOLS)
    raise ValueError(f"Unknown --genes mode {mode!r}; choose msigdb or l1000_landmark.")


def main(download_url: str, mode: str = "msigdb"):
    ach_map = real_ach_ids()
    ach_to_ours = {v: k for k, v in ach_map.items()}
    out_path = OUT_PATHS[mode]

    wanted_genes = _wanted_genes(mode)
    print(f"[{mode}] wanted {len(wanted_genes)} genes", file=sys.stderr)

    import requests

    result: dict[str, dict[str, float]] = {}
    with requests.get(download_url, stream=True, timeout=600) as r:
        r.raise_for_status()
        lines = r.iter_lines(decode_unicode=True, chunk_size=1024 * 1024)
        header = next(lines)
        cols = header.split(",")[1:]
        keep_idx = []
        for i, c in enumerate(cols):
            m = re.match(r"^(.*) \(\d+\)$", c)
            symbol = m.group(1) if m else c
            if symbol in wanted_genes:
                keep_idx.append((i, symbol))
        print(f"[{mode}] matched {len(keep_idx)} of {len(wanted_genes)} wanted genes in header", file=sys.stderr)

        found = 0
        for line in lines:
            if not line:
                continue
            model_id = line.split(",", 1)[0]
            if model_id in ach_to_ours:
                values = line.split(",")[1:]
                our_id = ach_to_ours[model_id]
                result[our_id] = {symbol: float(values[i]) for i, symbol in keep_idx if values[i]}
                found += 1
                print(f"[{mode}] found {our_id} ({model_id})", file=sys.stderr)
                if found == len(ach_map):
                    break

    missing = sorted(set(ach_map) - set(result))
    if missing:
        print(f"[{mode}] Not found in this release (left absent, not guessed): {missing}", file=sys.stderr)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(f"[{mode}] Wrote real expression data for {len(result)} cell lines to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_depmap_expression.py <figshare_download_url> [--genes msigdb|l1000_landmark]")
        sys.exit(1)
    url = sys.argv[1]
    genes_mode = "msigdb"
    if "--genes" in sys.argv:
        genes_mode = sys.argv[sys.argv.index("--genes") + 1]
    main(url, genes_mode)

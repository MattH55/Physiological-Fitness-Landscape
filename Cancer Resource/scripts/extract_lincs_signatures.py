"""
One-time extraction: real LINCS L1000 Level 5 signatures for the curated
drugs matched in GSE70138 (LINCS Phase 2), into a small local JSON cache.

This script is NOT part of the repeatable ingestion pipeline -- it consumes
the full Level 5 GCTX matrix (GSE70138_Broad_LINCS_Level5_COMPZ_..., ~5.4GB
compressed, real data downloaded from NCBI GEO's ungated FTP, no clue.io
registration needed), which is far too large to keep as a permanent local
data file the way data/depmap/*.csv or data/prism/*.csv are. Run this once
against a local copy of that file, then delete the big file -- the small
output (data/lincs/curated_drug_signatures.json, ~tens of KB) is what
`synlethality/ingest/lincs_l1000.py`'s repeatable ingestion step actually
reads.

GCTX layout, verified empirically against the real downloaded file
2026-09-22 by matching array lengths to the matrix's actual shape (NOT
assumed from the "ROW"/"COL" HDF5 group names, which turn out to be
counter-intuitive in this file -- see below):
  /0/DATA/0/matrix   -- data matrix, actual shape (118050, 12328).
  /0/META/COL/id     -- 118,050 entries = **sig_id** strings (as bytes) --
                        despite the group being named "COL", its length
                        matches the matrix's *first* axis (rows, in numpy
                        terms), confirmed by indexing a known sig_id and
                        checking the returned vector's length against
                        /0/META/ROW/id's count (see below).
  /0/META/ROW/id     -- 12,328 entries = **pr_gene_id** strings (as bytes),
                        matching gene_info.txt's pr_gene_id column --
                        despite the group being named "ROW", its length
                        matches the matrix's *second* axis (columns).
  So: matrix[sig_position_in_COL_id, :] is the correct way to get one
  signature's full real gene vector (length 12328, ordered same as
  ROW/id) -- matrix[:, sig_position] (the naming-literal reading) would
  be reading the wrong axis entirely and was caught here before shipping,
  via an empirical length check, not trusted from the group names.
  No chunking (contiguous storage), so this per-signature row slice is a
  single fast contiguous read, not a scan of the whole 5.8GB matrix.

Only the 6 curated drugs with a real, verified pert_id match in
GSE70138_Broad_LINCS_pert_info (found 2026-09-22 by exact pert_iname match;
the other 7 curated drugs -- cisplatin, oxaliplatin, carboplatin,
cyclophosphamide, erastin, triapine, lomustine -- are not in this Phase 2
release; Phase 1 (GSE92742) might have more of them but at 21GB was not
pulled this session) are extracted, all in MCF7 at the top dose (10 uM) and
standard 24h timepoint (verified real sig_ids, not guessed), restricted to
the 978 "landmark" genes (pr_is_lm == 1 in gene_info) -- the directly
measured, most reliable readout, rather than the ~11,350 computationally
inferred genes.
"""

import csv
import json
import os
import sys

DRUG_SIG_IDS = {
    "metformin": "REP.A024_MCF7_24H:P13",
    "5-fluorouracil": "REP.A004_MCF7_24H:J19",
    "mitomycin-c": "REP.A019_MCF7_24H:I07",
    "doxorubicin": "REP.A026_MCF7_24H:L19",
    "paclitaxel": "REP.A009_MCF7_24H:H19",
    "temozolomide": "REP.A009_MCF7_24H:K01",
}
CELL_LINE = "MCF7"
DOSE = "10.0 um"
TIME = "24 h"
SOURCE_TAG = (
    "lincs:GSE70138 Level 5 COMPZ.MODZ (LINCS Phase 2, Broad Connectivity Map); "
    "MCF7, 10uM, 24h"
)


def main(gctx_path: str, gene_info_path: str, out_path: str):
    import h5py

    gene_id_to_symbol = {}
    with open(gene_info_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["pr_is_lm"] == "1":
                gene_id_to_symbol[row["pr_gene_id"]] = row["pr_gene_symbol"]

    with h5py.File(gctx_path, "r") as f:
        # Real, empirically-verified orientation (see module docstring):
        # META/COL/id (118050 entries) = sig_id, indexes matrix axis 0.
        # META/ROW/id (12328 entries) = pr_gene_id, indexes matrix axis 1.
        sig_ids = [s.decode("utf-8") for s in f["0/META/COL/id"][:]]
        gene_ids = [g.decode("utf-8") for g in f["0/META/ROW/id"][:]]
        sig_index = {sig: i for i, sig in enumerate(sig_ids)}
        gene_index = {gid: i for i, gid in enumerate(gene_ids)}
        landmark_positions = [
            (gene_index[gid], symbol)
            for gid, symbol in gene_id_to_symbol.items()
            if gid in gene_index
        ]
        landmark_positions.sort()
        matrix = f["0/DATA/0/matrix"]

        signatures = {}
        for drug_id, sig_id in DRUG_SIG_IDS.items():
            if sig_id not in sig_index:
                print(f"WARNING: {sig_id} not found in this file's signatures; skipping {drug_id}")
                continue
            row = sig_index[sig_id]
            row_data = matrix[row, :]  # one contiguous HDF5 read per drug, not the whole matrix
            gene_zscore = {
                symbol: float(row_data[pos])
                for pos, symbol in landmark_positions
            }
            signatures[drug_id] = {
                "sig_id": sig_id,
                "cell_line": CELL_LINE,
                "dose": DOSE,
                "time": TIME,
                "source": SOURCE_TAG,
                "gene_zscore": gene_zscore,
            }
            print(f"{drug_id}: extracted {len(gene_zscore)} landmark-gene z-scores from {sig_id}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(signatures, fh, indent=1)
    print(f"Wrote {len(signatures)} real drug signatures to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: extract_lincs_signatures.py <gctx_path> <gene_info_path> <out_path>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])

"""
Track B (Signature-transfer modifier x drug predictor build order, parallel
track): extract a real, broad LINCS Phase 1 (GSE92742) chemical-signature
reference set for Phase 2's domain-shift diagnostics.

Why this exists: Phase 0/the pre-existing `extract_lincs_signatures.py`
gave only 6 real chemical (drug) signatures (the curated drugs with a
match in GSE70138, LINCS Phase 2). That is nowhere near enough to fit a
real reference *distribution* of chemical signatures (Phase 2 needs a
PCA-then-Mahalanobis or k-NN density estimate in ~50 dims, which is not
identifiable from 6 points). GSE92742 (LINCS Phase 1) is ~4x larger and
supplies thousands of distinct real compounds.

**Disk-space-constrained extraction, not a full decompression**: the real
compressed Level5 matrix (`GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_
n473647x12328.gctx.gz`) is 21.3GB; decompressed HDF5 (float32/float64
matrix data, only lightly compressible) would likely exceed this
machine's ~34GB free disk space. Instead of decompressing to disk, this
script uses `indexed_gzip` to build a one-time, in-memory seek index over
the *compressed* file (a single sequential pass that discards decoded
bytes as it goes -- it never writes the ~80GB+ decompressed matrix to
disk), then opens that indexed, seekable stream directly as an h5py file
object. Only the requested rows (one per target signature) are ever
materialized, each a single row read as in the original Phase 2 script.

**Real target signature selection**: MCF7, pert_type=='trt_cp',
pert_time=='24' h, dose in [9, 11] uM (closest to 10 uM per compound) --
the exact same convention `extract_lincs_signatures.py` used for the 6
curated drugs, just applied broadly instead of to a hand-picked list.
6,204 distinct real compounds match (from GSE92742_Broad_LINCS_sig_info,
verified 2026-09-23), built by `_build_reference_targets` below and
cached at data/lincs_phase1_raw/phase1_reference_targets.json.

Usage: python scripts/extract_lincs_phase1_reference.py <gctx_gz_path> <out_path> [--limit N]
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import sys

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "lincs_phase1_raw")
SIG_INFO_PATH = os.path.join(RAW_DIR, "GSE92742_Broad_LINCS_sig_info.txt.gz")
GENE_INFO_PATH = os.path.join(RAW_DIR, "GSE92742_Broad_LINCS_gene_info.txt.gz")
TARGETS_CACHE = os.path.join(RAW_DIR, "phase1_reference_targets.json")

CELL_LINE = "MCF7"
PERT_TIME = "24"
DOSE_LO, DOSE_HI = 9.0, 11.0
SOURCE_TAG = (
    "lincs:GSE92742 Level 5 COMPZ.MODZ (LINCS Phase 1, Broad Connectivity "
    "Map); MCF7, ~10uM, 24h -- Track B reference set for Phase 2"
)


def build_reference_targets(sig_info_path: str = SIG_INFO_PATH) -> dict:
    """Real sig_id per distinct compound (pert_iname), MCF7/24h/~10uM,
    closest-to-10uM dose kept when a compound has more than one match."""
    targets: dict[str, tuple[str, float, str]] = {}
    with gzip.open(sig_info_path, "rt", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["pert_type"] != "trt_cp" or row["cell_id"] != CELL_LINE or row["pert_time"] != PERT_TIME:
                continue
            try:
                dose = float(row["pert_dose"])
            except ValueError:
                continue
            if not (DOSE_LO <= dose <= DOSE_HI):
                continue
            name = row["pert_iname"]
            prev = targets.get(name)
            if prev is None or abs(dose - 10.0) < abs(prev[1] - 10.0):
                targets[name] = (row["sig_id"], dose, row["pert_id"])
    return {name: {"sig_id": sid, "dose_um": dose, "pert_id": pid}
            for name, (sid, dose, pid) in targets.items()}


def load_landmark_genes(gene_info_path: str = GENE_INFO_PATH) -> dict[str, str]:
    """{pr_gene_id -> pr_gene_symbol} restricted to the 978 landmark
    genes, from GSE92742's own gene_info (real file, this series)."""
    mapping = {}
    with gzip.open(gene_info_path, "rt", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["pr_is_lm"] == "1":
                mapping[row["pr_gene_id"]] = row["pr_gene_symbol"]
    return mapping


def open_gctx_streaming(gz_path: str):
    """Open a real, still-gzip-compressed GCTX file as a seekable h5py
    File, without decompressing it to disk. `indexed_gzip` does one
    sequential pass over the compressed bytes to build a seek index
    (discarding decoded bytes as it goes -- O(1) disk, O(index) memory),
    then serves random-access reads by reseeking to the nearest indexed
    point and decoding forward only the needed span.

    Verified empirically (smoke-tested 2026-09-23 against a small local
    HDF5 file, round-tripped through gzip): h5py accepts the
    `IndexedGzipFile` directly as a Python file-like object once its
    index is fully built (`h5py.File` calls `seek(0, SEEK_END)` during
    open to get file size, which `indexed_gzip` refuses until the index
    covers the whole stream -- `build_full_index()` must run first).

    Real size math for GSE92742's Level5 matrix: 473,647 sigs x 12,328
    genes x 4 bytes (float32) = ~23.3GB decompressed, barely larger than
    the 21.3GB compressed file (float z-score data is high-entropy, so
    gzip buys little) -- at 16MB seek-point spacing that's ~1,450 index
    entries, ~32KB deflate-window state each, ~45MB of index memory. Cheap.
    """
    import h5py
    import indexed_gzip as igzip

    fileobj = igzip.IndexedGzipFile(gz_path, spacing=16 * 1024 * 1024)
    print("Building full seek index over the compressed stream (one "
          "sequential decompression pass, nothing written to disk)...")
    fileobj.build_full_index()
    print("Index built.")
    return h5py.File(fileobj, "r")


def main(gz_path: str, out_path: str, limit: int | None = None) -> int:
    if os.path.isfile(TARGETS_CACHE):
        with open(TARGETS_CACHE, encoding="utf-8") as fh:
            targets = json.load(fh)
    else:
        targets = build_reference_targets()
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(TARGETS_CACHE, "w", encoding="utf-8") as fh:
            json.dump(targets, fh)
    print(f"{len(targets)} real distinct-compound target signatures (MCF7, ~10uM, 24h)")

    if limit:
        targets = dict(list(targets.items())[:limit])
        print(f"--limit applied: extracting {len(targets)}")

    gene_id_to_symbol = load_landmark_genes()

    print("Opening real GCTX file via indexed_gzip (one-time index-build pass, "
          "no full decompression to disk)...")
    with open_gctx_streaming(gz_path) as f:
        sig_ids = [s.decode("utf-8") for s in f["0/META/COL/id"][:]]
        gene_ids = [g.decode("utf-8") for g in f["0/META/ROW/id"][:]]
        sig_index = {sig: i for i, sig in enumerate(sig_ids)}
        gene_index = {gid: i for i, gid in enumerate(gene_ids)}
        landmark_positions = sorted(
            (gene_index[gid], symbol)
            for gid, symbol in gene_id_to_symbol.items()
            if gid in gene_index
        )
        matrix = f["0/DATA/0/matrix"]
        print(f"Real matrix: {len(sig_ids)} signatures x {len(gene_ids)} genes, "
              f"hdf5 shape {matrix.shape}, "
              f"{len(landmark_positions)} landmark positions matched")
        # Phase 2's GCTX stored signatures on axis 0 (META/COL) and genes on
        # axis 1 (META/ROW). Abort before the row loop if this file differs.
        if matrix.shape[0] != len(sig_ids) or matrix.shape[1] != len(gene_ids):
            raise SystemExit(
                f"Unexpected GCTX orientation: shape {matrix.shape}, "
                f"COL/id {len(sig_ids)}, ROW/id {len(gene_ids)}"
            )
        if len(landmark_positions) < 900:
            raise SystemExit(
                f"Only {len(landmark_positions)} landmark genes matched; "
                "refusing to write a thin reference set."
            )

        signatures = {}
        n_missing = 0
        for i, (name, meta) in enumerate(targets.items()):
            sig_id = meta["sig_id"]
            if sig_id not in sig_index:
                n_missing += 1
                continue
            row = sig_index[sig_id]
            row_data = matrix[row, :]
            gene_zscore = {symbol: float(row_data[pos]) for pos, symbol in landmark_positions}
            signatures[name] = {
                "sig_id": sig_id,
                "pert_id": meta["pert_id"],
                "cell_line": CELL_LINE,
                "dose": f"{meta['dose_um']} um",
                "time": f"{PERT_TIME} h",
                "source": SOURCE_TAG,
                "gene_zscore": gene_zscore,
            }
            if (i + 1) % 250 == 0:
                print(f"  {i + 1}/{len(targets)} extracted...")

    print(f"Extracted {len(signatures)} real signatures ({n_missing} sig_ids not found in matrix)")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(signatures, fh)
    print(f"Wrote {len(signatures)} real chemical reference signatures to {out_path} "
          f"({os.path.getsize(out_path):,} bytes)")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--limit")]
    limit_arg = next((a for a in sys.argv[1:] if a.startswith("--limit")), None)
    limit = int(limit_arg.split("=")[1]) if limit_arg and "=" in limit_arg else None
    if len(args) != 2:
        print("Usage: extract_lincs_phase1_reference.py <gctx_gz_path> <out_path> [--limit=N]")
        sys.exit(1)
    sys.exit(main(args[0], args[1], limit))

"""
Signature-transfer modifier x drug predictor -- Phase 0: signature space
alignment (build order, 2026-09-23, @Someone).

Everything downstream (Phase 1's modifier library, Phase 2's domain-shift
diagnostics, Phase 3's connectivity mapping, Phase 4's training corpus)
depends on modifier signatures, LINCS drug signatures, and cell-line
baselines living in one comparable space. This module is that space.

**Canonical space**: the L1000 978 landmark genes -- NOT the 212-gene
DepMap/MSigDB restriction `nearest_neighbor.py`'s Tier 2c similarity uses
(that restriction was a deliberate, documented simplification for a
different purpose -- cell-line similarity, not signature transfer -- and
stays as-is; this is a new, wider canonical space for this new purpose).

**Source of the canonical gene list, versioned, not hand-copied**:
`data/lincs/gene_info.txt` (real file, `GSE70138_Broad_LINCS_gene_info_
2017-03-06.txt`, the same LINCS Phase 2 gene annotation already used by
`scripts/extract_lincs_signatures.py`), filtered to `pr_is_lm == 1`. 978
real landmark genes, each with a real Entrez ID (`pr_gene_id`) and gene
symbol (`pr_gene_symbol`). Canonical order is Entrez-ID-sorted, for a
deterministic order independent of any one source file's row order.

**Normalization**: robust z-score (median/MAD, scaled by 1.4826 so MAD
approximates SD under normality) over the genes actually present in a
given signature -- the same transform applied identically regardless of
source, per the build order's "one comparable space" requirement. Missing
genes are `None`, never imputed or guessed.

**The 0.7 coverage gate**: any signature whose real overlap with the 978
landmark genes falls below 70% is refused registration outright (raises
`ValueError`), not silently registered with a warning -- Gate 0 of the
build order requires reporting per-source coverage and stopping if it's
inadequate, not proceeding on a thin projection.
"""

from __future__ import annotations

import csv
import os
import statistics

from synlethality import config

GENE_INFO_PATH = os.path.join(config.DATA_DIR, "lincs", "gene_info.txt")

#: Version string embedded in every registered signature's metadata, so a
#: later change to the canonical gene list (e.g. a newer LINCS gene_info
#: release) is a visible, trackable diff, not a silent shift.
CANONICAL_VERSION = "L1000-978-landmark-GSE70138-gene_info-2017-03-06"

MIN_COVERAGE = 0.7


def load_canonical_genes(path: str = GENE_INFO_PATH) -> list[tuple[str, str]]:
    """Real, deterministically-ordered (entrez_id, symbol) pairs for the
    978 L1000 landmark genes -- read directly from LINCS' own real gene
    annotation file (pr_is_lm == 1), sorted by Entrez ID. Never hardcoded:
    if this file is ever refreshed, the canonical order and CANONICAL_
    VERSION are the only two things that need updating together."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"{path} not found. This is LINCS' own real gene_info.txt "
            "(GSE70138_Broad_LINCS_gene_info_2017-03-06.txt), already "
            "downloaded once for scripts/extract_lincs_signatures.py -- "
            "copy it here (or re-download from the GSE70138 supplementary "
            "files on NCBI GEO's own ungated FTP) before using this module."
        )
    genes = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["pr_is_lm"] == "1":
                genes.append((row["pr_gene_id"], row["pr_gene_symbol"]))
    genes.sort(key=lambda g: int(g[0]))
    if len(genes) != 978:
        raise ValueError(
            f"Expected 978 real L1000 landmark genes, found {len(genes)} in "
            f"{path} -- the source file doesn't match what this module was "
            "built against; verify before trusting any downstream result."
        )
    return genes


CANONICAL_GENES = load_canonical_genes()
CANONICAL_SYMBOLS = [symbol for _, symbol in CANONICAL_GENES]
CANONICAL_ENTREZ = [entrez for entrez, _ in CANONICAL_GENES]


def to_canonical(signature: dict[str, float]) -> dict:
    """Project a real signature (gene_symbol -> value, any source/subset,
    any gene count) onto the canonical 978-landmark order.

    Returns {"vector": [float|None]*978 (None where the source signature
    doesn't cover that landmark gene), "coverage": float in [0,1],
    "n_present": int, "n_total": 978, "canonical_version": str}. Never
    imputes a missing gene's value -- a caller that needs a dense vector
    (e.g. a model's feature pipeline) must decide its own missing-value
    policy explicitly, not inherit a silent default from here.
    """
    vector = [signature.get(symbol) for symbol in CANONICAL_SYMBOLS]
    n_present = sum(1 for v in vector if v is not None)
    return {
        "vector": vector,
        "coverage": n_present / len(CANONICAL_SYMBOLS),
        "n_present": n_present,
        "n_total": len(CANONICAL_SYMBOLS),
        "canonical_version": CANONICAL_VERSION,
    }


def normalize_z(vector: list[float | None]) -> list[float | None]:
    """Robust z-score (median/MAD) over the present values only -- the same
    transform applied identically to every source, per the build order's
    'one comparable space' requirement. Entries that were None (missing
    from the source signature) stay None; not zero-filled, not imputed.
    Raises ValueError if fewer than 2 real values are present (nothing to
    normalize against)."""
    present = [v for v in vector if v is not None]
    if len(present) < 2:
        raise ValueError(
            f"Need >=2 present values to normalize; got {len(present)}.")
    med = statistics.median(present)
    mad = statistics.median(abs(v - med) for v in present)
    scale = 1.4826 * mad if mad > 0 else 1e-9
    return [None if v is None else (v - med) / scale for v in vector]


def register_signature(signature: dict[str, float], source_label: str) -> dict:
    """Real, end-to-end Phase 0 registration: project to canonical space,
    normalize, and refuse (raise ValueError) below MIN_COVERAGE -- 'refuse
    to register any signature below 0.7 [landmark coverage]' per the build
    order. `source_label` is free text identifying provenance (e.g.
    'lincs:doxorubicin', 'geo:GSE153830:mcf7_glucose_hippo') and is carried
    through into the returned dict for downstream reporting."""
    proj = to_canonical(signature)
    if proj["coverage"] < MIN_COVERAGE:
        raise ValueError(
            f"{source_label}: landmark coverage {proj['coverage']:.3f} "
            f"({proj['n_present']}/{proj['n_total']}) is below the "
            f"required {MIN_COVERAGE} -- refusing to register (Phase 0 "
            "Gate 0)."
        )
    proj["normalized_vector"] = normalize_z(proj["vector"])
    proj["source_label"] = source_label
    return proj

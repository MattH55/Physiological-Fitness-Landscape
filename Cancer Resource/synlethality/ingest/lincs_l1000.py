"""
Ingestion step: LINCS L1000 drug-induced gene expression signatures.

Real, working implementation (2026-09-22) for the **6 curated drugs**
matched by exact `pert_iname` lookup against LINCS Phase 2's own compound
registry (metformin, 5-fluorouracil, mitomycin-c, doxorubicin, paclitaxel,
temozolomide) -- the other 7 curated drugs (cisplatin, oxaliplatin,
carboplatin, cyclophosphamide, erastin, triapine, lomustine) are not in this
Phase 2 release; LINCS Phase 1 (GEO GSE92742) might cover more of them but
its Level 5 file is ~21GB and was not pulled this session (documented
limitation, not silently skipped).

**Where the real data came from, and why not clue.io**: clue.io (the
Broad's own LINCS portal) requires free account registration. The
identical Level 5 (moderated z-score, "COMPZ.MODZ") consensus signature
data is separately mirrored on NCBI GEO's own ungated FTP as GSE70138
(Phase 2) / GSE92742 (Phase 1) -- no login needed, verified 2026-09-22 by a
direct unauthenticated download. GSE70138's Level 5 file
(GSE70138_Broad_LINCS_Level5_COMPZ_n118050x12328_2017-03-06.gctx.gz) is
5.4GB -- too large to keep as a permanent local data file the way
data/depmap/*.csv or data/prism/*.csv are, so it was processed once by
`scripts/extract_lincs_signatures.py` (real HDF5/GCTX parsing via h5py,
column-indexed reads -- not a full-matrix load) into a small, permanent
local cache: `data/lincs/curated_drug_signatures.json`. That extraction
script, not this ingestion step, is what needs the 5.4GB file; this step
only needs its small output.

**What's captured**: for each of the 6 matched drugs, the real signature at
MCF7, 10 uM, 24h (the top dose available, chosen as the single most
detectable representative signature rather than pulling the full 6-point
dose series) -- restricted to the 978 "landmark" genes (directly measured,
not the ~11,350 computationally inferred ones, per LINCS' own
`pr_is_lm`/`pr_is_bing` gene tiers). MCF7 was chosen deliberately: it's the
one cell line where a real modifier-side signature already exists (the
GSE153830 glucose-deprivation DEG table, see ingest/geo_modifiers.py's
`mcf7_glucose_hippo` entry) -- so this is the drug-side half of the only
(modifier, cell_line) pair this codebase can currently run a genuine, real
`signature_correlation.xsum_correlation` against on both sides. See
synlethality/signature_correlation.py's `correlate_modifier_drug` for that.

Loads into `drug.induced_expression_signature_ref` (a pointer string, e.g.
"lincs:REP.A024_MCF7_24H:P13"), not a full copy of the L1000 dataset.

Status: real for the 6 drugs in DRUG_SIGNATURE_CACHE; extract() raises
NotImplementedError for any drug_id not in the cache (e.g. a bulk DepMap
drug, or one of the 7 curated drugs LINCS Phase 2 doesn't cover) -- no
fabricated signature refs are ever written; an uncovered drug keeps
induced_expression_signature_ref = NULL.
"""

from __future__ import annotations

import json
import os

from synlethality import config
from synlethality.ingest.base import IngestionStep
from synlethality.models import Drug

DATA_DIR = os.path.join(config.DATA_DIR, "lincs")
CACHE_PATH = os.path.join(DATA_DIR, "curated_drug_signatures.json")


class LincsL1000Ingest(IngestionStep):
    step_name = "lincs_l1000"
    source_study_tag = "lincs:GSE70138-phase2-gctx"

    def __init__(self, cache_path: str = CACHE_PATH):
        self.cache_path = cache_path

    def extract(self) -> list[dict]:
        if not os.path.isfile(self.cache_path):
            raise NotImplementedError(
                f"{self.cache_path} not found. Run "
                "scripts/extract_lincs_signatures.py against a local copy of "
                "GSE70138_Broad_LINCS_Level5_COMPZ_n118050x12328_2017-03-06.gctx "
                "(downloaded from "
                "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE70nnn/GSE70138/suppl/, "
                "no clue.io registration needed) first -- see module docstring."
            )
        with open(self.cache_path, encoding="utf-8") as fh:
            cache = json.load(fh)
        return [
            {"drug_id": drug_id, "sig_id": rec["sig_id"], "cell_line": rec["cell_line"],
             "dose": rec["dose"], "time": rec["time"], "source": rec["source"]}
            for drug_id, rec in cache.items()
        ]

    def transform(self, raw: list[dict]) -> list[dict]:
        for r in raw:
            r["induced_expression_signature_ref"] = f"lincs:{r['sig_id']}"
        return raw

    def load(self, session, rows: list[dict]) -> int:
        n = 0
        for r in rows:
            drug = session.query(Drug).filter_by(drug_id=r["drug_id"]).one_or_none()
            if drug is None:
                # Real drug_ids only -- this step never mints a new Drug
                # identity for a signature ref (unlike the general spec
                # contract sketched in earlier revisions of this file).
                continue
            drug.induced_expression_signature_ref = r["induced_expression_signature_ref"]
            n += 1
        return n


def load_gene_signature(drug_id: str, cache_path: str = CACHE_PATH) -> dict[str, float]:
    """Real landmark-gene z-score signature (gene_symbol -> z-score) for
    `drug_id`, from the cache LincsL1000Ingest reads. Raises
    FileNotFoundError/KeyError if not covered -- callers must not fall back
    to a fabricated signature."""
    with open(cache_path, encoding="utf-8") as fh:
        cache = json.load(fh)
    return cache[drug_id]["gene_zscore"]

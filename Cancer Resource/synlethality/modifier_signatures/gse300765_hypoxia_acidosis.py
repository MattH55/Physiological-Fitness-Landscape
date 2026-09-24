"""
Modifier signature parser: GSE300765 -- "Acidosis and hypoxia responsive
gene expression profiles of U87MG glioblastoma cells" (pmid:41673170,
Belting lab, Lund University; Series public Jan 04 2026; real Illumina
HumanHT-12 V4.0, GPL10558 -- the platform probe_annotation.py already
maps centrally).

Sourced 2026-09 via a live GEO DataSets (E-utilities) search specifically
for the build order's Phase 1 priority #1 class -- hypoxia -- after the
GSE291296 lesson (a series previously listed here as hypoxia that turned
out not to be; every candidate is now verified end-to-end against its own
Series title/summary/overall_design *and* sample-level characteristics
before a parser is written).

**Design (verified against the real series matrix's own
`!Sample_characteristics_ch1` treatment fields)**: U87MG glioblastoma
(curated line U87MG_CENTRAL_NERVOUS_SYSTEM), 6 arms x 3 biological
replicates (GSM9068191-208):
  - `hox`   "Hypoxia (1 % O2) 48 h"      vs `nox`      "Normoxia (21 % O2) 48 h"
  - `aapH64` "Acidosis (pH 6.4) 48 h"     vs `aactrl74` "Neutral pH (pH 7.4) 48 h"
  - `selpH647` "Acidosis (pH 6.4) 10 weeks" (adaptation) vs `selctrlpH74`
    "Neutral pH (pH 7.4) 10 weeks"
All three comparisons have complete dose metadata (level + duration) from
the series' own sample annotations -- no paper-side lookup needed.

**Data**: `GSE300765_series_matrix.txt.gz` (submitter-processed with
limma::neqc background correction/normalization per the series' own
`!Sample_data_processing`; real value range 4.18..14.49 = log2 scale),
so per-probe log2FC is the plain difference of replicate means, median
across probes per symbol -- the shared `common.py` computation.
"""

from __future__ import annotations

import os

from synlethality import config
from synlethality.modifier_signatures.common import (
    load_and_collapse_series_matrix,
    make_record,
)

DATA_PATH = os.path.join(
    config.DATA_DIR, "geo", "GSE300765", "GSE300765_series_matrix.txt.gz")
GPL_ID = "GPL10558"
ACCESSION = "GSE300765"
CITATION = "pmid:41673170"
CELL_LINE_ID = "U87MG_CENTRAL_NERVOUS_SYSTEM"
CELL_LINE_NAME = "U87MG"

#: Real comparison arms (sample-title prefixes verbatim from the series
#: matrix header) with their real doses from the sample characteristics.
ARMS = [
    {
        "treat": ["U87_hox_1", "U87_hox_2", "U87_hox_3"],
        "ctrl": ["U87_nox_1", "U87_nox_2", "U87_nox_3"],
        "signature_id": "gse300765_u87_hypoxia1pct48h",
        "modifier_class": "hypoxic",
        "condition_id": "hypoxia_1pct_o2_48h",
        "modifier_label": "Hypoxia (1% O2, 48 h) vs normoxia (21% O2)",
        "dose": {
            "modality": "hypoxic",
            "unit": "% O2",
            "o2_percent": 1.0,
            "control_o2_percent": 21.0,
            "duration_hr": 48.0,
        },
        "timepoint_hr": 48.0,
    },
    {
        "treat": ["U87_aapH64_1", "U87_aapH64_2", "U87_aapH64_3"],
        "ctrl": ["U87_aactrl74_1", "U87_aactrl74_2", "U87_aactrl74_3"],
        "signature_id": "gse300765_u87_acidosis_ph64_48h",
        "modifier_class": "acidotic",
        "condition_id": "acidosis_ph6.4_48h",
        "modifier_label": "Acute acidosis (pH 6.4, 48 h) vs pH 7.4",
        "dose": {
            "modality": "acidotic",
            "unit": "pH",
            "ph": 6.4,
            "control_ph": 7.4,
            "duration_hr": 48.0,
        },
        "timepoint_hr": 48.0,
    },
    {
        "treat": ["U87_selpH647_1", "U87_selpH647_2", "U87_selpH647_3"],
        "ctrl": ["U87_selctrlpH74_1", "U87_selctrlpH74_2", "U87_selctrlpH74_3"],
        "signature_id": "gse300765_u87_acidosis_ph64_10wk",
        "modifier_class": "acidotic",
        "condition_id": "acidosis_adaptation_ph6.4_10weeks",
        "modifier_label": "Chronic acidosis adaptation (pH 6.4, 10 weeks) vs pH 7.4",
        "dose": {
            "modality": "acidotic",
            "unit": "pH",
            "ph": 6.4,
            "control_ph": 7.4,
            "duration_hr": 10 * 7 * 24.0,  # 10 weeks = 1680 h
        },
        "timepoint_hr": 10 * 7 * 24.0,
    },
]


def parse(data_path: str = DATA_PATH, probe_map_path: str | None = None) -> list[dict]:
    """Real hypoxia + acidosis (acute & chronic) DEG signatures in U87MG
    (3 records)."""
    if not os.path.isfile(data_path):
        raise FileNotFoundError(
            f"{data_path} not found. Download the real "
            "GSE300765_series_matrix.txt.gz from "
            "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE300nnn/GSE300765/matrix/ "
            "(no gate) and place it there."
        )
    records = []
    for arm in ARMS:
        gene_log2fc, n_treat, n_ctrl = load_and_collapse_series_matrix(
            data_path, GPL_ID, arm["treat"], arm["ctrl"], scale="log2",
            probe_map_path=probe_map_path,
        )
        records.append(make_record(
            signature_id=arm["signature_id"],
            modifier_class=arm["modifier_class"],
            condition_id=arm["condition_id"],
            modifier_label=arm["modifier_label"],
            cell_line_id=CELL_LINE_ID,
            cell_line_name=CELL_LINE_NAME,
            dose=arm["dose"],
            timepoint_hr=arm["timepoint_hr"],
            citation=CITATION,
            geo_accession=ACCESSION,
            platform=GPL_ID,
            n_treatment_samples=n_treat,
            n_control_samples=n_ctrl,
            data_source=(
                "GSE300765_series_matrix.txt.gz (submitter-processed "
                "limma::neqc, log2 scale); per-probe difference of replicate "
                "means, median across probes per symbol"
            ),
            gene_log2fc=gene_log2fc,
        ))
    return records

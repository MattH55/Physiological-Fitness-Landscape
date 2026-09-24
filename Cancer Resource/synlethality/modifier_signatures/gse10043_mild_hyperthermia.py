"""
Modifier signature parser: GSE10043 -- "Identification of genes responsive
to mild hyperthermia in human leukemia U937 cells" (pmid:18608577; real
Affymetrix HG-U133A, GPL96).

One of the three series `probe_annotation.py` was built to unblock; the
probe->symbol mapping comes from the real, centrally-downloaded GPL96
`.annot.gz`.

**Protocol (verified 2026-09 against the live Series record)**: U937 cells
treated with mild hyperthermia, **41 degC for 30 min**, then incubated
**3 h at 37 degC** before RNA preparation; non-treated cells as control.
2 treatment + 2 control real replicates (GSM253743-746), exactly as the
series' own sample sheet records.

**Data**: `GSE10043_series_matrix.txt.gz` (GEO's submitter-processed
matrix, "GeneChip Analysis Suite" = MAS5-era processing; real value range
0.145..47131.5 = linear-scale signal), so per-probe log2FC is
log2((mean_treat + 1)/(mean_ctrl + 1)), median across probe sets per
symbol -- the shared `common.py` computation.

Thermal dose in CEM43 (Sapareto-Dewey): CEM43(41 degC, 30 min)
= 30 * 0.25^(43-41) = 1.875 -- a genuinely *mild* thermal dose, roughly
two orders of magnitude below GSE48398's 45 degC shock (120 CEM43), which
is exactly the dose diversity Phase 1 wants in the thermal class.
"""

from __future__ import annotations

import os

from synlethality import config
from synlethality.modifier_signatures.common import (
    cem43,
    load_and_collapse_series_matrix,
    make_record,
)

DATA_PATH = os.path.join(
    config.DATA_DIR, "geo", "GSE10043", "GSE10043_series_matrix.txt.gz")
GPL_ID = "GPL96"
ACCESSION = "GSE10043"
CITATION = "pmid:18608577"

#: Real protocol from the Series record's own overall_design.
HEAT_TEMP_C = 41.0
DURATION_HR = 0.5          # 30 min at 41 degC
RECOVERY_HR = 3.0          # then 3 h at 37 degC before RNA
TIMEPOINT_HR = DURATION_HR + RECOVERY_HR

#: Real sample titles, verbatim from the series matrix header.
TREAT_TITLES = [
    "U937 cells treated with mild hyperthermia (treatment-1)",
    "U937 cells treated with mild hyperthermia (treatment-2)",
]
CTRL_TITLES = [
    "U937 cells treated with mild hyperthermia (control-1)",
    "U937 cells treated with mild hyperthermia (control-2)",
]


def parse(data_path: str = DATA_PATH, probe_map_path: str | None = None) -> list[dict]:
    """Real mild-hyperthermia DEG signature in U937 (1 record)."""
    if not os.path.isfile(data_path):
        raise FileNotFoundError(
            f"{data_path} not found. Download the real "
            "GSE10043_series_matrix.txt.gz from "
            "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE10nnn/GSE10043/matrix/ "
            "(no gate) and place it there."
        )
    gene_log2fc, n_treat, n_ctrl = load_and_collapse_series_matrix(
        data_path, GPL_ID, TREAT_TITLES, CTRL_TITLES, scale="linear",
        probe_map_path=probe_map_path,
    )
    return [make_record(
        signature_id="gse10043_u937_mildhyperthermia41c30min",
        modifier_class="thermal",
        condition_id="mild_hyperthermia_41c_30min_rna+3h",
        modifier_label=(
            f"Mild hyperthermia ({HEAT_TEMP_C:.0f}C, {int(DURATION_HR * 60)} min), "
            f"RNA {RECOVERY_HR:.0f} h post-exposure, vs untreated control"
        ),
        cell_line_id="U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE",
        cell_line_name="U937",
        dose={
            "modality": "thermal",
            "unit": "CEM43",
            "value": cem43(HEAT_TEMP_C, DURATION_HR * 60),
            "temperature_c": HEAT_TEMP_C,
            "duration_hr": DURATION_HR,
            "recovery_hr": RECOVERY_HR,
        },
        timepoint_hr=TIMEPOINT_HR,
        citation=CITATION,
        geo_accession=ACCESSION,
        platform=GPL_ID,
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source=(
            "GSE10043_series_matrix.txt.gz (submitter-processed MAS5-era "
            "signal, linear scale); per-probe log2 ratio of replicate means, "
            "median across probe sets per symbol"
        ),
        gene_log2fc=gene_log2fc,
    )]

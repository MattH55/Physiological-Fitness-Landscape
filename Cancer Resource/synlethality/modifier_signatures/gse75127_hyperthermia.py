"""
Modifier signature parser: GSE75127 -- "Identification of genes involved
in enhancement of hyperthermia sensitivity by knockdown of BAG3 in human
oral squamous cell carcinoma cells" (pmid:27245201 -- this pmid was
previously mis-attached to GSE48398 in an early draft of
gse48398_heat_shock.py; verified 2026-09 against both live Series
records, it belongs here). Real Affymetrix HG-U133 Plus 2.0, GPL570.

One of the three series `probe_annotation.py` was built to unblock.

**Design (verified 2026-09 against the live Series record and sample
sheet)**: HSC-3 oral squamous carcinoma cells, 4 arms x 2 replicates
(GSM1943667-74): siLuc control, siLuc + hyperthermia, siBAG3, siBAG3 +
hyperthermia. HT = **44 degC for 90 min**.

**What this parser extracts -- and what it deliberately doesn't**: the
clean non-pharmaceutical-modifier comparison is **HT-Control (siLuc + HT)
vs Control (siLuc, no heat)**: a real hyperthermia DEG signature in
luciferase-siRNA-matched cells, so the siRNA/transfection context is
identical across arms. The BAG3-knockdown comparisons (siBAG3 vs siLuc;
HT+siBAG3 vs HT+siLuc) are a *genetic* perturbation, not a non-
pharmaceutical modifier, and are excluded from this library by design --
recorded here so the exclusion is an explicit decision, not an oversight.

HSC-3 is **not** one of seed_data's 14 curated cell lines; cell_line_id
is None (recorded under its real study name) rather than mapped to
anything it isn't.

**Data**: `GSE75127_series_matrix.txt.gz` (submitter-processed with
affymetrix RMA, Expression Console 1.2.1.20; real value range
1.629..14.583 = already log2 scale), so per-probe log2FC is the plain
difference of replicate means, median across probe sets per symbol.

Thermal dose in CEM43 (Sapareto-Dewey): CEM43(44 degC, 90 min)
= 90 * 0.5^(43-44) = 180.
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
    config.DATA_DIR, "geo", "GSE75127", "GSE75127_series_matrix.txt.gz")
GPL_ID = "GPL570"
ACCESSION = "GSE75127"
CITATION = "pmid:27245201"

#: Real protocol from the Series record's own overall_design.
HEAT_TEMP_C = 44.0
DURATION_HR = 1.5          # 90 min at 44 degC
#: The Series record states no post-exposure recovery before RNA
#: preparation; timepoint is therefore the end of the exposure itself
#: (documented assumption, not a guessed recovery interval).
TIMEPOINT_HR = DURATION_HR

#: Real sample titles, verbatim from the series matrix header.
TREAT_TITLES = [
    "HT-Control (HT and siRNA for luciferase)-1",
    "HT-Control (HT and siRNA for luciferase)-2",
]
CTRL_TITLES = [
    "Control (siRNA for luciferase)-1",
    "Control (siRNA for luciferase)-2",
]


def parse(data_path: str = DATA_PATH, probe_map_path: str | None = None) -> list[dict]:
    """Real hyperthermia DEG signature in HSC-3, siLuc-matched arms (1 record)."""
    if not os.path.isfile(data_path):
        raise FileNotFoundError(
            f"{data_path} not found. Download the real "
            "GSE75127_series_matrix.txt.gz from "
            "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE75nnn/GSE75127/matrix/ "
            "(no gate) and place it there."
        )
    gene_log2fc, n_treat, n_ctrl = load_and_collapse_series_matrix(
        data_path, GPL_ID, TREAT_TITLES, CTRL_TITLES, scale="log2",
        probe_map_path=probe_map_path,
    )
    return [make_record(
        signature_id="gse75127_hsc3_hyperthermia44c90min",
        modifier_class="thermal",
        condition_id="hyperthermia_44c_90min",
        modifier_label=(
            f"Hyperthermia ({HEAT_TEMP_C:.0f}C, {int(DURATION_HR * 60)} min), "
            "luciferase-siRNA-matched arms, vs no-heat control"
        ),
        cell_line_id=None,
        cell_line_name="HSC-3",
        dose={
            "modality": "thermal",
            "unit": "CEM43",
            "value": cem43(HEAT_TEMP_C, DURATION_HR * 60),
            "temperature_c": HEAT_TEMP_C,
            "duration_hr": DURATION_HR,
            "context": "luciferase siRNA in both arms (BAG3-KD arms excluded)",
        },
        timepoint_hr=TIMEPOINT_HR,
        citation=CITATION,
        geo_accession=ACCESSION,
        platform=GPL_ID,
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source=(
            "GSE75127_series_matrix.txt.gz (submitter-processed RMA, log2 "
            "scale); per-probe difference of replicate means, median across "
            "probe sets per symbol"
        ),
        gene_log2fc=gene_log2fc,
    )]

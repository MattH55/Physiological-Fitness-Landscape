"""
Modifier signature parser: GSE70976 -- "Expression data of LoVo cells
treated by 10 uM asymmetric dimethylarginine (ADMA) for 96h in serum
starvation medium" (pmid:27180883; real Affymetrix HG-U133 Plus 2.0,
GPL570 -- centrally mapped by probe_annotation.py).

Sourced 2026-09 via a live GEO DataSets (E-utilities) search for the
build order's Phase 1 priority #1 class -- serum starvation -- and
verified end-to-end against the Series record's own design: "Human
derived LoVo cells were cultured in normal, serum free and serum free
medium plus ADMA (10 uM) for 96h ... grouped as CON, SF96, A96",
3-4 biological replicates per arm (GSM-level sample sheet verified).

**What this parser extracts -- and what it deliberately doesn't**: the
non-pharmaceutical-modifier comparison is **SF96 (serum-free, 96 h) vs
CON (normal medium)**: a real serum-starvation DEG signature in LoVo
colon adenocarcinoma cells. The A96 arm (ADMA, a small-molecule
metabolite treatment) is pharmacological, not a non-pharmaceutical
modifier -- excluded by design, same posture as GSE75127's BAG3-KD arms.

LoVo is **not** one of seed_data's 14 curated cell lines; cell_line_id
is None (recorded under its real study name) rather than mapped to
anything it isn't.

**Data**: `GSE70976_series_matrix.txt.gz` (submitter-processed; real
value range 0.083..46512.8 = linear-scale signal), so per-probe log2FC
is log2((mean_treat + 1)/(mean_ctrl + 1)), median across probe sets per
symbol -- the shared `common.py` computation.

Dose metadata (build order: the fasting/serum modality records level +
duration): 0% serum, 96 h.
"""

from __future__ import annotations

import os

from synlethality import config
from synlethality.modifier_signatures.common import (
    load_and_collapse_series_matrix,
    make_record,
)

DATA_PATH = os.path.join(
    config.DATA_DIR, "geo", "GSE70976", "GSE70976_series_matrix.txt.gz")
GPL_ID = "GPL570"
ACCESSION = "GSE70976"
CITATION = "pmid:27180883"

DURATION_HR = 96.0

#: Real sample titles, verbatim from the series matrix header (note the
#: double space after the comma in the serum-free titles -- exact match
#: is enforced by load_and_collapse_series_matrix).
TREAT_TITLES = [
    "Serum free 96h,  biological rep1",
    "Serum free 96h,  biological rep2",
    "Serum free 96h,  biological rep3",
]
CTRL_TITLES = [
    "Control cells, biological rep1",
    "Control cells, biological rep2",
    "Control cells, biological rep3",
]


def parse(data_path: str = DATA_PATH, probe_map_path: str | None = None) -> list[dict]:
    """Real serum-starvation DEG signature in LoVo (1 record)."""
    if not os.path.isfile(data_path):
        raise FileNotFoundError(
            f"{data_path} not found. Download the real "
            "GSE70976_series_matrix.txt.gz from "
            "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE70nnn/GSE70976/matrix/ "
            "(no gate) and place it there."
        )
    gene_log2fc, n_treat, n_ctrl = load_and_collapse_series_matrix(
        data_path, GPL_ID, TREAT_TITLES, CTRL_TITLES, scale="linear",
        probe_map_path=probe_map_path,
    )
    return [make_record(
        signature_id="gse70976_lovo_serumfree96h",
        modifier_class="serum_starvation",
        condition_id="serum_free_96h",
        modifier_label="Serum starvation (0% FBS, 96 h) vs normal medium",
        cell_line_id=None,
        cell_line_name="LoVo",
        dose={
            "modality": "serum_starvation",
            "unit": "% serum",
            "serum_percent": 0.0,
            "duration_hr": DURATION_HR,
            "context": "ADMA-treated arm excluded (pharmacological)",
        },
        timepoint_hr=DURATION_HR,
        citation=CITATION,
        geo_accession=ACCESSION,
        platform=GPL_ID,
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source=(
            "GSE70976_series_matrix.txt.gz (submitter-processed signal, "
            "linear scale); per-probe log2 ratio of replicate means, "
            "median across probe sets per symbol"
        ),
        gene_log2fc=gene_log2fc,
    )]

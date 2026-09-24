"""
Modifier signature parser: GSE153830 -- glucose deprivation /
beta-hydroxybutyrate (BHB), MCF-7 & T47D (Zhang et al. 2021,
pmid:33281976; RNA-seq FPKM matrix, not a microarray -- the one real
modifier source this project already had before Phase 1, registered in
Phase 0).

This parser does NOT recompute the DEG: it reuses the real, already-
computed per-gene log2FC tables in `data/geo/computed_deg_cache.json`
(written by `ingest/geo_modifiers.py`'s GEOModifierIngest from the
study's own published FPKM matrix -- see that module's docstring for the
computation and its documented deviation from a full DESeq2/edgeR
pipeline) and attaches the Phase 1 record schema's dose metadata. The
four (modifier, cell_line) keys and their real sample groups are defined
there, not duplicated here.

Dose metadata (build order: "duration and glucose nadir for fasting"):
  - glucose deprivation: 0.225 g/L glucose (vs 4.5 g/L control), 96 h
  - BHB (a fasting/CR-mimetic metabolite): 10 or 25 mM, 96 h, on the
    glucose-deprived 0.225 g/L baseline (i.e. the BHB arms isolate the
    BHB effect under glucose restriction -- control is the same
    glucose-deprived cells without BHB), per SAMPLE_GROUPS in
    ingest/geo_modifiers.py.
"""

from __future__ import annotations

import os

from synlethality import config
from synlethality.ingest.geo_modifiers import SAMPLE_GROUPS, load_deg_cache
from synlethality.modifier_signatures.common import make_record

FPKM_MATRIX_PATH = os.path.join(config.DATA_DIR, "geo", "GSE153830", "FPKM_matrix.txt")


def _real_sample_counts(group: dict) -> tuple[int, int]:
    """Real per-arm sample counts for a SAMPLE_GROUPS entry, read directly
    off the FPKM matrix's own header rows (Cell_Line / glucose / BHB) --
    the same matching logic as ingest/geo_modifiers.py's transform(). The
    computed DEG cache doesn't persist sample counts, so they are
    re-derived from the real matrix here; if the matrix isn't on disk this
    raises rather than recording any assumed count."""
    if not os.path.isfile(FPKM_MATRIX_PATH):
        raise FileNotFoundError(
            f"{FPKM_MATRIX_PATH} not found -- needed to count real "
            "treatment/control samples (see ingest/geo_modifiers.py)."
        )
    with open(FPKM_MATRIX_PATH, encoding="utf-8") as fh:
        fh.readline()  # sample ids
        cell_lines = fh.readline().rstrip("\n").split("\t")[2:]
        glucose = [float(v) for v in fh.readline().rstrip("\n").split("\t")[2:]]
        bhb = [float(v) for v in fh.readline().rstrip("\n").split("\t")[2:]]

    def _count(target: dict) -> int:
        return sum(
            1 for cl, g, b in zip(cell_lines, glucose, bhb)
            if cl == group["cell_line"] and g == target["glucose"] and b == target["bhb"]
        )

    n_treat = _count(group["treatment"])
    n_ctrl = _count(group["control"])
    if not n_treat or not n_ctrl:
        raise ValueError(
            f"No real samples matched {group['key']} "
            f"(treat={n_treat}, ctrl={n_ctrl}) -- SAMPLE_GROUPS no longer "
            "matches the real sample sheet."
        )
    return n_treat, n_ctrl

ACCESSION = "GSE153830"
CITATION = "pmid:33281976"
PLATFORM = "RNA-seq (study's own FPKM matrix)"

#: The four real (modifier, cell_line) records GSE153830 supports, with
#: their Phase 1 dose metadata. Keys match ingest/geo_modifiers.py's
#: SAMPLE_GROUPS entries exactly (auditable, not re-derived here).
RECORDS = [
    {
        "deg_key": "t47d_glucose_nrf2",
        "signature_id": "gse153830_t47d_glucose_deprivation",
        "condition_id": "glucose_deprivation_0.225gL_96h",
        "modifier_label": "Glucose deprivation (0.225 g/L, 96 h) vs 4.5 g/L",
        "dose": {
            "modality": "dietary_metabolic",
            "unit": "g/L glucose",
            "glucose_gL": 0.225,
            "control_glucose_gL": 4.5,
            "duration_hr": 96.0,
        },
    },
    {
        "deg_key": "mcf7_glucose_hippo",
        "signature_id": "gse153830_mcf7_glucose_deprivation",
        "condition_id": "glucose_deprivation_0.225gL_96h",
        "modifier_label": "Glucose deprivation (0.225 g/L, 96 h) vs 4.5 g/L",
        "dose": {
            "modality": "dietary_metabolic",
            "unit": "g/L glucose",
            "glucose_gL": 0.225,
            "control_glucose_gL": 4.5,
            "duration_hr": 96.0,
        },
    },
    {
        "deg_key": "mcf7_bhb10_null",
        "signature_id": "gse153830_mcf7_bhb10mm",
        "condition_id": "bhb_10mm_96h_on_glucose_deprivation",
        "modifier_label": "BHB 10 mM, 96 h, on glucose-deprived baseline",
        "dose": {
            "modality": "dietary_metabolic",
            "unit": "mM BHB",
            "bhb_mM": 10.0,
            "baseline_glucose_gL": 0.225,
            "duration_hr": 96.0,
        },
    },
    {
        "deg_key": "t47d_bhb25_null",
        "signature_id": "gse153830_t47d_bhb25mm",
        "condition_id": "bhb_25mm_96h_on_glucose_deprivation",
        "modifier_label": "BHB 25 mM, 96 h, on glucose-deprived baseline",
        "dose": {
            "modality": "dietary_metabolic",
            "unit": "mM BHB",
            "bhb_mM": 25.0,
            "baseline_glucose_gL": 0.225,
            "duration_hr": 96.0,
        },
    },
]


def parse() -> list[dict]:
    """Real GSE153830 modifier DEG signatures (4 records), re-emitted in
    the Phase 1 record schema from the existing computed DEG cache."""
    records = []
    for spec in RECORDS:
        cached = load_deg_cache(spec["deg_key"])
        group = SAMPLE_GROUPS[(cached["modifier_id"], cached["cell_line_id"])]
        n_treat, n_ctrl = _real_sample_counts(group)
        records.append(make_record(
            signature_id=spec["signature_id"],
            modifier_class="dietary_metabolic",
            condition_id=spec["condition_id"],
            modifier_label=spec["modifier_label"],
            cell_line_id=cached["cell_line_id"],
            cell_line_name=group["cell_line"].replace("_", "-"),
            dose=spec["dose"],
            timepoint_hr=spec["dose"]["duration_hr"],
            citation=CITATION,
            geo_accession=ACCESSION,
            platform=PLATFORM,
            n_treatment_samples=n_treat,
            n_control_samples=n_ctrl,
            data_source=cached["source"],
            gene_log2fc=cached["gene_log2fc"],
        ))
    return records

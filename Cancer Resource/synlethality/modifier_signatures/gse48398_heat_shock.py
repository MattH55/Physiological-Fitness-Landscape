"""
Modifier signature parser: GSE48398 -- "Gene expression profiles of
mammary epithelial and breast cancer cells following fever range
hyperthermia" (Bryan/Mitchell labs; Series submitted Jun 28 2013; real
Illumina HumanHT-12 V4.0, GPL10558).

**Protocol (verified 2026-09 against the live Series record, correcting
this parser's first draft)**: cells were subjected to **30 minutes** of
45 degC hyperthermic shock, then returned to conditioned media at 37
degC; **RNA was collected 4 hours after shock**. The first draft said
"1 h exposure, Zhang et al., pmid:27245201" -- both wrong: 1 h was not
the protocol, and pmid:27245201 is in fact the citation of *GSE75127*'s
own study (verified against both Series records); GSE48398's Series
record carries no linked publication as of this verification date, so
the citation is the GEO accession itself. Caught here before any
derived artifact propagated the mis-citation.

**Design (real, from the downloaded `non_normalized.txt`)**: 4 cell lines
(MCF-10A mammary epithelial; MCF-7, MDA-MB-231, MDA-MB-468 breast cancer)
x 2 conditions (37 degC control, 45 degC shock), 3-6 real replicates per
condition. Per-gene log2 fold-change: per Illumina probe,
log2((mean_heat + 1)/(mean_control + 1)) over the real replicate
intensities (linear-scale, non-normalized submitter values), then the
median across probes per gene symbol -- the shared `common.py`
computation, identical across this phase's microarray parsers. Real but
simplified DEG computation (no background correction / moderated
statistics on the non-normalized file) -- documented deviation, same
posture as GSE153830's own caveat in ingest/geo_modifiers.py.

Thermal dose in CEM43 (Sapareto-Dewey), the build order's standard unit
for the thermal modality: CEM43(45 degC, 30 min) = 30 * 0.5^(43-45) = 120.
"""

from __future__ import annotations

import os

from synlethality import config
from synlethality.modifier_signatures.common import (
    cem43,
    collapse_to_symbols,
    make_record,
    per_probe_log2fc,
)
from synlethality.probe_annotation import load_probe_map

DATA_PATH = os.path.join(config.DATA_DIR, "geo", "GSE48398", "non_normalized.txt")
GPL_ID = "GPL10558"
ACCESSION = "GSE48398"
CITATION = "geo:GSE48398"  # no linked publication on the Series record (verified 2026-09)

#: Real protocol from the Series record's own overall_design.
HEAT_TEMP_C = 45.0
CONTROL_TEMP_C = 37.0
DURATION_HR = 0.5          # 30 minutes at 45 degC
RECOVERY_HR = 4.0          # RNA collected 4 h after shock
TIMEPOINT_HR = DURATION_HR + RECOVERY_HR  # hours from exposure start to RNA

#: Column-prefix -> (curated cell-line id, study's own name).
CELL_LINES = {
    "MCF10A": ("MCF10A_BREAST", "MCF-10A"),
    "MCF7": ("MCF7_BREAST", "MCF-7"),
    "MDA231": ("MDAMB231_BREAST", "MDA-MB-231"),
    "MDA468": ("MDAMB468_BREAST", "MDA-MB-468"),
}


def _load_non_normalized(path: str):
    """GSE48398's submitter-processed file (not a standard series matrix):
    tab-separated, header 'ID_REF, <cell> <temp>oC rep<N>, ... p value ...',
    one row per Illumina probe. Returns (col_meta, {probe_id: [float|None]})
    where col_meta[i] is (cell_prefix, temp_c) or None for p-value columns."""
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")[1:]  # drop ID_REF
        col_meta = []
        for h in header:
            if h.endswith("p value"):
                col_meta.append(None)
                continue
            parts = h.split(" ")
            col_meta.append((parts[0], float(parts[1].replace("oC", ""))))
        rows: dict[str, list[float | None]] = {}
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if not parts[0]:
                continue
            rows[parts[0]] = [float(v) if v else None for v in parts[1:]]
    return col_meta, rows



def parse(data_path: str = DATA_PATH, probe_map_path: str | None = None) -> list[dict]:
    """Real per-cell-line 45 degC heat-shock DEG signatures (4 records)."""
    if not os.path.isfile(data_path):
        raise FileNotFoundError(
            f"{data_path} not found. Download the real "
            "GSE48398_non-normalized_data.txt.gz from "
            "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE48nnn/GSE48398/suppl/ "
            "(no gate) and place it there."
        )
    col_meta, rows = _load_non_normalized(data_path)
    probe_map = load_probe_map(GPL_ID, cache_path=probe_map_path)

    records = []
    for cell_prefix, (cell_line_id, cell_line_name) in CELL_LINES.items():
        treat_idx = [i for i, m in enumerate(col_meta)
                     if m and m[0] == cell_prefix and m[1] == HEAT_TEMP_C]
        ctrl_idx = [i for i, m in enumerate(col_meta)
                    if m and m[0] == cell_prefix and m[1] == CONTROL_TEMP_C]
        if not treat_idx or not ctrl_idx:
            raise ValueError(
                f"{ACCESSION}: no {cell_prefix} columns for "
                f"{HEAT_TEMP_C}/{CONTROL_TEMP_C} degC -- the parser's design "
                "no longer matches the real file."
            )
        probe_fc = per_probe_log2fc(rows, treat_idx, ctrl_idx, scale="linear")
        gene_log2fc = collapse_to_symbols(probe_fc, probe_map)
        records.append(make_record(
            signature_id=f"gse48398_{cell_prefix.lower()}_heat45c30min",
            modifier_class="thermal",
            condition_id="hyperthermia_45c_30min_rna+4h",
            modifier_label=(
                f"Heat shock ({HEAT_TEMP_C:.0f}C, {int(DURATION_HR * 60)} min), "
                f"RNA {RECOVERY_HR:.0f} h post-shock, vs 37C control"
            ),
            cell_line_id=cell_line_id,
            cell_line_name=cell_line_name,
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
            n_treatment_samples=len(treat_idx),
            n_control_samples=len(ctrl_idx),
            data_source=(
                "GSE48398_non-normalized_data.txt (submitter-processed, "
                "linear-scale Illumina intensities); per-probe log2 ratio of "
                "replicate means, median across probes per symbol"
            ),
            gene_log2fc=gene_log2fc,
        ))
    return records

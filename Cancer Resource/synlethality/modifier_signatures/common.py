"""
Shared machinery for the Phase 1 modifier-signature parsers (Signature-
transfer modifier x drug predictor build order, 2026-09): one parser module
per GEO series, each emitting canonical-space-ready DEG records with
complete dose metadata.

Everything every parser needs exactly once, per the build order's "shared
infrastructure, not per-series" rule:

- `load_series_matrix` -- real GEO `*_series_matrix.txt.gz` files (quoted
  SOFT-format TSV between the `!series_matrix_table_begin/end` markers).
  Missing values stay missing (None), never zero-filled.
- `per_probe_log2fc` / `collapse_to_symbols` -- the per-gene DEG
  computation used identically by every microarray parser: per probe,
  log2 fold-change of mean(treatment) vs mean(control) replicates, then
  the **median across the probes mapping to one gene symbol**. Scale is
  declared explicitly per series ('linear' -> log2((t+1)/(c+1));
  'log2' -> plain difference of means) after real inspection of each
  file's value range -- never auto-detected at runtime.
- `cem43` -- Sapareto-Dewey thermal dose, the build order's standard unit
  for the thermal modality.
- `make_record` -- the one record schema every parser emits, with Gate
  1's "complete dose metadata" enforced as a hard validation (a record
  with missing dose fields raises, it doesn't warn).
"""

from __future__ import annotations

import gzip
import math
import os
import statistics
from datetime import date

from synlethality.probe_annotation import load_probe_map

#: Processing version stamped into every record and the library manifest;
#: bump when the shared computation changes (provenance standing rule).
PROCESSING_VERSION = "modifier_signatures-1.0.0"

RECORD_REQUIRED_KEYS = (
    "signature_id", "modifier_class", "condition_id", "modifier_label",
    "cell_line_id", "cell_line_name", "dose", "timepoint_hr", "citation",
    "geo_accession", "platform", "n_treatment_samples", "n_control_samples",
    "processing", "data_source", "gene_log2fc",
)

#: Gate 1's "complete dose metadata", made explicit per modifier class:
#: the build order requires dose "in the standard unit for its modality"
#: (CEM43 thermal; O2% + duration hypoxia; duration + glucose nadir
#: fasting). pH + duration for acidosis and serum% + duration for serum
#: starvation follow the same pattern.
REQUIRED_DOSE_KEYS = {
    "thermal": {"unit", "value", "temperature_c", "duration_hr"},
    "hypoxic": {"unit", "o2_percent", "duration_hr"},
    "acidotic": {"unit", "ph", "duration_hr"},
    "dietary_metabolic": {"unit", "duration_hr"},
    "serum_starvation": {"unit", "serum_percent", "duration_hr"},
    # Human-physiology series. Fasting has no measured glucose nadir, cold is
    # not a CEM43 heat dose, and sauna temperature is air temperature.
    "fasting": {"unit", "duration_hr", "fasting_hr"},
    "meal_timing": {"unit", "duration_hr", "eating_window_hr"},
    "exercise": {"unit", "duration_hr"},
    "cold": {"unit", "temperature_c", "duration_hr"},
    "cold_immersion": {"unit", "duration_hr"},
    "local_heat": {"unit", "duration_hr"},
    "sauna": {"unit", "temperature_c", "duration_hr"},
}


def cem43(temp_c: float, duration_min: float) -> float:
    """Sapareto-Dewey Cumulative Equivalent Minutes at 43 degC -- the
    standard thermal dose unit (build order, Phase 1 item 2).
    CEM43 = t * R^(43 - T), R = 0.5 for T >= 43, R = 0.25 for T < 43."""
    r = 0.5 if temp_c >= 43.0 else 0.25
    return duration_min * (r ** (43.0 - temp_c))


def _open_text(path: str):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") \
        if path.endswith(".gz") else open(path, encoding="utf-8", errors="replace")


def load_series_matrix(path: str) -> tuple[list[str], dict[str, list[float | None]]]:
    """Parse a real GEO series-matrix file into (sample_titles,
    {probe_id -> [value per sample, None where empty]}). Quoted fields are
    unquoted; only rows between the table begin/end markers are read."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path} not found -- download the real "
                                f"{os.path.basename(path)} from GEO first (no gate).")
    sample_titles: list[str] = []
    rows: dict[str, list[float | None]] = {}
    in_table = False
    with _open_text(path) as fh:
        for line in fh:
            if line.startswith("!series_matrix_table_begin"):
                in_table = True
                continue
            if line.startswith("!series_matrix_table_end"):
                break
            if line.startswith("!Sample_title") and not sample_titles:
                sample_titles = [p.strip().strip('"') for p in line.rstrip("\n").split("\t")[1:]]
                continue
            if not in_table:
                continue
            parts = [p.strip().strip('"') for p in line.rstrip("\n").split("\t")]
            if not parts or parts[0] in ("ID_REF", ""):
                continue
            values = [float(v) if v not in ("", "null", "NA") else None for v in parts[1:]]
            rows[parts[0]] = values
    if not sample_titles or not rows:
        raise ValueError(f"{path}: no sample titles or data rows parsed -- "
                         "file doesn't look like a real GEO series matrix.")
    return sample_titles, rows


def per_probe_log2fc(
    rows: dict[str, list[float | None]],
    treat_idx: list[int],
    ctrl_idx: list[int],
    scale: str,
) -> dict[str, float]:
    """{probe_id -> log2 fold-change}, mean of treatment replicates vs
    mean of control replicates, per probe. `scale` is declared by the
    calling parser from real inspection of that series' value range:
    'linear' -> log2((t+1)/(c+1)); 'log2' -> t - c. Probes with no
    complete pair of means are dropped, never imputed."""
    if not treat_idx or not ctrl_idx:
        raise ValueError("Need >=1 treatment and >=1 control replicate.")
    if scale not in ("linear", "log2"):
        raise ValueError(f"scale must be 'linear' or 'log2', got {scale!r}")
    out = {}
    for probe_id, values in rows.items():
        treat = [values[i] for i in treat_idx if i < len(values) and values[i] is not None]
        ctrl = [values[i] for i in ctrl_idx if i < len(values) and values[i] is not None]
        if not treat or not ctrl:
            continue
        t_mean = sum(treat) / len(treat)
        c_mean = sum(ctrl) / len(ctrl)
        if scale == "log2":
            out[probe_id] = t_mean - c_mean
        else:
            out[probe_id] = math.log2((t_mean + 1.0) / (c_mean + 1.0))
    return out


def collapse_to_symbols(
    probe_log2fc: dict[str, float],
    probe_map: dict[str, str],
) -> dict[str, float]:
    """Median across the probes mapping to one gene symbol (robust to a
    dead or cross-hybridizing probe set); probes with no real annotation
    in `probe_map` are dropped, never carried as unnamed genes."""
    by_symbol: dict[str, list[float]] = {}
    for probe_id, fc in probe_log2fc.items():
        symbol = probe_map.get(probe_id)
        if not symbol:
            continue
        by_symbol.setdefault(symbol, []).append(fc)
    return {symbol: statistics.median(fcs) for symbol, fcs in by_symbol.items()}


def load_and_collapse_series_matrix(
    path: str,
    gpl_id: str,
    treat_titles: list[str],
    ctrl_titles: list[str],
    scale: str,
    probe_map_path: str | None = None,
) -> tuple[dict[str, float], int, int]:
    """Full real pipeline for one series-matrix comparison arm: parse
    matrix, match sample columns by exact title, per-probe log2FC,
    collapse to symbols via the central GPL probe map. Returns
    (gene_log2fc, n_treatment_samples, n_control_samples)."""
    sample_titles, rows = load_series_matrix(path)
    treat_idx = [i for i, t in enumerate(sample_titles) if t in treat_titles]
    ctrl_idx = [i for i, t in enumerate(sample_titles) if t in ctrl_titles]
    if len(treat_idx) != len(treat_titles) or len(ctrl_idx) != len(ctrl_titles):
        raise ValueError(
            f"{os.path.basename(path)}: expected {len(treat_titles)} treatment + "
            f"{len(ctrl_titles)} control columns, matched {len(treat_idx)} + "
            f"{len(ctrl_idx)}. Sample titles on file: {sample_titles!r} -- the "
            "parser's arm definition no longer matches the real sample sheet."
        )
    probe_fc = per_probe_log2fc(rows, treat_idx, ctrl_idx, scale)
    probe_map = load_probe_map(gpl_id, cache_path=probe_map_path)
    return collapse_to_symbols(probe_fc, probe_map), len(treat_idx), len(ctrl_idx)


def make_record(
    *,
    signature_id: str,
    modifier_class: str,
    condition_id: str,
    modifier_label: str,
    cell_line_id: str | None,
    cell_line_name: str,
    dose: dict,
    timepoint_hr: float,
    citation: str,
    geo_accession: str,
    platform: str,
    n_treatment_samples: int,
    n_control_samples: int,
    data_source: str,
    gene_log2fc: dict[str, float],
) -> dict:
    """The one Phase 1 record schema, with Gate 1's complete-dose-metadata
    requirement enforced: missing schema keys, missing modality dose
    fields, an empty signature, or a zero-sample arm all raise -- a
    record that can't carry complete dose metadata never reaches the
    library, per the build order's standing 'no placeholder' rule."""
    record = {
        "signature_id": signature_id,
        "modifier_class": modifier_class,
        "condition_id": condition_id,
        "modifier_label": modifier_label,
        "cell_line_id": cell_line_id,
        "cell_line_name": cell_line_name,
        "dose": dose,
        "timepoint_hr": timepoint_hr,
        "citation": citation,
        "geo_accession": geo_accession,
        "platform": platform,
        "n_treatment_samples": n_treatment_samples,
        "n_control_samples": n_control_samples,
        "processing": PROCESSING_VERSION,
        "data_source": data_source,
        "pulled": str(date.today()),
        "gene_log2fc": gene_log2fc,
    }
    missing = []
    for k in RECORD_REQUIRED_KEYS:
        v = record.get(k)
        if k == "cell_line_id":
            # Nullable by design: None = line not among seed_data's curated
            # ids (the record is then identified by its real study name in
            # cell_line_name) -- honest, versus mapping it to a curated line
            # it isn't. An empty string/dict is still an error.
            if v in ("", {}, []):
                missing.append(k)
        elif v in (None, "", {}, []):
            missing.append(k)
    if missing:
        raise ValueError(f"{signature_id}: incomplete record, missing {missing}")
    if modifier_class not in REQUIRED_DOSE_KEYS:
        raise ValueError(f"{signature_id}: unknown modifier_class {modifier_class!r}")
    dose_missing = REQUIRED_DOSE_KEYS[modifier_class] - set(dose)
    if dose_missing:
        raise ValueError(
            f"{signature_id}: incomplete dose metadata for {modifier_class} "
            f"(missing {sorted(dose_missing)}) -- Gate 1 refuses this record."
        )
    if modifier_class == "dietary_metabolic" and not (
        {"glucose_gL", "bhb_mM"} & set(dose)
    ):
        raise ValueError(
            f"{signature_id}: dietary_metabolic dose needs glucose_gL or "
            "bhb_mM (the build order's 'duration and glucose nadir')."
        )
    if n_treatment_samples < 1 or n_control_samples < 1:
        raise ValueError(f"{signature_id}: zero-sample arm.")
    return record


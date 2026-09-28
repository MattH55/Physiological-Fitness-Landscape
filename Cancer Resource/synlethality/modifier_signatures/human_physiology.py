"""Human fasting, exercise, cold, and sauna signatures.

Parsed from the GEO files downloaded 2026-09-24 into data/geo/. Each
contrast is the series' own before/after or condition labels. Cell lines
are human tissues, so cell_line_id is None.

GPL5175 and GPL17586 have no small .annot.gz. The probe id and the
Affymetrix gene_assignment column were read from GEO's platform data
table. GPL22321 is the Brainarray HGU133Plus2 ENTREZG CDF: the probeset
id is an Entrez gene id plus `_at`, mapped with NCBI gene_info.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import urllib.request

from synlethality import config
from synlethality.modifier_signatures.common import (
    load_and_collapse_series_matrix,
    make_record,
)

GEO = os.path.join(config.DATA_DIR, "geo")

PLATFORMS = os.path.join(config.DATA_DIR, "geo_platforms")


def _path(accession: str, filename: str) -> str:
    return os.path.join(GEO, accession, filename)


def _require(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path


def _by_title(accession, filename, gpl, treat_fn, ctrl_fn, scale, probe_map_path=None):
    path = _require(_path(accession, filename))
    from synlethality.modifier_signatures.common import load_series_matrix
    titles, _rows = load_series_matrix(path)
    treat = [t for t in titles if treat_fn(t)]
    ctrl = [t for t in titles if ctrl_fn(t)]
    if not treat or not ctrl:
        raise ValueError(f"{accession}: no samples matched the contrast")
    return load_and_collapse_series_matrix(
        path, gpl, treat, ctrl, scale, probe_map_path=probe_map_path)


def _mean(values):
    present = [v for v in values if v is not None and not math.isnan(v)]
    if not present:
        return None
    return sum(present) / len(present)


def _log2_ratio(treat, ctrl):
    if treat is None or ctrl is None:
        return None
    return math.log2((treat + 1.0) / (ctrl + 1.0))


def _id_to_symbol(accessions: list[str], cache_name: str, scopes: str) -> dict[str, str]:
    cache = os.path.join(GEO, "_id_maps", cache_name)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    known = {}
    if os.path.isfile(cache):
        known = json.load(open(cache, encoding="utf-8"))
    missing = [a for a in accessions if a not in known]
    url = "https://mygene.info/v3/query"
    for start in range(0, len(missing), 800):
        batch = missing[start:start + 800]
        body = json.dumps({
            "q": batch, "scopes": scopes, "fields": "symbol",
            "species": "human",
        }).encode()
        req = urllib.request.Request(
            url, data=body, headers={
                "Content-Type": "application/json",
                "User-Agent": "OpenSourceMed/1.0",
            },
        )
        payload = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
        for row in payload:
            query = row.get("query")
            symbol = row.get("symbol")
            if query and symbol and not row.get("notfound"):
                known[query] = symbol
            elif query:
                known[query] = ""
        json.dump(known, open(cache, "w", encoding="utf-8"))
    return {k: v for k, v in known.items() if v}


def _refseq_to_symbol(accessions: list[str]) -> dict[str, str]:
    return _id_to_symbol(accessions, "refseq_to_symbol.json", "refseq.rna")


def _ensembl_to_symbol(accessions: list[str]) -> dict[str, str]:
    return _id_to_symbol(accessions, "ensembl_to_symbol.json", "ensembl.gene")


def _record(**kwargs):
    kwargs.setdefault("cell_line_id", None)
    return make_record(**kwargs)


def _fasting_24h():
    genes, n_treat, n_ctrl = _by_title(
        "GSE55924", "GSE55924_series_matrix.txt.gz", "GPL10558",
        lambda t: "24h post-meal" in t,
        lambda t: "1,5h post-meal" in t,
        "log2",
    )
    return _record(
        signature_id="gse55924_muscle_fast24h_vs_1p5h",
        modifier_class="fasting",
        condition_id="fast_24h_vs_1.5h_postmeal",
        modifier_label="Skeletal muscle, 24 h vs 1.5 h after a meal, 12 men",
        cell_line_name="human skeletal muscle",
        dose={"unit": "hours", "duration_hr": 24.0, "fasting_hr": 24.0,
              "control": "1.5 h post-meal"},
        timepoint_hr=24.0,
        citation="pmid:25249505",
        geo_accession="GSE55924",
        platform="GPL10558",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source="GSE55924 series matrix, values already log2 (range about 7-15)",
        gene_log2fc=genes,
    )


def _treadmill():
    out = []
    specs = (
        ("gse3606_wbc_exhaustive_1h", "exhaustive", "past exhaustive", "before exhaustive"),
        ("gse3606_wbc_moderate_1h", "moderate", "past moderate", "before moderate"),
    )
    for sig_id, kind, treat_s, ctrl_s in specs:
        genes, n_treat, n_ctrl = _by_title(
            "GSE3606", "GSE3606_series_matrix.txt.gz", "GPL571",
            lambda t, s=treat_s: s in t,
            lambda t, s=ctrl_s: s in t,
            "linear",
        )
        out.append(_record(
            signature_id=sig_id,
            modifier_class="exercise",
            condition_id=f"treadmill_{kind}_1h_post",
            modifier_label=f"White blood cells, 1 h after {kind} treadmill exercise",
            cell_line_name="human white blood cells",
            dose={"unit": "hours_after_bout", "duration_hr": 1.0, "bout": kind},
            timepoint_hr=1.0,
            citation="pmid:16990507",
            geo_accession="GSE3606",
            platform="GPL571",
            n_treatment_samples=n_treat,
            n_control_samples=n_ctrl,
            data_source="GSE3606 series matrix, MAS5 linear signal",
            gene_log2fc=genes,
        ))
    return out


def _cold():
    genes, n_treat, n_ctrl = _by_title(
        "GSE156248", "GSE156248_series_matrix.txt.gz", "GPL11532",
        lambda t: "after 10 day cold" in t,
        lambda t: "before cold" in t,
        "log2",
    )
    return _record(
        signature_id="gse156248_muscle_cold10d",
        modifier_class="cold",
        condition_id="cold_acclimation_10d_14to15c",
        modifier_label="Vastus lateralis after 10 days at 14-15 C air, men with type 2 diabetes",
        cell_line_name="human vastus lateralis",
        dose={
            "unit": "hours_per_day_at_air_temperature",
            "temperature_c": 14.5,
            "temperature_note": "Paper states 14-15 C air. 14.5 is the midpoint, not a measured core temperature. Not a CEM43 dose.",
            "duration_hr": 6.0,
            "schedule": "2 h day 1, 4 h day 2, 6 h days 3-10",
        },
        timepoint_hr=10 * 24.0,
        citation="pmid:32887608",
        geo_accession="GSE156248",
        platform="GPL11532",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source="GSE156248 series matrix, values already log2",
        gene_log2fc=genes,
    )


def _training_12w():
    genes, n_treat, n_ctrl = _by_title(
        "GSE156247", "GSE156247_series_matrix.txt.gz", "GPL11532",
        lambda t: "after training" in t,
        lambda t: "before training" in t,
        "log2",
    )
    return _record(
        signature_id="gse156247_muscle_exercise12w",
        modifier_class="exercise",
        condition_id="combined_exercise_12w",
        modifier_label="Vastus lateralis after 12 weeks of combined exercise, overweight men",
        cell_line_name="human vastus lateralis",
        dose={
            "unit": "calendar_hours",
            "duration_hr": 12 * 7 * 24.0,
            "program_weeks": 12,
            "note": "Per-session length is not in the series record. duration_hr is the 12-week calendar span.",
        },
        timepoint_hr=12 * 7 * 24.0,
        citation="pmid:32887608",
        geo_accession="GSE156247",
        platform="GPL11532",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source="GSE156247 series matrix, values already log2",
        gene_log2fc=genes,
    )


def _heat_sheet():
    genes, n_treat, n_ctrl = _by_title(
        "GSE12474", "GSE12474_series_matrix.txt.gz", "GPL570",
        lambda t: "1 day after" in t,
        lambda t: "two months before" in t,
        "linear",
    )
    return _record(
        signature_id="gse12474_muscle_heat_sheet10w",
        modifier_class="local_heat",
        condition_id="heat_sheet_8h_day_10w",
        modifier_label="Vastus lateralis one day after 10 weeks of a thigh heat-and-steam sheet",
        cell_line_name="human vastus lateralis",
        dose={
            "unit": "hours_per_day",
            "duration_hr": 8.0,
            "days_per_week": 4,
            "weeks": 10,
            "note": "No temperature is stated in the abstract or the series record.",
        },
        timepoint_hr=24.0,
        citation="pmid:20803152",
        geo_accession="GSE12474",
        platform="GPL570",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source="GSE12474 series matrix, MAS5 linear signal",
        gene_log2fc=genes,
    )


def _sauna():
    genes, n_treat, n_ctrl = _by_title(
        "GSE90763", "GSE90763_series_matrix.txt.gz", "GPL570",
        lambda t: "_T1_" in t,
        lambda t: "_T0_" in t,
        "log2",
    )
    return _record(
        signature_id="gse90763_pbmc_sauna_15min_after",
        modifier_class="sauna",
        condition_id="sauna_pbmc_15min_after_vs_before",
        modifier_label="PBMC 15 min after sauna exposure versus before",
        cell_line_name="human PBMC",
        dose={
            "unit": "hours_after_exposure",
            "temperature_c": 75.7,
            "temperature_note": "Abstract reports sauna air 75.7±0.86 C. GEO summary says 78±6 C. Not tissue temperature and not CEM43.",
            "duration_hr": 0.25,
            "note": "Sample source calls T1 '15 min after exposure'. Sauna length itself is not in the series record.",
        },
        timepoint_hr=0.25,
        citation="pmid:28842615",
        geo_accession="GSE90763",
        platform="GPL570",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source="GSE90763 series matrix, RMA-scale log2 values",
        gene_log2fc=genes,
    )


def _trf():
    path = _require(_path("GSE129843", "GSE129843_RESTRICT.txt.gz"))
    by_symbol: dict[str, list[float]] = {}
    n_r = n_u = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        r_idx = [i for i, h in enumerate(header) if ".R." in h]
        u_idx = [i for i, h in enumerate(header) if ".U." in h]
        n_r, n_u = len(r_idx), len(u_idx)
        sym_i = header.index("Symbol")
        raw_rows = []
        ensembl_ids = []
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            raw_rows.append(parts)
            token = parts[sym_i].strip() if sym_i < len(parts) else ""
            if token.startswith("ENSG"):
                ensembl_ids.append(token.split(".")[0])
        symbols_of = _ensembl_to_symbol(sorted(set(ensembl_ids)))
        for parts in raw_rows:
            token = parts[sym_i].strip() if sym_i < len(parts) else ""
            if token.startswith("ENSG"):
                symbol = symbols_of.get(token.split(".")[0], "")
            else:
                symbol = token
            if not symbol or symbol == "NA":
                continue
            def nums(idxs):
                out = []
                for i in idxs:
                    if i >= len(parts) or parts[i] in ("", "NA"):
                        continue
                    try:
                        out.append(float(parts[i]))
                    except ValueError:
                        continue
                return out
            fc = _log2_ratio(_mean(nums(r_idx)), _mean(nums(u_idx)))
            if fc is None:
                continue
            by_symbol.setdefault(symbol, []).append(fc)
    genes = {s: sum(v) / len(v) for s, v in by_symbol.items()}
    return _record(
        signature_id="gse129843_muscle_trf8h_vs_15h",
        modifier_class="meal_timing",
        condition_id="trf_8h_vs_15h_5days",
        modifier_label="Vastus lateralis, 8 h eating window versus 15 h, day 5, all clock times pooled",
        cell_line_name="human vastus lateralis",
        dose={"unit": "hours", "duration_hr": 5 * 24.0, "eating_window_hr": 8.0,
              "control_window_hr": 15.0},
        timepoint_hr=5 * 24.0,
        citation="pmid:32938935",
        geo_accession="GSE129843",
        platform="RNA-seq",
        n_treatment_samples=n_r,
        n_control_samples=n_u,
        data_source="GSE129843_RESTRICT.txt.gz counts; log2 ratio of means, restricted (.R.) versus unrestricted (.U.), clock times pooled",
        gene_log2fc=genes,
    )


def _resistance():
    path = _require(_path("GSE252357", "GSE252357_normalized_counts_protein_coding.csv.gz"))
    with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = list(reader)
    header = [h.strip() for h in header]
    def cols(prefix, suffix):
        return [i for i, h in enumerate(header) if h.startswith(prefix) and h.endswith(suffix)]
    out = []
    for hours, suffix in ((3.0, "_3h"), (24.0, "_24h")):
        treat = cols("RE", suffix)
        ctrl = cols("RE", "_PRE")
        by_symbol = {}
        for row in rows:
            symbol = row[0].strip().strip('"')
            if not symbol:
                continue
            def nums(idxs):
                vals = []
                for i in idxs:
                    if i >= len(row) or row[i] in ("", "NA"):
                        continue
                    try:
                        vals.append(float(row[i]))
                    except ValueError:
                        continue
                return vals
            fc = _log2_ratio(_mean(nums(treat)), _mean(nums(ctrl)))
            if fc is None:
                continue
            by_symbol.setdefault(symbol, []).append(fc)
        genes = {s: sum(v) / len(v) for s, v in by_symbol.items()}
        tag = f"{int(hours)}h"
        out.append(_record(
            signature_id=f"gse252357_muscle_resistance_{tag}",
            modifier_class="exercise",
            condition_id=f"resistance_exercise_{tag}_vs_pre",
            modifier_label=f"Vastus lateralis {tag} after resistance exercise versus pre",
            cell_line_name="human vastus lateralis",
            dose={"unit": "hours_after_session", "duration_hr": hours},
            timepoint_hr=hours,
            citation="pmid:38586026",
            geo_accession="GSE252357",
            platform="RNA-seq",
            n_treatment_samples=len(treat),
            n_control_samples=len(ctrl),
            data_source="GSE252357 normalized counts; log2 ratio of RE timepoint versus RE pre. Control-arm columns were not used.",
            gene_log2fc=genes,
        ))
    return out


def _tre_adipose():
    path = _require(_path("GSE168705", "GSE168705_raw.txt.gz"))
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        data = [line.rstrip("\n").split("\t") for line in fh]
    # Header is sample IDs only; each data row starts with a RefSeq accession.
    samples = header
    late = [i for i, s in enumerate(samples) if s.endswith("_5")]
    base = [i for i, s in enumerate(samples) if s.endswith("_1")]
    accessions = [row[0].split(".")[0] for row in data if row and row[0].startswith("NM_")]
    symbols = _refseq_to_symbol(sorted(set(accessions)))
    by_symbol: dict[str, list[float]] = {}
    for row in data:
        if not row or not row[0].startswith("NM_"):
            continue
        symbol = symbols.get(row[0].split(".")[0])
        if not symbol:
            continue
        def nums(idxs):
            vals = []
            for i in idxs:
                j = i + 1  # sample columns are shifted by the gene id
                if j >= len(row) or row[j] in ("", "NA"):
                    continue
                try:
                    vals.append(float(row[j]))
                except ValueError:
                    continue
            return vals
        fc = _log2_ratio(_mean(nums(late)), _mean(nums(base)))
        if fc is None:
            continue
        by_symbol.setdefault(symbol, []).append(fc)
    genes = {s: sum(v) / len(v) for s, v in by_symbol.items()}
    if len(genes) < 500:
        raise ValueError(f"GSE168705: only {len(genes)} symbols mapped from RefSeq")
    return _record(
        signature_id="gse168705_adipose_tre10h_8w",
        modifier_class="meal_timing",
        condition_id="tre_10h_window_8weeks_6am",
        modifier_label="Adipose, 8-week 10 h eating window versus baseline, 6 AM samples",
        cell_line_name="human adipose",
        dose={"unit": "calendar_hours", "duration_hr": 8 * 7 * 24.0, "eating_window_hr": 10.0},
        timepoint_hr=8 * 7 * 24.0,
        citation="pmid:35912794",
        geo_accession="GSE168705",
        platform="RNA-seq",
        n_treatment_samples=len(late),
        n_control_samples=len(base),
        data_source="GSE168705_raw.txt.gz counts. Columns ending _5 are the series titles' 8-week 6 AM samples; _1 are baseline 6 AM. RefSeq mapped through mygene.info.",
        gene_log2fc=genes,
    )


def _write_probe_csv(path: str, rows: list[tuple[str, str]]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ID", "gene_symbol", "entrez_id"])
        for probe_id, symbol in rows:
            if symbol:
                writer.writerow([probe_id, symbol, ""])
    return path


def _brainarray_map() -> str:
    """GPL22321 probeset `{entrez}_at` -> symbol, from NCBI gene_info."""
    dest = os.path.join(PLATFORMS, "GPL22321_probe_map.csv")
    if os.path.isfile(dest):
        return dest
    info = os.path.join(PLATFORMS, "Homo_sapiens.gene_info.gz")
    if not os.path.isfile(info):
        raise FileNotFoundError(info)
    rows = []
    with gzip.open(info, "rt", encoding="utf-8", errors="replace") as fh:
        header = fh.readline()
        if not header.startswith("#"):
            raise ValueError("gene_info header missing")
        for line in fh:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            gene_id, symbol = parts[1], parts[2]
            if gene_id.isdigit() and symbol and symbol != "-":
                rows.append((f"{gene_id}_at", symbol))
    return _write_probe_csv(dest, rows)


def _symbol_from_assignment(text: str) -> str:
    """First gene symbol in an Affymetrix gene_assignment cell.
    Format: accession // symbol // description // locus // entrez,
    repeated after '///'."""
    if not text:
        return ""
    for chunk in text.split("///"):
        fields = [part.strip() for part in chunk.split("//")]
        if len(fields) >= 2 and fields[1] not in ("", "---"):
            return fields[1]
    return ""


def _geo_platform_map(gpl_id: str) -> str:
    dest = os.path.join(PLATFORMS, f"{gpl_id}_probe_map.csv")
    if os.path.isfile(dest) and os.path.getsize(dest) > 1000:
        return dest
    src = os.path.join(PLATFORMS, f"{gpl_id}_data.txt")
    if not os.path.isfile(src):
        raise FileNotFoundError(
            f"{src} missing. It is the GEO platform data table for {gpl_id}."
        )
    rows = []
    with open(src, encoding="utf-8", errors="replace") as fh:
        header = None
        for line in fh:
            if line.startswith("!platform_table_begin"):
                header = next(fh).rstrip("\n").split("\t")
                continue
            if header is None:
                continue
            if line.startswith("!platform_table_end"):
                break
            parts = line.rstrip("\n").split("\t")
            rec = dict(zip(header, parts))
            symbol = _symbol_from_assignment(rec.get("gene_assignment", ""))
            probe_id = rec.get("ID", "")
            if probe_id and symbol:
                rows.append((probe_id, symbol))
    if len(rows) < 1000:
        raise ValueError(f"{gpl_id}: only {len(rows)} probes had a gene symbol")
    return _write_probe_csv(dest, rows)


def _fast_40h():
    genes, n_treat, n_ctrl = _by_title(
        "GSE28016", "GSE28016_series_matrix.txt.gz", "GPL5175",
        lambda t: t.startswith("fasting sample"),
        lambda t: t.startswith("fed sample"),
        "log2",
        probe_map_path=_geo_platform_map("GPL5175"),
    )
    return _record(
        signature_id="gse28016_muscle_fast40h_vs_fed",
        modifier_class="fasting",
        condition_id="fast_40h_vs_fed",
        modifier_label="Vastus lateralis, 40 h fast versus 6 h after a meal",
        cell_line_name="human vastus lateralis",
        dose={"unit": "hours", "duration_hr": 40.0, "fasting_hr": 40.0,
              "control": "6 h after a mixed meal"},
        timepoint_hr=40.0,
        citation="pmid:21641545",
        geo_accession="GSE28016",
        platform="GPL5175",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source="GSE28016 series matrix, log2 values; HuEx transcript clusters mapped from the GPL5175 gene_assignment column",
        gene_log2fc=genes,
    )


def _running(accession, tissue, signature_id):
    genes, n_treat, n_ctrl = _by_title(
        accession, f"{accession}_series_matrix.txt.gz", "GPL17586",
        lambda t: "posttraining" in t,
        lambda t: "baseline" in t,
        "log2",
        probe_map_path=_geo_platform_map("GPL17586"),
    )
    return _record(
        signature_id=signature_id,
        modifier_class="exercise",
        condition_id=f"running_18w_{tissue}",
        modifier_label=f"{tissue}, after 18 weeks of running (3 x 60 min/week) versus baseline",
        cell_line_name=f"human {tissue}",
        dose={"unit": "hours_of_running", "duration_hr": 18 * 3 * 1.0,
              "sessions_per_week": 3, "weeks": 18},
        timepoint_hr=18 * 7 * 24.0,
        citation="geo:GSE111551",
        geo_accession=accession,
        platform="GPL17586",
        n_treatment_samples=n_treat,
        n_control_samples=n_ctrl,
        data_source=f"{accession} series matrix, log2 values; HTA 2.0 ids mapped from the GPL17586 gene_assignment column",
        gene_log2fc=genes,
    )


def _gse82323():
    huex = _geo_platform_map("GPL5175")
    specs = (
        ("gse82323_muscle_heat", "heat", "thermal",
         {"unit": "exposure_min", "value": 30.0, "temperature_c": 73.0, "duration_hr": 0.5,
          "note": "Chamber air ~73 C for 30 min. Not converted to CEM43 because 73 C is air, not tissue."}),
        ("gse82323_soleus_contraction", "contraction", "exercise",
         {"unit": "hours_after_bout", "duration_hr": 3.0}),
        ("gse82323_soleus_vibration", "vibration", "exercise",
         {"unit": "hours_after_bout", "duration_hr": 3.0}),
    )
    out = []
    for sig_id, arm, klass, dose in specs:
        genes, n_treat, n_ctrl = _by_title(
            "GSE82323", "GSE82323_series_matrix.txt.gz", "GPL5175",
            lambda t, a=arm: f"{a}, experimental" in t,
            lambda t, a=arm: f"{a}, control" in t,
            "log2",
            probe_map_path=huex,
        )
        out.append(_record(
            signature_id=sig_id,
            modifier_class=klass,
            condition_id=f"gse82323_{arm}_3h",
            modifier_label=f"GSE82323 {arm} arm, 3 h after the stress versus its own control",
            cell_line_name="human skeletal muscle",
            dose=dose,
            timepoint_hr=3.0,
            citation="pmid:27486743",
            geo_accession="GSE82323",
            platform="GPL5175",
            n_treatment_samples=n_treat,
            n_control_samples=n_ctrl,
            data_source="GSE82323 series matrix, log2 values; HuEx transcript clusters mapped from the GPL5175 gene_assignment column",
            gene_log2fc=genes,
        ))
    return out


def _cwi():
    brain = _brainarray_map()
    out = []
    for sig_id, tag, klass, dose, label in (
        ("gse85620_cwi_post_vs_pre", "CWI", "cold_immersion",
         {"unit": "calendar_hours", "duration_hr": 10 * 7 * 24.0,
          "note": "Water temperature is not in the GEO record, so none is stored."},
         "Vastus lateralis after 10 weeks of strength training plus cold-water immersion versus before"),
        ("gse85620_placebo_post_vs_pre", "PLA", "exercise",
         {"unit": "calendar_hours", "duration_hr": 10 * 7 * 24.0,
          "note": "Placebo recovery drink, same strength program, no immersion."},
         "Vastus lateralis after 10 weeks of strength training with a placebo drink versus before"),
    ):
        genes, n_treat, n_ctrl = _by_title(
            "GSE85620", "GSE85620_series_matrix.txt.gz", "GPL22321",
            lambda t, tag=tag: f"_{tag}_POST" in t,
            lambda t, tag=tag: f"_{tag}_PRE" in t,
            "log2",
            probe_map_path=brain,
        )
        out.append(_record(
            signature_id=sig_id,
            modifier_class=klass,
            condition_id=f"strength10w_{tag.lower()}",
            modifier_label=label,
            cell_line_name="human vastus lateralis",
            dose=dose,
            timepoint_hr=10 * 7 * 24.0,
            citation="geo:GSE85620",
            geo_accession="GSE85620",
            platform="GPL22321",
            n_treatment_samples=n_treat,
            n_control_samples=n_ctrl,
            data_source="GSE85620 series matrix, log2 values; Brainarray ENTREZG probeset ids mapped through NCBI gene_info",
            gene_log2fc=genes,
        ))
    return out


def parse() -> list[dict]:
    records = [
        _fasting_24h(),
        _cold(),
        _training_12w(),
        _heat_sheet(),
        _sauna(),
        _trf(),
        _tre_adipose(),
    ]
    records.extend(_treadmill())
    records.extend(_resistance())
    records.append(_fast_40h())
    records.append(_running("GSE111551", "skeletal muscle", "gse111551_muscle_running18w"))
    records.append(_running("GSE111552", "PBMC", "gse111552_pbmc_running18w"))
    records.extend(_gse82323())
    records.extend(_cwi())
    return records

"""Phase 1 (Signature-transfer modifier x drug predictor build order):
the per-series parsers in synlethality/modifier_signatures/. Fixture
tests: each parser runs against a tiny but format-real synthetic data
file + probe map in tmp_path (titles pulled from each parser's own
constants, so a fixture can never drift from the parser), and the exact
log2FC / dose / arm-count outputs are asserted. The real end-to-end
build over the downloaded GEO series is covered by PHASE_1_REPORT.md's
own run (repo convention: test_signature_space.py)."""

import gzip
import math

import pytest

from synlethality.modifier_signatures import (
    gse10043_mild_hyperthermia,
    gse48398_heat_shock,
    gse70976_serum_starvation,
    gse75127_hyperthermia,
    gse153830_metabolic,
    gse300765_hypoxia_acidosis,
)


def _write_series_matrix(path, titles, rows):
    lines = [
        "!Sample_title\t" + "\t".join(f'"{t}"' for t in titles),
        "!series_matrix_table_begin",
        '"ID_REF"\t' + "\t".join(f'"GSM{i}"' for i in range(len(titles))),
    ]
    for probe_id, values in rows.items():
        lines.append("\t".join([f'"{probe_id}"'] + [str(v) for v in values]))
    lines.append("!series_matrix_table_end")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_probe_map(path, rows):
    import csv
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ID", "gene_symbol", "entrez_id"])
        writer.writerows(rows)


# --- GSE48398 (submitter non-normalized Illumina file) ----------------------

def test_gse48398_parser_exact_math_and_dose(tmp_path):
    data = tmp_path / "non_normalized.txt"
    probe_map = tmp_path / "GPL10558_probe_map.csv"
    # Real header shape: '<cell> <temp>oC rep<N>' columns + '<cell> p value'.
    header = ["ID_REF"]
    for prefix in ("MCF10A", "MCF7", "MDA231", "MDA468"):
        header += [f"{prefix} 45oC rep1", f"{prefix} 37oC rep1", f"{prefix} p value"]
    rows = [
        ["ILMN_0001"] + ["7", "1", "0.5"] * 4,   # +2.0 log2FC per line
        ["ILMN_0002"] + ["1", "7", "0.9"] * 4,   # -2.0 log2FC per line
    ]
    with open(data, "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            fh.write("\t".join(row) + "\n")
    _write_probe_map(str(probe_map), [
        ["ILMN_0001", "GENEA", "1"], ["ILMN_0002", "GENEB", "2"]])

    records = gse48398_heat_shock.parse(str(data), str(probe_map))
    assert len(records) == 4
    by_id = {r["signature_id"]: r for r in records}
    assert set(by_id) == {
        "gse48398_mcf10a_heat45c30min", "gse48398_mcf7_heat45c30min",
        "gse48398_mda231_heat45c30min", "gse48398_mda468_heat45c30min",
    }
    for record in records:
        assert record["gene_log2fc"] == {"GENEA": 2.0, "GENEB": -2.0}
        assert record["dose"]["unit"] == "CEM43"
        assert record["dose"]["value"] == pytest.approx(120.0)
        assert record["dose"]["temperature_c"] == 45.0
        assert (record["n_treatment_samples"], record["n_control_samples"]) == (1, 1)
        assert record["modifier_class"] == "thermal"
        assert record["citation"] == "geo:GSE48398"  # no linked pub, verified
    assert by_id["gse48398_mcf7_heat45c30min"]["cell_line_id"] == "MCF7_BREAST"


# --- GSE10043 (Affymetrix GPL96 series matrix, linear scale) ----------------

def test_gse10043_parser_exact_math_and_mild_dose(tmp_path):
    data = tmp_path / "GSE10043_series_matrix.txt.gz"
    probe_map = tmp_path / "GPL96_probe_map.csv"
    titles = gse10043_mild_hyperthermia.TREAT_TITLES + gse10043_mild_hyperthermia.CTRL_TITLES
    _write_series_matrix(str(data), titles, {"1007_s_at": [7.0, 9.0, 1.0, 3.0]})
    _write_probe_map(str(probe_map), [["1007_s_at", "GENEA", "1"]])

    (record,) = gse10043_mild_hyperthermia.parse(str(data), str(probe_map))
    # treat mean 8 vs ctrl mean 2, linear: log2(9/3)
    assert record["gene_log2fc"]["GENEA"] == pytest.approx(math.log2(3.0))
    assert record["dose"]["value"] == pytest.approx(1.875)  # genuinely mild
    assert record["dose"]["temperature_c"] == 41.0
    assert record["cell_line_id"] == "U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE"
    assert (record["n_treatment_samples"], record["n_control_samples"]) == (2, 2)



# --- GSE75127 (Affymetrix GPL570 series matrix, log2 scale) -----------------

def test_gse75127_parser_uses_siluc_matched_heat_arm_only(tmp_path):
    data = tmp_path / "GSE75127_series_matrix.txt.gz"
    probe_map = tmp_path / "GPL570_probe_map.csv"
    titles = gse75127_hyperthermia.TREAT_TITLES + gse75127_hyperthermia.CTRL_TITLES
    _write_series_matrix(str(data), titles, {
        "1552267_at": [8.0, 8.0, 5.0, 5.0],   # +3.0 (log2 scale)
        "200001_at": [5.0, 5.0, 8.0, 8.0],    # -3.0
    })
    _write_probe_map(str(probe_map), [
        ["1552267_at", "GENEA", "1"], ["200001_at", "GENEB", "2"]])

    (record,) = gse75127_hyperthermia.parse(str(data), str(probe_map))
    assert record["gene_log2fc"] == {"GENEA": 3.0, "GENEB": -3.0}
    assert record["dose"]["value"] == pytest.approx(180.0)  # CEM43(44C, 90min)
    assert record["dose"]["temperature_c"] == 44.0
    # Non-curated line: honest None + real study name, never a mapping.
    assert record["cell_line_id"] is None
    assert record["cell_line_name"] == "HSC-3"
    assert record["citation"] == "pmid:27245201"  # the pmid's real owner
    # The BAG3-KD arms are excluded by design: exactly one record.
    assert "BAG3" not in record["signature_id"]


# --- GSE300765 (Illumina GPL10558, 6 arms, log2 scale) ----------------------

def test_gse300765_parser_three_real_conditions(tmp_path):
    data = tmp_path / "GSE300765_series_matrix.txt.gz"
    probe_map = tmp_path / "GPL10558_probe_map.csv"
    arms = gse300765_hypoxia_acidosis.ARMS
    titles = [t for arm in arms for t in (arm["treat"] + arm["ctrl"])]
    # GENEA: +3.0 hypoxia, +2.0 acute acidosis, +1.0 chronic acidosis.
    values = [8.0] * 3 + [5.0] * 3 + [7.0] * 3 + [5.0] * 3 + [6.0] * 3 + [5.0] * 3
    _write_series_matrix(str(data), titles, {"ILMN_0001": values})
    _write_probe_map(str(probe_map), [["ILMN_0001", "GENEA", "1"]])

    records = gse300765_hypoxia_acidosis.parse(str(data), str(probe_map))
    assert len(records) == 3
    by_cond = {r["condition_id"]: r for r in records}
    assert by_cond["hypoxia_1pct_o2_48h"]["gene_log2fc"]["GENEA"] == pytest.approx(3.0)
    assert by_cond["acidosis_ph6.4_48h"]["gene_log2fc"]["GENEA"] == pytest.approx(2.0)
    assert by_cond["acidosis_adaptation_ph6.4_10weeks"]["gene_log2fc"]["GENEA"] == pytest.approx(1.0)
    # Gate 1 dose completeness per class, from the series' own annotations.
    assert by_cond["hypoxia_1pct_o2_48h"]["dose"]["o2_percent"] == 1.0
    assert by_cond["hypoxia_1pct_o2_48h"]["dose"]["duration_hr"] == 48.0
    assert by_cond["acidosis_ph6.4_48h"]["dose"]["ph"] == 6.4
    assert by_cond["acidosis_adaptation_ph6.4_10weeks"]["dose"]["duration_hr"] == 1680.0
    for record in records:
        assert record["cell_line_id"] == "U87MG_CENTRAL_NERVOUS_SYSTEM"
        assert (record["n_treatment_samples"], record["n_control_samples"]) == (3, 3)


# --- GSE70976 (Affymetrix GPL570, serum-free arm only, linear scale) --------

def test_gse70976_parser_serum_starvation_excludes_adma_arm(tmp_path):
    data = tmp_path / "GSE70976_series_matrix.txt.gz"
    probe_map = tmp_path / "GPL570_probe_map.csv"
    # Titles from the parser's own constants -- including the real double
    # space in the submitter's serum-free titles.
    titles = gse70976_serum_starvation.CTRL_TITLES + gse70976_serum_starvation.TREAT_TITLES
    _write_series_matrix(str(data), titles, {"1552267_at": [1.0, 1.0, 1.0, 7.0, 7.0, 7.0]})
    _write_probe_map(str(probe_map), [["1552267_at", "GENEA", "1"]])

    (record,) = gse70976_serum_starvation.parse(str(data), str(probe_map))
    assert record["gene_log2fc"]["GENEA"] == pytest.approx(2.0)
    assert record["dose"]["serum_percent"] == 0.0
    assert record["dose"]["duration_hr"] == 96.0
    assert record["cell_line_id"] is None
    assert record["cell_line_name"] == "LoVo"
    assert "ADMA" not in record["modifier_label"]


# --- GSE153830 (RNA-seq FPKM; reuses the computed DEG cache) ----------------

def test_gse153830_parser_schema_and_real_sample_counts(tmp_path, monkeypatch):
    # Fixture stands in for the computed DEG cache (real schema, synthetic
    # values), keyed off the REAL SAMPLE_GROUPS entries in
    # ingest/geo_modifiers.py -- so the test also guards parser/ingest
    # agreement on the four real (modifier, cell_line) keys.
    from synlethality.ingest.geo_modifiers import SAMPLE_GROUPS

    cache = {
        (group["key"]): {
            "modifier_id": modifier_id,
            "cell_line_id": cell_line_id,
            "gene_log2fc": {"GENEA": 1.5},
            "source": "synthetic fixture cache",
        }
        for (modifier_id, cell_line_id), group in SAMPLE_GROUPS.items()
    }
    monkeypatch.setattr(
        gse153830_metabolic, "load_deg_cache", lambda key: cache[key])

    # Tiny real-format FPKM matrix header (4 lines: ids, Cell_Line, glucose,
    # BHB) with the real per-arm sample multiplicities, incl. MCF-7 BHB10's
    # genuine single replicate.
    fpkm = tmp_path / "FPKM_matrix.txt"
    fpkm.write_text(
        "gene\tx\tm1\tm2\tm3\tm4\tm5\tm6\tm7\tm8\tm9\tm10\tm11\n"
        "Cell_Line\t\tMCF_7\tMCF_7\tMCF_7\tMCF_7\tMCF_7\tT47D\tT47D\tT47D\tT47D\tT47D\tT47D\n"
        "glucose (g/L)\t\t0.225\t0.225\t4.5\t4.5\t0.225\t0.225\t0.225\t4.5\t4.5\t0.225\t0.225\n"
        "BHB (mM)\t\t0\t0\t0\t0\t10\t0\t0\t0\t0\t25\t25\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gse153830_metabolic, "FPKM_MATRIX_PATH", str(fpkm))

    records = gse153830_metabolic.parse()
    assert len(records) == 4
    by_id = {r["signature_id"]: r for r in records}
    assert by_id["gse153830_mcf7_bhb10mm"]["n_treatment_samples"] == 1  # real singleton
    assert by_id["gse153830_mcf7_bhb10mm"]["n_control_samples"] == 2
    assert by_id["gse153830_t47d_glucose_deprivation"]["n_treatment_samples"] == 2
    for record in records:
        assert record["modifier_class"] == "dietary_metabolic"
        assert record["gene_log2fc"] == {"GENEA": 1.5}
        assert {"glucose_gL", "bhb_mM"} & set(record["dose"])
        assert record["dose"]["duration_hr"] == 96.0


def test_gse153830_parser_raises_when_arm_unmatched(tmp_path, monkeypatch):
    from synlethality.ingest.geo_modifiers import SAMPLE_GROUPS
    cache = {
        (group["key"]): {
            "modifier_id": modifier_id,
            "cell_line_id": cell_line_id,
            "gene_log2fc": {"GENEA": 1.5},
            "source": "synthetic fixture cache",
        }
        for (modifier_id, cell_line_id), group in SAMPLE_GROUPS.items()
    }
    monkeypatch.setattr(
        gse153830_metabolic, "load_deg_cache", lambda key: cache[key])
    fpkm = tmp_path / "FPKM_matrix.txt"
    fpkm.write_text(  # no samples match any group's arms
        "gene\tx\ts1\nCell_Line\t\tHEK293\nglucose\t\t1.0\nBHB\t\t0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gse153830_metabolic, "FPKM_MATRIX_PATH", str(fpkm))
    with pytest.raises(ValueError, match="No real samples matched"):
        gse153830_metabolic.parse()

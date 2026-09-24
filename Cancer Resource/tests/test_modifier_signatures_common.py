"""Phase 1 (Signature-transfer modifier x drug predictor build order):
synlethality/modifier_signatures/common.py -- the shared machinery every
parser uses (series-matrix parsing, per-probe log2FC, symbol collapse,
CEM43, the Gate 1 record validation). Unit tests on synthetic fixtures;
the real end-to-end library build is covered by PHASE_1_REPORT.md's own
run, per repo convention (test_signature_space.py)."""

import gzip
import math

import pytest

from synlethality.modifier_signatures.common import (
    cem43,
    collapse_to_symbols,
    load_and_collapse_series_matrix,
    load_series_matrix,
    make_record,
    per_probe_log2fc,
)


def _write_series_matrix(path, titles, rows, gzip_out=True):
    """A tiny but format-real GEO series matrix: quoted SOFT fields,
    begin/end markers, an ID_REF header row."""
    lines = [
        "!Series_title = \"A synthetic fixture series\"",
        "!Sample_title\t" + "\t".join(f'"{t}"' for t in titles),
        "!series_matrix_table_begin",
        '"ID_REF"\t' + "\t".join(f'"GSM{i}"' for i in range(len(titles))),
    ]
    for probe_id, values in rows.items():
        lines.append("\t".join([f'"{probe_id}"'] + ["" if v is None else str(v) for v in values]))
    lines.append("!series_matrix_table_end")
    text = "\n".join(lines) + "\n"
    if gzip_out:
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)


# --- cem43: exact Sapareto-Dewey values -------------------------------------

def test_cem43_exact_values():
    # Above 43C: R = 0.5. The real Phase 1 doses:
    assert cem43(45.0, 30.0) == pytest.approx(120.0)     # GSE48398
    assert cem43(44.0, 90.0) == pytest.approx(180.0)     # GSE75127
    assert cem43(43.0, 60.0) == pytest.approx(60.0)      # boundary: R=0.5 at >=43
    # Below 43C: R = 0.25. GSE10043's genuinely mild dose:
    assert cem43(41.0, 30.0) == pytest.approx(1.875)
    assert cem43(42.0, 60.0) == pytest.approx(15.0)


# --- load_series_matrix -----------------------------------------------------

def test_load_series_matrix_quoted_fields_and_missing_values(tmp_path):
    path = tmp_path / "fixture_series_matrix.txt.gz"
    _write_series_matrix(str(path), ["treat-1", "ctrl-1"], {
        "ILMN_0001": [10.0, 5.0],
        "ILMN_0002": [None, 3.0],   # empty field stays None, never zero-filled
    })
    titles, rows = load_series_matrix(str(path))
    assert titles == ["treat-1", "ctrl-1"]
    assert rows["ILMN_0001"] == [10.0, 5.0]
    assert rows["ILMN_0002"] == [None, 3.0]


def test_load_series_matrix_ignores_rows_outside_markers(tmp_path):
    path = tmp_path / "fixture.txt"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("!Sample_title\t\"t\"\t\"c\"\n")
        fh.write("STRAY_ROW\t1\t2\n")  # before the begin marker: ignored
        fh.write("!series_matrix_table_begin\n")
        fh.write('"ID_REF"\t"GSM0"\t"GSM1"\n')
        fh.write('"P1"\t7\t3\n')
        fh.write("!series_matrix_table_end\n")
        fh.write("AFTER_END\t9\t9\n")
    titles, rows = load_series_matrix(str(path))
    assert titles == ["t", "c"]
    assert rows == {"P1": [7.0, 3.0]}


def test_load_series_matrix_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_series_matrix(str(tmp_path / "absent.txt.gz"))


# --- per_probe_log2fc -------------------------------------------------------

def test_per_probe_log2fc_linear_scale_exact_math():
    rows = {"P1": [3.0, 7.0, 1.0, 1.0]}  # treat mean 5, ctrl mean 1
    out = per_probe_log2fc(rows, [0, 1], [2, 3], scale="linear")
    assert out["P1"] == pytest.approx(math.log2((5.0 + 1.0) / (1.0 + 1.0)))


def test_per_probe_log2fc_log2_scale_exact_math():
    rows = {"P1": [6.0, 8.0, 3.0, 5.0]}  # treat mean 7, ctrl mean 4
    out = per_probe_log2fc(rows, [0, 1], [2, 3], scale="log2")
    assert out["P1"] == pytest.approx(3.0)


def test_per_probe_log2fc_drops_probes_without_complete_arms():
    rows = {
        "P1": [None, 5.0, 2.0],   # one real treat replicate: kept
        "P2": [None, None, 2.0],  # no treat replicate at all: dropped
    }
    out = per_probe_log2fc(rows, [0, 1], [2], scale="linear")
    assert set(out) == {"P1"}


def test_per_probe_log2fc_rejects_empty_arms_and_bad_scale():
    with pytest.raises(ValueError):
        per_probe_log2fc({}, [], [0], scale="linear")
    with pytest.raises(ValueError, match="scale"):
        per_probe_log2fc({"P": [1.0, 2.0]}, [0], [1], scale="auto-detect-me")


# --- collapse_to_symbols ----------------------------------------------------

def test_collapse_to_symbols_median_and_unmapped_dropped():
    probe_fc = {"P1": 1.0, "P2": 3.0, "P3": 100.0, "P4": 9.0}
    probe_map = {"P1": "GENEA", "P2": "GENEA", "P3": "GENEA", "P5": "GENEB"}
    out = collapse_to_symbols(probe_fc, probe_map)
    # GENEA: median of its three real probe values; P4 unmapped -> dropped;
    # GENEB's probe never measured -> absent, never fabricated.
    assert out == {"GENEA": 3.0}


# --- load_and_collapse_series_matrix ---------------------------------------

def _write_probe_map(path, rows):
    import csv
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ID", "gene_symbol", "entrez_id"])
        writer.writerows(rows)


def test_load_and_collapse_end_to_end_exact(tmp_path):
    matrix = tmp_path / "fixture_series_matrix.txt.gz"
    probe_map = tmp_path / "GPLTEST_probe_map.csv"
    _write_series_matrix(str(matrix), ["heat-1", "heat-2", "ctrl-1", "ctrl-2"], {
        "ILMN_0001": [7.0, 9.0, 1.0, 3.0],   # GENEA: mean 8 vs 2 -> log2(9/3)
        "ILMN_0002": [2.0, 2.0, 2.0, 2.0],   # GENEA: flat 2 vs 2 -> log2(3/3)=0
    })
    _write_probe_map(str(probe_map), [
        ["ILMN_0001", "GENEA", "1"],
        ["ILMN_0002", "GENEA", "1"],
    ])
    gene_fc, n_treat, n_ctrl = load_and_collapse_series_matrix(
        str(matrix), "GPLTEST", ["heat-1", "heat-2"], ["ctrl-1", "ctrl-2"],
        scale="linear", probe_map_path=str(probe_map),
    )
    assert (n_treat, n_ctrl) == (2, 2)
    # GENEA = median(log2(9/3), 0.0) = log2(3)/2
    assert gene_fc["GENEA"] == pytest.approx(math.log2(3.0) / 2.0)


def test_load_and_collapse_refuses_when_titles_dont_match(tmp_path):
    matrix = tmp_path / "fixture_series_matrix.txt.gz"
    probe_map = tmp_path / "GPLTEST_probe_map.csv"
    _write_series_matrix(str(matrix), ["real-title-1", "real-title-2"], {"P1": [1.0, 1.0]})
    _write_probe_map(str(probe_map), [["P1", "GENEA", "1"]])
    with pytest.raises(ValueError, match="no longer matches the real sample sheet"):
        load_and_collapse_series_matrix(
            str(matrix), "GPLTEST", ["guessed-title"], ["real-title-2"],
            scale="linear", probe_map_path=str(probe_map),
        )


# --- make_record: Gate 1's hard validation ---------------------------------

def _record_kwargs(**overrides):
    kwargs = dict(
        signature_id="fixture_sig",
        modifier_class="thermal",
        condition_id="fixture_condition",
        modifier_label="Fixture label",
        cell_line_id="MCF7_BREAST",
        cell_line_name="MCF-7",
        dose={"modality": "thermal", "unit": "CEM43", "value": 120.0,
              "temperature_c": 45.0, "duration_hr": 0.5},
        timepoint_hr=4.5,
        citation="geo:FIXTURE",
        geo_accession="GSEFIXTURE",
        platform="GPLTEST",
        n_treatment_samples=2,
        n_control_samples=2,
        data_source="synthetic fixture",
        gene_log2fc={"GENEA": 1.0},
    )
    kwargs.update(overrides)
    return kwargs


def test_make_record_complete_record_passes():
    record = make_record(**_record_kwargs())
    assert record["processing"] == "modifier_signatures-1.0.0"
    assert record["dose"]["value"] == 120.0


def test_make_record_allows_null_cell_line_id_but_not_empty():
    # Non-curated lines (LoVo, HSC-3) honestly record None + their real
    # study name; an empty string is still an error.
    record = make_record(**_record_kwargs(cell_line_id=None, cell_line_name="LoVo"))
    assert record["cell_line_id"] is None
    with pytest.raises(ValueError, match="incomplete record"):
        make_record(**_record_kwargs(cell_line_id=""))


def test_make_record_gate1_refuses_incomplete_dose_metadata():
    with pytest.raises(ValueError, match="incomplete dose metadata"):
        make_record(**_record_kwargs(dose={"modality": "thermal", "unit": "CEM43"}))


def test_make_record_rejects_unknown_modifier_class():
    with pytest.raises(ValueError, match="unknown modifier_class"):
        make_record(**_record_kwargs(modifier_class="guessed_modality"))


def test_make_record_rejects_zero_sample_arm_and_empty_signature():
    with pytest.raises(ValueError, match="zero-sample arm"):
        make_record(**_record_kwargs(n_treatment_samples=0))
    with pytest.raises(ValueError, match="incomplete record"):
        make_record(**_record_kwargs(gene_log2fc={}))


def test_make_record_dietary_metabolic_needs_a_real_nadir():
    with pytest.raises(ValueError, match="glucose_gL or bhb_mM"):
        make_record(**_record_kwargs(
            modifier_class="dietary_metabolic",
            dose={"modality": "dietary_metabolic", "unit": "% fasting", "duration_hr": 96.0},
        ))
    record = make_record(**_record_kwargs(
        modifier_class="dietary_metabolic",
        dose={"modality": "dietary_metabolic", "unit": "g/L glucose",
              "glucose_gL": 0.225, "duration_hr": 96.0},
    ))
    assert record["dose"]["glucose_gL"] == 0.225


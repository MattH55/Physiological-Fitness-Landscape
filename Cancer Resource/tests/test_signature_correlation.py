"""Unit tests for synlethality/signature_correlation.py -- Prediction
Methodology Stage 1's real, reusable computations (deterministic synthetic
inputs; the real-data pipeline is covered separately in test_seed.py's
GSE153830 ingestion test)."""

import json

import pytest

from synlethality.signature_correlation import (
    correlate_modifier_drug,
    geneset_enrichment_score,
    xsum_correlation,
)


def test_geneset_enrichment_score_detects_elevated_set():
    gene_log2fc = {f"bg{i}": 0.0 for i in range(10)}
    gene_log2fc.update({f"set{i}": 3.0 for i in range(5)})
    gene_set = {f"set{i}" for i in range(5)}
    result = geneset_enrichment_score(gene_log2fc, gene_set)
    assert result["score"] > 0
    assert result["n_genes_in_set"] == 5
    assert result["n_genes_background"] == 10
    assert result["mean_log2fc_in_set"] == pytest.approx(3.0)
    assert result["mean_log2fc_background"] == pytest.approx(0.0)


def test_geneset_enrichment_score_detects_suppressed_set():
    gene_log2fc = {f"bg{i}": 0.0 for i in range(10)}
    gene_log2fc.update({f"set{i}": -3.0 for i in range(5)})
    gene_set = {f"set{i}" for i in range(5)}
    result = geneset_enrichment_score(gene_log2fc, gene_set)
    assert result["score"] < 0


def test_geneset_enrichment_score_requires_minimum_genes():
    gene_log2fc = {"a": 1.0, "b": 2.0, "bg1": 0.0, "bg2": 0.0, "bg3": 0.0}
    with pytest.raises(ValueError):
        geneset_enrichment_score(gene_log2fc, {"a", "b"})  # only 2 in-set genes
    gene_log2fc2 = {"a": 1.0, "b": 2.0, "c": 1.5, "bg1": 0.0, "bg2": 0.0}
    with pytest.raises(ValueError):
        geneset_enrichment_score(gene_log2fc2, {"a", "b", "c"})  # only 2 background genes


def test_xsum_correlation_mimicking_signature_is_positive():
    reference_ranks = {"up1": 2.0, "up2": 1.5, "down1": -2.0, "down2": -1.5}
    result = xsum_correlation(
        query_up={"up1", "up2"}, query_down={"down1", "down2"},
        reference_ranks=reference_ranks,
    )
    assert result["xsum"] > 0
    assert result["n_genes_matched"] == 4
    assert result["n_up_matched"] == 2
    assert result["n_down_matched"] == 2


def test_xsum_correlation_reversing_signature_is_negative():
    reference_ranks = {"up1": 2.0, "up2": 1.5, "down1": -2.0, "down2": -1.5}
    # query's "up" genes are actually down in the reference, and vice versa.
    result = xsum_correlation(
        query_up={"down1", "down2"}, query_down={"up1", "up2"},
        reference_ranks=reference_ranks,
    )
    assert result["xsum"] < 0


def test_xsum_correlation_no_overlap_returns_none_not_zero():
    result = xsum_correlation(
        query_up={"unrelated1"}, query_down={"unrelated2"},
        reference_ranks={"up1": 2.0, "down1": -2.0},
    )
    assert result["xsum"] is None
    assert result["n_genes_matched"] == 0


def test_correlate_modifier_drug_runs_real_wiring_against_synthetic_lincs(tmp_path):
    """Exercises the real end-to-end wiring (ingest/geo_modifiers.py's DEG
    cache -> correlate_modifier_drug -> ingest/lincs_l1000.py's signature
    cache) against synthetic, controlled fixtures -- the real-data version
    of this pairing (mcf7_glucose_hippo x an actual LINCS-covered drug) is
    exercised separately once real signatures are ingested; this test
    proves the plumbing and the up/down thresholding are correct
    independent of that real data being present."""
    deg_cache_path = tmp_path / "deg_cache.json"
    lincs_cache_path = tmp_path / "lincs_cache.json"

    deg_cache = {
        "fake_modifier_key": {
            "modifier_id": "MOD-FAKE",
            "cell_line_id": "FAKE_LINE",
            "gene_log2fc": {
                "UP1": 2.0, "UP2": 1.5,        # top 2 by log2FC -> query_up
                "DOWN1": -2.0, "DOWN2": -1.5,  # bottom 2 by log2FC -> query_down
                "FLAT1": 0.1, "FLAT2": -0.2,   # middle -> neither, with query_size=2
            },
            "source": "test-fixture",
        }
    }
    deg_cache_path.write_text(json.dumps(deg_cache), encoding="utf-8")

    lincs_cache = {
        "fake_drug": {
            "sig_id": "FAKE:SIG1", "cell_line": "FAKE_LINE",
            "dose": "10 um", "time": "24 h", "source": "test-fixture",
            "gene_zscore": {"UP1": 3.0, "UP2": 2.0, "DOWN1": -3.0, "DOWN2": -2.0},
        }
    }
    lincs_cache_path.write_text(json.dumps(lincs_cache), encoding="utf-8")

    result = correlate_modifier_drug(
        "fake_modifier_key", "fake_drug", query_size=2,
        deg_cache_path=str(deg_cache_path), lincs_cache_path=str(lincs_cache_path),
    )
    assert result["modifier_id"] == "MOD-FAKE"
    assert result["cell_line_id"] == "FAKE_LINE"
    assert result["drug_id"] == "fake_drug"
    assert result["n_query_up"] == 2
    assert result["n_query_down"] == 2
    # UP1/UP2 (query up) are also up in the reference; DOWN1/DOWN2 (query
    # down) are also down in the reference -- a strongly mimicking
    # signature, so xsum must be strongly positive.
    # mean(reference at up genes) - mean(reference at down genes)
    # = mean(3.0, 2.0) - mean(-3.0, -2.0) = 2.5 - (-2.5) = 5.0
    assert result["xsum"] == pytest.approx(5.0)
    assert result["n_genes_matched"] == 4


def test_correlate_modifier_drug_top_n_query_beats_fixed_threshold(tmp_path):
    """Regression test for the real bug found 2026-09-22: an earlier version
    used a fixed |log2FC| > 1 threshold, which -- because the drug side only
    ever covers LINCS' 978 landmark genes, a small slice of the
    transcriptome -- could select a query so small that almost none of it
    landed on a landmark gene (2 of 978 measured on real data). A top-N
    query fixes the query sample size independent of any one study's log2FC
    scale, so a modifier with many strongly-changed genes should still
    reliably produce a comparable, non-trivial matched-gene count."""
    deg_cache_path = tmp_path / "deg_cache.json"
    lincs_cache_path = tmp_path / "lincs_cache.json"

    # 20 genes with a wide range of log2FC; only the extremes should be
    # selected as the query when query_size is small.
    gene_log2fc = {f"g{i}": float(i - 10) for i in range(20)}  # -10..9
    deg_cache_path.write_text(json.dumps({
        "fake_modifier_key": {
            "modifier_id": "MOD-FAKE", "cell_line_id": "FAKE_LINE",
            "gene_log2fc": gene_log2fc, "source": "test-fixture",
        }
    }), encoding="utf-8")
    # "Drug" landmark panel only covers a handful of these genes -- like the
    # real 978-gene LINCS panel only covering a slice of a full DEG table.
    lincs_cache_path.write_text(json.dumps({
        "fake_drug": {
            "sig_id": "FAKE:SIG1", "cell_line": "FAKE_LINE",
            "dose": "10 um", "time": "24 h", "source": "test-fixture",
            "gene_zscore": {"g0": 1.0, "g19": -1.0, "g10": 0.5},
        }
    }), encoding="utf-8")

    result = correlate_modifier_drug(
        "fake_modifier_key", "fake_drug", query_size=5,
        deg_cache_path=str(deg_cache_path), lincs_cache_path=str(lincs_cache_path),
    )
    # Top 5 up = g19..g15, bottom 5 down = g0..g4 -- g0 (down) and g19 (up)
    # both fall in the drug's small landmark panel; g10 does not (it's in
    # neither the top nor bottom 5).
    assert result["n_query_up"] == 5
    assert result["n_query_down"] == 5
    assert result["n_genes_matched"] == 2
    assert result["n_up_matched"] == 1
    assert result["n_down_matched"] == 1


def test_correlate_modifier_drug_real_lincs_and_geo_data():
    """Real end-to-end run (2026-09-22), both sides real data: GSE153830's
    own published expression matrix (modifier side, MCF-7 glucose
    deprivation) and LINCS L1000 GSE70138's own Level 5 signatures (drug
    side, extracted via scripts/extract_lincs_signatures.py from the real
    5.4GB GCTX file -- no clue.io registration needed, downloaded from
    NCBI GEO's ungated FTP). Skipped if the real ingestion caches aren't
    present in this environment (they're multi-step real downloads, not
    committed test fixtures)."""
    from synlethality.ingest.geo_modifiers import DEG_CACHE_PATH
    from synlethality.ingest.lincs_l1000 import CACHE_PATH as LINCS_CACHE_PATH
    import os

    if not (os.path.isfile(DEG_CACHE_PATH) and os.path.isfile(LINCS_CACHE_PATH)):
        pytest.skip("Real GEO DEG cache and/or LINCS signature cache not present "
                    "in this environment -- run GEOModifierIngest('GSE153830') "
                    "and LincsL1000Ingest first.")

    for drug_id in ("metformin", "5-fluorouracil", "mitomycin-c",
                     "doxorubicin", "paclitaxel", "temozolomide"):
        result = correlate_modifier_drug("mcf7_glucose_hippo", drug_id)
        assert result["modifier_id"] == "MOD-GLUCOSE-RESTRICT-5PCT-96H"
        assert result["cell_line_id"] == "MCF7_BREAST"
        assert result["drug_id"] == drug_id
        assert isinstance(result["xsum"], float)
        # Real, thin sample -- LINCS' 978 landmark genes are ~2.7% of the
        # transcriptome, so a 300-gene query (default query_size=150 up +
        # 150 down) typically only matches single digits to low tens of
        # landmark genes. Assert it's real and non-trivial, not a specific
        # count -- the exact number depends on which genes happen to
        # overlap for each drug's own signature.
        assert 0 < result["n_genes_matched"] < 300


def test_correlate_modifier_drug_missing_key_raises_not_fabricated(tmp_path):
    deg_cache_path = tmp_path / "deg_cache.json"
    deg_cache_path.write_text(json.dumps({}), encoding="utf-8")
    lincs_cache_path = tmp_path / "lincs_cache.json"
    lincs_cache_path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(KeyError):
        correlate_modifier_drug(
            "nonexistent_modifier", "nonexistent_drug",
            deg_cache_path=str(deg_cache_path), lincs_cache_path=str(lincs_cache_path),
        )

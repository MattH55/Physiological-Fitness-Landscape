"""Phase 1 (Signature-transfer modifier x drug predictor build order):
synlethality/probe_annotation.py -- the central GEO probe->symbol
annotation path. Unit tests on synthetic fixtures; the real downloads of
GPL10558/GPL96/GPL570's `.annot.gz` (and their cached probe maps) are
covered by the real Phase 1 run in PHASE_1_REPORT.md, not re-executed as
a pytest (same posture as test_signature_space.py: network-scale fetches
belong to one-time scripts, not the test suite)."""

import csv

import pytest

from synlethality.probe_annotation import (
    annot_url,
    load_probe_map,
    platform_bucket,
)


def test_platform_bucket_real_rule():
    # The rule verified live against GEO's FTP 2026-09: last 3 digits -> nnn.
    assert platform_bucket("GPL10558") == "GPL10nnn"
    assert platform_bucket("GPL13534") == "GPL13nnn"
    # <=3-digit platforms have no prefix left: bare 'GPLnnn'.
    assert platform_bucket("GPL96") == "GPLnnn"
    assert platform_bucket("GPL570") == "GPLnnn"
    assert platform_bucket("GPL4") == "GPLnnn"


def test_platform_bucket_rejects_non_gpl_ids():
    with pytest.raises(ValueError, match="Not a recognized GPL id"):
        platform_bucket("ILMN_v4")
    with pytest.raises(ValueError):
        platform_bucket("")


def test_annot_url_composes_bucket_and_path():
    assert annot_url("GPL10558") == (
        "https://ftp.ncbi.nlm.nih.gov/geo/platforms/GPL10nnn/GPL10558/"
        "annot/GPL10558.annot.gz"
    )
    assert annot_url("GPL96") == (
        "https://ftp.ncbi.nlm.nih.gov/geo/platforms/GPLnnn/GPL96/"
        "annot/GPL96.annot.gz"
    )


def _write_cache(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ID", "gene_symbol", "entrez_id"])
        writer.writerows(rows)


def test_load_probe_map_reads_real_cache_format(tmp_path):
    cache = tmp_path / "GPLTEST_probe_map.csv"
    _write_cache(cache, [
        ["ILMN_0001", "DDR1", "780"],
        ["ILMN_0002", "HSP90AA1", "3320"],
        ["ILMN_0003", "MAPK1", "5594"],
    ])
    mapping = load_probe_map("GPLTEST", cache_path=str(cache))
    assert mapping == {
        "ILMN_0001": "DDR1",
        "ILMN_0002": "HSP90AA1",
        "ILMN_0003": "MAPK1",
    }


def test_load_probe_map_never_falls_back_when_cache_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="download_probe_map"):
        load_probe_map("GPL999", cache_path=str(tmp_path / "absent.csv"))

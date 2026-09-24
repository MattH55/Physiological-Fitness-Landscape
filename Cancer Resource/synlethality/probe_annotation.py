"""
Phase 1 (Signature-transfer modifier x drug predictor build order,
2026-09-23): the probe-annotation gap, solved once, centrally.

**What blocked GSE48398 (Illumina GPL10558), GSE10043 (Affymetrix GPL96),
and GSE75127 (Affymetrix GPL570) before**: mapping a platform's own probe
IDs (ILMN_xxxxxxx, or Affymetrix probe-set IDs) to gene symbols needs a
real annotation table, and the only free path found earlier
(`ingest/geo_modifiers.py`'s original investigation) was GEO's own
`<GPL>_family.soft.gz` file -- which bundles the platform record together
with EVERY series ever submitted on it, 43GB for GPL10558 alone. Not a
usable route.

**The real fix**: GEO separately publishes a much smaller, curated,
platform-only annotation file at a different path --
`<GPL>.annot.gz` under `.../platforms/<bucket>/<GPL>/annot/` -- containing
exactly the probe-to-gene mapping (`ID`, `Gene symbol`, `Gene ID`
[Entrez]) and nothing else. Real sizes: GPL10558 (Illumina HumanHT-12
V4.0) 7.0MB, GPL96 (Affymetrix HG-U133A) 4.3MB, GPL570 (Affymetrix
HG-U133 Plus 2.0) 8.1MB -- three to four orders of magnitude smaller than
the family file, and the same real, curated GEO-maintained mapping.

**The real bucketing rule**, verified against all three platforms above
(not guessed): GEO shards its platform FTP directories by replacing a
platform ID's last 3 digits with `nnn` -- e.g. `GPL10558` -> `GPL10nnn`.
For platform IDs with 3 or fewer digits (e.g. `GPL96`, `GPL570`), there
are no digits left after stripping 3, so the bucket is simply `GPLnnn`
with no numeric prefix. This module implements that rule once, generally,
rather than hand-mapping each series' bucket the way earlier stub
docstrings anticipated doing ("shared infrastructure, not per-series").
"""

from __future__ import annotations

import csv
import gzip
import io
import os
import re

from synlethality import config

DATA_DIR = os.path.join(config.DATA_DIR, "geo_platforms")


def platform_bucket(gpl_id: str) -> str:
    """Real GEO FTP sharding rule for a platform ID, e.g. 'GPL10558' ->
    'GPL10nnn', 'GPL96' -> 'GPLnnn'. Verified 2026-09-23 against
    GPL10558/GPL96/GPL570's real directory listings."""
    m = re.match(r"^GPL(\d+)$", gpl_id)
    if not m:
        raise ValueError(f"Not a recognized GPL id: {gpl_id!r}")
    digits = m.group(1)
    prefix = digits[:-3] if len(digits) > 3 else ""
    return f"GPL{prefix}nnn"


def annot_url(gpl_id: str) -> str:
    bucket = platform_bucket(gpl_id)
    return f"https://ftp.ncbi.nlm.nih.gov/geo/platforms/{bucket}/{gpl_id}/annot/{gpl_id}.annot.gz"


def _cache_path(gpl_id: str) -> str:
    return os.path.join(DATA_DIR, f"{gpl_id}_probe_map.csv")


def download_probe_map(gpl_id: str, cache_path: str | None = None) -> str:
    """Download the real, small `.annot.gz` for `gpl_id` (no gate -- GEO's
    own FTP, verified 2026-09-23) and cache the parsed probe -> gene symbol
    mapping as a small local CSV (`ID,gene_symbol,entrez_id`), stripping
    the surrounding SOFT-format header/footer and the ~20 other annotation
    columns this project doesn't need. Returns the cache path.
    """
    import requests

    cache_path = cache_path or _cache_path(gpl_id)
    url = annot_url(gpl_id)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    text = gzip.decompress(resp.content).decode("utf-8", errors="replace")

    lines = text.splitlines()
    try:
        start = lines.index("!platform_table_begin") + 1
    except ValueError as exc:
        raise ValueError(f"{gpl_id}: no !platform_table_begin marker found in real annot file") from exc
    end = next(i for i in range(start, len(lines)) if lines[i] == "!platform_table_end")
    table_lines = lines[start:end]

    reader = csv.DictReader(io.StringIO("\n".join(table_lines)), delimiter="\t")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    n = 0
    with open(cache_path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["ID", "gene_symbol", "entrez_id"])
        for row in reader:
            symbol = (row.get("Gene symbol") or "").strip()
            if not symbol:
                continue  # real control/unannotated probe; not guessed
            writer.writerow([row["ID"], symbol, (row.get("Gene ID") or "").strip()])
            n += 1
    return cache_path, n


def load_probe_map(gpl_id: str, cache_path: str | None = None) -> dict[str, str]:
    """Real probe ID -> gene symbol mapping for `gpl_id`, from the local
    cache `download_probe_map` wrote. Raises FileNotFoundError if not yet
    downloaded -- never falls back to a guessed or partial mapping."""
    cache_path = cache_path or _cache_path(gpl_id)
    if not os.path.isfile(cache_path):
        raise FileNotFoundError(
            f"{cache_path} not found. Run "
            f"probe_annotation.download_probe_map({gpl_id!r}) first -- "
            f"real download from {annot_url(gpl_id)}, no gate."
        )
    mapping = {}
    with open(cache_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            mapping[row["ID"]] = row["gene_symbol"]
    return mapping

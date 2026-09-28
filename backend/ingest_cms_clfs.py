"""
CMS Clinical Laboratory Fee Schedule (CLFS) ingestion.

Implements price-data-sources-build-spec.md, source #1 (authoritative tier):
downloads the current CLFS national payment rate file, parses it, and joins
it onto the existing HCPCS/CPT billing-code table already built for the
biomarker -> test pipeline.

CMS reorganizes the CLFS files page periodically (confirmed by hand on
2026-09-12: the files live under
https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files
as quarterly zips named e.g. "26clabq3.zip", gated behind an AMA license
click-through at /apps/ama/license.asp that resolves to a plain GET of
`{base}/files/zip/<slug>.zip?agree=yes`). This module re-discovers the
current file from that listing page rather than hardcoding a URL, but the
regex it uses to find zip links is exactly the kind of thing that breaks
silently if CMS changes the page layout — `discover_current_clfs_file()`
raises rather than guessing if it can't find a confident match, and the
current slug can always be forced via the CLFS_FILE_SLUG env var.

Only HCPCS-keyed rows are used for pricing (see TEST_COST_BUILD_SPEC.md
§0.3 — CPT code *descriptions* are AMA-copyrighted; HCPCS is public domain
and preferred). The CSV happens to key everything by "HCPCS" column but
that column holds both HCPCS Level II codes and 5-digit CPT-like codes;
this module stores the rate either way, keyed only by the bare code, and
never republishes the AMA-copyrighted long description text.
"""

import csv
import io
import logging
import os
import re
import zipfile
from datetime import date, datetime
from typing import Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from backend.test_cost_models import (
    TestBillingCode,
    TestCostSummary,
    TestPrice,
    SOURCE_TIER_AUTHORITATIVE,
)

logger = logging.getLogger(__name__)

CLFS_FILES_PAGE = (
    "https://www.cms.gov/medicare/payment/fee-schedules/"
    "clinical-laboratory-fee-schedule-clfs/files"
)
CLFS_LICENSE_BASE = "https://www.cms.gov"

RAW_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "raw", "test_prices", "cms_clfs"
)
MISSING_RATE_LOG = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "missing_clfs_rate.csv"
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OpenSourceMedResearchBot/1.0)",
}

# The files-listing page links to per-quarter *detail* pages (no .zip
# suffix), e.g. .../files/26clabq3 — confirmed by hand on 2026-09-12. The
# actual download link only appears on that detail page, as an AMA
# license click-through: license.asp?file=/files/zip/26clabq3.zip.
_DETAIL_LINK_RE = re.compile(
    r"/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files/([0-9]{2}clabq[0-9]v?[0-9]*)(?:\"|$)",
    re.IGNORECASE,
)
_ZIP_LINK_RE = re.compile(r"license\.asp\?file=/files/zip/([^\"'&]+)\.zip", re.IGNORECASE)


def discover_current_clfs_file(session: Optional[requests.Session] = None) -> str:
    """
    Find the most recent CLFS quarterly file slug (e.g. "26clabq3") via a
    two-step lookup: the files-listing page links to per-quarter detail
    pages (no .zip suffix), and each detail page embeds the actual
    license.asp?file=/files/zip/<slug>.zip download link. Raises
    RuntimeError if either step can't find a confident match — callers
    should fall back to CLFS_FILE_SLUG rather than guessing.
    """
    override = os.environ.get("CLFS_FILE_SLUG")
    if override:
        logger.info(f"Using CLFS_FILE_SLUG override: {override}")
        return override

    session = session or requests.Session()
    resp = session.get(CLFS_FILES_PAGE, headers=_HEADERS, timeout=30)
    resp.raise_for_status()

    detail_slugs = sorted(set(m.group(1).lower() for m in _DETAIL_LINK_RE.finditer(resp.text)))
    if not detail_slugs:
        raise RuntimeError(
            "Could not find any CLFS quarterly detail-page links on "
            f"{CLFS_FILES_PAGE} — CMS may have reorganized the page. "
            "Set CLFS_FILE_SLUG env var to the current slug (e.g. '26clabq3') "
            "as a manual override."
        )
    # Slugs sort lexicographically in the right order for same-length
    # 'YYclabqN' patterns (e.g. '26clabq1' < '26clabq2' < '26clabq3').
    most_recent_detail_slug = detail_slugs[-1]
    logger.info(f"Discovered CLFS detail pages {detail_slugs}; checking most recent: {most_recent_detail_slug}")

    detail_url = f"{CLFS_LICENSE_BASE}/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files/{most_recent_detail_slug}"
    detail_resp = session.get(detail_url, headers=_HEADERS, timeout=30)
    detail_resp.raise_for_status()

    zip_match = _ZIP_LINK_RE.search(detail_resp.text)
    if not zip_match:
        raise RuntimeError(
            f"Found detail page {detail_url} but no license.asp zip download "
            "link on it — CMS may have changed the download mechanism. "
            "Set CLFS_FILE_SLUG env var as a manual override after checking "
            "the page by hand."
        )
    current = zip_match.group(1).lower()
    logger.info(f"Resolved current CLFS file: {current}")
    return current


def download_clfs_zip(slug: str, session: Optional[requests.Session] = None) -> bytes:
    """
    Download the CLFS zip for a given file slug, accepting the AMA license
    click-through the way a browser does (GET with agree=yes — confirmed by
    inspecting the license page's own "Accept" form on 2026-09-12).
    """
    session = session or requests.Session()
    url = f"{CLFS_LICENSE_BASE}/files/zip/{slug}.zip"
    resp = session.get(url, params={"agree": "yes"}, headers=_HEADERS, timeout=60)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "zip" not in content_type and not resp.content[:2] == b"PK":
        raise RuntimeError(
            f"Expected a zip file from {url} but got content-type={content_type!r}. "
            "CMS may require a fresh license click-through path — inspect "
            "https://www.cms.gov/apps/ama/license.asp?file=/files/zip/"
            f"{slug}.zip by hand."
        )
    return resp.content


def _extract_csv_from_zip(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError(f"No .csv file found inside CLFS zip (contents: {zf.namelist()})")
        with zf.open(csv_names[0]) as f:
            return f.read().decode("utf-8", errors="replace")


def parse_clfs_csv(csv_text: str) -> Dict[str, dict]:
    """
    Parse a CLFS PUF CSV into {hcpcs_code: {rate, indicator, eff_date, year}}.

    The PUF CSV has a few free-text header/notice lines before the real
    header row (see fixture in the CY2026 Q3 file: title line, AMA
    copyright notice, a PHE notice, then a blank line, then the real
    "YEAR,HCPCS,MOD,..." header). We locate the header row by content
    rather than a fixed line number so a notice being added/removed doesn't
    silently misalign the columns.

    INDICATOR values seen: 'N' (national rate — usable directly), 'L' or
    other non-N codes generally mean "not a single national rate" (carrier-
    priced / gapfill / local) — per the spec, these are NOT interpolated;
    they are surfaced as flagged/carrier-specific rather than silently
    averaged.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == "YEAR" and "HCPCS" in [c.strip().upper() for c in row]:
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("Could not locate the 'YEAR,HCPCS,...' header row in the CLFS CSV")

    header = [c.strip().upper() for c in rows[header_idx]]
    col = {name: idx for idx, name in enumerate(header)}
    required = {"HCPCS", "RATE", "INDICATOR"}
    missing = required - set(col)
    if missing:
        raise RuntimeError(f"CLFS CSV header is missing expected columns: {missing}")

    out: Dict[str, dict] = {}
    for row in rows[header_idx + 1:]:
        if len(row) <= col["HCPCS"]:
            continue
        hcpcs = row[col["HCPCS"]].strip()
        if not hcpcs:
            continue
        rate_raw = row[col["RATE"]].strip() if col.get("RATE") is not None else ""
        try:
            rate = float(rate_raw)
        except ValueError:
            continue
        indicator = row[col["INDICATOR"]].strip() if col.get("INDICATOR") is not None else ""
        eff_date_raw = row[col.get("EFF_DATE", -1)].strip() if "EFF_DATE" in col else ""
        year = row[col["YEAR"]].strip() if "YEAR" in col else ""

        eff_date = None
        if eff_date_raw and len(eff_date_raw) == 8:
            try:
                eff_date = datetime.strptime(eff_date_raw, "%Y%m%d").date()
            except ValueError:
                eff_date = None

        # A code can appear more than once (e.g. modifier variants); keep
        # the first (base, unmodified) national-rate row we see.
        if hcpcs in out and out[hcpcs]["indicator"] == "N":
            continue
        out[hcpcs] = {
            "rate": rate,
            "indicator": indicator,
            "effective_date": eff_date,
            "year": year,
        }
    return out


def run_cms_clfs_ingestion(
    db: Session,
    slug: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> dict:
    """
    Full ingestion run: discover/download the current CLFS file, parse it,
    join it onto every TestBillingCode row keyed by HCPCS, and upsert
    TestPrice + the tier-1 reference_price fields on TestCostSummary.

    Codes present in TestBillingCode but absent from (or non-national in)
    the CLFS file are NOT interpolated — they're written to
    data/missing_clfs_rate.csv for manual review, per the spec.

    Returns a summary dict: {slug, n_billing_codes, n_priced, n_missing,
    n_carrier_specific, raw_payload_ref}.
    """
    session = session or requests.Session()
    slug = slug or discover_current_clfs_file(session)

    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    zip_bytes = download_clfs_zip(slug, session)

    year_dir = os.path.join(RAW_DATA_DIR, slug[:2] and f"20{slug[:2]}" or "unknown")
    os.makedirs(year_dir, exist_ok=True)
    raw_zip_path = os.path.join(year_dir, f"{slug}.zip")
    with open(raw_zip_path, "wb") as f:
        f.write(zip_bytes)

    csv_text = _extract_csv_from_zip(zip_bytes)
    raw_csv_path = os.path.join(year_dir, f"{slug}.csv")
    with open(raw_csv_path, "w", encoding="utf-8") as f:
        f.write(csv_text)

    rates = parse_clfs_csv(csv_text)
    logger.info(f"Parsed {len(rates)} HCPCS rate rows from CLFS file '{slug}'")

    all_billing_codes: List[TestBillingCode] = db.query(TestBillingCode).filter(
        TestBillingCode.coding_system.in_(["HCPCS", "CPT"])
    ).all()
    # A test can have both an HCPCS and a CPT row for the *same* numeric
    # code (billing systems often share 5-digit codes). Dedupe on
    # (test_id, code) so we don't price — or worse, try to insert — the
    # same CLFS observation twice; prefer HCPCS per TEST_COST_BUILD_SPEC.md
    # §0.3 (public domain, vs. AMA-copyrighted CPT descriptions).
    dedup: Dict[tuple, TestBillingCode] = {}
    for bc in all_billing_codes:
        key = (bc.test_id, bc.code)
        if key not in dedup or bc.coding_system == "HCPCS":
            dedup[key] = bc
    billing_codes = list(dedup.values())

    retrieved = date.today()
    source_url = f"{CLFS_LICENSE_BASE}/files/zip/{slug}.zip"
    raw_payload_ref = os.path.relpath(raw_csv_path, os.path.dirname(os.path.dirname(__file__)))

    n_priced = 0
    n_carrier_specific = 0
    missing_rows = []

    for bc in billing_codes:
        entry = rates.get(bc.code)
        if entry is None:
            missing_rows.append((bc.test_id, bc.coding_system, bc.code, "not_found_in_clfs_file"))
            continue

        is_national = entry["indicator"] == "N"
        if not is_national:
            n_carrier_specific += 1

        price_id = f"cms_clfs_{bc.test_id}_{bc.code}_{retrieved.isoformat()}"
        price = db.query(TestPrice).filter(TestPrice.price_id == price_id).first()
        if price is None:
            price = TestPrice(price_id=price_id)
            db.add(price)

        price.test_id = bc.test_id
        price.source = "cms_clfs"
        price.source_tier = SOURCE_TIER_AUTHORITATIVE
        price.provider = "Medicare"
        price.price_type = "medicare_reimbursement"
        price.payer = None
        price.amount = entry["rate"]
        price.currency = "USD"
        price.geography = "national" if is_national else "carrier_specific_no_national_rate"
        price.state_restrictions = None
        price.retrieved_date = retrieved
        price.effective_date = entry["effective_date"]
        price.collection_period = None
        price.source_url = source_url
        price.source_version = slug
        price.raw_payload_ref = raw_payload_ref
        n_priced += 1

        _update_reference_price(db, bc.test_id, entry["rate"], is_national, retrieved)

    if missing_rows:
        _write_missing_rate_log(missing_rows)

    db.flush()
    return {
        "slug": slug,
        "n_billing_codes": len(billing_codes),
        "n_priced": n_priced,
        "n_missing": len(missing_rows),
        "n_carrier_specific": n_carrier_specific,
        "raw_payload_ref": raw_payload_ref,
        "missing_log": MISSING_RATE_LOG if missing_rows else None,
    }


def _update_reference_price(db: Session, test_id: str, rate: float, is_national: bool, as_of: date) -> None:
    """Update tier-1 (authoritative) reference price fields on TestCostSummary."""
    summary = db.query(TestCostSummary).filter(TestCostSummary.test_id == test_id).first()
    if summary is None:
        summary = TestCostSummary(test_id=test_id)
        db.add(summary)

    summary.reference_price = rate
    summary.reference_price_source = "cms_clfs"
    summary.reference_price_region = "national" if is_national else "carrier_specific"
    summary.reference_price_date = as_of
    summary.reference_price_is_carrier_specific = 0 if is_national else 1

    # Keep the legacy field in sync for callers that still read cms_clfs.
    summary.cms_clfs = rate
    summary.price_date = as_of


def _write_missing_rate_log(rows: List[tuple]) -> None:
    """
    Log HCPCS/CPT codes with no CLFS rate to a CSV for manual review,
    per the spec ("leave the row absent rather than interpolating, and log
    it to a missing_clfs_rate list").
    """
    os.makedirs(os.path.dirname(MISSING_RATE_LOG), exist_ok=True)
    today = date.today().isoformat()

    already_logged_today = set()
    if os.path.exists(MISSING_RATE_LOG):
        with open(MISSING_RATE_LOG, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("checked_at") == today:
                    already_logged_today.add((r["test_id"], r["coding_system"], r["code"]))

    write_header = not os.path.exists(MISSING_RATE_LOG)
    new_rows = [
        (test_id, coding_system, code, reason)
        for test_id, coding_system, code, reason in rows
        if (test_id, coding_system, code) not in already_logged_today
    ]
    if not new_rows:
        return
    with open(MISSING_RATE_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["test_id", "coding_system", "code", "reason", "checked_at"])
        for test_id, coding_system, code, reason in new_rows:
            writer.writerow([test_id, coding_system, code, reason, today])
    logger.warning(f"Logged {len(new_rows)} missing/unmapped CLFS rates to {MISSING_RATE_LOG}")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from sqlalchemy.orm import sessionmaker
    from backend.models import get_engine, init_db
    from backend.test_cost_models import init_test_cost_tables

    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")
    engine = get_engine(f"sqlite:///{DB_PATH}")
    init_db(engine)
    init_test_cost_tables(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        result = run_cms_clfs_ingestion(db)
        db.commit()
        logger.info(f"CMS CLFS ingestion complete: {result}")
    finally:
        db.close()

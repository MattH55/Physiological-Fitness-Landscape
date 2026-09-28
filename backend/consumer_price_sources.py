"""
Consumer cash-pay price source framework — price-data-sources-build-spec.md
source #3.

This module is the *shared* ingestion scaffolding for find_a_lab_test and
the eight additional consumer cash-pay sites listed in the spec. It does
three things that are real and safe to run unattended:

1. Checks (and re-checks) each site's robots.txt before any fetch, and
   refuses to fetch a site whose policy hasn't been reviewed or that is
   actively hostile to automated requests (Cloudflare-challenged, etc.).
2. Caches every raw response under
   data/raw/test_prices/<source_slug>/<YYYY-MM-DD>/, never overwriting a
   previous day's pull, and throttles re-fetches to a configurable minimum
   interval (default weekly) per the spec's "polite, low-frequency, cached
   scrape" instruction.
3. Provides the per-test name-matching + price upsert plumbing that a
   per-site parser plugs into.

What this module deliberately does NOT do: parse any individual site's
HTML into prices. Building that reliably requires iterating against each
site's real markup (which changes) and, for several of these sites,
resolving a ToS question a human hasn't signed off on yet (see
robots_txt_status in SOURCE_REGISTRY — several sites are open per
robots.txt but that's necessary, not sufficient, permission). Each site
below has a `parser` slot that raises NotImplementedError with the
concrete blocker until someone (a) reads that site's actual ToS and (b)
writes/verifies the extraction logic against a live page. Wiring a new
site in only requires implementing `parse_price_page()` — the fetch/cache/
robots/upsert plumbing is already done.
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, List, Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from sqlalchemy.orm import Session

from backend.test_cost_models import (
    SOURCE_REGISTRY,
    SOURCE_TIER_CONSUMER_CASH_PAY,
    TestCostSummary,
    TestPrice,
)

logger = logging.getLogger(__name__)

RAW_DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "raw", "test_prices"
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OpenSourceMedResearchBot/1.0; "
                  "+https://landscape.opensourcemed.info)",
}

# Sites confirmed (2026-09-12, see SOURCE_REGISTRY.robots_txt_status) to
# actively block non-browser requests with a Cloudflare challenge, or that
# have not had their ToS read by a human yet. Ingestion refuses to run
# against these regardless of what a live robots.txt check says, until a
# human updates this set.
BLOCKED_PENDING_HUMAN_REVIEW = {"discountedlabs", "request_a_test", "ulta_lab_tests"}

CONSUMER_CASH_PAY_SLUGS = [
    "find_a_lab_test",
    "testing_com",
    "walk_in_lab",
    "ulta_lab_tests",
    "discountedlabs",
    "request_a_test",
    "privatemdlabs",
    "quest_direct",
    "labcorp_ondemand",
]


@dataclass
class RobotsCheckResult:
    slug: str
    allowed: bool
    reason: str
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def check_robots_txt(slug: str, path: str = "/", session: Optional[requests.Session] = None) -> RobotsCheckResult:
    """
    Live robots.txt check for one source + path, using Python's stdlib
    robotparser. This is necessary-but-not-sufficient permission — a
    robots.txt allow does not substitute for reading the site's Terms of
    Service (see module docstring).
    """
    if slug in BLOCKED_PENDING_HUMAN_REVIEW:
        entry = SOURCE_REGISTRY.get(slug, {})
        return RobotsCheckResult(
            slug=slug,
            allowed=False,
            reason=(
                f"Blocked pending human review: {entry.get('robots_txt_status', 'not reviewed')}"
            ),
        )

    entry = SOURCE_REGISTRY.get(slug)
    if entry is None or "base_url" not in entry:
        return RobotsCheckResult(slug=slug, allowed=False, reason="Unknown source slug")

    base_url = entry["base_url"]
    session = session or requests.Session()
    rp = RobotFileParser()
    try:
        resp = session.get(urljoin(base_url, "/robots.txt"), headers=_HEADERS, timeout=15)
        if resp.status_code >= 400:
            return RobotsCheckResult(
                slug=slug, allowed=False,
                reason=f"robots.txt fetch returned HTTP {resp.status_code}",
            )
        rp.parse(resp.text.splitlines())
    except requests.RequestException as e:
        return RobotsCheckResult(slug=slug, allowed=False, reason=f"robots.txt fetch failed: {e}")

    allowed = rp.can_fetch(_HEADERS["User-Agent"], urljoin(base_url, path))
    return RobotsCheckResult(
        slug=slug, allowed=allowed,
        reason="robots.txt allows this path" if allowed else "disallowed by robots.txt",
    )


def _cache_dir(slug: str) -> str:
    d = os.path.join(RAW_DATA_ROOT, slug, date.today().isoformat())
    os.makedirs(d, exist_ok=True)
    return d


def fetch_and_cache(
    slug: str,
    url: str,
    path_for_robots_check: str = "/",
    min_refetch_interval_days: int = 7,
    session: Optional[requests.Session] = None,
    timeout: int = 30,
    retries: int = 2,
    retry_backoff_seconds: float = 5.0,
) -> Optional[str]:
    """
    Fetch `url` for source `slug` if (a) robots.txt allows it and the slug
    isn't in BLOCKED_PENDING_HUMAN_REVIEW, and (b) we haven't already
    cached a pull for this exact URL within `min_refetch_interval_days`.

    Returns the path to the cached raw response, or None if the fetch was
    skipped/refused (reason is logged).
    """
    check = check_robots_txt(slug, path_for_robots_check, session)
    if not check.allowed:
        logger.warning(f"Refusing to fetch {slug} ({url}): {check.reason}")
        return None

    cache_dir = _cache_dir(slug)
    fname = "".join(c if c.isalnum() else "_" for c in url)[-150:] + ".html"
    cache_path = os.path.join(cache_dir, fname)

    # Skip if a same-day-or-recent cached copy already exists anywhere in
    # the last N days of cache directories for this slug+filename.
    slug_root = os.path.join(RAW_DATA_ROOT, slug)
    if os.path.isdir(slug_root):
        for day_dir in sorted(os.listdir(slug_root), reverse=True)[:min_refetch_interval_days]:
            candidate = os.path.join(slug_root, day_dir, fname)
            if os.path.exists(candidate):
                logger.info(f"Using cached pull for {slug} from {day_dir} (within {min_refetch_interval_days}d window)")
                return candidate

    session = session or requests.Session()
    last_error = None
    resp = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            last_error = None
            break
        except requests.RequestException as e:
            last_error = e
            if attempt < retries:
                logger.warning(f"Fetch attempt {attempt + 1} failed for {slug} ({url}): {e}; retrying in {retry_backoff_seconds}s")
                time.sleep(retry_backoff_seconds)
    if last_error is not None:
        logger.error(f"Fetch failed for {slug} ({url}) after {retries + 1} attempts: {last_error}")
        return None

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(resp.text)
    logger.info(f"Cached {slug} pull -> {cache_path}")

    # Be polite: a short pause between requests to the same host.
    time.sleep(3.0)
    return cache_path


@dataclass
class CashPayObservation:
    """One parsed price observation, ready to upsert as a TestPrice row."""
    test_id: str
    amount: float
    provider: Optional[str] = None
    # The exact product this price is for, as named by the store, e.g.
    # "CRP - C-Reactive Protein" (standalone) vs "Basal Inflammation Scan"
    # (a panel). Optional because not every source exposes one.
    product_name: Optional[str] = None
    geography: Optional[str] = None
    state_restrictions: Optional[str] = None
    # The specific per-product page the price came from (preferred), and
    # the comparison page that linked to it (always available).
    source_url: Optional[str] = None
    source_page_url: Optional[str] = None
    effective_date: Optional[date] = None


ParserFn = Callable[[str, str], List[CashPayObservation]]
# A parser takes (cached_html_path, test_id) and returns observations.


def upsert_cash_pay_observations(
    db: Session,
    slug: str,
    observations: List[CashPayObservation],
    raw_payload_ref: Optional[str] = None,
) -> int:
    """
    Upsert parsed cash-pay observations as TestPrice rows with
    source_tier=consumer_cash_pay, price_type=cash_price. Keeps a rolling
    history (does not overwrite prior pulls) per the spec — each day's
    pull gets its own price_id, keyed by retrieval date.
    """
    entry = SOURCE_REGISTRY.get(slug, {})
    retrieved = date.today()
    n = 0
    for obs in observations:
        price_id = f"{slug}_{obs.test_id}_{retrieved.isoformat()}_{n}"
        price = db.query(TestPrice).filter(TestPrice.price_id == price_id).first()
        if price is None:
            price = TestPrice(price_id=price_id)
            db.add(price)

        price.test_id = obs.test_id
        price.source = slug
        price.source_tier = SOURCE_TIER_CONSUMER_CASH_PAY
        price.provider = obs.provider or entry.get("label", slug)
        price.price_type = "cash_price"
        price.payer = None
        price.amount = obs.amount
        price.currency = "USD"
        price.geography = obs.geography
        price.state_restrictions = obs.state_restrictions
        price.retrieved_date = retrieved
        price.effective_date = obs.effective_date
        price.source_url = obs.source_url
        price.source_version = None
        price.raw_payload_ref = raw_payload_ref
        price.product_name = obs.product_name
        n += 1
    return n


def is_likely_panel(product_name: Optional[str], test_name: Optional[str] = None) -> bool:
    """
    Heuristic: does this product name describe a multi-analyte panel rather
    than the single analyte we're pricing?

    Why this exists: consumer lab stores sell an analyte two ways — as its
    own test (e.g. "Alanine Aminotransferase (ALT)") and bundled inside a
    panel ("Comprehensive Metabolic Panel", "Hepatic Function Panel",
    "Basal Inflammation Scan"). Both are real, correctly-scraped prices,
    but only the standalone one is comparable to that biomarker's own
    test cost. Verified against the live 2026-09-12 findlabtest.com pulls:
    of the 10 ALT cards, 8 were panels, which is exactly why leaving them
    blended pushes the "ALT price" up toward panel territory.

    Deliberately keyword-based and conservative: an unrecognised name is
    treated as standalone (False), and the raw per-observation product
    names are always retained, so a human can audit every classification
    rather than trusting a black box.
    """
    if not product_name:
        # No name captured (some stores only expose a SKU link). Not
        # enough evidence to call it a panel.
        return False
    name = product_name.lower()
    panel_keywords = (
        "panel", "profile", "scan", "screen", "checkup", "check-up",
        "comprehensive", "metabolic", "basic", "complete", "bundle",
        "package", "wellness", "executive", "annual", "basal", "arthritis",
        "cardio", "thyroid", "hormone", "female", "male",
    )
    if any(k in name for k in panel_keywords):
        return True
    # A name listing multiple analytes separated by "/", "&", "+", ","
    # or " and " is a multi-analyte product.
    if re.search(r"[&+]|,|\band\b|(?<=\w)/(?=\w)", name):
        return True
    return False


def update_cash_pay_summary(
    db: Session,
    test_id: str,
    test_name: Optional[str] = None,
) -> TestCostSummary:
    """
    Recompute tier-3 (consumer_cash_pay) min/median/max from the most
    recent day's worth of consumer_cash_pay TestPrice observations for
    this test. Per the spec ("keep a rolling history... use a recency-
    weighted average or the most recent observation, decided explicitly"):
    the chosen default here is "most recent retrieval date, all
    observations from that date" — every provider/site price pulled on
    that date counts (a single site can legitimately report several
    provider prices for one test), but a stale pull from a week or month
    ago doesn't silently drag the range down.

    Also records a standalone-only subset (`cash_pay_standalone_*`) that
    excludes products classified as multi-analyte panels by
    is_likely_panel(). The blended range stays the headline figure — the
    spec asks for all consumer observations — but the standalone figure
    is the one that's genuinely comparable to this biomarker's own cost,
    since a panel's price buys several other analytes too.
    """
    prices = db.query(TestPrice).filter(
        TestPrice.test_id == test_id,
        TestPrice.source_tier == SOURCE_TIER_CONSUMER_CASH_PAY,
    ).all()

    if not prices:
        amounts = []
        standalone_amounts = []
    else:
        most_recent_date = max((p.retrieved_date or date.min) for p in prices)
        recent = [p for p in prices if p.retrieved_date == most_recent_date]
        amounts = sorted(p.amount for p in recent)
        standalone_amounts = sorted(
            p.amount for p in recent if not is_likely_panel(p.product_name, test_name)
        )
    summary = db.query(TestCostSummary).filter(TestCostSummary.test_id == test_id).first()
    if summary is None:
        summary = TestCostSummary(test_id=test_id)
        db.add(summary)

    def _median(vals):
        n = len(vals)
        mid = n // 2
        return vals[mid] if n % 2 == 1 else (vals[mid - 1] + vals[mid]) / 2

    if amounts:
        median = _median(amounts)
        summary.cash_pay_min = amounts[0]
        summary.cash_pay_median = median
        summary.cash_pay_max = amounts[-1]
        summary.cash_pay_source_count = len(amounts)
        summary.cash_pay_date = date.today()
        # Keep legacy d2c_* fields in sync.
        summary.d2c_min = amounts[0]
        summary.d2c_median = median
        summary.d2c_max = amounts[-1]
        summary.reference_consumer_price = median
        summary.price_date = date.today()

    if standalone_amounts:
        summary.cash_pay_standalone_min = standalone_amounts[0]
        summary.cash_pay_standalone_median = _median(standalone_amounts)
        summary.cash_pay_standalone_max = standalone_amounts[-1]
        summary.cash_pay_standalone_count = len(standalone_amounts)
    else:
        # Distinguish "no standalone price exists" (None) from "a
        # standalone price of zero" ($0.00) — for vitamin D every product
        # in this source is a panel, so there is genuinely no standalone
        # figure and the pane must not print a $0.00 price.
        summary.cash_pay_standalone_min = None
        summary.cash_pay_standalone_median = None
        summary.cash_pay_standalone_max = None
        summary.cash_pay_standalone_count = 0

    return summary


def registry_status_report() -> List[dict]:
    """Human-readable status of every consumer cash-pay source, for an
    audit endpoint / manual-review checklist."""
    report = []
    for slug in CONSUMER_CASH_PAY_SLUGS:
        entry = SOURCE_REGISTRY.get(slug, {})
        report.append({
            "slug": slug,
            "label": entry.get("label"),
            "base_url": entry.get("base_url"),
            "robots_txt_status": entry.get("robots_txt_status"),
            "blocked_pending_human_review": slug in BLOCKED_PENDING_HUMAN_REVIEW,
            "parser_implemented": entry.get("implemented", False),
        })
    return report

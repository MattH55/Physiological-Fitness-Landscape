"""
Find A Lab Test (findlabtest.com) ingestion — the reference consumer
cash-pay parser called out in price-data-sources-build-spec.md ("keep the
existing findalabtest.com scrape... don't discard it").

Confirmed by hand on 2026-09-12:
- robots.txt only disallows the Internet Archive bot (`ia_archiver`); no
  blanket disallow for a generic user agent.
- terms-of-service page has no scraping/automation restriction.
- The site's own client-side search widget calls a *public, read-only*
  Algolia index using a search-only API key that's shipped in the page
  source (`window.algolia_settings`) — this is the intended way visitors'
  browsers query the catalog, not a private endpoint we're bypassing.
- The actual per-test price comparison page is a plain server-rendered
  GET: `/lab-test/search?q=<internal_search_id>`, where the id (e.g.
  "qt4420" for CRP) comes from the Algolia `quest_tests` index.

This still fetches at most once per test per day (via
consumer_price_sources.fetch_and_cache's cache-by-date), consistent with
the spec's "polite, low-frequency, cached scrape" instruction, and stores
the raw HTML for audit under data/raw/test_prices/find_a_lab_test/.
"""

import logging
import os
import re
from datetime import date
from typing import Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from backend.consumer_price_sources import (
    CashPayObservation,
    fetch_and_cache,
    update_cash_pay_summary,
    upsert_cash_pay_observations,
)
from backend.test_cost_models import LabTest, SOURCE_REGISTRY

logger = logging.getLogger(__name__)

ALGOLIA_APP_ID = "76U86Z1DD2"
ALGOLIA_SEARCH_KEY = "8364f3718e68949360433a738ae79cdb"  # public search-only key, shipped client-side by findlabtest.com itself
ALGOLIA_QUEST_INDEX = "production_labtest_quest_tests"
ALGOLIA_QUERY_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_QUEST_INDEX}/query"

SEARCH_URL = "https://www.findlabtest.com/lab-test/search"

# Curated (test_id -> Quest internal_search_id) map. Each id was resolved
# via the Algolia quest_tests index on 2026-09-12 and manually reviewed
# against the returned quest_test_name (see the comment on each line) —
# per TEST_COST_BUILD_SPEC.md §6, this is "curated manual mapping",
# review_status MANUAL_VERIFIED, not blind fuzzy-match auto-publish.
# estimated_gfr maps to plain serum Creatinine (qt375): eGFR itself is a
# calculated value, not a directly orderable Quest test, and creatinine is
# what the cash-pay sites actually sell to get there.
TEST_ID_TO_QUEST_SEARCH_ID = {
    "test_high_sensitivity_crp": "qt4420",   # "C-Reactive Protein (CRP)"
    "test_hba1c": "qt496",                   # "Hemoglobin A1c"
    "test_ldl_cholesterol": "qt8293",        # "Direct LDL"
    "test_hdl_cholesterol": "qt608",         # "HDL Cholesterol"
    "test_triglycerides": "qt896",           # "Triglycerides"
    "test_estimated_gfr": "qt375",           # "Creatinine" (eGFR is derived, not directly orderable)
    "test_alanine_aminotransferase": "qt823",  # "Alanine Aminotransferase (ALT)"
    "test_aspartate_aminotransferase": "qt822",  # "Aspartate Aminotransferase (AST)"
    "test_serum_25_hydroxyvitamin_d": "qt92888",  # "QuestAssureD (25-Hydroxyvitamin D)"
    "test_serum_ferritin": "qt457",          # "Ferritin"
}


def resolve_quest_search_id(query: str, session: Optional[requests.Session] = None) -> Optional[dict]:
    """
    Look up a candidate Quest test via the site's own public Algolia index.
    Returns the raw top hit (or None) — candidate generation only, per
    TEST_COST_BUILD_SPEC.md §6 fuzzy-match rule; never auto-published
    without a human adding it to TEST_ID_TO_QUEST_SEARCH_ID above.
    """
    session = session or requests.Session()
    resp = session.post(
        ALGOLIA_QUERY_URL,
        json={"query": query, "hitsPerPage": 3},
        headers={
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_SEARCH_KEY,
            "Referer": "https://www.findlabtest.com/",
        },
        timeout=20,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    return hits[0] if hits else None


def parse_price_comparison_page(html: str) -> List[CashPayObservation]:
    """
    Parse a /lab-test/search?q=<id> page into one CashPayObservation per
    store card. Uses "total price should be $X.XX" (checkout total,
    including any per-order requisition charge) rather than the bare panel
    price shown next to the Order button, since the checkout total is what
    a buyer actually pays.

    Also captures, per card, the store's own product URL and the product
    name, both of which are already present in the markup. These matter:

    - source_url: per price-data-sources-build-spec.md, every observation
      must be traceable to the specific page it came from. Storing only
      the generic /lab-test/search URL (as this parser originally did)
      makes an individual price unauditable — you can't tell which
      product a number refers to.
    - product name: a single store often sells the analyte standalone
      *and* bundled inside multi-analyte panels at a different price
      (e.g. quest "STTM 8.0 ALT & AST" at $22.95 alongside standalone
      ALT). Both are real prices, but only the standalone one is
      comparable to the biomarker's own cost. Recording the name lets
      the summary logic and a human reviewer separate the two instead of
      silently averaging a 2-analyte panel into a single-analyte price.

    Cards whose store name can't be resolved are still emitted (with the
    SOURCE_REGISTRY label as the provider) rather than dropped, so a
    markup change degrades the provider label instead of losing the price.
    """
    blocks = re.split(r'<div id="card_body_\d+">', html)[1:]
    observations = []
    for block in blocks:
        store_m = re.search(
            r'data-ga-event-category="store_name_click"\s+data-ga-event-action="([^"]+)"', block
        )
        if not store_m:
            store_m = re.search(r'Order from ([A-Za-z0-9 .&\'-]+)</p>', block)
        total_m = re.search(r'total price should be\s*\n?\s*\$([\d,]+\.\d{2})', block)
        if not total_m:
            continue
        if store_m:
            store = store_m.group(1).strip()
        else:
            # Fall back to the store whose /store/<slug>/ link appears in
            # this card, then to the source label. Never leave it blank.
            store_slug_m = re.search(r'href="/store/([a-z0-9-]+)/"', block)
            store = (
                SOURCE_REGISTRY.get("find_a_lab_test", {}).get("label", "find_a_lab_test")
                if not store_slug_m else store_slug_m.group(1).replace("-", " ").title()
            )

        # The store's own product page + visible product name. The card's
        # *first* outbound link is the "Order" button (literal text
        # "Order"), so that must be skipped — the product link lives in
        # the `<div class="f6 fw7 lh-copy">` name block. Fall back to the
        # store-name link, then to no name.
        product_url = None
        product_name = None
        name_div_m = re.search(r'<div class="f6 fw7 lh-copy">(.*?)</div>', block, re.S)
        search_scope = name_div_m.group(1) if name_div_m else block
        out_m = re.search(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>\s*([^<]+?)\s*</a>',
            search_scope, re.S,
        )
        if not out_m:
            out_m = re.search(
                r'<a[^>]*href="(https?://[^"]+)"[^>]*>\s*([^<]+?)\s*</a>',
                block, re.S,
            )
        if out_m:
            candidate_url = out_m.group(1).strip()
            candidate_name = out_m.group(2).strip()
            # "Order" is the button label, never a product name. Keep the
            # URL (it is the only per-SKU deep link some stores expose)
            # but don't record a bogus product name.
            if candidate_name.lower() != "order":
                product_url = candidate_url
                product_name = candidate_name
            else:
                product_url = candidate_url

        amount = float(total_m.group(1).replace(",", ""))
        observations.append(CashPayObservation(
            test_id="",  # filled in by caller
            amount=amount,
            provider=store,
            product_name=product_name,
            source_url=product_url or SEARCH_URL,
            source_page_url=SEARCH_URL,
        ))
    return observations


def ingest_find_a_lab_test_for_test(
    db: Session,
    test_id: str,
    quest_search_id: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> int:
    """
    Ingest cash-pay observations for one internal test_id. Returns the
    number of observations upserted (0 if the fetch was refused/cached-skip
    yielded nothing new, or the page had no parseable cards).
    """
    quest_search_id = quest_search_id or TEST_ID_TO_QUEST_SEARCH_ID.get(test_id)
    if not quest_search_id:
        logger.warning(f"No curated Quest search id for {test_id}; skipping. "
                        f"Add one to TEST_ID_TO_QUEST_SEARCH_ID after resolving via resolve_quest_search_id().")
        return 0

    url = f"{SEARCH_URL}?q={quest_search_id}"
    cached_path = fetch_and_cache(
        "find_a_lab_test", url, path_for_robots_check="/lab-test/search", session=session,
        timeout=45, retries=3, retry_backoff_seconds=10.0,
    )
    if cached_path is None:
        return 0

    with open(cached_path, encoding="utf-8") as f:
        html = f.read()

    observations = parse_price_comparison_page(html)
    for obs in observations:
        obs.test_id = test_id

    if not observations:
        logger.warning(f"No price cards parsed for {test_id} ({url}) — page structure may have changed.")
        return 0

    raw_payload_ref = os.path.relpath(cached_path, os.path.dirname(os.path.dirname(__file__)))
    n = upsert_cash_pay_observations(db, "find_a_lab_test", observations, raw_payload_ref=raw_payload_ref)
    # The LabTest row carries the canonical name; product_name is overloaded
    # (it holds the *store's* product title, e.g. "Hepatic Function Panel"),
    # so we need the analyte's own name to decide if a product is a panel.
    lab_test = db.query(LabTest).filter(LabTest.test_id == test_id).first()
    update_cash_pay_summary(
        db, test_id,
        test_name=(lab_test.test_name if lab_test else None),
    )
    logger.info(f"{test_id}: upserted {n} find_a_lab_test observations "
                f"(range ${min(o.amount for o in observations):.2f}-${max(o.amount for o in observations):.2f})")
    return n


def ingest_find_a_lab_test_all(db: Session, test_ids: Optional[List[str]] = None) -> Dict[str, int]:
    """Ingest every curated test (or a given subset). Commits are the caller's responsibility."""
    session = requests.Session()
    test_ids = test_ids or list(TEST_ID_TO_QUEST_SEARCH_ID.keys())
    results = {}
    for test_id in test_ids:
        try:
            results[test_id] = ingest_find_a_lab_test_for_test(db, test_id, session=session)
        except requests.RequestException as e:
            logger.error(f"Fetch failed for {test_id}: {e}")
            results[test_id] = 0
    return results


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
        result = ingest_find_a_lab_test_all(db)
        db.commit()
        logger.info(f"find_a_lab_test ingestion complete: {result}")
    finally:
        db.close()

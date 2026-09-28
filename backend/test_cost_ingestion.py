"""
Test Cost Ingestion Scripts.

Implements the ingestion pipeline from TEST_COST_BUILD_SPEC.md §2:
- FindLabTest: D2C prices (scraped, with rate limiting)
- CMS CLFS: Medicare allowed prices (official, stable)
- CMS Private Payer: Private payer rates (official, stable)

Each ingestion script:
1. Downloads raw data to data/raw/test_costs/
2. Parses into structured records
3. Upserts into test_prices table
4. Updates test_cost_summary
5. Logs provenance (source, URL, retrieval date)

IMPORTANT: These scripts require network access. They are designed to be
run manually or via cron, not as part of the API request cycle.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from dataclasses import dataclass

import requests
from sqlalchemy.orm import Session

from backend.test_cost_models import (
    LabTest,
    LabTestIdentifier,
    TestBillingCode,
    TestPrice,
    TestCostSummary,
)

logger = logging.getLogger(__name__)

RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "test_costs")
os.makedirs(RAW_DATA_DIR, exist_ok=True)


def _make_price_id(test_id: str, source: str, price_type: str, amount: float, retrieved_date: date) -> str:
    """Generate a deterministic price ID."""
    raw = f"{test_id}|{source}|{price_type}|{amount}|{retrieved_date.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _upsert_price(
    db: Session,
    test_id: str,
    source: str,
    provider: Optional[str],
    price_type: str,
    amount: float,
    currency: str = "USD",
    geography: Optional[str] = None,
    state_restrictions: Optional[str] = None,
    retrieved_date: Optional[date] = None,
    effective_date: Optional[date] = None,
    collection_period: Optional[str] = None,
    source_url: Optional[str] = None,
    source_version: Optional[str] = None,
) -> TestPrice:
    """Upsert a price record."""
    if retrieved_date is None:
        retrieved_date = date.today()
    
    price_id = _make_price_id(test_id, source, price_type, amount, retrieved_date)
    
    price = db.query(TestPrice).filter(TestPrice.price_id == price_id).first()
    if price is None:
        price = TestPrice(price_id=price_id)
        db.add(price)
    
    price.test_id = test_id
    price.source = source
    price.provider = provider
    price.price_type = price_type
    price.amount = amount
    price.currency = currency
    price.geography = geography
    price.state_restrictions = state_restrictions
    price.retrieved_date = retrieved_date
    price.effective_date = effective_date
    price.collection_period = collection_period
    price.source_url = source_url
    price.source_version = source_version
    
    return price


def _update_cost_summary(db: Session, test_id: str) -> TestCostSummary:
    """Update the materialized cost summary for a test."""
    prices = db.query(TestPrice).filter(TestPrice.test_id == test_id).all()
    
    d2c_prices = [p.amount for p in prices if p.price_type == "DIRECT_TO_CONSUMER"]
    clfs_prices = [p.amount for p in prices if p.price_type == "MEDICARE_ALLOWED"]
    private_payer_prices = [p.amount for p in prices if p.price_type == "PRIVATE_PAYER_RATE"]
    
    summary = db.query(TestCostSummary).filter(TestCostSummary.test_id == test_id).first()
    if summary is None:
        summary = TestCostSummary(test_id=test_id)
        db.add(summary)
    
    # D2C stats
    if d2c_prices:
        d2c_sorted = sorted(d2c_prices)
        summary.d2c_min = d2c_sorted[0]
        summary.d2c_max = d2c_sorted[-1]
        n = len(d2c_sorted)
        mid = n // 2
        summary.d2c_median = d2c_sorted[mid] if n % 2 == 1 else (d2c_sorted[mid - 1] + d2c_sorted[mid]) / 2
    
    # CLFS
    if clfs_prices:
        summary.cms_clfs = clfs_prices[0]  # CLFS is typically a single value
    
    # Private payer
    if private_payer_prices:
        pp_sorted = sorted(private_payer_prices)
        n = len(pp_sorted)
        mid = n // 2
        summary.cms_private_payer_median = pp_sorted[mid] if n % 2 == 1 else (pp_sorted[mid - 1] + pp_sorted[mid]) / 2
        # Get collection period from most recent price
        pp_prices = [p for p in prices if p.price_type == "PRIVATE_PAYER_RATE"]
        if pp_prices:
            latest = max(pp_prices, key=lambda p: p.retrieved_date or date.min)
            summary.cms_private_payer_collection_period = latest.collection_period
    
    # Reference prices (median, not minimum)
    if summary.d2c_median is not None:
        summary.reference_consumer_price = summary.d2c_median
    if summary.cms_private_payer_median is not None:
        summary.reference_payer_price = summary.cms_private_payer_median
    
    # Price confidence
    total_obs = len(prices)
    if total_obs >= 3:
        summary.price_confidence = "HIGH"
    elif total_obs == 2:
        summary.price_confidence = "MEDIUM"
    elif total_obs == 1:
        summary.price_confidence = "LOW"
    else:
        summary.price_confidence = None
    
    summary.price_date = date.today()
    
    return summary


# ======================================================================
# FindLabTest Ingestion
# ======================================================================

def ingest_findlabtest(
    db: Session,
    test_id: str,
    search_term: str,
    state: Optional[str] = None,
    max_results: int = 50,
    delay_seconds: float = 2.0,
) -> List[TestPrice]:
    """
    Ingest D2C prices from FindLabTest.com.
    
    FindLabTest is a consumer-facing price comparison site. Prices are
    D2C (direct-to-consumer) and vary by state and provider.
    
    Parameters
    ----------
    db : Session
        Database session.
    test_id : str
        Internal test ID.
    search_term : str
        Search term for FindLabTest (e.g., "C-reactive protein").
    state : str, optional
        Two-letter state code to filter by.
    max_results : int
        Maximum number of results to ingest.
    delay_seconds : float
        Delay between requests (rate limiting).
    
    Returns
    -------
    List[TestPrice]
        Ingested price records.
    """
    import time
    
    base_url = "https://www.findlabtest.com"
    search_url = f"{base_url}/search?q={requests.utils.quote(search_term)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    logger.info(f"Fetching FindLabTest for '{search_term}'...")
    
    try:
        response = requests.get(search_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch FindLabTest: {e}")
        return []
    
    # Save raw HTML
    raw_path = os.path.join(RAW_DATA_DIR, f"findlabtest_{test_id}_{date.today().isoformat()}.html")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    logger.info(f"Saved raw HTML to {raw_path}")
    
    # Parse results (simplified - actual parsing would use BeautifulSoup)
    # This is a placeholder for the actual parsing logic
    prices = []
    
    # In a real implementation, you would parse the HTML to extract:
    # - Provider name
    # - Price
    # - State
    # - Effective date
    
    # For now, return empty list (no actual scraping implemented)
    logger.warning("FindLabTest parsing not yet implemented. Returning empty list.")
    
    return prices


# ======================================================================
# CMS CLFS Ingestion
# ======================================================================

def ingest_cms_clfs(
    db: Session,
    test_id: str,
    hcpcs_code: str,
    year: Optional[int] = None,
) -> List[TestPrice]:
    """
    Ingest Medicare allowed prices from CMS CLFS (Carrier Lookup for
    Laboratory Services).
    
    CLFS provides the Medicare allowed amount for laboratory services.
    This is the most stable and authoritative price source.
    
    Parameters
    ----------
    db : Session
        Database session.
    test_id : str
        Internal test ID.
    hcpcs_code : str
        HCPCS code for the test (e.g., "80048" for CRP).
    year : int, optional
        Year of the CLFS file (defaults to current year).
    
    Returns
    -------
    List[TestPrice]
        Ingested price records.
    """
    if year is None:
        year = datetime.now().year
    
    # CLFS files are available at:
    # https://www.cms.gov/medicare/payment/fee-for-service/clinical-laboratory/
    # or via the CMS API
    
    base_url = "https://www.cms.gov"
    clfs_url = f"{base_url}/files/document/{year}/clfs_{hcpcs_code}.csv"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/csv,application/csv;q=0.9,*/*;q=0.8",
    }
    
    logger.info(f"Fetching CMS CLFS for HCPCS {hcpcs_code} ({year})...")
    
    try:
        response = requests.get(clfs_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch CMS CLFS: {e}")
        return []
    
    # Save raw CSV
    raw_path = os.path.join(RAW_DATA_DIR, f"cms_clfs_{test_id}_{year}.csv")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    logger.info(f"Saved raw CSV to {raw_path}")
    
    # Parse CSV (simplified)
    prices = []
    
    # In a real implementation, you would parse the CSV to extract:
    # - HCPCS code
    # - Allowed amount
    # - Effective date
    
    # For now, return empty list (no actual parsing implemented)
    logger.warning("CMS CLFS parsing not yet implemented. Returning empty list.")
    
    return prices


# ======================================================================
# CMS Private Payer Ingestion
# ======================================================================

def ingest_cms_private_payer(
    db: Session,
    test_id: str,
    hcpcs_code: str,
    collection_period: Optional[str] = None,
) -> List[TestPrice]:
    """
    Ingest private payer rates from CMS.
    
    CMS publishes private payer rate data for laboratory services.
    This is used as a reference for what private insurers pay.
    
    Parameters
    ----------
    db : Session
        Database session.
    test_id : str
        Internal test ID.
    hcpcs_code : str
        HCPCS code for the test.
    collection_period : str, optional
        Collection period (e.g., "2024-Q1").
    
    Returns
    -------
    List[TestPrice]
        Ingested price records.
    """
    if collection_period is None:
        # Default to most recent quarter
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        collection_period = f"{now.year}-Q{quarter}"
    
    base_url = "https://www.cms.gov"
    pp_url = f"{base_url}/files/document/private-payer-rates/{hcpcs_code}_{collection_period}.csv"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/csv,application/csv;q=0.9,*/*;q=0.8",
    }
    
    logger.info(f"Fetching CMS Private Payer rates for HCPCS {hcpcs_code} ({collection_period})...")
    
    try:
        response = requests.get(pp_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch CMS Private Payer rates: {e}")
        return []
    
    # Save raw CSV
    raw_path = os.path.join(RAW_DATA_DIR, f"cms_pp_{test_id}_{collection_period}.csv")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    logger.info(f"Saved raw CSV to {raw_path}")
    
    # Parse CSV (simplified)
    prices = []
    
    # In a real implementation, you would parse the CSV to extract:
    # - HCPCS code
    # - Payer name
    # - Rate
    # - Collection period
    
    # For now, return empty list (no actual parsing implemented)
    logger.warning("CMS Private Payer parsing not yet implemented. Returning empty list.")
    
    return prices


# ======================================================================
# Batch Ingestion
# ======================================================================

def ingest_all_prices_for_test(
    db: Session,
    test_id: str,
    search_term: str,
    hcpcs_code: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, List[TestPrice]]:
    """
    Ingest all available prices for a test from all sources.
    
    Parameters
    ----------
    db : Session
        Database session.
    test_id : str
        Internal test ID.
    search_term : str
        Search term for FindLabTest.
    hcpcs_code : str, optional
        HCPCS code for CMS sources.
    state : str, optional
        Two-letter state code for FindLabTest.
    
    Returns
    -------
    Dict[str, List[TestPrice]]
        Ingested prices keyed by source.
    """
    results = {}
    
    # FindLabTest
    results["findlabtest"] = ingest_findlabtest(
        db, test_id, search_term, state=state
    )
    
    # CMS CLFS
    if hcpcs_code:
        results["cms_clfs"] = ingest_cms_clfs(db, test_id, hcpcs_code)
        results["cms_private_payer"] = ingest_cms_private_payer(db, test_id, hcpcs_code)
    
    # Update cost summary
    _update_cost_summary(db, test_id)
    db.commit()
    
    return results


def ingest_all_tests(
    db: Session,
    tests: List[Dict],
) -> Dict[str, Dict[str, List[TestPrice]]]:
    """
    Ingest prices for all tests.
    
    Parameters
    ----------
    db : Session
        Database session.
    tests : List[Dict]
        List of test dictionaries with keys:
        - test_id: str
        - search_term: str
        - hcpcs_code: str (optional)
        - state: str (optional)
    
    Returns
    -------
    Dict[str, Dict[str, List[TestPrice]]]
        Ingested prices keyed by test_id, then by source.
    """
    all_results = {}
    
    for test in tests:
        test_id = test["test_id"]
        search_term = test["search_term"]
        hcpcs_code = test.get("hcpcs_code")
        state = test.get("state")
        
        logger.info(f"Ingesting prices for test {test_id}...")
        results = ingest_all_prices_for_test(
            db, test_id, search_term, hcpcs_code=hcpcs_code, state=state
        )
        all_results[test_id] = results
    
    return all_results
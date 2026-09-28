"""
Syncs the real, freshly-scraped/ingested prices in test_cost_summary back
onto Biomarker.test_price_usd / Biomarker.cms_reimbursement_usd — the two
simple fields the standalone-HTML build (build_standalone_html.py) and the
VOI/EHIV pane actually read (biomarker.testPriceUSD / cmsReimbursementUSD).

Why this is needed: build_standalone_html.py's enrichment step prefers
Biomarker.test_price_usd over the live test_cost_summary join whenever the
former is already set (see its `b.get("test_price_usd") if ... is not None
else priced.get(...)` line) — that's the right precedence for a curated
override, but it also means the placeholder numbers seed_test_cost_data.py
originally wrote onto Biomarker stick around even after real data lands in
test_cost_summary, unless something explicitly overwrites them. This
script is that something.

Sets, per biomarker with a mapped LabTest + TestCostSummary row:
  - test_price_usd = cash_pay_standalone_median when the source sells this
    analyte as a standalone product. This matters: most findlabtest.com
    cards are multi-analyte panels, and a panel's price also buys several
    other analytes, so the blended median overstates what this single test
    costs. When the source is panel-only for this analyte (e.g. 25-OH
    vitamin D — all 10 observed cards are panels), cash_pay_standalone_median
    is None and we fall back to the blended cash_pay_median, because some
    price is a better c_test input than none.
  - cms_reimbursement_usd = reference_price if set (tier 1: real CMS CLFS
    national rate), falling back to the legacy cms_clfs field.

The blended median is preserved on Biomarker.cash_pay_blended_median so the
pane can show both and flag when the c_test figure is panel-derived.

Run with: python -m backend.sync_biomarker_prices_from_test_cost
"""

import logging
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import sessionmaker
from backend.models import Biomarker, get_engine, init_db
from backend.test_cost_models import LabTest, TestCostSummary, init_test_cost_tables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")


def sync_prices():
    engine = get_engine(f"sqlite:///{DB_PATH}")
    init_db(engine)
    init_test_cost_tables(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    updated = []
    try:
        tests = db.query(LabTest).filter(LabTest.canonical_biomarker_id.isnot(None)).all()
        for test in tests:
            bm = db.query(Biomarker).filter(Biomarker.id == test.canonical_biomarker_id).first()
            if not bm:
                continue
            summary = db.query(TestCostSummary).filter(TestCostSummary.test_id == test.test_id).first()
            if not summary:
                continue

            changed = False
            # Prefer the standalone-analyte median: it is the price of
            # *this* test, whereas the blended median is dominated by
            # multi-analyte panels whose price also buys other analytes.
            price = summary.cash_pay_standalone_median
            if price is None:
                price = summary.cash_pay_median
            if price is not None and bm.test_price_usd != price:
                bm.test_price_usd = round(price, 2)
                changed = True

            blended = summary.cash_pay_median
            if blended is not None and bm.cash_pay_blended_median != blended:
                bm.cash_pay_blended_median = round(blended, 2)
                changed = True

            ref = summary.reference_price if summary.reference_price is not None else summary.cms_clfs
            if ref is not None and bm.cms_reimbursement_usd != ref:
                bm.cms_reimbursement_usd = round(ref, 2)
                changed = True

            if changed:
                updated.append((bm.slug, bm.test_price_usd, bm.cms_reimbursement_usd, blended))

        db.commit()
    finally:
        db.close()

    logger.info(f"Synced {len(updated)} biomarker price fields from test_cost_summary:")
    for slug, price, cms, blended in updated:
        suffix = "" if price == blended else f"  (blended all-products median=${blended})"
        logger.info(f"  {slug}: test_price_usd=${price} cms_reimbursement_usd=${cms}{suffix}")
    return updated


if __name__ == "__main__":
    sync_prices()

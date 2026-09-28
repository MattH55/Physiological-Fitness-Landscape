"""
Regression tests for the consumer cash-pay price rollup.

The invariant these lock down: `update_cash_pay_summary` must never let a
CMS/Medicare rate leak into a cash-pay statistic, and must never blend a
multi-analyte panel price into the standalone-analyte figure.

Both were live bugs, not hypotheticals:
  * Fabricated legacy seed rows (CMS_CLFS / CMS_PRIMARY_PAYER) were being
    re-inserted on every re-seed with today's date, so they won the
    "most recent date" rollup and were averaged in as if they were
    cash-pay observations.
  * findlabtest.com sells analytes both standalone and inside panels
    ("Alanine Aminotransferase (ALT)" vs "Hepatic Function Panel"). Of the
    10 ALT cards scraped 2026-09-12, 9 were panels, which dragged the
    reported ALT price well above any true standalone quote.
"""

import itertools
import os
import sys
from datetime import date, timedelta

import pytest
from sqlalchemy import Column, Index, Integer, MetaData, Table, create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# test_cost_models foreign keys resolve under Base.metadata.create_all)
from backend.consumer_price_sources import (
    SOURCE_TIER_CONSUMER_CASH_PAY,
    is_likely_panel,
    update_cash_pay_summary,
)
from backend.test_cost_models import (
    Base,
    LabTest,
    SOURCE_REGISTRY,
    TestCostSummary,
    TestPrice,
)

# Looked up rather than hardcoded, so a registry re-tiering shows up here as
# a test failure instead of silently drifting out of sync.
SOURCE_TIER_CMS = SOURCE_REGISTRY["cms_clfs"]["tier"]
SOURCE_TIER_PRIVATE_PAYER = SOURCE_REGISTRY["turquoise_health"]["tier"]


@pytest.fixture()
def db():
    # Back the fixture with an in-memory DB containing only the three tables
    # under test. Base.metadata.create_all() can't be used here: LabTest
    # carries a FK to `biomarker`, which lives on backend.models' *separate*
    # declarative base, so a full create_all raises NoReferencedTableError.
    # We are testing the rollup arithmetic, not the FK graph, so building
    # just these tables keeps the test hermetic and free of the 50-biomarker
    # production DB.
    engine = create_engine("sqlite:///:memory:")
    # LabTest carries a FK to `biomarker`, whose real definition lives on
    # backend.models' *separate* declarative base. Adding a matching stub here
    # lets SQLAlchemy resolve the FK at flush time, so we can insert a LabTest
    # without constructing the whole 50-biomarker production schema. The table
    # is added at most once even if multiple fixtures run in one process.
    if "biomarker" not in Base.metadata.tables:
        Table("biomarker", Base.metadata,
              Column("id", Integer, primary_key=True))
    # Build only the three tables under test into a local MetaData. Column
    # objects are rebuilt from their type rather than copied, which drops the
    # cross-schema FK outright and sidesteps both the deprecated Column.copy()
    # and its index-name collision with the live schema.
    md = MetaData()
    for table in (LabTest.__table__, TestPrice.__table__, TestCostSummary.__table__):
        Table(table.name, md, *(
            Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable,
                   default=c.default, index=bool(c.index))
            for c in table.columns
        ))
    md.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(LabTest(
        test_id="test_demo",
        test_name="Alanine Aminotransferase",
        test_type="blood",
    ))
    session.commit()
    yield session
    session.close()


_SEQ = itertools.count(1)


def _add_price(db, amount, tier, product_name=None, days_ago=0, provider="acme"):
    db.add(TestPrice(
        price_id=f"p{next(_SEQ)}",
        test_id="test_demo",
        amount=amount,
        source="test_source",
        source_tier=tier,
        price_type="cash_price",
        provider=provider,
        product_name=product_name,
        retrieved_date=date.today() - timedelta(days=days_ago),
        source_url="https://example.invalid/x",
    ))
    db.commit()


class TestTierSeparation:
    """A CMS rate is not a cash-pay price and must never enter its median."""

    def test_cms_rate_excluded_from_cash_pay_median(self, db):
        _add_price(db, 900.00, SOURCE_TIER_CMS, provider="CMS")
        _add_price(db, 20.00, SOURCE_TIER_CONSUMER_CASH_PAY)
        _add_price(db, 30.00, SOURCE_TIER_CONSUMER_CASH_PAY)

        s = update_cash_pay_summary(db, "test_demo", test_name="ALT")

        assert s.cash_pay_median == pytest.approx(25.0)
        assert s.cash_pay_max == pytest.approx(30.0), "CMS 900 must not be the max"

    def test_private_payer_rate_excluded_from_cash_pay_median(self, db):
        _add_price(db, 500.00, SOURCE_TIER_PRIVATE_PAYER, provider="BCBS")
        _add_price(db, 40.00, SOURCE_TIER_CONSUMER_CASH_PAY)

        s = update_cash_pay_summary(db, "test_demo", test_name="ALT")

        assert s.cash_pay_median == pytest.approx(40.0)
        assert s.cash_pay_source_count == 1

    def test_only_most_recent_retrieval_date_counts(self, db):
        # A stale cheap quote must not drag down today's range.
        _add_price(db, 5.00, SOURCE_TIER_CONSUMER_CASH_PAY, days_ago=30)
        _add_price(db, 50.00, SOURCE_TIER_CONSUMER_CASH_PAY)
        _add_price(db, 60.00, SOURCE_TIER_CONSUMER_CASH_PAY)

        s = update_cash_pay_summary(db, "test_demo", test_name="ALT")

        assert s.cash_pay_min == pytest.approx(50.0)
        assert s.cash_pay_source_count == 2

    def test_no_cash_pay_rows_leaves_median_none(self, db):
        _add_price(db, 900.00, SOURCE_TIER_CMS, provider="CMS")

        s = update_cash_pay_summary(db, "test_demo", test_name="ALT")

        assert s.cash_pay_median is None


class TestStandaloneVsPanel:
    """The standalone figure is the one comparable to the analyte's own cost."""

    def test_panel_prices_shift_blended_median_off_standalone(self, db):
        # Mirrors the real ALT pull: one true standalone, two panels.
        _add_price(db, 23.00, SOURCE_TIER_CONSUMER_CASH_PAY,
                   product_name="Alanine Aminotransferase (ALT)",
                   provider="Jason Health")
        _add_price(db, 26.00, SOURCE_TIER_CONSUMER_CASH_PAY,
                   product_name="Hepatic Function Panel", provider="Jason Health")
        _add_price(db, 99.00, SOURCE_TIER_CONSUMER_CASH_PAY,
                   product_name="Comprehensive Metabolic Panel", provider="LabsMD")

        s = update_cash_pay_summary(db, "test_demo",
                                    test_name="Alanine Aminotransferase")

        assert s.cash_pay_median == pytest.approx(26.0)
        assert s.cash_pay_standalone_median == pytest.approx(23.0)
        assert s.cash_pay_standalone_count == 1

    def test_no_standalone_price_is_none_not_zero(self, db):
        # Mirror of vitamin D: every scraped product was a panel.
        _add_price(db, 74.00, SOURCE_TIER_CONSUMER_CASH_PAY,
                   product_name="Vitamin D Panel", provider="LabsMD")
        _add_price(db, 84.00, SOURCE_TIER_CONSUMER_CASH_PAY,
                   product_name="Cardio IQ Vitamin D", provider="Quest")

        s = update_cash_pay_summary(db, "test_demo", test_name="Vitamin D")

        assert s.cash_pay_standalone_median is None
        assert s.cash_pay_standalone_min is None
        assert s.cash_pay_standalone_max is None
        assert s.cash_pay_standalone_count == 0

    def test_blended_range_always_brackets_standalone(self, db):
        for amount, name in [
            (23.00, "Alanine Aminotransferase (ALT)"),
            (26.00, "Hepatic Function Panel"),
            (44.00, "Arthritis Basic Panel"),
        ]:
            _add_price(db, amount, SOURCE_TIER_CONSUMER_CASH_PAY, product_name=name)

        s = update_cash_pay_summary(db, "test_demo", test_name="ALT")

        assert s.cash_pay_min <= s.cash_pay_standalone_min
        assert s.cash_pay_standalone_max <= s.cash_pay_max
        assert s.cash_pay_min <= s.cash_pay_median <= s.cash_pay_max

    def test_unnamed_product_treated_as_standalone(self, db):
        # Some stores expose only a SKU deep link; absence of a name is
        # not evidence of a panel, so it must not be silently dropped.
        _add_price(db, 31.00, SOURCE_TIER_CONSUMER_CASH_PAY, product_name=None)

        s = update_cash_pay_summary(db, "test_demo", test_name="ALT")

        assert s.cash_pay_standalone_count == 1
        assert s.cash_pay_standalone_median == pytest.approx(31.0)


class TestIsLikelyPanel:
    @pytest.mark.parametrize("name", [
        "Hepatic Function Panel",
        "Comprehensive Metabolic Panel, Plasma",
        "Basal Inflammation Scan",
        "Arthritis Basic Panel",
        "Post-holiday morning checkup",
        "STTM 8.0 ALT & AST",
        "Basic Wellness Profile",
    ])
    def test_panels_detected(self, name):
        assert is_likely_panel(name) is True

    @pytest.mark.parametrize("name", [
        "Alanine Aminotransferase (ALT)",
        "C-Reactive Protein (CRP)",
        "Direct LDL",
        "Ferritin",
        "Hemoglobin A1c",
    ])
    def test_standalone_not_flagged(self, name):
        assert is_likely_panel(name) is False

    def test_missing_name_is_not_a_panel(self):
        assert is_likely_panel(None) is False
        assert is_likely_panel("") is False

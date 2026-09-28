"""
Biomarker Test Cost + Expected Hazard Information Value (EHIV) Models.

Implements the schema from TEST_COST_BUILD_SPEC.md:
- lab_tests: canonical test identity (distinct from biomarker)
- lab_test_identifiers: multi-lab identifiers (Quest, LOINC, CPT, HCPCS)
- test_billing_codes: CPT/HCPCS billing codes
- test_prices: observed prices with full provenance
- test_cost_summary: materialized price summary
- biomarker_test_value: EHIV/REHIV results per (biomarker, test, population)

Key conceptual distinction (do NOT collapse):
- Prognostic value: HR(x) — how strongly the biomarker relates to mortality
- Information value: EHIV/REHIV — how much mortality-risk heterogeneity the test reveals
- Economic value: EVSI — requires decision model (reserved, not built yet)
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Text,
    DateTime,
    Date,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# =======================================================================
# Source registry — price-data-sources-build-spec.md
# =======================================================================
# Canonical mapping of every price source this pipeline knows about to its
# tier and default price_type. `source_tier` on TestPrice rows should
# always come from here (never guessed at ingestion time), so a reviewer
# can answer "which figure is being used where and why" by looking up one
# table. Do not silently blend tiers — see TestCostSummary.to_dict().
SOURCE_TIER_AUTHORITATIVE = "authoritative"
SOURCE_TIER_AGGREGATOR_TRANSPARENCY = "aggregator_transparency"
SOURCE_TIER_CONSUMER_CASH_PAY = "consumer_cash_pay"

SOURCE_REGISTRY = {
    "cms_clfs": {
        "label": "CMS Clinical Laboratory Fee Schedule",
        "tier": SOURCE_TIER_AUTHORITATIVE,
        "default_price_type": "medicare_reimbursement",
        "base_url": "https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs",
        "licensing_status": "PUBLIC_NO_KEY_REQUIRED",
        "implemented": True,
    },
    "turquoise_health": {
        "label": "Turquoise Health (hospital/payer price transparency)",
        "tier": SOURCE_TIER_AGGREGATOR_TRANSPARENCY,
        "default_price_type": "negotiated_rate",
        "base_url": "https://turquoise.health",
        "licensing_status": "PENDING_HUMAN_LICENSING_DECISION",
        "implemented": False,
    },
    # Consumer cash-pay sites, in the order given in the spec's source
    # registry. `robots_txt_status` reflects a live check on 2026-09-12 —
    # re-verify before ingesting, robots.txt and ToS can change.
    "find_a_lab_test": {
        "label": "Find A Lab Test / findlabtest.com",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.findlabtest.com",
        "robots_txt_status": "OPEN (no blanket disallow found 2026-09-12)",
        "implemented": False,
    },
    "testing_com": {
        "label": "Testing.com (formerly Health Testing Centers)",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.testing.com",
        "robots_txt_status": "OPEN except /search/, /wp-admin (2026-09-12)",
        "implemented": False,
    },
    "walk_in_lab": {
        "label": "Walk-In Lab",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.walkinlab.com",
        "robots_txt_status": "OPEN for generic UA; per-bot rules only exclude cart/checkout/admin (2026-09-12)",
        "implemented": False,
    },
    "ulta_lab_tests": {
        "label": "Ulta Lab Tests",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.ultalabtests.com",
        "robots_txt_status": "INCONCLUSIVE — empty robots.txt, HTTP 202 on fetch (2026-09-12); read ToS manually before scraping",
        "implemented": False,
    },
    "discountedlabs": {
        "label": "DiscountedLabs",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.discountedlabs.com",
        "robots_txt_status": "BLOCKED — site serves a Cloudflare bot challenge to non-browser requests (2026-09-12); do not scrape without explicit permission",
        "implemented": False,
    },
    "request_a_test": {
        "label": "Request A Test",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.requestatest.com",
        "robots_txt_status": "BLOCKED — site serves a Cloudflare bot challenge to non-browser requests (2026-09-12); do not scrape without explicit permission",
        "implemented": False,
    },
    "privatemdlabs": {
        "label": "PrivateMDLabs",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.privatemdlabs.com",
        "robots_txt_status": "OPEN except /lab_cart.php (2026-09-12)",
        "implemented": False,
    },
    "quest_direct": {
        "label": "Quest Diagnostics QuestDirect (self-pay portal)",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.questhealth.com",
        "robots_txt_status": "OPEN for product pages; /search and account paths disallowed (2026-09-12) — use sitemap/category browsing, not on-site search",
        "implemented": False,
    },
    "labcorp_ondemand": {
        "label": "Labcorp OnDemand (self-pay portal)",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "base_url": "https://www.ondemand.labcorp.com",
        "robots_txt_status": "OPEN except /customer/, /kit/ (2026-09-12)",
        "implemented": False,
    },
    # Legacy source slugs from before this registry existed. Kept so old
    # rows still resolve to a tier; new ingestion should use the slugs above.
    "FINDLABTEST": {
        "label": "FindLabTest (legacy slug — use 'find_a_lab_test')",
        "tier": SOURCE_TIER_CONSUMER_CASH_PAY,
        "default_price_type": "cash_price",
        "implemented": True,
    },
    "CMS_CLFS": {
        "label": "CMS CLFS (legacy slug — use 'cms_clfs')",
        "tier": SOURCE_TIER_AUTHORITATIVE,
        "default_price_type": "medicare_reimbursement",
        "implemented": True,
    },
    "CMS_PRIVATE_PAYER": {
        "label": "CMS private-payer rates/volumes (legacy slug)",
        "tier": SOURCE_TIER_AGGREGATOR_TRANSPARENCY,
        "default_price_type": "negotiated_rate",
        "implemented": False,
    },
}


def source_tier_for(source: str) -> Optional[str]:
    """Look up the tier for a source slug, or None if unregistered."""
    entry = SOURCE_REGISTRY.get(source)
    return entry["tier"] if entry else None


class LoincReference(Base):
    """
    LOINC reference table. Stores the structured axes (component, property,
    time, system, scale, method) for each LOINC code, ingested from the
    Regenstrief LOINC bulk table (LoincTable/Loinc.csv).

    This is the lookup used by the §6 matching hierarchy to resolve a
    lab_tests row to a LOINC code via verified component/specimen/method
    match against LOINC's structured axes.

    Only ACTIVE codes are ingested by default (see ingest_loinc.py).
    """
    __tablename__ = "loinc_reference"

    loinc_code = Column(String(20), primary_key=True)
    component = Column(String(500), nullable=True)
    property_ = Column(String(100), nullable=True)
    time_aspect = Column(String(100), nullable=True)
    system = Column(String(300), nullable=True)
    scale_type = Column(String(100), nullable=True)
    method_type = Column(String(100), nullable=True)
    loinc_class = Column(String(100), nullable=True)
    short_name = Column(String(500), nullable=True)
    long_common_name = Column(String(500), nullable=True)
    display_name = Column(String(500), nullable=True)
    status = Column(String(20), nullable=True)
    example_units = Column(String(200), nullable=True)
    example_ucum_units = Column(String(200), nullable=True)
    related_names = Column(Text, nullable=True)
    loinc_version = Column(String(20), nullable=True)
    version_first_released = Column(String(20), nullable=True)
    version_last_changed = Column(String(20), nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "loinc_code": self.loinc_code,
            "component": self.component,
            "property": self.property_,
            "time_aspect": self.time_aspect,
            "system": self.system,
            "scale_type": self.scale_type,
            "method_type": self.method_type,
            "loinc_class": self.loinc_class,
            "short_name": self.short_name,
            "long_common_name": self.long_common_name,
            "display_name": self.display_name,
            "status": self.status,
            "example_units": self.example_units,
            "example_ucum_units": self.example_ucum_units,
            "related_names": self.related_names,
            "loinc_version": self.loinc_version,
            "version_first_released": self.version_first_released,
            "version_last_changed": self.version_last_changed,
        }


class LabTest(Base):
    """
    Canonical test identity. One biomarker (e.g. 'crp') can map to multiple
    test_ids (different assays/labs). Never assume 1:1.
    """
    __tablename__ = "lab_tests"

    test_id = Column(String(100), primary_key=True)
    canonical_biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=True, index=True)
    test_name = Column(String(300), nullable=False)
    test_type = Column(String(100), nullable=True)  # e.g. 'serum', 'plasma', 'whole_blood'
    specimen = Column(String(100), nullable=True)
    method = Column(String(200), nullable=True)  # e.g. 'immunoturbidimetric', 'enzymatic'
    canonical_unit = Column(String(50), nullable=True)
    loinc_code = Column(String(20), nullable=True)
    loinc_version = Column(String(20), nullable=True)
    # loinc_status: 'unmapped' | 'candidate' | 'verified'
    loinc_status = Column(String(20), default="unmapped", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    identifiers = relationship("LabTestIdentifier", back_populates="lab_test", cascade="all, delete-orphan")
    billing_codes = relationship("TestBillingCode", back_populates="lab_test", cascade="all, delete-orphan")
    prices = relationship("TestPrice", back_populates="lab_test", cascade="all, delete-orphan")
    cost_summary = relationship("TestCostSummary", back_populates="lab_test", uselist=False, cascade="all, delete-orphan")
    test_values = relationship("BiomarkerTestValue", back_populates="lab_test", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "test_id": self.test_id,
            "canonical_biomarker_id": self.canonical_biomarker_id,
            "test_name": self.test_name,
            "test_type": self.test_type,
            "specimen": self.specimen,
            "method": self.method,
            "canonical_unit": self.canonical_unit,
            "loinc_code": self.loinc_code,
            "loinc_version": self.loinc_version,
            "loinc_status": self.loinc_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LabTestIdentifier(Base):
    """
    Multi-lab identifiers for a test. A single test can have a Quest ID,
    LOINC code, CPT code, HCPCS code, and/or lab-local code.
    """
    __tablename__ = "lab_test_identifiers"

    test_id = Column(String(100), ForeignKey("lab_tests.test_id"), primary_key=True)
    laboratory = Column(String(100), nullable=False, primary_key=True)
    # identifier_type: QUEST_TEST_ID | LOINC | CPT | HCPCS | LAB_LOCAL_CODE
    identifier_type = Column(String(50), nullable=False, primary_key=True)
    identifier = Column(String(100), nullable=False, primary_key=True)
    # Omit for CPT unless licensed to store AMA text (see spec §0.3)
    identifier_description = Column(Text, nullable=True)
    source = Column(String(200), nullable=True)
    source_date = Column(Date, nullable=True)

    # Relationships
    lab_test = relationship("LabTest", back_populates="identifiers")

    def to_dict(self):
        return {
            "test_id": self.test_id,
            "laboratory": self.laboratory,
            "identifier_type": self.identifier_type,
            "identifier": self.identifier,
            "identifier_description": self.identifier_description,
            "source": self.source,
            "source_date": self.source_date.isoformat() if self.source_date else None,
        }


class TestBillingCode(Base):
    """
    CPT/HCPCS billing codes. A single code can represent a panel rather than
    one analyte — don't assume 1:1 with lab_tests.
    """
    __tablename__ = "test_billing_codes"

    test_id = Column(String(100), ForeignKey("lab_tests.test_id"), primary_key=True)
    # coding_system: CPT | HCPCS
    coding_system = Column(String(20), nullable=False, primary_key=True)
    code = Column(String(20), nullable=False, primary_key=True)
    # HCPCS only, or CPT if licensed
    description = Column(Text, nullable=True)
    # e.g. 'exact' | 'panel_component'
    relationship_type = Column(String(50), nullable=True)
    source = Column(String(200), nullable=True)
    source_date = Column(Date, nullable=True)

    # Relationships
    lab_test = relationship("LabTest", back_populates="billing_codes")

    def to_dict(self):
        return {
            "test_id": self.test_id,
            "coding_system": self.coding_system,
            "code": self.code,
            "description": self.description,
            "relationship": self.relationship_type,
            "source": self.source,
            "source_date": self.source_date.isoformat() if self.source_date else None,
        }


class TestPrice(Base):
    """
    Observed price with full provenance. Every price must retain:
    source, source_url, retrieval_date, effective_date, price_type,
    laboratory, geography.

    Extended per price-data-sources-build-spec.md to carry a `source_tier`
    (authoritative | aggregator_transparency | consumer_cash_pay) so the
    dashboard can show a ranked, un-blended three-tier price breakdown
    instead of a single number. See SOURCE_REGISTRY below for the
    source -> tier mapping; `source_tier` is denormalized onto each row so
    historical rows keep their tier even if the registry changes later.
    """
    __tablename__ = "test_prices"

    price_id = Column(String(100), primary_key=True)
    test_id = Column(String(100), ForeignKey("lab_tests.test_id"), nullable=False, index=True)
    # source: a SOURCE_REGISTRY key, e.g. cms_clfs | find_a_lab_test |
    # testing_com | walk_in_lab | ulta_lab_tests | discountedlabs |
    # request_a_test | privatemdlabs | quest_direct | labcorp_ondemand |
    # turquoise_health. Legacy rows may carry the older FINDLABTEST /
    # CMS_CLFS / CMS_PRIVATE_PAYER values from before this registry existed.
    source = Column(String(50), nullable=False, index=True)
    # source_tier: authoritative | aggregator_transparency | consumer_cash_pay
    source_tier = Column(String(30), nullable=True, index=True)
    provider = Column(String(200), nullable=True)
    # price_type: medicare_reimbursement | negotiated_rate | cash_price |
    # list_price (legacy rows may carry DIRECT_TO_CONSUMER /
    # MEDICARE_ALLOWED / PRIVATE_PAYER_RATE from before this spec).
    price_type = Column(String(50), nullable=False, index=True)
    # payer: populated for negotiated rates (e.g. a specific insurer).
    # Nullable — most rows (CLFS, cash-pay) have no payer.
    payer = Column(String(200), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    # geography / region: ZIP, state, or 'national'
    geography = Column(String(100), nullable=True)
    state_restrictions = Column(Text, nullable=True)
    retrieved_date = Column(Date, nullable=False)
    effective_date = Column(Date, nullable=True)
    # Required when price_type = PRIVATE_PAYER_RATE / negotiated_rate
    collection_period = Column(String(50), nullable=True)
    source_url = Column(String(500), nullable=True)
    source_version = Column(String(100), nullable=True)
    # Pointer to the raw stored response (HTML/CSV/JSON) for auditability,
    # e.g. "data/raw/test_prices/cms_clfs/2026/PUF_CLFS_CY2026_Q3V1.csv"
    raw_payload_ref = Column(String(500), nullable=True)
    # The exact product this price buys, as named by the provider, e.g.
    # "CRP - C-Reactive Protein" vs "Basal Inflammation Scan". A provider
    # can sell the same analyte standalone and inside a multi-analyte
    # panel at different prices; without this, a panel price is
    # indistinguishable from a standalone one.
    product_name = Column(String(300), nullable=True)
    lab_test = relationship("LabTest", back_populates="prices")

    def to_dict(self):
        return {
            "price_id": self.price_id,
            "test_id": self.test_id,
            "source": self.source,
            "source_tier": self.source_tier,
            "provider": self.provider,
            "price_type": self.price_type,
            "payer": self.payer,
            "amount": self.amount,
            "currency": self.currency,
            "geography": self.geography,
            "state_restrictions": self.state_restrictions,
            "retrieved_date": self.retrieved_date.isoformat() if self.retrieved_date else None,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "collection_period": self.collection_period,
            "source_url": self.source_url,
            "source_version": self.source_version,
            "raw_payload_ref": self.raw_payload_ref,
            "product_name": self.product_name,
        }


class TestCostSummary(Base):
    """
    Materialized price summary per test.
    Default reference_consumer_price is the MEDIAN, not the minimum.

    Extended per price-data-sources-build-spec.md ("Dashboard-facing
    aggregation") with an explicit three-tier breakdown that is never
    blended into a single number:

    - reference_price: CMS CLFS national (or carrier) rate — the primary
      EHIV/VOI cost input, since it's the most defensible, citable figure.
    - negotiated_rate_*: median/IQR of aggregator-transparency
      (Turquoise Health) negotiated rates — context only, not fed into
      EHIV math by default.
    - cash_pay_*: min/median/max across consumer_cash_pay sources — the
      realistic out-of-pocket figure for the willingness-to-pay comparison.

    The legacy d2c_*/cms_clfs/cms_private_payer_* fields are kept for
    backward compatibility with existing callers and are populated
    alongside the tier-explicit fields, not instead of them.
    """
    __tablename__ = "test_cost_summary"

    test_id = Column(String(100), ForeignKey("lab_tests.test_id"), primary_key=True)

    # --- Legacy fields (pre price-data-sources-build-spec.md) ---
    d2c_min = Column(Float, nullable=True)
    d2c_median = Column(Float, nullable=True)
    d2c_max = Column(Float, nullable=True)
    cms_clfs = Column(Float, nullable=True)
    cms_private_payer_median = Column(Float, nullable=True)
    cms_private_payer_collection_period = Column(String(50), nullable=True)
    # Default: d2c_median, not d2c_min
    reference_consumer_price = Column(Float, nullable=True)
    reference_payer_price = Column(Float, nullable=True)
    price_date = Column(Date, nullable=True)
    # price_confidence: HIGH (>=3 obs) | MEDIUM (2) | LOW (1)
    price_confidence = Column(String(20), nullable=True)

    # --- Tier 1: authoritative (CMS CLFS) ---
    reference_price = Column(Float, nullable=True)
    reference_price_source = Column(String(50), nullable=True)  # e.g. 'cms_clfs'
    reference_price_region = Column(String(100), nullable=True)  # 'national' or carrier/MAC
    reference_price_date = Column(Date, nullable=True)
    reference_price_is_carrier_specific = Column(Integer, default=0)

    # --- Tier 2: aggregator_transparency (Turquoise Health) ---
    negotiated_rate_median = Column(Float, nullable=True)
    negotiated_rate_iqr_low = Column(Float, nullable=True)
    negotiated_rate_iqr_high = Column(Float, nullable=True)
    negotiated_rate_payer_count = Column(Integer, nullable=True)
    negotiated_rate_date = Column(Date, nullable=True)

    # --- Tier 3: consumer_cash_pay (find_a_lab_test + the 8 sites) ---
    cash_pay_min = Column(Float, nullable=True)
    cash_pay_median = Column(Float, nullable=True)
    cash_pay_max = Column(Float, nullable=True)
    cash_pay_source_count = Column(Integer, nullable=True)
    cash_pay_date = Column(Date, nullable=True)
    # Standalone-analyte subset of the above: same window, but excluding
    # products classified as multi-analyte panels (see
    # consumer_price_sources.is_likely_panel). This is the figure actually
    # comparable to *this* biomarker's test cost — a panel's price also
    # buys several other analytes.
    cash_pay_standalone_min = Column(Float, nullable=True)
    cash_pay_standalone_median = Column(Float, nullable=True)
    cash_pay_standalone_max = Column(Float, nullable=True)
    cash_pay_standalone_count = Column(Integer, nullable=True)

    # Relationships
    lab_test = relationship("LabTest", back_populates="cost_summary")

    def to_dict(self):
        return {
            "test_id": self.test_id,
            # Legacy (kept for backward compatibility)
            "d2c_min": self.d2c_min,
            "d2c_median": self.d2c_median,
            "d2c_max": self.d2c_max,
            "cms_clfs": self.cms_clfs,
            "cms_private_payer_median": self.cms_private_payer_median,
            "cms_private_payer_collection_period": self.cms_private_payer_collection_period,
            "reference_consumer_price": self.reference_consumer_price,
            "reference_payer_price": self.reference_payer_price,
            "price_date": self.price_date.isoformat() if self.price_date else None,
            "price_confidence": self.price_confidence,
            # Three-tier breakdown (never blended — see price-data-sources-build-spec.md)
            "three_tier_price": {
                "reference_price": {
                    "amount": self.reference_price,
                    "source": self.reference_price_source,
                    "region": self.reference_price_region,
                    "as_of": self.reference_price_date.isoformat() if self.reference_price_date else None,
                    "is_carrier_specific": bool(self.reference_price_is_carrier_specific),
                    "label": "CMS CLFS reference rate (authoritative, used in EHIV/VOI cost math)",
                },
                "negotiated_rate_range": {
                    "median": self.negotiated_rate_median,
                    "iqr_low": self.negotiated_rate_iqr_low,
                    "iqr_high": self.negotiated_rate_iqr_high,
                    "payer_count": self.negotiated_rate_payer_count,
                    "as_of": self.negotiated_rate_date.isoformat() if self.negotiated_rate_date else None,
                    "label": "Negotiated-rate range (aggregator transparency, context only)",
                },
                "cash_pay_range": {
                    "min": self.cash_pay_min,
                    "median": self.cash_pay_median,
                    "max": self.cash_pay_max,
                    "source_count": self.cash_pay_source_count,
                    "as_of": self.cash_pay_date.isoformat() if self.cash_pay_date else None,
                    "label": "Cash-pay range (consumer sites, realistic out-of-pocket comparison)",
                },
            },
        }


class BiomarkerTestValue(Base):
    """
    EHIV/REHIV results per (biomarker, test, population stratum).
    
    This is INFORMATION VALUE, not economic value.
    - EHIV: mean absolute deviation of HR from expected HR
    - REHIV: EHIV / expected HR (relative, for cross-biomarker comparison)
    
    Do NOT combine with price. Display side by side.
    A descriptive ratio (rehiv / reference_consumer_price) is fine but must
    be labeled "hazard-information units per dollar" — never "ROI".
    """
    __tablename__ = "biomarker_test_value"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    test_id = Column(String(100), ForeignKey("lab_tests.test_id"), nullable=False, index=True)
    age = Column(Integer, nullable=True)
    sex = Column(String(20), nullable=True)
    race_ethnicity = Column(String(100), nullable=True)
    
    # HR distribution statistics
    expected_hr = Column(Float, nullable=True)
    hr_sd = Column(Float, nullable=True)
    # EHIV: mean |HR_i - expected_hr|
    ehiv = Column(Float, nullable=True)
    # REHIV: EHIV / expected_hr
    rehiv = Column(Float, nullable=True)
    
    # Price reference (displayed alongside, never combined)
    reference_consumer_price = Column(Float, nullable=True)
    cms_clfs_price = Column(Float, nullable=True)
    cms_private_payer_price = Column(Float, nullable=True)
    
    # Provenance
    population_n = Column(Integer, nullable=True)
    mortality_model_id = Column(String(100), nullable=True)
    simulation_count = Column(Integer, nullable=True)
    simulation_seed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Reserved for future EVSI layer (do NOT populate yet)
    decision_model_id = Column(String(100), nullable=True)
    intervention_id = Column(String(100), nullable=True)
    decision_threshold = Column(Float, nullable=True)
    treatment_cost = Column(Float, nullable=True)
    treatment_effect = Column(Float, nullable=True)
    qaly_gain = Column(Float, nullable=True)
    net_monetary_benefit = Column(Float, nullable=True)
    evsi = Column(Float, nullable=True)

    # Relationships
    lab_test = relationship("LabTest", back_populates="test_values")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "test_id": self.test_id,
            "age": self.age,
            "sex": self.sex,
            "race_ethnicity": self.race_ethnicity,
            "expected_hr": self.expected_hr,
            "hr_sd": self.hr_sd,
            "ehiv": self.ehiv,
            "rehiv": self.rehiv,
            "reference_consumer_price": self.reference_consumer_price,
            "cms_clfs_price": self.cms_clfs_price,
            "cms_private_payer_price": self.cms_private_payer_price,
            "population_n": self.population_n,
            "mortality_model_id": self.mortality_model_id,
            "simulation_count": self.simulation_count,
            "simulation_seed": self.simulation_seed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_test_cost_tables(engine):
    """Create all test cost tables."""
    # Import Biomarker from main models to resolve foreign key
    from backend.models import Biomarker
    
    # Add Biomarker table to our metadata so FK can be resolved
    if "biomarker" not in LabTest.metadata.tables:
        # Reflect the biomarker table into our metadata
        from sqlalchemy import Table, MetaData
        biomarker_table = Table(
            "biomarker",
            LabTest.metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String(200)),
            Column("display_name", String(300)),
            Column("category", String(100)),
            Column("unit", String(50)),
            Column("description", Text),
            Column("source", String(200)),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
            extend_existing=True,
        )
    
    LabTest.metadata.create_all(engine, tables=[
        LoincReference.__table__,
        LabTest.__table__,
        LabTestIdentifier.__table__,
        TestBillingCode.__table__,
        TestPrice.__table__,
        TestCostSummary.__table__,
        BiomarkerTestValue.__table__,
    ])

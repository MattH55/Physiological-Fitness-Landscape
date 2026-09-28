"""
Seed data for test cost and EHIV calculations.

Populates the test cost tables with starter data for the 10 biomarkers
identified in TEST_COST_BUILD_SPEC.md §1:
1. hs-CRP
2. HbA1c
3. LDL-C
4. HDL-C
5. Triglycerides
6. eGFR
7. ALT
8. AST
9. Total Testosterone
10. Vitamin D (25-OH)

This script:
1. Creates LabTest records for each biomarker
2. Adds identifiers (LOINC, CPT, HCPCS)
3. Adds billing codes
4. Seeds price data (placeholder values - replace with real ingestion)
5. Computes EHIV/REHIV from existing HR curves and population distributions
6. Updates cost summaries

Run with: python -m backend.seed_test_cost_data
"""

import os
import sys
import logging
from datetime import date

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import sessionmaker
from backend.models import (
    Biomarker,
    BiomarkerHRCurve,
    PopulationDistribution,
    get_engine,
    init_db,
)
from backend.test_cost_models import (
    LabTest,
    LabTestIdentifier,
    TestBillingCode,
    TestPrice,
    TestCostSummary,
    BiomarkerTestValue,
    init_test_cost_tables,
)
from backend.test_cost_models import source_tier_for
from backend.consumer_price_sources import update_cash_pay_summary
from backend.ehiv_engine import (
    compute_ehiv_from_empirical_biomarker,
    compute_ehiv_from_empirical_biomarker_lognormal,
    compute_ehiv_from_empirical_biomarker_piecewise,
    compute_ehiv_from_empirical_biomarker_log_log,
    compute_ehiv_from_empirical_biomarker_quadratic,
    compute_ehiv_from_empirical_biomarker_linear_log,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")


# ======================================================================
# Starter Biomarker Definitions
# ======================================================================

STARTER_BIOMARKERS = [
    {
        "slug": "high_sensitivity_crp",
        "name": "High-Sensitivity C-Reactive Protein",
        "test_name": "hs-CRP (High-Sensitivity C-Reactive Protein)",
        "test_type": "IMMUNOASSAY",
        "specimen": "SERUM",
        "method": "IMMUNOTURBIDIMETRIC",
        "canonical_unit": "mg/L",
        "loinc_code": "1975-2",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "86141",
        "cpt_code": "86141",
        "search_term": "C-reactive protein high sensitivity",
        # Placeholder prices (replace with real ingestion)
        "d2c_prices": [25.0, 35.0, 45.0, 55.0, 65.0],
        "cms_clfs_price": 42.50,
        "private_payer_prices": [38.0, 45.0, 52.0, 58.0],
    },
    {
        "slug": "hba1c",
        "name": "Hemoglobin A1c",
        "test_name": "HbA1c (Hemoglobin A1c)",
        "test_type": "CHROMATOGRAPHY",
        "specimen": "WHOLE_BLOOD",
        "method": "ION_EXCHANGE_CHROMATOGRAPHY",
        "canonical_unit": "%",
        "loinc_code": "4548-4",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "83036",
        "cpt_code": "83036",
        "search_term": "hemoglobin a1c",
        "d2c_prices": [20.0, 30.0, 40.0, 50.0],
        "cms_clfs_price": 35.00,
        "private_payer_prices": [30.0, 38.0, 45.0],
    },
    {
        "slug": "ldl_cholesterol",
        "name": "LDL Cholesterol",
        "test_name": "LDL-C (Low-Density Lipoprotein Cholesterol)",
        "test_type": "ENZYMATIC",
        "specimen": "SERUM",
        "method": "ENZYMATIC_COLORIMETRIC",
        "canonical_unit": "mg/dL",
        "loinc_code": "13457-7",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "83540",
        "cpt_code": "83540",
        "search_term": "ldl cholesterol",
        "d2c_prices": [15.0, 25.0, 35.0, 45.0],
        "cms_clfs_price": 28.00,
        "private_payer_prices": [22.0, 30.0, 38.0],
    },
    {
        "slug": "hdl_cholesterol",
        "name": "HDL Cholesterol",
        "test_name": "HDL-C (High-Density Lipoprotein Cholesterol)",
        "test_type": "ENZYMATIC",
        "specimen": "SERUM",
        "method": "ENZYMATIC_COLORIMETRIC",
        "canonical_unit": "mg/dL",
        "loinc_code": "2085-9",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "83516",
        "cpt_code": "83516",
        "search_term": "hdl cholesterol",
        "d2c_prices": [15.0, 25.0, 35.0, 45.0],
        "cms_clfs_price": 28.00,
        "private_payer_prices": [22.0, 30.0, 38.0],
    },
    {
        "slug": "triglycerides",
        "name": "Triglycerides",
        "test_name": "Triglycerides (Fasting)",
        "test_type": "ENZYMATIC",
        "specimen": "SERUM",
        "method": "ENZYMATIC_COLORIMETRIC",
        "canonical_unit": "mg/dL",
        "loinc_code": "2571-8",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "84478",
        "cpt_code": "84478",
        "search_term": "triglycerides",
        "d2c_prices": [15.0, 25.0, 35.0, 45.0],
        "cms_clfs_price": 28.00,
        "private_payer_prices": [22.0, 30.0, 38.0],
    },
    {
        "slug": "estimated_gfr",
        "name": "Estimated Glomerular Filtration Rate",
        "test_name": "eGFR (Estimated Glomerular Filtration Rate)",
        "test_type": "CALCULATED",
        "specimen": "SERUM",
        "method": "CKD-EPI_2021",
        "canonical_unit": "mL/min/1.73m2",
        "loinc_code": "69405-9",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "80048",
        "cpt_code": "80048",
        "search_term": "estimated glomerular filtration rate",
        "d2c_prices": [20.0, 30.0, 40.0, 50.0],
        "cms_clfs_price": 35.00,
        "private_payer_prices": [28.0, 35.0, 42.0],
    },
    {
        "slug": "alanine_aminotransferase",
        "name": "Alanine Aminotransferase",
        "test_name": "ALT (Alanine Aminotransferase)",
        "test_type": "ENZYMATIC",
        "specimen": "SERUM",
        "method": "UV_KINETIC",
        "canonical_unit": "U/L",
        "loinc_code": "1742-6",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "84460",
        "cpt_code": "84460",
        "search_term": "alt alanine aminotransferase",
        "d2c_prices": [10.0, 15.0, 20.0, 25.0],
        "cms_clfs_price": 18.00,
        "private_payer_prices": [15.0, 20.0, 25.0],
    },
    {
        "slug": "aspartate_aminotransferase",
        "name": "Aspartate Aminotransferase",
        "test_name": "AST (Aspartate Aminotransferase)",
        "test_type": "ENZYMATIC",
        "specimen": "SERUM",
        "method": "UV_KINETIC",
        "canonical_unit": "U/L",
        "loinc_code": "1920-8",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "84450",
        "cpt_code": "84450",
        "search_term": "ast aspartate aminotransferase",
        "d2c_prices": [10.0, 15.0, 20.0, 25.0],
        "cms_clfs_price": 18.00,
        "private_payer_prices": [15.0, 20.0, 25.0],
    },
    {
        "slug": "serum_25_hydroxyvitamin_d",
        "name": "Vitamin D (25-Hydroxy)",
        "test_name": "Vitamin D (25-Hydroxyvitamin D)",
        "test_type": "IMMUNOASSAY",
        "specimen": "SERUM",
        "method": "LIQUID_CHROMATOGRAPHY_TANDEM_MASS_SPECTROMETRY",
        "canonical_unit": "ng/mL",
        "loinc_code": "1989-8",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "82306",
        "cpt_code": "82306",
        "search_term": "vitamin d 25 hydroxy",
        "d2c_prices": [30.0, 45.0, 60.0, 75.0],
        "cms_clfs_price": 55.00,
        "private_payer_prices": [45.0, 55.0, 65.0],
    },
    {
        "slug": "serum_ferritin",
        "name": "Serum Ferritin",
        "test_name": "Serum Ferritin",
        "test_type": "IMMUNOASSAY",
        "specimen": "SERUM",
        "method": "CHEMILUMINESCENT_IMMUNOASSAY",
        "canonical_unit": "ng/mL",
        "loinc_code": "2289-6",
        "loinc_status": "VERIFIED",
        "hcpcs_code": "82310",
        "cpt_code": "82310",
        "search_term": "serum ferritin",
        "d2c_prices": [40.0, 55.0, 70.0, 85.0],
        "cms_clfs_price": 65.00,
        "private_payer_prices": [50.0, 60.0, 75.0],
    },
]


def seed_test_cost_data():
    """Seed the test cost tables with starter data."""
    
    engine = get_engine(f"sqlite:///{DB_PATH}")
    init_db(engine)
    init_test_cost_tables(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    logger.info("Seeding test cost data...")
    
    for bm_def in STARTER_BIOMARKERS:
        slug = bm_def["slug"]
        logger.info(f"Processing {slug}...")
        
        # Find biomarker
        bm = db.query(Biomarker).filter(Biomarker.slug == slug).first()
        if not bm:
            logger.warning(f"Biomarker '{slug}' not found in database. Skipping.")
            continue
        
        # Create LabTest
        test_id = f"test_{slug}"
        test = db.query(LabTest).filter(LabTest.test_id == test_id).first()
        if test is None:
            test = LabTest(test_id=test_id)
            db.add(test)
        
        test.canonical_biomarker_id = bm.id
        test.test_name = bm_def["test_name"]
        test.test_type = bm_def["test_type"]
        test.specimen = bm_def["specimen"]
        test.method = bm_def["method"]
        test.canonical_unit = bm_def["canonical_unit"]
        test.loinc_code = bm_def["loinc_code"]
        test.loinc_status = bm_def["loinc_status"]
        
        # Add identifiers
        _upsert_identifier(db, test_id, "LOINC", bm_def["loinc_code"], "VERIFIED")
        _upsert_identifier(db, test_id, "HCPCS", bm_def["hcpcs_code"], "VERIFIED")
        _upsert_identifier(db, test_id, "CPT", bm_def["cpt_code"], "VERIFIED")
        
        # Add billing codes
        _upsert_billing_code(db, test_id, "HCPCS", bm_def["hcpcs_code"], "PRIMARY")
        _upsert_billing_code(db, test_id, "CPT", bm_def["cpt_code"], "PRIMARY")
        
        # NOTE: this function used to also seed fake DIRECT_TO_CONSUMER /
        # MEDICARE_ALLOWED / PRIVATE_PAYER_RATE placeholder prices here
        # (bm_def["d2c_prices"], "cms_clfs_price", "private_payer_prices").
        # Those were invented numbers, never real observations, and they
        # actively corrupted the real pipeline once it existed: because
        # they shared the same source_tier and were re-inserted with
        # today's date on every re-seed, they got averaged in alongside
        # real backend.ingest_find_a_lab_test / backend.ingest_cms_clfs
        # data in update_cash_pay_summary's "most recent date" rollup.
        # Real prices now come from those two ingestion scripts — this
        # function only seeds the LabTest/identifier/billing-code metadata
        # they join against. Run, in order:
        #   python -m backend.seed_test_cost_data
        #   python -m backend.ingest_cms_clfs
        #   python -m backend.ingest_find_a_lab_test
        update_cash_pay_summary(db, test_id, test_name=bm_def.get("test_name"))

        # Compute EHIV from existing HR curve and population distribution
        _compute_ehiv_for_biomarker(db, bm, test_id)
        
        logger.info(f"  Seeded {slug}: test_id={test_id}")
    
    db.commit()
    db.close()
    
    logger.info("Test cost data seeding complete.")


def _upsert_identifier(db, test_id, identifier_type, identifier_value, status):
    """Upsert a test identifier."""
    # Use 'GENERIC' as laboratory for seed data
    laboratory = "GENERIC"
    ident = db.query(LabTestIdentifier).filter(
        LabTestIdentifier.test_id == test_id,
        LabTestIdentifier.laboratory == laboratory,
        LabTestIdentifier.identifier_type == identifier_type,
        LabTestIdentifier.identifier == identifier_value,
    ).first()
    
    if ident is None:
        ident = LabTestIdentifier(
            test_id=test_id,
            laboratory=laboratory,
            identifier_type=identifier_type,
            identifier=identifier_value,
        )
        db.add(ident)
    
    # Map status to loinc_status if it's a LOINC identifier
    if identifier_type == "LOINC":
        ident.loinc_status = status.lower()
    return ident


def _upsert_billing_code(db, test_id, code_type, code_value, role):
    """Upsert a billing code."""
    bc = db.query(TestBillingCode).filter(
        TestBillingCode.test_id == test_id,
        TestBillingCode.coding_system == code_type,
        TestBillingCode.code == code_value,
    ).first()
    
    if bc is None:
        bc = TestBillingCode(
            test_id=test_id,
            coding_system=code_type,
            code=code_value,
        )
        db.add(bc)
    
    bc.relationship_type = role
    return bc


def _upsert_price(db, test_id, source, provider, price_type, amount, 
                  retrieved_date=None, collection_period=None):
    """Upsert a price record."""
    import hashlib
    
    if retrieved_date is None:
        retrieved_date = date.today()
    
    raw = f"{test_id}|{source}|{price_type}|{amount}|{retrieved_date.isoformat()}"
    price_id = hashlib.md5(raw.encode()).hexdigest()[:16]
    
    price = db.query(TestPrice).filter(TestPrice.price_id == price_id).first()
    if price is None:
        price = TestPrice(price_id=price_id)
        db.add(price)
    
    price.test_id = test_id
    price.source = source
    price.source_tier = source_tier_for(source)
    price.provider = provider
    price.price_type = price_type
    price.amount = amount
    price.currency = "USD"
    price.retrieved_date = retrieved_date
    price.collection_period = collection_period

    return price


def _update_cost_summary(db, test_id):
    """Update the materialized cost summary for a test."""
    prices = db.query(TestPrice).filter(TestPrice.test_id == test_id).all()
    
    d2c_prices = [p.amount for p in prices if p.price_type == "DIRECT_TO_CONSUMER"]
    clfs_prices = [p.amount for p in prices if p.price_type == "MEDICARE_ALLOWED"]
    private_payer_prices = [p.amount for p in prices if p.price_type == "PRIVATE_PAYER_RATE"]
    
    summary = db.query(TestCostSummary).filter(TestCostSummary.test_id == test_id).first()
    if summary is None:
        summary = TestCostSummary(test_id=test_id)
        db.add(summary)
    
    if d2c_prices:
        d2c_sorted = sorted(d2c_prices)
        summary.d2c_min = d2c_sorted[0]
        summary.d2c_max = d2c_sorted[-1]
        n = len(d2c_sorted)
        mid = n // 2
        summary.d2c_median = d2c_sorted[mid] if n % 2 == 1 else (d2c_sorted[mid - 1] + d2c_sorted[mid]) / 2
    
    if clfs_prices:
        summary.cms_clfs = clfs_prices[0]
    
    if private_payer_prices:
        pp_sorted = sorted(private_payer_prices)
        n = len(pp_sorted)
        mid = n // 2
        summary.cms_private_payer_median = pp_sorted[mid] if n % 2 == 1 else (pp_sorted[mid - 1] + pp_sorted[mid]) / 2
        pp_prices = [p for p in prices if p.price_type == "PRIVATE_PAYER_RATE"]
        if pp_prices:
            latest = max(pp_prices, key=lambda p: p.retrieved_date or date.min)
            summary.cms_private_payer_collection_period = latest.collection_period
    
    if summary.d2c_median is not None:
        summary.reference_consumer_price = summary.d2c_median
    if summary.cms_private_payer_median is not None:
        summary.reference_payer_price = summary.cms_private_payer_median
    
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


def _compute_ehiv_for_biomarker(db, bm, test_id):
    """
    Compute EHIV/REHIV for a biomarker using its HR curve and population distribution.
    
    This uses the existing BiomarkerHRCurve and PopulationDistribution data
    to generate a distribution of individual HR values, then computes EHIV.
    """
    # Get HR curve
    curve = db.query(BiomarkerHRCurve).filter(
        BiomarkerHRCurve.biomarker_id == bm.id
    ).first()
    
    # Get population distribution (overall)
    pop_dist = db.query(PopulationDistribution).filter(
        PopulationDistribution.biomarker_id == bm.id,
        PopulationDistribution.sex == "all",
        PopulationDistribution.age_band == "all",
    ).first()
    
    if not curve or not pop_dist:
        logger.warning(f"  No HR curve or population distribution for {bm.slug}. Skipping EHIV.")
        return
    
    # Generate population values from distribution
    n_sim = 10000
    rng = np.random.default_rng(42)
    
    # Use normal distribution approximation
    pop_values = rng.normal(pop_dist.mean, pop_dist.sd, size=n_sim)
    
    # Clip to valid domain
    valid_min = curve.valid_min if curve.valid_min is not None else pop_dist.p1
    valid_max = curve.valid_max if curve.valid_max is not None else pop_dist.p99
    pop_values = np.clip(pop_values, valid_min, valid_max)
    
    # Compute HR for each individual based on curve type
    curve_type = (curve.curve_type or "").upper()
    params = curve.parameters or {}
    ref_value = curve.reference_value
    optimal_value = curve.optimal_value
    
    if curve_type == "LINEAR_LOG":
        # HR = exp(beta * (x - ref))
        beta = params.get("beta", 0.0)
        log_hr = beta * (pop_values - ref_value)
        hr_values = np.exp(log_hr)
        
    elif curve_type == "LOG_LOG":
        # HR = exp(beta * (ln(x) - ln(ref)))
        beta = params.get("beta", 0.0)
        pop_values_safe = np.maximum(pop_values, 0.01)
        log_hr = beta * (np.log(pop_values_safe) - np.log(ref_value))
        hr_values = np.exp(log_hr)
        
    elif curve_type == "QUADRATIC":
        # HR = exp(a * (x - optimal)^2)
        a = params.get("a", 0.0)
        log_hr = a * (pop_values - optimal_value) ** 2
        hr_values = np.exp(log_hr)
        
    elif curve_type in ("PIECEWISE_LINEAR", "PIECEWISE"):
        # Two formats:
        # 1. slope_low/slope_high/x_opt: HR = exp(slope_low*(x_opt-x)) for x < x_opt, exp(slope_high*(x-x_opt)) for x >= x_opt
        # 2. knots/log_hr_at_knots: HR = exp(interp(x, knots, log_hr_at_knots))
        if "slope_low" in params and "slope_high" in params:
            slope_low = params["slope_low"]
            slope_high = params["slope_high"]
            x_opt = params.get("x_opt", optimal_value or ref_value)
            log_hr = np.where(
                pop_values < x_opt,
                slope_low * (x_opt - pop_values),
                slope_high * (pop_values - x_opt)
            )
            hr_values = np.exp(log_hr)
        else:
            knots = params.get("knots", [valid_min, valid_max])
            log_hr_at_knots = params.get("log_hr_at_knots", [0.0, 0.0])
            log_hr = np.interp(pop_values, knots, log_hr_at_knots)
            hr_values = np.exp(log_hr)
        
    else:
        logger.warning(f"  Unknown curve type '{curve_type}' for {bm.slug}. Skipping EHIV.")
        return
    
    # Compute EHIV from the HR distribution
    from backend.ehiv_engine import compute_ehiv_from_hr_distribution
    result = compute_ehiv_from_hr_distribution(hr_values, population_n=n_sim)
    
    # Store result
    btv = db.query(BiomarkerTestValue).filter(
        BiomarkerTestValue.biomarker_id == bm.id,
        BiomarkerTestValue.test_id == test_id,
        BiomarkerTestValue.age == None,
        BiomarkerTestValue.sex == None,
        BiomarkerTestValue.race_ethnicity == None,
    ).first()
    
    if btv is None:
        btv = BiomarkerTestValue(
            biomarker_id=bm.id,
            test_id=test_id,
        )
        db.add(btv)
    
    btv.expected_hr = result.expected_hr
    btv.hr_sd = result.hr_sd
    btv.ehiv = result.ehiv
    btv.rehiv = result.rehiv
    btv.population_n = result.population_n
    btv.mortality_model_id = f"MC_{curve_type}"
    btv.simulation_count = n_sim
    btv.simulation_seed = 42
    
    logger.info(f"  EHIV={result.ehiv:.4f}, REHIV={result.rehiv:.4f}, E[HR]={result.expected_hr:.4f}")


if __name__ == "__main__":
    seed_test_cost_data()
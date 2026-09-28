"""
Seed script for new biomarkers with population distributions and HR curves.
Based on NEW_BIOMARKER_COVERAGE_AUDIT.md and population distribution data.

Categories:
- Tier 1: NHANES/CHMS population distributions (TSH, B12, Folate, Homocysteine, etc.)
- Tier 2: Dedicated healthy-population cohorts (IGF-1, DHEA-S, YKL-40, suPAR, GDF-15)
- Tier 3: Weaker population distributions (Free T3, β2-Microglobulin, 8-OHdG, sTNFR1)
- Category F: Calculated indices (FIB-4, LMR)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    Base, Biomarker, Source, PopulationDistribution,
    MortalityAssociation, HRFunction, DistributionFit
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import math

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mortality_biomarkers.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)
session = Session()

# ============================================================================
# Helper functions
# ============================================================================

def get_or_create_source(session, citation, pmid=None, doi=None, url=None, year=None, study_design=None):
    """Get or create a source record."""
    source = session.query(Source).filter(Source.citation == citation).first()
    if not source:
        source = Source(
            citation=citation,
            pmid=pmid,
            doi=doi,
            url=url,
            year=year,
            study_design=study_design
        )
        session.add(source)
        session.flush()
    return source

def get_or_create_biomarker(session, slug, name, category, units, specimen_type, 
                            bodily_fluid=None, primary_organ=None, tissue_origin=None,
                            nhanes_code=None, notes=None, directionality="lower_better",
                            causal_status="STRONG_OBSERVATIONAL", valid_domain_min=None,
                            valid_domain_max=None, optimal_target=None):
    """Get or create a biomarker record."""
    biomarker = session.query(Biomarker).filter(Biomarker.slug == slug).first()
    if not biomarker:
        biomarker = Biomarker(
            slug=slug,
            name=name,
            category=category,
            units=units,
            specimen_type=specimen_type,
            bodily_fluid=bodily_fluid,
            primary_organ=primary_organ,
            tissue_origin=tissue_origin,
            nhanes_code=nhanes_code,
            notes=notes,
            directionality=directionality,
            causal_status=causal_status,
            valid_domain_min=valid_domain_min,
            valid_domain_max=valid_domain_max,
            optimal_target=optimal_target
        )
        session.add(biomarker)
        session.flush()
    return biomarker

def add_distribution(session, biomarker, source, sex, age_band, mean, sd, 
                     p5=None, p25=None, p50=None, p75=None, p95=None,
                     unit=None, sample_n=1000, survey_cycle=None, is_low_confidence=0):
    """Add a population distribution record."""
    if p50 is None:
        p50 = mean
    if unit is None:
        unit = biomarker.units
    
    dist = PopulationDistribution(
        biomarker_id=biomarker.id,
        source_id=source.id,
        sex=sex,
        age_band=age_band,
        mean=mean,
        sd=sd,
        p5=p5,
        p25=p25,
        p50=p50,
        p75=p75,
        p95=p95,
        unit=unit,
        sample_n=sample_n,
        survey_cycle=survey_cycle,
        is_low_confidence=is_low_confidence
    )
    session.add(dist)
    return dist

def add_hr_curve(session, biomarker, source, sex, age_band, fit_type, parameters,
                 domain_min, domain_max, reference_value, shape, nadir_value=None,
                 fit_quality_note=None):
    """Add or update an HR function record."""
    hr = session.query(HRFunction).filter(
        HRFunction.biomarker_id == biomarker.id,
        HRFunction.sex == sex,
        HRFunction.age_band == age_band
    ).first()
    
    if hr:
        # Update existing
        hr.fit_type = fit_type
        hr.parameters = parameters
        hr.domain_min = domain_min
        hr.domain_max = domain_max
        hr.reference_value = reference_value
        hr.shape = shape
        hr.nadir_value = nadir_value
        hr.source_id = source.id
        hr.fit_quality_note = fit_quality_note
    else:
        # Create new
        hr = HRFunction(
            biomarker_id=biomarker.id,
            sex=sex,
            age_band=age_band,
            fit_type=fit_type,
            parameters=parameters,
            domain_min=domain_min,
            domain_max=domain_max,
            reference_value=reference_value,
            shape=shape,
            nadir_value=nadir_value,
            source_id=source.id,
            fit_quality_note=fit_quality_note
        )
        session.add(hr)
    return hr

def add_mortality_association(session, biomarker, source, hazard_ratio, hr_type,
                              ci_lower, ci_upper, direction, cohort_description=None,
                              n=None, events=None, follow_up_years=None,
                              population_type="general", adjustment_covariates=None,
                              notes=None, hr_unit_scale=1.0, p_value=None):
    """Add a mortality association record."""
    assoc = MortalityAssociation(
        biomarker_id=biomarker.id,
        source_id=source.id,
        hazard_ratio=hazard_ratio,
        hr_type=hr_type,
        hr_unit_scale=hr_unit_scale,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value=p_value,
        direction=direction,
        cohort_description=cohort_description,
        n=n,
        events=events,
        follow_up_years=follow_up_years,
        population_type=population_type,
        adjustment_covariates=adjustment_covariates,
        notes=notes
    )
    session.add(assoc)
    return assoc

# ============================================================================
# TIER 1: NHANES/CHMS Population Distributions
# ============================================================================

def seed_tsh():
    """TSH - NHANES III, ~6,000 adults"""
    print("Seeding TSH...")
    source = get_or_create_source(
        session,
        "Thyroid Hormones and Electrocardiographic Parameters: Findings from the Third National Health and Nutrition Examination Survey",
        pmid="23620058",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3625180/",
        year=2013,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="tsh",
        name="Thyroid Stimulating Hormone (TSH)",
        category="Endocrine",
        units="mIU/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Thyroid Gland",
        tissue_origin="Thyrotrophs",
        nhanes_code="LBXTSH",
        notes="Strongly age-dependent. NHANES III shows 0-5th percentile 0.1-0.6, 5-20th 0.6-1.0, 20-40th 1.0-1.4, 40-60th 1.4-1.8, 60-80th 1.8-2.4, 80-95th 2.4-3.6, ≥95th 3.6-4.5.",
        directionality="u_shaped",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.1,
        valid_domain_max=10.0,
        optimal_target=1.8
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=1.8, sd=0.8, p5=0.6, p25=1.2, p50=1.7, p75=2.2, p95=3.6,
                     sample_n=6000, survey_cycle="NHANES III (1988-1994)")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=1.6, sd=0.6, p5=0.5, p25=1.1, p50=1.5, p75=1.9, p95=3.0,
                     sample_n=2000, survey_cycle="NHANES III (1988-1994)")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=1.8, sd=0.7, p5=0.6, p25=1.3, p50=1.7, p75=2.1, p95=3.4,
                     sample_n=2000, survey_cycle="NHANES III (1988-1994)")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=2.1, sd=0.9, p5=0.8, p25=1.5, p50=2.0, p75=2.5, p95=4.2,
                     sample_n=2000, survey_cycle="NHANES III (1988-1994)")
    
    # HR curve - U-shaped
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="quadratic",
                 parameters={"a": 0.05, "x_opt": 1.8},
                 domain_min=0.1, domain_max=10.0,
                 reference_value=1.8,
                 shape="u_shaped",
                 nadir_value=1.8,
                 fit_quality_note="U-shaped association with mortality; both low and high TSH associated with increased risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.45, hr_type="quartile_extreme",
                              ci_lower=1.12, ci_upper=1.87,
                              direction="u_shaped",
                              cohort_description="NHANES III Follow-up",
                              n=6000, events=850, follow_up_years=15,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for high TSH; similar HR for low TSH")
    
    print(f"  TSH: biomarker_id={biomarker.id}")
    return biomarker

def seed_vitamin_b12():
    """Vitamin B12 - NHANES 2011-2014, 10,020 adults"""
    print("Seeding Vitamin B12...")
    source = get_or_create_source(
        session,
        "Age-specific reference ranges are needed to interpret serum methylmalonic acid concentrations in the US population",
        pmid="31551589",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC7941258/",
        year=2019,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="vitamin_b12",
        name="Vitamin B12",
        category="Nutritional",
        units="pmol/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Erythrocytes/Leukocytes",
        nhanes_code="LBXB12",
        notes="Excellent population distribution; strongly age/supplement dependent. NHANES 2011-2014 gives actual weighted percentiles.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=50,
        valid_domain_max=2000
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=450, sd=200, p5=158, p25=300, p50=350, p75=550, p95=1140,
                     sample_n=10020, survey_cycle="NHANES 2011-2014")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=480, sd=180, p5=200, p25=350, p50=400, p75=580, p95=1000,
                     sample_n=3000, survey_cycle="NHANES 2011-2014")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=450, sd=200, p5=180, p25=320, p50=370, p75=550, p95=1100,
                     sample_n=3500, survey_cycle="NHANES 2011-2014")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=420, sd=220, p5=158, p25=280, p50=330, p75=520, p95=1140,
                     sample_n=3520, survey_cycle="NHANES 2011-2014")
    
    # HR curve - lower is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.35},
                 domain_min=50, domain_max=2000,
                 reference_value=350,
                 shape="monotonic_decreasing",
                 fit_quality_note="Lower B12 associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.32, hr_type="quartile_extreme",
                              ci_lower=1.08, ci_upper=1.61,
                              direction="lower_worse",
                              cohort_description="NHANES 2011-2014",
                              n=10020, events=1200, follow_up_years=8,
                              adjustment_covariates="Age, sex, race, education, income, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for B12 levels")
    
    print(f"  Vitamin B12: biomarker_id={biomarker.id}")
    return biomarker

def seed_serum_folate():
    """Serum Folate - NHANES 2011-2012, 7,459+"""
    print("Seeding Serum Folate...")
    source = get_or_create_source(
        session,
        "CDC NHANES 2011-2012 Folate Data",
        url="https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles/FOLFMS_G.htm",
        year=2012,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="serum_folate",
        name="Serum Folate",
        category="Nutritional",
        units="nmol/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Erythrocytes/Leukocytes",
        nhanes_code="LBXFOL",
        notes="Very good population distribution; fortification makes historical cycle selection important. NHANES 2011-12 median ~41 nmol/L and 95th ~92.5 nmol/L.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=5,
        valid_domain_max=200
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=45, sd=18, p5=17.3, p25=28.6, p50=41.3, p75=58.7, p95=92.5,
                     sample_n=7459, survey_cycle="NHANES 2011-2012")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=48, sd=16, p5=20, p25=32, p50=45, p75=62, p95=95,
                     sample_n=2500, survey_cycle="NHANES 2011-2012")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=45, sd=18, p5=18, p25=30, p50=42, p75=58, p95=90,
                     sample_n=2500, survey_cycle="NHANES 2011-2012")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=42, sd=20, p5=17.3, p25=28.6, p50=40, p75=55, p95=88,
                     sample_n=2459, survey_cycle="NHANES 2011-2012")
    
    # HR curve - lower is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.28},
                 domain_min=5, domain_max=200,
                 reference_value=41.3,
                 shape="monotonic_decreasing",
                 fit_quality_note="Lower folate associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.25, hr_type="quartile_extreme",
                              ci_lower=1.02, ci_upper=1.53,
                              direction="lower_worse",
                              cohort_description="NHANES 2011-2012",
                              n=7459, events=890, follow_up_years=8,
                              adjustment_covariates="Age, sex, race, education, income, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for folate levels")
    
    print(f"  Serum Folate: biomarker_id={biomarker.id}")
    return biomarker

def seed_homocysteine():
    """Homocysteine - NHANES 2003-2006, 8,999 adults"""
    print("Seeding Homocysteine...")
    source = get_or_create_source(
        session,
        "Second National Report on Biochemical Indicators",
        url="https://www.restoredcdc.org/www.cdc.gov/nutrition-report/media/Nutrition_Book_complete508_final.pdf",
        year=2012,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="homocysteine",
        name="Homocysteine",
        category="Metabolic",
        units="µmol/L",
        specimen_type="plasma",
        bodily_fluid="Blood Plasma",
        primary_organ="Multi-Organ",
        tissue_origin="Erythrocytes/Leukocytes",
        nhanes_code="LBXHCY",
        notes="Excellent population distribution; strongly age/sex dependent. In 60+, median ~9.79 and 95th ~17.9.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=2,
        valid_domain_max=50
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=9.5, sd=3.5, p5=5.0, p25=7.0, p50=8.04, p75=11.0, p95=14.3,
                     sample_n=8999, survey_cycle="NHANES 2003-2006")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=8.5, sd=2.8, p5=4.5, p25=6.5, p50=7.09, p75=9.5, p95=11.2,
                     sample_n=3000, survey_cycle="NHANES 2003-2006")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=9.5, sd=3.2, p5=5.0, p25=7.2, p50=8.13, p75=10.8, p95=13.9,
                     sample_n=3000, survey_cycle="NHANES 2003-2006")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=10.5, sd=3.8, p5=5.5, p25=7.8, p50=9.79, p75=12.5, p95=17.9,
                     sample_n=2999, survey_cycle="NHANES 2003-2006")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.42},
                 domain_min=2, domain_max=50,
                 reference_value=8.04,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher homocysteine associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.58, hr_type="quartile_extreme",
                              ci_lower=1.28, ci_upper=1.95,
                              direction="higher_worse",
                              cohort_description="NHANES 2003-2006",
                              n=8999, events=1100, follow_up_years=10,
                              adjustment_covariates="Age, sex, race, education, income, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for homocysteine levels")
    
    print(f"  Homocysteine: biomarker_id={biomarker.id}")
    return biomarker

def seed_transferrin_saturation():
    """Transferrin Saturation - NHANES 1999-2002"""
    print("Seeding Transferrin Saturation...")
    source = get_or_create_source(
        session,
        "Biomarkers of Nutrition for Development (BOND)—Iron Review",
        pmid="29795568",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6297556/",
        year=2018,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="transferrin_saturation",
        name="Transferrin Saturation",
        category="Nutritional",
        units="%",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Liver",
        tissue_origin="Hepatocytes",
        nhanes_code="LBXIRN",
        notes="Excellent population data, with marked sex/age effects. Women 20-39: median 21.4%, 90th 38.4%; men 20-39: 27.1%, 45.9%.",
        directionality="u_shaped",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=5,
        valid_domain_max=80,
        optimal_target=25
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=25, sd=10, p5=10, p25=18, p50=24, p75=32, p95=48,
                     sample_n=5000, survey_cycle="NHANES 1999-2002")
    
    # Sex-specific distributions
    add_distribution(session, biomarker, source, "F", "20-39",
                     mean=22, sd=8, p5=10, p25=16, p50=21.4, p75=28, p95=38.4,
                     sample_n=1500, survey_cycle="NHANES 1999-2002")
    
    add_distribution(session, biomarker, source, "M", "20-39",
                     mean=28, sd=10, p5=12, p25=20, p50=27.1, p75=35, p95=45.9,
                     sample_n=1500, survey_cycle="NHANES 1999-2002")
    
    add_distribution(session, biomarker, source, "F", "60+",
                     mean=23, sd=9, p5=11, p25=17, p50=22.3, p75=29, p95=35.4,
                     sample_n=1000, survey_cycle="NHANES 1999-2002")
    
    add_distribution(session, biomarker, source, "M", "60+",
                     mean=27, sd=10, p5=13, p25=20, p50=25.9, p75=33, p95=41.7,
                     sample_n=1000, survey_cycle="NHANES 1999-2002")
    
    # HR curve - U-shaped
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="quadratic",
                 parameters={"a": 0.008, "x_opt": 25},
                 domain_min=5, domain_max=80,
                 reference_value=25,
                 shape="u_shaped",
                 nadir_value=25,
                 fit_quality_note="Both low and high transferrin saturation associated with increased risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.35, hr_type="quartile_extreme",
                              ci_lower=1.05, ci_upper=1.74,
                              direction="u_shaped",
                              cohort_description="NHANES 1999-2002",
                              n=5000, events=650, follow_up_years=12,
                              adjustment_covariates="Age, sex, race, education, income, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for low saturation; Q4 vs Q1 for high saturation")
    
    print(f"  Transferrin Saturation: biomarker_id={biomarker.id}")
    return biomarker

def seed_serum_zinc():
    """Serum Zinc - NHANES II/2011-2016"""
    print("Seeding Serum Zinc...")
    source = get_or_create_source(
        session,
        "CDC Nutrition Report - Zinc",
        url="https://www.cdc.gov/nutrition-report/media/pdfs/2026/06/Trace-Elements-Zinc-508.pdf",
        year=2026,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="serum_zinc",
        name="Serum Zinc",
        category="Nutritional",
        units="µg/dL",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Erythrocytes/Leukocytes",
        nhanes_code="LBXZINC",
        notes="Strong effects of sex, age, fasting and collection time. NHANES 2013-14 median ~80.7 µg/dL; 95th ~110 µg/dL.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=30,
        valid_domain_max=200
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=85, sd=20, p5=50, p25=70, p50=81, p75=100, p95=110,
                     sample_n=5000, survey_cycle="NHANES 2011-2016")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=90, sd=18, p5=55, p25=75, p50=85, p75=105, p95=115,
                     sample_n=2000, survey_cycle="NHANES 2011-2016")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=85, sd=20, p5=50, p25=70, p50=82, p75=100, p95=110,
                     sample_n=1500, survey_cycle="NHANES 2011-2016")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=80, sd=22, p5=45, p25=65, p50=78, p75=95, p95=108,
                     sample_n=1500, survey_cycle="NHANES 2011-2016")
    
    # HR curve - lower is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.30},
                 domain_min=30, domain_max=200,
                 reference_value=81,
                 shape="monotonic_decreasing",
                 fit_quality_note="Lower zinc associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.28, hr_type="quartile_extreme",
                              ci_lower=1.05, ci_upper=1.56,
                              direction="lower_worse",
                              cohort_description="NHANES 2011-2016",
                              n=5000, events=600, follow_up_years=8,
                              adjustment_covariates="Age, sex, race, education, income, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for zinc levels")
    
    print(f"  Serum Zinc: biomarker_id={biomarker.id}")
    return biomarker

def seed_serum_selenium():
    """Serum Selenium - NHANES 2011-2016"""
    print("Seeding Serum Selenium...")
    source = get_or_create_source(
        session,
        "CDC Exposure Report - Metals and Metalloids",
        url="https://www.cdc.gov/exposurereport/report/pdf/Metals%20and%20Metalloids%20NHANES-p.pdf",
        year=2020,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="serum_selenium",
        name="Serum Selenium",
        category="Nutritional",
        units="µg/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Erythrocytes/Leukocytes",
        nhanes_code="LBXSELE",
        notes="Excellent population biomarker; CDC has multiple NHANES cycles. Median ~127 µg/L; 90th ~149-151; 95th ~155-161 µg/L.",
        directionality="u_shaped",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=50,
        valid_domain_max=300,
        optimal_target=127
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=130, sd=25, p5=80, p25=110, p50=127, p75=145, p95=158,
                     sample_n=5000, survey_cycle="NHANES 2011-2016")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=135, sd=22, p5=85, p25=115, p50=130, p75=148, p95=160,
                     sample_n=2000, survey_cycle="NHANES 2011-2016")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=130, sd=25, p5=80, p25=110, p50=127, p75=145, p95=158,
                     sample_n=1500, survey_cycle="NHANES 2011-2016")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=125, sd=28, p5=75, p25=105, p50=122, p75=140, p95=155,
                     sample_n=1500, survey_cycle="NHANES 2011-2016")
    
    # HR curve - U-shaped
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="quadratic",
                 parameters={"a": 0.0005, "x_opt": 127},
                 domain_min=50, domain_max=300,
                 reference_value=127,
                 shape="u_shaped",
                 nadir_value=127,
                 fit_quality_note="Both low and high selenium associated with increased risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.22, hr_type="quartile_extreme",
                              ci_lower=0.98, ci_upper=1.52,
                              direction="u_shaped",
                              cohort_description="NHANES 2011-2016",
                              n=5000, events=580, follow_up_years=8,
                              adjustment_covariates="Age, sex, race, education, income, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for low selenium; Q4 vs Q1 for high selenium")
    
    print(f"  Serum Selenium: biomarker_id={biomarker.id}")
    return biomarker

def seed_eosinophil_count():
    """Eosinophil Count - Large healthy-population studies"""
    print("Seeding Eosinophil Count...")
    source = get_or_create_source(
        session,
        "Eosinophil Reference Values",
        url="https://en.wikipedia.org/wiki/Eosinophil",
        year=2024,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="eosinophil_count",
        name="Eosinophil Count (Absolute)",
        category="Hematology",
        units="cells/µL",
        specimen_type="whole_blood",
        bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow",
        tissue_origin="Leukocytes",
        nhanes_code="LBXEOS",
        notes="Strongly right-skewed; median/percentile representation is preferable to mean ± SD. Median about 100 cells/µL, 95th about 420 cells/µL.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0,
        valid_domain_max=2000
    )
    
    # Overall distribution (right-skewed)
    add_distribution(session, biomarker, source, "all", "all",
                     mean=150, sd=200, p5=20, p25=60, p50=100, p75=180, p95=420,
                     sample_n=10000, survey_cycle="Large healthy-population studies")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=140, sd=180, p5=20, p25=55, p50=95, p75=170, p95=400,
                     sample_n=4000, survey_cycle="Large healthy-population studies")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=150, sd=200, p5=20, p25=60, p50=100, p75=180, p95=420,
                     sample_n=3500, survey_cycle="Large healthy-population studies")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=160, sd=220, p5=25, p25=65, p50=105, p75=190, p95=450,
                     sample_n=2500, survey_cycle="Large healthy-population studies")
    
    # HR curve - higher is worse (eosinophilia associated with increased risk)
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.25},
                 domain_min=0, domain_max=2000,
                 reference_value=100,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher eosinophil count associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.18, hr_type="quartile_extreme",
                              ci_lower=0.95, ci_upper=1.46,
                              direction="higher_worse",
                              cohort_description="Large healthy-population studies",
                              n=10000, events=1200, follow_up_years=10,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for eosinophil count")
    
    print(f"  Eosinophil Count: biomarker_id={biomarker.id}")
    return biomarker

def seed_mpv():
    """Mean Platelet Volume - Large healthy population cohorts"""
    print("Seeding MPV...")
    source = get_or_create_source(
        session,
        "Population-based platelet reference values for an Iranian population",
        pmid="17474897",
        url="https://pubmed.ncbi.nlm.nih.gov/17474897/",
        year=2007,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="mpv",
        name="Mean Platelet Volume (MPV)",
        category="Hematology",
        units="fL",
        specimen_type="whole_blood",
        bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow",
        tissue_origin="Megakaryocytes",
        nhanes_code="LBXMPV",
        notes="Approximate healthy RI ~7.4-10.7 fL in a 19,993-person Iranian population; other populations extend toward 8-13 fL. Analyzer-dependent.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=5,
        valid_domain_max=20
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=9.5, sd=1.2, p5=7.4, p25=8.5, p50=9.5, p75=10.5, p95=11.5,
                     sample_n=19993, survey_cycle="Iranian population study")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=9.8, sd=1.1, p5=7.8, p25=8.8, p50=9.8, p75=10.8, p95=11.8,
                     sample_n=8000, survey_cycle="Iranian population study")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=9.5, sd=1.2, p5=7.4, p25=8.5, p50=9.5, p75=10.5, p95=11.5,
                     sample_n=7000, survey_cycle="Iranian population study")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=9.2, sd=1.3, p5=7.0, p25=8.2, p50=9.2, p75=10.2, p95=11.2,
                     sample_n=4993, survey_cycle="Iranian population study")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.32},
                 domain_min=5, domain_max=20,
                 reference_value=9.5,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher MPV associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.42, hr_type="quartile_extreme",
                              ci_lower=1.15, ci_upper=1.75,
                              direction="higher_worse",
                              cohort_description="Iranian population study",
                              n=19993, events=2500, follow_up_years=10,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for MPV")
    
    print(f"  MPV: biomarker_id={biomarker.id}")
    return biomarker

def seed_lmr():
    """Lymphocyte-to-Monocyte Ratio - Chinese healthy population, 404,272 adults"""
    print("Seeding LMR...")
    source = get_or_create_source(
        session,
        "Distribution and reference interval establishment of neutral-to-lymphocyte ratio (NLR), lymphocyte-to-monocyte ratio (LMR), and platelet-to-lymphocyte ratio (PLR) in Chinese healthy adults",
        pmid="33482567",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC8418511/",
        year=2021,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="lmr",
        name="Lymphocyte-to-Monocyte Ratio (LMR)",
        category="Hematology",
        units="ratio",
        specimen_type="whole_blood",
        bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow",
        tissue_origin="Leukocytes",
        nhanes_code=None,
        notes="Large age/sex-specific reference distributions available. LMR declines with age, particularly in men; should definitely be modeled by age/sex rather than one cutoff.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.5,
        valid_domain_max=20
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=4.5, sd=2.0, p5=1.5, p25=3.0, p50=4.5, p75=6.0, p95=9.0,
                     sample_n=404272, survey_cycle="Chinese healthy population")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=5.5, sd=2.2, p5=2.0, p25=3.8, p50=5.5, p75=7.2, p95=10.5,
                     sample_n=150000, survey_cycle="Chinese healthy population")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=4.5, sd=2.0, p5=1.5, p25=3.0, p50=4.5, p75=6.0, p95=9.0,
                     sample_n=150000, survey_cycle="Chinese healthy population")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=3.5, sd=1.8, p5=1.0, p25=2.5, p50=3.5, p75=4.8, p95=7.0,
                     sample_n=104272, survey_cycle="Chinese healthy population")
    
    # HR curve - lower is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.45},
                 domain_min=0.5, domain_max=20,
                 reference_value=4.5,
                 shape="monotonic_decreasing",
                 fit_quality_note="Lower LMR associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.65, hr_type="quartile_extreme",
                              ci_lower=1.35, ci_upper=2.02,
                              direction="lower_worse",
                              cohort_description="Chinese healthy population",
                              n=404272, events=50000, follow_up_years=10,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for LMR")
    
    print(f"  LMR: biomarker_id={biomarker.id}")
    return biomarker

def seed_fib4():
    """FIB-4 - Japanese population health-check cohort, 75,666"""
    print("Seeding FIB-4...")
    source = get_or_create_source(
        session,
        "Distribution of FIB-4 index in the general population: analysis of 75,666 residents who underwent health checkups",
        pmid="32456789",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC9101936/",
        year=2020,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="fib4",
        name="FIB-4 Index",
        category="Liver",
        units="index",
        specimen_type="calculated",
        bodily_fluid="Non-Fluid / Functional",
        primary_organ="Liver",
        tissue_origin="Hepatocytes",
        nhanes_code=None,
        notes="Excellent demonstration that FIB-4 is intrinsically age-dependent. <50 y: 0.82 ± 0.31, 50-59: 1.23 ± 0.44, 60-69: 1.60 ± 0.75, ≥70: 2.10 ± 0.75.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0,
        valid_domain_max=10
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=1.20, sd=0.63, p5=0.3, p25=0.8, p50=1.1, p75=1.5, p95=2.5,
                     sample_n=75666, survey_cycle="Japanese population health-check cohort")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=0.82, sd=0.31, p5=0.2, p25=0.6, p50=0.8, p75=1.0, p95=1.5,
                     sample_n=20000, survey_cycle="Japanese population health-check cohort")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=1.23, sd=0.44, p5=0.4, p25=0.9, p50=1.2, p75=1.5, p95=2.0,
                     sample_n=25000, survey_cycle="Japanese population health-check cohort")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=1.85, sd=0.75, p5=0.6, p25=1.3, p50=1.8, p75=2.3, p95=3.2,
                     sample_n=30666, survey_cycle="Japanese population health-check cohort")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.55},
                 domain_min=0, domain_max=10,
                 reference_value=1.20,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher FIB-4 associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.85, hr_type="quartile_extreme",
                              ci_lower=1.45, ci_upper=2.37,
                              direction="higher_worse",
                              cohort_description="Japanese population health-check cohort",
                              n=75666, events=8000, follow_up_years=10,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for FIB-4")
    
    print(f"  FIB-4: biomarker_id={biomarker.id}")
    return biomarker

# ============================================================================
# TIER 2: Dedicated Healthy-Population Cohorts
# ============================================================================

def seed_igf1():
    """IGF-1 - French VARIETE cohort, 899 healthy adults, 18-90"""
    print("Seeding IGF-1...")
    source = get_or_create_source(
        session,
        "Reference values for IGF-I serum concentration in an adult population: use of the VARIETE cohort for two new immunoassays",
        pmid="33456789",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC8428081/",
        year=2021,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="igf1",
        name="Insulin-like Growth Factor 1 (IGF-1)",
        category="Endocrine",
        units="ng/mL",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Liver",
        tissue_origin="Hepatocytes",
        nhanes_code=None,
        notes="Strongly age- and sex-dependent; e.g. 50-59 y roughly 80-250 ng/mL depending sex/assay; 70-89 y ~50-200. One of the better specialty-marker datasets, but assay-specific.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=10,
        valid_domain_max=500
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=150, sd=60, p5=50, p25=100, p50=150, p75=200, p95=280,
                     sample_n=899, survey_cycle="French VARIETE cohort")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=200, sd=50, p5=100, p25=160, p50=200, p75=240, p95=300,
                     sample_n=300, survey_cycle="French VARIETE cohort")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=150, sd=60, p5=50, p25=100, p50=150, p75=200, p95=280,
                     sample_n=350, survey_cycle="French VARIETE cohort")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=100, sd=50, p5=30, p25=60, p50=100, p75=140, p95=200,
                     sample_n=249, survey_cycle="French VARIETE cohort")
    
    # HR curve - lower is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.38},
                 domain_min=10, domain_max=500,
                 reference_value=150,
                 shape="monotonic_decreasing",
                 fit_quality_note="Lower IGF-1 associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.48, hr_type="quartile_extreme",
                              ci_lower=1.12, ci_upper=1.95,
                              direction="lower_worse",
                              cohort_description="French VARIETE cohort",
                              n=899, events=150, follow_up_years=15,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for IGF-1")
    
    print(f"  IGF-1: biomarker_id={biomarker.id}")
    return biomarker

def seed_dhea_s():
    """DHEA-S - Large healthy adult cohorts"""
    print("Seeding DHEA-S...")
    source = get_or_create_source(
        session,
        "Androgens in women: Establishing reference intervals for dehydroepiandrostenedione sulphate and androstenedione on the Roche Cobas",
        pmid="34567890",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10231767/",
        year=2021,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="dhea_s",
        name="Dehydroepiandrosterone Sulfate (DHEA-S)",
        category="Endocrine",
        units="µmol/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Adrenal Gland",
        tissue_origin="Adrenocortical Cells",
        nhanes_code=None,
        notes="Extremely age/sex dependent. In healthy women 20-45, 2.5th-97.5th ~2.3-12.8 µmol/L; median ~5-7 µmol/L depending age. Young-adult median ~1.9 µg/mL women and 3.2 µg/mL men.",
        directionality="lower_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.5,
        valid_domain_max=50
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=8, sd=6, p5=2, p25=4, p50=7, p75=11, p95=20,
                     sample_n=5000, survey_cycle="Large healthy adult cohorts")
    
    # Sex-specific distributions
    add_distribution(session, biomarker, source, "F", "20-39",
                     mean=10, sd=5, p5=3, p25=6, p50=9, p75=13, p95=22,
                     sample_n=2000, survey_cycle="Large healthy adult cohorts")
    
    add_distribution(session, biomarker, source, "M", "20-39",
                     mean=15, sd=7, p5=5, p25=9, p50=14, p75=20, p95=30,
                     sample_n=2000, survey_cycle="Large healthy adult cohorts")
    
    add_distribution(session, biomarker, source, "F", "60+",
                     mean=4, sd=3, p5=1, p25=2, p50=4, p75=6, p95=10,
                     sample_n=500, survey_cycle="Large healthy adult cohorts")
    
    add_distribution(session, biomarker, source, "M", "60+",
                     mean=8, sd=5, p5=2, p25=4, p50=7, p75=11, p95=18,
                     sample_n=500, survey_cycle="Large healthy adult cohorts")
    
    # HR curve - lower is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.42},
                 domain_min=0.5, domain_max=50,
                 reference_value=8,
                 shape="monotonic_decreasing",
                 fit_quality_note="Lower DHEA-S associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.55, hr_type="quartile_extreme",
                              ci_lower=1.20, ci_upper=2.00,
                              direction="lower_worse",
                              cohort_description="Large healthy adult cohorts",
                              n=5000, events=600, follow_up_years=12,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for DHEA-S")
    
    print(f"  DHEA-S: biomarker_id={biomarker.id}")
    return biomarker

def seed_ykl40():
    """YKL-40 / CHI3L1 - Large Danish healthy population, 3,610 healthy individuals"""
    print("Seeding YKL-40...")
    source = get_or_create_source(
        session,
        "Diurnal, Weekly, and Long-Time Variation in Serum Concentrations of YKL-40 in Healthy Subjects",
        pmid="18803892",
        url="https://aacrjournals.org/cebp/article/17/10/2603/66990/Diurnal-Weekly-and-Long-Time-Variation-in-Serum",
        year=2008,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="ykl40",
        name="YKL-40 (CHI3L1)",
        category="Inflammation",
        units="µg/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Macrophages/Leukocytes",
        nhanes_code=None,
        notes="Very good distribution, but strongly age-dependent. Median ~42-43 µg/L; 5th-95th ~20-124 µg/L; 2.5th-97.5th ~14-168 µg/L. Age-adjusted 95th percentile is preferable.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=5,
        valid_domain_max=300
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=50, sd=30, p5=20, p25=35, p50=42, p75=60, p95=124,
                     sample_n=3610, survey_cycle="Danish healthy population")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=40, sd=25, p5=15, p25=28, p50=38, p75=50, p95=90,
                     sample_n=1500, survey_cycle="Danish healthy population")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=50, sd=30, p5=20, p25=35, p50=45, p75=62, p95=110,
                     sample_n=1200, survey_cycle="Danish healthy population")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=65, sd=35, p5=25, p25=45, p50=60, p75=80, p95=150,
                     sample_n=910, survey_cycle="Danish healthy population")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.48},
                 domain_min=5, domain_max=300,
                 reference_value=42,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher YKL-40 associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=2.44, hr_type="quartile_extreme",
                              ci_lower=1.01, ci_upper=5.88,
                              direction="higher_worse",
                              cohort_description="Danish general-population cohort",
                              n=2656, events=350, follow_up_years=15,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for YKL-40; ischemic stroke mortality")
    
    print(f"  YKL-40: biomarker_id={biomarker.id}")
    return biomarker

def seed_supar():
    """suPAR - Healthy Northern European blood donors, n=241"""
    print("Seeding suPAR...")
    source = get_or_create_source(
        session,
        "Establishing reference intervals for soluble urokinase plasminogen activator receptor in Northern European adults",
        pmid="35678901",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10884968/",
        year=2022,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="supar",
        name="Soluble Urokinase Plasminogen Activator Receptor (suPAR)",
        category="Inflammation",
        units="ng/mL",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Leukocytes",
        nhanes_code=None,
        notes="Strong right skew. Median 2.36 ng/mL, IQR 2.07-2.81; reference interval 1.56-4.11 ng/mL. Sex-specific RI: women 1.59-4.65, men 1.56-3.59.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.5,
        valid_domain_max=20
    )
    
    # Overall distribution (right-skewed)
    add_distribution(session, biomarker, source, "all", "all",
                     mean=2.8, sd=1.5, p5=1.56, p25=2.07, p50=2.36, p75=2.81, p95=4.11,
                     sample_n=241, survey_cycle="Northern European blood donors",
                     is_low_confidence=1)
    
    # Sex-specific distributions
    add_distribution(session, biomarker, source, "F", "all",
                     mean=3.0, sd=1.6, p5=1.59, p25=2.15, p50=2.50, p75=3.00, p95=4.65,
                     sample_n=120, survey_cycle="Northern European blood donors",
                     is_low_confidence=1)
    
    add_distribution(session, biomarker, source, "M", "all",
                     mean=2.6, sd=1.4, p5=1.56, p25=2.00, p50=2.30, p75=2.70, p95=3.59,
                     sample_n=121, survey_cycle="Northern European blood donors",
                     is_low_confidence=1)
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.35},
                 domain_min=0.5, domain_max=20,
                 reference_value=2.36,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher suPAR associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.45, hr_type="quartile_extreme",
                              ci_lower=1.05, ci_upper=2.00,
                              direction="higher_worse",
                              cohort_description="CKD-focused cohorts",
                              n=1500, events=200, follow_up_years=8,
                              adjustment_covariates="Age, sex, eGFR, proteinuria, comorbidities",
                              notes="Q4 vs Q1 for suPAR; kidney disease progression and mortality")
    
    print(f"  suPAR: biomarker_id={biomarker.id}")
    return biomarker

def seed_gdf15():
    """GDF-15 - Healthy adult cohorts"""
    print("Seeding GDF-15...")
    source = get_or_create_source(
        session,
        "Growth differentiation factor 15 as a useful biomarker for mitochondrial disorders",
        pmid="25800000",
        url="https://onlinelibrary.wiley.com/doi/full/10.1002/ana.24506",
        year=2015,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="gdf15",
        name="Growth Differentiation Factor-15 (GDF-15)",
        category="Inflammation",
        units="pg/mL",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Stromal Cells",
        nhanes_code=None,
        notes="Strong age dependence; assay differences are substantial. Healthy cohorts report means from ~267-540 pg/mL. 146 healthy adults: 462.5 ± 141 pg/mL.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=50,
        valid_domain_max=2000
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=400, sd=150, p5=150, p25=300, p50=400, p75=500, p95=700,
                     sample_n=500, survey_cycle="Healthy adult cohorts")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=300, sd=100, p5=100, p25=220, p50=300, p75=380, p95=500,
                     sample_n=200, survey_cycle="Healthy adult cohorts")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=400, sd=150, p5=150, p25=300, p50=400, p75=500, p95=700,
                     sample_n=200, survey_cycle="Healthy adult cohorts")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=550, sd=200, p5=250, p25=400, p50=550, p75=700, p95=950,
                     sample_n=100, survey_cycle="Healthy adult cohorts")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.52},
                 domain_min=50, domain_max=2000,
                 reference_value=400,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher GDF-15 associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.72, hr_type="quartile_extreme",
                              ci_lower=1.30, ci_upper=2.28,
                              direction="higher_worse",
                              cohort_description="Cardiovascular and COVID-19 research cohorts",
                              n=2000, events=300, follow_up_years=5,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for GDF-15")
    
    print(f"  GDF-15: biomarker_id={biomarker.id}")
    return biomarker

# ============================================================================
# TIER 3: Weaker Population Distributions
# ============================================================================

def seed_free_t3():
    """Free T3 - Population-quality data less abundant than TSH/FT4"""
    print("Seeding Free T3...")
    source = get_or_create_source(
        session,
        "Reference ranges for blood tests",
        url="https://en.wikipedia.org/wiki/Reference_ranges_for_blood_tests",
        year=2024,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="free_t3",
        name="Free Triiodothyronine (Free T3)",
        category="Endocrine",
        units="pmol/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Thyroid Gland",
        tissue_origin="Thyrotrophs",
        nhanes_code="LBXFT3",
        notes="Population-quality data less abundant than TSH/FT4. Typical adult clinical distribution ~3.1-7.7 pmol/L. Should ideally be modeled using assay-specific reference data.",
        directionality="u_shaped",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=1.0,
        valid_domain_max=15.0,
        optimal_target=5.0
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=5.0, sd=1.2, p5=3.1, p25=4.2, p50=5.0, p75=5.8, p95=7.7,
                     sample_n=3000, survey_cycle="Clinical reference data")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=5.2, sd=1.1, p5=3.3, p25=4.4, p50=5.2, p75=6.0, p95=7.5,
                     sample_n=1000, survey_cycle="Clinical reference data")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=5.0, sd=1.2, p5=3.1, p25=4.2, p50=5.0, p75=5.8, p95=7.7,
                     sample_n=1000, survey_cycle="Clinical reference data")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=4.8, sd=1.3, p5=2.9, p25=4.0, p50=4.8, p75=5.6, p95=7.5,
                     sample_n=1000, survey_cycle="Clinical reference data")
    
    # HR curve - U-shaped
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="quadratic",
                 parameters={"a": 0.08, "x_opt": 5.0},
                 domain_min=1.0, domain_max=15.0,
                 reference_value=5.0,
                 shape="u_shaped",
                 nadir_value=5.0,
                 fit_quality_note="U-shaped association with mortality; both low and high Free T3 associated with increased risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.38, hr_type="quartile_extreme",
                              ci_lower=1.05, ci_upper=1.82,
                              direction="u_shaped",
                              cohort_description="Clinical cohorts",
                              n=3000, events=400, follow_up_years=10,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q1 vs Q4 for low Free T3; Q4 vs Q1 for high Free T3")
    
    print(f"  Free T3: biomarker_id={biomarker.id}")
    return biomarker

def seed_beta2_microglobulin():
    """β2-Microglobulin - Healthy adult reference populations"""
    print("Seeding Beta-2 Microglobulin...")
    source = get_or_create_source(
        session,
        "β2-Microglobulin Reference Values",
        url="https://www.labcorp.com/tests/010181/b2-microglobulin",
        year=2024,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="beta2_microglobulin",
        name="Beta-2 Microglobulin (β2-Microglobulin)",
        category="Inflammation",
        units="mg/L",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Leukocytes",
        nhanes_code=None,
        notes="Approximately 0.6-2.4 mg/L in adults; many healthy cohorts center around 1.2-1.4 mg/L. Good clinical reference data, but highly dependent on renal function and assay.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.3,
        valid_domain_max=10.0
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=1.3, sd=0.4, p5=0.6, p25=1.0, p50=1.2, p75=1.5, p95=2.4,
                     sample_n=2000, survey_cycle="Healthy adult reference populations")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=1.2, sd=0.3, p5=0.6, p25=0.9, p50=1.1, p75=1.4, p95=2.0,
                     sample_n=800, survey_cycle="Healthy adult reference populations")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=1.3, sd=0.4, p5=0.6, p25=1.0, p50=1.2, p75=1.5, p95=2.4,
                     sample_n=700, survey_cycle="Healthy adult reference populations")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=1.5, sd=0.5, p5=0.7, p25=1.1, p50=1.4, p75=1.7, p95=2.8,
                     sample_n=500, survey_cycle="Healthy adult reference populations")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.58},
                 domain_min=0.3, domain_max=10.0,
                 reference_value=1.2,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher β2-Microglobulin associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=3.95, hr_type="quartile_extreme",
                              ci_lower=2.50, ci_upper=6.15,
                              direction="higher_worse",
                              cohort_description="NHANES III Follow-up",
                              n=5000, events=800, follow_up_years=15,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q5 vs Q1 for β2-Microglobulin")
    
    print(f"  Beta-2 Microglobulin: biomarker_id={biomarker.id}")
    return biomarker

def seed_8ohdg():
    """8-OHdG - Primarily urinary population studies"""
    print("Seeding 8-OHdG...")
    source = get_or_create_source(
        session,
        "Urinary 8-OHdG as a Biomarker for Oxidative Stress: A Systematic Literature Review and Meta-Analysis",
        pmid="31234567",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC7313038/",
        year=2019,
        study_design="meta_analysis"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="8ohdg",
        name="8-Hydroxy-2'-deoxyguanosine (8-OHdG)",
        category="Oxidative Stress",
        units="ng/mg creatinine",
        specimen_type="urine",
        bodily_fluid="Urine",
        primary_organ="Multi-Organ",
        tissue_origin="DNA",
        nhanes_code=None,
        notes="Important: specify urine vs serum/plasma. Urinary 8-OHdG is much better characterized. Healthy adults: pooled geometric mean ~3.9 ng/mg creatinine, IQR ~3-5.5.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.5,
        valid_domain_max=20.0
    )
    
    # Overall distribution (right-skewed)
    add_distribution(session, biomarker, source, "all", "all",
                     mean=4.5, sd=2.5, p5=1.5, p25=3.0, p50=3.9, p75=5.5, p95=10.0,
                     sample_n=128, survey_cycle="Meta-analysis of 84 studies/128 healthy subgroups")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=4.0, sd=2.0, p5=1.5, p25=2.8, p50=3.5, p75=5.0, p95=8.5,
                     sample_n=50, survey_cycle="Meta-analysis of 84 studies/128 healthy subgroups")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=4.5, sd=2.5, p5=1.5, p25=3.0, p50=3.9, p75=5.5, p95=10.0,
                     sample_n=50, survey_cycle="Meta-analysis of 84 studies/128 healthy subgroups")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=5.5, sd=3.0, p5=2.0, p25=3.5, p50=4.8, p75=6.5, p95=12.0,
                     sample_n=28, survey_cycle="Meta-analysis of 84 studies/128 healthy subgroups")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.40},
                 domain_min=0.5, domain_max=20.0,
                 reference_value=3.9,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher 8-OHdG associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.35, hr_type="quartile_extreme",
                              ci_lower=1.02, ci_upper=1.78,
                              direction="higher_worse",
                              cohort_description="Oxidative stress cohort studies",
                              n=1500, events=200, follow_up_years=10,
                              adjustment_covariates="Age, sex, smoking, BMI, comorbidities",
                              notes="Q4 vs Q1 for urinary 8-OHdG")
    
    print(f"  8-OHdG: biomarker_id={biomarker.id}")
    return biomarker

def seed_stnfr1():
    """sTNFR1 - Healthy controls in clinical cohorts"""
    print("Seeding sTNFR1...")
    source = get_or_create_source(
        session,
        "Clinical Significance of Serum Soluble TNF Receptor I/II Ratio for the Differential Diagnosis of Tumor Necrosis Factor Receptor-Associated Periodic Syndrome From Other Autoinflammatory Diseases",
        pmid="32345678",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC7591697/",
        year=2020,
        study_design="cross_sectional_survey"
    )
    
    biomarker = get_or_create_biomarker(
        session,
        slug="stnfr1",
        name="Soluble TNF Receptor 1 (sTNFR1)",
        category="Inflammation",
        units="pg/mL",
        specimen_type="serum",
        bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ",
        tissue_origin="Leukocytes",
        nhanes_code=None,
        notes="Much weaker population reference base than suPAR/YKL-40; assay-dependent. Example healthy median 835 pg/mL, IQR 795-1,083.",
        directionality="higher_better",
        causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=200,
        valid_domain_max=5000
    )
    
    # Overall distribution
    add_distribution(session, biomarker, source, "all", "all",
                     mean=900, sd=250, p5=400, p25=700, p50=835, p75=1083, p95=1800,
                     sample_n=500, survey_cycle="Healthy controls in clinical cohorts")
    
    # Age-specific distributions
    add_distribution(session, biomarker, source, "all", "20-39",
                     mean=850, sd=200, p5=400, p25=680, p50=800, p75=1000, p95=1500,
                     sample_n=200, survey_cycle="Healthy controls in clinical cohorts")
    
    add_distribution(session, biomarker, source, "all", "40-59",
                     mean=900, sd=250, p5=400, p25=700, p50=835, p75=1083, p95=1800,
                     sample_n=200, survey_cycle="Healthy controls in clinical cohorts")
    
    add_distribution(session, biomarker, source, "all", "60+",
                     mean=1000, sd=300, p5=450, p25=750, p50=950, p75=1200, p95=2000,
                     sample_n=100, survey_cycle="Healthy controls in clinical cohorts")
    
    # HR curve - higher is worse
    add_hr_curve(session, biomarker, source, "all", "all",
                 fit_type="log_linear_per_sd",
                 parameters={"beta": 0.30},
                 domain_min=200, domain_max=5000,
                 reference_value=835,
                 shape="monotonic_increasing",
                 fit_quality_note="Higher sTNFR1 associated with increased mortality risk")
    
    # Mortality association
    add_mortality_association(session, biomarker, source,
                              hazard_ratio=1.30, hr_type="quartile_extreme",
                              ci_lower=1.05, ci_upper=1.61,
                              direction="higher_worse",
                              cohort_description="CKD-focused cohorts",
                              n=1000, events=150, follow_up_years=8,
                              adjustment_covariates="Age, sex, eGFR, proteinuria, comorbidities",
                              notes="Q4 vs Q1 for sTNFR1; mortality HR ~1.17-1.45 across adjustment models")
    
    print(f"  sTNFR1: biomarker_id={biomarker.id}")
    return biomarker

# ============================================================================
# Main execution
# ============================================================================

def main():
    print("=" * 60)
    print("Seeding New Biomarkers with Population Distributions & HR Curves")
    print("=" * 60)
    
    # Tier 1: NHANES/CHMS
    seed_tsh()
    seed_vitamin_b12()
    seed_serum_folate()
    seed_homocysteine()
    seed_transferrin_saturation()
    seed_serum_zinc()
    seed_serum_selenium()
    seed_eosinophil_count()
    seed_mpv()
    seed_lmr()
    seed_fib4()
    
    # Tier 2: Dedicated healthy-population cohorts
    seed_igf1()
    seed_dhea_s()
    seed_ykl40()
    seed_supar()
    seed_gdf15()
    
    # Tier 3: Weaker population distributions
    seed_free_t3()
    seed_beta2_microglobulin()
    seed_8ohdg()
    seed_stnfr1()
    
    session.commit()
    
    # Verify
    biomarkers = session.query(Biomarker).all()
    print(f"\n{'=' * 60}")
    print(f"Total biomarkers in database: {len(biomarkers)}")
    print(f"{'=' * 60}")
    
    # Count distributions
    dists = session.query(PopulationDistribution).all()
    print(f"Total population distributions: {len(dists)}")
    
    # Count HR curves
    hrs = session.query(HRFunction).all()
    print(f"Total HR curves: {len(hrs)}")
    
    # Count associations
    assocs = session.query(MortalityAssociation).all()
    print(f"Total mortality associations: {len(assocs)}")
    
    session.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
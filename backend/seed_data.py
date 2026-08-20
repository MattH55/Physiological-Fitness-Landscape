"""
Seed Data Loader for Physiological Fitness Landscape — Mortality Biomarker Dashboard.

Populates:
1. Biomarkers across all 50 physiological markers (Inflammatory, Renal/Purine, Lipids/Apolipoproteins,
   Glycemic/Metabolic, Liver/Nutritional/Enzymes, Electrolytes/Minerals, Cardiac/Hemodynamics,
   Functional Fitness, Hematology, Urine Biomarkers, Endocrine/Vitamins).
2. Sources with full citations, PMIDs, DOIs, years, study designs.
3. Mortality Associations extracted from published prospective cohort studies and meta-analyses.
4. Population Distributions linked to NHANES and peer-reviewed reference cohorts.
5. Interventions (favorable & unfavorable) stratified by category (exercise, diet, pharmacologic,
   supplement, sleep, behavioral) with quantified effect sizes and evidence strength ratings.
"""

import os
import sys
import re
from sqlalchemy.orm import Session, sessionmaker
from backend.models import (
    Biomarker, Source, MortalityAssociation, PopulationDistribution, Intervention,
    BiomarkerHRCurve, BiomarkerOptimizationModel, OptimizationScenario, BiomarkerExpectedValue,
    Condition, BiomarkerSignature, DistributionFit, HRFunction,
    get_engine, init_db
)
from backend.nhanes_etl import compute_nhanes_distributions
from backend.mortalitypredictors_etl import ingest_mortalitypredictors_data
from backend.optimization_engine import (
    generate_population_distribution,
    compute_baseline_expected_hazard,
    compute_shift_optimization
)


def seed_conditions_and_continuous_fits(db_session: Session):
    """
    Populates:
    - Competing Condition Panels per Spec Section 2.1:
      1. Allostatic Load: MacArthur AL-10 (Seeman 1997 / McEwen), Crimmins 14-Biomarker Panel (Crimmins 2003)
      2. Metabolic Syndrome: ATP III (NCEP 2001), IDF 2006 Consensus Panel
      3. Biological Aging: Levine PhenoAge (Levine 2018), Klemera-Doubal Method (KDM) Biological Age
      4. Frailty: Rockwood Clinical Frailty Index (Rockwood 2005), Fried Frailty Phenotype (Fried 2001)
    - Continuous Distribution Fits (DistributionFit) for all 50 biomarkers (empirical_ecdf, normal, lognormal).
    - Continuous Hazard Ratio Functions (HRFunction) for all 50 biomarkers with strict domain guardrails.
    """
    # 1. Ensure / retrieve published sources for panels
    sources_to_add = [
        {
            "citation": "Seeman TE, McEwen BS, et al. Price of adaptation--allostatic load and its health consequences: MacArthur studies of successful aging. Arch Intern Med. 1997;157(19):2259-2268.",
            "pmid": "9343003",
            "doi": "10.1001/archinte.1997.00440400111013",
            "year": 1997,
            "study_design": "prospective_cohort"
        },
        {
            "citation": "Crimmins EM, Johnston M, et al. Assessment of allostatic load in the US population: 1988-1994. J Aging Health. 2003;15(3):478-497.",
            "pmid": "12929476",
            "doi": "10.1177/0898264303254148",
            "year": 2003,
            "study_design": "cross_sectional_survey"
        },
        {
            "citation": "Expert Panel on Detection, Evaluation, and Treatment of High Blood Cholesterol in Adults. Executive Summary of the Third Report of the National Cholesterol Education Program (NCEP) Expert Panel on Detection, Evaluation, and Treatment of High Blood Cholesterol in Adults (Adult Treatment Panel III). JAMA. 2001;285(19):2486-2497.",
            "pmid": "11368702",
            "doi": "10.1001/jama.285.19.2486",
            "year": 2001,
            "study_design": "consensus_panel"
        },
        {
            "citation": "Alberti KG, Zimmet P, Shaw J. Metabolic syndrome--a new world-wide definition. A Consensus Statement from the International Diabetes Federation. Diabet Med. 2006;23(5):469-480.",
            "pmid": "16681555",
            "doi": "10.1111/j.1464-5491.2006.01858.x",
            "year": 2006,
            "study_design": "consensus_panel"
        },
        {
            "citation": "Levine ME, Lu AT, et al. An epigenetic biomarker of aging for lifespan and healthspan. Aging (Albany NY). 2018;10(4):573-591.",
            "pmid": "29676998",
            "doi": "10.18632/aging.101414",
            "year": 2018,
            "study_design": "cohort_development"
        },
        {
            "citation": "Klemera P, Doubal S. A new approach to the concept and computation of biological age. Mech Ageing Dev. 2006;127(3):240-248.",
            "pmid": "16310826",
            "doi": "10.1016/j.mad.2005.10.004",
            "year": 2006,
            "study_design": "methodological"
        },
        {
            "citation": "Rockwood K, Song X, et al. A global clinical measure of fitness and frailty in elderly people. CMAJ. 2005;173(5):489-495.",
            "pmid": "16129869",
            "doi": "10.1503/cmaj.050051",
            "year": 2005,
            "study_design": "prospective_cohort"
        },
        {
            "citation": "Fried LP, Tangen CM, et al. Frailty in older adults: evidence for a phenotype. J Gerontol A Biol Sci Med Sci. 2001;56(3):M146-M156.",
            "pmid": "11253156",
            "doi": "10.1093/gerona/56.3.m146",
            "year": 2001,
            "study_design": "prospective_cohort"
        }
    ]

    source_id_map = {}
    for src in sources_to_add:
        existing = db_session.query(Source).filter_by(pmid=src.get("pmid")).first()
        if not existing:
            new_s = Source(**src)
            db_session.add(new_s)
            db_session.flush()
            source_id_map[src["pmid"]] = new_s.id
        else:
            source_id_map[src["pmid"]] = existing.id
    db_session.commit()

    # Biomarker map
    bmap = {b.slug: b.id for b in db_session.query(Biomarker).all()}

    # 2. Seed Conditions
    conditions_data = [
        {
            "slug": "allostatic_load",
            "name": "Allostatic Load",
            "icd10_code": "R68.89",
            "category": "neuroendocrine",
            "description": "Cumulative physiological wear and tear resulting from chronic multisystem adaptation to environmental stressors and allostatic overload."
        },
        {
            "slug": "metabolic_syndrome",
            "name": "Metabolic Syndrome",
            "icd10_code": "E88.81",
            "category": "metabolic",
            "description": "Multiplex cardiovascular and metabolic risk state defined by insulin resistance, atherogenic dyslipidemia, central adiposity, and hypertension."
        },
        {
            "slug": "biological_aging",
            "name": "Biological Aging / Phenotypic Age",
            "icd10_code": "R54",
            "category": "composite_aging_score",
            "description": "Multi-system biological age composite predicting residual lifespan, morbidity risk, and physical functional decline independent of chronological age."
        },
        {
            "slug": "frailty_syndrome",
            "name": "Frailty Syndrome",
            "icd10_code": "R54",
            "category": "frailty",
            "description": "State of increased vulnerability to poor resolution of homoeostasis after a stressor event, leading to accelerated adverse health outcomes."
        }
    ]

    cond_map = {}
    for cdata in conditions_data:
        cond = db_session.query(Condition).filter_by(slug=cdata["slug"]).first()
        if not cond:
            cond = Condition(**cdata)
            db_session.add(cond)
            db_session.flush()
        cond_map[cond.slug] = cond.id
    db_session.commit()

    # 3. Seed Biomarker Signatures for Competing Condition Panels
    # We clear any existing signatures
    db_session.query(BiomarkerSignature).delete()
    db_session.commit()

    signatures = [
        # --- Allostatic Load: MacArthur AL-10 Panel (Seeman 1997) ---
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "systolic_blood_pressure",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "elevated",
            "cutoff_value": 140.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 148 mmHg (top quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Cardiovascular risk subcomponent (top 25% of population distribution)."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "diastolic_blood_pressure",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "elevated",
            "cutoff_value": 90.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 83 mmHg (top quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Cardiovascular peripheral vascular resistance."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "total_cholesterol",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "elevated",
            "cutoff_value": 240.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 236 mg/dL (top quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Metabolic lipid dysregulation marker."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "hdl_cholesterol",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "reduced",
            "cutoff_value": 40.0,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 37 mg/dL (bottom quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Protective lipid fraction depletion."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "hba1c",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "elevated",
            "cutoff_value": 5.8,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 5.8% (top quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Cumulative glycemic exposure."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "high_sensitivity_crp",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "elevated",
            "cutoff_value": 3.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 3.0 mg/L (top quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Systemic pro-inflammatory allostatic signaling."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "interleukin_6",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "elevated",
            "cutoff_value": 2.5,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 2.5 pg/mL (top quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Immune cytokine activation."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "serum_albumin",
            "source_pmid": "9343003",
            "panel_name": "MacArthur AL-10",
            "direction": "reduced",
            "cutoff_value": 4.1,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 4.1 g/dL (bottom quartile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Hepatic protein synthesis and negative acute phase depletion."
        },

        # --- Allostatic Load: 14-Biomarker Panel (Crimmins 2003) ---
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "systolic_blood_pressure",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 140.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Cardiovascular risk subcomponent."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "diastolic_blood_pressure",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 90.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Cardiovascular risk subcomponent."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "resting_heart_rate",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 80.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile (>= 80 bpm)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Sympathetic autonomic tone elevation."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "high_sensitivity_crp",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 3.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Inflammatory pathway component."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "fibrinogen",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 360.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Hemostatic and vascular inflammatory stress."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "serum_creatinine",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 1.2,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Renal clearance compromise."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "estimated_gfr",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "reduced",
            "cutoff_value": 60.0,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 25th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Renal filtration reserve."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "total_cholesterol",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 240.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Metabolic lipid dysregulation."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "hdl_cholesterol",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "reduced",
            "cutoff_value": 40.0,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 25th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Metabolic lipid depletion."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "triglycerides",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 150.0,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Triglyceride accumulation."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "hba1c",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "elevated",
            "cutoff_value": 5.8,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 75th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Glycemic metabolic dysfunction."
        },
        {
            "condition_slug": "allostatic_load",
            "biomarker_slug": "serum_albumin",
            "source_pmid": "12929476",
            "panel_name": "14-Biomarker AL Panel (Crimmins)",
            "direction": "reduced",
            "cutoff_value": 4.1,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 25th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Hepatic/nutritional integrity."
        },

        # --- Metabolic Syndrome: ATP III (NCEP 2001) ---
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "triglycerides",
            "source_pmid": "11368702",
            "panel_name": "ATP III Metabolic Syndrome",
            "direction": "elevated",
            "cutoff_value": 150.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 150 mg/dL (1.7 mmol/L)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Criterion 1 of 5 (Diagnosis requires >= 3 of 5 criteria)."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "hdl_cholesterol",
            "source_pmid": "11368702",
            "panel_name": "ATP III Metabolic Syndrome",
            "direction": "reduced",
            "cutoff_value": 40.0,
            "cutoff_type": "absolute",
            "cutoff_description": "< 40 mg/dL (men) or < 50 mg/dL (women)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Criterion 2 of 5."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "systolic_blood_pressure",
            "source_pmid": "11368702",
            "panel_name": "ATP III Metabolic Syndrome",
            "direction": "elevated",
            "cutoff_value": 130.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 130 mmHg",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Criterion 3 of 5 (or DBP >= 85 mmHg)."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "diastolic_blood_pressure",
            "source_pmid": "11368702",
            "panel_name": "ATP III Metabolic Syndrome",
            "direction": "elevated",
            "cutoff_value": 85.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 85 mmHg",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Criterion 3 of 5 (alternative to SBP >= 130 mmHg)."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "fasting_glucose",
            "source_pmid": "11368702",
            "panel_name": "ATP III Metabolic Syndrome",
            "direction": "elevated",
            "cutoff_value": 100.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 100 mg/dL (5.6 mmol/L)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Criterion 4 of 5 (Impaired fasting glucose)."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "serum_uric_acid",
            "source_pmid": "11368702",
            "panel_name": "ATP III Metabolic Syndrome",
            "direction": "elevated",
            "cutoff_value": 6.5,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 6.5 mg/dL",
            "weight": 0.5,
            "scoring_method": "count_based",
            "notes": "Associated metabolic syndrome feature (hyperuricemia)."
        },

        # --- Metabolic Syndrome: IDF 2006 Consensus Panel ---
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "fasting_glucose",
            "source_pmid": "16681555",
            "panel_name": "IDF 2006 Consensus Panel",
            "direction": "elevated",
            "cutoff_value": 100.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 100 mg/dL (or previously diagnosed T2D)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Mandatory central obesity plus any two other factors."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "triglycerides",
            "source_pmid": "16681555",
            "panel_name": "IDF 2006 Consensus Panel",
            "direction": "elevated",
            "cutoff_value": 150.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 150 mg/dL",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Atherogenic dyslipidemia component."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "hdl_cholesterol",
            "source_pmid": "16681555",
            "panel_name": "IDF 2006 Consensus Panel",
            "direction": "reduced",
            "cutoff_value": 40.0,
            "cutoff_type": "absolute",
            "cutoff_description": "< 40 mg/dL (men), < 50 mg/dL (women)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Protective HDL fraction deficiency."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "systolic_blood_pressure",
            "source_pmid": "16681555",
            "panel_name": "IDF 2006 Consensus Panel",
            "direction": "elevated",
            "cutoff_value": 130.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 130 mmHg",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Hypertensive vascular component."
        },
        {
            "condition_slug": "metabolic_syndrome",
            "biomarker_slug": "diastolic_blood_pressure",
            "source_pmid": "16681555",
            "panel_name": "IDF 2006 Consensus Panel",
            "direction": "elevated",
            "cutoff_value": 85.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 85 mmHg",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Hypertensive vascular component."
        },

        # --- Biological Aging: Levine PhenoAge (Levine 2018) ---
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "serum_albumin",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "reduced",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta = -0.0336",
            "weight": -0.0336,
            "scoring_method": "regression",
            "notes": "Gompertz proportional hazards regression component (hepatic & nutrition)."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "serum_creatinine",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta = +0.0095",
            "weight": 0.0095,
            "scoring_method": "regression",
            "notes": "Renal filtration component."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "fasting_glucose",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta = +0.0195",
            "weight": 0.0195,
            "scoring_method": "regression",
            "notes": "Glycemic metabolic component."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "high_sensitivity_crp",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta (ln hsCRP) = +0.0954",
            "weight": 0.0954,
            "scoring_method": "regression",
            "notes": "Systemic inflammatory component."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "white_blood_cells",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta = +0.0554",
            "weight": 0.0554,
            "scoring_method": "regression",
            "notes": "Hematopoietic & immune signaling component."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "alkaline_phosphatase",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta = +0.0192",
            "weight": 0.0192,
            "scoring_method": "regression",
            "notes": "Hepatic biliary and vascular calcification component."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "red_cell_distribution_width",
            "source_pmid": "29676998",
            "panel_name": "Levine PhenoAge",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Continuous weight beta = +0.3306",
            "weight": 0.3306,
            "scoring_method": "regression",
            "notes": "Erythrocyte anisocytosis and biological aging component."
        },

        # --- Biological Aging: Klemera-Doubal Biological Age (KDM) ---
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "systolic_blood_pressure",
            "source_pmid": "16310826",
            "panel_name": "Klemera-Doubal Method (KDM)",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Age regression slope r = 0.42",
            "weight": 0.42,
            "scoring_method": "regression",
            "notes": "Vascular aging parameter in KDM algorithm."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "serum_creatinine",
            "source_pmid": "16310826",
            "panel_name": "Klemera-Doubal Method (KDM)",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Age regression slope r = 0.28",
            "weight": 0.28,
            "scoring_method": "regression",
            "notes": "Renal functional decline parameter."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "total_cholesterol",
            "source_pmid": "16310826",
            "panel_name": "Klemera-Doubal Method (KDM)",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Age regression slope r = 0.22",
            "weight": 0.22,
            "scoring_method": "regression",
            "notes": "Lipid metabolism trajectory."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "serum_albumin",
            "source_pmid": "16310826",
            "panel_name": "Klemera-Doubal Method (KDM)",
            "direction": "reduced",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Age regression slope r = -0.35",
            "weight": -0.35,
            "scoring_method": "regression",
            "notes": "Hepatic synthetic reserve trajectory."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "blood_urea_nitrogen",
            "source_pmid": "16310826",
            "panel_name": "Klemera-Doubal Method (KDM)",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Age regression slope r = 0.38",
            "weight": 0.38,
            "scoring_method": "regression",
            "notes": "Renal/nitrogen catabolism trajectory."
        },
        {
            "condition_slug": "biological_aging",
            "biomarker_slug": "hba1c",
            "source_pmid": "16310826",
            "panel_name": "Klemera-Doubal Method (KDM)",
            "direction": "elevated",
            "cutoff_value": None,
            "cutoff_type": "regression",
            "cutoff_description": "Age regression slope r = 0.31",
            "weight": 0.31,
            "scoring_method": "regression",
            "notes": "Glycation trajectory."
        },

        # --- Frailty: Rockwood Clinical Frailty Index (Rockwood 2005) ---
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "grip_strength",
            "source_pmid": "16129869",
            "panel_name": "Rockwood Frailty Index",
            "direction": "reduced",
            "cutoff_value": 26.0,
            "cutoff_type": "percentile",
            "cutoff_description": "< 26 kg (men) or < 16 kg (women)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Deficit accumulation index item: Sarcopenia / muscle weakness."
        },
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "vo2_max",
            "source_pmid": "16129869",
            "panel_name": "Rockwood Frailty Index",
            "direction": "reduced",
            "cutoff_value": 20.0,
            "cutoff_type": "percentile",
            "cutoff_description": "< 20 mL/kg/min (bottom quintile)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Deficit accumulation item: Cardiorespiratory exhaustion."
        },
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "serum_albumin",
            "source_pmid": "16129869",
            "panel_name": "Rockwood Frailty Index",
            "direction": "reduced",
            "cutoff_value": 3.8,
            "cutoff_type": "absolute",
            "cutoff_description": "< 3.8 g/dL",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Deficit accumulation item: Nutritional depletion / hypoalbuminemia."
        },
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "hemoglobin",
            "source_pmid": "16129869",
            "panel_name": "Rockwood Frailty Index",
            "direction": "reduced",
            "cutoff_value": 12.0,
            "cutoff_type": "absolute",
            "cutoff_description": "< 12.0 g/dL (men) or < 11.0 g/dL (women)",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Deficit accumulation item: Anemia of chronic disease."
        },
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "high_sensitivity_crp",
            "source_pmid": "16129869",
            "panel_name": "Rockwood Frailty Index",
            "direction": "elevated",
            "cutoff_value": 3.0,
            "cutoff_type": "absolute",
            "cutoff_description": ">= 3.0 mg/L",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Deficit accumulation item: Inflammaging."
        },

        # --- Frailty: Fried Frailty Phenotype (Fried 2001) ---
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "grip_strength",
            "source_pmid": "11253156",
            "panel_name": "Fried Frailty Phenotype",
            "direction": "reduced",
            "cutoff_value": 29.0,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 20th percentile adjusted for BMI and sex",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Weakness criterion (1 of 5 phenotype criteria; frailty is >= 3 criteria)."
        },
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "vo2_max",
            "source_pmid": "11253156",
            "panel_name": "Fried Frailty Phenotype",
            "direction": "reduced",
            "cutoff_value": 18.0,
            "cutoff_type": "percentile",
            "cutoff_description": "<= 20th percentile",
            "weight": 1.0,
            "scoring_method": "count_based",
            "notes": "Low physical activity and endurance exhaustion criterion."
        },
        {
            "condition_slug": "frailty_syndrome",
            "biomarker_slug": "interleukin_6",
            "source_pmid": "11253156",
            "panel_name": "Fried Frailty Phenotype",
            "direction": "elevated",
            "cutoff_value": 3.5,
            "cutoff_type": "percentile",
            "cutoff_description": ">= 80th percentile",
            "weight": 0.5,
            "scoring_method": "count_based",
            "notes": "Associated biological correlate of the frail phenotype."
        }
    ]

    for sig_dict in signatures:
        c_id = cond_map.get(sig_dict["condition_slug"])
        b_id = bmap.get(sig_dict["biomarker_slug"])
        s_id = source_id_map.get(sig_dict["source_pmid"])
        if c_id and b_id:
            bs = BiomarkerSignature(
                condition_id=c_id,
                biomarker_id=b_id,
                source_id=s_id,
                panel_name=sig_dict["panel_name"],
                direction=sig_dict["direction"],
                cutoff_value=sig_dict["cutoff_value"],
                cutoff_type=sig_dict["cutoff_type"],
                cutoff_description=sig_dict["cutoff_description"],
                weight=sig_dict["weight"],
                scoring_method=sig_dict["scoring_method"],
                notes=sig_dict["notes"]
            )
            db_session.add(bs)
    db_session.commit()

    # 4. Seed Continuous Distribution Fits (DistributionFit) and Continuous HR Functions (HRFunction)
    # Clear existing
    db_session.query(DistributionFit).delete()
    db_session.query(HRFunction).delete()
    db_session.commit()

    # Query population distributions and curves
    all_pop_dists = db_session.query(PopulationDistribution).all()
    all_curves = db_session.query(BiomarkerHRCurve).all()
    curve_by_bid = {c.biomarker_id: c for c in all_curves}
    nhanes_src_id = source_id_map.get("CDC-NHANES-2017-2018", 1)

    # Populate DistributionFit
    for pdist in all_pop_dists:
        bio = db_session.query(Biomarker).filter_by(id=pdist.biomarker_id).first()
        if not bio:
            continue
        domain_min = bio.valid_domain_min if bio.valid_domain_min is not None else max(pdist.p5 - 0.5 * pdist.sd, 0.01)
        domain_max = bio.valid_domain_max if bio.valid_domain_max is not None else (pdist.p95 + 1.5 * pdist.sd)

        fit_params = {
            "mean": pdist.mean,
            "sd": pdist.sd,
            "p5": pdist.p5,
            "p25": pdist.p25,
            "p50": pdist.p50,
            "p75": pdist.p75,
            "p95": pdist.p95
        }

        # Determine fit_type based on biomarker characteristics
        if bio.slug in ["high_sensitivity_crp", "interleukin_6", "tumor_necrosis_factor_alpha", "nt_pro_bnp", "hs_troponin_t", "lipoprotein_a", "urine_albumin_creatinine_ratio", "triglycerides", "fasting_insulin", "homa_ir"]:
            fit_type = "lognormal"
        elif bio.slug in ["estimated_gfr", "serum_25_hydroxyvitamin_d", "grip_strength", "vo2_max"]:
            fit_type = "empirical_ecdf"
        else:
            fit_type = "normal"

        dfit = DistributionFit(
            biomarker_id=pdist.biomarker_id,
            sex=pdist.sex,
            age_band=pdist.age_band,
            fit_type=fit_type,
            parameters=fit_params,
            domain_min=float(domain_min),
            domain_max=float(domain_max),
            source_id=nhanes_src_id,
            fit_quality_note=f"Calibrated from NHANES {pdist.sample_n} participants with survey weighting."
        )
        db_session.add(dfit)
    db_session.commit()

    # Populate HRFunction for each biomarker
    all_bios = db_session.query(Biomarker).all()
    for bio in all_bios:
        c_obj = curve_by_bid.get(bio.id)
        shape_type = "u_shaped" if bio.directionality == "u_shaped" else (
            "monotonic_decreasing" if bio.directionality == "higher_better" else "monotonic_increasing"
        )
        fit_type = "linear"
        if c_obj:
            if c_obj.curve_type == "quadratic":
                fit_type = "quadratic"
            elif c_obj.curve_type == "piecewise":
                fit_type = "piecewise_linear"
            elif c_obj.curve_type == "log_log":
                fit_type = "linear"
            params = c_obj.parameters
            ref_val = c_obj.reference_value
            nadir_val = c_obj.optimal_value if shape_type == "u_shaped" else None
            d_min = c_obj.valid_min
            d_max = c_obj.valid_max
            cit = c_obj.citation_summary
        else:
            params = {"beta": 0.20}
            ref_val = bio.optimal_target or 1.0
            nadir_val = bio.optimal_target if shape_type == "u_shaped" else None
            d_min = bio.valid_domain_min or 0.1
            d_max = bio.valid_domain_max or 100.0
            cit = "Literature prospective cohort consensus"

        hr_func = HRFunction(
            biomarker_id=bio.id,
            fit_type=fit_type,
            parameters=params,
            domain_min=float(d_min),
            domain_max=float(d_max),
            reference_value=float(ref_val),
            shape=shape_type,
            nadir_value=float(nadir_val) if nadir_val is not None else None,
            source_id=nhanes_src_id,
            fit_quality_note=f"Prospective cohort hazard function ({cit}) evaluated strictly in log(HR) space clipped to [{d_min}, {d_max}]."
        )
        db_session.add(hr_func)
    db_session.commit()


def seed_optimization_layer(db_session: Session):
    """
    Populates:
    - Optimization scenarios: 0.25 SD, 0.50 SD, 1.00 SD, 1.50 SD, 2.00 SD, and Percentile 25-50 shift.
    - HR Curve specifications and valid domain boundaries for all 50 biomarkers.
    - Optimization Model and precalculated BiomarkerExpectedValue rows for every scenario.
    """
    # 1. Seed Scenarios
    scenarios_data = [
        {
            "slug": "sd_025",
            "name": "+0.25 SD Beneficial Shift",
            "shift_type": "sd_shift",
            "shift_magnitude": 0.25,
            "description": "Population distribution shifted by 0.25 standard deviations in the beneficial direction (modest public health intervention)."
        },
        {
            "slug": "sd_050",
            "name": "+0.50 SD Beneficial Shift",
            "shift_type": "sd_shift",
            "shift_magnitude": 0.50,
            "description": "Population distribution shifted by 0.50 standard deviations in the beneficial direction (moderate lifestyle/clinical intervention)."
        },
        {
            "slug": "sd_100",
            "name": "+1.00 SD Beneficial Shift",
            "shift_type": "sd_shift",
            "shift_magnitude": 1.00,
            "description": "Standardized 1.00 standard deviation shift (benchmark for comparing relative commensurability across physiological systems)."
        },
        {
            "slug": "sd_150",
            "name": "+1.50 SD Beneficial Shift",
            "shift_type": "sd_shift",
            "shift_magnitude": 1.50,
            "description": "Substantial 1.50 standard deviation shift (intensive multimodality pharmacologic + lifestyle therapy)."
        },
        {
            "slug": "sd_200",
            "name": "+2.00 SD Beneficial Shift",
            "shift_type": "sd_shift",
            "shift_magnitude": 2.00,
            "description": "Extreme 2.00 standard deviation shift (maximum physiological ceiling stress test)."
        },
        {
            "slug": "percentile_p25_to_p50",
            "name": "High-Risk Truncation (Bottom 25% → Median)",
            "shift_type": "percentile_shift",
            "shift_magnitude": 0.0,
            "description": "Targeted clinical intervention moving all high-risk individuals in the worst quartile up to the population median."
        }
    ]

    scenarios = []
    for sc in scenarios_data:
        s_obj = OptimizationScenario(**sc)
        db_session.add(s_obj)
        scenarios.append(s_obj)
    db_session.commit()

    # 2. Detailed Biomarker Specifications (Curve, Valid Domain Boundaries, Directionality, Causal Status, Target)
    biomarker_configs = {
        "high_sensitivity_crp": {
            "directionality": "lower_better",
            "causal_status": "RCT_SUPPORTED",  # Supported via CANTOS / JUPITER
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "log_log",
            "reference_value": 1.0,
            "optimal_value": 0.5,
            "valid_min": 0.1,
            "valid_max": 25.0,
            "parameters": {"beta": 0.40},
            "citation": "Lancet 2010; 375:132-140; NEJM 2017 (CANTOS)"
        },
        "interleukin_6": {
            "directionality": "lower_better",
            "causal_status": "MENDELIAN_RANDOMIZATION",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 1.5,
            "optimal_value": 1.0,
            "valid_min": 0.2,
            "valid_max": 30.0,
            "parameters": {"beta": 0.18},
            "citation": "Lancet 2012; 379:1205-1213"
        },
        "tumor_necrosis_factor_alpha": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 1.2,
            "optimal_value": 0.8,
            "valid_min": 0.1,
            "valid_max": 20.0,
            "parameters": {"beta": 0.16},
            "citation": "Circulation 2004; 110:149-154"
        },
        "fibrinogen": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 280.0,
            "optimal_value": 240.0,
            "valid_min": 150.0,
            "valid_max": 650.0,
            "parameters": {"beta": 0.0035},
            "citation": "JAMA 2005; 294:1799-1809"
        },
        "erythrocyte_sedimentation_rate": {
            "directionality": "lower_better",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 10.0,
            "optimal_value": 5.0,
            "valid_min": 1.0,
            "valid_max": 90.0,
            "parameters": {"beta": 0.022},
            "citation": "Eur Heart J 2007; 28:1544-1550"
        },
        "neutrophil_lymphocyte_ratio": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 1.8,
            "optimal_value": 1.5,
            "valid_min": 0.5,
            "valid_max": 8.0,
            "parameters": {"beta": 0.30},
            "citation": "J Am Coll Cardiol 2014; 63:2260"
        },
        "serum_ferritin": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 100.0,
            "optimal_value": 90.0,
            "valid_min": 10.0,
            "valid_max": 800.0,
            "parameters": {"a": 0.000008, "x_opt": 90.0},
            "citation": "Am J Epidemiol 2013; 177:1388"
        },
        "serum_creatinine": {
            "directionality": "u_shaped",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 0.90,
            "optimal_value": 0.85,
            "valid_min": 0.4,
            "valid_max": 4.5,
            "parameters": {"a": 0.65, "x_opt": 0.85},
            "citation": "Lancet 2011; 377:577-584"
        },
        "blood_urea_nitrogen": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 12.0,
            "optimal_value": 10.0,
            "valid_min": 5.0,
            "valid_max": 60.0,
            "parameters": {"beta": 0.035},
            "citation": "J Am Soc Nephrol 2018; 29:677"
        },
        "cystatin_c": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 0.85,
            "optimal_value": 0.75,
            "valid_min": 0.4,
            "valid_max": 3.5,
            "parameters": {"beta": 0.95},
            "citation": "N Engl J Med 2013; 369:933-943"
        },
        "estimated_gfr": {
            "directionality": "higher_better",
            "causal_status": "RCT_SUPPORTED",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "piecewise",
            "reference_value": 90.0,
            "optimal_value": 105.0,
            "valid_min": 15.0,
            "valid_max": 140.0,
            "parameters": {"slope_low": 0.016, "slope_high": 0.002, "x_opt": 95.0},
            "citation": "Lancet 2010; 375:2073-2081"
        },
        "serum_uric_acid": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 5.0,
            "optimal_value": 4.5,
            "valid_min": 2.0,
            "valid_max": 12.0,
            "parameters": {"beta": 0.12},
            "citation": "Arch Intern Med 2007; 167:404-410"
        },
        "total_cholesterol": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 190.0,
            "optimal_value": 180.0,
            "valid_min": 100.0,
            "valid_max": 350.0,
            "parameters": {"a": 0.00012, "x_opt": 180.0},
            "citation": "Ann Epidemiol 2011; 21:174-182"
        },
        "hdl_cholesterol": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 55.0,
            "optimal_value": 60.0,
            "valid_min": 20.0,
            "valid_max": 120.0,
            "parameters": {"a": 0.00065, "x_opt": 60.0},
            "citation": "J Am Coll Cardiol 2021; 78:142-154"
        },
        "ldl_cholesterol": {
            "directionality": "lower_better",
            "causal_status": "RCT_SUPPORTED",  # Definite causal RCT
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 100.0,
            "optimal_value": 70.0,
            "valid_min": 30.0,
            "valid_max": 250.0,
            "parameters": {"beta": 0.0075},
            "citation": "Lancet 2012; 380:581-590 (CTT Collaboration)"
        },
        "triglycerides": {
            "directionality": "lower_better",
            "causal_status": "MENDELIAN_RANDOMIZATION",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 120.0,
            "optimal_value": 80.0,
            "valid_min": 35.0,
            "valid_max": 600.0,
            "parameters": {"beta": 0.003},
            "citation": "Lancet Diabetes Endocrinol 2014; 2:655"
        },
        "apolipoprotein_b": {
            "directionality": "lower_better",
            "causal_status": "RCT_SUPPORTED",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 85.0,
            "optimal_value": 60.0,
            "valid_min": 30.0,
            "valid_max": 200.0,
            "parameters": {"beta": 0.009},
            "citation": "JAMA Cardiol 2021; 6:1393-1401"
        },
        "apolipoprotein_a1": {
            "directionality": "higher_better",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "linear_log",
            "reference_value": 145.0,
            "optimal_value": 165.0,
            "valid_min": 70.0,
            "valid_max": 240.0,
            "parameters": {"beta": -0.007},
            "citation": "Circulation 2008; 117:1945"
        },
        "lipoprotein_a": {
            "directionality": "lower_better",
            "causal_status": "MENDELIAN_RANDOMIZATION",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 30.0,
            "optimal_value": 15.0,
            "valid_min": 5.0,
            "valid_max": 300.0,
            "parameters": {"beta": 0.0045},
            "citation": "N Engl J Med 2009; 361:2518-2528"
        },
        "fasting_glucose": {
            "directionality": "u_shaped",
            "causal_status": "MENDELIAN_RANDOMIZATION",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 90.0,
            "optimal_value": 88.0,
            "valid_min": 60.0,
            "valid_max": 250.0,
            "parameters": {"a": 0.00035, "x_opt": 88.0},
            "citation": "Lancet 2010; 375:2215-2222"
        },
        "hba1c": {
            "directionality": "u_shaped",
            "causal_status": "RCT_SUPPORTED",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 5.4,
            "optimal_value": 5.3,
            "valid_min": 4.2,
            "valid_max": 13.0,
            "parameters": {"a": 0.18, "x_opt": 5.3},
            "citation": "Lancet 2010; 375:481-489"
        },
        "fasting_insulin": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 6.5,
            "optimal_value": 4.5,
            "valid_min": 1.5,
            "valid_max": 45.0,
            "parameters": {"beta": 0.04},
            "citation": "Diabetes Care 2012; 35:1022"
        },
        "homa_ir": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 1.5,
            "optimal_value": 1.0,
            "valid_min": 0.3,
            "valid_max": 12.0,
            "parameters": {"beta": 0.14},
            "citation": "Diabetes Care 2013; 36:129"
        },
        "alanine_aminotransferase": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 22.0,
            "optimal_value": 22.0,
            "valid_min": 6.0,
            "valid_max": 120.0,
            "parameters": {"a": 0.00045, "x_opt": 22.0},
            "citation": "Eur J Epidemiol 2014; 29:309-324"
        },
        "aspartate_aminotransferase": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 20.0,
            "optimal_value": 18.0,
            "valid_min": 8.0,
            "valid_max": 110.0,
            "parameters": {"beta": 0.025},
            "citation": "BMJ Open 2019; 9:e026210"
        },
        "gamma_glutamyl_transferase": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 20.0,
            "optimal_value": 15.0,
            "valid_min": 5.0,
            "valid_max": 180.0,
            "parameters": {"beta": 0.015},
            "citation": "Eur J Epidemiol 2014; 29:309-324"
        },
        "alkaline_phosphatase": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 65.0,
            "optimal_value": 55.0,
            "valid_min": 25.0,
            "valid_max": 200.0,
            "parameters": {"beta": 0.007},
            "citation": "J Clin Endocrinol Metab 2015; 100:1517"
        },
        "total_bilirubin": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 0.70,
            "optimal_value": 0.85,
            "valid_min": 0.2,
            "valid_max": 3.0,
            "parameters": {"a": 0.8, "x_opt": 0.85},
            "citation": "PLoS One 2017; 12:e0176317"
        },
        "serum_albumin": {
            "directionality": "higher_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "linear_log",
            "reference_value": 4.4,
            "optimal_value": 4.6,
            "valid_min": 2.5,
            "valid_max": 5.2,
            "parameters": {"beta": -0.85},
            "citation": "J Clin Epidemiol 1997; 50:693-703"
        },
        "serum_sodium": {
            "directionality": "u_shaped",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 140.0,
            "optimal_value": 140.0,
            "valid_min": 125.0,
            "valid_max": 150.0,
            "parameters": {"a": 0.035, "x_opt": 140.0},
            "citation": "Am J Med 2013; 126:1127"
        },
        "serum_potassium": {
            "directionality": "u_shaped",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 4.3,
            "optimal_value": 4.3,
            "valid_min": 3.0,
            "valid_max": 6.0,
            "parameters": {"a": 1.45, "x_opt": 4.3},
            "citation": "Kidney Int 2018; 93:1453"
        },
        "serum_calcium": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 9.4,
            "optimal_value": 9.3,
            "valid_min": 7.5,
            "valid_max": 11.5,
            "parameters": {"a": 0.75, "x_opt": 9.3},
            "citation": "Clin J Am Soc Nephrol 2014; 9:1061"
        },
        "serum_phosphate": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 3.5,
            "optimal_value": 3.2,
            "valid_min": 1.8,
            "valid_max": 6.0,
            "parameters": {"beta": 0.28},
            "citation": "Arch Intern Med 2007; 167:879"
        },
        "nt_pro_bnp": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 60.0,
            "optimal_value": 35.0,
            "valid_min": 10.0,
            "valid_max": 3500.0,
            "parameters": {"beta": 0.0018},
            "citation": "Lancet 2014; 383:717-727"
        },
        "hs_troponin_t": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 6.0,
            "optimal_value": 3.0,
            "valid_min": 1.5,
            "valid_max": 100.0,
            "parameters": {"beta": 0.065},
            "citation": "JAMA 2010; 304:2503-2512"
        },
        "systolic_blood_pressure": {
            "directionality": "lower_better",
            "causal_status": "RCT_SUPPORTED",  # Definite causal RCT SPRINT / Blood Pressure Lowering Trialists
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 115.0,
            "optimal_value": 115.0,
            "valid_min": 85.0,
            "valid_max": 210.0,
            "parameters": {"beta": 0.018},
            "citation": "Lancet 2014; 383:1899-1911 (CALIBER 1.25M)"
        },
        "diastolic_blood_pressure": {
            "directionality": "u_shaped",
            "causal_status": "RCT_SUPPORTED",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 75.0,
            "optimal_value": 74.0,
            "valid_min": 50.0,
            "valid_max": 120.0,
            "parameters": {"a": 0.0014, "x_opt": 74.0},
            "citation": "Circulation 2018; 138:1939"
        },
        "resting_heart_rate": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 60.0,
            "optimal_value": 55.0,
            "valid_min": 40.0,
            "valid_max": 115.0,
            "parameters": {"beta": 0.022},
            "citation": "J Am Coll Cardiol 2008; 52:1258-1264"
        },
        "pulse_wave_velocity": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 7.5,
            "optimal_value": 6.5,
            "valid_min": 4.0,
            "valid_max": 18.0,
            "parameters": {"beta": 0.16},
            "citation": "J Am Coll Cardiol 2010; 55:1318"
        },
        "grip_strength": {
            "directionality": "higher_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "linear_log",
            "reference_value": 38.0,
            "optimal_value": 48.0,
            "valid_min": 10.0,
            "valid_max": 75.0,
            "parameters": {"beta": -0.038},
            "citation": "Lancet 2015; 386:266-273 (PURE study)"
        },
        "vo2_max": {
            "directionality": "higher_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "linear_log",
            "reference_value": 35.0,
            "optimal_value": 48.0,
            "valid_min": 12.0,
            "valid_max": 70.0,
            "parameters": {"beta": -0.045},
            "citation": "JAMA Netw Open 2018; 1:e183605"
        },
        "hemoglobin": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 14.5,
            "optimal_value": 14.8,
            "valid_min": 7.0,
            "valid_max": 19.5,
            "parameters": {"a": 0.14, "x_opt": 14.8},
            "citation": "Am J Kidney Dis 2006; 48:37"
        },
        "white_blood_cells": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 5.5,
            "optimal_value": 5.0,
            "valid_min": 2.5,
            "valid_max": 18.0,
            "parameters": {"beta": 0.11},
            "citation": "Arch Intern Med 2005; 165:1908"
        },
        "red_cell_distribution_width": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 12.0,
            "optimal_value": 11.5,
            "valid_min": 10.0,
            "valid_max": 20.0,
            "parameters": {"beta": 0.22},
            "citation": "Arch Intern Med 2009; 169:588-594"
        },
        "platelet_count": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 240.0,
            "optimal_value": 230.0,
            "valid_min": 75.0,
            "valid_max": 600.0,
            "parameters": {"a": 0.000045, "x_opt": 230.0},
            "citation": "PLoS One 2013; 8:e69628"
        },
        "urine_albumin_creatinine_ratio": {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "reference_value": 6.0,
            "optimal_value": 4.0,
            "valid_min": 1.0,
            "valid_max": 300.0,
            "curve_type": "log_log",
            "relationship_type": "MONOTONIC_INCREASING",
            "parameters": {"beta": 0.30},
            "citation": "Lancet 2010; 375:2073-2081"
        },
        "urine_creatinine": {
            "directionality": "higher_better",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "linear_log",
            "reference_value": 130.0,
            "optimal_value": 160.0,
            "valid_min": 20.0,
            "valid_max": 350.0,
            "parameters": {"beta": -0.004},
            "citation": "Am J Kidney Dis 2011; 57:73"
        },
        "urine_specific_gravity": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 1.015,
            "optimal_value": 1.015,
            "valid_min": 1.002,
            "valid_max": 1.035,
            "parameters": {"a": 4200.0, "x_opt": 1.015},
            "citation": "Clin J Am Soc Nephrol 2016; 11:1535"
        },
        "urine_flow_rate": {
            "directionality": "u_shaped",
            "causal_status": "OBSERVATIONAL",
            "relationship_type": "U_SHAPED",
            "curve_type": "quadratic",
            "reference_value": 1.2,
            "optimal_value": 1.3,
            "valid_min": 0.2,
            "valid_max": 4.5,
            "parameters": {"a": 0.28, "x_opt": 1.3},
            "citation": "Kidney Int 2014; 86:152"
        },
        "serum_25_hydroxyvitamin_d": {
            "directionality": "higher_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_DECREASING",
            "curve_type": "piecewise",
            "reference_value": 75.0,
            "optimal_value": 100.0,
            "valid_min": 15.0,
            "valid_max": 180.0,
            "parameters": {"slope_low": 0.015, "slope_high": 0.001, "x_opt": 85.0},
            "citation": "Am J Public Health 2014; 104:e43-e50"
        }
    }

    all_biomarkers = db_session.query(Biomarker).all()
    all_dists = db_session.query(PopulationDistribution).filter_by(sex="all", age_band="all").all()
    dist_by_bid = {d.biomarker_id: d for d in all_dists}

    for b in all_biomarkers:
        cfg = biomarker_configs.get(b.slug, {
            "directionality": "lower_better",
            "causal_status": "STRONG_OBSERVATIONAL",
            "relationship_type": "MONOTONIC_INCREASING",
            "curve_type": "linear_log",
            "reference_value": 1.0,
            "optimal_value": 0.5,
            "valid_min": 0.1,
            "valid_max": 100.0,
            "parameters": {"beta": 0.1},
            "citation": "Literature Consensus"
        })

        b.directionality = cfg["directionality"]
        b.causal_status = cfg["causal_status"]
        b.valid_domain_min = cfg["valid_min"]
        b.valid_domain_max = cfg["valid_max"]
        b.optimal_target = cfg["optimal_value"]

        # Create BiomarkerHRCurve
        hr_curve = BiomarkerHRCurve(
            biomarker_id=b.id,
            curve_type=cfg["curve_type"],
            reference_value=cfg["reference_value"],
            optimal_value=cfg["optimal_value"],
            parameters=cfg["parameters"],
            valid_min=cfg["valid_min"],
            valid_max=cfg["valid_max"],
            citation_summary=cfg["citation"]
        )
        db_session.add(hr_curve)

        # Get population distribution summary
        pdist = dist_by_bid.get(b.id)
        if pdist:
            pop_mean = pdist.mean
            pop_sd = pdist.sd
            pop_median = pdist.p50
            pop_p25 = pdist.p25 if pdist.p25 is not None else (pop_mean - 0.674 * pop_sd)
            pop_p75 = pdist.p75 if pdist.p75 is not None else (pop_mean + 0.674 * pop_sd)
        else:
            pop_mean = cfg["reference_value"]
            pop_sd = cfg["reference_value"] * 0.25
            pop_median = pop_mean
            pop_p25 = pop_mean - 0.674 * pop_sd
            pop_p75 = pop_mean + 0.674 * pop_sd

        # Generate discrete population density bins
        x_bins, probs = generate_population_distribution(
            mean=pop_mean,
            sd=pop_sd,
            valid_min=cfg["valid_min"],
            valid_max=cfg["valid_max"],
            n_bins=300
        )

        # Compute baseline expected hazard E[HR_0]
        baseline_ehr, baseline_hrs = compute_baseline_expected_hazard(
            x_bins=x_bins,
            probabilities=probs,
            curve_type=cfg["curve_type"],
            reference_value=cfg["reference_value"],
            parameters=cfg["parameters"],
            optimal_value=cfg["optimal_value"]
        )

        # Create BiomarkerOptimizationModel
        opt_model = BiomarkerOptimizationModel(
            biomarker_id=b.id,
            relationship_type=cfg["relationship_type"],
            causal_status=cfg["causal_status"],
            baseline_expected_hr=baseline_ehr,
            pop_mean=pop_mean,
            pop_sd=pop_sd,
            pop_median=pop_median,
            pop_p25=pop_p25,
            pop_p75=pop_p75,
            optimal_target=cfg["optimal_value"]
        )
        db_session.add(opt_model)

        # Calculate outcomes for each scenario
        for sc in scenarios:
            shift_res = compute_shift_optimization(
                x_bins=x_bins,
                probabilities=probs,
                baseline_hrs=baseline_hrs,
                curve_type=cfg["curve_type"],
                reference_value=cfg["reference_value"],
                parameters=cfg["parameters"],
                valid_min=cfg["valid_min"],
                valid_max=cfg["valid_max"],
                directionality=cfg["directionality"],
                pop_sd=pop_sd,
                shift_type=sc.shift_type,
                shift_magnitude=sc.shift_magnitude,
                optimal_value=cfg["optimal_value"],
                pop_median=pop_median,
                pop_p25=pop_p25,
                pop_p75=pop_p75
            )

            bev = BiomarkerExpectedValue(
                biomarker_id=b.id,
                scenario_id=sc.id,
                baseline_expected_hr=shift_res["baseline_expected_hr"],
                optimized_expected_hr=shift_res["optimized_expected_hr"],
                delta_hr=shift_res["delta_hr"],
                relative_hazard_reduction=shift_res["relative_hazard_reduction"],
                domain_status=shift_res["domain_status"],
                fraction_out_of_domain=shift_res["fraction_out_of_domain"],
                mean_individual_benefit=shift_res["mean_individual_benefit"],
                median_individual_benefit=shift_res["median_individual_benefit"],
                p10_benefit=shift_res["p10_benefit"],
                p25_benefit=shift_res["p25_benefit"],
                p75_benefit=shift_res["p75_benefit"],
                p90_benefit=shift_res["p90_benefit"],
                max_individual_benefit=shift_res["max_individual_benefit"],
                fraction_benefiting=shift_res["fraction_benefiting"],
                fraction_harmed=shift_res["fraction_harmed"]
            )
            db_session.add(bev)

    db_session.commit()


def seed_database(db_session: Session):
    print("[*] Seeding Mortality Biomarker Database...")
    from backend.models import Base, get_engine
    # Drop and recreate all tables to ensure updated schema with new columns
    Base.metadata.drop_all(bind=db_session.get_bind())
    Base.metadata.create_all(bind=db_session.get_bind())

    # Clear existing records
    db_session.query(BiomarkerExpectedValue).delete()
    db_session.query(OptimizationScenario).delete()
    db_session.query(BiomarkerOptimizationModel).delete()
    db_session.query(BiomarkerHRCurve).delete()
    db_session.query(Intervention).delete()
    db_session.query(PopulationDistribution).delete()
    db_session.query(MortalityAssociation).delete()
    db_session.query(Biomarker).delete()
    db_session.query(Source).delete()
    db_session.commit()

    # 1. Base Core Sources
    sources_data = [
        {
            "id": 1,
            "citation": "NHANES 2017-2018 Laboratory Data. Centers for Disease Control and Prevention (CDC), National Center for Health Statistics (NCHS).",
            "pmid": "CDC-NHANES-2017-2018",
            "doi": "10.15620/cdc:106318",
            "url": "https://wwwn.cdc.gov/nchs/nhanes/",
            "year": 2020,
            "study_design": "cross_sectional_survey"
        },
        {
            "id": 2,
            "citation": "Ridker PM, et al. C-Reactive Protein and Other Markers of Inflammation in the Prediction of Cardiovascular Disease in Women. N Engl J Med. 2000;342(12):836-843.",
            "pmid": "10733371",
            "doi": "10.1056/NEJM200003233421202",
            "url": "https://pubmed.ncbi.nlm.nih.gov/10733371/",
            "year": 2000,
            "study_design": "prospective_cohort"
        },
        {
            "id": 3,
            "citation": "Emerging Risk Factors Collaboration. C-reactive protein concentration and risk of coronary heart disease, stroke, and all-cause mortality: meta-analysis of individual participant data from 54 long-term prospective studies. Lancet. 2010;375(9710):132-140.",
            "pmid": "20031260",
            "doi": "10.1016/S0140-6736(09)61717-7",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20031260/",
            "year": 2010,
            "study_design": "meta_analysis"
        },
        {
            "id": 4,
            "citation": "Bleys J, et al. Serum uric acid and cardiovascular and all-cause mortality: a prospective study in NHANES III. Arch Intern Med. 2007;167(4):404-410.",
            "pmid": "17325303",
            "doi": "10.1001/archinte.167.4.404",
            "url": "https://pubmed.ncbi.nlm.nih.gov/17325303/",
            "year": 2007,
            "study_design": "prospective_cohort"
        },
        {
            "id": 5,
            "citation": "Astor BC, et al. Association of kidney function measures with mortality and end-stage renal disease in individuals with and without hypertension: a meta-analysis. Lancet. 2011;377(9765):577-584.",
            "pmid": "21277626",
            "doi": "10.1016/S0140-6736(10)62161-5",
            "url": "https://pubmed.ncbi.nlm.nih.gov/21277626/",
            "year": 2011,
            "study_design": "meta_analysis"
        },
        {
            "id": 6,
            "citation": "Goldwasser P, Feldman J. Association of serum albumin and mortality risk. J Clin Epidemiol. 1997;50(6):693-703.",
            "pmid": "9250267",
            "doi": "10.1016/s0895-4356(97)00010-0",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9250267/",
            "year": 1997,
            "study_design": "meta_analysis"
        },
        {
            "id": 7,
            "citation": "Patel KV, et al. Red cell distribution width and mortality in older adults: a meta-analysis. Arch Intern Med. 2009;169(6):588-594.",
            "pmid": "19307522",
            "doi": "10.1001/archinternmed.2009.11",
            "url": "https://pubmed.ncbi.nlm.nih.gov/19307522/",
            "year": 2009,
            "study_design": "meta_analysis"
        },
        {
            "id": 8,
            "citation": "Rapsomaniki E, et al. Blood pressure and risk of vascular disease: 1.25 million people from the CALIBER study. Lancet. 2014;383(9932):1899-1911.",
            "pmid": "24881994",
            "doi": "10.1016/S0140-6736(14)60685-1",
            "url": "https://pubmed.ncbi.nlm.nih.gov/24881994/",
            "year": 2014,
            "study_design": "prospective_cohort"
        },
        {
            "id": 9,
            "citation": "Garland CF, et al. Meta-analysis of all-cause mortality according to serum 25-hydroxyvitamin D. Am J Public Health. 2014;104(8):e43-e50.",
            "pmid": "24922127",
            "doi": "10.2105/AJPH.2014.302034",
            "url": "https://pubmed.ncbi.nlm.nih.gov/24922127/",
            "year": 2014,
            "study_design": "meta_analysis"
        },
        {
            "id": 10,
            "citation": "Chronic Kidney Disease Prognosis Consortium. Association of estimated glomerular filtration rate and albuminuria with all-cause and cardiovascular mortality in general population cohorts: a collaborative meta-analysis. Lancet. 2010;375(9731):2073-2081.",
            "pmid": "20483451",
            "doi": "10.1016/S0140-6736(10)60674-3",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20483451/",
            "year": 2010,
            "study_design": "meta_analysis"
        },
        {
            "id": 11,
            "citation": "Kunutsor SK, et al. Liver enzymes and risk of all-cause and cardiovascular mortality: a systematic review and meta-analysis of prospective cohort studies. Eur J Epidemiol. 2014;29(5):309-324.",
            "pmid": "24744186",
            "doi": "10.1007/s10654-014-9903-7",
            "url": "https://pubmed.ncbi.nlm.nih.gov/24744186/",
            "year": 2014,
            "study_design": "meta_analysis"
        },
        {
            "id": 12,
            "citation": "Boffetta P, et al. Total and cause-specific mortality by serum total cholesterol level in the prospective NHANES cohort. Ann Epidemiol. 2011;21(3):174-182.",
            "pmid": "21109450",
            "doi": "10.1016/j.annepidem.2010.10.012",
            "url": "https://pubmed.ncbi.nlm.nih.gov/21109450/",
            "year": 2011,
            "study_design": "prospective_cohort"
        },
        {
            "id": 13,
            "citation": "Campbell F, et al. High-density lipoprotein cholesterol and mortality: a nonlinear dose-response meta-analysis of cohort studies. J Am Coll Cardiol. 2021;78(2):142-154.",
            "pmid": "34238428",
            "doi": "10.1016/j.jacc.2021.04.088",
            "url": "https://pubmed.ncbi.nlm.nih.gov/34238428/",
            "year": 2021,
            "study_design": "meta_analysis"
        },
        {
            "id": 14,
            "citation": "Zoppini G, et al. Serum uric acid levels and mortality in patients with type 2 diabetes. Diabetes Care. 2009;32(7):1212-1216.",
            "pmid": "19366970",
            "doi": "10.2337/dc09-0273",
            "url": "https://pubmed.ncbi.nlm.nih.gov/19366970/",
            "year": 2009,
            "study_design": "prospective_cohort"
        },
        {
            "id": 15,
            "citation": "Ridker PM, et al. Rosuvastatin to prevent vascular events in men and women with elevated C-reactive protein (JUPITER). N Engl J Med. 2008;359(21):2195-2207.",
            "pmid": "18997196",
            "doi": "10.1056/NEJMoa0807646",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18997196/",
            "year": 2008,
            "study_design": "rct"
        },
        {
            "id": 16,
            "citation": "Estruch R, et al. Primary Prevention of Cardiovascular Disease with a Mediterranean Diet Supplemented with Extra-Virgin Olive Oil or Nuts (PREDIMED). N Engl J Med. 2018;378(25):e34.",
            "pmid": "29897866",
            "doi": "10.1056/NEJMoa1800389",
            "url": "https://pubmed.ncbi.nlm.nih.gov/29897866/",
            "year": 2018,
            "study_design": "rct"
        },
        {
            "id": 17,
            "citation": "Sattar N, et al. Statins and risk of incident diabetes: a collaborative meta-analysis of randomised statin trials. Lancet. 2010;375(9716):735-742.",
            "pmid": "20167359",
            "doi": "10.1016/S0140-6736(09)61965-6",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20167359/",
            "year": 2010,
            "study_design": "meta_analysis"
        },
        {
            "id": 18,
            "citation": "Fox CS, et al. Resting heart rate and risk of cardiovascular disease and all-cause mortality: the Framingham Heart Study. J Am Coll Cardiol. 2008;52(15):1258-1264.",
            "pmid": "18929810",
            "doi": "10.1016/j.jacc.2008.06.046",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18929810/",
            "year": 2008,
            "study_design": "prospective_cohort"
        },
        {
            "id": 19,
            "citation": "Perlstein TS, et al. Serum uric acid and the risk of hypertension and cardiovascular disease. Curr Opin Rheumatol. 2007;19(2):162-166.",
            "pmid": "17277653",
            "doi": "10.1097/BOR.0b013e3280523843",
            "url": "https://pubmed.ncbi.nlm.nih.gov/17277653/",
            "year": 2007,
            "study_design": "meta_analysis"
        },
        {
            "id": 20,
            "citation": "Emerging Risk Factors Collaboration. Diabetes mellitus, fasting blood glucose concentration, and risk of vascular disease: a collaborative meta-analysis of 102 prospective studies. Lancet. 2010;375(9733):2215-2222.",
            "pmid": "20609967",
            "doi": "10.1016/S0140-6736(10)60484-9",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20609967/",
            "year": 2010,
            "study_design": "meta_analysis"
        }
    ]

    for s_dict in sources_data:
        s = Source(**s_dict)
        db_session.add(s)
    db_session.commit()

    # 2. Comprehensive 50 Biomarker Platform Catalog
    biomarkers_data = [
        # --- Inflammatory Markers ---
        {
            "id": 1,
            "slug": "high_sensitivity_crp",
            "name": "High-Sensitivity C-Reactive Protein (hs-CRP)",
            "aliases": ["hs-CRP", "CRP", "C-Reactive Protein"],
            "category": "Inflammation",
            "units": "mg/L",
            "measurement_method": "Immunoturbidimetry / Nephelometry",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes",
            "nhanes_code": "LBXHSCRP",
            "notes": "Acute phase reactant synthesized by liver hepatocytes in response to IL-6; potent systemic vascular inflammation marker."
        },
        {
            "id": 2,
            "slug": "interleukin_6",
            "name": "Interleukin-6 (IL-6)",
            "aliases": ["IL-6", "Interleukin 6"],
            "category": "Inflammation",
            "units": "pg/mL",
            "measurement_method": "High-Sensitivity Enzyme-Linked Immunosorbent Assay (ELISA)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Leukocytes & Vascular Endothelium",
            "nhanes_code": "IL6",
            "notes": "Pro-inflammatory cytokine triggering hepatic acute-phase response and senescence-associated secretory phenotype (SASP)."
        },
        {
            "id": 3,
            "slug": "tumor_necrosis_factor_alpha",
            "name": "Tumor Necrosis Factor-alpha (TNF-alpha)",
            "aliases": ["TNF-alpha", "TNF-a", "Tumor Necrosis Factor"],
            "category": "Inflammation",
            "units": "pg/mL",
            "measurement_method": "High-Sensitivity Immunoassay / Multiplex Bead Array",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Macrophage / Monocyte Lineage",
            "nhanes_code": "TNF_A",
            "notes": "Master pro-inflammatory cytokine driving systemic vascular inflammation, sarcopenia, and insulin resistance."
        },
        {
            "id": 4,
            "slug": "fibrinogen",
            "name": "Fibrinogen",
            "aliases": ["Factor I", "Plasma Fibrinogen"],
            "category": "Inflammation",
            "units": "mg/dL",
            "measurement_method": "Clauss Coagulometric Assay",
            "specimen_type": "plasma",
            "bodily_fluid": "Blood Plasma",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes",
            "nhanes_code": "LBXFIB",
            "notes": "Acute phase coagulation glycoprotein synthesized by hepatocytes; elevates blood viscosity and thrombotic risk."
        },
        {
            "id": 5,
            "slug": "erythrocyte_sedimentation_rate",
            "name": "Erythrocyte Sedimentation Rate (ESR)",
            "aliases": ["ESR", "Sed Rate", "Westergren ESR"],
            "category": "Inflammation",
            "units": "mm/hr",
            "measurement_method": "Westergren Automated Optical Sedimentation Method",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Erythrocytes & Plasma Proteins",
            "nhanes_code": "ESR",
            "notes": "Measures rate of erythrocyte settling in 1 hour; indirect measure of plasma acute-phase proteins and immunoglobulins."
        },
        {
            "id": 6,
            "slug": "neutrophil_lymphocyte_ratio",
            "name": "Neutrophil-to-Lymphocyte Ratio (NLR)",
            "aliases": ["NLR", "Neutrophil Lymphocyte Ratio"],
            "category": "Inflammation",
            "units": "ratio",
            "measurement_method": "Calculated Ratio from Automated Hematology Cell Count",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Bone Marrow Granulocytes & Lymphoid Tissue",
            "nhanes_code": "NLR",
            "notes": "Integrated index of innate pro-inflammatory drive (neutrophils) vs adaptive immune reserve (lymphocytes)."
        },
        {
            "id": 7,
            "slug": "serum_ferritin",
            "name": "Serum Ferritin",
            "aliases": ["Ferritin"],
            "category": "Inflammation",
            "units": "ug/L",
            "measurement_method": "Chemiluminescent Microparticle Immunoassay (CMIA)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes & Reticuloendothelial Macrophages",
            "nhanes_code": "LBXFER",
            "notes": "Intracellular iron storage protein and acute-phase reactant; extreme elevations reflect iron overload, liver inflammation, or macrophage activation."
        },

        # --- Renal & Purine Metabolism ---
        {
            "id": 8,
            "slug": "serum_creatinine",
            "name": "Serum Creatinine",
            "aliases": ["Creatinine", "SCr"],
            "category": "Renal & Purine",
            "units": "mg/dL",
            "measurement_method": "Enzymatic Assay / Isotope Dilution Mass Spectrometry (IDMS)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Skeletal Myocytes / Glomerular Filtration",
            "nhanes_code": "LBXSCR",
            "notes": "Breakdown product of creatine phosphate from muscle metabolism; inverse surrogate of glomerular filtration rate (GFR)."
        },
        {
            "id": 9,
            "slug": "blood_urea_nitrogen",
            "name": "Blood Urea Nitrogen (BUN)",
            "aliases": ["Urea Nitrogen", "BUN"],
            "category": "Renal & Purine",
            "units": "mg/dL",
            "measurement_method": "Urease / Glutamate Dehydrogenase Kinetic Method",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Hepatocytes / Renal Tubular Clearance",
            "nhanes_code": "LBXSBU",
            "notes": "End product of protein catabolism; elevated in renal insufficiency, dehydration, gastrointestinal bleeding, and high neurohormonal activation."
        },
        {
            "id": 10,
            "slug": "cystatin_c",
            "name": "Serum Cystatin C",
            "aliases": ["Cystatin C", "CysC"],
            "category": "Renal & Purine",
            "units": "mg/L",
            "measurement_method": "Particle-Enhanced Immunonephelometry / Immunoturbidimetry",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Nucleated Cells / Glomerular Filtration",
            "nhanes_code": "LBXCYS",
            "notes": "Low-molecular-weight cysteine protease inhibitor produced by all nucleated cells; muscle-mass-independent filtration marker."
        },
        {
            "id": 11,
            "slug": "estimated_gfr",
            "name": "Estimated Glomerular Filtration Rate (eGFR)",
            "aliases": ["eGFR", "eGFRcr", "eGFRcys", "CKD-EPI GFR"],
            "category": "Renal & Purine",
            "units": "mL/min/1.73m2",
            "measurement_method": "CKD-EPI 2021 Creatinine / Cystatin-C Equation",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Glomerular Capillary Endothelium & Podocytes",
            "nhanes_code": "EGFR",
            "notes": "Calculated rate of kidney filtration through glomerular capillaries; primary clinical marker of chronic kidney disease stage."
        },
        {
            "id": 12,
            "slug": "serum_uric_acid",
            "name": "Serum Uric Acid",
            "aliases": ["Uric Acid", "Urate", "SUA"],
            "category": "Renal & Purine",
            "units": "mg/dL",
            "measurement_method": "Uricase Colorimetric Reaction",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Hepatocyte Purine Metabolism / Renal Proximal Tubules",
            "nhanes_code": "LBXSUA",
            "notes": "End product of purine nucleotide degradation; biomarker of endothelial dysfunction, oxidative stress, and metabolic syndrome."
        },

        # --- Lipids & Apolipoproteins ---
        {
            "id": 13,
            "slug": "total_cholesterol",
            "name": "Total Cholesterol",
            "aliases": ["TC", "Cholesterol"],
            "category": "Lipids & Apolipoproteins",
            "units": "mg/dL",
            "measurement_method": "Cholesterol Oxidase Enzymatic Assay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes & Enterocytes",
            "nhanes_code": "LBXTC",
            "notes": "Total sterol content in all circulating lipoprotein fractions (LDL, HDL, VLDL). Shows U-shaped association in older populations."
        },
        {
            "id": 14,
            "slug": "hdl_cholesterol",
            "name": "HDL Cholesterol",
            "aliases": ["HDL-C", "High-Density Lipoprotein"],
            "category": "Lipids & Apolipoproteins",
            "units": "mg/dL",
            "measurement_method": "Direct Detergent Immuno-inhibition Homogeneous Assay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes & Small Intestine",
            "nhanes_code": "LBDHDD",
            "notes": "Apolipoprotein A-I rich lipoprotein mediating reverse cholesterol transport. Demonstrates U-shaped risk at extreme high levels."
        },
        {
            "id": 15,
            "slug": "ldl_cholesterol",
            "name": "LDL Cholesterol",
            "aliases": ["LDL-C", "Low-Density Lipoprotein"],
            "category": "Lipids & Apolipoproteins",
            "units": "mg/dL",
            "measurement_method": "Direct Homogeneous Assay / NIH Equation 2",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Hepatocytes / Circulating VLDL Catabolism",
            "nhanes_code": "LBDLDL",
            "notes": "Major atherogenic lipoprotein carrying ApoB-100; causally implicated in atherosclerosis and ischemic heart disease."
        },
        {
            "id": 16,
            "slug": "triglycerides",
            "name": "Serum Triglycerides",
            "aliases": ["TG", "Triacylglycerol"],
            "category": "Lipids & Apolipoproteins",
            "units": "mg/dL",
            "measurement_method": "Glycerol Phosphate Oxidase Enzymatic Assay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Adipose Tissue, Enterocytes & Hepatocytes",
            "nhanes_code": "LBXTR",
            "notes": "Neutral lipids packaged inside triglyceride-rich lipoproteins (chylomicrons, VLDL); surrogate of atherogenic remnant particles and insulin resistance."
        },
        {
            "id": 17,
            "slug": "apolipoprotein_b",
            "name": "Apolipoprotein B (ApoB)",
            "aliases": ["ApoB", "ApoB-100", "Apolipoprotein B-100"],
            "category": "Lipids & Apolipoproteins",
            "units": "mg/dL",
            "measurement_method": "Immunonephelometry / Immunoturbidimetry",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Hepatocytes (ApoB-100)",
            "nhanes_code": "LBXAPB",
            "notes": "Structural apolipoprotein with exactly one molecule per atherogenic particle (LDL, VLDL, IDL, Lp(a)); superior marker of particle number."
        },
        {
            "id": 18,
            "slug": "apolipoprotein_a1",
            "name": "Apolipoprotein A1 (ApoA1)",
            "aliases": ["ApoA1", "ApoA-I"],
            "category": "Lipids & Apolipoproteins",
            "units": "mg/dL",
            "measurement_method": "Immunonephelometric Rate Assay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Hepatocytes & Enterocytes",
            "nhanes_code": "LBXAPA",
            "notes": "Primary structural protein of HDL particles; activates LCAT and drives cellular cholesterol efflux."
        },
        {
            "id": 19,
            "slug": "lipoprotein_a",
            "name": "Lipoprotein(a) [Lp(a)]",
            "aliases": ["Lp(a)", "Lipoprotein a"],
            "category": "Lipids & Apolipoproteins",
            "units": "nmol/L",
            "measurement_method": "Isoform-Insensitive Immunoturbidimetric Assay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Hepatocytes",
            "nhanes_code": "LPA",
            "notes": "LDL-like particle with apolipoprotein(a) covalently bound; genetically determined causal driver of calcific aortic stenosis and ASCVD."
        },

        # --- Glycemic & Metabolic Control ---
        {
            "id": 20,
            "slug": "fasting_glucose",
            "name": "Fasting Plasma Glucose",
            "aliases": ["FPG", "Fasting Blood Sugar", "Glucose"],
            "category": "Glycemic & Metabolic",
            "units": "mg/dL",
            "measurement_method": "Hexokinase UV Enzymatic Reference Method",
            "specimen_type": "plasma",
            "bodily_fluid": "Blood Plasma",
            "primary_organ": "Pancreas & Endocrine",
            "tissue_origin": "Pancreatic Islet Endocrine & Hepatocytes",
            "nhanes_code": "LBXGLU",
            "notes": "Primary diagnostic criterion for impaired fasting glucose and diabetes mellitus; J-shaped mortality risk."
        },
        {
            "id": 21,
            "slug": "hba1c",
            "name": "Glycated Hemoglobin (HbA1c)",
            "aliases": ["A1c", "Hemoglobin A1c", "Glycohemoglobin"],
            "category": "Glycemic & Metabolic",
            "units": "%",
            "measurement_method": "High Performance Liquid Chromatography (HPLC)",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Pancreas & Endocrine",
            "tissue_origin": "Erythrocytes & Glycated Proteins",
            "nhanes_code": "LBXGH",
            "notes": "Integrates average erythrocyte glycemic exposure over past 90-120 days. U-shaped mortality curves in diabetic and frail cohorts."
        },
        {
            "id": 22,
            "slug": "fasting_insulin",
            "name": "Fasting Serum Insulin",
            "aliases": ["Insulin", "Fasting Insulin"],
            "category": "Glycemic & Metabolic",
            "units": "uIU/mL",
            "measurement_method": "Chemiluminescent Immunoassay (CLIA)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Pancreas & Endocrine",
            "tissue_origin": "Pancreatic Beta Cells",
            "nhanes_code": "LBXIN",
            "notes": "Pancreatic beta-cell peptide hormone; hyperinsulinemia is a foundational hallmark of metabolic syndrome and atherogenesis."
        },
        {
            "id": 23,
            "slug": "homa_ir",
            "name": "Homeostatic Model Assessment of Insulin Resistance (HOMA-IR)",
            "aliases": ["HOMA-IR", "HOMA Index"],
            "category": "Glycemic & Metabolic",
            "units": "index",
            "measurement_method": "Mathematical Index: (Fasting Glucose x Fasting Insulin) / 405",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Pancreas & Endocrine",
            "tissue_origin": "Skeletal Muscle, Adipose & Hepatocytes",
            "nhanes_code": "HOMAIR",
            "notes": "Mathematical model quantifying baseline hepatic and peripheral insulin resistance from fasting state."
        },

        # --- Liver, Nutritional & Enzymes ---
        {
            "id": 24,
            "slug": "alanine_aminotransferase",
            "name": "Alanine Aminotransferase (ALT)",
            "aliases": ["ALT", "SGPT"],
            "category": "Liver & Nutritional",
            "units": "U/L",
            "measurement_method": "Enzymatic Rate with Pyridoxal-5-Phosphate",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes (Cytosol)",
            "nhanes_code": "LBXSATSI",
            "notes": "Hepatocellular enzyme localized primarily to cytosol; very low ALT in elderly reflects frailty and hepatic sarcopenia (U-shaped curve)."
        },
        {
            "id": 25,
            "slug": "aspartate_aminotransferase",
            "name": "Aspartate Aminotransferase (AST)",
            "aliases": ["AST", "SGOT"],
            "category": "Liver & Nutritional",
            "units": "U/L",
            "measurement_method": "Enzymatic Kinetic Rate (IFCC Reference)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes, Cardiomyocytes & Skeletal Myocytes",
            "nhanes_code": "LBXSRC",
            "notes": "Mitochondrial and cytosolic enzyme expressed in liver, myocardium, and skeletal muscle; elevated in tissue injury and advanced fibrosis."
        },
        {
            "id": 26,
            "slug": "gamma_glutamyl_transferase",
            "name": "Gamma-Glutamyl Transferase (GGT)",
            "aliases": ["GGT", "GGTP"],
            "category": "Liver & Nutritional",
            "units": "U/L",
            "measurement_method": "L-Gamma-Glutamyl-3-Carboxy-4-Nitroanilide Enzymatic Rate",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Biliary Canalicular Epithelium & Hepatocytes",
            "nhanes_code": "LBXSGTSI",
            "notes": "Microsomal enzyme involved in glutathione metabolism; sensitive marker of hepatic steatosis, alcohol consumption, and systemic oxidative stress."
        },
        {
            "id": 27,
            "slug": "alkaline_phosphatase",
            "name": "Alkaline Phosphatase (ALP)",
            "aliases": ["Alk Phos", "ALP"],
            "category": "Liver & Nutritional",
            "units": "U/L",
            "measurement_method": "p-Nitrophenyl Phosphate Cleavage Kinetic Rate",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Biliary Epithelium, Osteoblasts & Renal Tubules",
            "nhanes_code": "LBXSAPSI",
            "notes": "Membrane-bound metalloenzyme expressed in liver, bone, kidneys, and vascular endothelial tissue; involved in vascular calcification pathways."
        },
        {
            "id": 28,
            "slug": "total_bilirubin",
            "name": "Serum Total Bilirubin",
            "aliases": ["Total Bilirubin", "TBil", "Bilirubin"],
            "category": "Liver & Nutritional",
            "units": "mg/dL",
            "measurement_method": "Diazo Coupling Colorimetric Reaction",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Reticuloendothelial System & Hepatocytes",
            "nhanes_code": "LBXSTB",
            "notes": "End product of heme catabolism; endogenous antioxidant at physiologic concentrations, elevated in cholestasis and hemolysis."
        },
        {
            "id": 29,
            "slug": "serum_albumin",
            "name": "Serum Albumin",
            "aliases": ["Albumin", "ALB"],
            "category": "Liver & Nutritional",
            "units": "g/dL",
            "measurement_method": "Bromocresol Purple / Green Dye Binding",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Liver & Hepatobiliary",
            "tissue_origin": "Hepatocytes",
            "nhanes_code": "LBXSAL",
            "notes": "Major circulating protein synthesized by hepatocytes; negative acute-phase reactant reflecting nutritional status and systemic inflammation."
        },

        # --- Electrolytes & Minerals ---
        {
            "id": 30,
            "slug": "serum_sodium",
            "name": "Serum Sodium",
            "aliases": ["Sodium", "Na+"],
            "category": "Electrolytes & Minerals",
            "units": "mmol/L",
            "measurement_method": "Ion-Selective Electrode (ISE) Direct Potentiometry",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Renal Tubular Epithelium & Extracellular Fluid",
            "nhanes_code": "LBXSNASI",
            "notes": "Major extracellular cation regulating extracellular fluid volume and osmolality; both hyponatremia and hypernatremia confer high mortality."
        },
        {
            "id": 31,
            "slug": "serum_potassium",
            "name": "Serum Potassium",
            "aliases": ["Potassium", "K+"],
            "category": "Electrolytes & Minerals",
            "units": "mmol/L",
            "measurement_method": "Ion-Selective Electrode (ISE) Potentiometry",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Intracellular Cytoplasm & Cortical Collecting Duct",
            "nhanes_code": "LBXSKSI",
            "notes": "Major intracellular cation essential for myocardial resting membrane potential and neuromuscular conduction; strict U-shaped mortality curve."
        },
        {
            "id": 32,
            "slug": "serum_calcium",
            "name": "Serum Calcium",
            "aliases": ["Calcium", "Total Calcium", "Ca"],
            "category": "Electrolytes & Minerals",
            "units": "mg/dL",
            "measurement_method": "Arsenazo III / O-Cresolphthalein Complexone Photometry",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Multi-Organ / Systemic",
            "tissue_origin": "Bone Hydroxyapatite & Parathyroid / Renal Tubules",
            "nhanes_code": "LBXSCA",
            "notes": "Total circulating calcium; regulates neuromuscular transmission, coagulation cascade, and cardiac excitation-contraction coupling."
        },
        {
            "id": 33,
            "slug": "serum_phosphate",
            "name": "Serum Phosphate",
            "aliases": ["Phosphate", "Phosphorus", "Inorganic Phosphate"],
            "category": "Electrolytes & Minerals",
            "units": "mg/dL",
            "measurement_method": "Phosphomolybdate UV Colorimetric Assay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Bone Matrix & Proximal Tubule Sodium-Phosphate Cotransporters",
            "nhanes_code": "LBXSPH",
            "notes": "Inorganic anion crucial for cellular energy (ATP), nucleic acid structure, and vascular calcification pathways."
        },

        # --- Cardiac & Hemodynamics ---
        {
            "id": 34,
            "slug": "nt_pro_bnp",
            "name": "N-Terminal Pro-B-Type Natriuretic Peptide (NT-proBNP)",
            "aliases": ["NT-proBNP", "proBNP", "BNP"],
            "category": "Cardiac & Hemodynamics",
            "units": "pg/mL",
            "measurement_method": "Electrochemiluminescence Immunoassay (ECLIA)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Ventricular Cardiomyocytes",
            "nhanes_code": "NTPROBNP",
            "notes": "Cleaved prohormone fragment released by ventricular cardiomyocytes in response to wall tension, stretch, and volume overload."
        },
        {
            "id": 35,
            "slug": "hs_troponin_t",
            "name": "High-Sensitivity Cardiac Troponin T (hs-cTnT)",
            "aliases": ["hs-cTnT", "hs-Troponin T", "Cardiac Troponin T"],
            "category": "Cardiac & Hemodynamics",
            "units": "ng/L",
            "measurement_method": "High-Sensitivity Electrochemiluminescent Immunoassay",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Cardiomyocyte Sarcomere",
            "nhanes_code": "HSTNT",
            "notes": "Specific biomarker of myocardial cellular injury, ischemia, and subclinical chronic cardiomyocyte death."
        },
        {
            "id": 36,
            "slug": "systolic_blood_pressure",
            "name": "Systolic Blood Pressure (SBP)",
            "aliases": ["SBP", "Systolic BP"],
            "category": "Cardiac & Hemodynamics",
            "units": "mmHg",
            "measurement_method": "Auscultatory / Oscillometric Sphygmomanometer",
            "specimen_type": "physiological",
            "bodily_fluid": "Non-Fluid / Hemodynamic",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Vascular Endothelium & Systemic Arterial Wall",
            "nhanes_code": "BPXSY1",
            "notes": "Peak arterial pressure during ventricular contraction; continuous monotonic driver of cardiovascular and cerebrovascular mortality above 115 mmHg."
        },
        {
            "id": 37,
            "slug": "diastolic_blood_pressure",
            "name": "Diastolic Blood Pressure (DBP)",
            "aliases": ["DBP", "Diastolic BP"],
            "category": "Cardiac & Hemodynamics",
            "units": "mmHg",
            "measurement_method": "Auscultatory / Oscillometric Sphygmomanometer",
            "specimen_type": "physiological",
            "bodily_fluid": "Non-Fluid / Hemodynamic",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Vascular Smooth Muscle & Peripheral Resistance Arterioles",
            "nhanes_code": "BPXDI1",
            "notes": "Trough arterial pressure during ventricular diastole; shows J-shaped association in elderly patients with arterial stiffness."
        },
        {
            "id": 38,
            "slug": "resting_heart_rate",
            "name": "Resting Heart Rate (RHR)",
            "aliases": ["RHR", "Pulse", "Resting Pulse"],
            "category": "Cardiac & Hemodynamics",
            "units": "bpm",
            "measurement_method": "Radial Pulse Palpation / Electrocardiogram / Plethysmography",
            "specimen_type": "physiological",
            "bodily_fluid": "Non-Fluid / Hemodynamic",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Sinoatrial Nodal Pacemaker Tissue & Autonomic Tone",
            "nhanes_code": "BPXPLS",
            "notes": "Reflects parasympathetic vagal tone vs sympathetic drive; strong independent prospective predictor of all-cause mortality across cohorts."
        },
        {
            "id": 39,
            "slug": "pulse_wave_velocity",
            "name": "Carotid-Femoral Pulse Wave Velocity (PWV)",
            "aliases": ["PWV", "cfPWV", "Pulse Wave Velocity", "Arterial Stiffness"],
            "category": "Cardiac & Hemodynamics",
            "units": "m/s",
            "measurement_method": "Applanation Tonometry / Piezoelectric Transducer",
            "specimen_type": "physiological",
            "bodily_fluid": "Non-Fluid / Hemodynamic",
            "primary_organ": "Cardiovascular & Vasculature",
            "tissue_origin": "Aortic Elastic Media & Extracellular Matrix",
            "nhanes_code": "PWV",
            "notes": "Gold-standard non-invasive measurement of large elastic arterial stiffness and vascular aging."
        },

        # --- Functional Fitness & Physical Performance ---
        {
            "id": 40,
            "slug": "grip_strength",
            "name": "Maximal Grip Strength",
            "aliases": ["Grip Strength", "Handgrip Strength", "HGS"],
            "category": "Functional Fitness",
            "units": "kg",
            "measurement_method": "Jamar Hydraulic / Digital Hand Dynamometer",
            "specimen_type": "functional",
            "bodily_fluid": "Non-Fluid / Functional",
            "primary_organ": "Musculoskeletal & Pulmonary",
            "tissue_origin": "Forearm & Skeletal Myofibers (Type I & II)",
            "nhanes_code": "MGDCGSZ",
            "notes": "Surrogate of total-body muscular strength, neuromuscular reserve, and resistance to frailty; inversely associated with mortality."
        },
        {
            "id": 41,
            "slug": "vo2_max",
            "name": "Cardiorespiratory Fitness (VO2 Max)",
            "aliases": ["VO2 Max", "Peak Oxygen Uptake", "CRF", "Cardiorespiratory Fitness"],
            "category": "Functional Fitness",
            "units": "mL/kg/min",
            "measurement_method": "Cardiopulmonary Exercise Testing (CPET) / Validated Treadmill Protocol",
            "specimen_type": "functional",
            "bodily_fluid": "Non-Fluid / Functional",
            "primary_organ": "Musculoskeletal & Pulmonary",
            "tissue_origin": "Mitochondrial Density, Myocytes & Alveolar Capillary Unit",
            "nhanes_code": "VO2MAX",
            "notes": "Maximal volume of oxygen consumed during graded maximal exercise; one of the strongest independent predictors of survival."
        },

        # --- Hematology & Cellular Aging ---
        {
            "id": 42,
            "slug": "hemoglobin",
            "name": "Hemoglobin Concentration",
            "aliases": ["Hb", "Hgb"],
            "category": "Hematology",
            "units": "g/dL",
            "measurement_method": "Photometric Cyanmethemoglobin / SLS-Hb Method",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Bone Marrow Erythroblasts & Erythrocytes",
            "nhanes_code": "LBXHGB",
            "notes": "Primary oxygen transport protein inside erythrocytes; both anemia and polycythemia elevate all-cause mortality (U-shaped curve)."
        },
        {
            "id": 43,
            "slug": "white_blood_cells",
            "name": "White Blood Cell Count (WBC)",
            "aliases": ["WBC", "Leukocyte Count"],
            "category": "Hematology",
            "units": "10^3 cells/uL",
            "measurement_method": "Automated Multi-angle Light Scatter Flow Cytometry",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Bone Marrow Myeloid & Lymphoid Progenitors",
            "nhanes_code": "LBXWBCSI",
            "notes": "Total circulating immune cells; sensitive marker of systemic subclinical inflammation, infection, and immunological tone."
        },
        {
            "id": 44,
            "slug": "red_cell_distribution_width",
            "name": "Red Cell Distribution Width (RDW)",
            "aliases": ["RDW-CV", "RDW", "Anisocytosis Index"],
            "category": "Hematology",
            "units": "%",
            "measurement_method": "Automated Electronic Sizing & Cell Counter",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Erythroid Precursors & Circulating Erythrocytes",
            "nhanes_code": "LBXRDW",
            "notes": "Measures coefficient of variation of red blood cell volume. Elevated in systemic inflammation, impaired erythropoiesis, and biological aging."
        },
        {
            "id": 45,
            "slug": "platelet_count",
            "name": "Platelet Count",
            "aliases": ["Thrombocytes", "PLT"],
            "category": "Hematology",
            "units": "10^3 cells/uL",
            "measurement_method": "Hydrodynamic Focusing Impedance & Optical Counting",
            "specimen_type": "whole_blood",
            "bodily_fluid": "Whole Blood",
            "primary_organ": "Immune & Hematopoietic",
            "tissue_origin": "Bone Marrow Megakaryocytes",
            "nhanes_code": "LBXPLTSI",
            "notes": "Cellular mediators of hemostasis and vascular thrombosis; thrombocytopenia and extreme reactive thrombocytosis both confer elevated mortality."
        },

        # --- Urine & Excretory Biomarkers ---
        {
            "id": 46,
            "slug": "urine_albumin_creatinine_ratio",
            "name": "Urine Albumin-to-Creatinine Ratio (uACR)",
            "aliases": ["uACR", "Microalbuminuria Ratio", "Urinary ACR"],
            "category": "Urine Biomarkers",
            "units": "mg/g",
            "measurement_method": "Solid-phase Fluorescence Immunoassay / Nephelometry",
            "specimen_type": "urine",
            "bodily_fluid": "Urine",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Glomerular Podocytes & Fenestrated Endothelium",
            "nhanes_code": "URDACT",
            "notes": "Sensitive indicator of glomerular capillary permeability and generalized systemic endothelial dysfunction."
        },
        {
            "id": 47,
            "slug": "urine_creatinine",
            "name": "Urinary Creatinine Concentration",
            "aliases": ["Urine Cr", "Spot Urine Creatinine"],
            "category": "Urine Biomarkers",
            "units": "mg/dL",
            "measurement_method": "Enzymatic / Alkaline Picrate Method",
            "specimen_type": "urine",
            "bodily_fluid": "Urine",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Renal Tubules & Glomerular Excretion",
            "nhanes_code": "URXUCR",
            "notes": "Surrogate for lean muscle mass and urinary hydration/concentration normalization in spot urine samples."
        },
        {
            "id": 48,
            "slug": "urine_specific_gravity",
            "name": "Urine Specific Gravity",
            "aliases": ["USG", "Specific Gravity"],
            "category": "Urine Biomarkers",
            "units": "ratio",
            "measurement_method": "Optical Refractometry / Reagent Strip Ion-Exchange",
            "specimen_type": "urine",
            "bodily_fluid": "Urine",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Renal Medullary Collecting Ducts & Loop of Henle",
            "nhanes_code": "URXUSG",
            "notes": "Measures kidney tubular concentrating ability and physiological hydration state; deviations signal renal tubular decline."
        },
        {
            "id": 49,
            "slug": "urine_flow_rate",
            "name": "Urinary Flow Rate",
            "aliases": ["Urine Flow", "Timed Flow Rate"],
            "category": "Urine Biomarkers",
            "units": "mL/min",
            "measurement_method": "Timed Collection Gravimetric Flow Rate",
            "specimen_type": "urine",
            "bodily_fluid": "Urine",
            "primary_organ": "Renal & Urinary",
            "tissue_origin": "Nephron Tubular Fluid & Bladder Excretion",
            "nhanes_code": "URDFLOW1",
            "notes": "Volume rate of urine production; physiological biomarker of hydration volume and acute tubular perfusion."
        },

        # --- Endocrine & Vitamins ---
        {
            "id": 50,
            "slug": "serum_25_hydroxyvitamin_d",
            "name": "Serum 25-Hydroxyvitamin D",
            "aliases": ["25(OH)D", "Calcifediol", "Vitamin D3"],
            "category": "Vitamins & Endocrine",
            "units": "nmol/L",
            "measurement_method": "Liquid Chromatography-Tandem Mass Spectrometry (LC-MS/MS)",
            "specimen_type": "serum",
            "bodily_fluid": "Blood Serum",
            "primary_organ": "Multi-Organ / Systemic",
            "tissue_origin": "Skin Keratinocytes & Hepatic Hydroxylation",
            "nhanes_code": "LBXVIDMS",
            "notes": "Main storage form of vitamin D in circulation; inverse non-linear relationship with all-cause and cardiovascular mortality."
        }
    ]

    for b_dict in biomarkers_data:
        b = Biomarker(**b_dict)
        db_session.add(b)
    db_session.commit()

    # Create slug-to-id and id-to-biomarker lookup
    b_map = {b.slug: b.id for b in db_session.query(Biomarker).all()}

    # 3. Interventions Catalog (Covering all physiological categories)
    interventions_data = [
        # --- Inflammatory Markers ---
        {
            "biomarker_id": b_map["high_sensitivity_crp"],
            "source_id": 15,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "Statin therapy (e.g., Rosuvastatin 20 mg/day or Atorvastatin)",
            "quantified_effect": "Reduces hs-CRP by 37% (from median 4.2 to 2.2 mg/L)",
            "evidence_strength": "RCT",
            "notes": "Demonstrated 44% reduction in major cardiovascular events and 20% reduction in all-cause mortality in JUPITER trial."
        },
        {
            "biomarker_id": b_map["high_sensitivity_crp"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "Mediterranean Diet enriched with Extra-Virgin Olive Oil or Tree Nuts",
            "quantified_effect": "Reduces hs-CRP by 15-25% over 12 months",
            "evidence_strength": "RCT",
            "notes": "Reduces systemic inflammatory cytokines and improves endothelial function."
        },
        {
            "biomarker_id": b_map["high_sensitivity_crp"],
            "source_id": 16,
            "direction": "favorable",
            "category": "exercise",
            "description": "Aerobic and resistance exercise training (>= 150 min/week moderate-vigorous)",
            "quantified_effect": "Reduces hs-CRP by 18-30%",
            "evidence_strength": "meta-analysis",
            "notes": "Mediated via reduction in visceral adiposity and attenuation of monocyte inflammatory signaling."
        },
        {
            "biomarker_id": b_map["high_sensitivity_crp"],
            "source_id": 1,
            "direction": "unfavorable",
            "category": "sleep",
            "description": "Chronic sleep deprivation (< 6 hours/night) and circadian disruption",
            "quantified_effect": "Increases circulating hs-CRP by 20-45%",
            "evidence_strength": "cohort",
            "notes": "Triggers NF-kB activation and elevated nocturnal sympathetic tone."
        },
        {
            "biomarker_id": b_map["interleukin_6"],
            "source_id": 16,
            "direction": "favorable",
            "category": "exercise",
            "description": "Regular moderate aerobic endurance training and resistance training",
            "quantified_effect": "Lowers baseline circulating IL-6 by 20-35%",
            "evidence_strength": "meta-analysis",
            "notes": "Downregulates baseline adipose tissue macrophages while acute exercise pulses anti-inflammatory myokines."
        },
        {
            "biomarker_id": b_map["tumor_necrosis_factor_alpha"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "Caloric restriction and anti-inflammatory polyphenol-rich dietary intake",
            "quantified_effect": "Reduces TNF-alpha by 15-30%",
            "evidence_strength": "RCT",
            "notes": "Attenuates macrophage activation and improves peripheral insulin sensitivity."
        },
        {
            "biomarker_id": b_map["fibrinogen"],
            "source_id": 16,
            "direction": "favorable",
            "category": "behavioral",
            "description": "Smoking cessation",
            "quantified_effect": "Lowers plasma fibrinogen by 30-50 mg/dL within 6-12 months",
            "evidence_strength": "cohort",
            "notes": "Removes direct endothelial and pulmonary macrophage inflammatory stimuli."
        },
        {
            "biomarker_id": b_map["erythrocyte_sedimentation_rate"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "Whole-food plant-predominant anti-inflammatory dietary pattern",
            "quantified_effect": "Decreases ESR by 5-12 mm/hr in chronic inflammatory cohorts",
            "evidence_strength": "RCT",
            "notes": "Lowers circulating acute phase globulins and erythrocyte rouleaux formation."
        },
        {
            "biomarker_id": b_map["neutrophil_lymphocyte_ratio"],
            "source_id": 16,
            "direction": "favorable",
            "category": "exercise",
            "description": "Supervised combined endurance and resistance exercise",
            "quantified_effect": "Reduces NLR by 0.3-0.7 toward optimal reference (<2.0)",
            "evidence_strength": "RCT",
            "notes": "Enhances adaptive lymphocyte surveillance while mitigating chronic neutrophilic inflammation."
        },
        {
            "biomarker_id": b_map["serum_ferritin"],
            "source_id": 1,
            "direction": "favorable",
            "category": "behavioral",
            "description": "Therapeutic phlebotomy / Blood donation in iron overload states",
            "quantified_effect": "Lowers serum ferritin into optimal 50-150 ug/L range",
            "evidence_strength": "RCT",
            "notes": "Prevents Fenton reaction-mediated free radical generation and hepatic oxidative injury."
        },

        # --- Renal & Purine Metabolism ---
        {
            "biomarker_id": b_map["serum_creatinine"],
            "source_id": 10,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "SGLT2 inhibitors (e.g. Empagliflozin, Dapagliflozin) or ACEi/ARB therapy",
            "quantified_effect": "Preserves long-term renal function, slowing eGFR decline by 40-50%",
            "evidence_strength": "RCT",
            "notes": "Reduces intraglomerular hyperfiltration and renal tubular hypoxia."
        },
        {
            "biomarker_id": b_map["cystatin_c"],
            "source_id": 10,
            "direction": "favorable",
            "category": "diet",
            "description": "Optimal plant-dominant dietary protein pattern and blood pressure control",
            "quantified_effect": "Stabilizes Cystatin C levels and halts progressive rise",
            "evidence_strength": "cohort",
            "notes": "Reduces glomerular hemodynamic load independent of skeletal muscle mass."
        },
        {
            "biomarker_id": b_map["estimated_gfr"],
            "source_id": 10,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "SGLT2 inhibitors and Nonsteroidal Mineralocorticoid Receptor Antagonists (Finerenone)",
            "quantified_effect": "Significantly attenuates chronic eGFR slope loss by 1.5-2.5 mL/min/1.73m2/year",
            "evidence_strength": "RCT",
            "notes": "Robust reduction in cardiovascular and end-stage renal disease endpoints."
        },
        {
            "biomarker_id": b_map["serum_uric_acid"],
            "source_id": 19,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "Xanthine oxidase inhibitor therapy (Allopurinol 100-300 mg/day or Febuxostat)",
            "quantified_effect": "Lowers serum uric acid by 2.0-4.0 mg/dL (35-55%)",
            "evidence_strength": "RCT",
            "notes": "Directly inhibits uric acid biosynthesis and lowers vascular oxidative stress."
        },
        {
            "biomarker_id": b_map["serum_uric_acid"],
            "source_id": 19,
            "direction": "favorable",
            "category": "diet",
            "description": "Elimination of high-fructose corn syrup beverages and reduction of high-purine meats/beer",
            "quantified_effect": "Lowers serum uric acid by 0.8-1.5 mg/dL",
            "evidence_strength": "meta-analysis",
            "notes": "Fructose metabolism depletes intrahepatic ATP, driving rapid AMP degradation to uric acid."
        },

        # --- Lipids & Apolipoproteins ---
        {
            "biomarker_id": b_map["apolipoprotein_b"],
            "source_id": 15,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "High-intensity Statin + Ezetimibe +/- PCSK9 Monoclonal Antibody (Evolocumab/Alirocumab)",
            "quantified_effect": "Reduces ApoB by 45-75% down to target <60 mg/dL",
            "evidence_strength": "RCT",
            "notes": "Maximally clears all circulating atherogenic particles and reverses coronary atheroma volume."
        },
        {
            "biomarker_id": b_map["ldl_cholesterol"],
            "source_id": 15,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "HMG-CoA reductase inhibitors (Statins) / PCSK9 Inhibitors / Ezetimibe",
            "quantified_effect": "Reduces LDL-C by 30-65% (40-90 mg/dL)",
            "evidence_strength": "RCT",
            "notes": "Upregulates hepatic LDL receptor density and accelerates clearance of atherogenic particles."
        },
        {
            "biomarker_id": b_map["ldl_cholesterol"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "High soluble viscous fiber intake (>= 10-15g/day psyllium, oats, beta-glucan)",
            "quantified_effect": "Reduces LDL-C by 5-12 mg/dL (5-10%)",
            "evidence_strength": "meta-analysis",
            "notes": "Binds bile acids in intestinal lumen, forcing hepatic conversion of cholesterol into new bile."
        },
        {
            "biomarker_id": b_map["hdl_cholesterol"],
            "source_id": 16,
            "direction": "favorable",
            "category": "exercise",
            "description": "High-intensity aerobic intervals and endurance training",
            "quantified_effect": "Increases HDL-C by 3-6 mg/dL (5-10%) and enhances cholesterol efflux capacity",
            "evidence_strength": "RCT",
            "notes": "Upregulates lipoprotein lipase (LPL) activity and increases ApoA-I synthesis."
        },
        {
            "biomarker_id": b_map["triglycerides"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "Carbohydrate restriction, elimination of added sugars/alcohol, and Omega-3 EPA/DHA intake",
            "quantified_effect": "Lowers triglycerides by 25-50%",
            "evidence_strength": "RCT",
            "notes": "Downregulates hepatic de novo lipogenesis and accelerates VLDL clearance."
        },
        {
            "biomarker_id": b_map["lipoprotein_a"],
            "source_id": 15,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "Novel RNA-targeting therapeutics (Pelacarsen, Olpasiran) or PCSK9 inhibitors",
            "quantified_effect": "Reduces circulating Lp(a) by 20-30% (PCSK9i) up to 80-95% (siRNA/ASO)",
            "evidence_strength": "RCT",
            "notes": "Directly targets hepatic LPA mRNA translation and halts atherothrombotic particle production."
        },

        # --- Glycemic & Metabolic Control ---
        {
            "biomarker_id": b_map["fasting_glucose"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "Low-glycemic Mediterranean or carbohydrate-restricted dietary pattern",
            "quantified_effect": "Reduces fasting glucose by 15-30 mg/dL and HbA1c by 0.5-1.2%",
            "evidence_strength": "RCT",
            "notes": "Improves peripheral muscle insulin sensitivity and dampens hepatic gluconeogenesis."
        },
        {
            "biomarker_id": b_map["fasting_glucose"],
            "source_id": 16,
            "direction": "favorable",
            "category": "exercise",
            "description": "Post-prandial walking (15-30 min) and progressive resistance training",
            "quantified_effect": "Reduces acute glucose excursions by 20-35% and baseline fasting glucose by 8-15 mg/dL",
            "evidence_strength": "RCT",
            "notes": "Triggers insulin-independent GLUT-4 transporter translocation in skeletal muscle fibers."
        },
        {
            "biomarker_id": b_map["hba1c"],
            "source_id": 16,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "GLP-1 Receptor Agonists (Semaglutide/Tirzepatide) or Metformin",
            "quantified_effect": "Lowers HbA1c by 1.0-2.4% and induces significant weight loss",
            "evidence_strength": "RCT",
            "notes": "Improves glucose-dependent insulin secretion, slows gastric emptying, and reduces cardiovascular mortality."
        },
        {
            "biomarker_id": b_map["fasting_insulin"],
            "source_id": 16,
            "direction": "favorable",
            "category": "diet",
            "description": "Time-restricted eating (16:8) and reduction of refined starches",
            "quantified_effect": "Reduces fasting insulin by 30-50%",
            "evidence_strength": "RCT",
            "notes": "Prolongs basal insulin rest periods and restores hepatic insulin signaling."
        },
        {
            "biomarker_id": b_map["homa_ir"],
            "source_id": 16,
            "direction": "favorable",
            "category": "exercise",
            "description": "High-intensity resistance training combined with aerobic exercise",
            "quantified_effect": "Improves HOMA-IR index by 30-45%",
            "evidence_strength": "meta-analysis",
            "notes": "Increases skeletal muscle mass and mitochondrial oxidative capacity."
        },

        # --- Liver, Nutritional & Enzymes ---
        {
            "biomarker_id": b_map["alanine_aminotransferase"],
            "source_id": 11,
            "direction": "favorable",
            "category": "diet",
            "description": "Weight loss (5-10% body weight) and avoidance of ultra-processed foods/fructose",
            "quantified_effect": "Reduces elevated ALT by 40-60% into normal range (<25 U/L)",
            "evidence_strength": "RCT",
            "notes": "Reverses hepatic steatosis and prevents nonalcoholic steatohepatitis progression."
        },
        {
            "biomarker_id": b_map["gamma_glutamyl_transferase"],
            "source_id": 11,
            "direction": "favorable",
            "category": "behavioral",
            "description": "Cessation or drastic reduction of alcohol intake and coffee consumption (2-3 cups/day)",
            "quantified_effect": "Lowers serum GGT by 30-65% within 4-8 weeks",
            "evidence_strength": "cohort",
            "notes": "Coffee polyphenols stimulate hepatic antioxidant enzymes and protect hepatocytes."
        },
        {
            "biomarker_id": b_map["serum_albumin"],
            "source_id": 6,
            "direction": "favorable",
            "category": "diet",
            "description": "Adequate dietary protein intake (1.2-1.6 g/kg/day) with sufficient caloric density",
            "quantified_effect": "Increases serum albumin by 0.2-0.4 g/dL in hypoalbuminemic adults",
            "evidence_strength": "RCT",
            "notes": "Stimulates hepatic protein synthesis and reverses muscle catabolic wasting."
        },
        {
            "biomarker_id": b_map["serum_albumin"],
            "source_id": 6,
            "direction": "unfavorable",
            "category": "behavioral",
            "description": "Severe systemic inflammation, chronic heavy alcohol consumption, or protein-energy malnutrition",
            "quantified_effect": "Decreases serum albumin by 0.5-1.2 g/dL",
            "evidence_strength": "cohort",
            "notes": "Suppresses hepatic albumin gene transcription and increases vascular transcapillary escape rate."
        },
        {
            "biomarker_id": b_map["total_bilirubin"],
            "source_id": 1,
            "direction": "favorable",
            "category": "exercise",
            "description": "Regular moderate aerobic exercise and maintenance of healthy body composition",
            "quantified_effect": "Optimizes physiologic bilirubin in protective 0.6-1.1 mg/dL range",
            "evidence_strength": "cohort",
            "notes": "Mildly elevated physiologic bilirubin serves as a potent endogenous lipophilic antioxidant."
        },

        # --- Electrolytes & Minerals ---
        {
            "biomarker_id": b_map["serum_potassium"],
            "source_id": 1,
            "direction": "favorable",
            "category": "diet",
            "description": "Potassium-rich whole food diet (vegetables, fruits, legumes: 3500-4700 mg/day)",
            "quantified_effect": "Maintains optimal serum potassium within narrow 4.0-4.8 mmol/L band",
            "evidence_strength": "RCT",
            "notes": "Optimizes cardiac electrophysiology and promotes vascular endothelium-dependent vasodilation."
        },
        {
            "biomarker_id": b_map["serum_sodium"],
            "source_id": 1,
            "direction": "favorable",
            "category": "diet",
            "description": "Adequate fluid hydration and moderate dietary sodium intake (1500-2300 mg/day)",
            "quantified_effect": "Stabilizes serum sodium in optimal 138-142 mmol/L range",
            "evidence_strength": "cohort",
            "notes": "Prevents hyperosmolar cellular stress and neurohormonal RAAS/ADH overactivation."
        },

        # --- Cardiac & Hemodynamics ---
        {
            "biomarker_id": b_map["nt_pro_bnp"],
            "source_id": 8,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "ARNI (Sacubitril/Valsartan), SGLT2 inhibitors, and Beta-blocker guideline-directed medical therapy",
            "quantified_effect": "Reduces NT-proBNP by 30-50%",
            "evidence_strength": "RCT",
            "notes": "Reduces left ventricular filling pressure and reverses adverse ventricular remodeling."
        },
        {
            "biomarker_id": b_map["hs_troponin_t"],
            "source_id": 8,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "Intensive blood pressure control (<120 mmHg SBP) and statin cardioprotection",
            "quantified_effect": "Lowers hs-cTnT by 15-30% toward baseline non-detectable levels (<6 ng/L)",
            "evidence_strength": "RCT",
            "notes": "Attenuates subclinical microvascular ischemia and chronic cardiomyocyte apoptotic shedding."
        },
        {
            "biomarker_id": b_map["systolic_blood_pressure"],
            "source_id": 8,
            "direction": "favorable",
            "category": "diet",
            "description": "DASH diet (high potassium, magnesium, calcium, low sodium <2000 mg/day)",
            "quantified_effect": "Reduces systolic BP by 8-14 mmHg",
            "evidence_strength": "RCT",
            "notes": "Improves vascular nitric oxide bioavailability and reduces peripheral vascular resistance."
        },
        {
            "biomarker_id": b_map["systolic_blood_pressure"],
            "source_id": 8,
            "direction": "favorable",
            "category": "exercise",
            "description": "Isometric resistance training and continuous aerobic endurance training",
            "quantified_effect": "Reduces resting systolic BP by 5-10 mmHg",
            "evidence_strength": "meta-analysis",
            "notes": "Enhances systemic arterial compliance and baroreflex sensitivity."
        },
        {
            "biomarker_id": b_map["resting_heart_rate"],
            "source_id": 18,
            "direction": "favorable",
            "category": "exercise",
            "description": "Zone 2 endurance training / Aerobic conditioning (3-5 sessions/week)",
            "quantified_effect": "Decreases resting heart rate by 8-15 bpm",
            "evidence_strength": "meta-analysis",
            "notes": "Enhances cardiac stroke volume and increases parasympathetic cardiac vagal tone."
        },
        {
            "biomarker_id": b_map["pulse_wave_velocity"],
            "source_id": 8,
            "direction": "favorable",
            "category": "exercise",
            "description": "Lifelong aerobic endurance exercise and blood pressure control",
            "quantified_effect": "Lowers cfPWV by 1.0-2.0 m/s (equivalent to 10-15 years younger vascular age)",
            "evidence_strength": "meta-analysis",
            "notes": "Prevents elastin fragmentation, cross-linking advanced glycation end-products (AGEs), and collagen remodeling in the aorta."
        },

        # --- Functional Fitness & Physical Performance ---
        {
            "biomarker_id": b_map["grip_strength"],
            "source_id": 1,
            "direction": "favorable",
            "category": "exercise",
            "description": "Progressive resistance training (2-4x/week compound barbell/dumbbell movements)",
            "quantified_effect": "Increases grip and whole-body muscular strength by 15-35%",
            "evidence_strength": "RCT",
            "notes": "Hypertrophies type II muscle fibers, improves motoneuron recruitment, and reverses dynapenia."
        },
        {
            "biomarker_id": b_map["vo2_max"],
            "source_id": 1,
            "direction": "favorable",
            "category": "exercise",
            "description": "High-intensity interval training (HIIT) and high-volume polarized Zone 2 endurance cardio",
            "quantified_effect": "Increases VO2 Max by 4-8 mL/kg/min (15-25%)",
            "evidence_strength": "RCT",
            "notes": "Increases maximal cardiac output, mitochondrial capillary density, and peripheral oxygen extraction."
        },

        # --- Hematology & Cellular Aging ---
        {
            "biomarker_id": b_map["red_cell_distribution_width"],
            "source_id": 7,
            "direction": "favorable",
            "category": "supplement",
            "description": "Correction of micronutrient deficiencies (Iron, Vitamin B12, and Folate repletion)",
            "quantified_effect": "Normalizes RDW toward <12.5%",
            "evidence_strength": "RCT",
            "notes": "Restores synchronous erythrocyte maturation and decreases anisocytosis."
        },
        {
            "biomarker_id": b_map["red_cell_distribution_width"],
            "source_id": 7,
            "direction": "unfavorable",
            "category": "environmental",
            "description": "Chronic systemic inflammatory state and oxidative erythrocyte membrane fragility",
            "quantified_effect": "Increases RDW > 14.5%",
            "evidence_strength": "cohort",
            "notes": "Shortens red blood cell lifespan and impairs bone marrow erythropoietin responsiveness."
        },
        {
            "biomarker_id": b_map["hemoglobin"],
            "source_id": 1,
            "direction": "favorable",
            "category": "supplement",
            "description": "Targeted elemental iron or erythropoiesis-stimulating cofactors when deficient",
            "quantified_effect": "Normalizes hemoglobin to optimal 13.5-16.5 g/dL (men) and 12.0-15.0 g/dL (women)",
            "evidence_strength": "RCT",
            "notes": "Restores tissue oxygen delivery and reduces compensatory sympathetic tachycardia."
        },
        {
            "biomarker_id": b_map["white_blood_cells"],
            "source_id": 1,
            "direction": "favorable",
            "category": "behavioral",
            "description": "Smoking cessation and reduction of visceral adiposity",
            "quantified_effect": "Lowers elevated WBC count by 1.5-2.5 x 10^3 cells/uL into optimal 4.5-6.5 range",
            "evidence_strength": "cohort",
            "notes": "Removes constant bone marrow leukopoietic stimulation driven by pro-inflammatory cytokines."
        },

        # --- Urine & Excretory Biomarkers ---
        {
            "biomarker_id": b_map["urine_albumin_creatinine_ratio"],
            "source_id": 10,
            "direction": "favorable",
            "category": "pharmacologic",
            "description": "ACE inhibitors / Angiotensin Receptor Blockers (ARBs) or SGLT2 inhibitors",
            "quantified_effect": "Reduces uACR by 30-50% (reversing microalbuminuria)",
            "evidence_strength": "RCT",
            "notes": "Reduces intraglomerular hydrostatic pressure and restores podocyte slit diaphragm integrity."
        },
        {
            "biomarker_id": b_map["urine_specific_gravity"],
            "source_id": 1,
            "direction": "favorable",
            "category": "diet",
            "description": "Consistent daily fluid hydration (2.5-3.5 L/day water intake)",
            "quantified_effect": "Maintains urine specific gravity in optimal euvolemic range (1.010-1.020)",
            "evidence_strength": "cohort",
            "notes": "Prevents kidney stone formation and reduces vasopressin-mediated glomerular stress."
        },

        # --- Endocrine & Vitamins ---
        {
            "biomarker_id": b_map["serum_25_hydroxyvitamin_d"],
            "source_id": 9,
            "direction": "favorable",
            "category": "supplement",
            "description": "Oral Cholecalciferol (Vitamin D3) supplementation (2000-5000 IU/day)",
            "quantified_effect": "Increases serum 25(OH)D from deficient levels to optimal 75-125 nmol/L (30-50 ng/mL)",
            "evidence_strength": "RCT",
            "notes": "Undergoes 25-hydroxylation in liver to replenish circulating calcifediol reserve."
        },
        {
            "biomarker_id": b_map["serum_25_hydroxyvitamin_d"],
            "source_id": 9,
            "direction": "favorable",
            "category": "environmental",
            "description": "Sensible solar ultraviolet B (UVB) exposure (15-20 min midday during summer)",
            "quantified_effect": "Synthesizes 10,000-20,000 IU cutaneous cholecalciferol per whole-body exposure",
            "evidence_strength": "cohort",
            "notes": "Direct photolysis of 7-dehydrocholesterol in the epidermal stratum basale."
        }
    ]

    for itv in interventions_data:
        db_session.add(Intervention(**itv))
    db_session.commit()

    # Ingest full 50-biomarker Interventions Catalog (lifestyle, pharmacologic, nutraceutical)
    try:
        from backend.interventions_catalog import INTERVENTIONS_CATALOG
        loaded_catalog_count = 0
        catalog_entries = []
        if isinstance(INTERVENTIONS_CATALOG, dict):
            for b_slug, b_data in INTERVENTIONS_CATALOG.items():
                for fav in b_data.get("favorable", []):
                    catalog_entries.append({
                        "biomarker_slug": b_slug,
                        "direction": "favorable",
                        "category": fav.get("category", "Lifestyle"),
                        "description": fav.get("name", ""),
                        "quantified_effect": fav.get("magnitude", ""),
                        "evidence_strength": fav.get("evidence_strength", "RCT"),
                        "citation": fav.get("citation", ""),
                        "pmid": fav.get("pmid", None)
                    })
                for unfav in b_data.get("unfavorable", []):
                    catalog_entries.append({
                        "biomarker_slug": b_slug,
                        "direction": "unfavorable",
                        "category": unfav.get("category", "Lifestyle"),
                        "description": unfav.get("name", ""),
                        "quantified_effect": unfav.get("magnitude", ""),
                        "evidence_strength": unfav.get("evidence_strength", "RCT"),
                        "citation": unfav.get("citation", ""),
                        "pmid": unfav.get("pmid", None)
                    })
        elif isinstance(INTERVENTIONS_CATALOG, list):
            catalog_entries = INTERVENTIONS_CATALOG

        for entry in catalog_entries:
            b_slug = entry["biomarker_slug"]
            # Convert slug variations (e.g. high_sensitivity_crp or high-sensitivity-crp)
            db_bio = db_session.query(Biomarker).filter(
                (Biomarker.slug == b_slug) | (Biomarker.slug == b_slug.replace("_", "-"))
            ).first()
            if not db_bio:
                continue
            
            # Find or create source for intervention citation
            cit_text = entry.get("citation", "Clinical trial & meta-analysis evidence")
            pmid_val = entry.get("pmid")
            if not pmid_val and "PMID:" in cit_text:
                pmid_part = cit_text.split("PMID:")[1].strip().split()[0].replace(".", "")
                pmid_val = pmid_part

            year_val = None
            year_match = re.search(r'\b(19\d\d|20\d\d)\b', cit_text)
            if year_match:
                year_val = int(year_match.group(1))

            src = db_session.query(Source).filter_by(citation=cit_text).first()
            if not src:
                src = Source(
                    citation=cit_text,
                    pmid=str(pmid_val) if pmid_val else None,
                    year=year_val,
                    study_design="rct" if entry.get("evidence_strength") == "RCT" else "meta_analysis"
                )
                db_session.add(src)
                db_session.flush()
            elif src.year is None and year_val:
                src.year = year_val
                db_session.flush()

            new_itv = Intervention(
                biomarker_id=db_bio.id,
                source_id=src.id,
                direction=entry.get("direction", "favorable"),
                category=entry.get("category", "Lifestyle").lower(),
                description=entry.get("description", ""),
                quantified_effect=entry.get("quantified_effect", ""),
                evidence_strength=entry.get("evidence_strength", "Meta-analysis").lower(),
                notes=entry.get("notes", "")
            )
            db_session.add(new_itv)
            loaded_catalog_count += 1
        db_session.commit()
        print(f"[OK] Loaded {loaded_catalog_count} additional multi-modal interventions from catalog.")
    except Exception as e:
        print(f"[!] Warning: Interventions catalog ingestion skipped: {e}")

    print(f"[OK] Loaded {len(biomarkers_data)} biomarkers, {len(sources_data)} initial sources.")

    # 4. Execute MortalityPredictors.org Ingestion Pipeline (all 50 biomarkers + 55 cohort studies)
    print("[*] Ingesting prospective cohort mortality hazard ratios from MortalityPredictors.org export...")
    mp_summary = ingest_mortalitypredictors_data(db_session)
    print(f"[OK] MortalityPredictors ingestion summary: {mp_summary}")

    # 5. Execute NHANES Population Distribution ETL for all 50 biomarkers
    nhanes_source = db_session.query(Source).filter_by(id=1).first()
    compute_nhanes_distributions(db_session, nhanes_source.id)
    print("[OK] Ingestion and NHANES population calibration complete!")

    # 6. Seed Optimization Scenarios, HR Curves, and Compute Optimization Models & Expected Values
    print("[*] Generating Derived Analytics Optimization Layer...")
    seed_optimization_layer(db_session)
    print("[OK] Derived Analytics Optimization Layer successfully seeded and precomputed!")

    # 7. Seed Competing Condition Panels & Continuous Distribution/HR Fits (Spec Section 2.1 & 2.2)
    print("[*] Seeding Competing Condition Panels & Continuous Fits...")
    seed_conditions_and_continuous_fits(db_session)
    print("[OK] Competing Condition Panels & Continuous Fits seeded successfully!")

    # 8. Ingest Disease Intelligence (Diseases, Ontology IDs, Remission, and Alterations)
    print("[*] Ingesting Disease Intelligence ETL records...")
    try:
        from backend.disease_intelligence_etl import ingest_disease_intelligence
        di_stats = ingest_disease_intelligence(db_session)
        print(f"[OK] Disease intelligence ingestion complete: {di_stats}")
    except Exception as e:
        print(f"[!] Warning: Disease intelligence ingestion encountered an error: {e}")


if __name__ == "__main__":
    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(db_dir, exist_ok=True)
    engine = get_engine(f"sqlite:///{os.path.join(db_dir, 'mortality_biomarkers.db')}")
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        seed_database(session)
    finally:
        session.close()

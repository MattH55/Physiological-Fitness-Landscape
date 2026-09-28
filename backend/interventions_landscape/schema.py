"""
SQL DDL for the interventions layer. Run these once against your database;
this module just holds the strings (no ORM assumed, since the rest of this
project's schema -- lab_tests, test_prices, etc. -- was also specified as
raw SQL).
"""

INTERVENTIONS_TABLE = """
CREATE TABLE interventions (
    intervention_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    intervention_type TEXT,      -- 'drug' | 'supplement' | 'diet' | 'exercise' | 'device' | 'other'
    description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

BIOMARKER_INTERVENTION_EFFECTS_TABLE = """
CREATE TABLE biomarker_intervention_effects (
    effect_id TEXT PRIMARY KEY,
    biomarker_id TEXT NOT NULL,
    intervention_id TEXT NOT NULL,

    effect_measure TEXT NOT NULL,     -- mean_difference | standardized_mean_difference
                                        -- | percent_change | relative_risk | odds_ratio
    effect_value REAL,
    effect_unit TEXT,                  -- biomarker's native unit for mean_difference; else null
    ci_low REAL,
    ci_high REAL,
    p_value REAL,

    direction TEXT,                    -- 'increases' | 'decreases' | 'no_significant_effect'

    dose TEXT,                         -- as reported, e.g. "1000mg/day" -- free text, don't parse
    duration TEXT,                     -- as reported, e.g. "12 weeks"
    population TEXT,                   -- as reported, e.g. "adults with elevated CRP"

    n_participants INTEGER,
    n_studies INTEGER,                 -- >1 implies a meta-analysis/pooled estimate

    study_design TEXT,                 -- see STUDY_DESIGNS in config.py

    source TEXT NOT NULL,              -- 'EUROPEPMC' | 'COCHRANE' | 'CLINICALTRIALS' | 'PUBMED'
    source_id TEXT,                    -- PMID, DOI, or NCT number
    source_url TEXT,
    source_title TEXT,
    publication_date TEXT,
    retrieved_date DATE,

    extraction_method TEXT,            -- 'llm_extracted' | 'manual'
    extraction_model TEXT,             -- model id/version used, if llm_extracted
    review_status TEXT NOT NULL,       -- AUTO_EXTRACTED | NEEDS_REVIEW | MANUAL_VERIFIED | REJECTED
    review_notes TEXT,
    plausibility_flag TEXT,            -- null | 'outside_nhanes_range' | 'implausible_effect_size'

    created_at TIMESTAMP
);
"""

# One row per (biomarker, age-cohort, sex) showing the resulting shifted
# distribution/HR after applying a MANUAL_VERIFIED effect -- built by
# combining biomarker_intervention_effects with the existing NHANES
# distribution + hazard_curves.predict_hr_curve, not by ingestion. Defined
# here for completeness since it's the payoff of this whole layer.
INTERVENTION_IMPACT_TABLE = """
CREATE TABLE intervention_hazard_impact (
    impact_id TEXT PRIMARY KEY,
    biomarker_id TEXT NOT NULL,
    intervention_id TEXT NOT NULL,
    effect_id TEXT NOT NULL,           -- which effect estimate this used

    age INTEGER, sex TEXT, race_ethnicity TEXT,

    baseline_value REAL,               -- population median/mean pre-intervention
    shifted_value REAL,                -- baseline_value adjusted by the effect

    hr_baseline REAL,
    hr_shifted REAL,
    hr_ratio REAL,                     -- hr_shifted / hr_baseline -- the headline number

    mortality_model_id TEXT,
    computed_at TIMESTAMP
);
"""

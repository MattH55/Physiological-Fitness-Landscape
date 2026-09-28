"""
SQL DDL for the interventions layer.

DESIGN GOAL: "generality" -- an intervention can be a drug, a device, a
surgical procedure, radiation, a biologic/vaccine, a dietary supplement,
gene therapy, a combination product, a diagnostic test, or (the harder
case) a behavioral intervention -- which itself spans exercise, dietary
patterns, sleep, smoking cessation, mindfulness, etc. A relational table
with a fixed column per intervention-type-specific attribute (dose+route
for drugs, model+manufacturer for devices, modality+intensity+frequency
for exercise, macronutrient targets for a diet) would need a schema
migration every time a new intervention type or attribute shows up. Two
choices avoid that:

1. TOP-LEVEL TYPE = ClinicalTrials.gov's own controlled vocabulary
   (verified current this session against CT.gov's own database
   requirements): Drug, Device, Biological/Vaccine, Procedure/Surgery,
   Radiation, Behavioral, Dietary Supplement, Genetic, Combination
   Product, Diagnostic Test, Other. Adopting this verbatim (not inventing
   a competing taxonomy) means every CT.gov record maps onto it with zero
   translation, which matters since CT.gov is a primary ingestion source
   (see interventions_toolkit/clinicaltrials_client.py).

2. SUBCATEGORY = an open, DATA-driven lookup table (`intervention_
   categories`), not a hardcoded enum -- adding "exercise" or "dietary
   pattern" as first-class subcategories under CT.gov's coarse
   "Behavioral" bucket is an INSERT, not a migration. Seeded with the
   subcategories called out explicitly (pharmaceutical, device, exercise,
   dietary_pattern), but the table is meant to grow.

3. TYPE-SPECIFIC DETAIL = an EAV attributes table (`intervention_
   attributes`), not per-type columns -- a drug's dose/route, a device's
   model/manufacturer, an exercise intervention's modality/intensity/
   frequency, and a dietary pattern's macronutrient targets all fit the
   same (key, value, unit) shape without ever needing a new column.

This mirrors the canonical-entity-vs-raw-source-record pattern already
used for lab tests (lab_tests + lab_test_identifiers +
test_biomarker_review.csv review queue) -- same reasoning here: a
CANONICAL intervention ("metformin", "Mediterranean diet") is a distinct
thing from any one trial's free-text description of what it gave its
participants, and the two are connected through a reviewed mapping, not
assumed identical.
"""

# --- 1. Extensible subcategory lookup (INSERT to add a new one, not a migration) ---

INTERVENTION_CATEGORIES_TABLE = """
CREATE TABLE intervention_categories (
    category_id TEXT PRIMARY KEY,        -- e.g. 'exercise', 'dietary_pattern', 'pharmaceutical_small_molecule'
    label TEXT NOT NULL,                  -- display name
    ct_gov_intervention_type TEXT NOT NULL,  -- the CT.gov top-level bucket this rolls up to --
                                              -- one of: DRUG | DEVICE | BIOLOGICAL | PROCEDURE |
                                              -- RADIATION | BEHAVIORAL | DIETARY_SUPPLEMENT | GENETIC |
                                              -- COMBINATION_PRODUCT | DIAGNOSTIC_TEST | OTHER
    description TEXT,
    created_at TIMESTAMP
);
"""

# Starter seed rows -- INSERT statements, not part of the DDL itself, so
# adding a new category later is the same INSERT pattern, no migration.
INTERVENTION_CATEGORIES_SEED = [
    # (category_id, label, ct_gov_intervention_type)
    ("pharmaceutical", "Pharmaceutical drug", "DRUG"),
    ("biologic_vaccine", "Biologic / vaccine", "BIOLOGICAL"),
    ("medical_device", "Medical device", "DEVICE"),
    ("procedure_surgery", "Procedure / surgery", "PROCEDURE"),
    ("radiation", "Radiation therapy", "RADIATION"),
    ("dietary_supplement", "Dietary supplement / nutraceutical", "DIETARY_SUPPLEMENT"),
    ("genetic_therapy", "Genetic / gene therapy", "GENETIC"),
    ("combination_product", "Combination product", "COMBINATION_PRODUCT"),
    ("diagnostic_test", "Diagnostic test (as intervention)", "DIAGNOSTIC_TEST"),
    # CT.gov files all of these under the single "Behavioral" bucket --
    # split out because the platform explicitly wants to distinguish them.
    ("exercise", "Exercise / physical activity", "BEHAVIORAL"),
    ("dietary_pattern", "Dietary pattern (e.g. Mediterranean, DASH)", "BEHAVIORAL"),
    ("sleep_intervention", "Sleep intervention", "BEHAVIORAL"),
    ("smoking_cessation", "Smoking cessation", "BEHAVIORAL"),
    ("mindfulness_stress", "Mindfulness / stress reduction", "BEHAVIORAL"),
    ("other_behavioral", "Other behavioral intervention", "BEHAVIORAL"),
    ("other", "Other / uncategorized", "OTHER"),
]

# --- 2. Canonical intervention entity ---

INTERVENTIONS_TABLE = """
CREATE TABLE interventions (
    intervention_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,          -- e.g. "metformin", "Mediterranean diet",
                                            -- "moderate-intensity aerobic exercise"
    category_id TEXT NOT NULL,             -- FK -> intervention_categories.category_id
    description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

INTERVENTION_SYNONYMS_TABLE = """
CREATE TABLE intervention_synonyms (
    intervention_id TEXT NOT NULL,
    synonym TEXT NOT NULL,
    synonym_type TEXT,      -- 'brand_name' | 'generic_name' | 'code_name' | 'other'
                             -- (CT.gov itself collects "Other Intervention Names" per this pattern)
    source TEXT,
    PRIMARY KEY (intervention_id, synonym)
);
"""

# --- 3. Type-agnostic structured attributes (EAV -- the generality mechanism) ---

INTERVENTION_ATTRIBUTES_TABLE = """
CREATE TABLE intervention_attributes (
    attribute_id TEXT PRIMARY KEY,
    intervention_id TEXT NOT NULL,
    attribute_key TEXT NOT NULL,    -- free but conventionally namespaced, e.g.:
                                     --   drug:  route, typical_dose, mechanism_class
                                     --   device: manufacturer, model, fda_classification
                                     --   exercise: modality, intensity, frequency_per_week, session_duration_min
                                     --   dietary_pattern: macronutrient_profile, key_foods_emphasized, key_foods_restricted
                                     -- Don't enforce a fixed key vocabulary here -- that's exactly
                                     -- what would force a migration for a new intervention type.
                                     -- DO keep an application-level registry of keys-in-use per
                                     -- category (see build-spec addendum) so free text doesn't
                                     -- fragment into near-duplicate keys.
    attribute_value TEXT,
    attribute_unit TEXT,            -- null for non-numeric attributes
    source TEXT,
    retrieved_date DATE,
    created_at TIMESTAMP
);
"""

# --- 4. Raw per-trial intervention arms, as ingested from ClinicalTrials.gov ---
# (or, later, other registries -- source column keeps this open)

TRIAL_INTERVENTION_ARMS_TABLE = """
CREATE TABLE trial_intervention_arms (
    arm_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                  -- 'CLINICALTRIALS' | (future: other registries)
    source_study_id TEXT NOT NULL,          -- NCT number
    raw_intervention_type TEXT,             -- verbatim CT.gov type as ingested, before mapping
    raw_name TEXT NOT NULL,                 -- verbatim intervention name/title from the registry
    raw_description TEXT,                   -- verbatim (or lightly trimmed) description field
    raw_other_names TEXT,                   -- JSON array -- CT.gov's "Other Intervention Names"
    arm_group_label TEXT,                   -- which arm/group within the study this applies to
    retrieved_date DATE,
    created_at TIMESTAMP
);
"""

# --- 5. Review queue: raw arm -> canonical intervention (same pattern as LOINC mapping) ---

INTERVENTION_ARM_MAPPINGS_TABLE = """
CREATE TABLE intervention_arm_mappings (
    mapping_id TEXT PRIMARY KEY,
    arm_id TEXT NOT NULL,                   -- FK -> trial_intervention_arms.arm_id
    candidate_intervention_id TEXT,         -- FK -> interventions.intervention_id (null if no
                                             -- canonical entity exists yet -- see note below)
    match_method TEXT,                      -- 'exact_name' | 'synonym_match' | 'llm_extracted' | 'manual'
    confidence TEXT,                        -- 'high' | 'medium' | 'low'
    review_status TEXT NOT NULL,            -- AUTO_VERIFIED | MANUAL_VERIFIED | NEEDS_REVIEW | REJECTED
    review_notes TEXT,
    created_at TIMESTAMP
);
"""
# Note: a raw arm with no matching canonical intervention isn't an error --
# it means a new `interventions` row needs to be created first (e.g. a
# never-before-seen supplement combination). Don't force a match to the
# nearest existing entity just to fill the column; create the canonical
# entity and map to it, or leave candidate_intervention_id null with
# review_status=NEEDS_REVIEW until someone does.

# --- 6. Effect estimates -- same shape as before, now referencing the general intervention_id ---

BIOMARKER_INTERVENTION_EFFECTS_TABLE = """
CREATE TABLE biomarker_intervention_effects (
    effect_id TEXT PRIMARY KEY,
    biomarker_id TEXT NOT NULL,
    intervention_id TEXT NOT NULL,          -- FK -> interventions.intervention_id (canonical, not a raw arm)

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

ALL_TABLES = [
    INTERVENTION_CATEGORIES_TABLE,
    INTERVENTIONS_TABLE,
    INTERVENTION_SYNONYMS_TABLE,
    INTERVENTION_ATTRIBUTES_TABLE,
    TRIAL_INTERVENTION_ARMS_TABLE,
    INTERVENTION_ARM_MAPPINGS_TABLE,
    BIOMARKER_INTERVENTION_EFFECTS_TABLE,
    INTERVENTION_IMPACT_TABLE,
]

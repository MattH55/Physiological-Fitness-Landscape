# Coding Agent Implementation Instructions

## Physiological Fitness Landscape --- Gap-Filling Implementation

### Objective

Extend the **existing implementation at
`https://landscape.opensourcemed.info`** so that it fully supports the
analytical workflow described in the manuscript *The Value of
Information in Longevity Biomarkers*.

**This is a gap-filling task, not a greenfield rebuild.**

The existing application is the source of truth for the current
architecture, UI conventions, data model, routing, deployment, and
implemented functionality. Before changing anything:

1.  Inspect the existing repository/application structure.
2.  Run the application locally if possible.
3.  Identify what is already implemented.
4.  Map existing functionality to the requirements below.
5.  Implement only missing, incomplete, placeholder, or materially
    incorrect pieces.
6.  Preserve existing behavior unless a change is required to satisfy
    the manuscript workflow.
7.  Do not duplicate existing functionality under a new architecture.

The manuscript explicitly describes the existing dashboard as allowing a
user to select a biomarker and view: - population distributions; - age
and sex toggles; - mortality hazard ratio (or proxy) as a function of
biomarker value; and - expected value of information for each biomarker.

Therefore, treat those capabilities as potentially already implemented
and verify them before modifying them.

------------------------------------------------------------------------

# 1. Target Product

The application should function as an interactive **Physiological
Fitness Landscape** for evaluating the value of measuring
longevity-associated biomarkers.

At minimum, the analytical pipeline should connect:

`Biomarker` → `population distribution` →
`individual/cohort biomarker value` →
`mortality hazard ratio or mortality-risk proxy` →
`expected value of information` → `potential improvement/intervention` →
`expected mortality/YLL benefit` → `test cost` → `willingness-to-pay` →
`value-to-price prioritization`

The system should support cohort-specific analysis, particularly by
**age and sex**, while allowing future expansion to other cohort
variables.

------------------------------------------------------------------------

# 2. First Task: Audit Existing Implementation

Before writing code, produce an internal implementation map.

Inspect:

-   application entry points;
-   routes/pages;
-   existing dashboard components;
-   biomarker schema;
-   biomarker data files/API endpoints;
-   population distribution data;
-   mortality/hazard-ratio data;
-   LOINC mappings;
-   price/test-cost data;
-   age/sex cohort handling;
-   existing VOI calculations;
-   YLL/DALY calculations;
-   charts and visualizations;
-   filtering/sorting;
-   tables;
-   API/data-loading layer;
-   persistence/database;
-   tests;
-   build/deployment configuration.

Create a gap matrix internally:

  --------------------------------------------------------------------------------------------
  Manuscript requirement     Existing          Status                        Required action
                             implementation                                  
  -------------------------- ----------------- ----------------------------- -----------------
  471 biomarker catalogue    inspect           implemented/partial/missing   gap action

  Biomarker categories       inspect           implemented/partial/missing   gap action

  LOINC mapping              inspect           implemented/partial/missing   gap action

  Population distributions   inspect           implemented/partial/missing   gap action

  Age/sex distributions      inspect           implemented/partial/missing   gap action

  Mortality HR/proxy curves  inspect           implemented/partial/missing   gap action

  Cohort-specific VOI        inspect           implemented/partial/missing   gap action

  Monte Carlo VOI            inspect           implemented/partial/missing   gap action

  Intervention/improvement   inspect           implemented/partial/missing   gap action
  assumption                                                                 

  YLL propagation            inspect           implemented/partial/missing   gap action

  Test prices                inspect           implemented/partial/missing   gap action

  Insurance/out-of-pocket    inspect           implemented/partial/missing   gap action
  price                                                                      

  WTP comparison             inspect           implemented/partial/missing   gap action

  Value/price ranking        inspect           implemented/partial/missing   gap action

  Top-five biomarkers by     inspect           implemented/partial/missing   gap action
  cohort                                                                     

  Data provenance            inspect           implemented/partial/missing   gap action

  Test uncertainty           inspect           implemented/partial/missing   gap action

  Intervention evidence      inspect           implemented/partial/missing   gap action
  layer                                                                      
  --------------------------------------------------------------------------------------------

Do not implement a feature simply because it appears in this list if the
current application already does it correctly.

------------------------------------------------------------------------

# 3. Biomarker Data Model

Ensure every biomarker can be represented as a structured record.

Recommended canonical fields:

``` text
biomarker_id
name
display_name
category
subcategory
description
unit
loinc_code
loinc_system
test_name
measurement_type
sample_type
data_source
source_url
distribution_source
mortality_source
price_source
population_scope
available_age_ranges
available_sexes
distribution_model
mortality_model
mortality_proxy
baseline_reference
standard_deviation
normal_range
minimum_value
maximum_value
evidence_quality
last_updated
```

Do not force fields that cannot be supported by the available data. Use
null/unknown states rather than fabricated values.

The manuscript describes six broad source categories:

-   composite
-   blood
-   urine
-   spirometry
-   functional
-   other

Preserve the existing taxonomy if one already exists, and only harmonize
it where necessary.

------------------------------------------------------------------------

# 4. Biomarker Catalogue

The manuscript specifies extraction of **471 biomarkers from
mortalitypredictors.org**.

The implementation should support a complete catalogue rather than a
hand-curated subset.

Requirements:

1.  Preserve a stable internal identifier for every biomarker.
2.  Store the original source identity.
3.  Store category.
4.  Map to LOINC where a defensible mapping exists.
5.  Distinguish:
    -   directly measured biomarkers;
    -   composite scores;
    -   functional measurements;
    -   mortality proxies.
6.  Record whether mortality-risk data exists.
7.  Record whether population-distribution data exists.
8.  Record whether pricing data exists.
9.  Record provenance independently for each data element.

Do not silently infer missing mappings.

------------------------------------------------------------------------

# 5. Data Provenance

Every externally derived analytical value should be traceable to its
source.

At minimum, provenance should support:

``` text
source_name
source_type
source_url
source_identifier
retrieval_date
population
age_range
sex
sample_size
measurement_unit
transformation
statistical_method
notes
```

A biomarker may have different sources for:

-   population distribution;
-   mortality association;
-   price;
-   intervention effectiveness.

These should not be conflated into a single generic source field.

The UI should expose provenance where practical, especially for
research-facing users.

------------------------------------------------------------------------

# 6. Population Distribution Layer

For each biomarker, store or calculate the population distribution.

Support:

-   general population;
-   age-specific cohorts;
-   sex-specific cohorts;
-   age × sex cohorts where data supports it.

The dashboard should be able to answer:

> "Given this user's age and sex, what is the expected distribution of
> this biomarker?"

Distribution data may come from published literature or calculated from
NHANES/public datasets.

Where a raw dataset is used, retain the transformation/calculation
metadata.

Do not assume that a published distribution applies universally.

------------------------------------------------------------------------

# 7. Mortality Association Layer

For each biomarker with sufficient evidence, represent mortality risk as
a function of biomarker value.

Preferred representation:

``` text
HR = f(biomarker_value, cohort)
```

where cohort may include:

``` text
age
sex
other available stratifiers
```

The system must support the reality that literature often reports
mortality associations as:

-   continuous functions;
-   per-unit changes;
-   per-standard-deviation changes;
-   quantile/category comparisons;
-   hazard ratios relative to a reference group.

Normalize these representations into a common internal representation
without destroying the original evidence.

For every mortality model, retain:

``` text
effect_measure
effect_unit
reference_value
reference_group
hazard_ratio
confidence_interval
study_population
follow_up
model_type
adjustment_variables
source
```

If the available evidence is only a proxy for all-cause mortality, label
it explicitly as a proxy.

Never display a mortality HR as though it were direct evidence of
causality.

------------------------------------------------------------------------

# 8. Mortality Curve Visualization

The existing biomarker page should provide, where data permits:

1.  Population distribution.
2.  Mortality HR/risk curve.
3.  Reference/baseline.
4.  User-selected or simulated biomarker value.
5.  Age selector.
6.  Sex selector.
7.  Units and reference ranges.
8.  Evidence/provenance information.

The charts should make clear whether a curve represents:

-   direct published data;
-   a fitted/interpolated curve;
-   a proxy;
-   an internally calculated estimate.

Avoid visual precision that exceeds the underlying evidence.

------------------------------------------------------------------------

# 9. Expected Value of Information

Implement or verify the manuscript's VOI calculation.

The manuscript describes a Monte Carlo approach:

1.  Select an age/sex cohort.
2.  Draw a biomarker value from the cohort population distribution.
3.  Assume the test accurately measures the ground-truth value.
4.  Evaluate mortality hazard associated with that value.
5.  Assume an intervention can improve the biomarker by a specified
    magnitude.
6.  Recalculate mortality risk after improvement.
7.  Estimate expected mortality benefit.
8.  Propagate that benefit into YLL/DALY value.
9.  Repeat across simulations.
10. Aggregate to expected value.

Core conceptual quantity:

``` text
VOI ≈ E[value after information + action]
       − E[value without information/action]
```

The exact existing implementation should be inspected before replacing
or adding a formula.

------------------------------------------------------------------------

# 10. Monte Carlo Engine

Where the VOI engine is missing or incomplete, implement a
deterministic, testable simulation service.

Inputs should include:

``` text
biomarker
age
sex
distribution
mortality_function
intervention_effect
number_of_simulations
random_seed
```

Outputs should include:

``` text
expected_baseline_risk
expected_post_intervention_risk
expected_risk_reduction
expected_YLL_saved
uncertainty_interval
simulation_metadata
```

Use a configurable random seed for reproducibility.

Do not hard-code a single intervention effect globally.

------------------------------------------------------------------------

# 11. Intervention / Improvement Assumption

The manuscript currently uses a simplifying assumption that an
individual can improve the marker by **one standard deviation**.

Represent this as a configurable parameter:

``` text
intervention_effect_sd = 1.0
```

Support future values such as:

``` text
0.25 SD
0.50 SD
1.00 SD
1.50 SD
```

Do not present the one-SD assumption as evidence that a real
intervention can achieve that improvement.

The UI should clearly label it as a modeling assumption.

------------------------------------------------------------------------

# 12. Test Measurement Uncertainty

The manuscript identifies test inaccuracy as a current limitation.

Do not make measurement error a blocker for the initial implementation
if the current application assumes perfect measurement.

Instead:

1.  Preserve the existing perfect-measurement model if that is already
    implemented.
2.  Make the measurement-error layer extensible.
3.  Define an interface such as:

``` text
observed_value ~ MeasurementModel(true_value, test_characteristics)
```

Future implementations should be able to incorporate:

-   analytical sensitivity;
-   analytical specificity;
-   coefficient of variation;
-   standard error;
-   false-positive/negative behavior;
-   device-specific measurement error.

Clearly label the current model as assuming accurate measurement.

------------------------------------------------------------------------

# 13. YLL / DALY Propagation

The manuscript proposes converting a biomarker-associated mortality
hazard ratio into expected years of life lost.

Implement this as a separate service rather than embedding it inside
chart components.

Conceptually:

``` text
biomarker value
→ mortality hazard ratio
→ age-specific mortality risk
→ survival/life expectancy model
→ expected YLL
```

Inputs:

``` text
age
sex
baseline mortality
hazard ratio
life-table/model parameters
```

Outputs:

``` text
expected_life_years
expected_YLL
incremental_YLL
```

The manuscript contains an unresolved placeholder for the specific YLL
model. Do not invent the missing model silently.

If the existing implementation already uses a model, preserve it and
document it.

If no model exists, create an abstraction:

``` text
LifeExpectancyModel
```

with a clearly identified placeholder implementation or configuration
requiring a future evidence-backed model.

------------------------------------------------------------------------

# 14. Cohort Dependence

VOI must be cohort-dependent.

At minimum, support:

-   age;
-   sex.

Design the data model so it can later support:

-   ethnicity;
-   baseline health status;
-   genetics;
-   other clinically meaningful risk strata.

Do not create unsupported stratified estimates simply because the schema
allows them.

The core calculation should therefore conceptually be:

``` text
VOI = f(biomarker, age, sex, distribution, mortality model, intervention effect)
```

rather than a single universal biomarker score.

------------------------------------------------------------------------

# 15. Biomarker Prioritization

Create/verify a ranking layer that can produce:

> "Which biomarkers have the highest modeled value for this cohort?"

For each age × sex cohort:

1.  Calculate VOI/YLL for eligible biomarkers.
2.  Exclude biomarkers lacking sufficient inputs.
3.  Rank descending.
4.  Display the top five.
5.  Show the inputs driving the ranking.

Ranking should support at least:

-   expected YLL;
-   expected mortality-risk reduction;
-   test cost;
-   value-to-price ratio.

Avoid presenting a ranking as a clinical recommendation.

Label it as a modeled prioritization.

------------------------------------------------------------------------

# 16. Cost / Price Layer

The manuscript specifies extraction of test price data from
**findalabtest.com**.

Integrate/verify a test-price data layer.

Support:

``` text
test_price
insurance_price
out_of_pocket_price
currency
price_source
retrieval_date
test_name
biomarker_mapping
```

Important:

-   Distinguish biomarker from commercial test.
-   One biomarker may have multiple tests.
-   One panel may measure multiple biomarkers.
-   Panel pricing should not automatically be assigned to each biomarker
    without a defined allocation method.

If the current application already has pricing, preserve its model and
improve mapping only where necessary.

------------------------------------------------------------------------

# 17. Willingness-to-Pay

Implement/verify the health-economic comparison.

Inputs:

``` text
expected_YLL_saved
willingness_to_pay_per_DALY_or_QALY
test_price
intervention_effectiveness
```

Support scenario analysis for different intervention effectiveness
assumptions.

For example:

``` text
10%
25%
50%
75%
100%
```

These are modeling scenarios, not claims about actual intervention
effectiveness.

The implementation should make the distinction explicit.

------------------------------------------------------------------------

# 18. Value-to-Price Ratio

Provide a cohort-specific economic ranking.

Conceptually:

``` text
economic_value = expected_health_benefit × WTP
value_to_price = economic_value / test_cost
```

Allow the exact valuation unit to follow the existing implementation.

Display:

-   health benefit;
-   economic value;
-   test cost;
-   value-to-price ratio;
-   intervention-effect assumption.

Do not rank tests solely by biological association.

------------------------------------------------------------------------

# 19. Dashboard Requirements

The existing dashboard should be enhanced only where gaps exist.

A biomarker detail view should support:

### Biomarker identity

-   Name
-   Category
-   Description
-   Unit
-   LOINC mapping
-   Test availability

### Population

-   Distribution
-   Age
-   Sex
-   Cohort selection

### Mortality association

-   HR/risk curve
-   Reference
-   Confidence interval where available
-   Source/evidence

### VOI

-   Expected VOI
-   Expected risk reduction
-   Expected YLL
-   Intervention-effect assumption
-   Simulation uncertainty

### Economics

-   Test cost
-   WTP
-   Economic value
-   Value-to-price ratio

### Evidence

-   Distribution source
-   Mortality source
-   Price source
-   Data limitations

------------------------------------------------------------------------

# 20. Global Biomarker Ranking View

The manuscript describes a global analysis moving from the individual to
population perspective.

Add this only if absent.

Provide a ranking/table across biomarkers with filters for:

-   age;
-   sex;
-   biomarker category;
-   evidence availability;
-   price availability.

Useful columns:

``` text
Biomarker
Category
LOINC
Expected YLL
Expected VOI
Test Price
Value/Price
Evidence Status
```

Allow sorting by each quantitative metric.

------------------------------------------------------------------------

# 21. Population-Level Analysis

Where data supports it, provide a population-level summary.

The distinction must be maintained between:

### Individual VOI

Value to a person who obtains the measurement and can act on it.

### Population value

Aggregate potential value across a defined population.

Population calculations should require explicit population assumptions:

``` text
population_size
age_distribution
sex_distribution
biomarker_prevalence/distribution
test_uptake
intervention_uptake
intervention_effectiveness
```

Do not extrapolate individual VOI to a national population without these
assumptions.

------------------------------------------------------------------------

# 22. Intervention Evidence Layer --- Future-Ready

The manuscript explicitly identifies intervention linkage as a future
improvement.

Design the application so biomarkers can eventually link to:

``` text
biomarker
→ intervention
→ intervention evidence
→ expected biomarker change
→ health outcome
```

Potential future evidence sources include clinical trials and
meta-analyses.

The manuscript specifically identifies ClinicalTrials.gov as a possible
systematic source.

Do not fabricate intervention mappings in this implementation.

Instead:

-   create the schema/interface;
-   identify missing mappings;
-   expose "intervention evidence unavailable" where appropriate.

------------------------------------------------------------------------

# 23. ClinicalTrials.gov / Evidence Integration Architecture

If the existing application already has an evidence-ingestion layer,
extend it rather than replacing it.

Future records should support:

``` text
trial_id
biomarker
intervention
population
baseline_value
post_intervention_value
effect_size
confidence_interval
duration
study_design
source
```

The goal is eventually to replace the simplifying "1 SD improvement"
assumption with evidence-based intervention distributions.

------------------------------------------------------------------------

# 24. Handling Missing Data

Missingness is expected.

Use explicit states:

``` text
available
partial
not_available
not_applicable
insufficient_evidence
```

Do not:

-   substitute generic population data without labeling it;
-   invent a mortality curve;
-   infer an intervention effect;
-   infer a test price;
-   silently extrapolate across cohorts.

The UI should distinguish "no evidence found" from "biomarker has no
mortality association."

------------------------------------------------------------------------

# 25. Evidence Quality and Confidence

Add an evidence-status layer if absent.

At minimum:

``` text
mortality_evidence
distribution_evidence
intervention_evidence
price_evidence
```

Each can be:

``` text
strong
moderate
limited
proxy
missing
```

This is primarily a metadata layer. Do not invent numerical evidence
scores unless the project already defines one.

------------------------------------------------------------------------

# 26. Reproducibility

All computed analytical outputs should be reproducible.

Store or expose:

-   source dataset/version;
-   source retrieval date;
-   model version;
-   calculation version;
-   simulation count;
-   random seed;
-   intervention-effect assumption;
-   cohort definition.

If the application has a versioned data pipeline, integrate with it.

------------------------------------------------------------------------

# 27. API / Calculation Separation

Keep analytical calculations out of UI components.

Preferred conceptual modules:

``` text
biomarkers/
  catalogue
  distributions
  mortality
  provenance

voi/
  simulation
  intervention
  measurement_error

health_economics/
  yll
  daly
  wtp
  pricing
  ranking

evidence/
  sources
  quality
```

Adapt this structure to the existing application rather than forcing a
new framework.

------------------------------------------------------------------------

# 28. Performance

The dashboard may eventually contain hundreds of biomarkers and multiple
cohort combinations.

Do not run expensive Monte Carlo calculations on every UI render.

Prefer:

1.  Precompute stable population-level outputs where possible.
2.  Cache cohort-specific calculations.
3.  Calculate interactive scenario changes client-side only when
    inexpensive.
4.  Use deterministic seeds.
5.  Avoid repeatedly fetching identical source data.
6.  Consider Web Workers/background computation for large client-side
    simulations if appropriate to the existing stack.

------------------------------------------------------------------------

# 29. Validation Tests

Add automated tests for the analytical layer.

At minimum test:

### Distribution

-   sampling from a known distribution;
-   cohort selection;
-   missing cohort behavior.

### Mortality

-   HR at reference value;
-   monotonicity where the source model is monotonic;
-   interpolation;
-   out-of-range behavior.

### VOI

-   zero intervention effect → zero incremental benefit;
-   identical baseline/post-intervention value → zero benefit;
-   increasing intervention effect → non-decreasing modeled benefit;
-   deterministic output with fixed random seed.

### YLL

-   zero mortality difference → zero incremental YLL;
-   increased mortality hazard → increased YLL;
-   age changes produce sensible cohort-dependent results.

### Economics

-   zero price handling;
-   higher health value increases value-to-price;
-   higher price decreases value-to-price.

### Ranking

-   deterministic ordering;
-   missing data excluded appropriately;
-   cohort changes can change rankings.

------------------------------------------------------------------------

# 30. UI Guardrails

The product is an analytical/research dashboard, not a diagnostic
system.

Avoid UI language such as:

-   "You will live X years longer."
-   "This test will prevent death."
-   "You should take intervention X."

Prefer:

-   "Modeled expected YLL"
-   "Association with all-cause mortality"
-   "Modeled value under stated assumptions"
-   "Evidence source"
-   "Intervention effect assumed at 1 SD"
-   "Not a clinical recommendation"

Make clear when the result is based on observational mortality
association.

------------------------------------------------------------------------

# 31. Priority Order

Implement gaps in this order:

### P0 --- Core analytical correctness

1.  Audit existing implementation.
2.  Ensure biomarker schema is coherent.
3.  Ensure population distributions are correctly represented.
4.  Ensure mortality associations are correctly represented.
5.  Verify cohort selection.
6.  Verify/implement VOI calculation.
7.  Verify/implement YLL propagation.
8.  Add reproducible calculation tests.

### P1 --- Economic layer

9.  Verify test pricing.
10. Map prices to actual tests.
11. Implement/verify WTP.
12. Implement/verify value-to-price ranking.
13. Implement top-five cohort rankings.

### P2 --- Evidence/provenance

14. Improve provenance.
15. Add evidence-quality metadata.
16. Surface source information in the UI.
17. Track model/calculation versions.

### P3 --- Future analytical depth

18. Measurement-error model.
19. Intervention evidence layer.
20. ClinicalTrials.gov linkage.
21. Evidence-based intervention-effect distributions.
22. Population-level policy analysis.

------------------------------------------------------------------------

# 32. Important Manuscript Limitations to Preserve

The implementation must explicitly preserve the manuscript's stated
limitations.

The current conceptual model does **not** fully account for:

-   test inaccuracy;
-   a realistic intervention layer;
-   evidence-based intervention effectiveness.

The manuscript specifically identifies these as areas for further work.

Do not hide these limitations behind polished UI.

------------------------------------------------------------------------

# 33. Definition of Done

The task is complete when:

-   the existing application has been audited;
-   every manuscript requirement has been mapped to an existing feature
    or identified gap;
-   only necessary gaps have been implemented;
-   biomarker → distribution → mortality → VOI → YLL → economics is a
    coherent pipeline;
-   age and sex materially affect cohort-specific outputs where data
    supports them;
-   rankings can be generated for cohorts;
-   pricing can be compared with modeled health-economic value;
-   provenance is retained;
-   assumptions are visible;
-   missing data is explicit;
-   calculations are reproducible;
-   analytical functions have automated tests;
-   existing functionality has not been unnecessarily rewritten;
-   the dashboard remains usable and performant.

## Final Agent Report

After implementation, report:

1.  What already existed.
2.  What was missing.
3.  What was implemented.
4.  Files/modules changed.
5.  Data sources used.
6.  Analytical assumptions introduced or preserved.
7.  Tests added and their results.
8.  Remaining manuscript requirements that cannot yet be implemented
    because the necessary data/model is unavailable.
9.  Any places where the manuscript itself leaves an unresolved
    methodological choice.

**Do not claim a manuscript requirement is implemented merely because a
UI element exists. Verify the underlying calculation/data path.**

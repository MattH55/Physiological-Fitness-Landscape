# Physiological Fitness Landscape — Mortality Biomarker Dashboard
## Build Specification for a Coding Agent

## 1. Objective
Build a database-backed web dashboard that, for each biomarker of all-cause mortality:
1. Shows the distribution of published hazard ratios (HRs) across studies
2. Shows the distribution of that biomarker's values in the general population
3. Overlays (1) and (2) so a user can see where in the population distribution mortality risk rises
4. Lists interventions that favorably shift the biomarker, and factors that unfavorably shift it
5. Lets users compare biomarkers side by side and filter/sort by effect size, category, evidence volume

This generalizes two existing published pilots (blood biomarkers and urine biomarkers papers by
the project owner) to the full range of physiological/mortality biomarkers.

## 2. Data model
Implement as a relational schema (Postgres or SQLite for v1) with these tables:

- `biomarker(id, name, aliases[], category, units, measurement_method, specimen_type, notes)`
- `source(id, citation, pmid, doi, url, year, study_design)`
- `mortality_association(id, biomarker_id FK, source_id FK, hazard_ratio, hr_type
  ['per_unit','per_sd','quartile_extreme','tertile_extreme','per_log_unit'], ci_lower, ci_upper,
  p_value, direction ['higher_worse','lower_worse','u_shaped'], cohort_description, n,
  follow_up_years, population_type ['general','patient_subgroup'], adjustment_covariates, notes)`
- `population_distribution(id, biomarker_id FK, source_id FK, sex ['M','F','all'],
  age_band, mean, sd, p5, p25, p50, p75, p95, unit, sample_n)`
- `intervention(id, biomarker_id FK, source_id FK, direction ['favorable','unfavorable'],
  category ['diet','exercise','pharmacologic','sleep','supplement','environmental','behavioral'],
  description, quantified_effect, evidence_strength ['RCT','cohort','meta-analysis','mechanistic'])`

Every numeric claim must carry a `source_id` — no unsourced HRs or distribution values.

### 2.1 Disease-state / combined-biomarker signatures
In addition to single-biomarker mortality associations, the resource should characterize
disease and physiological states (e.g. allostatic load, metabolic syndrome, frailty,
biological age) as combinations of biomarker alterations. Add:

- `condition(id, name, icd10_code, category ['metabolic','cardiovascular','frailty',
  'infectious','neuroendocrine','composite_aging_score'])`
- `biomarker_signature(id, condition_id FK, biomarker_id FK, source_id FK,
  panel_name, direction ['elevated','reduced'], cutoff_value, cutoff_type
  ['percentile','absolute','sd'], weight, scoring_method
  ['count_based','weighted_composite','regression'])`

Important design constraint: the same condition (e.g. "allostatic load") legitimately has
*multiple, competing, published panels* with different biomarker sets, cutoffs, and scoring
methods (a 2026 specification-curve analysis found at least 18 distinct AL calculation
methods across 26 biomarkers in the literature, with materially different HRs depending on
panel/scoring choices). Do not collapse these into one canonical row — store each published
panel as its own set of `biomarker_signature` rows keyed to `panel_name` + `source_id`, and
let the UI show "N published ways to score this condition" rather than silently picking one.
This applies to allostatic load, frailty indices, and any other composite score with more
than one published operationalization.

Seed examples to start this table: MacArthur AL-10 (allostatic load), ATP III metabolic
syndrome criteria, and Levine's PhenoAge (biological age clock) — see `/data/seed/conditions/`
for draft rows.

### 2.2 Continuous functions (required for the Monte Carlo module, section 7)
The `population_distribution` and `mortality_association` tables above store discrete
summary statistics (percentiles, categorical HRs). The Monte Carlo module needs continuous,
sampleable functions derived from these. Add two derived/fitted tables rather than computing
fits on the fly at simulation time — fits should be reviewed, versioned, and cached:

- `distribution_fit(id, biomarker_id FK, sex, age_band, fit_type
  ['empirical_ecdf','kde','lognormal','normal','johnson_su'], parameters (JSON),
  domain_min, domain_max, source_id FK, fit_quality_note)`
  - Preferred: build directly from raw NHANES microdata (empirical ECDF or KDE) when available
    — do not assume normality for skewed biomarkers (CRP, triglycerides, etc.).
  - Fallback: when only summary percentiles are available (from a paper, not raw data), fit a
    parametric family via quantile-matching (minimize squared error between the fitted
    distribution's p5/p25/p50/p75/p95 and the reported ones). Flag these as lower-confidence
    than empirical fits (`fit_quality_note`).

- `hr_function(id, biomarker_id FK, fit_type
  ['log_linear_per_sd','log_linear_per_unit','monotonic_spline_categorical',
  'digitized_dose_response'], parameters (JSON), domain_min, domain_max, reference_value,
  shape ['monotonic_increasing','monotonic_decreasing','u_shaped'], source_id FK,
  fit_quality_note)`
  - Priority order when multiple source types exist for a biomarker: published dose-response
    meta-analysis curve > categorical (quartile/quintile) HRs fit with a monotonic spline
    (use monotonic cubic interpolation, e.g. PCHIP, not a plain cubic spline, to avoid
    non-physical oscillation or dips below HR=1 between data points) > single per-SD linear
    estimate (weakest — assumes log-linearity, flag as such).
  - `domain_min`/`domain_max` must be set to the actual range covered by the source data.
    The simulation module (section 8) must not evaluate `hr_function` outside this range —
    treat as a hard extrapolation guard, not a soft warning.
  - For `u_shaped` curves, the fit must expose a queryable nadir (`argmin` of the fitted
    function within domain) — this becomes the biomarker's data-derived optimal value.
  - Work in log(HR) space when fitting/interpolating, since HRs are multiplicative — averaging
    or interpolating raw HR values (rather than log HR) produces biased midpoints.

## 3. Data acquisition pipeline (build in this order)

### Phase 1 — Seed from existing curated sources
- Extract the biomarker/HR/distribution/intervention tables directly from the project owner's own
  two prior publications (blood biomarker and urine biomarker mortality papers) as the first
  populated rows — these already match the target schema closely.
- Pull associations from MortalityPredictors.org for the same biomarkers to cross-check and expand
  HR coverage. Since the site disallows automated scraping, use its manual export/download
  interface rather than a scraper; store the raw export in `/data/raw/mortalitypredictors/` with a
  timestamp, then write a normalization script that maps their columns to the schema above.

### Phase 2 — Population distributions
- Write an NHANES ETL script (NHANES public-use datasets are `.XPT` files, downloadable via
  `https://wwwn.cdc.gov/nchs/nhanes/`) that, per biomarker, extracts sex- and age-stratified
  mean/SD/percentiles across available cycles.
- Where NHANES doesn't cover a biomarker, fall back to reference ranges reported in the source
  papers themselves.

### Phase 3 — Expand association + intervention coverage
- For biomarkers not yet covered by the two seed papers, run a semi-automated PubMed literature
  search per biomarker (query pattern: `"<biomarker>" AND "all-cause mortality" AND
  ("hazard ratio" OR "cohort")`), surface candidate studies to a human reviewer for
  inclusion/exclusion (do not auto-ingest extracted numbers without review — HRs are easy to
  misparse from abstracts), then structured-extract HR, CI, cohort size, follow-up into the schema.
- Repeat with an intervention-focused query pattern
  (`"<biomarker>" AND ("intervention" OR "randomized") AND ("exercise" OR "diet" OR "supplement")`)
  to populate the `intervention` table.
- Log every extraction with source_id — this becomes an audit trail, not just a data dump.

### Phase 4 — QA
- Flag biomarkers where HR direction disagrees across studies (e.g., some report higher-worse,
  others u-shaped) for manual review rather than silently averaging.
- Flag population distributions with sample_n below a threshold (e.g., 500) as low-confidence.

## 4. Backend
- Language: Python (FastAPI) or Node (Express) — pick whichever the existing OSMF stack uses for
  consistency with other resources (RepurpOS, Vaccine Data Navigator, etc.).
- Expose REST endpoints:
  - `GET /biomarkers` — list with category/search filters
  - `GET /biomarkers/{id}` — full detail: associations, distribution, interventions, sources
  - `GET /biomarkers/{id}/hr-distribution` — array of HRs with CIs for chart rendering
  - `GET /biomarkers/{id}/population-distribution` — percentile data for chart rendering
  - `GET /compare?ids=1,2,3` — side-by-side comparison payload

## 5. Frontend / dashboard
- Biomarker index page: sortable/filterable table (category, evidence count, max HR, direction).
- Biomarker detail page:
  - HR forest-plot-style chart: one row per study, point estimate + CI, color-coded by direction
  - Population distribution histogram/violin plot with percentile markers, overlaid with a risk
    gradient (color intensity mapped to HR at that value range) — this is the key "landscape" view
  - Two-column list: Interventions to favor / Factors to avoid, each linked to its source
  - Citation list for full traceability
- Comparison view: select 2–6 biomarkers, show normalized HR-per-SD side by side.
- Condition detail page: for a selected condition (e.g. allostatic load, metabolic syndrome),
  show each published panel side by side (panel_name, source, biomarker list with
  direction/cutoffs), and link each component biomarker through to its own biomarker detail
  page. Do not merge panels into a single displayed score.
- Every chart element must be clickable through to its source citation — no bare numbers.

## 6. Non-negotiables
- Every HR, distribution statistic, and intervention claim traces to a `source_id` with a
  resolvable citation (PMID/DOI preferred).
- Distinguish HR types explicitly in the UI (per-unit vs per-SD vs quartile-extreme) — these are
  not comparable without normalization, and the comparison view must normalize before overlaying.
- Do not conflate association with causation in UI copy, especially for the intervention layer
  (observational vs RCT evidence should be visually distinguished, e.g. by the evidence_strength
  field).
- Version and timestamp every data pull (NHANES cycle, MortalityPredictors export date) so the
  resource can be refreshed without silently changing historical values.

## 7. Value-of-information Monte Carlo module

### 7.1 What this answers
For a given biomarker: if a person gets tested, learns their value, and then takes action
to shift it favorably by a realistic amount, how much expected mortality-hazard benefit does
that produce — and how does that compare to *not* testing (acting blind)? This frames "value
of the test" specifically as the benefit of a **personalized, targeted** shift (informed by
knowing your own starting point) versus an **untargeted** shift or no action.

### 7.2 Shift-magnitude rule
For each simulated individual with baseline value `x0`:
```
favorable_direction = sign implied by hr_function.shape and x0's position
                       (toward lower values if monotonic_decreasing-risk-with-lower-value etc.;
                        toward the nadir if u_shaped)
x_target  = the data-derived optimum:
            - u_shaped: the fitted nadir (argmin of hr_function)
            - monotonic: the domain boundary in the favorable direction
              (domain_min or domain_max of hr_function — i.e. the most extreme value actually
              supported by data, NOT an unbounded extrapolation)
distance_to_target = |x_target - x0|
shift = favorable_direction * min( 1 * SD_of_distribution, distance_to_target )
x1 = clip( x0 + shift, hr_function.domain_min, hr_function.domain_max )
```
This is the "1 SD, or less if you're already close to optimal" rule as specified — implemented
so it never overshoots the nadir (for U-shaped biomarkers, overshooting past the nadir would
make things worse, which the cap must prevent) and never proposes a target outside the range
the HR function is actually fitted on (for monotonic biomarkers, this is what keeps "improve
forever" from being simulated as unboundedly beneficial — the practical ceiling is the most
extreme value with empirical support, not infinity).

`SD_of_distribution` should come from `distribution_fit` for the same age/sex stratum as the
draw, not a pooled population SD, when stratified fits are available.

### 7.3 Simulation algorithm
```
for i in 1..N:
    draw age_band, sex per target population composition (or fix if simulating a specific stratum)
    x0 = sample from distribution_fit(biomarker, sex, age_band)
    HR0 = hr_function(x0)                      # baseline hazard at draw
    x1 = apply shift-magnitude rule (8.2) to x0
    HR1 = hr_function(x1)                      # hazard after targeted shift
    log_delta_i = log(HR0) - log(HR1)          # positive = benefit
store log_delta_i for all i
```
Report, across the N draws:
- Mean and median relative risk reduction (`1 - exp(-mean(log_delta_i))` or similar,
  state the transform explicitly in the UI)
- Full distribution of `log_delta_i` (histogram) — this is expected to be right-skewed: people
  starting near the population median with a flat local HR curve gain little, people starting
  in an unfavorable tail gain much more. Showing this spread, not just the mean, is the point —
  it demonstrates *for whom* the test is informative.
- Fraction of simulated draws with `x0` already within one `distance_to_target` of optimal
  (i.e., testing would mostly confirm "you're fine, no action needed" for this slice) —
  report this explicitly, since it's also informational value.

### 7.4 The actual "value of information" comparison
Run two policies and compare their aggregate outcomes over the same N draws:
- **Blind policy** (no test): apply a single population-average shift (or no shift) to
  everyone regardless of their true `x0` — you don't know who's already optimal and who isn't.
- **Informed policy** (test then act): apply the per-individual capped shift from 8.2, which
  requires knowing `x0`.

The gap between the two policies' aggregate expected hazard reduction is the quantity actually
attributable to *testing* (i.e., the information), separate from the benefit of the underlying
intervention itself. Implement this as a second output panel alongside the single-policy
simulation in 8.3.

### 7.5 Required interpretive caveats (must appear in the UI, not just documentation)
- The `hr_function` curves are built from observational epidemiology in the large majority of
  cases. Simulating "move x0 to x1 and get HR1" assumes the observed value-hazard association
  is causal and that the *intervention-driven* change in the biomarker carries the same
  hazard reduction as the *naturally-occurring* cross-sectional difference the HR was
  estimated from — this is not guaranteed (confounding by indication, reverse causation, and
  the surrogate-outcome problem all apply). Where the `intervention` table's
  `evidence_strength` for shifting this biomarker is RCT-backed, note that as higher
  confidence; where it's observational/mechanistic only, the simulated benefit should be
  labeled as an epidemiologically-implied upper bound, not an expected causal benefit.
- Do not present the simulation output as a personalized medical prediction. Frame it as an
  illustration of population-level informational value, consistent with the tone used
  elsewhere in the resource (association ≠ causation, per section 6).

## 8. Suggested build order for the agent
1. Schema + migrations
2. Seed loader for the two existing papers' data (fastest path to a working demo)
3. NHANES ETL for population distributions of those same seeded biomarkers
4. Frontend detail page for a single biomarker, end to end, before scaling to many
5. Index + comparison views
6. Literature-search-assisted expansion pipeline (Phase 3 above) once the core UI is proven

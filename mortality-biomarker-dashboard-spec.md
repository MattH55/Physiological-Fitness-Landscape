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

## 7. Suggested build order for the agent
1. Schema + migrations
2. Seed loader for the two existing papers' data (fastest path to a working demo)
3. NHANES ETL for population distributions of those same seeded biomarkers
4. Frontend detail page for a single biomarker, end to end, before scaling to many
5. Index + comparison views
6. Literature-search-assisted expansion pipeline (Phase 3 above) once the core UI is proven

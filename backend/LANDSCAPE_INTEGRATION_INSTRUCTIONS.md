# Coding Agent Instructions: Integrating This Session's Work into `landscape.opensourcemed.info`

## What exists and where it currently lives

Over this build session, five largely independent pieces were built, tested
against synthetic/mocked data (network access to cdc.gov, clinicaltrials.gov,
and ebi.ac.uk was not available in the build sandbox — see each module's own
"what's tested" notes), and delivered as standalone files. None of them are
wired into the live platform yet. This doc is the wiring instructions.

1. **`nhanes_toolkit/`** — NHANES ingestion, distributions, age/sex/race-
   varying Cox+spline hazard curves (`hazard_curves.py`), distributional
   testing-priority ranking (`testing_priority.py`, `clinical_bands.py`),
   and the PhenoAge proxy (`phenoage.py`, `phenoage_ingestion.py`,
   `phenoage_curves.py`).
2. **`interventions_toolkit/`** — ClinicalTrials.gov + Europe PMC search,
   LLM-based effect extraction, the general intervention schema
   (`schema.py`), and `impact.py` (applies a verified effect to a hazard
   curve).
3. **`TEST_COST_BUILD_SPEC.md`** — LOINC/CPT/price layer and Expected
   Hazard Information Value (EHIV), including the age/sex hazard-curve
   integration addendum.
4. **`AGE_SEX_HAZARD_CURVE_INTEGRATION.md`** — diagnosis + fix for age/sex
   curves not appearing in the API/frontend.
5. **`COVERAGE_GAP_SEARCH_INSTRUCTIONS.md`** — systematic search process
   for biomarkers missing a distribution and/or HR curve.

## 1. Repository layout

Land the two toolkits as top-level packages (or a shared `libs/` if the
platform already has one), not inside a single service's directory —
`nhanes_toolkit` in particular will be imported by at least three things:
the distribution/HR ingestion pipeline, the testing-priority endpoint, and
the PhenoAge proxy endpoint.

```
landscape/
  libs/
    nhanes_toolkit/          # as delivered
    interventions_toolkit/   # as delivered
  services/
    ingestion/                # cron/batch jobs, imports from libs/
    api/                       # request handlers, imports from libs/
  migrations/                 # SQL from schema.py files, versioned normally
```

## 2. Database migrations

Run, in this order (later ones reference earlier ones' tables):

1. `nhanes_toolkit` doesn't define SQL itself — it's the source of the
   Python objects (`RcsCoxResult`, distribution summaries) that get
   persisted. Create the storage tables per the age/sex integration spec:
   `hazard_curve_points` (§2 of `AGE_SEX_HAZARD_CURVE_INTEGRATION.md`).
2. `TEST_COST_BUILD_SPEC.md` §5 — `lab_tests`, `lab_test_identifiers`,
   `test_billing_codes`, `test_prices`, `test_cost_summary`,
   `biomarker_test_value`.
3. `interventions_toolkit/schema.py` — `ALL_TABLES`, in the order given
   (categories → interventions → synonyms/attributes → trial arms →
   mappings → effects → impact). Seed `intervention_categories` from
   `INTERVENTION_CATEGORIES_SEED` immediately after creating that table.
4. A `biomarker_coverage_audit` table per `COVERAGE_GAP_SEARCH_INSTRUCTIONS.md`
   §5, plus `distribution_status`/`hr_curve_status` columns on whatever
   table is the canonical biomarker catalog.

Write a migration test that creates all tables in a fresh test database and
inserts one row into each — the same style of check already used to verify
`interventions_toolkit/schema.py` (an in-memory sqlite round-trip). Catching
an FK/type mismatch here is much cheaper than catching it in production
ingestion.

## 3. Ingestion pipeline (batch/cron)

Four jobs, each idempotent and independently re-runnable:

- **`nhanes_distribution_refresh`** — for every biomarker in
  `nhanes_toolkit.config.BIOMARKERS`, run `pool_cycles` +
  `stratified_summary`, write to whatever table backs the distribution
  view. Also run `racial_difference_tests` and `testing_priority_report`
  and cache their output — these are cheap relative to model fitting and
  don't need to be computed per-request.
- **`hazard_curve_refresh`** — per biomarker, per sex: `fit_rcs_cox(...,
  age_interaction=True)`, check events-per-coefficient (~15:1), set
  `curve_specificity` accordingly, precompute the `hazard_curve_points`
  grid per `AGE_SEX_HAZARD_CURVE_INTEGRATION.md` §2. This is the fix for
  the "hazard ratios not showing per age/sex cohort" issue from earlier —
  if this job silently fits without `age_interaction=True`, that bug comes
  right back.
- **`phenoage_proxy_refresh`** — for biomarkers that fail (or aren't
  attempted for) `hazard_curve_refresh`: run `pool_phenoage_inputs`, join
  to the biomarker's own NHANES pull on `(seqn, cycle)`,
  `phenoage_acceleration`, then `fit_phenoage_accel_curve`. See §5 below
  for exactly when this job should run instead of / in addition to the
  real HR pipeline.
- **`intervention_search_refresh`** — per biomarker,
  `search_orchestrator.search_biomarker` + `extraction.extract_batch`,
  landing in the review CSVs/tables. Keep this on a slower cadence (weekly/
  monthly) — it's the most API-call-heavy job and the least time-sensitive
  (literature doesn't change daily).

## 4. API endpoints

Extend (don't replace) the biomarker endpoint contract from
`TEST_COST_BUILD_SPEC.md` §10 and `AGE_SEX_HAZARD_CURVE_INTEGRATION.md` §3:

```
GET /api/biomarkers/{id}                      -- existing: identity, LOINC, test cost
GET /api/biomarkers/{id}/hazard-curve          -- existing (per age/sex integration spec)
GET /api/biomarkers/{id}/distribution          -- new: stratified_summary output
GET /api/biomarkers/{id}/testing-priority      -- new: testing_priority_report output
GET /api/biomarkers/{id}/phenoage-association  -- new: ONLY present when hazard-curve
                                                   isn't available (see §5) -- returns
                                                   predicted_phenoage_accel_years + CI,
                                                   NEVER framed as an HR
GET /api/interventions/{biomarker_id}          -- new: MANUAL_VERIFIED effects only,
                                                   from biomarker_intervention_effects
```

Every response that includes a hazard curve or a PhenoAge association must
carry a `data_type` field (`"mortality_hazard_ratio"` vs
`"phenoage_acceleration_proxy"`) — this is a hard requirement, not a nice-
to-have, given §5 below. The frontend must never render a proxy curve on
the same chart axis/style as a real HR curve without a visibly different
label.

## 5. Decision rule: when to use the PhenoAge proxy instead of a real HR curve

Don't compute both for every biomarker as a matter of course — pick one
per biomarker, in this order:

1. If the biomarker has NHANES coverage AND enough mortality events
   (events-per-coefficient check passes) → use the real Cox/spline HR
   curve. This is always preferred when available.
2. If the biomarker has NHANES coverage but insufficient events for even a
   pooled (non-age/sex-specific) Cox model → still prefer attempting the
   real curve at reduced specificity (`curve_specificity="pooled"`) over
   falling back to the proxy — a low-specificity real HR curve is more
   informative than a high-specificity proxy for a different outcome.
3. If the biomarker has NO NHANES coverage at all (see the audit in
   `NEW_BIOMARKER_COVERAGE_AUDIT.md`) but CAN be measured on a subset of
   NHANES participants who also have full PhenoAge inputs (i.e. it's
   ingestible from a different NHANES-adjacent source, or a research
   cohort that separately published enough data to approximate this) →
   use the PhenoAge proxy.
4. If the biomarker has neither NHANES coverage nor a computable PhenoAge
   association (truly external cohort only, e.g. a Danish or CKD-cohort
   study with no NHANES linkage) → don't force either pipeline. Surface
   whatever categorical HR points the coverage-gap literature search found
   (§3 of `COVERAGE_GAP_SEARCH_INSTRUCTIONS.md`, `hr_reporting_type =
   categorical_quartile`) as a labeled "external cohort finding," clearly
   distinguished from both the NHANES HR curve and the PhenoAge proxy.

Store which path was used per biomarker (`hr_source =
"nhanes_cox_spline" | "phenoage_proxy" | "external_cohort_anchor" |
"none"`) so the frontend and any downstream EHIV calculation
(`TEST_COST_BUILD_SPEC.md` §7) knows what kind of evidence it's building
on. EHIV as originally specified assumes a real Cox HR model
(`hazard_curves.fit_rcs_cox`'s coefficient covariance) — do NOT run the
EHIV simulation against a `phenoage_proxy` or `external_cohort_anchor`
curve without redesigning that calculation first; the uncertainty
propagation assumes a survival model, and a PhenoAge OLS model's
coefficient covariance means something different.

## 6. Frontend

- Biomarker page: distribution chart, hazard-curve or PhenoAge-proxy chart
  (labeled per §5's `hr_source`), testing-priority cohort table, and
  (below a `MANUAL_VERIFIED`-only filter) the interventions tab.
- Interventions tab: group by `intervention_categories.label`, not raw
  CT.gov type — this is exactly why that subcategory table was built
  (exercise and dietary pattern as distinct groups, not buried in a single
  "Behavioral" bucket).
- Never render a `phenoage_proxy` curve with a "reduces mortality by X%"
  framing — enforce the wording constraint from `phenoage_curves.py`'s
  module docstring in the component itself, not just as a docs note.

## 7. Regression tests to add (don't skip these)

1. The age/sex curve-divergence test from `AGE_SEX_HAZARD_CURVE_INTEGRATION.md`
   §3 — two different `age` values must return non-identical curves.
2. A schema round-trip test for every new migration (§2).
3. A test that `phenoage-association` is only ever served for biomarkers
   with `hr_source = "phenoage_proxy"` — i.e. the decision rule in §5 is
   actually enforced server-side, not just documented.
4. A copy/label test asserting no response with `data_type =
   "phenoage_acceleration_proxy"` contains the strings "mortality" or
   "hazard ratio" in any human-readable field — cheap, mechanical, and
   catches exactly the mislabeling risk §5 and §6 both call out.

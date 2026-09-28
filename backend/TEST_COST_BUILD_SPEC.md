# Coding Agent Build Spec: Biomarker Test Cost + Expected Hazard Information Value

## What this extends

`landscape.opensourcemed.info`. Connects each mortality biomarker to a specific
lab test, its billing/terminology codes, observed prices, and (from the
existing NHANES + Cox-spline work) a continuous mortality-HR function, then
computes a purely *informational* (not economic) value for testing.

This is a refinement of an earlier draft of this spec, corrected against
actually-checked sources as of Aug 2026. Where the earlier draft assumed
something that turned out not to exist (a public NHANES-to-LOINC crosswalk,
for instance), that's flagged explicitly below rather than silently fixed,
since it changes what's achievable in phase 1.

```
Biomarker → Lab test → LOINC → Quest test ID → CPT/HCPCS → Market price
    → CMS reimbursement → NHANES distribution → HR(x) → Expected Hazard
    Information Value
```

Do **not** build EVSI, QALYs, or ROI yet — reserve the fields (§29) but stop
at "how much mortality-risk information does this test provide, and what
does it cost."

---

## 0. Corrections to verify before building (read first)

1. **No public NHANES→LOINC crosswalk exists.** I checked NHANES's own lab
   documentation pages and could not find LOINC codes attached to lab
   variables (e.g. `LBXCRP`, `LBXSAL`) in the published docs. LOINC mapping
   for NHANES variables will have to be curated by hand, test by test,
   against LOINC's own search tool — treat every mapping as
   `NEEDS_REVIEW` until a human confirms component/property/system/scale/
   method match. This was already the instruction in §6/§18 below; it's now
   confirmed necessary rather than a defensive default.

2. **LOINC access requires a free Regenstrief account**, even for the
   downloadable table. Bulk table: https://loinc.org/downloads/ (account
   required, no-cost). Search/lookup: https://loinc.org/search/. A FHIR
   terminology server also exists at https://fhir.loinc.org but needs the
   same account credentials via HTTP Basic Auth. Don't hardcode credentials
   in the repo — pull from environment variables and document that a human
   needs to register once.

3. **CPT codes and descriptions are AMA copyrighted.** CMS's own CLFS
   documentation carries this notice explicitly. Storing a bare CPT code as
   an identifier (the way an EHR or billing system does) is normal and
   fine; storing and republishing AMA's *code descriptions* verbatim in a
   public-facing product is a licensing question worth resolving before
   launch, not after. HCPCS (Level II) codes are public domain and don't
   have this issue — prefer HCPCS where a test has both.

4. **CMS CLFS current file location (confirmed working as of this
   writing)**: https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files
   — the CY2026 Public Use File posts in the last week of December 2025, in
   Excel/text/CSV. There's also a "CMS cloud fee file API" mentioned in
   CMS's transmittal but I could not find public API documentation for it in
   this search pass — have the agent check
   https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs
   directly for current API docs before assuming file-download is the only
   path.

5. **CMS private-payer rates/volumes dataset**: confirmed to exist at
   https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/medicare-clinical-laboratory-fee-schedule-private-payer-rates-and-volumes
   — as of the original check, the public dataset reflected the **2018**
   collection period. Verify the current vintage when you pull it; CMS
   collects this periodically (a new period was scheduled to open
   May–July 2026 per CMS's CY2026 update, covering Jan–Jun 2025 data), so a
   more recent cut may be published by the time this is built. Never
   present whatever vintage you get as current-year pricing without the
   collection-period date attached.

6. **Find Lab Tests / "Lab Testing API"** (findlabtest.com) is a real
   direct-to-consumer lab-test marketplace (confirmed via independent
   company-database listings, not just its own site) that resells Quest
   Diagnostics tests with posted prices and Quest test IDs. I could not
   confirm from outside the site whether it publishes a structured feed or
   only rendered HTML, or what its scraping policy is. **Before writing
   `ingest_findlabtest.py`, have the agent fetch and read the site's
   `robots.txt` and any Terms of Service page itself**, and prefer a
   documented API/feed if one exists over HTML scraping. This is a
   from-scratch check, not something to assume either way.

7. **Quest's own test directory** (testdirectory.questdiagnostics.com) is
   worth checking as a second source for test IDs/specimen requirements —
   useful for cross-validating whatever Find Lab Tests reports, rather than
   trusting a single reseller's page as ground truth for a lab's own test
   catalog.

---

## 1. Objective

Build the pipeline above for a starter set of biomarkers (§30), landing on
one number per (biomarker, test, population): **Expected Hazard Information
Value (EHIV)** — how much the biomarker result, given population variability
and model uncertainty, actually moves the predicted mortality HR — shown
*alongside*, never combined with, the test's price.

---

## 2. Ingestion: Find Lab Tests (market price layer)

Create `scripts/ingest_findlabtest.py`. Before writing it: check
`robots.txt` and ToS (see §0.6). Do not crawl recursively — target only the
catalogue page and the search/test pages needed to resolve biomarkers in the
existing Landscape catalogue (the same list as `BIOMARKERS` in the NHANES
toolkit already built for this project).

Extract per test: name, Quest test ID, component(s), price, provider/store,
price date if shown, state restrictions. Save raw responses under
`data/raw/test_prices/findlabtest/YYYY-MM-DD/` (never overwrite historical
pulls), then normalize into the schema below.

## 3. Ingestion: CMS CLFS

Create `scripts/ingest_cms_clfs.py` pulling from the URL in §0.4. Output raw
to `data/raw/test_prices/cms_clfs/`, normalized into `test_prices` with
`source = CMS_CLFS`, `price_type = MEDICARE_ALLOWED`.

## 4. Ingestion: CMS private-payer rates

Create `scripts/ingest_cms_private_payer.py` pulling from the dataset in
§0.5. Store `collection_period` explicitly and separately from
`retrieved_date` — these will usually differ by years, and conflating them
is the single easiest way to mislabel 2018-vintage data as current.

---

## 5. Schema

### `lab_tests` — canonical test identity (distinct from biomarker)

```sql
CREATE TABLE lab_tests (
    test_id TEXT PRIMARY KEY,
    canonical_biomarker_id TEXT,
    test_name TEXT NOT NULL,
    test_type TEXT,
    specimen TEXT,
    method TEXT,
    canonical_unit TEXT,
    loinc_code TEXT,
    loinc_version TEXT,
    loinc_status TEXT,          -- 'unmapped' | 'candidate' | 'verified'
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

One biomarker (e.g. `crp`) can map to multiple `test_id`s (different
assays/labs). Never assume 1:1.

### `lab_test_identifiers`

```sql
CREATE TABLE lab_test_identifiers (
    test_id TEXT NOT NULL,
    laboratory TEXT NOT NULL,
    identifier_type TEXT NOT NULL,   -- QUEST_TEST_ID | LOINC | CPT | HCPCS | LAB_LOCAL_CODE
    identifier TEXT NOT NULL,
    identifier_description TEXT,     -- omit for CPT unless licensed to store AMA text (see §0.3)
    source TEXT,
    source_date DATE,
    PRIMARY KEY (test_id, laboratory, identifier_type, identifier)
);
```

### `test_billing_codes`

```sql
CREATE TABLE test_billing_codes (
    test_id TEXT NOT NULL,
    coding_system TEXT NOT NULL,     -- CPT | HCPCS
    code TEXT NOT NULL,
    description TEXT,                -- HCPCS only, or CPT if licensed
    relationship TEXT,                -- e.g. 'exact' | 'panel_component'
    source TEXT,
    source_date DATE,
    PRIMARY KEY (test_id, coding_system, code)
);
```

A single CPT/HCPCS code can represent a panel rather than one analyte —
don't assume 1:1 with `lab_tests` either.

### `test_prices`

```sql
CREATE TABLE test_prices (
    price_id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL,
    source TEXT NOT NULL,             -- FINDLABTEST | CMS_CLFS | CMS_PRIVATE_PAYER
    provider TEXT,
    price_type TEXT NOT NULL,         -- DIRECT_TO_CONSUMER | MEDICARE_ALLOWED | PRIVATE_PAYER_RATE
    amount DECIMAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    geography TEXT,
    state_restrictions TEXT,
    retrieved_date DATE,
    effective_date DATE,
    collection_period TEXT,           -- required when price_type = PRIVATE_PAYER_RATE
    source_url TEXT,
    source_version TEXT
);
```

### `test_cost_summary` (materialized)

```sql
CREATE TABLE test_cost_summary (
    test_id TEXT PRIMARY KEY,
    d2c_min REAL, d2c_median REAL, d2c_max REAL,
    cms_clfs REAL,
    cms_private_payer_median REAL,
    cms_private_payer_collection_period TEXT,
    reference_consumer_price REAL,    -- default: d2c_median, not d2c_min
    reference_payer_price REAL,
    price_date DATE,
    price_confidence TEXT             -- HIGH (>=3 obs) | MEDIUM (2) | LOW (1)
);
```

Default `reference_consumer_price` to the **median**, not the minimum —
minimum is more useful as a separate "lowest observed price" field than as
the default, since it's sensitive to one outlier discounter.

### `biomarker_test_value`

```sql
CREATE TABLE biomarker_test_value (
    biomarker_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    age INTEGER, sex TEXT, race_ethnicity TEXT,
    expected_hr REAL, hr_sd REAL,
    ehiv REAL, rehiv REAL,
    reference_consumer_price REAL,
    cms_clfs_price REAL,
    cms_private_payer_price REAL,
    population_n INTEGER,
    mortality_model_id TEXT,
    simulation_count INTEGER,
    simulation_seed INTEGER,
    created_at TIMESTAMP
);
```

---

## 6. LOINC mapping process

Matching hierarchy, in order, for resolving a `lab_tests` row to a LOINC
code:

1. Exact LOINC match (manually confirmed against loinc.org/search)
2. Exact Quest test ID cross-reference (if Quest publishes one — check
   Quest's own test directory)
3. Verified component/specimen/method match against LOINC's structured
   axes (component, property, time, system, scale, method)
4. Curated manual mapping with a named reviewer
5. Fuzzy name match — **candidate generation only, never auto-published**

Track every mapping in `data/mappings/test_biomarker_review.csv`:
`test_id, test_name, quest_test_id, loinc_code, candidate_biomarker,
match_method, confidence, review_status (AUTO_VERIFIED|MANUAL_VERIFIED|
NEEDS_REVIEW|REJECTED), review_notes`. Given §0.1, expect most rows to start
at `NEEDS_REVIEW`.

Watch for near-duplicate test names that are actually different tests:
`glucose` / `fasting glucose` / `glucose, plasma` / `glucose, serum` /
`glucose tolerance` are not interchangeable.

---

## 7. Expected Hazard Information Value

```python
def calculate_expected_hazard_information(
    biomarker_id, age, sex, race_ethnicity,
    n_simulations=10000, seed=20260821,
):
```

**A — population distribution.** Pull the NHANES biomarker distribution for
this (age, sex, race_ethnicity) stratum from the toolkit already built for
this project (`nhanes_toolkit`, `pool_cycles` + `stratified_summary`). Use
the most specific stratum with adequate n; fall back to a coarser stratum
(and say so in the response) rather than silently using population-wide
values.

**B — sample possible test results.** Sample from the *empirical* NHANES
values for that stratum (`rng.choice(values, size=n_simulations,
replace=True)`), not a parametric distribution — most of these biomarkers
are right-skewed and a normal-distribution assumption will misrepresent the
tails, which is exactly where mortality information concentrates.

**C — sample HR model uncertainty.** `beta_i ~ MVN(beta_hat,
covariance_matrix)` using the fitted Cox model's coefficient covariance
(available from `lifelines`' `CoxPHFitter.variance_matrix_`, already
produced by `hazard_curves.fit_rcs_cox` in the existing toolkit).

**D — HR per draw.** `hr_i = predict_hr(beta_i, value=x_i, age=age,
sex=sex, race=race_ethnicity)` — reuse `hazard_curves.predict_hr_curve`'s
spline-transform logic (via the stored `design_info`) rather than
re-deriving it, since that's exactly the bug that had to be fixed there
(knot mismatch on small inputs).

**E/F — expected HR and EHIV.**

```python
expected_hr = np.mean(hr_i)
ehiv = np.mean(np.abs(hr_i - expected_hr))
hr_sd = np.std(hr_i)
hr_variance = np.var(hr_i)
```

## 8. Relative EHIV

```python
rehiv = ehiv / expected_hr
```

Use for the cross-biomarker leaderboard.

## 9. Do not conflate EHIV with price

```python
# WRONG — units aren't commensurate (HR units vs. dollars)
test_value = ehiv - price
```

Display EHIV and price side by side. A descriptive (not economic) ratio is
fine to compute and label explicitly:

```python
information_per_dollar = rehiv / reference_consumer_price
```

Label it **"hazard-information units per dollar"** — never "ROI",
"cost-effectiveness", "economic value", or "EVSI". Those require a decision
model (action, intervention, cost, QALY) this phase doesn't have.

---

## 10. API

```
GET /api/biomarkers/{biomarker_id}/test-value
    ?age=60&sex=Female&race_ethnicity=Non-Hispanic%20Black
    &test_id=quest_10124&n_simulations=10000&seed=20260821
```

Returns test identity + prices (with source/vintage attached), population
definition, and `{expected_hr, hr_sd, ehiv, rehiv}`. Every price in the
response must retain its `source`, `retrieved_date`/`collection_period`, and
`price_type` — a bare number with no provenance is exactly the kind of thing
that gets miscited later as "the cost of a CRP test."

## 11. Frontend

Per-biomarker card: test name, LOINC (or "unmapped" if not yet resolved),
Quest test ID, observed consumer price (with date), CMS CLFS (with date),
EHIV, REHIV, HR-distribution chart. Do not label REHIV as a risk-reduction
percentage — it isn't one.

Population comparison table (biomarker × age/sex strata × REHIV × median
price) is the first version of a "Biomarker Test Value Landscape" view.

---

## 12. Starter biomarker list

Reuse the set already in `nhanes_toolkit.config.BIOMARKERS`
(`wbc, hemoglobin, platelet, albumin, creatinine, glucose,
total_cholesterol, hdl, crp`), extended with `hba1c, ldl, triglycerides,
rdw, ggt, uric_acid` — add these to `config.py`'s `BIOMARKERS` dict the same
way `crp`'s cycle-dependent variable was handled, checking each variable
name against the NHANES variable list
(https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx) rather than
assuming stability across all 10 cycles.

For each: (1) confirm NHANES variable, (2) resolve LOINC (expect
`NEEDS_REVIEW` per §0.1), (3) resolve Quest test ID, (4) resolve CPT/HCPCS —
prefer HCPCS per §0.3, (5) ingest Find Lab Tests price, (6) ingest CMS
price, (7) connect to the existing mortality HR model, (8) EHIV, (9) REHIV.

## 13. Acceptance test: hs-CRP

Find Lab Tests (as of the original check) lists hs-CRP at Quest test
`10124`, priced at $36 through "Lab Testing API" — re-verify this at
ingestion time rather than hardcoding it, since consumer lab pricing
changes. Full acceptance: `biomarker=crp` resolves to a `lab_tests` row with
a human-reviewed LOINC status, a Quest ID, at least one Find Lab Tests price
observation and one CMS benchmark (CLFS if available), and
`/api/biomarkers/crp/test-value` returns a complete response per §10 with
every price provenance field populated.

## 14. Provenance requirements (non-negotiable)

Every price: `source, source_url, retrieval_date, effective_date,
price_type, laboratory, geography`. Every HR result: `NHANES cycles,
mortality model version/id, population definition, simulation seed,
simulation count`. Every LOINC mapping: `code, version, mapping source,
mapping confidence`.

## 15. Three distinct concepts — do not collapse into one score

- **Prognostic value**: `HR(x)` — how strongly does the biomarker relate to
  mortality.
- **Information value**: `EHIV` / `REHIV` — how much mortality-risk
  heterogeneity can the test reveal in this population.
- **Economic value**: requires `EVSI` — needs actions, interventions, costs,
  outcomes, utilities. Reserve fields (`decision_model_id, intervention_id,
  decision_threshold, treatment_cost, treatment_effect, qaly_gain,
  net_monetary_benefit, evsi`) but don't build this yet.

```
BIOMARKER
    ├── MORTALITY MODEL → HR(x|population) → HR uncertainty → EHIV/REHIV
    └── TEST → LOINC / Quest ID → CPT/HCPCS → FindLabTest + CMS prices
              └────────────────┬────────────────┘
                    TEST INFORMATION VALUE (by population segment)
                                │
                    "who should we test?" (now)
                                │
                    future EVSI layer → "is it worth testing?" (later)
```

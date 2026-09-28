# Fitness Landscape: Biomarker Test Cost + Expected Test Information Value

## Objective

Extend `landscape.opensourcemed.info` so every mortality biomarker can be connected to:

```text
Biomarker
   ↓
Specific laboratory test
   ↓
LOINC
   ↓
Quest test ID / other laboratory identifiers
   ↓
CPT / HCPCS
   ↓
Observed market prices
   ↓
CMS reimbursement/payment
   ↓
NHANES biomarker distribution
   ↓
Continuous mortality HR function
   ↓
Expected Hazard Information Value
   ↓
Population-specific test-information ranking
```

The first implementation should answer:

> **How much mortality-risk information does this test provide in a particular population, and what does the test actually cost?**

Do **not** calculate formal EVSI, QALYs, ROI, or years of life gained yet.

---

## 1. Use Find Lab Tests as the primary consumer-price source

Use the Find Lab Tests / Lab Testing API catalogue as the initial source for observed direct-to-consumer test prices:

https://www.findlabtest.com/store/lab-testing-api/

The catalogue provides laboratory test offerings, prices, and Quest as the underlying laboratory.

Find Lab Tests individual/search pages can also expose:

- test name
- Quest test ID
- components
- laboratory/store
- price
- state restrictions

Use Find Lab Tests as a **market/self-pay price source**, not as a universal clinical cost.

Do not crawl the entire site indiscriminately. Use a controlled ingestion process and respect the site's terms, robots rules, rate limits, and access restrictions. If a structured API/feed is available, prefer it over HTML scraping.

---

## 2. Canonical biomarker schema

Create:

```text
data/biomarkers/
```

with one machine-readable record per biomarker:

```text
data/biomarkers/{biomarker_id}.json
```

Example:

```json
{
  "biomarker_id": "crp",
  "name": "High-Sensitivity C-Reactive Protein",
  "short_name": "hs-CRP",
  "category": "Inflammation",
  "measurement": {
    "canonical_unit": "mg/L",
    "value_type": "continuous",
    "normalization": "none",
    "transformation": "log"
  },
  "optimization": {
    "direction": "lower",
    "enabled": true
  },
  "identifiers": {
    "loinc": [],
    "cpt": [],
    "hcpcs": []
  },
  "nhanes": {
    "enabled": true,
    "variables": []
  },
  "mortality_model": {
    "model_id": null,
    "outcome": "all_cause_mortality",
    "model_type": "cox_rcs"
  },
  "test_cost": {
    "cms_clfs": null,
    "private_payer_median": null,
    "market_self_pay": null,
    "currency": "USD",
    "effective_date": null
  }
}
```

Do not put a single LOINC code directly into the biomarker record if multiple legitimate test variants exist.

---

## 3. LOINC as canonical laboratory-test identifier

Use LOINC for the specific measurement/test concept.

Preserve relevant LOINC distinctions such as:

- component
- property
- time
- specimen/system
- scale
- method

Use the current LOINC release and retain its version.

Do not invent mappings. If a test cannot be confidently mapped:

```text
loinc_status = "unmapped"
```

---

## 4. Laboratory-test table

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
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

`biomarker_id` and `test_id` are different concepts. One biomarker can have multiple tests.

---

## 5. Laboratory-specific identifiers

```sql
CREATE TABLE lab_test_identifiers (
    test_id TEXT NOT NULL,
    laboratory TEXT NOT NULL,
    identifier_type TEXT NOT NULL,
    identifier TEXT NOT NULL,
    identifier_description TEXT,
    source TEXT,
    source_date DATE,
    PRIMARY KEY (
        test_id,
        laboratory,
        identifier_type,
        identifier
    )
);
```

Initial identifier types:

```text
QUEST_TEST_ID
LOINC
CPT
HCPCS
LABORATORY_LOCAL_CODE
```

---

## 6. Billing-code crosswalk

```sql
CREATE TABLE test_billing_codes (
    test_id TEXT NOT NULL,
    coding_system TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    relationship TEXT,
    source TEXT,
    source_date DATE,
    PRIMARY KEY (
        test_id,
        coding_system,
        code
    )
);
```

Initially support CPT and HCPCS.

Do not assume one-to-one relationships between clinical concepts and billing codes.

---

## 7. Test-price table

```sql
CREATE TABLE test_prices (
    price_id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL,
    source TEXT NOT NULL,
    provider TEXT,
    price_type TEXT NOT NULL,
    amount DECIMAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    geography TEXT,
    state_restrictions TEXT,
    retrieved_date DATE,
    effective_date DATE,
    source_url TEXT,
    source_version TEXT
);
```

Initial sources:

```text
FINDLABTEST
CMS_CLFS
CMS_PRIVATE_PAYER
```

Initial price types:

```text
DIRECT_TO_CONSUMER
MEDICARE_ALLOWED
PRIVATE_PAYER_RATE
```

---

## 8. Find Lab Tests ingestion

Create:

```text
scripts/ingest_findlabtest.py
```

The process should:

1. retrieve relevant catalogue/search data;
2. identify individual tests;
3. extract test name;
4. extract Quest test ID;
5. extract components;
6. extract price;
7. extract laboratory/store;
8. extract state restrictions;
9. extract price date if available;
10. save raw source data;
11. normalize into the internal schema.

Store raw data under:

```text
data/raw/test_prices/findlabtest/YYYY-MM-DD/
```

Every record must retain source URL and retrieval date.

Do not overwrite historical observations.

---

## 9. Find Lab Tests price interpretation

A Find Lab Tests price should be labeled:

> **Observed direct-to-consumer price**

Do not label it simply “test cost.”

Where multiple direct-to-consumer observations exist, calculate:

```text
minimum
median
maximum
```

Use the median as the default market reference price.

---

## 10. CMS Clinical Laboratory Fee Schedule

Create:

```text
scripts/ingest_cms_clfs.py
```

Ingest the current CMS Clinical Laboratory Fee Schedule data.

Store raw data under:

```text
data/raw/test_prices/cms_clfs/YYYY/
```

Normalize into `test_prices` with:

```text
source = CMS_CLFS
price_type = MEDICARE_ALLOWED
```

Retain effective date, source version, billing code, description, and amount.

Do not assume CLFS equals laboratory cost or patient bill.

---

## 11. CMS private-payer rates

Ingest:

**CMS Medicare Clinical Laboratory Fee Schedule Private Payer Rates and Volumes**

https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/medicare-clinical-laboratory-fee-schedule-private-payer-rates-and-volumes

Use this as a historical commercial/private-payer benchmark.

Store its collection period separately. Do not represent an older public dataset as current commercial pricing.

---

## 12. Separate price categories

Retain separately:

```text
market_price
payer_price
medicare_price
```

Initial interpretation:

- Find Lab Tests = consumer/direct-access market price
- CMS CLFS = standardized Medicare payer benchmark
- CMS private-payer data = historical commercial benchmark

---

## 13. Price-summary table

```sql
CREATE TABLE test_cost_summary (
    test_id TEXT PRIMARY KEY,
    d2c_min REAL,
    d2c_median REAL,
    d2c_max REAL,
    cms_clfs REAL,
    cms_private_payer_median REAL,
    reference_consumer_price REAL,
    reference_payer_price REAL,
    price_date DATE,
    price_confidence TEXT
);
```

Price confidence:

```text
HIGH
MEDIUM
LOW
```

Suggested rule:

```text
HIGH: >=3 current observations
MEDIUM: 2 current observations
LOW: 1 current observation
```

---

## 14. NHANES test mappings

```sql
CREATE TABLE test_nhanes_mappings (
    test_id TEXT NOT NULL,
    nhanes_cycle TEXT NOT NULL,
    dataset TEXT NOT NULL,
    variable TEXT NOT NULL,
    unit TEXT,
    transformation TEXT,
    mapping_confidence TEXT,
    source TEXT,
    PRIMARY KEY (
        test_id,
        nhanes_cycle,
        dataset,
        variable
    )
);
```

Validate all NHANES variable names against official NHANES documentation.

---

## 15. Test-to-biomarker crosswalk

Use this hierarchy:

1. Exact validated LOINC match
2. Exact Quest test ID
3. Verified laboratory component match
4. Curated manual mapping
5. Fuzzy name matching only for candidate generation

Never automatically publish an uncertain fuzzy match.

Create:

```text
data/mappings/test_biomarker_review.csv
```

Columns:

```text
test_id
test_name
quest_test_id
loinc_code
candidate_biomarker
match_method
confidence
review_status
review_notes
```

Statuses:

```text
AUTO_VERIFIED
MANUAL_VERIFIED
NEEDS_REVIEW
REJECTED
```

---

## 16. Mortality model linkage

```sql
CREATE TABLE mortality_models (
    model_id TEXT PRIMARY KEY,
    biomarker_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    model_type TEXT NOT NULL,
    data_source TEXT,
    cycles TEXT,
    spline_type TEXT,
    spline_knots JSON,
    transformation TEXT,
    reference_value DECIMAL,
    coefficient_vector JSON,
    covariance_matrix JSON,
    age_interaction BOOLEAN,
    sex_interaction BOOLEAN,
    race_interaction BOOLEAN,
    n INTEGER,
    deaths INTEGER,
    model_version TEXT,
    created_at TIMESTAMP
);
```

Retain fitted coefficients and covariance matrix so uncertainty can be propagated.

---

## 17. Continuous HR functions

```sql
CREATE TABLE mortality_hr_curves (
    model_id TEXT NOT NULL,
    age REAL,
    sex TEXT,
    race_ethnicity TEXT,
    biomarker_value REAL,
    hazard_ratio REAL,
    ci_low REAL,
    ci_high REAL,
    reference_value REAL,
    domain_min REAL,
    domain_max REAL,
    PRIMARY KEY (
        model_id,
        age,
        sex,
        race_ethnicity,
        biomarker_value
    )
);
```

The HR function must remain continuous.

---

## 18. Expected Hazard Information Value

Implement:

```python
calculate_expected_hazard_information(
    biomarker_id,
    age,
    sex,
    race_ethnicity,
    n_simulations=10000,
    seed=20260821
)
```

Process:

1. retrieve the appropriate NHANES biomarker distribution;
2. generate possible test results;
3. retrieve the continuous mortality HR model;
4. propagate model uncertainty;
5. evaluate HR for every possible result;
6. calculate the HR distribution;
7. calculate expected hazard-information metrics.

---

## 19. Population biomarker distribution

Use the most specific valid distribution:

```text
age × sex × race
        ↓
age × sex
        ↓
age
        ↓
sex
        ↓
overall
```

Record:

```text
distribution_level
distribution_source
population_N
```

Never silently fall back to a less-specific population.

---

## 20. Generate possible test results

Prefer empirical NHANES values:

```python
x = rng.choice(
    population_biomarker_values,
    size=n_simulations,
    replace=True
)
```

Do not assume normality for strongly skewed biomarkers.

---

## 21. Propagate mortality-model uncertainty

For each simulation:

```python
beta_i = sample_model_parameters(
    beta_hat,
    covariance_matrix
)
```

For frequentist models initially use:

```text
beta ~ MVN(beta_hat, covariance_matrix)
```

---

## 22. Evaluate HR

```python
hr_i = predict_hr(
    beta_i,
    biomarker=x_i,
    age=age,
    sex=sex,
    race_ethnicity=race_ethnicity
)
```

This must use the continuous spline function.

---

## 23. Expected HR distribution

Calculate:

```python
expected_hr = np.mean(hr_i)
median_hr = np.median(hr_i)
hr_sd = np.std(hr_i)
hr_variance = np.var(hr_i)
hr_p05 = np.percentile(hr_i, 5)
hr_p25 = np.percentile(hr_i, 25)
hr_p75 = np.percentile(hr_i, 75)
hr_p95 = np.percentile(hr_i, 95)
```

---

## 24. Expected Hazard Information Value

Define:

\[
EHIV =
E\left[
|HR(X)-E(HR(X))|
ight]
\]

Implementation:

```python
expected_hr = np.mean(hr_samples)

ehiv = np.mean(
    np.abs(hr_samples - expected_hr)
)
```

This measures expected mortality-hazard heterogeneity revealed by testing.

---

## 25. Relative Expected Hazard Information

For cross-biomarker comparison:

\[
REHIV =
rac{EHIV}{E(HR)}
\]

Implementation:

```python
rehiv = ehiv / expected_hr
```

Use REHIV for the initial test-information ranking.

Do not call it mortality reduction, ROI, cost-effectiveness, or EVSI.

---

## 26. Do not subtract test cost from EHIV

Do NOT calculate:

```python
test_value = ehiv - test_cost
```

because EHIV is in hazard-ratio units and cost is in dollars.

Display information and cost separately.

---

## 27. Descriptive information-per-dollar metric

For exploratory ranking only:

```python
information_per_dollar = rehiv / reference_consumer_price
```

Label:

> **Hazard-information units per dollar**

Do not call this ROI, economic value, cost-effectiveness, or EVSI.

---

## 28. Population test-value table

```sql
CREATE TABLE population_test_value (
    biomarker_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    age INTEGER,
    sex TEXT,
    race_ethnicity TEXT,
    distribution_level TEXT,
    population_n INTEGER,
    expected_hr REAL,
    hr_sd REAL,
    ehiv REAL,
    rehiv REAL,
    reference_consumer_price REAL,
    cms_clfs_price REAL,
    cms_private_payer_price REAL,
    mortality_model_id TEXT,
    simulation_count INTEGER,
    simulation_seed INTEGER,
    created_at TIMESTAMP,
    PRIMARY KEY (
        biomarker_id,
        test_id,
        age,
        sex,
        race_ethnicity
    )
);
```

---

## 29. Population matrix

Initially calculate:

### Age

```text
40
50
60
70
80
```

### Sex

```text
Male
Female
```

### Race/ethnicity

```text
Mexican American
Other Hispanic
Non-Hispanic White
Non-Hispanic Black
Non-Hispanic Asian
Other/Multiracial
```

Only publish combinations meeting existing NHANES sample/event requirements.

Calculate:

```text
EHIV
REHIV
HR SD
test cost
population N
```

---

## 30. Test Information Landscape

Add a visualization:

### Expected Mortality Information From Testing

Controls:

```text
Biomarker
Age
Sex
Race/ethnicity
Test
```

Display:

- HR distribution
- Expected HR
- HR SD
- P5–P95 HR
- EHIV
- REHIV
- observed consumer price
- CMS CLFS benchmark
- CMS private-payer benchmark

---

## 31. Biomarker test-information leaderboard

Rank biomarkers by:

```text
Relative Expected Hazard Information
```

The leaderboard answers:

> **Which tests are expected to reveal the greatest mortality-risk heterogeneity?**

It does not yet answer whether testing is economically worthwhile.

---

## 32. Population leaderboard

For a selected biomarker, rank population segments by:

```text
REHIV
```

Interpretation:

> Testing is expected to provide greater mortality-risk information in these segments.

Do not interpret this as evidence that these people will benefit most from treatment.

---

## 33. API

Add:

```text
GET /api/biomarkers/{biomarker_id}/test-value
```

Parameters:

```text
age
sex
race_ethnicity
test_id
n_simulations
seed
```

Example:

```text
/api/biomarkers/crp/test-value
    ?age=60
    &sex=Female
    &race_ethnicity=Non-Hispanic%20Black
    &test_id=quest_10124
```

Return:

```json
{
  "biomarker": {
    "id": "crp",
    "name": "High-Sensitivity C-Reactive Protein"
  },
  "test": {
    "test_id": "quest_10124",
    "quest_test_id": "10124",
    "loinc": [],
    "market_price": {
      "median": null,
      "source": "FINDLABTEST"
    },
    "cms_clfs": null
  },
  "population": {
    "age": 60,
    "sex": "Female",
    "race_ethnicity": "Non-Hispanic Black"
  },
  "expected_hazard_information": {
    "expected_hr": null,
    "hr_sd": null,
    "ehiv": null,
    "rehiv": null
  },
  "simulation": {
    "n": 10000,
    "seed": 20260821
  }
}
```

---

## 34. Biomarker-page test card

Add:

### Test Information Value

Display:

```text
Test
hs-CRP

LOINC
[validated code]

Quest test
10124

Observed consumer price
$XX

CMS CLFS
$XX

Expected mortality-information value
XX

Relative hazard-information value
XX%
```

Do not label the information percentage as a mortality reduction.

---

## 35. Future formal EVSI

Reserve:

```text
decision_model_id
intervention_id
decision_threshold
treatment_cost
treatment_effect
qaly_gain
net_monetary_benefit
evsi
```

Eventually:

```text
Test
 ↓
Result
 ↓
Risk
 ↓
Decision
 ↓
Intervention
 ↓
QALYs
 ↓
Costs
 ↓
EVSI
```

The current version stops at:

```text
Test
 ↓
Result
 ↓
Mortality HR
 ↓
Expected hazard information
```

---

## 36. Initial biomarker implementation

Start with:

```text
CRP / hs-CRP
glucose
HbA1c
HDL
LDL
triglycerides
albumin
creatinine
hemoglobin
RDW
GGT
uric acid
```

For each:

1. identify exact NHANES variable;
2. identify exact LOINC;
3. identify Quest test where available;
4. identify CPT/HCPCS;
5. ingest Find Lab Tests price;
6. ingest CMS price;
7. connect to mortality model;
8. calculate EHIV;
9. calculate REHIV.

---

## 37. First complete implementation: hs-CRP

Use hs-CRP as the first end-to-end test.

Find Lab Tests currently identifies Quest test `10124` for hs-CRP and provides a direct-access market price on its listing.

The agent must create:

```text
biomarker:
crp

test:
quest_10124

LOINC:
validated exact mapping

Quest ID:
10124

Find Lab Tests price:
ingested value

CMS HCPCS:
validated mapping

CMS CLFS:
current value if available

NHANES:
validated variable mapping

mortality_model:
existing CRP model
```

Then this endpoint must work:

```text
/api/biomarkers/crp/test-value
    ?age=60
    &sex=Female
    &race_ethnicity=Non-Hispanic%20Black
    &test_id=quest_10124
```

---

## 38. Acceptance test

A valid biomarker/test must return:

1. Canonical biomarker
2. Specific laboratory test
3. LOINC mapping
4. Quest/laboratory identifier if available
5. CPT/HCPCS mapping if available
6. Current observed market price where available
7. CMS CLFS benchmark where available
8. Population biomarker distribution
9. Continuous mortality HR function
10. HR uncertainty distribution
11. Expected HR
12. HR SD
13. EHIV
14. REHIV
15. Population metadata
16. Model version
17. Simulation count
18. Simulation seed

---

## 39. Data provenance

Every price must retain:

```text
source
source URL
retrieval date
effective date
price type
laboratory
geography
```

Every HR result must retain:

```text
NHANES cycles
mortality model version
model ID
population definition
simulation seed
simulation count
```

Every LOINC mapping must retain:

```text
LOINC code
LOINC version
mapping source
mapping confidence
```

---

## 40. Critical conceptual distinction

Keep these three concepts separate:

### Prognostic value

How strongly does the biomarker relate to mortality?

```text
HR(x)
```

### Information value

How much mortality-risk heterogeneity can testing reveal?

```text
EHIV
REHIV
```

### Economic value

Is the information worth paying for because it changes decisions?

```text
EVSI
```

The first two can be implemented now.

The third requires:

```text
actions
interventions
costs
outcomes
utilities
```

Do not collapse these into a single score.

---

## 41. Final architecture

```text
                    BIOMARKER
                        │
             ┌──────────┴──────────┐
             ↓                     ↓
       MORTALITY MODEL          TEST
             │                     │
             │              ┌──────┴──────┐
             │              ↓             ↓
             │           LOINC       Quest ID
             │                            │
             │                         CPT/HCPCS
             │                            │
             │                     ┌──────┴──────┐
             │                     ↓             ↓
             │                 FindLabTest     CMS
             │                     ↓             ↓
             │                Market price   Payer price
             │
             ↓
       HR(x | population)
             │
             ↓
      HR uncertainty
             │
             ↓
       Monte Carlo sampling
             ↓
        HR distribution
             ↓
    Expected Hazard Information
             ↓
       Population ranking
             ↓
    Test Information Landscape
             │
             ↓
       FUTURE EVSI LAYER
             ↓
     Economic Test Value
```

## Product objective

The existing Fitness Landscape asks:

> **Which biomarkers have the strongest mortality associations?**

The new layer should allow it to ask:

> **Which biomarkers provide the most useful mortality information when tested in this population?**

And eventually:

> **For which population is testing this biomarker actually worth doing?**

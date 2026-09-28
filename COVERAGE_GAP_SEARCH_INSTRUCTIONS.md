# Coding Agent Instructions: Systematic Search for Coverage Gaps
## (biomarkers missing a population distribution and/or an HR(value) curve)

## 0. Objective

Some biomarkers in the platform's catalog have neither a population
distribution (NHANES or otherwise) nor a hazard-ratio-vs-value curve —
some are missing one, some both. Build a **repeatable audit** that finds
these gaps, then run a **systematic, reproducible literature search** per
gap to surface candidate sources, landing everything in a human-reviewed
queue. Nothing here gets auto-published — same review-status discipline as
the LOINC mapping (`test_biomarker_review.csv`) and intervention-effect
(`*_intervention_effects_review.csv`) queues already built for this
project.

**Honesty check before you start**: this is a *systematic-style targeted
search* (Europe PMC as primary source, which covers PubMed + PMC + Cochrane
abstracts + preprints), not a full PRISMA-compliant systematic review — it
doesn't reach Embase, Web of Science, or grey literature. Good for
triage/prioritization; don't describe its output as exhaustive or
publication-grade evidence synthesis.

---

## 1. Build the gap list first — audit, don't guess

Create `scripts/audit_biomarker_coverage.py`, re-runnable idempotently
(not a one-off script you run once and forget).

For every `biomarker_id` in the platform's existing catalog (the same id
space used by `lab_tests.canonical_biomarker_id` from the test-cost layer,
and/or whatever backs the Fitness Landscape leaderboard):

```python
has_nhanes_distribution = (
    biomarker_id in nhanes_toolkit.config.BIOMARKERS
    and pool_cycles(biomarker_id, with_mortality=False) actually returns rows
)  # configured-but-untested and actually-pulled are different things --
   # check both, don't just check the config dict

has_hr_curve = (
    a fitted RcsCoxResult / hazard_curve_points row exists for this
    biomarker_id for at least the pooled tier (per the age/sex hazard
    curve integration spec's curve_specificity field)
)
```

Write `data/audit/biomarker_coverage.csv`:
`biomarker_id, name, has_nhanes_distribution, has_hr_curve, gap_type
(distribution_only_missing | hr_curve_only_missing | both_missing |
complete), audit_date`.

Only biomarkers with a non-`complete` `gap_type` go on to the search
steps below.

---

## 2. For biomarkers missing a population distribution

NHANES doesn't cover everything — many newer biomarkers (advanced lipid
subfractions, specific cytokines, novel aging/senescence markers) simply
aren't in it. Search in this order:

**a) Check NHANES itself first — free, fast, do this before any
literature search.** Search
`https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx` for the
biomarker's common names/synonyms. It's entirely possible the variable is
already collected and just hasn't been added to `BIOMARKERS` in
`config.py` yet — that's a five-minute fix, not a literature-search
project. Only proceed to (b) if it's genuinely not in NHANES.

**b) If not in NHANES, search for alternative population-distribution
sources.** Query templates (Europe PMC, reuse
`interventions_toolkit.literature_search.search_europepmc` — it's not
intervention-specific under the hood, same client applies here):

```
'"{biomarker}" AND "reference range" AND (population OR normative OR percentile)'
'"{biomarker}" AND "reference interval" AND cohort'
'"{biomarker}" AND (NHANES OR "UK Biobank" OR MESA OR "Framingham Heart Study" OR "Atherosclerosis Risk in Communities" OR InCHIANTI OR "Rotterdam Study") AND distribution'
```

Also worth checking (each is a real, named resource — verify current
access/URL yourself before hardcoding, since I haven't independently
re-confirmed all of these this session):
- **UK Biobank's own data showcase** — has summary statistics for many
  biomarkers across its ~500k participants; search for its current
  showcase/variable-browser URL rather than assuming a specific one, since
  UK Biobank has had more than one URL/platform over time.
- **CALIPER** and similar pediatric/adult reference-interval studies, and
  individual labs' (e.g. Mayo Clinic Laboratories) published reference
  ranges — these are typically a **95% central reference interval from a
  healthy population**, not a full percentile distribution. Log which
  kind you found; don't conflate a reference interval with a distribution
  in the schema (see §5) — a reference interval alone can't feed the
  dispersion/borderline-mass testing-priority work built earlier, which
  needs actual percentiles.

**c) Log every candidate source** with standard provenance (source name,
url, retrieved_date, cohort/study name, n, whether it's raw individual-
level data or only summary statistics, distribution_type:
`percentile_distribution` | `reference_interval_only`) into
`data/mappings/distribution_source_review.csv`, `review_status =
NEEDS_REVIEW`.

---

## 3. For biomarkers missing an HR(value) curve

Query templates aimed specifically at dose-response mortality papers
(different from the intervention-effect templates used earlier — those
targeted RCTs/treatment effects, these target observational cohort
dose-response):

```
'"{biomarker}" AND mortality AND "restricted cubic spline"'
'"{biomarker}" AND mortality AND "dose-response"'
'"{biomarker}" AND mortality AND "hazard ratio" AND (quartile OR tertile OR continuous)'
'"{biomarker}" AND mortality AND cohort AND (NHANES OR "UK Biobank" OR "prospective cohort")'
'JOURNAL:"Cochrane Database Syst Rev" AND "{biomarker}" AND mortality'
```

**Don't bother querying ClinicalTrials.gov for this gap type** — trial
registries report treatment effects, not population dose-response
mortality curves; that's the right source for the interventions layer, not
this one. Skip it here to avoid burning API calls on structurally
irrelevant results.

For each candidate paper, log (same review-CSV pattern as elsewhere):
`title, doi/pmid, journal, year, study_design, cohort_name, n_participants,
n_events, biomarker_unit, hr_reporting_type` where `hr_reporting_type` is
one of:
- `continuous_spline` — reports an actual continuous HR(value) curve or
  the data to reconstruct one (highest priority — this is directly usable)
- `categorical_quartile` — only reports HR by quartile/tertile (still
  useful as an anchor/sanity-check against a curve you fit yourself from
  NHANES, but can't directly produce a continuous function)
- `per_unit_linear` — reports a single linear per-unit HR (e.g. "HR 1.05
  per 1-unit increase") — useful but assumes linearity, worth noting as a
  simplifying assumption if that's all that exists
- `other`

**Figure digitization is out of scope for this phase.** Some papers only
present the dose-response curve as a figure (not tabulated data), which
would need image digitization (e.g. WebPlotDigitizer-style pixel-to-value
extraction) from full-text PDFs — often paywalled, and a materially
different (harder, more error-prone) task than text extraction. Log these
as `hr_reporting_type = continuous_spline` with a note that only figure
data is available, and leave actual digitization as a flagged stretch
goal, not something this pass attempts.

---

## 4. Extraction step — same discipline as the intervention-effects layer

Reuse the extraction contract from `interventions_toolkit/extraction.py`
verbatim in spirit: the model sees only the retrieved title/abstract text,
every numeric field must trace to text actually present in the input, no
verbatim quoting beyond a few words, nothing auto-published — every row
lands as `NEEDS_REVIEW` until a human sets `MANUAL_VERIFIED`.

Extend the schema for this use case (a new `ExtractedHRRecord` pydantic
model, same pattern as `ExtractedEffect`) to also capture the fields listed
in §3 (`study_design`, `cohort_name`, `n_participants`, `n_events`,
`hr_reporting_type`), plus a `reported_hr_points` list of `{value_or_
category, hr, ci_low, ci_high}` for whatever anchor points the text
actually states (quartile HRs, a stated per-unit HR, etc.) — leave the
list empty rather than inventing points that aren't in the text.

---

## 5. Schema

```sql
CREATE TABLE biomarker_coverage_audit (
    biomarker_id TEXT NOT NULL,
    name TEXT,
    has_nhanes_distribution BOOLEAN,
    has_hr_curve BOOLEAN,
    gap_type TEXT,              -- distribution_only_missing | hr_curve_only_missing | both_missing | complete
    audit_date DATE,
    PRIMARY KEY (biomarker_id, audit_date)
);

CREATE TABLE distribution_source_candidates (
    candidate_id TEXT PRIMARY KEY,
    biomarker_id TEXT NOT NULL,
    source_name TEXT,
    source_url TEXT,
    cohort_name TEXT,
    n_participants INTEGER,
    distribution_type TEXT,      -- percentile_distribution | reference_interval_only
    retrieved_date DATE,
    review_status TEXT NOT NULL, -- NEEDS_REVIEW | MANUAL_VERIFIED | REJECTED
    review_notes TEXT
);

CREATE TABLE hr_curve_source_candidates (
    candidate_id TEXT PRIMARY KEY,
    biomarker_id TEXT NOT NULL,
    title TEXT, source_id TEXT, source_url TEXT, journal TEXT, publication_date TEXT,
    study_design TEXT,
    cohort_name TEXT,
    n_participants INTEGER,
    n_events INTEGER,
    biomarker_unit TEXT,
    hr_reporting_type TEXT,      -- continuous_spline | categorical_quartile | per_unit_linear | other
    reported_hr_points TEXT,     -- JSON array, see §4
    extraction_model TEXT,
    review_status TEXT NOT NULL,
    review_notes TEXT,
    retrieved_date DATE
);
```

Also add two status columns to whatever table already tracks biomarkers
(e.g. `lab_tests` or a dedicated `biomarkers` table):
`distribution_status`, `hr_curve_status`, each one of `NOT_STARTED |
CANDIDATE_SOURCES_FOUND | IN_PROGRESS | COMPLETE` — this is what actually
drives a "coverage progress" view, separate from the raw candidate tables.

---

## 6. Prioritization

Once the gap list and candidates exist, rank gap biomarkers for build
priority by:
1. Number of `continuous_spline`-type HR candidates found (more usable
   evidence = worth building sooner).
2. Whether a real (not reference-interval-only) distribution source
   exists.
3. Whether the biomarker already has a `MANUAL_VERIFIED` LOINC mapping
   from the test-cost layer — finishing a biomarker that's already
   partway built (has a test/price mapping, just missing distribution/HR)
   is lower-effort than starting one from zero.

Surface this as a simple sorted table, not a single blended score — same
reasoning as the dispersion-vs-borderline-mass testing-priority work: these
are different signals about different things, and collapsing them loses
information a reviewer would want to see separately.

---

## 7. Rollout

1. Run the coverage audit (§1), get the gap list.
2. Run distribution-source search (§2) for `distribution_only_missing` and
   `both_missing` biomarkers.
3. Run HR-curve search (§3) for `hr_curve_only_missing` and `both_missing`
   biomarkers.
4. Run extraction (§4) on both candidate sets.
5. Human review pass — nothing moves past `NEEDS_REVIEW` without one.
6. Re-run the audit (§1) periodically (e.g. monthly, or on every biomarker
   catalog update) — this is meant to be a standing check, not a one-time
   sweep, since new biomarkers get added to the catalog over time and NHANES
   itself adds variables in new cycles.

# Interventions layer: what affects each biomarker, and by how much

Adds an "interventions" step to the pipeline already built for this project:

```
Biomarker → thorough literature/trial search → LLM-extracted effect estimates
   → human review (MANUAL_VERIFIED) → applied to the existing NHANES
   distribution + Cox/spline HR curve → "if this biomarker shifted by X,
   how does predicted HR change"
```

Stops there -- no EVSI/QALY/cost-effectiveness, same boundary as the rest
of this project (see `TEST_COST_BUILD_SPEC.md` §15/§16 for why that's kept
separate).

## Data sources (verified this session)

- **ClinicalTrials.gov API v2** (`clinicaltrials.gov/api/v2/studies`) — free,
  no key, confirmed current parameter names (`query.cond`, `query.intr`,
  `query.outc`, `query.term`, `filter.overallStatus`, `fields`,
  `pageToken`).
- **Europe PMC REST API** (`ebi.ac.uk/europepmc/webservices/rest/search`) —
  free, no key. Used as the primary literature source because it ingests
  all of PubMed *plus* PMC full text, preprints, and — importantly —
  **Cochrane Database of Systematic Reviews abstracts**. There is no
  separate public Cochrane API; Cochrane coverage here comes from a
  journal-filtered Europe PMC query (`search_cochrane_reviews`), and it's
  abstracts only — full Cochrane review text is behind Wiley's paywall.
- **PubMed E-utilities** — wired in as a fallback only, not independently
  re-verified this session (long-stable API).

## What's tested vs. not

Same caveat as the NHANES toolkit: this sandbox can't reach
clinicaltrials.gov or ebi.ac.uk, so the HTTP clients are written against
verified current documentation but not exercised against live traffic.
What WAS tested, against mocked responses matching the documented schemas:

- Dedup logic across overlapping query templates (`search_orchestrator`)
- The full extraction → validation → CSV pipeline (`extraction.py`),
  including a malformed-JSON-from-the-model case and a not-relevant case
- Applying a verified effect to a real fitted HR curve (`impact.py`),
  including the unsupported-effect-measure error path

One real bug caught in testing and fixed: `check_plausibility` originally
mutated its input row and only set the flag when triggered, so re-checking
an already-flagged row against a *wider* (passing) reference range kept
the stale flag from a previous check. Fixed to return a new row with the
flag explicitly set either way.

**Not verified**: the exact nested JSON shape of `resultsSection.
outcomeMeasuresModule` in ClinicalTrials.gov's posted numeric results
(group means/SDs) — that part of the schema is deep and has shifted across
CT.gov API revisions historically. `extract_outcome_measurements` in
`clinicaltrials_client.py` is written defensively (never raises on an
unexpected shape) but should be checked against 2-3 real completed trials
with posted results before relying on it at scale.

## Why extraction needs an LLM, and the guardrails around it

Effect sizes, doses, and populations are stated in free text in wildly
inconsistent formats across abstracts and registry entries -- there's no
reliable regex for "extract the treatment effect." The extraction step
(`extraction.py`) hands the model ONLY the retrieved abstract/registry
text and enforces:

- The model is told explicitly not to use outside knowledge of the study
  or "typical" effect sizes -- every number must be traceable to the
  provided text, or left null.
- No verbatim quoting beyond a few words (copyright — same rule as
  elsewhere in this project's citation handling); free-text fields are
  paraphrased.
- Nothing is auto-published. Every row lands as `NEEDS_REVIEW` (or
  `REJECTED` if the model itself flags it as not relevant, or if its
  output didn't parse) until a human sets `MANUAL_VERIFIED`.
- A cheap plausibility check (`check_plausibility`) flags — doesn't
  reject — effects whose magnitude looks implausible against the
  NHANES-observed range for that biomarker, to help a reviewer prioritize.

## Quick start

```bash
pip install pandas numpy scipy matplotlib requests lifelines patsy anthropic pydantic
export ANTHROPIC_API_KEY=...
python run_intervention_search.py crp
```

Writes `<biomarker>_intervention_effects_review.csv` — every row needs
human review before use. To extend to more biomarkers, add a
`BiomarkerSearchSpec` to `BIOMARKER_SEARCH_SPECS` in `config.py` (include
synonyms — trials rarely use NHANES's internal variable names).

## Files

- `interventions_toolkit/config.py` — search specs, query templates, controlled vocab
- `interventions_toolkit/clinicaltrials_client.py` — ClinicalTrials.gov v2 client
- `interventions_toolkit/literature_search.py` — Europe PMC (+ Cochrane filter) + PubMed fallback
- `interventions_toolkit/search_orchestrator.py` — runs the full "thorough search" per biomarker, dedupes
- `interventions_toolkit/extraction.py` — LLM-based structured extraction + review-CSV writer
- `interventions_toolkit/schema.py` — SQL DDL (interventions, effects, impact tables)
- `interventions_toolkit/impact.py` — applies a verified effect to the existing HR curve
- `run_intervention_search.py` — end-to-end example for one biomarker

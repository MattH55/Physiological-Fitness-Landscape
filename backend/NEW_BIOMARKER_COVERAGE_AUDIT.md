# New Biomarker Coverage Audit: TSH, B12, Folate, IGF-1, Free T3, DHEA-S,
# Beta-2 Microglobulin, 8-OHdG, Homocysteine, FIB-4, YKL-40, suPAR,
# sTNFR1, LMR, GDF-15, Transferrin Saturation, MPV, Eosinophil Count,
# Serum Zinc, Serum Selenium

Checked each of these against what's actually known about NHANES coverage
before writing any ingestion instructions — several of the items on this
list are NOT NHANES analytes at all, and building against
`nhanes_toolkit.config.BIOMARKERS` for those would just fail. Sorted into
five categories, each with a different action.

## Category A — Confirmed in continuous NHANES (1999–2018): add and build normally

| Biomarker | Confirmed via | Notes |
|---|---|---|
| TSH | NHANES thyroid profile (THYROD_x files), confirmed present 2001–2002 and 2007–2012 | **Gap: no thyroid data 2003–2006** — don't silently pool across that gap; exclude those cycles explicitly in `CYCLES` for this biomarker rather than letting `pool_cycles` return fewer rows than expected without comment |
| Free T3 | Same THYROD_x files as TSH, same cycle coverage | Same gap caveat |
| Homocysteine | Standard NHANES biochemistry analyte (HCY component) | Variable name not re-verified this session — confirm exact `LBXHCY`-style name and cycle coverage against the NHANES variable list before adding |

Action for this category: add each to `nhanes_toolkit/config.py`'s
`BIOMARKERS` dict following the existing pattern (see `crp`'s
`component_overrides`/`variable_overrides` for how to handle the THYROD
cycle gap). Confirm exact variable names against
`https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx` before writing
the config entry — I have not independently re-verified the exact SAS
variable names (e.g. `LBXTSH`, `LBXFT3`) this session, only that the
underlying data exists.

## Category B — Confirmed, but part of the standard CBC differential (already partially wired)

| Biomarker | Notes |
|---|---|
| Mean Platelet Volume (MPV) | Same `CBC_x` component file already used for `wbc`/`hemoglobin`/`platelet` — just needs its own `Biomarker` config entry with the right variable name |
| Eosinophil Count | Same `CBC_x` file — both percent and absolute-count variables typically exist; decide which one matches how you want the distribution reported (percent is more directly comparable across the CBC panel; absolute count is what most clinical mortality-association literature uses — check the literature convention for this biomarker specifically before picking) |

Action: add both to `BIOMARKERS` with `component="CBC"` — no new
ingestion code needed, just config entries, since `download.py` already
fetches this file for the existing CBC-derived biomarkers.

## Category C — Likely in NHANES, but with important caveats — verify before building

| Biomarker | Concern |
|---|---|
| Vitamin B12 | Standard NHANES nutritional biochemistry analyte, but I have not re-verified exact cycle coverage or variable name this session |
| Serum Folate | Same — also check whether NHANES reports serum folate, RBC folate, or both (they're not interchangeable; a mortality/distribution analysis should specify which) |
| Transferrin Saturation | NHANES has an iron-status panel (iron, TIBC, transferrin saturation) but it has historically NOT been measured in every cycle — confirm which cycles before pooling, since silently pooling across cycles where it wasn't measured would just produce a smaller-than-expected but not obviously-wrong-looking sample |
| Serum Zinc | Historically measured only in a **subsample** in specific cycles as part of a nutritional trace-elements panel, not the full NHANES sample — expect meaningfully lower n and correspondingly wider uncertainty; verify actual cycle/subsample coverage before treating the resulting distribution as comparable in precision to a full-sample biomarker |
| Serum Selenium | Same subsample caveat as zinc |
| IGF-1 | Possibly measured in a specific set of continuous-NHANES cycles as part of a growth-hormone-axis study — **not confirmed this session**, and it's possible this is restricted-access data requiring an NCHS Research Data Center application rather than a public-use file. Check public-use availability FIRST before planning any ingestion work around it. |
| DHEA-S | Possibly measured in specific cycles (and/or NHANES III) — **not confirmed this session**. Same "check public-use availability first" caution as IGF-1. |

Action: for each, search the NHANES variable list directly, confirm public-
use availability and cycle coverage, THEN add to `BIOMARKERS`. Don't
write ingestion code against an assumed variable name for any of these —
verify first, per the "check NHANES itself first" step already established
in `COVERAGE_GAP_SEARCH_INSTRUCTIONS.md` §2a.

## Category D — Confirmed NOT in continuous NHANES; needs a different pipeline or source

| Biomarker | Where it actually is |
|---|---|
| Beta-2 Microglobulin | **Confirmed measured in NHANES III (1988–1994) only** — a completely different dataset from the continuous NHANES (1999–2018) this toolkit is built around. NHANES III has its own file formats, its own URL structure, and its OWN separate public-use mortality-linkage file (also NCHS-published, same general idea as the continuous-NHANES linkage but a distinct download). Confirmed via published Cox-model mortality analyses using this exact data (β2M positively associated with all-cause mortality, HR ~3.95 Q5 vs Q1 in one analysis). |

Action: this is NOT a config-entry addition to the existing toolkit — it
needs a **separate ingestion module** (`nhanes3_toolkit/` or similar,
mirroring `nhanes_toolkit`'s structure but pointed at NHANES III's actual
file locations and mortality-linkage format, which have NOT been verified
this session and need their own confirmation pass before building). Once
built, an actual HR curve IS achievable for this biomarker (NHANES III has
mortality follow-up), just not through the existing pipeline as-is.

## Category E — NOT in NHANES (any wave); only in specific research cohorts

| Biomarker | What exists instead |
|---|---|
| 8-Hydroxy-2'-deoxyguanosine (8-OHdG) | Not found as a routine NHANES analyte in this session's checking. It's a standard oxidative-stress research assay (urinary), typically only in dedicated toxicology/oxidative-stress cohort studies. |
| YKL-40 (CHI3L1) | Not in NHANES. Found a Danish general-population cohort (n=2,656, 15-year mortality follow-up) with a **published quartile HR for ischemic stroke mortality** (Q4 vs. Q1: HR 2.44, 95% CI 1.01–5.88) — a strong candidate for the `categorical_quartile` external-cohort-anchor path (§5 of `LANDSCAPE_INTEGRATION_INSTRUCTIONS.md`). |
| Soluble Urokinase Plasminogen Activator Receptor (suPAR) | Not in NHANES. Found in CKD-focused cohorts (e.g. CRIC-type studies) with published HRs for kidney disease progression, ESKD, and mortality. |
| Soluble TNF Receptor 1 (sTNFR1) | Not in NHANES. Same CKD-cohort literature as suPAR — one source found reports mortality HR ~1.17–1.45 across adjustment models, which is directly usable as a categorical anchor. |
| Growth Differentiation Factor-15 (GDF-15) | Not in NHANES. Found in cardiovascular- and COVID-19-specific research cohorts (ELISA-measured), correlates with age and CRP in those cohorts but population-level distribution data comparable to NHANES wasn't found. |

Action for this whole category: run the systematic search process already
specified in `COVERAGE_GAP_SEARCH_INSTRUCTIONS.md` — these are exactly
the `hr_curve_only_missing` / `both_missing` gap types that pipeline was
built for. Given what surfaced during this session's checking, expect the
searches for YKL-40, suPAR, and sTNFR1 in particular to come back with
real `categorical_quartile` or `per_unit_linear` anchor points fairly
quickly (the papers found here weren't the result of an exhaustive search,
just incidental hits while checking NHANES coverage — the actual gap-search
pipeline should do meaningfully better).

Do NOT default to the PhenoAge proxy for this whole category just because
it's convenient — the decision rule in `LANDSCAPE_INTEGRATION_INSTRUCTIONS.md`
§5 puts "real external cohort HR data" ahead of "PhenoAge proxy" for
biomarkers with neither NHANES coverage nor a way to compute PhenoAge
alongside them (which is the case for all five of these — they're not
measured on NHANES participants, so there's no way to jointly compute
PhenoAge and correlate it with these values in the first place). The
PhenoAge proxy specifically requires the new biomarker and the 9 PhenoAge
inputs on the SAME people — it is not usable here at all, not just
deprioritized.

## Category F — Not primary lab measurements; these are CALCULATED indices

| Index | Formula | What's needed |
|---|---|---|
| FIB-4 (used here as a NAFLD fibrosis proxy) | `(Age × AST) / (Platelets × √ALT)` | Age ✅ already available; Platelets ✅ already in `BIOMARKERS`; **AST and ALT are NOT currently in `BIOMARKERS`** — add both (standard NHANES `BIOPRO_x` analytes, same file already used for albumin/creatinine/glucose) |
| Lymphocyte-to-Monocyte Ratio (LMR) | `Lymphocyte count / Monocyte count` | Both are part of the standard CBC differential (same `CBC_x` file) but **neither is currently in `BIOMARKERS`** — add lymphocyte count and monocyte count (note: NHANES CBC gives both percentages and absolute counts; use absolute counts for the ratio, consistent with how LMR is defined in the clinical literature) |

Action: don't run a literature search for these — that would waste effort
looking for a "distribution of FIB-4" or "distribution of LMR" as though
they were independently measured analytes. Instead:
1. Add AST, ALT, lymphocyte count, and monocyte count to `BIOMARKERS`
   (verify exact NHANES variable names first, same as every other addition
   here).
2. Write a small `computed_indices.py` in `nhanes_toolkit` that takes a
   merged per-person dataframe (same merge pattern as
   `phenoage_ingestion.py` — join the needed component files by SEQN) and
   computes `fib4` and `lmr` as new columns.
3. Once computed per person, both indices flow through the EXISTING
   distribution (`stratified_summary`) and HR-curve (`fit_rcs_cox`)
   pipeline exactly like any other biomarker — a computed index is still
   just a continuous value per person once it exists as a column, and
   NHANES mortality linkage still applies the same way.

## Summary table for quick reference

| Category | Biomarkers | Path |
|---|---|---|
| A | TSH, Free T3, Homocysteine | Add to `BIOMARKERS`, verify variable names, build normally |
| B | MPV, Eosinophil Count | Same file already used — just add config entries |
| C | Vitamin B12, Serum Folate, Transferrin Saturation, Serum Zinc, Serum Selenium, IGF-1, DHEA-S | Verify NHANES availability/cycle coverage/public-use status FIRST, then build |
| D | Beta-2 Microglobulin | NHANES III only — separate ingestion pipeline needed |
| E | 8-OHdG, YKL-40, suPAR, sTNFR1, GDF-15 | Not in NHANES at all — run the coverage-gap literature search; PhenoAge proxy NOT usable (biomarker not measured on NHANES participants) |
| F | FIB-4, LMR | Not independent analytes — compute from AST/ALT/platelets/age and lymphocyte/monocyte counts respectively, once those underlying analytes are added |

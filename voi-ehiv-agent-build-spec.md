# Build Spec: Value-of-Information / EHIV Layer for the Physiological Fitness Landscape

## 0. Context for the agent

`landscape.opensourcemed.info` (v2.0) already implements, per biomarker:
- A continuous-spline mortality hazard-ratio curve overlaid on the NHANES population distribution, with age/sex filters.
- An "Optimization Simulator": a population-shift model computing baseline E[HR₀], shifted E[HR_δ] under an SD-shift slider (0–3 SD, presets at 0.25/0.5/1.0/1.5/2.0 SD and a "P25→P50" preset), Relative Hazard Reduction `RHR = 1 − E[HR_δ]/E[HR₀]`, expected absolute ΔHR, percent-benefiting, and domain-guardrail clamping.
- A leaderboard ranking biomarkers by RHR under a "Full Physiological Optimization" scenario.
- A multi-biomarker comparative view (up to 8 markers).
- Evidence-source registry, NHANES cohort benchmarks by age/sex, and a chronic-disease/multi-scale-alteration explorer.

This spec adds a **new, additive layer** — Value of Information (VOI) and Expected Hazard Information Value (EHIV) — on top of the existing hazard/optimization machinery. It does **not** replace RHR or the optimization simulator; it reuses their outputs (E[HR₀], E[HR_δ], the SD-shift mechanism, and domain guardrails) as inputs to a new DALY/dollar layer. Match the existing app's conventions for state management, charting, and data loading rather than introducing a parallel pattern — inspect the current biomarker-detail component and the optimization-simulator component first and extend them.

The underlying equations (numbered (1)–(13)) are defined in the companion manuscript "The Value of Information in Longevity Biomarkers"; this document maps each to an implementation task. Re-read that manuscript alongside this spec before starting.

## 1. New data required (beyond what's already loaded)

| Dataset | Purpose | Source | Notes |
|---|---|---|---|
| Life tables (baseline hazard/survival by single-year age × sex) | h₀, S₀ in eq. (3)–(5) | CDC/SSA actuarial life tables | Cache as a static age→(h₀,S₀) lookup; interpolate between tabulated ages. |
| Test market price per biomarker | c_test in eq. (12) | findalabtest.com (already used for price extraction per the paper's Methods) | Store price alongside existing LOINC mapping in the biomarker schema. |
| CMS reimbursement rate (optional secondary cost) | alternate c_test for a "payer view" toggle | CMS CLFS | Only needed if a payer-perspective toggle is built (§5, optional). |
| DALY willingness-to-pay threshold λ | eq. (12) | Configurable, not fetched | Expose as an adjustable parameter (default suggestion: 1–3× per-capita GDP or a fixed $/DALY, user-configurable — do not hardcode a single "correct" value; see §4). |
| Intervention effectiveness ε defaults | eq. (10)–(11) | Reuse existing intervention-effectiveness assumptions already embedded in the optimization simulator's SD-shift model where available; otherwise default ε = 1 at "Standard" (1.0 SD) preset, matching the existing simulator's default. | Keep this parameter shared with the optimization simulator rather than duplicating it, so a change to one updates the other. |

No new biomarker-response modeling is required — HR(x) and f_X(x; a,s,c) already exist in the current build; this layer consumes them.

## 2. Core computation module

Implement as a pure, independently testable module (e.g. `voi.ts` / `voi.py`, colocated with the existing hazard-curve and optimization-simulator logic), with no UI dependencies, so it can be unit-tested against hand-computed cases before wiring into components.

**2.1 `eyll(x, xRef, age, sex, HRfn, baselineTable) → years`**
Implements eq. (5): discretized life-table sum, not continuous integration —
```
EYLL = Σ_t [ S0(age+t)^HR(xRef) − S0(age+t)^HR(x) ]   for t = 0, 1, 2, ... up to max tabulated age
```
Reuse the existing spline/quantile HR(x) evaluator already powering the hazard-curve chart — do not re-implement HR fitting.

**2.2 `deltaDALY(x, xRef, age, sex) → DALYs`**
Eq. (6): mortality-only, `deltaDALY = eyll(...)`. Leave a named extension point (e.g. a `ylD` parameter defaulting to 0) for a future morbidity/YLD term — do not build YLD now, just don't foreclose it.

**2.3 `voiPerIndividual(x, age, sex, sigmaX, epsilon, cIntDaly) → DALYs`**
Eq. (11): `max(0, deltaDALY(x) − deltaDALY(x − ε·σ_X·sign) − c_int)`.
- `sigmaX` and the shift direction (`sign`) should be pulled from the same population-distribution object already used by the optimization simulator's SD-shift slider — this is the same σ, do not recompute it separately.
- Expose `epsilon` and `cIntDaly` as function parameters (not globals) so the UI can vary them per intervention scenario.

**2.4 `expectedVOI(ageBand, sex, cohort, sigmaX, epsilon, cIntDaly) → DALYs`**
Eq. (9)/(11) expectation: numerically integrate `voiPerIndividual(x, ...)` over the existing NHANES empirical distribution `f_X(x; a,s,c)` (reuse the same distribution object/histogram bins already driving the population-density chart — do not refit a new distribution).

**2.5 `ehiv(ageBand, sex, cohort, lambda, cTest, sigmaX, epsilon, cIntDaly) → dollars`**
Eq. (12): `lambda * expectedVOI(...) - cTest`.

**2.6 `populationVOI(biomarkerId, lambda, cTest) → { totalVOI, totalEHIV, byStratum[] }`**
Eq. (13): sum `N_{a,s,c} * expectedVOI(a,s,c,...)` across all (age band × sex × cohort) strata with sufficient data for that biomarker, using existing cohort population-size data (Census/NHANES survey weights, already available for the NHANES benchmark tables). Return the per-stratum breakdown, not just the total — the leaderboard and detail views both need it.

**Unit tests to include:** (a) EHIV = 0 boundary case when c_test equals λ·VOI; (b) VOI monotonically non-negative for all inputs; (c) EYLL reduces to 0 when x = x_ref; (d) population aggregation total equals the sum of its per-stratum parts (no double counting across overlapping cohort definitions — flag and exclude overlapping strata rather than silently double-counting).

## 3. Data-layer / schema changes

- Extend the biomarker schema with `testPriceUSD`, `cmsReimbursementUSD` (nullable), and a `loincToTestId` mapping if not already present from the LOINC work.
- Add a `lifeTables` static dataset (age × sex → h₀, S₀), loaded once at startup, not per-request.
- Add a config table/object for `lambdaDefault`, `epsilonDefault`, `cIntDalyDefault` — these are policy parameters, not biomarker data, and should be user-adjustable in the UI (§4), not hardcoded.

## 4. UI additions

**4.1 Biomarker detail page — new "Value of Information" panel**, positioned adjacent to the existing Optimization Simulator panel (reuse its SD-shift slider state rather than duplicating a second slider):
- Displays EYLL(x), ΔDALY(x), VOI(x) as a function of the same SD-shift input already in the Optimization Simulator.
- A λ (willingness-to-pay) input, with a sensible default and a short explanatory tooltip — do not present a single unlabeled default as authoritative, since λ is a normative policy choice, not an empirical estimate.
- Displays c_test (and, if the payer toggle is built, c_CMS) sourced from the schema, with a citation/link back to findalabtest.com.
- Headline EHIV figure with a sign-colored badge (favorable / unfavorable) and the underlying VOI, λ·VOI, and c_test broken out — do not show only the net number; show the three terms so the figure is auditable.

**4.2 Leaderboard — new sort/column option**
Add "EHIV" and "Population VOI (DALYs)" as sortable columns alongside the existing RHR-based ranking, using `populationVOI()` (§2.6). Keep RHR as the default sort to avoid changing existing behavior; EHIV is an additional, not replacement, ranking.

**4.3 Demographics / cohort panel**
Reuse the existing age/sex filter UI (already present per the current build) to drive `ehiv()` and `expectedVOI()` recomputation, matching how it currently drives the hazard-curve and distribution charts. No new filter UI should be needed here — wire the existing one to the new panel.

**4.4 Multi-biomarker comparative view**
Add EHIV as a comparable metric in the existing up-to-8-biomarker comparison table, alongside the current hazard-ratio and benchmark metrics.

## 5. Optional / phase 2 (do not build unless explicitly requested)

- Payer-perspective toggle (c_test → CMS reimbursement).
- Measurement-error convolution on f_X (relaxing the "perfect test" assumption in eq. (7)–(9)).
- YLD/morbidity term in eq. (6).
- Publication-ready export of the population-level EHIV ranking (for the companion methods paper).

## 6. Acceptance criteria

- For at least 3 biomarkers with existing published HR curves, EHIV values are validated against a hand-computed spreadsheet check before merging.
- Changing the SD-shift slider in the Optimization Simulator updates the VOI panel's figures without a page reload (shared state, per §2.3).
- Leaderboard sort by EHIV and by RHR can disagree in ordering (this is expected and should not be "fixed" — it's the point of adding a second ranking) but both must be independently correct.
- No existing chart, filter, or simulator behavior regresses — this is an additive layer.

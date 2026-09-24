# Signature-transfer modifier×drug predictor — build order

Sep 23, 2026 · @Someone

## Purpose and current state

The goal is a model that ranks **modifier × drug × cell line × schedule** combinations by predicted interaction, with calibrated uncertainty, so experimental effort goes to the most informative pairs. Modifiers are non-pharmaceutical interventions: hyperthermia, fasting and caloric restriction, TTFields, hypoxia, serum starvation.

**Why a conventional supervised approach is blocked.** There are currently 5 real quantitative labels (one TER, four IC50 fold-shifts), not homogeneous in metric type. Modifier×drug combination screening is not a funded, standardized paradigm the way drug×drug screening is, so there is no NCI-ALMANAC equivalent to mine. Most published work reports single-condition comparisons rather than checkerboards, and several relevant publishers are bot-blocked.

**The approach that unblocks it.** Architectures like DeepSynergy and MARSY never consume drug identity — they consume a perturbagen representation plus a cell context. If that representation is an L1000-style expression signature, hyperthermia at a given thermal dose in a given cell line is just another 978-dimensional vector. The modifier arm is drop-in compatible with existing drug×drug frameworks.

The consequence is that **chemical mimetics unlock the existing label sets**. Connectivity-mapping a real modifier DEG signature against LINCS identifies the compounds whose signatures most resemble it. Those compounds already appear in DrugComb and ALMANAC, which together hold on the order of a million measured drug×drug combinations across dozens of cell lines. Training happens on drug×drug; transfer to modifiers is zero-shot.

**The inversion that keeps this honest.** The 5 real labels are hopeless as training data and nearly ideal as a held-out test set. Five points cannot establish calibration, but they can falsify the transfer outright — a real result either way.

### Current asset state

| Asset | What exists | Coverage |
| --- | --- | --- |
| Drug induced signature | LINCS L1000 Phase 2 | 6 of 13 curated drugs, MCF7-anchored |
| Modifier induced signature | GSE153830 real DEG | 1 of \~40 modifiers, 2 cell lines |
| Cell line baseline expression | DepMap, restricted to 212 genes | 13 of 14 lines, partial transcriptome |
| Cell line mutation profile | Curated key\_mutations | 14 of 14, sparse (1–3 genes per line) |
| Real quantitative labels | 1 TER, 4 IC50 fold-shifts | 5 total, heterogeneous metrics |

Two previously-deferred items are now active and run parallel to the main phase sequence: **Track B** (LINCS Phase 1 expansion) and **Track C** (thermal radiobiology TER extraction and figure digitization).

## Standing rules for the agent

These hold in every phase. They exist because the failure mode of this project is a model that looks trained and is not.

- **No synthetic, imputed, or placeholder labels.** If a value is not in a real dataset, the row does not exist.
- **Provenance on every derived artifact**: source accession, pull date, processing version.
- **Each phase writes `PHASE_N_REPORT.md`** with the numbers its gate is judged on, before the next phase begins.
- **A failed gate stops work.** Surface it. Do not route around it. "This approach does not work for reason X" is a valid and valuable output.
- **Nothing writes a `tier_2b_model_predicted` row until Gate 6 passes.** `validate_tier_model_run()` already enforces that every such row carries a `model_run_id`; that schema constraint stays.
- **One featurizer.** The function that builds a feature vector must not branch on whether a perturbagen is a drug or a modifier. If it needs to, the representation is wrong.
- **Negative results are recorded, not discarded.** Measured non-synergies and antagonism stay in every dataset.

## Phase 0 — Signature space alignment

Everything downstream depends on modifier signatures, LINCS drug signatures, and cell-line baselines living in one comparable space.

1. Fix the canonical space as the **L1000 978 landmark genes**. Not the current 212-gene DepMap restriction.
2. Write `signature_space.py`: canonical gene ordering, symbol→Entrez mapping with an explicit version, a `to_canonical(vec, source_genes)` projection, and a z-score/robust-z normalization applied identically to every source.
3. Re-express existing artifacts in canonical space: LINCS Phase 2 signatures for the 6 covered drugs, GSE153830 modifier DEG, DepMap baselines for the 14 cell lines.
4. Emit per-signature landmark coverage and refuse to register any signature below 0.7.

**Gate 0** — all three existing sources round-trip through `to_canonical` with ≥0.7 landmark coverage and matching gene order. Report per-source coverage.

## Phase 1 — Modifier signature library

Current state is 1 modifier of \~40. This phase is the bulk of the real work.

1. Build `modifier_signatures/` with one parser module per GEO series, each emitting a canonical-space DEG vector plus a metadata record: modifier class, dose, cell line, timepoint, platform, GEO accession.
2. Dose is recorded in the standard unit for its modality — **CEM43** for thermal, duration and glucose nadir for fasting, V/cm and hours/day for TTFields, O₂ percentage and duration for hypoxia.
3. Prioritize by data abundance, not by interest: serum starvation and hypoxia first (abundant), heat shock second, fasting and CR-mimetic third, TTFields last.
4. Solve the probe-annotation gap **once, centrally**, in `probe_annotation.py` — platform GPL→Entrez tables pulled from GEO rather than hand-mapped per series. This is what blocked GSE48398, GSE10043 and GSE75127 before; fix it as shared infrastructure, not per-series.
5. Target ≥8 distinct modifier conditions spanning ≥3 mechanism classes, each in ≥1 cell line.

**Gate 1** — ≥8 modifier signatures registered with complete dose metadata. Below 5, stop: the transfer approach lacks the modifier diversity to be worth continuing, and that is itself a finding worth reporting.

## Phase 2 — Domain shift diagnostics

This phase decides whether the whole approach is sound. Run it before any model code. Heat shock produces a massive, coherent, high-amplitude transcriptional program; most LINCS chemical signatures are weak and noisy by comparison. If modifier signatures sit outside the training distribution, the result is confident extrapolation off-manifold.

1. Compute the distribution of signature L2 norms across LINCS chemical signatures.
2. Compute the same for each modifier signature; report each as a z-score against the chemical distribution.
3. For each modifier, compute nearest-neighbour Pearson and cosine similarity against the full LINCS chemical set; record top-20 neighbours and scores.
4. Fit a density estimate (PCA to \~50 dims, then Mahalanobis distance or k-NN density) on the chemical signature manifold and score each modifier's position on it.
5. Write `PHASE_2_REPORT.md` with a per-modifier table: norm z-score, top neighbour correlation, manifold distance, verdict of `in-distribution` / `edge` / `off-manifold`.

**Gate 2** — at least 4 modifiers classified `in-distribution` or `edge`. Any modifier scoring `off-manifold` is flagged permanently in its metadata and excluded from Phase 6 predictions. Heat shock is expected to score high on norm; confirming that here is worth more than discovering it in Phase 6.

## Phase 3 — Mimetic mapping

1. For each in-distribution modifier, take the top-k LINCS chemical neighbours from Phase 2 as candidate mimetics.
2. Cross-reference against DrugComb and ALMANAC compound coverage. A mimetic is only usable if it appears in combination screens.
3. Write `mimetics.json`: modifier → ranked list of (compound, connectivity score, available pair count).
4. Register **2–3 negative-control modifiers** with deliberately poor connectivity. These exist so Phase 6 can test that model confidence drops where it should.
5. Record a mechanistic rationale per mimetic as a free-text field, but **do not let it override the connectivity score**. If HSP90 inhibitors do not actually surface as hyperthermia's top neighbours, that is data, not a bug to fix.

### Expected mappings, for sanity-checking only

| Modifier | Expected chemical neighbours | Confidence |
| --- | --- | --- |
| Hyperthermia | HSP90 inhibitors — geldanamycin, 17-AAG, radicicol | High; HSR connectivity is well established |
| Fasting / CR | mTOR and AMPK axis — rapamycin, metformin, 2-DG | High; cleanest of the three |
| TTFields | Mitotic arrest — vinca alkaloids, taxanes | Low; downstream-of-phenotype, not mechanistic |

**Mimetic pleiotropy is a known false-positive source.** HSP90 inhibitors induce HSR but also degrade client proteins across AKT, HER2 and RAF; hyperthermia shares the first effect and not the second. Any ALMANAC synergy driven by client degradation will transfer as a false positive. Flag mimetics with known broad client effects in `mimetics.json`.

**Gate 3** — ≥4 modifiers have ≥1 mimetic with ≥50 combination pairs available downstream, plus ≥2 negative controls registered.

## Phase 4 — Training corpus

1. Pull **DrugComb** in preference to raw ALMANAC — already harmonized, includes multiple synergy scores. Cache locally with pull-date provenance.
2. Filter to the mimetic-anchored subset: any pair where at least one compound is a registered mimetic.
3. Featurize each pair through `featurize.py`: perturbagen A signature, perturbagen B signature, cell-line baseline, cell-line mutation profile. Same function that will later serve modifiers, with **no branch on perturbagen type**.
4. Preserve measured non-synergies and antagonism. Do not filter to positives.
5. Add an explicit `schedule` feature: `simultaneous` / `A_first` / `B_first` plus interval.

**On schedule.** DrugComb is overwhelmingly simultaneous-exposure, so this feature will be near-constant in training. It exists anyway, because thermochemotherapy TER depends strongly on whether heat precedes, coincides with, or follows the drug — sometimes flipping sign. A model trained on DrugComb cannot learn this and will silently assume simultaneity unless schedule is an explicit input. The coefficient on it comes from Track C, not from here.

**Gate 4** — ≥20,000 featurized pairs across ≥10 cell lines, with the synergy-score distribution reported. It must not be positive-skewed after filtering; if it is, the filter is wrong.

## Phase 5 — Model and validation harness

1. **Build the CV harness before any model**: leave-one-cell-line-out and leave-one-drug-out splitters in `crossval.py`, with a hard assertion that no held-out entity leaks into training features.
2. Baselines in order, none skipped:
   - (a) global mean
   - (b) Bliss/Loewe expectation from single-agent potency alone
   - (c) gradient-boosted trees on hand-engineered features
   - (d) dual-arm signature network
3. A model advances only if it beats **baseline (b)** under both CV schemes. Report this explicitly — "the deep model lost to Bliss independence" is a legitimate and useful outcome, and at realistic label scale it is a plausible one.
4. Calibration is mandatory: predicted-vs-observed plots, plus an uncertainty estimate for the chosen model. **Conformal intervals** are the default choice — simplest, and they give coverage guarantees.

**Gate 5** — chosen model beats baseline (b) under both leave-one-cell-line-out and leave-one-drug-out, and its stated intervals achieve near-nominal empirical coverage on held-out data.

## Phase 6 — Zero-shot transfer and falsification

1. Feed real modifier signatures through the trained model. **No fine-tuning yet.**
2. Compare predictions against the real anchors — the original 5 plus whatever Track C has delivered by this point. **Each metric type gets its own comparison**; do not pool TER and IC50 fold-shift into one correlation.
3. Check the Phase 3 negative controls: predictions for poorly-connected modifiers must carry visibly wider intervals. If they do not, the uncertainty model is not tracking domain shift and Phase 5's calibration is misleading.
4. Propagate mimetic connectivity score into final interval width, so a prediction routed through a weak mimetic is visibly less certain.
5. Write `PHASE_6_REPORT.md` stating plainly whether transfer is supported, contradicted, or underpowered. **Five points can falsify; they cannot confirm.** The report must say so in those terms.

**Gate 6** — predictions fall within stated intervals for the real anchors, and negative-control intervals are wider than in-distribution ones. Only after this gate may `tier_2b_model_predicted` rows be written, each carrying `model_run_id`, the mimetic path used, and the connectivity score.

## Phase 7 — Deliverable

A ranked hypothesis list: **modifier × drug × cell line × schedule**, each row carrying predicted effect, calibrated interval, mimetic provenance, connectivity score, and domain-shift flag.

That ranking is the decision-relevant output — which pairs to test next — and it stays honest even when the intervals are wide. It is not a substitute for measurement, and the document that ships with it should not imply otherwise.

## Track B — LINCS Phase 1 expansion

**Status: active.** Runs parallel to Phases 1–3; feeds Phase 4. Not a blocker for any gate.

Phase 1 of LINCS (GSE92742, \~21GB, currently unpulled) covers the 7 curated drugs missing from Phase 2 and, more importantly, broadens the chemical signature reference set that Phase 2's domain-shift diagnostics and Phase 3's connectivity mapping both depend on. A larger reference set makes both of those measurements sharper rather than merely larger.

1. Pull GSE92742 Level 5 signatures. Do not pull Level 3/4 — the moderated z-scores are what connectivity mapping needs and the lower levels multiply the storage cost for no gain.
2. Store as HDF5 with a signature-id index; never load the full matrix into memory. Query by `sig_id` / `pert_id` / `cell_id`.
3. Deduplicate against Phase 2. Where a compound×cell combination appears in both, prefer Phase 2 (better QC) and record the collision.
4. Reconcile the two phases' differing landmark sets and normalization through the Phase 0 `to_canonical` path. **Do not write a Phase 1-specific normalizer** — if Phase 0's projection cannot handle it, fix Phase 0.
5. Re-run Phase 2 diagnostics against the enlarged reference set once loaded, and record whether any modifier's verdict changes. A modifier moving from `off-manifold` to `edge` purely because the reference set grew is a meaningful result and should be reported as such.
6. Extend `mimetics.json` with any new candidates the larger set surfaces.

**Scope discipline.** This track is a reference-set and coverage expansion, not a licence to widen the feature vector. At realistic label scale the model still cannot spend degrees of freedom on full dual 978-dim arms; hand-engineered features remain the Phase 5 default regardless of how much LINCS is on disk.

**Track B done when** — GSE92742 is queryable by accession, Phase 2 diagnostics have been re-run against it, and coverage of the 13 curated drugs is reported as a number.

## Track C — Thermal TER extraction and figure digitization

**Status: active.** Runs parallel to everything. Feeds Phase 6's test set and the Phase 4 `schedule` coefficient. This is the single highest-leverage source of real labels.

**Why this literature specifically.** TER is not an odd one-off metric. It was the house endpoint of the 1980s–90s thermal radiobiology and thermochemotherapy literature (Dewey, Overgaard, Hahn and successors), reported systematically across drugs, cell lines, and temperature-time schedules. That work is old enough to sit largely outside current bot-blocking, and a meaningful share is in PMC or aggregated into review tables. The adjacent hypoxic-radiosensitizer literature used enhancement ratios as a house metric too. The fasting and TTFields literatures are genuinely thin by comparison — do not spend equal effort there.

### C1 — Corpus assembly

1. Systematic search of PMC and PubMed for thermal enhancement ratio, thermochemotherapy, and hyperthermia potentiation, 1975–2005 as the primary window.
2. Prioritize **review articles with aggregated TER tables** — one review can yield dozens of primary values with citations, at a fraction of the per-paper cost.
3. Record every candidate in `ter_corpus.json` with PMID, access route, and extraction status. Papers that cannot be accessed are recorded as blocked, not dropped silently.

### C2 — Figure digitization

Most combination papers report dose-response only as figures. Digitization recovers real curves from them, converting single-point comparisons into full-curve labels — which is exactly the metric-homogeneity problem the label set currently has.

1. Use an established digitizer (WebPlotDigitizer or equivalent) with axis calibration recorded per figure.
2. Store extracted points, not just fitted parameters, so refits are possible later.
3. **Two independent extractions on a 10% sample**, with agreement reported. Digitization error is real and must be quantified rather than assumed away.
4. Every digitized curve carries figure number, panel, and axis-calibration record.

### C3 — Normalization and schedule coding

1. Convert all thermal doses to **CEM43**. Where the paper reports only temperature and duration, compute it and flag the derivation.
2. Code schedule explicitly: heat-before-drug, simultaneous, heat-after-drug, with interval in minutes. **This is the primary reason this track exists** — it is the only realistic source for the schedule coefficient that DrugComb cannot supply.
3. Record metric type per label (TER, IC50 fold-shift, ER, survival-fraction ratio). Do not homogenize across types.
4. Capture null and negative results deliberately. Published work skews positive, and a label set of only positives will teach the model that everything potentiates.

**Track C targets** — 50+ real labels of a single metric type (TER) is the realistic near-term goal; 100+ spanning ≥10 drugs makes fine-tuning viable in the deferred Phase 8. Every label lands in the same schema as the existing 5, documented per metric type.

## Still deferred

**Phase 8 — fine-tuning on real modifier labels.** Unblocks when Track C delivers 100+ labels spanning ≥10 drugs. At that point real labels serve as a correction term on top of the transferred model, not as the whole signal. Attempting this earlier reproduces the original problem in a more expensive form.

**Full dual 978-dim signature arms in the production model.** Unblocks only if label count becomes genuinely large. Track B increases what is on disk, not what the model can afford to use.

**Mechanistic and Bayesian hierarchical alternatives.** A 3–5 parameter model (Bliss/Loewe excess modulated by a mechanism-class interaction coefficient) degrades gracefully at low n and returns wide credible intervals rather than refusing to run. Hold this in reserve: if Gate 2 or Gate 6 fails, this is the fallback that still produces an honest ranked output, and it should be built rather than abandoning the deliverable.

## Risk register

| Risk | Where it bites | Caught by |
| --- | --- | --- |
| Modifier signatures off-manifold vs. chemical signatures | Confident extrapolation, silently wrong | Gate 2 diagnostics |
| Mimetic pleiotropy — HSP90 client degradation that hyperthermia does not share | False-positive synergy transfer | Phase 3 flagging; Gate 6 anchors |
| Schedule dependence absent from DrugComb | Model assumes simultaneity; TER can flip sign by schedule | Explicit `schedule` feature; Track C coefficient |
| Positive-publication skew in literature labels | Model learns everything potentiates | Phase 4 distribution check; Track C null capture |
| Digitization error treated as exact | False precision in the test set | C2 double-extraction on 10% sample |
| Uncertainty not tracking domain shift | Weak-mimetic predictions look as confident as strong ones | Gate 6 negative controls |
| Deep model adopted without beating Bliss | Complexity with no gain, harder to interpret | Gate 5 baseline ladder |

**The failure mode this whole structure exists to prevent** is a model that appears trained, reports a plausible metric, and has actually learned the chemical-combination manifold while being queried about physical interventions. Every gate above is a place to catch that before it reaches a `tier_2b_model_predicted` row.

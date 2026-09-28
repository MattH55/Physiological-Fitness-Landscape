# NPxP — predicting non-pharmacological × pharmacological interaction from expression signatures

Predicts the interaction effect (synergy / antagonism) of a **non-pharmacological
intervention** (hyperthermia, fasting/caloric restriction, ketogenic/low-glucose,
hypoxia, TTFields, radiotherapy) combined with a **drug**, in a specified cancer
cell line — from gene-expression signatures alone.

The central problem is label scarcity. Drug×drug synergy has ~10⁶ labelled
measurements; modifier×drug has a few dozen scattered thermal enhancement ratios
and IC50 fold-shifts, much of it locked in figures. So the model is **trained on
drug×drug data and transferred zero-shot** to modifier×drug. Everything in the
design follows from that one constraint.

---

## 1. Literature precedents

### 1a. Predicting synergy from expression signatures — the method is established

| Work | What it does | Relevance |
|---|---|---|
| **DeepSynergy** (Preuer et al., *Bioinformatics* 2018) | MLP on chemical fingerprints + untreated cell-line expression → Loewe score. First DL synergy model. | Establishes cell-line expression as the context representation. Structure-conditioned, so **cannot represent a modifier**. |
| **TreeCombo** (Janizek et al. 2018) | XGBoost on the same features; matches DeepSynergy. | Justifies boosted trees over deep nets at modest label counts. |
| **MatchMaker** (Kuru et al., *IEEE/ACM TCBB* 2022) | Per-drug subnetworks conditioned on cell-line expression; trained on DrugComb. | Two-branch conditioning pattern. Still structure-based. |
| **TranSynergy** (Liu & Xie, *PLOS Comp Biol* 2021) | Transformer over drug-target-derived gene vectors + **gene dependency (DepMap)**; pathway deconvolution. | Two direct borrowings: dependency as context, and pathway-level interpretability. |
| **MARSY** (El Khili, Memon & Emad, *Bioinformatics* 2023) | **Drops chemical structure**: represents each drug by its LINCS **differential-expression signature**, plus cell-line expression; multitask with single-agent response as auxiliary task. | **The key precedent.** Proves a perturbagen can be represented purely by what it does to the transcriptome. This is what makes a modifier representable at all. |
| **DRSPRING** (Jeon et al., *Comput Biol Med* 2024) | GCN over PPI network with LINCS drug-induced profiles + CCLE baseline + drug-target + gene-gene interactions. Predicts the L1000 profile first, then synergy. | Precedent for **imputing** a missing signature — the route to modifier signatures in cell lines never profiled under that modifier. |
| **PerturbSynX** (2025) | Multitask: molecular descriptors + drug-induced perturbation signatures → synergy + single-agent response. | Most recent confirmation that perturbation signatures carry synergy signal. |
| **Ma et al., *mBio* 2019** | Transcriptomic signatures predict regulators of drug synergy and clinical regimen efficacy in *M. tuberculosis*. | Signature→synergy transfer works **across intervention types**, not just drug pairs. |

### 1b. Representing a non-drug intervention as an expression signature — also established

Connectivity-mapping work has been converting non-pharmacological states into
signatures, and matching them to drugs, for two decades:

- **Calvert et al., *Aging Cell* 2016** — cross-linked mammalian caloric-restriction
  signatures against CMap drug signatures to find CR mimetics; validated rapamycin,
  allantoin, trichostatin A, LY-294002, geldanamycin in *C. elegans*.
- **de Magalhães, *Open Biology* 2020** — CR liver signatures vs a compound-perturbation
  reference set; recovered corticosteroids and PPAR agonists as CR mimetics.
- **Dhahbi et al., *Physiol Genomics* 2005** — metformin reproduces 75% of long-term-CR
  hepatic expression changes. A non-pharmacological state and a drug scored on the
  same axis.
- **Lamb et al., *Science* 2006** (CMap) and **Subramanian et al., *Cell* 2017**
  (L1000) — the reference framework and the 978-landmark space.
- **Cheng, Kovács & Barabási, *Nat Commun* 2019** — "Complementary Exposure": a
  combination is effective when both agents hit the disease module through
  **separate neighbourhoods**. Encoded directly as a feature block here.

**The gap this fills:** 1a predicts synergy but only between drugs; 1b represents
non-drug interventions as signatures but only to find *mimetics* — one agent at a
time, never an interaction. Nobody has joined them to predict modifier×drug
interaction. That join is the contribution.

### 1c. What the predictions must eventually be tested against

Empirical modifier×drug literature for ground truth:
- **Thermal enhancement ratios** — thermal radiobiology and HIPEC literature; TER by
  drug class (alkylators/platinums high, antimetabolites low) is the sharpest
  available qualitative test.
- **Hyperthermia + HSP90 inhibition / proteasome inhibition** — blocking the
  heat-shock escape route; the canonical mechanism-based modifier synergy.
- **Differential stress resistance** (Longo lab) — fasting + chemotherapy.
- **TTFields + drug** — EF-14 and preclinical combination screens.
- **Radiosensitisation** — the densest modifier×drug dataset in existence; the right
  positive control for the whole approach.

---

## 2. What is built and working

```
npxp/
  pathways.py    51-pathway space (L1000 stand-in), survival weights, 12 functional modules
  signatures.py  16 drugs + 7 modifiers as pathway signatures, with transcription-vs-function corrections
  celllines.py   8 cell lines (U87MG, MDAMB231, HCT116, A549, PANC1, OVCAR3, HEPG2, MCF7): baseline activity + dependency
  features.py    407 features in 8 mechanistic blocks
  simulator.py   mechanistic viability model → Bliss-excess labels (structural testbed)
  data.py        dataset assembly + real-data loader specification
  model.py       GBM + the CV1/CV2/CV3 split protocol + block permutation importance
run_experiments.py   full run (~15 min)
smoke_test.py        2 cell lines, 1 replicate (~5 min)
```

### The design constraint that makes transfer possible

**No feature may depend on chemical structure.** Hyperthermia has no SMILES, no
Morgan fingerprint, no molar concentration. So every feature is computed from
(signature, mechanism annotation, cell context) only. This is the one place the
design departs from DeepSynergy / MatchMaker / DeepDDS, and it is why those models
cannot be pointed at this problem. It follows MARSY.

Order invariance is structural, not learned: all pair features are symmetric
functions of A and B, so *f(A,B) = f(B,A)* exactly — no train-time augmentation.

### Feature blocks

| Block | Content | Provenance |
|---|---|---|
| 1 cell context | baseline pathway activity + dependency | DeepSynergy, TranSynergy |
| 2 pooled perturbation | symmetric summaries of both signatures | MARSY |
| 3 geometry | signature cosine, orthogonality, overlap of strongly-perturbed sets | Diaz et al. on monotherapy-profile correlation vs synergy |
| 4 dependency capture | single-agent efficacy proxies from cell dependency | TranSynergy |
| 5 complementary exposure | per-module joint-hit-but-separate-neighbourhood | Cheng et al. 2019 |
| 6 escape-route blockade | one agent suppresses the protective program the other induces | hyperthermia+HSP90i; fasting+IGF1R |
| 7 redundancy / buffering | same-pathway overlap; mutual restoration | Loewe additivity reasoning |
| 8 cell × mechanism cross | does the pair land on programs this line is running | — |

### Transcription vs function — a trap worth naming

Inhibiting a target often **upregulates its own transcriptional program** by
compensation. HSP90 inhibitors raise the heat-shock transcriptome while lowering
chaperone capacity; proteasome inhibitors raise subunit transcripts while lowering
flux. A signature-only model reads these as *agonists*. `FUNC_OVERRIDES` in
`signatures.py` records the functional direction where it diverges; in production
this block comes from DrugBank/ChEMBL target+action annotation, and it is the
drug-target feature layer TranSynergy and DRSPRING add on top of expression.

The same reasoning forced splitting `DNA_DAMAGE_RESPONSE` (lesion burden — bad for
the cell) from `DNA_REPAIR_CAPACITY` (repair competence — good for the cell).
Conflating them inverts the sign of hyperthermia's main chemosensitising mechanism.

### The simulator, and why it is not calibrated to real pharmacology

`simulator.py` generates labels from an explicit survival model the predictor never
sees, with four sources of non-additivity: per-pathway redundancy (L^q aggregation,
q=1.2 — sub-additive at *every* dose, unlike a saturating tanh which is linear in
the sub-IC50 regime where synergy is actually measured), module-level AND logic
(soft-min within module, product across modules — the mechanism behind complementary
exposure), inducible protection (stress programs blunt the partner's insult), and
uptake modulation (membrane permeability and efflux change effective dose).

I tried tuning it to reproduce a list of known synergistic/antagonistic drug pairs
and got sign agreement of 0.42–0.58 — chance. **I stopped, and that was the right
call:** tuning the label generator to known pharmacology and then training on its
output makes validation circular — the model would recover the curator's priors,
not learn anything. So the simulator's role is explicitly **structural**: it answers
"can a predictor built only from signature-level features recover interaction
structure, and does that survive holding out whole perturbagens and whole cell
lines?" Passing is necessary, not sufficient. Biological validation requires real
DrugComb labels (§3).

### Result from the smoke test — read this before trusting anything

2 cell lines, 1 replicate, 240 training / 224 transfer labels:

```
unseen-perturbagen CV   r=0.59  rho=0.31  sign_acc=0.70  P@10%=0.58
zero-shot drug→modifier r=0.19  rho=0.31  sign_acc=0.71  P@10%=0.09
```

Within-domain prediction works. **Zero-shot transfer fails**, and the failure mode
is the useful part: every one of the top-10 predicted modifier×drug combinations was
`<modifier> + verapamil`, predicted ≈ +87, true ≈ −4.

Diagnosis: efflux reversal (verapamil + anthracycline) is the single largest effect
in the drug×drug training labels, so the model learned "verapamil ⇒ enormous
synergy" as a **per-agent marginal** rather than an interaction, and applied it to
every modifier. One dominant mechanism in the training distribution hijacked
extrapolation.

This is not a simulator artefact — it is the central hazard of the whole approach,
and it will recur on real data, where DrugComb is likewise dominated by particular
drug classes and cell lines. Mitigations are step 4 below. **Do not report predicted
rankings until that step passes.**

---

## 3. Build instructions for the rest

Ordered by dependency. Steps 1–2 are mechanical; step 4 is where the science is.

### Step 1 — Replace the pathway space with real L1000 signatures

`pathways.py` is a 51-dim hand-built stand-in. Everything downstream is
dimension-agnostic, so this is a swap, not a rewrite.

1. Download LINCS L1000 level-5: GSE92742 (Phase 1) + GSE70138 (Phase 2), or
   pull from clue.io. Take the 978 landmark genes.
2. Collapse replicates per (pert_id, cell_id, dose, time); follow DRSPRING's QC —
   discard signatures with level-4/level-5 Pearson < 0.3. Standard condition is
   10 µM, 24 h (~18% of LINCS).
3. Build a gene-set projection matrix from MSigDB Hallmark + Reactome and project
   the 978-vector onto pathway scores, **or** keep the raw 978 space and let
   `MODULES` reference gene sets instead of pathway names. Keep both paths — the
   pathway projection is what makes modifier curation tractable and features 5–7
   interpretable; the raw space is what MARSY uses.
4. Replace `DRUGS[*]["vec"]`. Keep `FUNC_OVERRIDES`, now generated from
   DrugBank/ChEMBL/DGIdb target + action fields rather than by hand.

### Step 2 — Real cell-line context and real training labels

1. **Context**: CCLE/DepMap `OmicsExpressionProteinCodingGenesTPMLogp1.csv` for
   `expr_vec` (z-score across lines); `CRISPRGeneEffect.csv` for `dep_vec`.
2. **Labels**: DrugComb v1.5 `summary_v_1_5.csv` (~740k blocks) and/or
   NCI-ALMANAC `ComboDrugGrowth_Nov2017`. Use `synergy_zip` as primary target and
   `synergy_bliss` / `synergy_loewe` as robustness checks — ZIP is the most stable
   across dose grids.
3. **Intersect**: LINCS cell coverage ∩ DrugComb cell coverage ∩ CCLE ≈ 30–40 lines.
   This intersection, not the full 740k, is the real training set — the reason
   published models work at ~10⁴–10⁵ rows.
4. Delete `simulator.py` from the training path. Keep it as a regression test.
5. At ~10⁵ rows, swap the GBM for the MARSY architecture (two encoders — pair and
   triple — plus a multitask head predicting synergy *and* both single-agent
   responses). The auxiliary single-agent tasks are what keep the encoders from
   collapsing into per-agent marginals — which is precisely the failure seen above.

### Step 3 — Real modifier signatures

Replace the curated vectors in `signatures.py` with differential expression from
GEO, same projection as step 1:

| Modifier | Suggested series | Notes |
|---|---|---|
| hyperthermia | GSE13005, GSE50290, GSE168581 | prefer 42 °C/1 h in a cancer line; verify HSF1 targets dominate |
| fasting / CR | GSE74905, GSE119713 | in-vitro low-glucose+low-serum is the cell-line analogue of fasting; do not use whole-liver CR signatures for a cell-line model without noting the tissue mismatch |
| hypoxia | GSE47533, GSE142867 | separate acute from chronic — repair downregulation is chronic |
| TTFields | GSE179663 | scarce; expect to fall back on curation |
| radiotherapy | many | do this one first — densest interaction literature, best positive control |

Two hard problems here, both worth stating in any write-up:

- **Cell-line mismatch.** Modifier signatures are rarely available in the line you
  want. This is exactly what DRSPRING's module 1 solves — train a model to predict a
  perturbation signature in an unprofiled cell line from (perturbagen, baseline
  expression), then impute. DEPICT (2026) is the current best version of this.
- **Intensity/dose.** A modifier has no molar concentration. `data.py` scales the
  signature by an intensity factor as a stand-in. Better: collect signatures at
  several temperatures/durations/glucose levels and fit signature magnitude as a
  function of intensity.

### Step 4 — Fix the transfer failure (do this before reporting any prediction)

The smoke test's per-agent-marginal hijack must be eliminated. In order of expected
payoff:

1. **Multitask single-agent heads** (MARSY). Forces the encoders to represent each
   agent's own effect separately from the interaction. Most likely to be the actual
   fix.
2. **Interaction-only target.** Regress the *residual* after subtracting a fitted
   additive model of both agents' single-agent responses, so per-agent potency
   cannot leak into the interaction prediction.
3. **Winsorise / log-modulus-transform labels.** ZIP scores have heavy tails; a few
   extreme blocks dominate an L2 or even L1 fit.
4. **Mechanism-stratified training.** Stratify or reweight so no single mechanism
   class (efflux reversal, uptake modulation) dominates. Check with
   `permutation_importance_blocks` that blocks 5–7 carry the weight and block 4
   (single-agent capture) does not.
5. **Adversarial / domain-confusion term** on drug-vs-modifier, so the learned
   representation is not separable by agent class.
6. **Gatekeeping metric.** Report `precision_at_10pct` under `unseen_pert`, not
   Pearson r under a random split. Random-split r is the number everyone publishes
   and it is nearly meaningless for this use case.

### Step 5 — Calibrate and validate against real modifier data

1. Finish the Tier-1 label curation already in progress (5 quantitative labels so
   far: 1 TER, 4 IC50 fold-shifts). Target ~50 via figure digitisation of thermal
   radiobiology papers — that is enough for **calibration**, not training.
2. Fit a one-parameter monotone calibration (isotonic or Platt) from zero-shot
   predictions onto the real labels. Report both raw and calibrated.
3. **Qualitative tests the model must pass**, independent of any fitted label:
   - TER rank order by drug class: platinums/alkylators > anthracyclines >
     antimetabolites (a model that ranks 5-FU above cisplatin for hyperthermia is
     wrong, whatever its r).
   - Hyperthermia + HSP90 inhibitor and hyperthermia + proteasome inhibitor should
     rank near the top (escape-route blockade, block 6).
   - Radiotherapy × drug predictions should recover known radiosensitisers.
   - Fasting × PI3K/IGF1R-axis inhibitors should rank above fasting × DNA-damaging
     agents.
4. Prospective validation: a 4×4 dose matrix in one cell line for the top 3 and
   bottom 3 predicted combinations. Six combinations is a tractable wet-lab ask and
   the only result that would make this publishable.

### Step 6 — Ship the application layer

`run_experiments.py` already emits `transfer_predictions.csv`. For
`npxp.opensourcemed.info`:

- **Interaction lookup**: (cell line, modifier, drug) → predicted score, calibrated
  CI, the top contributing feature blocks, and the curated evidence tier if a real
  label exists.
- **Opportunity ranking**: per cell line / tissue, mean predicted gain from adding
  the best modifier — which cancer types have the most headroom for
  non-pharmacological adjuncts. This is the NCI Office of Data Sharing Impact Prize
  framing.
- Surface the evidence tier on every number. `tier_2b_model_predicted` must never be
  displayed the way a curated TER is.

---

## 4. Honest limitations

- **Zero-shot transfer does not work yet.** §2 result. Everything else is
  scaffolding until step 4 passes.
- Labels are currently synthetic. No number in this repo is a biological claim.
- Pathway signatures for both drugs and modifiers are hand-curated. Steps 1 and 3
  replace them.
- Bliss excess assumes independent mechanisms — the assumption most likely to be
  violated exactly where these combinations are interesting. ZIP is better; Loewe
  requires full dose-response fitting.
- In-vitro modifier ≠ clinical modifier. 42 °C for 1 h in a dish is not HIPEC; low
  glucose + low serum is not a 5-day fast. The systemic, immune, and stromal
  components of every one of these interventions are absent from a cell-line model,
  and for fasting and hyperthermia the immune component may be the dominant
  clinical mechanism.

## 5. Running it

```bash
python3 smoke_test.py        # ~5 min, 2 cell lines — sanity check
python3 run_experiments.py   # ~15 min, 8 cell lines — full CV + transfer + block importance
```

Requires numpy, pandas, scipy, scikit-learn. No network access needed in the current
offline configuration.

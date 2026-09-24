# Build Spec: NPxP (Non-Pharm × Pharm) — Drug × Non-Pharmacological Modifier Interactions
### Hosted at npxp.opensourcemed.info

## Goal
Build a web application that catalogues how non-pharmacological interventions (dietary/metabolic, thermal, hypoxic, and similar stressors) modify the fitness/death response of cancer cell lines to pharmacological agents. The core deliverable is a browsable, queryable, evidence-graded interaction database — not a predictive model. Every claim traces back to a cited source and an explicit evidence tier.

Positioning: this generalizes synthetic-lethality-style combinatorial thinking (two genetic perturbations → fitness effect) to include non-genetic perturbations (diet, temperature, hypoxia) crossed with pharmacological agents, at the cell-line level.

## Tech Stack Recommendation
- **Backend**: Python (FastAPI) or Node (Express) — either is fine; prefer whichever the team already uses for other OSMF platforms (RepurpOS, Vaccine Data Navigator) for consistency and code reuse.
- **Database**: Postgres. This is a relational, join-heavy schema (cell line × modifier × drug), not a document store use case.
- **Frontend**: React + a charting library that supports heatmaps well (e.g. Plotly.js, d3, or Nivo).
- **Hosting**: `npxp.opensourcemed.info` (confirmed). Follow the same infra/deployment conventions as the other opensourcemed.info properties (e.g. landscape.opensourcemed.info) for consistency.

## Data Model

### `cell_line`
| field | type | notes |
|---|---|---|
| cell_line_id | string (PK) | use DepMap/CCLE identifier as canonical ID |
| name | string | |
| tissue_origin | string | |
| cancer_subtype | string | e.g. "ER+/HER2-" |
| key_mutations | jsonb | array of {gene, variant} |
| tumor_concordance_score | float, nullable | from Celligner — how closely this line's transcriptional profile matches real patient tumors of its assigned type/subtype |
| tumor_concordance_flag | enum, nullable | good_model, poor_model_mesenchymal_shift, unassessed — surfaces Celligner's finding that a meaningful subset of commonly-used lines don't actually resemble any real tumor type, so users don't unknowingly build on a poor model |
| source | string | e.g. "CCLE" |

### `clinical_evidence`
Aggregate, publicly published clinical evidence only — never individual/patient-level records. Exists to answer "has anyone tested this combination in humans yet," not to store trial data itself.
| field | type | notes |
|---|---|---|
| id | uuid (PK) | |
| nct_id | string, nullable | ClinicalTrials.gov identifier |
| phase | string, nullable | |
| status | string, nullable | e.g. completed, recruiting, terminated |
| outcome_summary | text, nullable | brief, sourced from the published trial record/results — not raw data |
| publication_ref | string, nullable | DOI/PMID for a resulting paper, if any |
| linked_interaction_effect_id | FK → interaction_effect, nullable | which cell-line-level finding this trial evidence relates to |

### `modifier`
| field | type | notes |
|---|---|---|
| modifier_id | string (PK) | |
| modifier_type | enum | dietary_metabolic, thermal, hypoxic, mechanical_radiative, other |
| agent | string | e.g. "β-hydroxybutyrate", "fever-range hyperthermia" |
| protocol_parameters | jsonb | type-specific: {concentration_mM, duration_hr} for dietary/metabolic; {temperature_C, duration_min, timepoint_hr} for thermal; {o2_percent, duration_hr} for hypoxic. DO NOT normalize away these fields — cross-study pooling without protocol metadata is the single biggest known failure mode for thermal-stress data specifically (see meta-analysis note below), and likely applies to other modifier types too. |
| source_study | string | DOI or PMID |
| source_dataset_accession | string | e.g. GEO accession, nullable |

### `stress_signature_score`
| field | type | notes |
|---|---|---|
| id | uuid (PK) | |
| modifier_id | FK → modifier | |
| cell_line_id | FK → cell_line | |
| signature_panel | enum | isr_upr, nrf2_ferroptosis, hsf1_hsp, dna_damage, senescence, other |
| score | float | ssGSEA/GSVA output, or equivalent |
| raw_deg_evidence_ref | string | pointer/link to source DEG table or supplementary data |
| directionality | enum | death_promoting, protective_resistance, ambiguous |
| notes | text | free text for caveats (e.g. "no significant pathway enrichment detected") |

### `drug`
A normalized drug entity, needed once multiple source libraries (PRISM, GDSC, CTRP, LINCS) are merged — the same compound is named/IDed differently across each, so this table exists to resolve them to one record rather than silently fragmenting into duplicates.
| field | type | notes |
|---|---|---|
| drug_id | uuid (PK) | canonical internal ID |
| name | string | preferred display name |
| synonyms | jsonb | array of alternate names seen across source libraries |
| pubchem_cid | string, nullable | cross-reference |
| chembl_id | string, nullable | cross-reference |
| drugbank_id | string, nullable | cross-reference |
| mechanism_of_action | string, nullable | from Repurposing Hub |
| target | string, nullable | from Repurposing Hub |
| clinical_status | enum, nullable | approved, investigational, withdrawn, preclinical |
| induced_expression_signature_ref | string, nullable | pointer to LINCS L1000 signature, when available — this is what lets a drug be represented the same way a modifier is represented via `stress_signature_score`, which is the input format the Step 2 prediction models (MARSY/PerturbSynX) expect |

### `drug_response`
Ingested, not curated — pull directly from DepMap/PRISM, GDSC, and CTRP. Store only what's needed to join, don't duplicate their full datasets.
| field | type | notes |
|---|---|---|
| id | uuid (PK) | |
| drug_id | FK → drug | |
| cell_line_id | FK → cell_line | |
| viability_metric | float | |
| metric_type | enum | ic50, auc, viability_percent |
| source | string | e.g. "DepMap PRISM 24Q2", "GDSC2", "CTRP v2" |

### `interaction_effect`
The core output table.
| field | type | notes |
|---|---|---|
| id | uuid (PK) | |
| modifier_id | FK → modifier | |
| drug_id | FK → drug | |
| cell_line_id | FK → cell_line | |
| combined_effect_metric | float, nullable | Bliss/Loewe synergy score, or raw combined viability if that's what the source reports |
| interaction_type | enum | synergistic, antagonistic, additive, unknown |
| evidence_tier | enum | tier_1_direct, tier_2_inferred, tier_3_mechanism_only |
| mechanism_link | FK → stress_signature_score, nullable | which signature the hypothesized mechanism runs through |
| source_study | string | DOI/PMID, one or more |
| curator_notes | text | |

**Evidence tier definitions (surface these prominently in the UI, not just in a tooltip):**
- **Tier 1 — Direct**: combination was tested empirically in the same study (drug + modifier applied together, death/viability measured).
- **Tier 2 — Inferred**: drug response and modifier response measured separately but joined via shared cell line and biologically plausible shared mechanism.
- **Tier 3 — Mechanism-only**: signature overlap suggests a plausible interaction, but no death/viability readout exists for either factor in combination.

## Data Ingestion Sources (initial seed list)
- **DepMap / PRISM Repurposing** — drug sensitivity screens, cell line metadata (CCLE)
- **GDSC (Genomics of Drug Sensitivity in Cancer)** — hundreds of compounds × ~1,000 cell lines; cross-validation source against PRISM (disagreement between the two is itself a useful data-quality flag)
- **CTRP (Cancer Therapeutics Response Portal)** — third independent viability/IC50 source
- **LINCS L1000** — ~20,000 compounds × ~50 cell lines, drug-induced gene expression signatures. This is the highest-leverage addition: representing drugs via induced expression signature (rather than chemical structure) puts them in the same feature space as `stress_signature_score`-represented modifiers, which is what the Step 2 prediction models (MARSY/PerturbSynX) actually require as input.
- **Broad Repurposing Hub** — curated drug metadata: mechanism of action, target, clinical development phase (approved/investigational/withdrawn)
- **MSigDB Hallmark gene sets** — HALLMARK_UNFOLDED_PROTEIN_RESPONSE, HALLMARK_APOPTOSIS, HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY, HALLMARK_P53_PATHWAY — for scoring stress_signature_score via ssGSEA/GSVA
- **FerrDb** — curated ferroptosis marker genes, for the nrf2_ferroptosis panel specifically
- **GEO** — individual modifier studies, e.g.:
  - GSE153830 (BHB/glucose deprivation, MCF-7 + T47D)
  - GSE48398 (fever-range hyperthermia, mammary epithelial + 3 breast cancer lines)
  - GSE10043 (mild hyperthermia, U937)
  - GSE75127 (BAG3 knockdown × hyperthermia sensitivity, oral SCC)
  - GSE26370, GSE87773, GSE48984 (glutamine restriction)
  - GSE72131, GSE103602 (methionine restriction)
- **TCGA** — population-level plausibility checks (e.g. ketone-body-enzyme expression vs. survival)
- **Celligner** (Broad/DepMap) — precomputed cell-line-to-tumor transcriptomic alignment (Celligner data on figshare); populates `tumor_concordance_score`/`tumor_concordance_flag` without needing to run the alignment yourselves
- **ClinicalTrials.gov** — for populating `clinical_evidence` with aggregate trial metadata (phase, status) where a registered trial tests a combination also represented in `interaction_effect`

Each ingestion job should be its own pipeline step, tagged with source_study, so a bad/retracted source can be pulled without touching the rest of the table.

## Modifier Scope (MVP)

Confirmed to have usable cell-line-level gene expression and/or drug-combination data, so included in the initial modifier set:

| modifier_type | agent | notable source data |
|---|---|---|
| dietary_metabolic | β-hydroxybutyrate / ketosis | GSE153830 |
| dietary_metabolic | glutamine restriction | GSE26370, GSE87773, GSE48984 |
| dietary_metabolic | methionine restriction | GSE72131, GSE103602; clinical precedent improving 5-FU efficacy |
| thermal | fever-range hyperthermia | GSE48398, GSE10043, GSE75127 |
| hypoxic | tumor-microenvironment hypoxia | extensive HIF-1α target gene literature/GEO coverage |
| hypoxic | hyperbaric oxygen therapy (HBOT) | HIF-1α/PFKP axis mechanism in NSCLC (A549, H1299) — note: acts in the *protective/antagonistic* direction (suppresses Warburg effect/EMT), a useful second example alongside HSP70-doxorubicin of a modifier that isn't uniformly death-promoting |
| mechanical_radiative | Tumor Treating Fields (TTFields) | multiple RNA-seq/microarray datasets; direct synergy data with temozolomide/lomustine and PARP inhibitors via BRCA1 downregulation; FDA-approved, flagship modifier for the MVP |
| mechanical_radiative | pulsed electromagnetic field (PEMF) | 2025 genomic profiling (bladder cancer HT-1197); direct Tier 1 result showing PEMF decreases temozolomide resistance in glioblastoma via MGMT/Cyclin-D1/p53 modulation |

**Explicitly out of MVP scope** — no dedicated cell-line transcriptomic dataset found during scoping; revisit if/when verified data turns up:
- Cold exposure / cryotherapy
- Sonodynamic / photodynamic therapy
- Exercise-conditioned serum / myokine exposure
- Microbiome-derived metabolites (e.g. short-chain fatty acids)


- `GET /cell_lines` — list/search, filterable by tissue, subtype, mutation
- `GET /cell_lines/{id}` — detail, includes all known modifier scores and drug responses for that line
- `GET /drugs` — list/search, filterable by mechanism of action, target, clinical status
- `GET /drugs/{id}` — detail, cross-referenced IDs, all known cell-line responses and interactions
- `GET /modifiers` — list/search by type
- `GET /modifiers/{id}` — detail, protocol parameters, source
- `GET /interactions` — filterable by cell_line_id, modifier_id, drug_id, evidence_tier, interaction_type
- `GET /interactions/{id}` — full detail including mechanism link and all source citations

## Frontend Pages
1. **Landing/overview** — plain-language explanation of what the resource is, links into the three browsers below, and an explicit "what evidence tiers mean" explainer (this doubles as public-facing education and as documentation for reviewers/judges).
2. **Interaction explorer** (primary page) — a filterable heatmap or matrix: cell lines × modifiers, colored by interaction_type/effect magnitude for a selected drug (or drug class). Clicking a cell opens the interaction detail view. This is the "fitness landscape" visualization.
3. **Cell line browser** — search/filter by tissue, subtype, mutation; detail page shows all known modifier scores and interactions for that line, plus its Celligner tumor-concordance score/flag so users can see at a glance whether the line is actually a good model of real tumors.
4. **Drug library browser** — search/filter by mechanism of action, target, clinical status (approved/investigational); detail page shows cross-referenced IDs and all known cell-line responses and interactions for that drug.
5. **Modifier browser** — search/filter by type; detail page shows protocol parameters and all cell lines/drugs tested against it.
6. **Interaction detail view** — shows evidence tier prominently, mechanism link (with the stress signature score and its raw DEG evidence), full citation list, curator notes, and any linked `clinical_evidence` entries indicating whether this specific combination has been tested in humans.

## Prediction Layer (in MVP scope)

The database is not just a lookup table — it should predict interaction effects for drug×modifier×cell-line combinations that have never been tested together, clearly distinguished from directly measured ones via the evidence-tier system.

**Step 1 — Classical synergy quantification (ground-truth labeling).** Apply Bliss independence, Loewe additivity, HSA, and/or ZIP scoring (the same math SynergyFinder/DrugComb use for drug-drug pairs) to any dose-response matrix in the Tier 1 data — e.g. BHB-concentration × drug-dose, or temperature × drug-dose. These models don't require the second factor to be a drug; they just need a dose-response surface, so they apply unchanged to modifier×drug matrices. This produces real synergy/antagonism/additive labels for every Tier 1 combination and is cheap to implement first.

**Step 2 — Learned prediction for untested combinations.** Adapt an architecture from the MARSY / PerturbSynX family. These represent each agent not by chemical structure but by (a) the cell line's baseline gene expression and (b) the agent's induced differential-expression signature — which means a non-pharmacological modifier slots in naturally via its `stress_signature_score` data, in place of the "drug B" branch these models normally use for a second drug. Train/validate this model on the Tier 1 labels from Step 1 before trusting any of its output.

**Evidence tier for predicted output:** add a `tier_2b_model_predicted` value to the `evidence_tier` enum on `interaction_effect` (distinct from `tier_2_inferred`, which is a manual join of separate single-factor studies rather than a model output). Every model-predicted row must store the model version/training-run ID it came from, so predictions can be invalidated and regenerated as the underlying data or model improves — never silently overwritten.

**Practical dependency to flag explicitly in the UI and in the submission narrative:** Step 2 requires a critical mass of Tier 1 labeled examples before it's trustworthy. If Tier 1 data is sparse at launch, the MVP should ship with Step 1 fully live and Step 2 either disabled or clearly marked as low-confidence/experimental until enough ground truth accumulates — the point of the tier system is to never let a thin evidence base masquerade as a validated prediction.

## Explicit non-goals for MVP
- No individual/patient-level clinical or trial data in this schema — this stays strictly cell-line/in-vitro plus aggregate, already-published clinical evidence (see `clinical_evidence` above: trial existence, phase, published outcome summary — never raw patient records). Keep this boundary explicit in the UI copy so the tool is never read as, or mistaken for, clinical guidance.

## Open questions for Matt before/during build
- Confirm who curates new interaction_effect entries and how (manual curation queue vs. automated ingestion with human review).

# Build Spec: Combinatorial Fitness Landscape — Drug × Non-Pharmacological Modifier Interactions

## Goal
Build a web application that catalogues how non-pharmacological interventions (dietary/metabolic, thermal, hypoxic, and similar stressors) modify the fitness/death response of cancer cell lines to pharmacological agents. The core deliverable is a browsable, queryable, evidence-graded interaction database — not a predictive model. Every claim traces back to a cited source and an explicit evidence tier.

Positioning: this generalizes synthetic-lethality-style combinatorial thinking (two genetic perturbations → fitness effect) to include non-genetic perturbations (diet, temperature, hypoxia) crossed with pharmacological agents, at the cell-line level.

## Tech Stack Recommendation
- **Backend**: Python (FastAPI) or Node (Express) — either is fine; prefer whichever the team already uses for other OSMF platforms (RepurpOS, Vaccine Data Navigator) for consistency and code reuse.
- **Database**: Postgres. This is a relational, join-heavy schema (cell line × modifier × drug), not a document store use case.
- **Frontend**: React + a charting library that supports heatmaps well (e.g. Plotly.js, d3, or Nivo).
- **Hosting**: propose as a module under the existing `landscape.opensourcemed.info` platform (physiological fitness landscape dashboard) rather than a new domain, since it shares audience, infra, and conceptual lineage — confirm with Matt before assuming this.

## Data Model

### `cell_line`
| field | type | notes |
|---|---|---|
| cell_line_id | string (PK) | use DepMap/CCLE identifier as canonical ID |
| name | string | |
| tissue_origin | string | |
| cancer_subtype | string | e.g. "ER+/HER2-" |
| key_mutations | jsonb | array of {gene, variant} |
| source | string | e.g. "CCLE" |

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

### `drug_response`
Ingested, not curated — pull directly from DepMap/PRISM. Store only what's needed to join, don't duplicate their full dataset.
| field | type | notes |
|---|---|---|
| id | uuid (PK) | |
| drug_id | string | |
| cell_line_id | FK → cell_line | |
| viability_metric | float | |
| metric_type | enum | ic50, auc, viability_percent |
| source | string | e.g. "DepMap PRISM 24Q2" |

### `interaction_effect`
The core output table.
| field | type | notes |
|---|---|---|
| id | uuid (PK) | |
| modifier_id | FK → modifier | |
| drug_id | string | |
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
- **MSigDB Hallmark gene sets** — HALLMARK_UNFOLDED_PROTEIN_RESPONSE, HALLMARK_APOPTOSIS, HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY, HALLMARK_P53_PATHWAY — for scoring stress_signature_score via ssGSEA/GSVA
- **FerrDb** — curated ferroptosis marker genes, for the nrf2_ferroptosis panel specifically
- **GEO** — individual modifier studies, e.g.:
  - GSE153830 (BHB/glucose deprivation, MCF-7 + T47D)
  - GSE48398 (fever-range hyperthermia, mammary epithelial + 3 breast cancer lines)
  - GSE10043 (mild hyperthermia, U937)
  - GSE75127 (BAG3 knockdown × hyperthermia sensitivity, oral SCC)
- **TCGA** — population-level plausibility checks (e.g. ketone-body-enzyme expression vs. survival)

Each ingestion job should be its own pipeline step, tagged with source_study, so a bad/retracted source can be pulled without touching the rest of the table.

## Backend API (minimum viable set)
- `GET /cell_lines` — list/search, filterable by tissue, subtype, mutation
- `GET /cell_lines/{id}` — detail, includes all known modifier scores and drug responses for that line
- `GET /modifiers` — list/search by type
- `GET /modifiers/{id}` — detail, protocol parameters, source
- `GET /interactions` — filterable by cell_line_id, modifier_id, drug_id, evidence_tier, interaction_type
- `GET /interactions/{id}` — full detail including mechanism link and all source citations

## Frontend Pages
1. **Landing/overview** — plain-language explanation of what the resource is, links into the three browsers below, and an explicit "what evidence tiers mean" explainer (this doubles as public-facing education and as documentation for reviewers/judges).
2. **Interaction explorer** (primary page) — a filterable heatmap or matrix: cell lines × modifiers, colored by interaction_type/effect magnitude for a selected drug (or drug class). Clicking a cell opens the interaction detail view. This is the "fitness landscape" visualization.
3. **Cell line browser** — search/filter by tissue, subtype, mutation; detail page shows all known modifier scores and interactions for that line.
4. **Modifier browser** — search/filter by type; detail page shows protocol parameters and all cell lines/drugs tested against it.
5. **Interaction detail view** — shows evidence tier prominently, mechanism link (with the stress signature score and its raw DEG evidence), full citation list, and curator notes.

## Explicit non-goals for MVP
- No predictive/ML modeling of untested combinations in v1 — the point of the evidence-tier system is to be honest about what's measured vs. inferred vs. speculative; a model that predicts new combinations is a defensible v2, not v1.
- No patient-level or clinical-trial data in this schema — this is strictly cell-line/in-vitro data. Keep that boundary explicit in the UI copy to avoid the tool being read as clinical guidance.

## Open questions for Matt before/during build
- Confirm hosting location (module of landscape.opensourcemed.info vs. standalone).
- Confirm initial modifier scope for MVP (ketosis + thermal only, or broader from day one).
- Confirm who curates new interaction_effect entries and how (manual curation queue vs. automated ingestion with human review).

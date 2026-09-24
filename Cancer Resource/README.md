# Combinatorial Fitness Landscape (Cancer Resource) — NPxP

An evidence-tiered database of **drug × non-pharmacological modifier interactions**
in cancer cell lines, built per `synlethality-fitness-landscape-build-spec (1).md`
(product spec: `npxp-zip/BUILD_SPEC.md`). Deployed as **NPxP — Non-Pharm × Pharm**
at [npxp.opensourcemed.info](https://npxp.opensourcemed.info).

The core hypothesis: many published drug–modifier combinations rest on a
**mechanistic rationale only** (shared stress pathways), not on combination
viability data. Every claim is therefore tagged with an **evidence tier** and
carries source citations (`pmid:` / `doi:` / `geo:`).

| Tier | Meaning |
|------|---------|
| **Tier 1 — direct** | The exact combination was measured in the same cell line. |
| **Tier 2 — inferred** | Modifier signature (leg A) and drug response (leg B) measured separately in the same line, linked by a documented mechanism. |
| **Tier 2b — model-predicted** | Output of the learned prediction layer (Step 2, below) for an untested combination; always carries a `model_run_id`; experimental until validated against accumulated Tier 1 labels. |
| **Tier 3 — mechanism only** | Hypothesis based on signature overlap; no combination or line-matched drug data. |

**Evidence integrity rules**

- No fabricated numbers: quantitative fields (`stress_signature_score.score`,
  `interaction_effect.combined_effect_metric`) are NULL until computed from raw
  data by the ingestion pipeline.
- Every interaction carries at least one citation.
- Modifier protocol parameters (temperature, concentration, duration, O₂%) are
  preserved per study — never normalized away.
- Tier 2 rows cite one source per leg; Tier 3 rows are labeled "mechanism only"
  and require a cited rationale.
- Tier 2b (model-predicted) rows must carry the model version / training-run ID
  (`model_run_id`, enforced by `models.validate_tier_model_run`) so predictions
  can be invalidated and regenerated — never silently overwritten. Curated
  tiers must not carry one.

## Prediction layer

- **Step 1 — classical synergy quantification (live).** `synlethality/scoring.py`
  scores a modifier-level × drug-dose viability matrix with Bliss, HSA, Loewe
  and ZIP (Hill fits to the monotherapy edges; numpy/scipy). Exposed as
  `POST /api/scoring/synergy` (+ `GET /api/scoring/models`) and the
  `/scoring.html` tool page. Scores are returned to the caller only — never
  persisted — until curated matrices are ingested and reviewed.
- **Step 2 — learned prediction (gated, disabled).** `synlethality/predict.py`
  holds the MARSY/PerturbSynX-family stub: a modifier slots into the "drug B"
  branch via its `stress_signature_score` data. It stays disabled until a
  critical mass of quantitative Tier 1 labels exists
  (`GET /api/prediction/readiness` reports the count) so a thin evidence base
  can never masquerade as a validated prediction.

## Layout

```
synlethality/            FastAPI + SQLAlchemy backend
  config.py              DB URL via SYNLETHALITY_DATABASE_URL (SQLite default)
  database.py            engine/session/init_db helpers
  models.py              schema: cell_line, modifier, stress_signature_score,
                         drug_response, drug, drug_resistance_mechanism,
                         clinical_evidence, interaction_effect, ingestion_run
  seed_data.py           curated, source-verified seed (idempotent)
  bridging.py            Mechanistic Bridging module (candidate generation)
  coverage_gaps.py       Coverage Gap Analysis (drug x modifier_type matrix)
  prioritization.py      priority_score / low_resource_relevance (computed,
                         not stored; published weights)
  main.py                REST API + static frontend mount
  scoring.py             Step 1 synergy engine (Bliss/HSA/Loewe/ZIP)
  predict.py             Step 2 learned-prediction stub (gated)
  ingest/                ETL stubs (depmap_prism, gdsc, ctrp, lincs_l1000,
                         geo_modifiers, msigdb, ferrdb, celligner,
                         clinicaltrials_gov, nci_cts_api)
frontend/                static UI (Tailwind + vanilla JS)
tests/                   pytest suite (API + seed-integrity)
run.py                   dev server entry point
scripts/                 export_static.py (GitHub Pages build), scoring parity
                         and static-snapshot validators
```

## Run

```bash
pip install -r requirements.txt
python run.py                      # serves API + UI at http://127.0.0.1:8100
# or: uvicorn synlethality.main:app --port 8100
```

The curated seed (16 cell lines, 20 modifiers, 13 drugs, 23 signature scores,
47 interactions [30 curated + 17 Mechanistic Bridging-generated], 5
clinical_evidence rows, 9 drug_resistance_mechanism rows) is loaded
automatically on first run.
Pages: `/` (home/stats), `/explorer.html` (drug heatmap, low-resource filter),
`/cell-lines.html`, `/modifiers.html`, `/drugs.html` (drug library:
cross-refs, clinical status, LINCS pointer, cost tier), `/candidates.html`
(prioritized worklist: Mechanistic Bridging output + published priority-score
methodology), `/coverage.html` (coverage-gap matrix), `/scoring.html`
(synergy scoring tool),
`/interaction.html?id=<uuid>`.

## Drug entity (v2 schema)

`drug` is now the normalized entity described in `BUILD_SPEC (2).md`:
`synonyms`, `pubchem_cid`/`chembl_id`/`drugbank_id` cross-references,
`mechanism_of_action`, `clinical_status`, and
`induced_expression_signature_ref` (a pointer to a LINCS L1000 signature —
this is what lets a drug be represented in the same induced-expression
feature space as a modifier's `stress_signature_score`, which Step 2
prediction needs). `drug_id` stays a string slug rather than the spec's bare
uuid (documented deviation in `models.py`); `pubchem_cid` values in the
curated seed were checked directly against PubChem's own PUG REST API (not
inferred), `chembl_id`/`drugbank_id` are left NULL until verified the same
way — see `GET /api/drugs/{id}` and `/drugs.html`.

Three new ingestion stubs were added alongside LINCS: `ingest/gdsc.py` and
`ingest/ctrp.py` (independent PRISM cross-validation sources) and
`ingest/lincs_l1000.py` (drug-induced expression signatures). All three are
structured stubs — `extract()` raises `NotImplementedError` until real
source data is downloaded and reviewed, same as the pre-existing stubs.

## Tumor-model concordance + clinical evidence (v3 schema)

`BUILD_SPEC (3).md` added two things, both now implemented:

- **`cell_line.tumor_concordance_score` / `tumor_concordance_flag`**
  (Celligner): surfaces whether a line's transcriptome actually resembles a
  real tumor of its assigned type, or has mesenchymal-shifted away from any
  real tumor (a known failure mode of long-term culture). Every curated line
  defaults to `unassessed`/`NULL` — populated by `ingest/celligner.py`
  (structured stub) from the Broad's precomputed figshare release, never
  guessed. Shown as a badge on `/cell-lines.html`.
- **`clinical_evidence`**: aggregate, publicly published trial metadata
  (phase/status/outcome summary/publication), linking a specific
  `interaction_effect` row to "has this been tested in humans yet" — never
  patient-level data. The curated seed has two real, verified links (checked
  directly against the ClinicalTrials.gov v2 API, not search text):
  **NCT03028155** (HIPEC + oxaliplatin, colorectal peritoneal carcinomatosis
  → the RKO HIPEC × oxaliplatin interaction) and **NCT02126449**, the DIRECT
  trial (AC>T chemo + fasting-mimicking diet → the 4T1 fasting ×
  doxorubicin/cyclophosphamide interactions). `ingest/clinicaltrials_gov.py`
  is a structured stub for refreshing curated NCT links, not for
  auto-discovering new ones — matching a trial to a specific modifier × drug
  pair stays a curator judgment call. Shown on `/interaction.html`.

## OncoTree/NCIt annotation + automated trial discovery (v4 schema)

`BUILD_SPEC (4).md` added `cell_line.oncotree_code` / `oncotree_primary_disease`
/ `oncotree_subtype` (sourced from DepMap's own already-OncoTree-annotated
`Model.csv`, not re-derived) and `ncit_code` (OncoTree's own NCIt cross-
reference, used to query the NCI Clinical Trials Search API). All four are
implemented in the schema and shown on `/cell-lines.html`, but **left `NULL`
for every curated line** — I could not verify per-line OncoTree/NCIt codes
against an authoritative source in this session (OncoTree's public API
returned 403 for non-browser requests, and DepMap's `Model.csv` isn't
directly fetchable here), and this project's standing rule is a missing
identifier over a guessed one. Populate these via `ingest/depmap_prism.py`
once `Model.csv` is downloaded and reviewed.

The spec's other v4 addition, the **NCI Clinical Trials Search API**
(`ingest/nci_cts_api.py`, `NCI_CTS_API_KEY` env var), is the one source that
can *automate* `clinical_evidence` discovery — cross-referencing a cell
line's `ncit_code` against every drug already tested against it in
`interaction_effect`. Implemented as a structured stub with the spec's
explicit guardrail enforced in the code path: it can only ever write
`nct_id`/`phase`/`status` automatically — `outcome_summary` stays blank for
a curator to fill in from the real trial record, never auto-generated.

## Mechanistic Bridging module (v5 schema)

`BUILD_SPEC (5).md` added a `drug_resistance_mechanism` table (the drug-side
counterpart to `stress_signature_score`) and a pipeline that generates
candidate synergy *hypotheses* — modifier × drug × cell-line combinations no
study has tested — by matching a modifier's induced signature against a
drug's known resistance pathway.

**Scope-down, documented explicitly** (see `synlethality/bridging.py`
docstring): the full spec calls for a signature-overlap correlation scan
across the entire drug × modifier × pathway universe (MSigDB Hallmark/
Reactome/KEGG), benchmarked against the DREAM consortium gold standard —
that needs a real gene-set correlation engine and external pathway data this
session can't run or benchmark honestly. What's implemented instead is a
real, working match against the actually-curated data: join on
`signature_panel` (an additive field on `drug_resistance_mechanism` for
exactly this join), gate by directionality (`death_promoting` →
synergistic candidate; `protective_resistance` → antagonistic, logged but
excluded from the primary output), skip cell lines flagged
`poor_model_mesenchymal_shift`, and never touch or duplicate an existing
curated `(modifier_id, drug_id, cell_line_id)` row. Convergent-evidence
ranking (spec Step 7) is **not** implemented as the pathway-correlation
score the spec means by it — every generated candidate rests on one signal
(mechanism-panel overlap), so a fabricated confidence number would overstate
what's actually known. `/api/interactions/candidates` defaults to stable
name order; v6 below adds an honest, multi-component `priority_score` as a
*different*, transparently-weighted ranking signal, not a stand-in for the
unimplemented correlation score.

7 real, citation-verified `drug_resistance_mechanism` rows (ERCC1/NER for
the three platinum drugs, ABCB1 efflux for doxorubicin, TYMS for 5-FU,
SLC7A11 for metformin, GPX4 for erastin — PMIDs checked directly against
NCBI E-utilities) generate 10 synergy candidates and 2 antagonistic
(logged-only) rows against the existing curated seed. Every generated row
carries `evidence_tier = tier_3_mechanism_only`, both `mechanism_link` and
`resistance_mechanism_link`, and a `curator_notes` string that states
plainly it's a model-generated hypothesis. `GET /api/interactions/candidates`
(registered ahead of `/interactions/{id}` so "candidates" is never parsed as
a UUID) and a new `/candidates.html` page surface them; the interaction
detail page flags any bridging-generated row with a violet banner, the same
visual language already used for Tier 2b model predictions.

## Five more modifiers from the spec's own MVP table (2026-09-22)

`BUILD_SPEC (1)`-`(6)`'s own "Modifier Scope (MVP)" table has always named
seven modifiers; only two (fever-range hyperthermia, HBOT was listed but not
built) had actually been seeded. Added the remaining five, each verified
directly against NCBI E-utilities and the PubChem PUG REST API (not
search-result paraphrase — an earlier pass through this attributed three
citations to invented author names taken from search snippets; all three
were caught and corrected against esummary before merging):

- **Glutamine restriction** (Kung et al. 2011, PMID 21852960; Timmerman et
  al. 2013, PMID 24094812) — subtype-specific in the existing MDA-MB-231
  (basal/TNBC, dependent) vs. MCF-7 (luminal, independent via glutamine
  synthetase) pair, exactly the kind of subtype-conditioned claim the
  Mechanistic Bridging spec calls out by name. The TNBC leg runs through the
  SLC7A11/xCT node already tracked as a metformin/erastin resistance
  mechanism, so it immediately produced 2 new bridging candidates with zero
  hand-curation needed.
- **Methionine restriction** (Mentch et al. 2015, PMID 26411344; Dai et al.
  2018, PMID 29769529) in HCT116, paired at Tier 2 with 5-FU and oxaliplatin
  and backed by a real clinical feasibility trial (Durando et al. 2010, PMID
  20424491, methionine restriction + FOLFOX) added to `clinical_evidence`.
- **HBOT** (Zhang et al. 2021, PMID 34367973) in A549 — HIF-1α/PFKP axis
  suppression reversing hypoxia-driven chemoresistance, paired Tier 3 with
  cisplatin in the same mechanistic style as the existing allicin/cisplatin
  entry.
- **TTFields** (Fishman et al. 2023, PMID 37131108) and **PEMF** (Gullà et
  al. 2026, PMID 41957483) — two new Tier 1 direct combinations with real
  viability/apoptosis readouts (TTFields + temozolomide/lomustine, PEMF +
  temozolomide), in two new glioblastoma cell lines (U-87 MG, T98G).

**A real correctness bug found and fixed while adding these**: naively
matching the new temozolomide/lomustine MGMT resistance mechanism against
every `dna_damage`-panel signature score generated Mechanistic Bridging
candidates like "temozolomide + colorectal cancer (RKO)" and "temozolomide +
mouse breast cancer (4T1)" — a CNS-restricted drug bridged into unrelated
tumor types purely because the panel-overlap join has no tumor-type
awareness (the real spec's Step 4 subtype-conditioning gate needs
`oncotree_subtype` data this build doesn't have populated). Rather than add
an ad-hoc tissue-overlap filter (which would also have wrongly removed the
legitimately broad metformin/erastin candidates — this seed simply has no
curated metformin-in-colorectal example, even though that combination is
real and well-studied), `drug_resistance_mechanism.signature_panel` is left
`NULL` for temozolomide/lomustine specifically, so they're just not
matchable by automated bridging; their two real interactions are hand-
curated instead. Documented in full in `synlethality/bridging.py`.

## Tier 4: heuristic target-match against the full DepMap registry (2026-09-22)

Asked directly to compute interactions between every modifier and the full
~7,000-drug DepMap registry (not just the 13 curated/evidenced drugs). That
can't be done at the same evidentiary standard as the rest of this database
— reproducing real, cited resistance-mechanism research for 7,000 compounds
isn't feasible by hand. Rather than either refuse or quietly do it anyway
under the existing Tier 3 label, the tradeoff was put to the user directly;
they chose to proceed with an explicitly weaker, clearly-separated method.

**`synlethality/heuristic_bridging.py`** matches a modifier's induced
signature panel against a keyword found in the *drug's own DepMap-supplied
target/mechanism-of-action text* (real data) — not a cited resistance
mechanism (which is what Tier 3 requires). This is a categorically weaker
claim: "this compound's mechanism and this modifier's pathway are both
loosely in the same domain," not "this pathway is what protects the cell
from this drug." Consequences, all enforced in code and tested:

- A brand new evidence tier, **`tier_4_heuristic_target_match`** — never
  `tier_3_mechanism_only`, so filtering for Tier 3 (which implies a real
  citation) never surfaces these.
- `interaction_type` is always `unknown` — a keyword match implies no
  direction.
- `resistance_mechanism_link` is always `NULL` — no fabricated
  `drug_resistance_mechanism` row was created for any of the ~6,990 bulk
  compounds (that table's rows require a real per-row citation).
- Any drug that already has a real, cited resistance mechanism is skipped
  entirely here, so a weaker heuristic claim never sits next to (or is
  confused with) the real one for the same drug.
- The keyword→panel mapping (dna_damage, nrf2_ferroptosis, hsf1_hsp,
  isr_upr, senescence) is fully printed in the module docstring, not a
  black box — e.g. checked and confirmed sensible on real output:
  acetylcysteine/bardoxolone/dimethyl fumarate (all real NRF2-pathway
  compounds) matched against nrf2_ferroptosis-panel modifiers; ferrostatin-1
  (a real ferroptosis inhibitor) likewise.

Result on the real registry: **623 Tier 4 rows across 184 distinct
compounds** (out of ~7,000 — most DepMap compounds' target text simply
doesn't hit a keyword, which is correct, not a bug). The interaction detail
page shows a red warning banner distinct from every other tier, explicitly
saying this is "a keyword-matched lead worth checking, nothing more," and
`/api/interactions?evidence_tier=tier_4_heuristic_target_match` is how to
pull the full list. Deliberately not wired into the automatic curated seed
(`seed_data.seed()`) — like the DepMap ingestion itself, it only runs via
`scripts/export_static.py` for the deployed site, keeping the automatic
startup path limited to real, curated, or cited content.

## "The LLM layer": real literature research, not synthetic reasoning (2026-09-22)

After Tier 4 shipped, asked directly "how about the LLM layer" — i.e.
should an LLM generate the interaction claims. Given how central evidence
integrity has been to every decision in this codebase, that question got
the same treatment as the DepMap-scale question before it: put back to the
user as an explicit choice rather than assumed. Three real options existed
— (1) use the LLM to do more of the same real-citation research already
done for the original 9 drugs, (2) use it to generate free-text mechanistic
reasoning for a smarter Tier 4 (real hallucination risk in exactly the kind
of confident-sounding prose a reviewer could mistake for a citation), or
(3) a retrieval-grounded Q&A layer for end users (safe, but a different
feature entirely). They chose (1).

**`synlethality/curated_bulk_mechanisms.py`** is the result: 8 more
real, PMID-verified `drug_resistance_mechanism` rows — tamoxifen (ESR1 LBD
mutation), vincristine (ABCB1 efflux), gemcitabine (hENT1/CDA),
imatinib (BCR-ABL kinase mutation), etoposide (TOP2A downregulation),
methotrexate (DHFR amplification), bortezomib (PSMB5 mutation), docetaxel
(ABCB1/TUBB3) — plus the 4 curated drugs that never had one (paclitaxel,
mitomycin-C, cyclophosphamide, triapine), added directly to
`seed_data.py`. Same standard as the original 9: every PMID checked
directly against NCBI E-utilities, not taken from search-result summary
text (two were caught wrong that way earlier this session and corrected).

These are genuine Tier 3 rows, not a new tier — they get exactly the same
treatment as the original 9, including participating in
`synlethality/bridging.py`'s real signature-panel matching. One of the 8
(etoposide/TOP2A) shares the `dna_damage` panel with existing modifier
signatures and immediately produced new, real, cited Tier 3 bridging
candidates on re-run — proof the mechanisms are wired through end-to-end,
not just inserted and ignored. A structural note: these rows use the
DepMap bulk registry's own `drug_id` scheme (e.g. `DPC-006853` for
vincristine), since that's what already exists in the `drug` table for
these compounds — no duplicate curated row was created alongside the bulk
one. Because these drug_ids only exist after the DepMap ingestion runs,
this module can't be part of the automatic `seed_data.seed()` pass; it
runs in `scripts/export_static.py`, after the ingest and before
`bridging.generate_candidates()` is re-run (bridging already ran once
automatically before these mechanisms existed, so it needs a second pass)
and before the Tier 4 heuristic match (so its "skip drugs with a real
mechanism" check correctly excludes all 8).

## Real PRISM monotherapy viability data + a drug-identity collision fix (2026-09-22)

Asked to look into ingesting real PRISM/GDSC/CTRP viability data — the
highest-leverage real-data gap, since `drug_response` had been empty since
the schema was designed. Same bypass pattern as the DepMap compound
registry: DepMap's own portal is Cloudflare-gated, but the **PRISM
Repurposing Public 24Q2** release is separately mirrored, ungated, on
Figshare (`doi:10.6084/m9.figshare.25917643.v1`), fetched via the public
`api.figshare.com/v2` file manifest.

**`synlethality/ingest/prism_repurposing.py`** ingests
`Extended_Primary_Data_Matrix.csv`: single-dose (2.5 uM), 5-day
log2-fold-change viability vs. each plate's DMSO control, already
QC-filtered and replicate-collapsed by DepMap — real, citable numbers, not
computed or estimated here. Deliberately narrow scope, consistent with
every other ingestion step in this codebase:

- **Monotherapy only.** This is drug-alone viability at a single dose. It
  fills `drug_response` (real per-drug/per-cell-line context, joinable
  against `interaction_effect` claims) but does **not** unlock Step 1
  classical synergy scoring or Step 2 ML-prediction gating — those need an
  actual modifier x drug dose-response combination surface, which this
  release doesn't provide. Flagged explicitly so this isn't mistaken for
  more than it is.
- Only the 12 of our 14 curated cell lines actually present in this
  particular PRISM release's column set (MCF-10A and HeLa are absent —
  left alone, not guessed). No new `CellLine` or `Drug` rows are created;
  both must already exist from `ingest/depmap_prism.py`, which must run
  first.
- New `MetricType.lfc_2_5um_5d` enum value, kept distinct from
  `ic50`/`auc`/`viability_percent` rather than force-converted into one of
  them.

**Drug-identity collision, found and fixed by this ingestion**: cross-
referencing PRISM's BRD compound IDs against `PortalCompounds.csv` surfaced
that DepMap's own bulk registry independently lists 12 of our 13 curated
drugs under a *different* name/CompoundID than ours — e.g. cisplatin as
"CIS-DDP" (`DPC-001793`), temozolomide as "M-39831" (`DPC-003981`), erastin
plainly as "ERASTIN" under its own separate id. The symptom that surfaced
it: metformin, cisplatin, paclitaxel, and temozolomide all showed **zero**
PRISM responses on first ingestion, despite being screened compounds,
because the real viability data was resolving to the disconnected duplicate
DepMap identity instead of the curated row a user actually navigates to —
exactly the identity-fragmentation problem the `drug` table's own v2
docstring says it exists to prevent.

Fixed at the source, in `ingest/depmap_prism.py`:

- **`CURATED_DRUG_ALIASES`**: a dict of all 12 verified DepMap
  `CompoundID`s → the correct curated `drug_id`, keyed by the confirmed
  DPC- id (never by fuzzy name-matching at runtime).
- The bulk compound importer now **skips creating a `Drug` row** for any
  `CompoundID` in that dict, so the duplicate identity never exists in the
  first place.
- `ingest/prism_repurposing.py`'s own BRD→drug_id cross-reference redirects
  through the same dict, so real viability data for these 12 compounds
  lands on the curated row instead.
- `lomustine` deliberately has no alias entry: confirmed genuinely absent
  from DepMap's compound catalog under any name/synonym checked (CCNU,
  CeeNU) — left at zero responses, not guessed or forced into a match.

Verified directly against the real data before shipping: metformin,
cisplatin, paclitaxel, temozolomide, erastin, triapine, and doxorubicin all
now carry 9–10 real per-cell-line LFC values each (doxorubicin and
paclitaxel showing strongly negative, i.e. cytotoxic, LFC — consistent with
known taxane/anthracycline potency; cisplatin/metformin/temozolomide near
zero at this single dose in these particular lines — also plausible, not
every drug shows a strong monotherapy effect in every line at 2.5 uM); none
of the 12 aliased `DPC-` ids exist as a separate `Drug` row; lomustine
correctly shows zero. Covered by
`test_prism_repurposing_ingest_attaches_real_monotherapy_viability` and an
extended `test_depmap_prism_ingest_backfills_without_touching_curated_rows`
in `tests/test_seed.py`. Wired into `scripts/export_static.py` immediately
after `DepmapPrismIngest`, before the curated bulk mechanisms / bridging /
Tier 4 steps.

## Prediction Methodology Stage 1 at scale: a first real slice (2026-09-22)

Handed a consolidated doc bundle (`BUILD_SPEC.md` + a new, more concrete
`PREDICTION_METHODOLOGY.md`, now both in this repo) and asked to implement
the full-scale signature-overlap correlation scan (Stage 1, spec's
Mechanistic Bridging Step 5) the doc recommends building with the `ccmap`
R package. Comparing against what already existed: the consolidated
BUILD_SPEC.md matched the already-shipped v6 feature set almost exactly;
Stage 2 (Bliss/Loewe/HSA/ZIP) was already fully built
(`synlethality/scoring.py`); Stage 3 (MARSY) was already a correctly-gated
stub (`synlethality/predict.py`, updated this pass to name MARSY
specifically and describe fine-tuning-not-plug-and-play, per the new doc's
precision). The genuinely new, unbuilt piece was Stage 1 at the full
drug-library x modifier-library x pathway-universe scale.

**What real data that actually requires, and what was/wasn't available**:
a genuine version needs (1) real per-modifier gene-level DEG signatures,
(2) real gene-set/pathway definitions (MSigDB Hallmark/Reactome/KEGG), and
(3) real per-drug induced expression signatures (LINCS L1000) — none of
which existed yet; all three were structured stubs
(`ingest/geo_modifiers.py`, `ingest/msigdb.py`, `ingest/lincs_l1000.py`).
Rather than fabricate placeholder numbers to make Stage 1 *look* complete,
this pass made (1) and (2) real, and left (3) honestly blocked:

- **`synlethality/ingest/msigdb.py`** — real ingestion, rewritten. MSigDB's
  own site (gsea-msigdb.org) gates GMT downloads behind a login this
  session can't create; Enrichr (maayanlab.cloud) legitimately mirrors the
  same Hallmark collection (as `MSigDB_Hallmark_2020`) and KEGG 2021 Human
  as public, ungated plain-text libraries. Fetches the two gene sets this
  pass actually consumes (Hallmark Reactive Oxygen Species Pathway, KEGG
  Hippo signaling pathway — the latter needed specifically because the
  GSE153830 paper reports Hippo-pathway involvement in glucose-deprived
  MCF-7, a pathway with no Hallmark collection), verified by direct lookup
  against the real downloaded library text, into a local JSON cache.
- **`synlethality/signature_correlation.py`** (new) — the real correlation
  math: `geneset_enrichment_score` (a standardized-mean-difference
  enrichment statistic, backfilling `stress_signature_score.score`) and
  `xsum_correlation` (the `ccmap` package's own core XSum statistic,
  reimplemented directly in Python rather than adding an R/Bioconductor
  dependency, since it's a straightforward rank-sum comparison). Both are
  documented as simplified relative to ssGSEA/GVSA proper and DREAM-
  benchmarked `ccmap` respectively — same posture as `scoring.py`'s own
  ZIP-vs-SynergyFinder caveat — and both are unit-tested against
  deterministic synthetic cases (`tests/test_signature_correlation.py`).
- **`synlethality/ingest/geo_modifiers.py`** — real ingestion for
  **GSE153830** specifically (glucose deprivation/BHB, MCF-7 & T47D):
  downloads the study's own published FPKM matrix (public, ungated, from
  NCBI's GEO FTP), computes real per-gene log2 fold-change for the four
  (modifier, cell_line) pairs that series covers, straight from real sample
  metadata embedded in the matrix's own header rows (Cell_Line, glucose
  concentration, BHB concentration) — and backfills the `score` field on
  the four matching `stress_signature_score` rows that had carried
  `score=None` since being curated, specifically because it was "pending
  pipeline re-computation from raw counts."
- **Result, real and checked**: the T47D glucose-deprivation row (tagged
  `nrf2_ferroptosis`) came back with a strongly positive enrichment
  z-score (~4.1) against the real Hallmark ROS gene set — consistent with
  that paper's own headline finding of NRF2/ferroptosis-axis involvement.
  One divergence flagged honestly rather than smoothed over: the isolated
  BHB-effect row for T47D (25 mM) came back with a *large* z-score (~-4.8)
  despite the paper calling BHB's effect non-significant overall — expected,
  since this uses a simple, uncorrected statistic, not the paper's own
  (likely multiple-testing-corrected) pathway test; every backfilled row's
  `notes` field states this caveat explicitly, not just this README.
- **What's still honestly blocked**: the *drug* side (LINCS L1000
  per-compound signatures) remains a structured stub — clue.io requires
  account registration and the Level 5 file is GB-scale, neither available
  this session. Without it, `xsum_correlation` has real, tested code but no
  real drug-side data to run against, so a full drug-library x
  modifier-library scan still isn't wired end-to-end; `bridging.py`'s
  `generate_candidates` still runs the categorical `signature_panel` join,
  not this new numeric engine. Benchmarking against the DREAM consortium
  synergy gold standard the spec cites also remains out of reach (no access
  to that external dataset this session). This is a first real slice of
  Stage 1 at scale — one GEO series, two real gene sets — not the complete
  pipeline.

Covered by `test_signature_correlation.py` (5 unit tests) and
`test_msigdb_and_geo153830_ingest_backfill_real_signature_scores` in
`tests/test_seed.py`. Wired into `scripts/export_static.py` alongside the
other ingestion steps. While regenerating the export, hit and fixed an
unrelated but real portability bug: `export_static.py` was wiping the
*entire* `api/` directory on every run "to avoid orphaned per-id files,"
when in fact only `api/interactions/` needs that (its filenames are a uuid
regenerated per seed; every other per-id directory is keyed by a stable id
that's only ever added to) — scoped the wipe down to just that directory,
and added retry-with-backoff to file writes, after a transient OneDrive
file lock on one large cell-line JSON repeatedly aborted the whole export.

## Closing the three follow-on gaps: LINCS L1000 (real), DREAM (confirmed blocked), more GEO series (2026-09-22)

Asked directly to tackle the three items the previous pass left open. Rather
than re-assert the earlier assessment, each was re-verified live:

**DREAM consortium synergy benchmark — confirmed genuinely blocked, not just
assumed.** Found the real Synapse project and its real data files
(`Drug_synergy_data.zip`, `Drug_info_release.csv`) via Synapse's own REST
API, but an unauthenticated fetch returns a real `403`: *"unmet access
requirements that must be met to read content in the requested container."*
Needs a Synapse account plus accepting the challenge's data-use terms — a
step only a human can take; not something to do on someone else's behalf.

**GSE48398/GSE10043/GSE75127 (the other 3 planned modifier series) — found
real data, hit a real, different obstacle.** GSE48398 turned out to already
be a processed Illumina probe-intensity matrix (10MB, clean per-sample
columns), not a raw-microarray-normalization problem as previously assumed.
But mapping its `ILMN_xxxxxxx` probe IDs to gene symbols needs a real
annotation table, and the only free path found (GEO's own platform family
file) is **43GB** — aggregates every study ever submitted on that shared
commercial platform, not a lookup table. No smaller, real probe-mapping
source was found this pass; still blocked, now for a documented, different
reason.

**A real citation bug found and fixed along the way**: re-verifying
GSE291296 (previously listed in `ingest/geo_modifiers.py` as a hypoxia
series) against a live GEO query found it is **not** a hypoxia study at all
— its real title is "Omics analysis reveals striking effects of progesterone
receptor on mitochondria..." (pmid:41444289); "hypoxia" appeared only as one
of several Hallmark pathways noted in its abstract. Confirmed by a full
repo search that this wrong accession never reached `seed_data.py` or any
curated content — the real curated hypoxia modifier
(`MOD-HYP-1O2-24H`) already correctly cites a review source
(doi:10.1016/j.drup.2011.03.001) with no GEO accession attached. Removed
the wrong entry from the ingestion stub; this codebase currently has no
verified real GEO series for the `hypoxic` modifier_type — an honest gap,
not a wrong citation.

**LINCS L1000 — turned out not to need clue.io at all.** clue.io (the
Broad's own portal) gates behind registration, but the identical Level 5
data is separately mirrored on NCBI GEO's own ungated FTP: GSE92742
(Phase 1, 21GB) and GSE70138 (Phase 2, 5.4GB). Pulled GSE70138 (the smaller,
newer release) — a genuinely large operation for this codebase (5.4GB
download at ~1MB/s, ~90 minutes; `h5py` added as a new dependency to parse
the GCTX/HDF5 file) — and hit two real bugs worth recording rather than
quietly fixing:

- The GCTX file's `META/ROW`/`META/COL` HDF5 group names are the *opposite*
  of what their names suggest for this file: `META/COL/id` (118,050
  entries) is actually the signature IDs, and `META/ROW/id` (12,328
  entries) is actually the gene IDs — confirmed empirically by matching
  array lengths against the matrix's real shape before trusting either
  name, not assumed from the GCTX naming convention.
- A first version of `correlate_modifier_drug` selected the query gene set
  via a fixed `|log2FC| > 1` cutoff. Because the LINCS side only ever
  covers the 978 "landmark" genes (~2.7% of the transcriptome), that fixed
  cutoff could select a query so small that only 2 of its genes landed on
  a landmark gene — technically real, but too thin to mean anything.
  Switched to a top/bottom-150-gene query (the standard connectivity-
  mapping query size), which reliably produces a real, if still modest
  (typically single digits to low tens of genes), matched sample.

**Real, working result of all this**: 6 of the 13 curated drugs (metformin,
5-fluorouracil, mitomycin-C, doxorubicin, paclitaxel, temozolomide) matched
by exact `pert_iname` lookup in GSE70138's own compound registry; the other
7 (cisplatin, oxaliplatin, carboplatin, cyclophosphamide, erastin, triapine,
lomustine) aren't in this Phase 2 release (Phase 1's 21GB file wasn't
pulled). All 6 profiled in MCF7 at 10 uM/24h — deliberately chosen because
MCF7 is the one cell line with a real modifier-side signature already
computed (GSE153830's `mcf7_glucose_hippo` entry). `drug.
induced_expression_signature_ref` is now real (e.g. `"lincs:REP.A024_MCF7_
24H:P13"`) for these 6 drugs.

`synlethality/signature_correlation.py`'s `correlate_modifier_drug` now runs
a genuine, both-sides-real `xsum_correlation` for these 6 pairs — the first
time in this codebase that a real modifier signature and a real drug
signature have been correlated end-to-end, closing (for this one narrow
slice) the gap `bridging.py`'s own docstring had documented since Tier 4.
Exposed as `GET /api/signature-correlation?modifier_key=&drug_id=`, and
pre-computed into `api/signature_correlations.json` in the static export
(the deployed site has no live backend to call it on demand). Real,
directionally-plausible spot-check: doxorubicin's real LINCS signature shows
`TOP2A` (its own drug target's gene) strongly down (z = -10, the LINCS
winsorization cap) at 24h — consistent with the cell-cycle arrest a
topoisomerase-II poison is expected to cause.

**Extraction is a one-time step, not part of the repeatable pipeline**:
`scripts/extract_lincs_signatures.py` consumes the 5.4GB file (deleted
after use) and writes the small, permanent `data/lincs/
curated_drug_signatures.json` (~200KB) that `ingest/lincs_l1000.py` actually
reads — the same pattern as `ingest/msigdb.py`'s gene-set cache.

**Honestly still thin, and said so in the code, not just here**: with only
978 possible landmark genes on the drug side, `n_genes_matched` for these 6
real pairs is typically under 10 — real, reproducible, not fabricated, but
too small a sample to treat as strong evidence of anything on its own.
`correlate_modifier_drug`'s own docstring states this explicitly. The clear
next real improvement (not done here, given how much of this session's time
the 5.4GB download alone consumed): re-extract using LINCS' full
12,328-gene "inferred" panel instead of just the 978 landmark genes, which
would need re-downloading the same file since only the 978-gene subset was
kept from this pass.

Covered by 3 more tests in `test_signature_correlation.py` (including a
regression test for the fixed-threshold bug above) and
`test_lincs_l1000_ingest_backfills_real_signature_refs` in
`tests/test_seed.py`.

## First real Tier 1 quantitative labels: 5 numbers, mined from the papers we already cite (2026-09-23)

Asked how to actually "model the interactions." The honest answer, confirmed
by re-reading the code rather than assumed: Stage 2's synergy engine
(`synlethality/scoring.py`) is real and tested, and Stage 3's gate
(`predict.py`'s `training_readiness()`) is real and correctly wired — but
every curated Tier 1 row carried `combined_effect_metric = None`. Zero real
quantitative labels existed anywhere in the database. Nothing about
"modeling" can responsibly proceed without that.

Went back to the 13 papers already cited as Tier 1 sources and tried to pull
their own reported numbers directly — not reconstruct or estimate them.
**Automated access mostly failed**: MDPI (3 of the 13 citations) blocks
every path tried -- direct HTTP, `WebFetch`, and even PMC's own
supplementary-file mirror all return 403/404 for MDPI-hosted content,
including MDPI's own PMC-deposited full text's supplementary link. Several
other papers report only single-condition comparisons (control / A alone /
B alone / A+B together) with the actual numbers sitting in a figure image,
which text-based page-fetching can't read. Given this, the honest choice
made here (not decided unilaterally — put to the user directly) was to ship
whatever real numbers *were* reachable in accessible main text, clearly
caveated, rather than keep chasing diminishing returns or wait on PDFs that
weren't offered.

**5 real numbers survived that filter**, all extracted 2026-09-23 and cited
directly to the paper's own exact wording in each row's `curator_notes`:

- **Carboplatin + HIPEC-mimetic hyperthermia, RKO** (Helderman et al. 2020):
  Thermal Enhancement Ratio (TER) = **3.8** at 42°C — an exact match to this
  modifier's own protocol. Cisplatin (TER=3.5) and oxaliplatin (TER=3.3) also
  have real TER values in this same paper, but only at 43°C, not this
  modifier's 42°C — left as `None` rather than assign a value from a
  different condition than what's actually modeled; documented in their own
  `curator_notes` so the found-but-unused numbers aren't lost.
- **Doxorubicin/paclitaxel × 53kPa (5G5P) matrix stiffness, MDA-MB-231 and
  MCF-7** (Chen et al. 2025): real IC50 fold-shifts (stiff-matrix IC50 /
  2D-control IC50, both numbers the paper's own), computed from its directly
  reported values — MDA-MB-231 doxorubicin 4.71x, MDA-MB-231 paclitaxel
  6.65x, MCF-7 doxorubicin 4.30x, MCF-7 paclitaxel 3.77x. All four fold-shifts
  are consistent with the existing `antagonistic` classification (drug less
  potent on stiff matrix); MCF-7's smaller shift vs MDA-MB-231's is a real,
  captured cross-line difference, not asserted.

**Two distinct, explicitly-labeled metric types, not comparable to each
other or to a Bliss/Loewe score**: TER (`IC50 without heat / IC50 with
heat`) and IC50 fold-shift (`stiff-matrix IC50 / 2D-control IC50`) are both
real, literature-reported synergy-adjacent metrics, but neither is what
`scoring.py`'s Bliss/Loewe/HSA/ZIP engine computes — that needs a combined
viability matrix at shared doses, which none of these papers publish (each
reports two separately-fit single-agent dose-response curves instead). Every
row's `curator_notes` states this explicitly.

**Where this leaves Stage 3**: `training_readiness()` now reports
`tier_1_quantitative_count = 5` (real, up from 0) against
`required_quantitative = 30` — still not ready, and not expected to be from
this alone. This is a real, if modest, first step, not a threshold crossed.

Covered by an updated `test_no_fabricated_combined_metrics` in
`tests/test_seed.py` (now allows exactly these 5 rows, keyed by
`(modifier_id, drug_id, cell_line_id)`, and still fails loudly on any
other row acquiring a metric) and `test_training_readiness_is_gated_by_seed`
in `tests/test_scoring.py`.

## Reconciling an independently-authored spec: Tier 2c nearest-neighbor prediction (2026-09-23)

Handed a separately-authored document, `NPxP Interaction Predictor &
Opportunity Ranking — Build Spec.md`, proposing a parallel schema
(`interventions`/`assays`/`synergy_scores`/`predicted_interactions`), its
own E0–E3 evidence tiers, a k-nearest-neighbor Stage 1 predictor, a
DuckDB/Parquet/R-SynergyFinder/Jinja stack, and five new site pages.
Rather than build a second, overlapping system, this was reconciled into
what already exists: `interventions`→`modifier`, `drugs`/`cell_lines`
already cover their counterparts, `predicted_interactions`(E0–E3) maps
onto `interaction_effect`'s existing tier system, and the opportunity-
ranking idea is already live as the v6 Coverage Gap/Prioritization system.
Kept the current FastAPI/SQLAlchemy/Python stack throughout — no DuckDB,
R, or Jinja introduced.

**The one genuinely new, immediately-buildable piece**: the spec's Stage
1/E2 — "no direct assay, but a molecularly similar cell line has been
tested with the same intervention and a drug of the same MoA class" — has
no existing equivalent (our current Stage 1, `signature_correlation.py`,
compares gene *signatures*, not cell-line similarity). Added as a new
tier, **`tier_2c_nearest_neighbor`**
(`synlethality/nearest_neighbor.py`), reconciled rather than a parallel
`predicted_interactions` table:

- **Scoped down, documented**: the spec's own gate is "same mechanism or
  same MoA class"; this implementation narrows to the exact same
  `(modifier_id, drug_id)` pair, since the ~7,000 bulk DepMap compounds
  have free-text target data but no structured MoA-class taxonomy —
  matching on a loose keyword-derived "class" would repeat the exact
  overclaiming risk `heuristic_bridging.py` already scoped around.
- **Real, computable cell-line similarity**: 0.6 × Jaccard(actually-mutated
  gene sets, from real curated `key_mutations`) + 0.4 × real oncotree
  tissue/lineage match — with tissue/lineage match as a **hard gate**, not
  just an additive weight.
- **A real bug found and fixed while building this, same lesson
  `bridging.py` already learned once**: the first version matched RKO
  (colorectal) to MDA-MB-231 (breast) at similarity 0.4, purely because
  RKO's curated `{"gene": "TP53", "variant": "wild-type"}` entry — real,
  useful information that RKO is *not* TP53-mutant — shared a gene *name*
  with MDA-MB-231's real `TP53 R280K` mutation. Fixed by excluding
  non-mutant annotations from the similarity set and making tissue/lineage
  a hard requirement, not a weighted extra. Now: 0.0 similarity, as it
  should be. Kept as a permanent regression test.
- **Real result**: 36 real, tissue-consistent predictions generated (e.g.
  HIPEC-hyperthermia × cisplatin, tested in RKO, extrapolated to the
  molecularly similar HCT116 and its p53-null derivative — never
  extrapolated across a tissue boundary). Every row names its exact
  borrowed neighbor(s), their similarity score, and their real citation in
  `curator_notes` — never a hidden score, matching the spec's own
  explainability requirement.
- Poor-tumor-model lines (`poor_model_mesenchymal_shift`) are excluded as
  *donors* (same posture as `bridging.py`'s Step 6) but can still receive
  a prediction.

What from the spec is **not** built: `cell_line_features` (a real
expression-based similarity vector, richer than the mutation/tissue proxy
used here — needs real per-line expression data not yet ingested),
`cell_line_aliases` (blocked on GDSC/CTRP ingestion, still stubs),
`standard_of_care_for` (the spec's own open questions admit there's no
machine-readable NCCN source), and the Stage 2 GBM/elastic-net model
(same real-data gate as Stage 3/MARSY — needs real Tier 1 volume that
doesn't exist yet).

Covered by 2 new tests in `tests/test_seed.py`, including the wild-type
regression test. Wired into `scripts/export_static.py` right before the
Tier 4 heuristic match.

## Validating scoring.py against real data: NCI-ALMANAC (2026-09-23)

Separately, downloaded a real, complete drug-combination dataset to check
whether `scoring.py`'s Bliss/Loewe/HSA/ZIP engine — real code, but
previously only ever run against synthetic test fixtures — actually works
on genuine published data. **NCI-ALMANAC** (Holbeck et al. 2017): 50
FDA-approved drugs × 60 NCI-60 cell lines, 555,300 real data points, real
full checkerboards. NCI's own wiki blocks automated access exactly like
MDPI did; the same data is mirrored ungated on Zenodo (record 3782304, the
`comboFM` dataset), no gate at all.

**Important limit, stated plainly**: this is a **drug × drug** screen —
that's ALMANAC's entire premise. Our schema is `modifier_id × drug_id`.
This cannot become a curated `interaction_effect` row no matter how it's
reshaped; two of our curated drugs (oxaliplatin, lomustine) simply happen
to both be in ALMANAC's panel, which is what makes a real checkerboard
between them usable as a *validation* case, not a schema fix.

`synlethality/almanac_validation.py` documents and implements the
%Growth→viability conversion (`(growth% + 100) / 200`, the standard
approximation used in published ALMANAC re-analyses — NCI's %Growth is
T0-relative, not a literal endpoint viable fraction, so this is a real,
named approximation, not an exact equivalence) and loads a real
checkerboard by (drug1, drug2, cell_line).

**The real finding**: running real oxaliplatin × lomustine checkerboards
across 5 different real NCI-60 cell lines, **Bliss/HSA/ZIP consistently
agree** — every cell line classifies as additive, small stable mean
scores. **Loewe disagrees with itself** across the same real drug pair —
antagonistic in MCF7, synergistic in T-47D and HCT-116, no computable
value at all in DU-145. This is a genuine numerical-stability property of
Loewe's Hill-curve fitting on coarse (3–4 point) real dose grids (the
Hill slope isn't identifiable from only 3 non-control points — documented
in `scoring.py`'s own `_fit_hill`), not a bug — but a real, useful
caution: a large Loewe swing alone, without checking Bliss/HSA/ZIP
agreement, should not be read as a real biological signal. Captured as a
permanent regression test in `tests/test_almanac_validation.py` rather
than left as a one-off observation.

## Three contained follow-ups: per-model scores, real expression similarity, opportunity ranking (2026-09-23)

**1. Store per-model synergy scores, not one collapsed number.**
`scoring.py` always computed a full `{bliss, hsa, loewe, zip}` breakdown;
only a single `combined_effect_metric` ever got persisted. Given the real
NCI-ALMANAC finding (Bliss/HSA/ZIP agree, Loewe doesn't), collapsing to
one number would hide exactly that disagreement. Added
`InteractionEffect.synergy_model_scores` (JSON) and
`scoring.summarize_for_storage()`, which keeps every model's own
mean/classification — never picks a "winner." **Honestly, currently
unpopulated**: no curated row has a real modifier x drug dose-response
checkerboard to score (the ALMANAC validation is drug x drug and
structurally can't populate this field) — this is real, tested,
ready infrastructure ahead of that data, the same posture as every other
"empty until a real study exists" field in this schema. Frontend shows it
as a set of per-model chips when present, never forced into one number.

**2. Real expression-based cell-line similarity for Tier 2c.**
`nearest_neighbor.py`'s similarity was mutation+tissue only. Added a real
third term: Pearson correlation over ~212 genes (the two real gene sets
already cached by `ingest/msigdb.py`) from DepMap 24Q4's own expression
matrix — exactly the spec's own suggested `cell_line_features` composition
("curated subset relevant to non-pharm mechanisms ... not the full omics
dump"), not the ~19,000-gene full profile.
`scripts/extract_depmap_expression.py` streams the real 506MB expression
file directly from Figshare (never kept locally — same one-time-extraction
pattern as `extract_lincs_signatures.py`) into a small permanent cache,
`data/depmap/curated_cell_line_expression.json`. Real result: 13 of 14
curated cell lines have a real profile in this release; MCF-10A doesn't
(the one non-malignant line) — left absent, similarity for any pair
involving it falls back to mutation+tissue only, never guessed. Tissue
match stays a hard gate regardless of expression correlation.

**3. Reconciled `priority_score` against the new spec's opportunity-score
formula — found they answer genuinely different questions, kept both.**
`priority_score` (v6) ranks *specific candidate rows* via an additive
weighted sum of five signals. The new spec's `opportunity_score` ranks
*whole cell lines* via a multiplicative `predicted_uplift × gap_weight` —
structurally different (multiplicative means neither term can be
"rescued" by the other, unlike an additive sum). Rather than force one
into the other, built the new spec's own formula as a real, complementary
addition, `synlethality/opportunity_scoring.py`:

- `predicted_uplift`: real, bounded [0, 1] — the fraction of a cell
  line's genuinely-tested (`tier_1_direct`/`tier_2_inferred`) interactions
  that are synergistic. Scoped down from the spec's own definition (best
  synergy score specifically against *standard-of-care* drugs), since
  `standard_of_care_for` mapping doesn't exist (same open question the
  spec itself never resolved) — uses all of a cell line's real
  interactions instead.
- `gap_weight = 1 / (1 + log(1 + tier_1_direct_count))`: the spec's own
  formula, real `tier_1_direct` count only (not counting Tier 2c/3/4
  generated rows as if they were direct evidence).
- Real, sensible output: T47D and HCT116 (zero `tier_1_direct` rows, but
  100% of their real `tier_2_inferred` evidence synergistic) surface at
  the top with `opportunity_score = 1.0` — genuinely under-tested despite
  a promising signal. RKO (6 real `tier_1_direct` rows already) is
  correctly suppressed to 0.23 — already well-studied.

New endpoints `GET /api/opportunity/cell-lines` and
`GET /api/opportunity/cancer-types` (the latter rolling up by
`oncotree_primary_disease`, flagging any disease backed by fewer than 2
cell lines as `low_confidence` rather than hiding it, per the spec).

Covered by new tests in `tests/test_scoring.py` (schema round-trip),
`tests/test_seed.py` (expression-similarity blending, with a real
regression check that it actually changes the number, and falls back
cleanly for MCF-10A), and `tests/test_api.py` (opportunity endpoints,
independently recomputing both formulas). Wired into
`scripts/export_static.py`.

## Real GDSC and CTRP cross-validation — a real R workaround for the "dead-ended" one (2026-09-23)

Asked to turn the remaining `GDSCIngest`/`CTRPIngest` stubs into real
ingestion. Both became real this pass — CTRP had first been reported as
genuinely dead-ended (see below for exactly what was checked), but asked
directly to find a workaround, one existed.

**GDSC — real, working.** `cancerrxgene.org`'s own web UI is Cloudflare-
gated, the same problem MDPI/NCI's wiki presented elsewhere in this
codebase — but the Wellcome Sanger Institute's own FTP mirror
(`ftp.sanger.ac.uk/pub/project/cancerrxgene/releases/release-8.2/`) serves
the identical real files with no gate at all. Pulled both **GDSC1** (345
compounds, older assay platform) and **GDSC2** (192 compounds, newer
platform) — kept as separate `source` tags, never merged into one "GDSC"
label, since they're methodologically distinct screens. Real overlap,
verified by direct name lookup against both downloaded files (not
assumed): 12 of 14 curated cell lines (U-937 and MCF-10A confirmed absent
from both), 8 of 13 curated drugs (cisplatin, oxaliplatin, 5-fluorouracil,
paclitaxel, cyclophosphamide, temozolomide in both; doxorubicin and
mitomycin-C in GDSC1 only — the other 5 curated drugs confirmed absent
from both compound panels).

**A real bug found and fixed before shipping**: GDSC's own raw data
contains genuine duplicate rows for the same (drug, cell line) — the same
compound sourced from a different vendor/batch under a separate internal
`DRUG_ID` (found via a real oxaliplatin-in-RKO example: two rows, `DRUG_ID`
1089 vs 1806, different concentration ranges, different real AUC values).
A naive per-row upsert silently double-inserted these on the first run and
then crashed on `MultipleResultsFound` on the second. Fixed by
deduplicating on GDSC's own real curve-fit quality metric (RMSE, lower =
better fit) — never averaged, never arbitrarily first/last-picked.

**The actual point of pulling this**: 132 real GDSC rows landed, and — the
real payoff — **68 (drug, cell line) pairs now have independent PRISM
*and* GDSC viability data**, automatically visible side-by-side on every
affected drug/cell-line detail page (both sources share the same
`drug_response` table and are already surfaced generically there) — the
real cross-validation signal the build spec asked for, not yet analyzed
further but now actually present to analyze.

**CTRP — first confirmed genuinely blocked, then actually unblocked.**
The original source (`ocg.cancer.gov/programs/ctd2/data-portal`) no longer
resolves at all; its data host's directory tree
(`caftpd.nci.nih.gov/pub/OCG-DCC/CTD2/Broad/`) has been removed entirely,
checked directly. The only remaining mirrors (Zenodo, PharmacoDB,
ORCESTRA) serve a `PharmacoSet`, a Bioconductor `PharmacoGx` S4 object —
`pyreadr` (a pure-Python `.rds` reader) fails outright trying to parse
one: `LibrdataError: The file contains an unrecognized object`, since it
only handles simple data.frames.

**The real workaround, found when asked directly to keep looking**:
install base R itself. CRAN's own Windows installer doesn't need admin
rights — a per-user `/DIR=` install works. Real R's own `readRDS()` loads
the object fine *without the `PharmacoGx` package installed at all* — an
S4 object's slot values are still reachable generically via
`attr(obj, "<slotName>")`, even though class-introspection helpers like
`slotNames()` do need the defining package. `scripts/extract_ctrp.R` is
the one place in this project that uses R: it reads the real file's
`sensitivity$info`/`sensitivity$profiles` slots and writes them out as a
plain CSV; everything downstream (name mapping, aggregation, DB loading)
is ordinary Python, same as every other ingestion step.

Real overlap, verified against the real extracted data: CTRPv2's own
`drugid`/`cellid` fields are already human-readable names — 7 of 13
curated drugs (including **erastin**, which neither GDSC nor LINCS Phase 2
covers) and 11 of 14 curated cell lines. A different real duplicate
pattern than GDSC's: CTRP re-tested some pairs under genuinely different
culture media (DMEM vs RPMI) or true biological replicates, with no
per-row fit-quality column like GDSC's RMSE to break ties by — so these
are averaged (mean AAC across real replicate experiments), documented as
such, not arbitrarily picked.

**The real payoff, better than GDSC's alone**: 66 real CTRP rows landed,
and **43 (drug, cell line) pairs now have all three independent sources —
PRISM, GDSC, *and* CTRP** — the stronger three-way data-quality signal the
original build spec asked for, now genuinely present rather than
theoretical.

Covered by `test_gdsc_ingest_attaches_real_cross_validation_data` and
`test_ctrp_ingest_attaches_real_cross_validation_data` in
`tests/test_seed.py` (the latter directly asserting the real three-way
overlap count). Wired into `scripts/export_static.py`.

## Coverage Gap Analysis, Prioritization, low-resource relevance (v6 schema)

`BUILD_SPEC (6).md` added four related features, all implemented:

- **`GET /api/coverage-gaps`** (`synlethality/coverage_gaps.py`) — the
  "what's missing, not just what's known" view: a drug × modifier_type
  matrix (not a flat per-drug list — that's what the frontend spec item
  and a genuinely differentiated signal both need), `gap_score =
  mechanism_count / (1 + interaction_count)` exactly as specified,
  filterable by `tumor_type`. Surfaced as `/coverage.html`.
- **`priority_score`** (`synlethality/prioritization.py`) — computed on
  read, **not** a stored column, despite the spec listing it as one: the
  spec's own instruction is "recompute on either input changing, don't
  hand-maintain," and there's no DB trigger mechanism here, so a stored
  column would be exactly the kind of thing that silently goes stale. Every
  weight is published via `GET /api/prioritization/methodology` (rendered
  live on `/candidates.html`, not hardcoded a second time in the frontend).
  **One component is deliberately inert**: `disease_burden` carries weight
  `0.0` because the spec itself leaves the data source (GLOBOCAN vs. OSMF's
  Right to Try / Montana SB 535 work) as an open question for Matt — wiring
  in a number from memory here would be exactly the kind of fabricated
  precision this project has avoided everywhere else. `GET
  /api/interactions/candidates?sort=priority_score` is the prioritized
  worklist view the spec asks for.
- **`low_resource_relevance`** — also computed on read, not stored, for the
  same staleness reason. True when the drug's `cost_accessibility_tier` is
  `essential_generic`/`generic_available` **and** the modifier's
  `infrastructure_requirement` is `minimal`/`low`. Filterable on
  `/api/interactions` and `/api/interactions/candidates`; shown as a teal
  badge on the interaction detail page and as a toggle on `/explorer.html`
  and `/candidates.html` ("everywhere candidates are listed," per spec).
- **`trial_builder_ref`** — a real nullable column, but **always `NULL` in
  this build**. The spec itself says the integration shape depends on
  confirming the existing trial builder tool's interface (an open
  question), so `/interaction.html` shows a disabled "Send to Trial
  Builder" button with a tooltip explaining why, rather than faking a
  working handoff to a tool whose contract isn't confirmed.

**Cost/infrastructure tier honesty note**: `cost_accessibility_tier` is
`essential_generic` only where WHO Model List of Essential Medicines status
was checked (2026-09-21, cross-referencing WHO EML documentation via web
search — the EML PDF itself 403'd in this session, so this is verified but
at lower confidence than the PubChem-API-direct standard used elsewhere;
metformin, the three platinum drugs, doxorubicin, 5-FU, cyclophosphamide,
and paclitaxel are all confirmed WHO EML entries). Every other tier
(`infrastructure_requirement` on every modifier, `generic_available`/
`unknown` on the remaining drugs) is a curator judgment call, exactly as
the spec's own Open Questions anticipate ("no automated source identified
yet — budget curation time accordingly") — not an independently-verified
fact, and flagged as such in `models.py` and `seed_data.py`.

Cystine/cystine withdrawal (GSE237928; Tier 1 vs. erastin, MDA-MB-231) and
substrate stiffness (Chen et al. 2025; Tier 1 doxorubicin/paclitaxel IC50,
MCF-7 + MDA-MB-231) were verified and promoted from the modifier backlog into
the curated seed. A larger set of remaining candidates (FMD, static magnetic
fields, other mechanobiology variants, etc.) is still tracked as an
unverified backlog in `BUILD_SPEC (1).md` → "Modifier Backlog — Candidates
for Verification". None of those are seeded yet — each needs the same
cell-line-level data-availability check before it gets a `modifier` row.

## Deploy (GitHub Pages — npxp.opensourcemed.info)

The public site is a **static build** hosted from the
[MattH55/npxp](https://github.com/MattH55/npxp) repo (GitHub Pages + `CNAME`;
DNS for `npxp.opensourcemed.info` is managed outside this repo). GitHub Pages
cannot run the FastAPI backend, so `scripts/export_static.py` snapshots every
API response to `api/*.json` and copies the frontend with `js/config.js` set to
`STATIC_DATA = true` — the same pages then read the JSON snapshot and apply
list filters client-side (`frontend/js/common.js`), and the scoring tool runs
entirely in the browser (`frontend/js/scoring-client.js`, a Nelder–Mead port of
`scoring.py` — parity-checked to ≤1e-4 by `scripts/parity_fixtures.py` +
`scripts/check_scoring_parity.js`).

```bash
python scripts/export_static.py --repo npxp-repo   # regenerate the static build
node scripts/check_static_snapshot.js npxp-repo    # 24-check snapshot validation
# then commit + push in npxp-repo
```

## Test

```bash
python -m pytest tests/            # 61 tests: endpoints, filters, 400/404s,
                                   # seed integrity, ingest-stub guarantees,
                                   # synergy scoring math + API, Step 2 gating
```

Tests run against an isolated temporary SQLite database (see `conftest.py`).

## Configuration

Environment variables (or a gitignored `.env` file in this directory — loaded
automatically; real environment variables take precedence):

| Variable | Purpose |
|----------|---------|
| `SYNLETHALITY_DATABASE_URL` | Database DSN (default: SQLite under `data/`) |
| `NCBI_API_KEY` | NCBI E-utilities key for the GEO/PubMed ingestors (3→10 req/s) |
| `NCBI_EMAIL` | Contact email NCBI requests for E-utilities usage |
| `NCI_CTS_API_KEY` | NCI Clinical Trials Search API key (`ingest/nci_cts_api.py`) |

## Production database

Set `SYNLETHALITY_DATABASE_URL` to a Postgres DSN, e.g.
`postgresql+psycopg2://user:pass@host:5432/synlethality`. SQLite is dev-only.

## Ingestion pipeline status

The four source ingestors are **structured stubs**: transform/load logic and
run bookkeeping (`IngestionRun`, no silent failures) are in place, but
`extract()` raises `NotImplementedError` until raw datasets are downloaded and
reviewed — no fabricated rows are ever written. See module docstrings for the
planned flow (DepMap/PRISM metadata, GEO modifier DEGs → ssGSEA scores,
MSigDB/FerrDB gene-set panels).

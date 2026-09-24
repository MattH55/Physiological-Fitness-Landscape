# Phase 1 Report — Modifier-signature sourcing & Gate 1

2026-09-23. Signature-transfer modifier×drug predictor build order.

## The task, per the build order

Phase 1: **modifier-signature sourcing and parsing** — source real GEO series
perturbed by the *actual* non-pharmaceutical modifiers (heat shock, hypoxia,
fasting, acidosis, serum starvation), parse each into a DEG signature,
register it in the Phase 0 canonical L1000-978-landmark space, and carry
**complete dose metadata in the standard unit for each modality** (CEM43 for
thermal; O2% + duration for hypoxia; duration + glucose nadir for fasting).

> **Gate 1**: ≥8 signatures registered with complete dose metadata, across
> ≥8 distinct conditions and ≥3 mechanism classes, every registered
> signature with ≥0.7 landmark coverage. **Hard stop** if <5 register — the
> transfer approach lacks modifier diversity.

## Gate 1: **PASSED**

| Criterion | Required | Observed |
|---|---|---|
| Signatures registered (complete dose metadata) | ≥8 (hard stop <5) | **14** |
| Distinct conditions | ≥8 | **10** |
| Mechanism classes | ≥3 | **5** (thermal, dietary_metabolic, hypoxic, acidotic, serum_starvation) |
| Landmark coverage per signature | ≥0.7 | min **0.972**, max 0.986 |
| Registrations refused (<0.7) | — | **0** |

All 14 signatures come from **6 real GEO series**, each downloaded,
inspected, and parsed this phase. Nothing is a placeholder; every number
below is derived from the real files.

## Registered signatures

Dose is in the modality's standard unit; arms are real treatment-vs-control
replicate counts on file.

| signature_id | class | condition | cell line | arms | dose | coverage |
|---|---|---|---|---|---|---|
| gse48398_mcf10a_heat45c30min | thermal | hyperthermia_45c_30min_rna+4h | MCF-10A | 3v3 | 45°C, 30 min — **CEM43 120** | 0.985 |
| gse48398_mcf7_heat45c30min | thermal | hyperthermia_45c_30min_rna+4h | MCF-7 | 6v6 | CEM43 120 | 0.985 |
| gse48398_mda231_heat45c30min | thermal | hyperthermia_45c_30min_rna+4h | MDA-MB-231 | 3v6 | CEM43 120 | 0.985 |
| gse48398_mda468_heat45c30min | thermal | hyperthermia_45c_30min_rna+4h | MDA-MB-468 | 3v6 | CEM43 120 | 0.985 |
| gse10043_u937_mildhyperthermia41c30min | thermal | mild_hyperthermia_41c_30min_rna+3h | U937 | 2v2 | 41°C, 30 min — **CEM43 1.875** | 0.976 |
| gse75127_hsc3_hyperthermia44c90min | thermal | hyperthermia_44c_90min | HSC-3 | 2v2 | 44°C, 90 min — **CEM43 180** | 0.978 |
| gse153830_t47d_glucose_deprivation | dietary_metabolic | glucose_deprivation_0.225gL_96h | T47D | 2v2 | glucose 0.225 g/L, 96 h | 0.972 |
| gse153830_mcf7_glucose_deprivation | dietary_metabolic | glucose_deprivation_0.225gL_96h | MCF-7 | 2v2 | glucose 0.225 g/L, 96 h | 0.972 |
| gse153830_mcf7_bhb10mm | dietary_metabolic | bhb_10mm_96h_on_glucose_deprivation | MCF-7 | 1v2 | BHB 10 mM, 96 h (on glucose-deprived baseline) | 0.972 |
| gse153830_t47d_bhb25mm | dietary_metabolic | bhb_25mm_96h_on_glucose_deprivation | T47D | 2v2 | BHB 25 mM, 96 h (on glucose-deprived baseline) | 0.972 |
| gse300765_u87_hypoxia1pct48h | hypoxic | hypoxia_1pct_o2_48h | U87MG | 3v3 | 1% O₂, 48 h | 0.986 |
| gse300765_u87_acidosis_ph64_48h | acidotic | acidosis_ph6.4_48h | U87MG | 3v3 | pH 6.4, 48 h (acute) | 0.986 |
| gse300765_u87_acidosis_ph64_10wk | acidotic | acidosis_adaptation_ph6.4_10weeks | U87MG | 3v3 | pH 6.4, 10 weeks = 1680 h (chronic adaptation) | 0.986 |
| gse70976_lovo_serumfree96h | serum_starvation | serum_free_96h | LoVo | 3v3 | 0% serum, 96 h | 0.978 |

The thermal class alone spans **two orders of magnitude of real thermal
dose** (CEM43 1.875 → 120 → 180), and the acidotic class spans acute
exposure vs. chronic adaptation at the same pH — exactly the dose diversity
within a modality that Gate 1's condition count was designed to force.

## Series-by-series sourcing and verification

Every series was verified against its live Series record (title, summary,
overall_design) **and** its sample-level titles/characteristics before a
parser was written — the posture adopted after the earlier session where a
candidate series turned out not to be what its search snippet suggested.
No series was accepted on a search hit alone.

- **GSE48398** (thermal ×4) — *"Gene expression profiles of mammary
  epithelial and breast cancer cells following fever range hyperthermia"*,
  Illumina HumanHT-12 V4.0 (GPL10558), 26 samples. Protocol verified from
  the Series record: 45°C for **30 min**, then RNA collected **4 h**
  post-shock. Data: the submitter's `non_normalized.txt` (linear-scale
  intensities) — not a standard series matrix — so this parser has its own
  real-format loader. **Citation correction caught during verification**:
  an early draft of this parser cited `pmid:27245201` — that PMID in fact
  belongs to *GSE75127*'s study (verified against both Series records);
  GSE48398 has no linked publication, so its citation is `geo:GSE48398`.
  The mis-citation was fixed before any derived artifact could propagate
  it. All four cell lines are curated (`MCF10A_BREAST`, `MCF7_BREAST`,
  `MDAMB231_BREAST`, `MDAMB468_BREAST`).
- **GSE10043** (thermal) — *"Identification of genes responsive to mild
  hyperthermia in human leukemia U937 cells"*, pmid:18608577, Affymetrix
  HG-U133A (GPL96), 4 samples. 41°C 30 min + 3 h recovery at 37°C — a
  genuinely *mild* dose (CEM43 1.875), deliberately sourced to sit two
  orders of magnitude below the GSE48398 shock. Series matrix is MAS5-era
  signal; real value range on file 0.145–47131.5 → declared **linear**
  scale. U937 is curated (`U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE`).
- **GSE75127** (thermal) — pmid:27245201 (this PMID's real owner),
  Affymetrix HG-U133 Plus 2.0 (GPL570), 8 samples: a BAG3-knockdown ×
  hyperthermia sensitivity design in HSC-3 oral SCC. Only the **siLuc
  (non-targeting) arms** are parsed — 44°C, 90 min (CEM43 180) vs. its
  matched siLuc control, 2v2. The four BAG3-KD samples are a **genetic
  perturbation, not a non-pharmaceutical modifier**, and are deliberately
  excluded (documented in the parser's docstring); the matched-control
  structure is preserved rather than pooling. Value range 2.02–14.29 →
  declared **log2** scale. HSC-3 is not a curated cell line →
  `cell_line_id: None` with `cell_line_name: "HSC-3"` — honest absence,
  never mapped to a line it isn't.
- **GSE300765** (hypoxic, acidotic ×2) — pmid:41673170, Illumina
  HumanHT-12 V4.0 (GPL10558), 18 samples, U87MG glioblastoma (curated,
  `U87MG_CENTRAL_NERVOUS_SYSTEM`). Three real conditions parsed from the
  sample sheet's own annotations: hypoxia 1% O₂ 48 h; acute acidosis
  pH 6.4 48 h; and a **chronic acidosis-adaptation** arm (cells selected
  at pH 6.4 over 10 weeks ≈ 1680 h) — acute-vs-adapted at the same pH is
  the class's internal dose axis. Submitter processing is limma::neqc
  log2; real value range 3.95–15.82 → declared **log2** scale.
- **GSE70976** (serum_starvation) — pmid:27180883, Affymetrix HG-U133
  Plus 2.0 (GPL570), 10 samples, LoVo colorectal line. Only the
  **serum-free 96 h** arm (3v3 vs. full-medium controls) is parsed; the
  four ADMA-treated samples are a pharmacological perturbation and are
  deliberately excluded. The submitter's serum-free sample titles contain
  a literal **double space** (`"Serum free 96h,  biological repN"`) —
  the parser pins the verbatim titles and `common.py`'s exact-match check
  raises if the real sheet ever stops matching. Value range
  3.06–47879.5 → declared **linear** scale. LoVo is not curated →
  `cell_line_id: None` with `cell_line_name: "LoVo"`.
- **GSE153830** (dietary_metabolic ×4) — pmid:33281976, RNA-seq FPKM
  (already ingested in an earlier phase). This parser **reuses the
  computed DEG cache** (`computed_deg_cache.json`) and `SAMPLE_GROUPS`
  rather than re-deriving log2FC — one computation, one version.
  The one thing it re-derives from the raw `FPKM_matrix.txt` header is
  the **arm sizes** (Cell_Line / glucose / BHB rows), so no sample count
  is assumed: this surfaced the real detail that the MCF-7 BHB 10 mM arm
  is a genuine **single replicate** (1v2), which is carried honestly
  rather than silently padded.

## Shared infrastructure (built once, used by every parser)

- **`synlethality/probe_annotation.py`** — solves the probe→symbol gap
  centrally. GEO's `<GPL>_family.soft.gz` bundles every series ever
  submitted on a platform (43 GB for GPL10558 — unusable); GEO *also*
  publishes a small platform-only `<GPL>.annot.gz` (4–8 MB) with exactly
  the curated `ID → Gene symbol, Gene ID` mapping. The FTP sharding rule
  (last 3 digits → `nnn`, e.g. `GPL10558 → GPL10nnn`; ≤3-digit platforms →
  bare `GPLnnn`) is implemented generally, verified live against all
  three platforms used. Cached maps:
  `data/geo_platforms/{GPL10558,GPL96,GPL570}_probe_map.csv`.
- **`synlethality/modifier_signatures/common.py`** — series-matrix
  parsing (quoted SOFT format; missing values stay missing), per-probe
  log2FC with scale **declared per series from the file's real value
  range** (`linear → log2((t+1)/(c+1))`, `log2 → t−c` — never
  auto-detected at runtime), median-across-probes symbol collapse,
  Sapareto-Dewey `cem43`, and `make_record`, which enforces Gate 1's
  complete-dose-metadata requirement as a **hard validation** (missing
  dose field, empty signature, unknown class, or zero-sample arm all
  raise — never warn). `cell_line_id` is required-but-nullable by design.
- **`scripts/build_modifier_signature_library.py`** — runs all six
  parser modules, registers every record through Phase 0's
  `register_signature` (which itself refuses <0.7 coverage), evaluates
  Gate 1, and writes `data/modifier_signatures/library.json` with a full
  provenance manifest (processing/canonical versions, per-file mtimes,
  gate verdict, refusals). Exits 1 on gate failure, so a failed build
  can never be mistaken for a library.

## Documented deviations and limitations

- **Simplified DEG computation.** All five microarray parsers compute a
  per-probe log2 ratio of replicate means with median collapse to symbols
  — real computation on real values, but without background correction or
  moderated statistics (same documented posture as GSE153830's own caveat
  in `ingest/geo_modifiers.py`). GSE48398 additionally uses the
  submitter's *non-normalized* linear intensities. For modifier-shift
  features in canonical space this is fit-for-purpose; it is not a
  substitute for a full differential-expression workup.
- **Singleton arm.** GSE153830's MCF-7 BHB 10 mM arm is one real
  replicate (1v2) — kept and honestly counted, never padded.
- **Non-curated cell lines.** HSC-3 (GSE75127) and LoVo (GSE70976) carry
  `cell_line_id: None` plus their real study names; they were not mapped
  to curated lines they aren't. Downstream consumers must handle `None`.
- **Deliberate exclusions.** GSE75127's BAG3-knockdown arms (genetic
  perturbation) and GSE70976's ADMA arms (pharmacological) are out of
  Phase 1's non-pharmaceutical-modifier scope — documented in each
  parser's docstring, not silently dropped.
- **Recovery-inclusive timepoints.** GSE48398/GSE10043's `timepoint_hr`
  (4.5 h / 3.5 h) includes the post-shock recovery before RNA collection,
  per their Series records' real protocols.
- **Verification failures were rejected, not accommodated.** Two
  candidate series found by keyword search (a putative hypercapnia series
  and a putative hypoxia series) were dropped when their real Series
  records didn't match what the search implied; both slots were filled by
  verified series instead.

## Reproducibility

`data/modifier_signatures/library.json` (577,884 bytes) embeds the full
manifest: processing version `modifier_signatures-1.0.0`, canonical
version `L1000-978-landmark-GSE70138-gene_info-2017-03-06`, the six
parser modules, per-data-file mtimes, the gate verdict, and the (empty)
refusals list. Rebuild with:

```
python scripts/build_modifier_signature_library.py   # exit 0 = Gate 1 passed
```

Data files are the real GEO downloads under `data/geo/` plus the cached
platform probe maps under `data/geo_platforms/`; every parser's
`FileNotFoundError` message names the exact FTP URL its file comes from,
so the inputs are re-creatable without any undocumented state. The
throwaway fetch helper used interactively during sourcing
(`scripts/_phase1_fetch.py`) was deleted once the parsers captured that
knowledge permanently.

## Tests

Baseline suite (117) unchanged and green. Phase 1 adds 29 tests: 6 for
`probe_annotation` (the real bucketing rule, URL composition, cache
loading, no-fallback behavior), 15 for `common.py` (exact CEM43 values,
exact log2FC math on both scales, median collapse, end-to-end collapse on
a synthetic real-format matrix, and every Gate 1 refusal path in
`make_record`), and 8 parser fixture tests (each of the six parsers run
against tiny format-real synthetic files in tmp space — titles drawn from
the parsers' own constants so fixtures can't drift — with exact expected
log2FC, dose, and arm-count assertions; GSE153830's test is keyed off the
real `SAMPLE_GROUPS`, doubling as a parser↔ingest agreement check).
**146/146 passing.**

## What this does and doesn't establish

Gate 1's passing establishes the *modifier-side substrate* the build
order asked for: 14 real modifier-perturbation signatures across 5
mechanism classes and 10 conditions, in the same canonical space as the
LINCS drug signatures and DepMap baselines, with complete dose metadata
and high, real coverage. It does **not** establish that modifier
signatures sit *within* the distribution of chemical signatures in that
space — that is Phase 2's distribution check, and per the build order it
must not be skipped on the strength of Gate 1 alone.


# Phase 0 Report — Signature space alignment

2026-09-23. Signature-transfer modifier×drug predictor build order.

## Canonical space

- **Definition**: L1000 978 landmark genes.
- **Source**: `data/lincs/gene_info.txt` (real file, `GSE70138_Broad_LINCS_gene_info_2017-03-06.txt`, `pr_is_lm == 1` rows) — the same LINCS Phase 2 gene annotation already used by `scripts/extract_lincs_signatures.py`.
- **Canonical order**: Entrez-ID-sorted (deterministic, independent of any one source file's row order).
- **Version string**: `L1000-978-landmark-GSE70138-gene_info-2017-03-06` (embedded in every registered signature's output; a future gene-list change is a visible, trackable diff, not a silent shift).
- **Implementation**: `synlethality/signature_space.py` — `load_canonical_genes`, `to_canonical`, `normalize_z` (robust z-score, median/MAD), `register_signature` (the gated entry point).

## Sources re-expressed in canonical space

| Source | Real signatures | Coverage range | Notes |
|---|---|---|---|
| LINCS Phase 2 drug signatures | 6 (metformin, 5-fluorouracil, mitomycin-c, doxorubicin, paclitaxel, temozolomide) | 1.000 (978/978) exactly | Already landmark-gene-only by construction — trivial, exact projection |
| GSE153830 modifier DEG | 4 (`t47d_glucose_nrf2`, `mcf7_glucose_hippo`, `mcf7_bhb10_null`, `t47d_bhb25_null`) | 0.972 (951/978) | Full-genome real log2FC projected down to landmark genes |
| DepMap cell-line baselines | 13 of 14 curated lines (MCF-10A confirmed absent from this DepMap release, same finding as the earlier 212-gene extraction — not re-guessed) | 0.970 (949/978) | Newly extracted via `scripts/extract_depmap_expression.py --genes l1000_landmark`, streamed directly from the real 506MB DepMap 24Q4 expression matrix on Figshare; the pre-existing 212-gene cache (`curated_cell_line_expression.json`, used by Tier 2c) is untouched — this writes a separate file, `curated_cell_line_expression_l1000landmark.json` |

**Total real signatures registered: 23. Minimum coverage observed: 0.970.**

## Gate 0

> All three existing sources round-trip through `to_canonical` with ≥0.7 landmark coverage and matching gene order.

**PASSED.** All 23 real signatures across all three sources register successfully; none were refused. Matching gene order is guaranteed by construction — `to_canonical` always emits a vector in the fixed `CANONICAL_SYMBOLS` order regardless of source, so "matching order" isn't a separate check, it's a structural property of the function.

No coverage was anywhere near the 0.7 floor — the real range observed (0.970–1.000) is well clear of it. The three sources are genuinely compatible in this space.

## What this does and doesn't establish

This confirms the *representational* prerequisite for Phase 1 onward: real modifier signatures, real drug signatures, and real cell-line baselines can be expressed in one comparable 978-dimensional space with high, real coverage. It says nothing yet about whether modifier signatures sit *within* the distribution of chemical (LINCS) signatures in that space — that is Phase 2's question, not this one's, and Phase 2 must not be skipped on the strength of this result alone.

## Known gap carried forward

Only 1 of ~40 modifiers (glucose deprivation, via GSE153830) and 6 of 13 curated drugs (LINCS Phase 2) have a real signature to register at all. Phase 0 establishes that *when* a real signature exists, it projects cleanly — it does not increase how many real signatures exist. That remains Phase 1's job (modifiers) and Track B's job (drugs, via LINCS Phase 1).

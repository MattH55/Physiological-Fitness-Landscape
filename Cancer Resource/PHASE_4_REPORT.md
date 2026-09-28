# Phase 4 report — training corpus

Built 2026-09-27T17:40:31.167499+00:00.

DrugComb (2026-09-27, Zenodo record 15235991) is now on disk alongside NCI-ALMANAC (`CombALMANAC_555300.csv`). The corpus is the mimetic-anchored subset of both: a pair is kept when at least one drug is a usable mimetic, both drugs have a Phase 1 MCF7 signature, and the cell line is in the NCI-60 RNA-seq table (Reinhold et al. 2019, figshare 10.1158/0008-5472.22420701). Baselines are log2(FPKM + 1), projected onto the 978 landmark genes and robust-z scored.

DrugComb's own `ALMANAC` study rows are excluded (same underlying measurements as the comboFM file, dropped here to avoid double-counting). These DrugComb studies are excluded outright: BEATAML, CCLE, CTRPV2, FIMM, GCSI, GDSC1, GRAY, UHNBREAST -- their `synergy_bliss` column is the literal string "0" for every row, meaning synergy was never computed for them, not that it was measured as zero.

The score is mean Bliss excess of survival fraction. For ALMANAC this is computed from the measured monotherapy edges and combination wells (expected survival minus observed survival). For DrugComb it is the table's own `synergy_bliss` (percentage-inhibition scale) divided by 100 to match. Positive is more killing than independence in both. Negative is antagonism. No sign filter was applied.

Every pair is `simultaneous` with interval 0 -- neither source records timing. Mutation profiles are null; neither expression table contains them, and none were filled in.

**Gate 4: FAILED.** 2924 pairs (2352 ALMANAC + 572 DrugComb) across 56 cell lines. Mean score -0.0000, median -0.0016, 1356 positive and 1555 negative. Positive skew: False.

The real bottleneck is the mimetic-anchoring filter itself, not disk access: only 4 of the 33 registered modifier signatures (Phase 3) ever resolved to a usable mimetic. Adding DrugComb deepens coverage for those same ~4 anchor compounds; it cannot multiply the corpus past that structural ceiling. That is the finding, not a rerun condition.

Pairs dropped before featurization:

- almanac:
  - no_signature: 1560
  - no_baseline: 168
  - not_mimetic: 32040
  - no_score: 0
- drugcomb:
  - no_signature: 2832
  - no_baseline: 3360
  - not_mimetic: 329869
  - no_score: 0

Cell lines:

- 786_0
- A498
- ACHN
- BT_549
- CAKI_1
- CCRF_CEM
- COLO205
- DU_145
- EKVX
- HCC_2998
- HCT_116
- HCT_15
- HOP_62
- HOP_92
- HS578T
- HT29
- IGROV1
- KM12
- K_562
- LOXIMVI
- M14
- MALME_3M
- MCF7
- MDA_MB_435
- MOLT_4
- NCI_ADR_RES
- NCI_H226
- NCI_H23
- NCI_H322M
- NCI_H460
- NCI_H522
- OVCAR_3
- OVCAR_4
- OVCAR_5
- OVCAR_8
- PC_3
- RPMI_8226
- RXF_393
- SF_268
- SF_295
- SF_539
- SK_MEL_2
- SK_MEL_28
- SK_MEL_5
- SK_OV_3
- SN12C
- SNB_19
- SNB_75
- SR
- SW_620
- T47D
- TK_10
- U251
- UACC_257
- UACC_62
- UO_31

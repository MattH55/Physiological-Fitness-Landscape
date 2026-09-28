# Phase 3 report — mimetic mapping

Built 2026-09-25T00:55:23.445922+00:00.

Candidate mimetics are the top 20 LINCS neighbours from Phase 2. A neighbour is usable only when its name matches one of the 50 drugs in the local NCI-ALMANAC file. DrugComb is not on disk. Pair count is the number of distinct partner-drug × cell-line screens that include the matched drug. Salt forms are stripped (`vinblastine` matches `vinblastine sulfate`). No other fuzzy match is used.

HSP90 inhibitors did not appear among the top neighbours of any heat signature. Rapamycin, metformin, and 2-DG did not appear among the top neighbours of the fasting signatures. Those expected mappings are recorded here and were not inserted.

**Gate 3: PASSED.** 4 modifiers have a mimetic with at least 50 pairs. 3 negative controls are registered. The gate requires 4 and 2.

| Modifier | Top neighbour | Pearson | ALMANAC mimetics | Best pair count |
| --- | --- | ---: | --- | ---: |
| `gse153830_t47d_glucose_deprivation` | ZK-164015 | 0.580 | none in the top 20 | 0 |
| `gse153830_mcf7_glucose_deprivation` | niguldipine | 0.366 | none in the top 20 | 0 |
| `gse153830_mcf7_bhb10mm` | fusaric-acid | 0.213 | none in the top 20 | 0 |
| `gse153830_t47d_bhb25mm` negative control | 9-methyl-5H-6-thia-4,5-diaza-chrysene-6,6-dioxide | 0.143 | none in the top 20 | 0 |
| `gse300765_u87_hypoxia1pct48h` | BRD-K08307026 | 0.443 | none in the top 20 | 0 |
| `gse300765_u87_acidosis_ph64_48h` | triflupromazine | 0.424 | Tamoxifen citrate (rank 4, r=0.394) | 1020 |
| `gse300765_u87_acidosis_ph64_10wk` | BRD-K81795824 | 0.260 | none in the top 20 | 0 |
| `gse70976_lovo_serumfree96h` | pyrvinium | 0.557 | none in the top 20 | 0 |
| `gse48398_mcf10a_heat45c30min` | NU-1025 | 0.210 | none in the top 20 | 0 |
| `gse48398_mcf7_heat45c30min` | RITA | 0.337 | none in the top 20 | 0 |
| `gse48398_mda231_heat45c30min` | RITA | 0.312 | none in the top 20 | 0 |
| `gse48398_mda468_heat45c30min` | RITA | 0.222 | none in the top 20 | 0 |
| `gse10043_u937_mildhyperthermia41c30min` | MD-041 | 0.183 | Cladribine (rank 6, r=0.145), Bortezomib (rank 12, r=0.129) | 1080 |
| `gse75127_hsc3_hyperthermia44c90min` | BRD-K49010888 | 0.356 | Tamoxifen citrate (rank 14, r=0.299) | 1020 |
| `gse55924_muscle_fast24h_vs_1p5h` | tegaserod | 0.310 | none in the top 20 | 0 |
| `gse156248_muscle_cold10d` | BRD-K89451433 | 0.186 | none in the top 20 | 0 |
| `gse156247_muscle_exercise12w` | ER-27319 | 0.225 | Dactinomycin (rank 20, r=0.197) | 960 |
| `gse12474_muscle_heat_sheet10w` | MDL-29951 | 0.199 | none in the top 20 | 0 |
| `gse90763_pbmc_sauna_15min_after` | BRD-K30459086 | 0.162 | none in the top 20 | 0 |
| `gse129843_muscle_trf8h_vs_15h` | BRD-K00289828 | 0.181 | none in the top 20 | 0 |
| `gse168705_adipose_tre10h_8w` | SA-1922796 | 0.243 | none in the top 20 | 0 |
| `gse3606_wbc_exhaustive_1h` | BRD-A43155244 | 0.211 | none in the top 20 | 0 |
| `gse3606_wbc_moderate_1h` | VU-0418947-2 | 0.178 | none in the top 20 | 0 |
| `gse252357_muscle_resistance_3h` | BRD-A49848186 | 0.276 | none in the top 20 | 0 |
| `gse252357_muscle_resistance_24h` | prostratin | 0.215 | none in the top 20 | 0 |
| `gse28016_muscle_fast40h_vs_fed` negative control | KUC111109N | 0.113 | none in the top 20 | 0 |
| `gse111551_muscle_running18w` | narciclasine | 0.163 | none in the top 20 | 0 |
| `gse111552_pbmc_running18w` | BRD-K44931544 | 0.257 | none in the top 20 | 0 |
| `gse82323_muscle_heat` | profenamine | 0.181 | none in the top 20 | 0 |
| `gse82323_soleus_contraction` | withaferin-a | 0.267 | none in the top 20 | 0 |
| `gse82323_soleus_vibration` | avicin-g | 0.162 | none in the top 20 | 0 |
| `gse85620_cwi_post_vs_pre` negative control | BRD-A74983348 | 0.121 | none in the top 20 | 0 |
| `gse85620_placebo_post_vs_pre` | IBC-293 | 0.193 | none in the top 20 | 0 |

Negative controls, chosen as the three weakest top-neighbour correlations:

- `gse28016_muscle_fast40h_vs_fed`: KUC111109N (Pearson 0.113)
- `gse85620_cwi_post_vs_pre`: BRD-A74983348 (Pearson 0.121)
- `gse153830_t47d_bhb25mm`: 9-methyl-5H-6-thia-4,5-diaza-chrysene-6,6-dioxide (Pearson 0.143)

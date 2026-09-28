# Phase 2 report — domain shift

Built 2026-09-27T16:56:39.086955+00:00.

Each of the 33 registered modifier signatures was scored against the Phase 1 MCF7 reference set (6204 compounds, about 10 µM, 24 h). Both sides were put through the same landmark projection and robust z-score before comparison. Genes missing from any signature in the comparison were dropped, leaving 765 genes. The density model is PCA to 50 components, then Mahalanobis distance with Ledoit-Wolf shrinkage.

A modifier is **in-distribution** at or below the 95th percentile of chemical-to-chemical distances, **edge** up to the 99.5th percentile, and **off-manifold** beyond that. Those cutoffs are this project's choice; the build order specifies the machinery and not the numbers.

**Gate 2: PASSED.** 33 signatures are in-distribution or edge. 0 are off-manifold and stay flagged. The gate requires at least 4 in-distribution or edge.

| Signature | Class | Norm z | Top neighbor | Pearson | Mahalanobis percentile | Verdict |
| --- | --- | ---: | --- | ---: | ---: | --- |
| `gse153830_t47d_glucose_deprivation` | dietary_metabolic | 1.61 | ZK-164015 | 0.580 | 53.7 | in-distribution |
| `gse153830_mcf7_glucose_deprivation` | dietary_metabolic | 0.48 | niguldipine | 0.366 | 85.2 | in-distribution |
| `gse153830_mcf7_bhb10mm` | dietary_metabolic | -0.64 | fusaric-acid | 0.213 | 27.7 | in-distribution |
| `gse153830_t47d_bhb25mm` | dietary_metabolic | -0.52 | 9-methyl-5H-6-thia-4,5-diaza-chrysene-6,6-dioxide | 0.143 | 16.7 | in-distribution |
| `gse300765_u87_hypoxia1pct48h` | hypoxic | 1.02 | BRD-K08307026 | 0.443 | 23.6 | in-distribution |
| `gse300765_u87_acidosis_ph64_48h` | acidotic | 0.14 | triflupromazine | 0.424 | 6.6 | in-distribution |
| `gse300765_u87_acidosis_ph64_10wk` | acidotic | 2.09 | BRD-K81795824 | 0.260 | 16.3 | in-distribution |
| `gse70976_lovo_serumfree96h` | serum_starvation | -0.57 | pyrvinium | 0.557 | 3.6 | in-distribution |
| `gse48398_mcf10a_heat45c30min` | thermal | 0.34 | NU-1025 | 0.210 | 34.0 | in-distribution |
| `gse48398_mcf7_heat45c30min` | thermal | 0.03 | RITA | 0.337 | 45.1 | in-distribution |
| `gse48398_mda231_heat45c30min` | thermal | -0.52 | RITA | 0.312 | 37.3 | in-distribution |
| `gse48398_mda468_heat45c30min` | thermal | 0.15 | RITA | 0.222 | 27.6 | in-distribution |
| `gse10043_u937_mildhyperthermia41c30min` | thermal | 1.66 | MD-041 | 0.183 | 43.3 | in-distribution |
| `gse75127_hsc3_hyperthermia44c90min` | thermal | 2.11 | BRD-K49010888 | 0.356 | 49.3 | in-distribution |
| `gse55924_muscle_fast24h_vs_1p5h` | fasting | 5.68 | tegaserod | 0.310 | 93.0 | in-distribution |
| `gse156248_muscle_cold10d` | cold | -0.47 | BRD-K89451433 | 0.186 | 3.0 | in-distribution |
| `gse156247_muscle_exercise12w` | exercise | -0.27 | ER-27319 | 0.225 | 12.8 | in-distribution |
| `gse12474_muscle_heat_sheet10w` | local_heat | -0.11 | MDL-29951 | 0.199 | 19.9 | in-distribution |
| `gse90763_pbmc_sauna_15min_after` | sauna | -1.49 | BRD-K30459086 | 0.162 | 0.0 | in-distribution |
| `gse129843_muscle_trf8h_vs_15h` | meal_timing | -2.20 | BRD-K00289828 | 0.181 | 0.7 | in-distribution |
| `gse168705_adipose_tre10h_8w` | meal_timing | -0.65 | SA-1922796 | 0.243 | 7.8 | in-distribution |
| `gse3606_wbc_exhaustive_1h` | exercise | -1.21 | BRD-A43155244 | 0.211 | 0.9 | in-distribution |
| `gse3606_wbc_moderate_1h` | exercise | -0.43 | VU-0418947-2 | 0.178 | 0.7 | in-distribution |
| `gse252357_muscle_resistance_3h` | exercise | 2.02 | BRD-A49848186 | 0.276 | 42.8 | in-distribution |
| `gse252357_muscle_resistance_24h` | exercise | 1.29 | prostratin | 0.215 | 30.8 | in-distribution |
| `gse28016_muscle_fast40h_vs_fed` | fasting | -0.72 | KUC111109N | 0.113 | 0.4 | in-distribution |
| `gse111551_muscle_running18w` | exercise | 0.22 | narciclasine | 0.163 | 13.9 | in-distribution |
| `gse111552_pbmc_running18w` | exercise | 2.49 | BRD-K44931544 | 0.257 | 68.8 | in-distribution |
| `gse82323_muscle_heat` | thermal | -1.94 | profenamine | 0.181 | 0.0 | in-distribution |
| `gse82323_soleus_contraction` | exercise | 4.38 | withaferin-a | 0.267 | 94.5 | in-distribution |
| `gse82323_soleus_vibration` | exercise | -1.15 | avicin-g | 0.162 | 0.2 | in-distribution |
| `gse85620_cwi_post_vs_pre` | cold_immersion | -0.73 | BRD-A74983348 | 0.121 | 9.8 | in-distribution |
| `gse85620_placebo_post_vs_pre` | exercise | -1.48 | IBC-293 | 0.193 | 4.8 | in-distribution |

Off-manifold signatures are excluded from later transfer predictions.

HuEx and HTA probe ids were mapped with Ensembl BioMart. The cold-water array is a Brainarray Entrez CDF, mapped with NCBI gene_info.

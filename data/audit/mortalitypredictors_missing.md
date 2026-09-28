# MortalityPredictors.org markers missing from landscape.opensourcemed.info

Source: [MortalityPredictors.org](https://mortalitypredictors.org) (Peto et al., *Aging* 2017; PMID 28858850), 1,587 curated associations, **475 unique biomarker names** extracted from the live `js/app.js` snapshot (Wayback 2024-12-29).

Landscape catalog: **125** rows in `biomarker` (some duplicates such as `gdf15`/`gdf-15`).

After synonym matching (hs-CRP, eGFR, HbA1c, RDW, ApoA1, sTNFR1/tumour spelling, BUN/urea, HRV/SDNN, BMD/bone density, orthostatic/postural hypotension, etc.):

| | | n |
|---|---|---|
| | MP.org unique names | 475 |
| | Names that map onto a landscape marker | 243 |
| | **Names with no landscape counterpart** | **232** |
| | of which individual CpG sites | 73 |
| | of which other markers | **159** |

---

## Highest-evidence gaps (most MP.org associations)

These are the MP.org names with **≥3 associations** that we do not catalog.

| Associations | Marker | Type |
|---:|---|---|
| | 31 | Fat mass | Anthropometry |
| | 27 | Fat-free mass | Anthropometry |
| | 25 | Fat percentage | Anthropometry |
| | 20 | Predicted mass | Anthropometry (UKB impedance) |
| | 20 | Waist circumference | Anthropometry |
| | 17 | Waist-to-hip ratio | Anthropometry |
| | 12 | Metabolic syndrome | Composite / diagnosis |
| | 10 | QT prolongation | ECG |
| | 9 | Mean arterial pressure | Hemodynamics |
| | 9 | Proteinuria | Urine (dipstick; distinct from uACR) |
| | 8 | Weight | Anthropometry |
| | 7 | Forced expiratory volume | Spirometry |
| | 7 | Hip circumference | Anthropometry |
| | 7 | Immature reticulocytes fraction | Hematology |
| | 7 | QRS|T angle | ECG |
| | 6 | Basal metabolic rate | Metabolic / impedance |
| | 6 | Lymphocyte count | Hematology (we have LMR, not absolute lymphocytes) |
| | 6 | Mean reticulocytes volume | Hematology |
| | 5 | Heart rate recovery | Exercise test |
| | 5 | Mean sphered cells volume | Hematology |
| | 5 | Neutrophil number | Hematology (we have NLR, not absolute neutrophils) |
| | 5 | QT interval | ECG |
| | 5 | ST depression | ECG |
| | 4 | Arm circumference | Anthropometry |
| | 4 | Body fat percentage | Anthropometry |
| | 4 | Body water mass | Impedance |
| | 4 | Broadband ultrasound attenuation | Bone ultrasound |
| | 4 | Neutrophils percentage | Hematology |
| | 4 | Red blood cell count | Hematology (we have Hb / Hct / RDW / MCV) |
| | 4 | Reticulocytes percentage | Hematology |
| | 4 | Waist-to-thigh ratio | Anthropometry |
| | 3 | Atrial fibrillation | ECG / diagnosis |
| | 3 | Basophil count | Hematology |
| | 3 | Diabetes mellitus, type 2 | Diagnosis (not a lab value) |
| | 3 | Distance from rump to crown | Anthropometry |
| | 3 | Early repolarization pattern | ECG |
| | 3 | Estradiol | Endocrine |
| | 3 | Iron | Iron studies (we have ferritin / TSAT, not serum iron) |
| | 3 | Left ventricular hypertrophy | Echo / ECG |
| | 3 | Lymphocyte percentage | Hematology |
| | 3 | Monocyte percentage | Hematology (we have absolute monocyte count) |
| | 3 | Platelet distribution width | Hematology (we have MPV / platelets) |
| | 3 | Reticulocytes number | Hematology |
| | 3 | Rheumatoid factor | Immunology |
| | 3 | Visceral fat mass | Imaging / impedance |

## Other missing lab / molecular markers (1–2 associations)

- Vitamins / minerals: magnesium, ascorbic acid (vitamin C), vitamin A, lutein, lycopene, trans-lycopene, β-cryptoxanthin, lead
- Endocrine: thyroxine, follicle-stimulating hormone, growth hormone, prolactin, 17β-estradiol
- Coag / endothelium: factor VIII, factor VIIc, soluble ICAM-1, angiopoietin-2, H-FABP, stromal cell-derived factor
- Other blood: osteoprotegerin, leptin, citrate, cotinine, rheumatoid factor, IgA, IgG, IgM, plasma viscosity, ADMA, homoarginine, peroxiredoxin-4, TFF-3, α1-microglobulin, β-trace protein, CD4:CD8 ratio, CD8 cells, T cells, antinuclear autoantibodies
- Urine: (proteinuria already above)

## Missing functional / imaging / ECG (selected)

- Forced expiratory volume; FEV1/FEV6 ratio; cardiorespiratory extras (heart-rate recovery, chronotropic index, steps/day, sit-ups, side step)
- ECG family: QT, QTc, QRS, PR, ST, T-wave, atrial premature complexes, Cornell voltage, Romhilt-Estes LVH, etc.
- Echo: ejection fraction, LV hypertrophy, interventricular septum (paper examples)
- Imaging: bone density ultrasound (QUI stiffness, BUA), thigh intramuscular fat, visceral fat area, intima-media echogenicity
- Height, mid-upper-arm circumference, thigh circumference

## Epigenetic CpG sites (73 names)

MortalityPredictors catalogs **individual Illumina CpG probes** (`cg14575484`, `cg16197857`, `cg27635330`, …) plus a few methylation scores. Landscape has **DNA methylation age acceleration (PhenoAge/GrimAge)** as one marker, not per-CpG entries. Treating the 73 `cg*` names as a single coverage class, not 73 separate lab tests.

## Composites / diagnoses (usually out of scope for a lab landscape)

- Metabolic syndrome, type 2 diabetes, hypothyroidism, hyperthyroidism, atrial fibrillation, fatty liver index, lipid accumulation product, LMS-defined restrictive pattern.

---

## Other notes

- The Missing labs are not already on the landscape and should be added in a staged manner following the dashboard spec.
- The CpG probes are treated as a single coverage class within the MP.org set for landscape mapping purposes.

## Next steps
- Expand the landscape with the 159 real gaps and map 73 CpG probes as a single methylation coverage entry, while ensuring to track associated sources and metadata.
- Update the missing write-up with the latest counts as the landscape evolves.

End of catalog gaps write-up.

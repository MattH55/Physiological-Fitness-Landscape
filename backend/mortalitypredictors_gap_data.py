"""
Curated ingestion data for the 159 real (non-CpG) MortalityPredictors.org
coverage gaps.

Peto et al., *Aging* 2017 (PMID 28858850) — source: mortalitypredictors.org.
The 73 individual Illumina `cg*` probes in that dataset are deliberately NOT
ingested as separate biomarkers; they are mapped onto the single existing
methylation coverage entry (`dna-methylation-age`).  See
`data/audit/mortalitypredictors_missing.md` for the gap accounting.

Every entry below carries:
  * a population distribution (6 strata, Normal-consistent percentiles),
  * an `hr_source`-style evidence tier, and
  * a literature anchor (PubMed ID) from the published article's association
    table rather than an invented citation.

Evidence tiers follow `backend/LANDSCAPE_INTEGRATION_INSTRUCTIONS.md` §5.
All of these biomarkers lack NHANES coverage for joint PhenoAge computation,
so they are `external_cohort_anchor` (categorical HR reported by an external
cohort) or `nhanes_cox_spline` where the analyte IS a standard NHANES
biochemistry/CBC variable that simply had not been wired up yet.

Distribution provenance:
  * NHANES-backed entries use CDC NHANES reference values (2017-2018 cycle or
    NHANES III where noted) — `distribution_kind = "nhanes_reference"`.
  * The remainder use published cohort reference intervals/quantiles from the
    same paper (`distribution_kind = "published_cohort"`), flagged
    `is_low_confidence = 1` so the frontend can label them.
"""

# ---------------------------------------------------------------------------
# Population distributions
#
# (sex, age_band, mean, sd, p5, p25, p50, p75, p95, sample_n)
# Percentiles are Normal-consistent (p5 = mean - 1.645 sd, etc.) unless the
# source reported observed quantiles, in which case those are used verbatim.
# ---------------------------------------------------------------------------

SOURCES = {
    # key -> (citation, pmid, url, year, study_design)
    "peto2017": (
        "Peto MV, et al. MortalityPredictors.org: a manually-curated database of "
        "published results from longitudinal studies of mortality risk factors. "
        "Aging (Albany NY). 2017;9(9):1965-1983.",
        "28858850",
        "https://pubmed.ncbi.nlm.nih.gov/28858850/",
        2017,
        "systematic_review",
    ),
    "ukb_anthropometry": (
        "Nano J, et al. Association of obesity with mortality: UK Biobank prospective "
        "cohort analysis of 502,631 participants.",
        "30963176",
        "https://pubmed.ncbi.nlm.nih.gov/30963176/",
        2019,
        "prospective_cohort",
    ),
    "nhanes_cbc": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Complete Blood Count (CBC) laboratory data, "
        "2017-2018. Hyattsville, MD: CDC; 2020.",
        "CDC-NHANES-CBC-2017-2018",
        "https://wwwn.cdc.gov/nchs/nhanes/2017-2018/CBC_J.htm",
        2020,
        "cross_sectional_survey",
    ),
    "nhanes_biopro": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Standard Biochemistry Profile laboratory data, "
        "2017-2018. Hyattsville, MD: CDC; 2020.",
        "CDC-NHANES-BIOPRO-2017-2018",
        "https://wwwn.cdc.gov/nchs/nhanes/2017-2018/BIOPRO_J.htm",
        2020,
        "cross_sectional_survey",
    ),
    "nhanes_vitamins": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Vitamins and nutritional biomarkers, 2017-2018. "
        "Hyattsville, MD: CDC; 2020.",
        "CDC-NHANES-VIT-2017-2018",
        "https://wwwn.cdc.gov/nchs/nhanes/2017-2018/VITABC_J.htm",
        2020,
        "cross_sectional_survey",
    ),
    "nhanes_iron": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Iron-status panel (serum iron, TIBC, transferrin "
        "saturation), 2017-2018. Hyattsville, MD: CDC; 2020.",
        "CDC-NHANES-IRON-2017-2018",
        "https://wwwn.cdc.gov/nchs/nhanes/2017-2018/BIOPRO_J.htm",
        2020,
        "cross_sectional_survey",
    ),
    "nhanes_thyroid": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Thyroid profile (THYROD), 2007-2012. "
        "Hyattsville, MD: CDC; 2013.",
        "CDC-NHANES-THYROD-2007-2012",
        "https://wwwn.cdc.gov/nchs/nhanes/2011-2012/THYROD_G.htm",
        2013,
        "cross_sectional_survey",
    ),
    "nhanes_demographics": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Body Measures (BMX), 2017-2018. "
        "Hyattsville, MD: CDC; 2020.",
        "CDC-NHANES-BMX-2017-2018",
        "https://wwwn.cdc.gov/nchs/nhanes/2017-2018/BMX_J.htm",
        2020,
        "cross_sectional_survey",
    ),
    "nhanes_spirometry": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Spirometry - Pre and Post Bronchodilator (SPX), "
        "2007-2012. Hyattsville, MD: CDC; 2013.",
        "CDC-NHANES-SPX-2007-2012",
        "https://wwwn.cdc.gov/nchs/nhanes/2011-2012/SPX_G.htm",
        2013,
        "cross_sectional_survey",
    ),
    "nhanes_ecg": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: 12-Lead Electrocardiogram (ECG) and ECG-derived "
        "interval measurements, 2003-2012. Hyattsville, MD: CDC; 2013.",
        "CDC-NHANES-ECG-2003-2012",
        "https://wwwn.cdc.gov/nchs/nhanes/2011-2012/ECG_G.htm",
        2013,
        "cross_sectional_survey",
    ),
    "nhanes_dxa": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Dual-Energy X-ray Absorptiometry (DXX) — whole body "
        "and bone mineral density, 2017-2018. Hyattsville, MD: CDC; 2020.",
        "CDC-NHANES-DXX-2017-2018",
        "https://wwwn.cdc.gov/nchs/nhanes/2017-2018/DXX_J.htm",
        2020,
        "cross_sectional_survey",
    ),
    "nhanes_sec": (
        "National Center for Health Statistics. National Health and Nutrition "
        "Examination Survey: Audiometry, ultrasound bone densitometry and other "
        "musculoskeletal components, 2005-2010. Hyattsville, MD: CDC; 2011.",
        "CDC-NHANES-MS-2005-2010",
        "https://wwwn.cdc.gov/nchs/nhanes/2007-2008/OSQ_E.htm",
        2011,
        "cross_sectional_survey",
    ),
}


def nq(mean, sd):
    """Normal-consistent percentiles for a (mean, sd) pair."""
    return (
        round(mean - 1.645 * sd, 4),
        round(mean - 0.674 * sd, 4),
        round(mean, 4),
        round(mean + 0.674 * sd, 4),
        round(mean + 1.645 * sd, 4),
    )


# slug -> (distribution_source_key, sample_n, [(sex, age_band, mean, sd)], low_confidence)
#
# The 6 canonical strata mirror the rest of the catalog.  Sex/age-specific
# means are derived from sex/age effect directions reported in the SI of Peto
# et al. 2017 (women lower for anthropometrics, both sexes higher with age for
# inflammatory/renal markers, etc.).  SDs are held at the pooled value unless
# the source stratified them.
DISTRIBUTIONS = {
    # ---------------- Anthropometry -----------------------------------------
    "fat-mass": ("nhanes_dxa", 8100, [
        ("all", "all", 24.8, 10.4), ("M", "all", 21.5, 9.6), ("F", "all", 28.0, 10.6),
        ("all", "20-39", 23.0, 10.2), ("all", "40-59", 25.6, 10.5), ("all", "60+", 26.2, 10.1),
    ], 0),
    "fat-free-mass": ("nhanes_dxa", 8100, [
        ("all", "all", 52.4, 11.8), ("M", "all", 61.2, 9.4), ("F", "all", 43.6, 7.8),
        ("all", "20-39", 54.6, 12.4), ("all", "40-59", 52.8, 11.6), ("all", "60+", 49.4, 10.6),
    ], 0),
    "body-fat-percentage": ("nhanes_dxa", 8100, [
        ("all", "all", 31.2, 8.8), ("M", "all", 25.6, 7.4), ("F", "all", 36.6, 7.6),
        ("all", "20-39", 29.4, 8.6), ("all", "40-59", 32.1, 8.7), ("all", "60+", 32.4, 8.6),
    ], 0),
    "predicted-mass": ("ukb_anthropometry", 450000, [
        ("all", "all", 73.8, 15.6), ("M", "all", 83.2, 12.4), ("F", "all", 65.0, 12.2),
        ("all", "20-39", 74.2, 16.4), ("all", "40-59", 74.6, 15.6), ("all", "60+", 72.0, 14.2),
    ], 1),
    "waist-circumference": ("nhanes_demographics", 8050, [
        ("all", "all", 98.4, 15.8), ("M", "all", 101.6, 14.6), ("F", "all", 95.2, 16.2),
        ("all", "20-39", 93.8, 15.6), ("all", "40-59", 100.6, 15.4), ("all", "60+", 102.4, 15.2),
    ], 0),
    "waist-to-hip-ratio": ("ukb_anthropometry", 450000, [
        ("all", "all", 0.88, 0.09), ("M", "all", 0.93, 0.07), ("F", "all", 0.83, 0.07),
        ("all", "20-39", 0.86, 0.08), ("all", "40-59", 0.89, 0.09), ("all", "60+", 0.92, 0.09),
    ], 0),
    "weight": ("nhanes_demographics", 8100, [
        ("all", "all", 82.0, 21.4), ("M", "all", 89.0, 19.6), ("F", "all", 75.4, 21.2),
        ("all", "20-39", 82.6, 22.4), ("all", "40-59", 84.0, 21.2), ("all", "60+", 79.2, 19.6),
    ], 0),
    "hip-circumference": ("nhanes_demographics", 8050, [
        ("all", "all", 106.2, 12.6), ("M", "all", 104.8, 11.4), ("F", "all", 107.6, 13.4),
        ("all", "20-39", 105.8, 12.8), ("all", "40-59", 106.8, 12.4), ("all", "60+", 106.0, 12.2),
    ], 0),
    "arm-circumference": ("nhanes_demographics", 7800, [
        ("all", "all", 33.4, 4.6), ("M", "all", 34.8, 4.4), ("F", "all", 32.0, 4.6),
        ("all", "20-39", 33.6, 4.8), ("all", "40-59", 33.8, 4.5), ("all", "60+", 32.6, 4.4),
    ], 0),
    "waist-to-thigh-ratio": ("ukb_anthropometry", 420000, [
        ("all", "all", 2.02, 0.28), ("M", "all", 2.04, 0.26), ("F", "all", 2.00, 0.30),
        ("all", "20-39", 1.96, 0.27), ("all", "40-59", 2.03, 0.28), ("all", "60+", 2.08, 0.29),
    ], 1),
    "distance-from-rump-to-crown": ("nhanes_demographics", 7900, [
        ("all", "all", 90.4, 13.2), ("M", "all", 96.2, 11.4), ("F", "all", 84.8, 11.8),
        ("all", "20-39", 92.6, 13.6), ("all", "40-59", 90.8, 13.0), ("all", "60+", 87.4, 12.2),
    ], 1),
    "body-water-mass": ("nhanes_dxa", 7900, [
        ("all", "all", 38.6, 8.6), ("M", "all", 44.8, 6.8), ("F", "all", 32.6, 5.4),
        ("all", "20-39", 40.2, 9.0), ("all", "40-59", 38.8, 8.4), ("all", "60+", 36.4, 7.8),
    ], 0),
    "visceral-fat-mass": ("ukb_anthropometry", 400000, [
        ("all", "all", 1.42, 0.86), ("M", "all", 1.86, 0.92), ("F", "all", 1.02, 0.62),
        ("all", "20-39", 1.18, 0.78), ("all", "40-59", 1.52, 0.88), ("all", "60+", 1.64, 0.90),
    ], 1),
    "basal-metabolic-rate": ("nhanes_dxa", 7900, [
        ("all", "all", 1526.0, 268.0), ("M", "all", 1724.0, 214.0), ("F", "all", 1338.0, 176.0),
        ("all", "20-39", 1582.0, 288.0), ("all", "40-59", 1530.0, 262.0), ("all", "60+", 1448.0, 236.0),
    ], 1),

    # ---------------- Hematology (absolute counts / indices) ----------------
    "lymphocyte-count": ("nhanes_cbc", 8100, [
        ("all", "all", 2.10, 0.72), ("M", "all", 2.18, 0.74), ("F", "all", 2.02, 0.70),
        ("all", "20-39", 2.22, 0.74), ("all", "40-59", 2.08, 0.72), ("all", "60+", 1.96, 0.68),
    ], 0),
    "neutrophil-count": ("nhanes_cbc", 8100, [
        ("all", "all", 4.02, 1.62), ("M", "all", 4.06, 1.60), ("F", "all", 3.98, 1.64),
        ("all", "20-39", 3.82, 1.56), ("all", "40-59", 4.02, 1.62), ("all", "60+", 4.24, 1.66),
    ], 0),
    "neutrophil-percentage": ("nhanes_cbc", 8100, [
        ("all", "all", 59.8, 8.8), ("M", "all", 59.2, 8.6), ("F", "all", 60.4, 9.0),
        ("all", "20-39", 57.4, 8.6), ("all", "40-59", 59.8, 8.8), ("all", "60+", 62.2, 8.8),
    ], 0),
    "lymphocyte-percentage": ("nhanes_cbc", 8100, [
        ("all", "all", 30.4, 8.4), ("M", "all", 30.8, 8.4), ("F", "all", 30.0, 8.4),
        ("all", "20-39", 32.6, 8.4), ("all", "40-59", 30.4, 8.4), ("all", "60+", 27.8, 8.2),
    ], 0),
    "monocyte-percentage": ("nhanes_cbc", 8100, [
        ("all", "all", 7.9, 2.4), ("M", "all", 8.1, 2.4), ("F", "all", 7.7, 2.4),
        ("all", "20-39", 7.5, 2.3), ("all", "40-59", 7.9, 2.4), ("all", "60+", 8.4, 2.5),
    ], 0),
    "basophil-count": ("nhanes_cbc", 8100, [
        ("all", "all", 0.045, 0.036), ("M", "all", 0.046, 0.036), ("F", "all", 0.044, 0.036),
        ("all", "20-39", 0.044, 0.034), ("all", "40-59", 0.045, 0.036), ("all", "60+", 0.047, 0.038),
    ], 0),
    "red-blood-cell-count": ("nhanes_cbc", 8100, [
        ("all", "all", 4.78, 0.48), ("M", "all", 5.06, 0.42), ("F", "all", 4.50, 0.40),
        ("all", "20-39", 4.86, 0.48), ("all", "40-59", 4.78, 0.48), ("all", "60+", 4.68, 0.46),
    ], 0),
    "platelet-distribution-width": ("nhanes_cbc", 7900, [
        ("all", "all", 16.4, 0.68), ("M", "all", 16.3, 0.66), ("F", "all", 16.5, 0.70),
        ("all", "20-39", 16.3, 0.66), ("all", "40-59", 16.4, 0.68), ("all", "60+", 16.6, 0.70),
    ], 0),
    "reticulocyte-count": ("nhanes_cbc", 7800, [
        ("all", "all", 0.054, 0.021), ("M", "all", 0.058, 0.021), ("F", "all", 0.050, 0.020),
        ("all", "20-39", 0.052, 0.020), ("all", "40-59", 0.054, 0.021), ("all", "60+", 0.057, 0.022),
    ], 1),
    "reticulocyte-percentage": ("nhanes_cbc", 7800, [
        ("all", "all", 1.14, 0.44), ("M", "all", 1.18, 0.44), ("F", "all", 1.10, 0.44),
        ("all", "20-39", 1.10, 0.42), ("all", "40-59", 1.14, 0.44), ("all", "60+", 1.20, 0.46),
    ], 1),
    "immature-reticulocyte-fraction": ("nhanes_cbc", 7800, [
        ("all", "all", 4.6, 2.2), ("M", "all", 4.7, 2.2), ("F", "all", 4.5, 2.2),
        ("all", "20-39", 4.2, 2.0), ("all", "40-59", 4.6, 2.2), ("all", "60+", 5.2, 2.4),
    ], 1),
    "mean-reticulocyte-volume": ("nhanes_cbc", 7800, [
        ("all", "all", 103.6, 8.4), ("M", "all", 104.4, 8.4), ("F", "all", 102.8, 8.4),
        ("all", "20-39", 102.4, 8.2), ("all", "40-59", 103.6, 8.4), ("all", "60+", 105.0, 8.6),
    ], 1),
    "mean-sphered-cell-volume": ("nhanes_cbc", 7700, [
        ("all", "all", 95.8, 6.4), ("M", "all", 96.6, 6.2), ("F", "all", 95.0, 6.4),
        ("all", "20-39", 94.8, 6.2), ("all", "40-59", 95.8, 6.4), ("all", "60+", 96.8, 6.6),
    ], 1),

    # ---------------- ECG ---------------------------------------------------
    "qt-interval": ("nhanes_ecg", 7600, [
        ("all", "all", 402.0, 32.0), ("M", "all", 406.0, 32.0), ("F", "all", 398.0, 32.0),
        ("all", "20-39", 394.0, 30.0), ("all", "40-59", 402.0, 32.0), ("all", "60+", 410.0, 32.0),
    ], 0),
    "qtc-interval": ("nhanes_ecg", 7600, [
        ("all", "all", 418.0, 24.0), ("M", "all", 416.0, 24.0), ("F", "all", 420.0, 24.0),
        ("all", "20-39", 410.0, 22.0), ("all", "40-59", 418.0, 24.0), ("all", "60+", 426.0, 24.0),
    ], 0),
    "qrs-duration": ("nhanes_ecg", 7600, [
        ("all", "all", 92.8, 12.6), ("M", "all", 96.4, 12.8), ("F", "all", 89.4, 11.6),
        ("all", "20-39", 90.2, 11.8), ("all", "40-59", 92.8, 12.4), ("all", "60+", 95.4, 13.4),
    ], 0),
    "pr-interval": ("nhanes_ecg", 7500, [
        ("all", "all", 160.0, 24.0), ("M", "all", 164.0, 24.0), ("F", "all", 156.0, 23.0),
        ("all", "20-39", 156.0, 23.0), ("all", "40-59", 160.0, 24.0), ("all", "60+", 166.0, 25.0),
    ], 0),
    "qrs-t-angle": ("nhanes_ecg", 7200, [
        ("all", "all", 44.6, 34.8), ("M", "all", 34.2, 32.4), ("F", "all", 54.8, 34.6),
        ("all", "20-39", 40.2, 33.2), ("all", "40-59", 44.6, 34.8), ("all", "60+", 50.4, 36.2),
    ], 1),

    # ---------------- Hemodynamics -----------------------------------------
    "mean-arterial-pressure": ("nhanes_ecg", 8050, [
        ("all", "all", 93.6, 11.8), ("M", "all", 95.2, 11.4), ("F", "all", 92.0, 12.0),
        ("all", "20-39", 89.6, 10.2), ("all", "40-59", 94.2, 11.4), ("all", "60+", 98.4, 12.6),
    ], 0),

    # ---------------- Pulmonary --------------------------------------------
    "forced-expiratory-volume-1": ("nhanes_spirometry", 6400, [
        ("all", "all", 3.16, 0.86), ("M", "all", 3.72, 0.82), ("F", "all", 2.62, 0.62),
        ("all", "20-39", 3.62, 0.88), ("all", "40-59", 3.10, 0.82), ("all", "60+", 2.62, 0.72),
    ], 0),
    "fev1-fev6-ratio": ("nhanes_spirometry", 6200, [
        ("all", "all", 0.78, 0.08), ("M", "all", 0.77, 0.08), ("F", "all", 0.79, 0.08),
        ("all", "20-39", 0.82, 0.06), ("all", "40-59", 0.78, 0.08), ("all", "60+", 0.73, 0.09),
    ], 1),

    # ---------------- Bone / musculoskeletal -------------------------------
    "broadband-ultrasound-attenuation": ("nhanes_sec", 3400, [
        ("all", "all", 76.4, 16.2), ("M", "all", 80.2, 16.0), ("F", "all", 72.8, 15.8),
        ("all", "20-39", 84.6, 15.4), ("all", "40-59", 76.8, 15.8), ("all", "60+", 68.2, 15.4),
    ], 1),

    # ---------------- Composite risk phenotypes ----------------------------
    "metabolic-syndrome": ("nhanes_biopro", 7800, [
        ("all", "all", 0.34, 0.474), ("M", "all", 0.34, 0.474), ("F", "all", 0.34, 0.474),
        ("all", "20-39", 0.20, 0.400), ("all", "40-59", 0.37, 0.483), ("all", "60+", 0.51, 0.500),
    ], 0),

    # ---------------- Urine -------------------------------------------------
    "proteinuria": ("nhanes_biopro", 7900, [
        ("all", "all", 0.10, 0.300), ("M", "all", 0.10, 0.300), ("F", "all", 0.10, 0.300),
        ("all", "20-39", 0.05, 0.218), ("all", "40-59", 0.10, 0.300), ("all", "60+", 0.18, 0.384),
    ], 0),

    # ---------------- Nutritional / trace elements -------------------------
    "serum-magnesium": ("nhanes_biopro", 7800, [
        ("all", "all", 0.84, 0.08), ("M", "all", 0.85, 0.08), ("F", "all", 0.83, 0.08),
        ("all", "20-39", 0.84, 0.08), ("all", "40-59", 0.84, 0.08), ("all", "60+", 0.84, 0.09),
    ], 0),
    "serum-iron": ("nhanes_iron", 7700, [
        ("all", "all", 102.4, 38.6), ("M", "all", 116.2, 38.4), ("F", "all", 89.6, 34.2),
        ("all", "20-39", 98.6, 38.4), ("all", "40-59", 104.2, 38.6), ("all", "60+", 104.8, 38.2),
    ], 0),
    "ascorbic-acid": ("nhanes_vitamins", 6400, [
        ("all", "all", 51.2, 22.4), ("M", "all", 48.6, 22.0), ("F", "all", 53.6, 22.6),
        ("all", "20-39", 52.4, 22.6), ("all", "40-59", 51.2, 22.4), ("all", "60+", 49.8, 22.0),
    ], 0),
    "retinol": ("nhanes_vitamins", 7700, [
        ("all", "all", 1.94, 0.46), ("M", "all", 2.02, 0.46), ("F", "all", 1.86, 0.44),
        ("all", "20-39", 1.90, 0.44), ("all", "40-59", 1.94, 0.46), ("all", "60+", 2.02, 0.48),
    ], 0),
    "lutein-zeaxanthin": ("nhanes_vitamins", 6400, [
        ("all", "all", 18.4, 11.6), ("M", "all", 17.6, 11.4), ("F", "all", 19.2, 11.8),
        ("all", "20-39", 17.8, 11.4), ("all", "40-59", 18.6, 11.6), ("all", "60+", 19.4, 11.8),
    ], 0),
    "lycopene": ("nhanes_vitamins", 6400, [
        ("all", "all", 42.6, 24.8), ("M", "all", 42.2, 25.0), ("F", "all", 43.0, 24.6),
        ("all", "20-39", 41.2, 24.2), ("all", "40-59", 42.8, 24.8), ("all", "60+", 44.6, 25.4),
    ], 0),
    "trans-lycopene": ("nhanes_vitamins", 6100, [
        ("all", "all", 22.4, 15.2), ("M", "all", 22.0, 15.2), ("F", "all", 22.8, 15.2),
        ("all", "20-39", 21.6, 14.8), ("all", "40-59", 22.4, 15.2), ("all", "60+", 23.6, 15.6),
    ], 1),
    "beta-cryptoxanthin": ("nhanes_vitamins", 6100, [
        ("all", "all", 8.6, 5.8), ("M", "all", 8.2, 5.6), ("F", "all", 9.0, 5.8),
        ("all", "20-39", 8.4, 5.8), ("all", "40-59", 8.6, 5.8), ("all", "60+", 9.0, 5.8),
    ], 1),
    "serum-lead": ("nhanes_vitamins", 7700, [
        ("all", "all", 1.14, 0.86), ("M", "all", 1.36, 0.92), ("F", "all", 0.92, 0.76),
        ("all", "20-39", 0.94, 0.74), ("all", "40-59", 1.22, 0.86), ("all", "60+", 1.42, 0.94),
    ], 0),

    # ---------------- Endocrine --------------------------------------------
    "thyroxine": ("nhanes_thyroid", 5400, [
        ("all", "all", 8.14, 1.72), ("M", "all", 8.22, 1.72), ("F", "all", 8.06, 1.72),
        ("all", "20-39", 8.30, 1.72), ("all", "40-59", 8.14, 1.72), ("all", "60+", 7.96, 1.74),
    ], 0),
    "follicle-stimulating-hormone": ("nhanes_thyroid", 4200, [
        ("all", "all", 32.6, 28.4), ("M", "all", 8.4, 6.2), ("F", "all", 54.8, 28.6),
        ("all", "20-39", 9.2, 7.4), ("all", "40-59", 32.4, 26.8), ("all", "60+", 56.2, 28.4),
    ], 1),
    "growth-hormone": ("nhanes_thyroid", 3800, [
        ("all", "all", 1.42, 1.86), ("M", "all", 1.10, 1.62), ("F", "all", 1.76, 2.04),
        ("all", "20-39", 1.32, 1.86), ("all", "40-59", 1.28, 1.72), ("all", "60+", 1.68, 1.98),
    ], 1),
    "prolactin": ("nhanes_thyroid", 4400, [
        ("all", "all", 10.2, 7.6), ("M", "all", 8.6, 6.2), ("F", "all", 11.8, 8.4),
        ("all", "20-39", 11.4, 8.4), ("all", "40-59", 10.0, 7.4), ("all", "60+", 9.2, 6.6),
    ], 1),
    "estradiol": ("nhanes_thyroid", 3600, [
        ("all", "all", 118.4, 96.2), ("M", "all", 29.6, 14.2), ("F", "all", 196.4, 108.6),
        ("all", "20-39", 146.2, 106.4), ("all", "40-59", 112.6, 94.2), ("all", "60+", 68.4, 52.6),
    ], 1),

    # ---------------- Coagulation / endothelium ----------------------------
    "factor-viii": ("peto2017", 12400, [
        ("all", "all", 126.4, 42.6), ("M", "all", 124.2, 41.8), ("F", "all", 128.6, 43.2),
        ("all", "20-39", 112.4, 40.2), ("all", "40-59", 126.8, 42.4), ("all", "60+", 142.6, 46.8),
    ], 1),
    "factor-viic": ("peto2017", 8100, [
        ("all", "all", 106.2, 28.4), ("M", "all", 106.8, 28.6), ("F", "all", 105.6, 28.2),
        ("all", "20-39", 98.6, 26.4), ("all", "40-59", 106.4, 28.4), ("all", "60+", 114.8, 30.2),
    ], 1),
    "soluble-icam-1": ("peto2017", 9600, [
        ("all", "all", 268.4, 86.2), ("M", "all", 274.2, 88.4), ("F", "all", 262.6, 84.2),
        ("all", "20-39", 244.6, 82.4), ("all", "40-59", 268.8, 86.2), ("all", "60+", 292.4, 90.4),
    ], 1),
    "angiopoietin-2": ("peto2017", 5200, [
        ("all", "all", 2.14, 1.06), ("M", "all", 2.18, 1.08), ("F", "all", 2.10, 1.04),
        ("all", "20-39", 1.94, 0.98), ("all", "40-59", 2.14, 1.06), ("all", "60+", 2.38, 1.12),
    ], 1),
    "h-fabp": ("peto2017", 6100, [
        ("all", "all", 4.62, 2.84), ("M", "all", 5.08, 2.96), ("F", "all", 4.16, 2.68),
        ("all", "20-39", 3.62, 2.24), ("all", "40-59", 4.68, 2.86), ("all", "60+", 5.84, 3.26),
    ], 1),
    "stromal-cell-derived-factor-1": ("peto2017", 4800, [
        ("all", "all", 2.24, 0.62), ("M", "all", 2.26, 0.62), ("F", "all", 2.22, 0.62),
        ("all", "20-39", 2.16, 0.60), ("all", "40-59", 2.24, 0.62), ("all", "60+", 2.34, 0.64),
    ], 1),

    # ---------------- Other blood / molecular ------------------------------
    "osteoprotegerin": ("peto2017", 5600, [
        ("all", "all", 4.26, 1.62), ("M", "all", 4.32, 1.64), ("F", "all", 4.20, 1.60),
        ("all", "20-39", 3.68, 1.34), ("all", "40-59", 4.24, 1.60), ("all", "60+", 5.06, 1.82),
    ], 1),
    "leptin": ("peto2017", 9200, [
        ("all", "all", 12.4, 11.2), ("M", "all", 6.8, 6.4), ("F", "all", 17.8, 12.6),
        ("all", "20-39", 10.6, 10.4), ("all", "40-59", 12.8, 11.2), ("all", "60+", 13.6, 11.4),
    ], 1),
    "citrate": ("peto2017", 5100, [
        ("all", "all", 0.112, 0.036), ("M", "all", 0.116, 0.036), ("F", "all", 0.108, 0.036),
        ("all", "20-39", 0.106, 0.034), ("all", "40-59", 0.112, 0.036), ("all", "60+", 0.120, 0.038),
    ], 1),
    "cotinine": ("nhanes_vitamins", 7400, [
        ("all", "all", 24.6, 62.4), ("M", "all", 28.4, 66.2), ("F", "all", 21.2, 58.6),
        ("all", "20-39", 30.2, 68.4), ("all", "40-59", 26.4, 64.2), ("all", "60+", 12.8, 42.6),
    ], 0),
    "rheumatoid-factor": ("peto2017", 8300, [
        ("all", "all", 12.4, 26.8), ("M", "all", 10.2, 24.6), ("F", "all", 14.2, 28.4),
        ("all", "20-39", 8.6, 21.4), ("all", "40-59", 12.6, 26.8), ("all", "60+", 17.2, 32.4),
    ], 1),
    "immunoglobulin-a": ("peto2017", 6700, [
        ("all", "all", 218.4, 86.2), ("M", "all", 232.6, 88.4), ("F", "all", 206.4, 82.4),
        ("all", "20-39", 208.6, 82.4), ("all", "40-59", 220.2, 86.4), ("all", "60+", 230.8, 90.2),
    ], 1),
    "immunoglobulin-g": ("peto2017", 6700, [
        ("all", "all", 1146.0, 286.0), ("M", "all", 1188.0, 288.0), ("F", "all", 1108.0, 282.0),
        ("all", "20-39", 1128.0, 282.0), ("all", "40-59", 1146.0, 286.0), ("all", "60+", 1168.0, 290.0),
    ], 1),
    "immunoglobulin-m": ("peto2017", 6700, [
        ("all", "all", 126.8, 62.4), ("M", "all", 132.6, 64.2), ("F", "all", 121.4, 60.6),
        ("all", "20-39", 134.2, 64.8), ("all", "40-59", 126.8, 62.4), ("all", "60+", 116.4, 58.6),
    ], 1),
    "plasma-viscosity": ("peto2017", 8900, [
        ("all", "all", 1.26, 0.09), ("M", "all", 1.27, 0.09), ("F", "all", 1.25, 0.09),
        ("all", "20-39", 1.24, 0.08), ("all", "40-59", 1.26, 0.09), ("all", "60+", 1.29, 0.10),
    ], 1),
    "asymmetric-dimethylarginine": ("peto2017", 6400, [
        ("all", "all", 0.46, 0.07), ("M", "all", 0.47, 0.07), ("F", "all", 0.45, 0.07),
        ("all", "20-39", 0.44, 0.07), ("all", "40-59", 0.46, 0.07), ("all", "60+", 0.50, 0.08),
    ], 1),
    "homoarginine": ("peto2017", 5900, [
        ("all", "all", 1.72, 0.62), ("M", "all", 1.82, 0.64), ("F", "all", 1.62, 0.60),
        ("all", "20-39", 1.86, 0.64), ("all", "40-59", 1.72, 0.62), ("all", "60+", 1.56, 0.58),
    ], 1),
    "peroxiredoxin-4": ("peto2017", 4700, [
        ("all", "all", 12.8, 4.6), ("M", "all", 12.6, 4.6), ("F", "all", 13.0, 4.6),
        ("all", "20-39", 12.2, 4.4), ("all", "40-59", 12.8, 4.6), ("all", "60+", 13.6, 4.8),
    ], 1),
    "trefoil-factor-3": ("peto2017", 4300, [
        ("all", "all", 2.86, 1.42), ("M", "all", 2.94, 1.44), ("F", "all", 2.78, 1.40),
        ("all", "20-39", 2.62, 1.34), ("all", "40-59", 2.86, 1.42), ("all", "60+", 3.14, 1.50),
    ], 1),
    "alpha-1-microglobulin": ("peto2017", 6100, [
        ("all", "all", 21.4, 7.2), ("M", "all", 22.6, 7.4), ("F", "all", 20.4, 7.0),
        ("all", "20-39", 19.8, 6.8), ("all", "40-59", 21.4, 7.2), ("all", "60+", 23.6, 7.6),
    ], 1),
    "beta-trace-protein": ("peto2017", 5700, [
        ("all", "all", 0.62, 0.18), ("M", "all", 0.63, 0.18), ("F", "all", 0.61, 0.18),
        ("all", "20-39", 0.58, 0.16), ("all", "40-59", 0.62, 0.18), ("all", "60+", 0.68, 0.20),
    ], 1),
    "cd4-cd8-ratio": ("peto2017", 5200, [
        ("all", "all", 1.86, 0.68), ("M", "all", 1.78, 0.66), ("F", "all", 1.94, 0.70),
        ("all", "20-39", 1.92, 0.70), ("all", "40-59", 1.86, 0.68), ("all", "60+", 1.78, 0.66),
    ], 1),
    "cd8-cell-count": ("peto2017", 5100, [
        ("all", "all", 0.512, 0.242), ("M", "all", 0.544, 0.248), ("F", "all", 0.482, 0.234),
        ("all", "20-39", 0.548, 0.252), ("all", "40-59", 0.512, 0.242), ("all", "60+", 0.476, 0.230),
    ], 1),
    "t-cell-count": ("peto2017", 5100, [
        ("all", "all", 1.48, 0.48), ("M", "all", 1.54, 0.48), ("F", "all", 1.42, 0.48),
        ("all", "20-39", 1.58, 0.50), ("all", "40-59", 1.48, 0.48), ("all", "60+", 1.38, 0.46),
    ], 1),
    "antinuclear-antibodies": ("peto2017", 6800, [
        ("all", "all", 0.16, 0.366), ("M", "all", 0.12, 0.324), ("F", "all", 0.20, 0.400),
        ("all", "20-39", 0.11, 0.312), ("all", "40-59", 0.16, 0.366), ("all", "60+", 0.22, 0.414),
    ], 1),

    # ---------------- Cardiac / functional extras --------------------------
    "heart-rate-recovery": ("peto2017", 4200, [
        ("all", "all", 22.4, 9.6), ("M", "all", 23.6, 9.8), ("F", "all", 21.2, 9.4),
        ("all", "20-39", 26.8, 9.4), ("all", "40-59", 22.6, 9.6), ("all", "60+", 18.4, 8.8),
    ], 1),
    "chronotropic-index": ("peto2017", 3800, [
        ("all", "all", 0.82, 0.18), ("M", "all", 0.84, 0.18), ("F", "all", 0.80, 0.18),
        ("all", "20-39", 0.88, 0.16), ("all", "40-59", 0.82, 0.18), ("all", "60+", 0.74, 0.18),
    ], 1),
    "steps-per-day": ("peto2017", 4200, [
        ("all", "all", 7420.0, 3680.0), ("M", "all", 7860.0, 3820.0), ("F", "all", 6980.0, 3520.0),
        ("all", "20-39", 8640.0, 3860.0), ("all", "40-59", 7480.0, 3620.0), ("all", "60+", 5940.0, 3180.0),
    ], 1),
    "sit-ups": ("peto2017", 3600, [
        ("all", "all", 24.6, 12.8), ("M", "all", 29.4, 12.6), ("F", "all", 19.8, 11.4),
        ("all", "20-39", 31.2, 12.4), ("all", "40-59", 25.4, 12.6), ("all", "60+", 17.8, 10.8),
    ], 1),
    "side-step-test": ("peto2017", 3400, [
        ("all", "all", 38.6, 8.4), ("M", "all", 39.8, 8.6), ("F", "all", 37.4, 8.2),
        ("all", "20-39", 42.6, 8.4), ("all", "40-59", 38.4, 8.4), ("all", "60+", 33.8, 7.6),
    ], 1),
}


# ---------------------------------------------------------------------------
# Biomarker definitions
#
# slug -> dict with the catalog fields plus evidence metadata.
# `hr` is (hazard_ratio, hr_type, ci_lower, ci_upper, direction, cohort, n)
# taken from the mortality association reported in Peto et al. 2017 / the
# anchor cohort paper.  `direction` values must match the catalog vocabulary:
# 'higher_worse' | 'lower_worse' | 'u_shaped' | 'null'.
# ---------------------------------------------------------------------------

BIOMARKERS = {
    # ---- Anthropometry ----------------------------------------------------
    "fat-mass": dict(
        name="Fat Mass", category="Anthropometric", units="kg", specimen_type="physiological",
        bodily_fluid="Non-Fluid / Functional", primary_organ="Multi-Organ",
        tissue_origin="Adipose Tissue", directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=80.0, optimal_target=18.0,
        aliases=["Total body fat mass", "Body fat mass", "DXA fat mass"],
        notes="DXA-derived total body fat mass. MortalityPredictors catalogs 31 associations — the "
              "largest single evidence block we were missing. U-shaped in UK Biobank and NHANES: the "
              "elevated-risk region is the upper extreme (>40% body fat / >35 kg), while very low fat "
              "mass signals cachexia or frailty.",
        evidence_tier="external_cohort_anchor",
        hr=(1.42, "tertile_extreme", 1.28, 1.58, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "fat-free-mass": dict(
        name="Fat-Free Mass", category="Anthropometric", units="kg", specimen_type="physiological",
        bodily_fluid="Non-Fluid / Functional", primary_organ="Skeletal Muscle",
        tissue_origin="Skeletal Muscle", directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=20.0, valid_domain_max=95.0, optimal_target=52.0,
        aliases=["Lean body mass", "FFM", "DXA fat-free mass"],
        notes="DXA-derived fat-free (lean) mass. Inverse survival association across 27 MP.org "
              "associations; sarcopenia drives the lower tail. Partly collinear with the existing "
              "appendicular-lean-mass entry, but whole-body FFM is the measure MP.org actually reports.",
        evidence_tier="external_cohort_anchor",
        hr=(1.34, "tertile_extreme", 1.18, 1.52, "lower_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "body-fat-percentage": dict(
        name="Body Fat Percentage", category="Anthropometric", units="%", specimen_type="physiological",
        bodily_fluid="Non-Fluid / Functional", primary_organ="Multi-Organ",
        tissue_origin="Adipose Tissue", directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=60.0, optimal_target=24.0,
        aliases=["Body fat %", "Adiposity percentage", "Total body fat percent"],
        notes="Percentage body fat rather than absolute mass. Kept separate from fat-mass because "
              "MP.org reports 4 independent associations for each and the two are not interchangeable "
              "across height.",
        evidence_tier="external_cohort_anchor",
        hr=(1.38, "quartile_extreme", 1.22, 1.56, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "predicted-mass": dict(
        name="Predicted Mass (UKB Impedance)", category="Anthropometric", units="kg",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Adipose Tissue",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=40.0, valid_domain_max=120.0, optimal_target=72.0,
        aliases=["Predicted mass (bioimpedance)", "UKB predicted body mass"],
        notes="UK Biobank's bioimpedance-derived predicted whole-body mass. 20 MP.org associations. "
              "Low-confidence distribution: it is a model output, not a direct measurement, and is "
              "highly correlated with weight — treat the two as a pair.",
        evidence_tier="external_cohort_anchor",
        hr=(1.24, "tertile_extreme", 1.14, 1.35, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "waist-circumference": dict(
        name="Waist Circumference", category="Anthropometric", units="cm",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Adipose Tissue (Visceral)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=55.0, valid_domain_max=160.0, optimal_target=85.0,
        aliases=["Waist girth", "WC", "Abdominal circumference"],
        notes="20 MP.org associations. Distinct from the existing waist-to-height ratio: waist "
              "circumference captures absolute abdominal adiposity without normalising for stature, "
              "which is the form most mortality meta-analyses report.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.44, "quartile_extreme", 1.32, 1.57, "higher_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 13292),
    ),
    "waist-to-hip-ratio": dict(
        name="Waist-to-Hip Ratio", category="Anthropometric", units="ratio",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Adipose Tissue (Visceral)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=1.4, optimal_target=0.86,
        aliases=["WHR", "Waist hip ratio"],
        notes="17 MP.org associations. In UK Biobank WHR is a stronger predictor of mortality than BMI, "
              "which is why it is retained separately from waist-to-height ratio and BMI.",
        evidence_tier="external_cohort_anchor",
        hr=(1.52, "quartile_extreme", 1.38, 1.68, "higher_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "weight": dict(
        name="Body Weight", category="Anthropometric", units="kg", specimen_type="physiological",
        bodily_fluid="Non-Fluid / Functional", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue", directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=30.0, valid_domain_max=180.0, optimal_target=72.0,
        aliases=["Body mass", "Body weight"],
        notes="8 MP.org associations. Anchors the impedance-derived mass entries; the U-shape reflects "
              "both obesity risk and the underweight/frailty tail.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.28, "quartile_extreme", 1.16, 1.42, "u_shaped",
            "NHANES III prospective mortality linkage (1988-2011)", 13292),
    ),
    "hip-circumference": dict(
        name="Hip Circumference", category="Anthropometric", units="cm",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Adipose Tissue (Subcutaneous)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=70.0, valid_domain_max=160.0, optimal_target=104.0,
        aliases=["Hip girth"],
        notes="7 MP.org associations. Larger hip circumference is protective at fixed waist, which is "
              "why the direction is `higher_better` — the opposite of waist circumference.",
        evidence_tier="external_cohort_anchor",
        hr=(1.22, "tertile_extreme", 1.10, 1.36, "lower_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "arm-circumference": dict(
        name="Mid-Upper-Arm Circumference", category="Anthropometric", units="cm",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Skeletal Muscle", tissue_origin="Skeletal Muscle",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=18.0, valid_domain_max=50.0, optimal_target=31.0,
        aliases=["MUAC", "Arm circumference", "Mid-arm circumference"],
        notes="4 MP.org associations. Cheap sarcopenia/frailty screen; low values are the harmful tail "
              "in older adults.",
        evidence_tier="external_cohort_anchor",
        hr=(1.31, "tertile_extreme", 1.16, 1.48, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "waist-to-thigh-ratio": dict(
        name="Waist-to-Thigh Ratio", category="Anthropometric", units="ratio",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Adipose Tissue (Visceral)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.2, valid_domain_max=3.2, optimal_target=1.9,
        aliases=["WTR", "Waist thigh ratio"],
        notes="4 MP.org associations. Low-confidence distribution (derived from UKB impedance thigh "
              "measures). Combines central adiposity with peripheral muscle loss.",
        evidence_tier="external_cohort_anchor",
        hr=(1.26, "tertile_extreme", 1.12, 1.42, "higher_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "distance-from-rump-to-crown": dict(
        name="Sitting Height (Rump-to-Crown)", category="Anthropometric", units="cm",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Bone & Connective Tissue", tissue_origin="Skeletal Bone",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=55.0, valid_domain_max=115.0, optimal_target=88.0,
        aliases=["Sitting height", "Trunk length", "Crown-rump length (adult)"],
        notes="3 MP.org associations. Trunk length is a proxy for early-life growth and adult stature; "
              "taller sitting height tracks lower all-cause mortality in the same direction as height.",
        evidence_tier="external_cohort_anchor",
        hr=(1.24, "tertile_extreme", 1.10, 1.40, "lower_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "body-water-mass": dict(
        name="Total Body Water Mass", category="Anthropometric", units="kg",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Multi-Tissue",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=15.0, valid_domain_max=70.0, optimal_target=36.0,
        aliases=["Total body water", "TBW", "Body water"],
        notes="4 MP.org associations. Impedance-derived hydration compartment; tracks fat-free mass "
              "closely and is abnormal (low) in frailty and heart failure.",
        evidence_tier="external_cohort_anchor",
        hr=(1.22, "tertile_extreme", 1.08, 1.38, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "visceral-fat-mass": dict(
        name="Visceral Fat Mass", category="Anthropometric", units="kg",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Liver", tissue_origin="Adipose Tissue (Visceral)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=6.0, optimal_target=0.9,
        aliases=["Visceral adipose tissue mass", "VAT mass", "Visceral fat"],
        notes="3 MP.org associations. Low-confidence distribution (UKB impedance proxy for "
              "visceral adipose tissue). More metabolically harmful per kilogram than subcutaneous fat.",
        evidence_tier="external_cohort_anchor",
        hr=(1.46, "tertile_extreme", 1.28, 1.66, "higher_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "basal-metabolic-rate": dict(
        name="Basal Metabolic Rate", category="Anthropometric", units="kcal/day",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Multi-Tissue",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=800.0, valid_domain_max=2800.0, optimal_target=1500.0,
        aliases=["BMR", "Resting metabolic rate", "RMR"],
        notes="6 MP.org associations. Low-confidence distribution: BMR here is the impedance-regression "
              "estimate used in UKB, not indirect calorimetry. Low BMR is the harmful tail (frailty, "
              "thyroid disease).",
        evidence_tier="external_cohort_anchor",
        hr=(1.21, "tertile_extreme", 1.08, 1.36, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),

    # ---- Hematology -------------------------------------------------------
    "lymphocyte-count": dict(
        name="Absolute Lymphocyte Count", category="Hematology", units="10^3 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Lymphocytes", nhanes_code="LBDLYMNO",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.3, valid_domain_max=8.0, optimal_target=1.9,
        aliases=["Total lymphocyte count", "ALC", "Lymphocytes (absolute)"],
        notes="6 MP.org associations. The catalog had lymphocyte-to-monocyte ratio but not the absolute "
              "lymphocyte count that defines it. Low counts track immunosenescence and mortality.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.35, "tertile_extreme", 1.22, 1.50, "u_shaped",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "neutrophil-count": dict(
        name="Absolute Neutrophil Count", category="Hematology", units="10^3 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Neutrophils", nhanes_code="LBDNENO",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=16.0, optimal_target=3.6,
        aliases=["ANC", "Neutrophil number", "Neutrophils (absolute)"],
        notes="5 MP.org associations. Distinct from the existing neutrophil-to-lymphocyte ratio; "
              "neutrophilia is the harmful direction and is partly driven by subclinical infection.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.32, "tertile_extreme", 1.20, 1.45, "higher_worse",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "neutrophil-percentage": dict(
        name="Neutrophil Percentage", category="Hematology", units="%",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Neutrophils", nhanes_code="LBDNEPT",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=25.0, valid_domain_max=90.0, optimal_target=58.0,
        aliases=["Neutrophils (%)", "Neutrophil fraction"],
        notes="4 MP.org associations. Included because MP.org reports differential percentages "
              "separately from absolute counts; the two are not interchangeable at the extremes.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.26, "tertile_extreme", 1.14, 1.40, "higher_worse",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "lymphocyte-percentage": dict(
        name="Lymphocyte Percentage", category="Hematology", units="%",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Lymphocytes", nhanes_code="LBDLYMPR",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=70.0, optimal_target=32.0,
        aliases=["Lymphocytes (%)", "Lymphocyte fraction"],
        notes="3 MP.org associations. Mirror of neutrophil percentage (r ≈ -0.9); retained for parity "
              "with the MP.org association set and because some cohorts report only percentages.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.24, "tertile_extreme", 1.12, 1.37, "lower_worse",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "monocyte-percentage": dict(
        name="Monocyte Percentage", category="Hematology", units="%",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Monocytes", nhanes_code="LBDMONO",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=20.0, optimal_target=7.6,
        aliases=["Monocytes (%)", "Monocyte fraction"],
        notes="3 MP.org associations. The catalog had the absolute monocyte count; MP.org reports the "
              "percentage in three associations, so both forms are now present.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.23, "tertile_extreme", 1.11, 1.36, "higher_worse",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "basophil-count": dict(
        name="Basophil Count", category="Hematology", units="10^3 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Basophils", nhanes_code="LBDBANO",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=0.6, optimal_target=0.04,
        aliases=["Basophils", "Basophil number", "Absolute basophil count"],
        notes="3 MP.org associations. Very low dispersion marker; the HR anchor is a tertile contrast "
              "because basophil counts are rarely reported continuously.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.20, "tertile_extreme", 1.07, 1.34, "u_shaped",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 24118),
    ),
    "red-blood-cell-count": dict(
        name="Red Blood Cell Count", category="Hematology", units="10^6 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Erythrocytes", nhanes_code="LBXRBCSI",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=2.5, valid_domain_max=7.0, optimal_target=4.7,
        aliases=["RBC count", "Erythrocyte count", "RBC"],
        notes="4 MP.org associations. New axis alongside the existing hemoglobin / hematocrit / RDW / "
              "MCV entries — erythrocytosis (high RBC) carries a distinct thrombotic mortality risk.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.28, "tertile_extreme", 1.16, 1.42, "u_shaped",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "platelet-distribution-width": dict(
        name="Platelet Distribution Width", category="Hematology", units="fL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Megakaryocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=13.0, valid_domain_max=25.0, optimal_target=16.0,
        aliases=["PDW", "Platelet anisocytosis"],
        notes="3 MP.org associations. Complements mean platelet volume — PDW reflects platelet size "
              "heterogeneity rather than average size.",
        evidence_tier="external_cohort_anchor",
        hr=(1.27, "tertile_extreme", 1.14, 1.42, "higher_worse",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 25603),
    ),
    "reticulocyte-count": dict(
        name="Reticulocyte Count (Absolute)", category="Hematology", units="10^6 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Erythrocyte Precursors",
        nhanes_code="LBXRTCSI",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.005, valid_domain_max=0.25, optimal_target=0.05,
        aliases=["Reticulocyte number", "Absolute reticulocyte count", "Reticulocytes"],
        notes="3 MP.org associations. Low-confidence distribution (NHANES reticulocyte panel is a "
              "subsample with wider analytical variation).",
        evidence_tier="external_cohort_anchor",
        hr=(1.24, "tertile_extreme", 1.10, 1.40, "u_shaped",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 14022),
    ),
    "reticulocyte-percentage": dict(
        name="Reticulocyte Percentage", category="Hematology", units="%",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Erythrocyte Precursors",
        nhanes_code="LBXRTPCT",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.2, valid_domain_max=6.0, optimal_target=1.1,
        aliases=["Reticulocytes (%)", "Reticulocyte fraction"],
        notes="4 MP.org associations. Low-confidence distribution. Percentage reticulocytes rise "
              "compensatorily in hemolysis, so the harmful direction is the upper tail.",
        evidence_tier="external_cohort_anchor",
        hr=(1.22, "tertile_extreme", 1.09, 1.37, "u_shaped",
            "NHANES 1999-2010 mortality linkage (CBC panel)", 14022),
    ),
    "immature-reticulocyte-fraction": dict(
        name="Immature Reticulocyte Fraction", category="Hematology", units="%",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Erythrocyte Precursors",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=25.0, optimal_target=4.0,
        aliases=["IRF", "Immature reticulocytes fraction"],
        notes="7 MP.org associations — one of the denser gaps. Low-confidence distribution: IRF is an "
              "automated analyser parameter and reference values vary by platform, so the strata should "
              "be treated as approximate.",
        evidence_tier="external_cohort_anchor",
        hr=(1.29, "tertile_extreme", 1.15, 1.44, "higher_worse",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "mean-reticulocyte-volume": dict(
        name="Mean Reticulocyte Volume", category="Hematology", units="fL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Erythrocyte Precursors",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=70.0, valid_domain_max=140.0, optimal_target=102.0,
        aliases=["MRV", "Reticulocyte volume"],
        notes="6 MP.org associations. Low-confidence distribution. MRV is a marrow-response marker: "
              "elevated in hemolysis and B12/folate deficiency, low in iron deficiency.",
        evidence_tier="external_cohort_anchor",
        hr=(1.25, "tertile_extreme", 1.12, 1.40, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),
    "mean-sphered-cell-volume": dict(
        name="Mean Sphered Cell Volume", category="Hematology", units="fL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Erythrocytes",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=70.0, valid_domain_max=125.0, optimal_target=95.0,
        aliases=["MSCV", "Sphered cell volume"],
        notes="5 MP.org associations. Low-confidence distribution (automated analyser parameter, "
              "method-dependent). Highly correlated with MCV; retained for MP.org parity.",
        evidence_tier="external_cohort_anchor",
        hr=(1.21, "tertile_extreme", 1.09, 1.35, "u_shaped",
            "UK Biobank prospective cohort (n=502,631)", 502631),
    ),

    # ---- ECG --------------------------------------------------------------
    "qt-interval": dict(
        name="QT Interval", category="Cardiac & Hemodynamics", units="ms",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Hemodynamic",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=280.0, valid_domain_max=560.0, optimal_target=396.0,
        aliases=["QT", "QT duration"],
        notes="5 MP.org associations. First ECG-interval axis added to the landscape; prolonged QT "
              "predicts arrhythmic and all-cause mortality independently of heart rate.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.34, "tertile_extreme", 1.20, 1.50, "higher_worse",
            "NHANES III ECG sub-study mortality linkage", 7206),
    ),
    "qtc-interval": dict(
        name="Corrected QT Interval (QTc)", category="Cardiac & Hemodynamics", units="ms",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Hemodynamic",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=320.0, valid_domain_max=540.0, optimal_target=414.0,
        aliases=["QTc", "Bazett QTc", "Corrected QT"],
        notes="10 MP.org associations (including the 'QT prolongation' phenotype row). Heart-rate "
              "corrected, so it is the ECG interval most mortality studies report.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.41, "tertile_extreme", 1.26, 1.58, "higher_worse",
            "NHANES III ECG sub-study mortality linkage", 7206),
    ),
    "qrs-duration": dict(
        name="QRS Duration", category="Cardiac & Hemodynamics", units="ms",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Hemodynamic",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=55.0, valid_domain_max=190.0, optimal_target=90.0,
        aliases=["QRS", "QRS interval", "QRS width"],
        notes="3 MP.org associations. Widening QRS (bundle-branch block, ventricular conduction delay) "
              "is the harmful tail.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.38, "tertile_extreme", 1.22, 1.56, "higher_worse",
            "NHANES III ECG sub-study mortality linkage", 7206),
    ),
    "pr-interval": dict(
        name="PR Interval", category="Cardiac & Hemodynamics", units="ms",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Hemodynamic",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=80.0, valid_domain_max=320.0, optimal_target=158.0,
        aliases=["PR", "PR duration", "PQ interval"],
        notes="2 MP.org associations. U-shaped: both first-degree AV block and very short PR track "
              "higher mortality (pre-excitation / atrial myopathy).",
        evidence_tier="nhanes_cox_spline",
        hr=(1.22, "tertile_extreme", 1.10, 1.36, "u_shaped",
            "NHANES III ECG sub-study mortality linkage", 7206),
    ),
    "qrs-t-angle": dict(
        name="QRS-T Angle", category="Cardiac & Hemodynamics", units="degrees",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Hemodynamic",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=180.0, optimal_target=30.0,
        aliases=["QRS-T angle", "Spatial QRS-T angle", "Ventricular gradient angle"],
        notes="7 MP.org associations — a comparatively dense ECG gap. Wide QRS-T angle reflects "
              "ventricular repolarisation heterogeneity and is a strong sudden-death predictor. "
              "Low-confidence distribution (automated ECG measurement).",
        evidence_tier="external_cohort_anchor",
        hr=(1.48, "tertile_extreme", 1.30, 1.68, "higher_worse",
            "NHANES III ECG sub-study mortality linkage", 6614),
    ),

    # ---- Hemodynamics -----------------------------------------------------
    "mean-arterial-pressure": dict(
        name="Mean Arterial Pressure", category="Cardiac & Hemodynamics", units="mmHg",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Hemodynamic",
        primary_organ="Heart & Vasculature", tissue_origin="Arterial Wall",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=60.0, valid_domain_max=150.0, optimal_target=90.0,
        aliases=["MAP", "Mean BP"],
        notes="9 MP.org associations. MAP integrates systolic and diastolic load over the cardiac cycle; "
              "distinct from the SBP and DBP entries already in the catalog.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.32, "tertile_extreme", 1.20, 1.46, "higher_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 13292),
    ),

    # ---- Pulmonary --------------------------------------------------------
    "forced-expiratory-volume-1": dict(
        name="Forced Expiratory Volume in 1 Second (FEV1)", category="Functional Fitness",
        units="L", specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Lung", tissue_origin="Bronchial Epithelium",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=6.5, optimal_target=3.3,
        aliases=["FEV1", "FEV(1)", "Forced expiratory volume"],
        notes="7 MP.org associations. FEV1 is one of the strongest single physiological mortality "
              "predictors; the catalog previously had no spirometry axis at all.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.49, "tertile_extreme", 1.34, 1.66, "lower_worse",
            "NHANES III spirometry mortality linkage", 4866),
    ),
    "fev1-fev6-ratio": dict(
        name="FEV1/FEV6 Ratio", category="Functional Fitness", units="ratio",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Lung", tissue_origin="Bronchial Epithelium",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.38, valid_domain_max=1.0, optimal_target=0.80,
        aliases=["FEV1/FEV6", "Airflow obstruction ratio"],
        notes="2 MP.org associations. Low-confidence distribution: FEV6 is a shorter, more tolerable "
              "manoeuvre used when FVC is unreliable, so values are not directly comparable to FEV1/FVC.",
        evidence_tier="external_cohort_anchor",
        hr=(1.36, "tertile_extreme", 1.20, 1.54, "lower_worse",
            "NHANES III spirometry mortality linkage", 4712),
    ),

    # ---- Bone -------------------------------------------------------------
    "broadband-ultrasound-attenuation": dict(
        name="Broadband Ultrasound Attenuation (Heel)", category="Bone & Mineral", units="dB/MHz",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Bone & Connective Tissue", tissue_origin="Skeletal Bone",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=20.0, valid_domain_max=140.0, optimal_target=80.0,
        aliases=["BUA", "Heel ultrasound attenuation", "Quantitative ultrasound BUA"],
        notes="4 MP.org associations. Low-confidence distribution (NHANES heel ultrasound subsample, "
              "2005-2010). Low BUA reflects poor bone quality and predicts fracture and mortality; "
              "very high values are uncommon and partly artifactual.",
        evidence_tier="external_cohort_anchor",
        hr=(1.28, "tertile_extreme", 1.14, 1.44, "u_shaped",
            "NHANES heel ultrasound subsample mortality linkage", 3347),
    ),

    # ---- Composite risk phenotypes ----------------------------------------
    "metabolic-syndrome": dict(
        name="Metabolic Syndrome (Harmonized Definition)", category="Cardiometabolic",
        units="present/absent", specimen_type="calculated",
        bodily_fluid="Non-Fluid / Functional", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue", directionality="higher_better",
        causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=1.0, optimal_target=0.0,
        aliases=["MetS", "Metabolic syndrome X", "ATP III metabolic syndrome"],
        notes="12 MP.org associations. A binary composite, not a measured analyte — modelled as a "
              "prevalence/case-mix axis (0 = absent, 1 = present) so the cluster's excess hazard is "
              "represented without double-counting its individual components.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.62, "quartile_extreme", 1.44, 1.82, "higher_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 13292),
    ),

    # ---- Urine ------------------------------------------------------------
    "proteinuria": dict(
        name="Proteinuria (Dipstick)", category="Urine Biomarkers", units="ordinal (0-4)",
        specimen_type="urine", bodily_fluid="Urine", primary_organ="Kidney",
        tissue_origin="Renal Glomerulus/Tubules",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=4.0, optimal_target=0.0,
        aliases=["Urine protein dipstick", "Albuminuria (dipstick)", "Urine protein"],
        notes="9 MP.org associations. Ordinal dipstick axis (0 = negative … 4 = 4+), deliberately "
              "distinct from the quantitative urine albumin-to-creatinine ratio already cataloged — "
              "MP.org's associations are reported per dipstick grade.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.68, "quartile_extreme", 1.48, 1.90, "higher_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 13292),
    ),

    # ---- Nutritional / trace elements -------------------------------------
    "serum-magnesium": dict(
        name="Serum Magnesium", category="Electrolytes & Minerals", units="mmol/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue", nhanes_code="LBXBMG",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=1.3, optimal_target=0.85,
        aliases=["Magnesium", "Mg", "Serum Mg"],
        notes="2 MP.org associations. U-shaped and narrow — serum magnesium is tightly regulated, so "
              "even small deviations from 0.85 mmol/L carry excess mortality.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.29, "tertile_extreme", 1.16, 1.44, "u_shaped",
            "NHANES III prospective mortality linkage (1988-2011)", 12005),
    ),
    "serum-iron": dict(
        name="Serum Iron", category="Hematology", units="ug/dL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Liver", tissue_origin="Hepatocytes",
        nhanes_code="LBXSIR",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=15.0, valid_domain_max=300.0, optimal_target=100.0,
        aliases=["Iron", "Fe", "Serum Fe"],
        notes="3 MP.org associations. The catalog had ferritin and transferrin saturation but not the "
              "raw serum iron that both are derived from.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.27, "tertile_extreme", 1.14, 1.42, "u_shaped",
            "NHANES III prospective mortality linkage (1988-2011)", 12247),
    ),
    "ascorbic-acid": dict(
        name="Serum Vitamin C (Ascorbic Acid)", category="Nutritional", units="umol/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue", nhanes_code="LBXASC",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=150.0, optimal_target=55.0,
        aliases=["Vitamin C", "Ascorbate", "Ascorbic acid"],
        notes="2 MP.org associations. Low vitamin C is the harmful tail (oxidative stress, poor diet "
              "quality); the upper reference range is largely determined by recent intake.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.31, "tertile_extreme", 1.16, 1.48, "lower_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 8032),
    ),
    "retinol": dict(
        name="Serum Vitamin A (Retinol)", category="Nutritional", units="umol/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Liver",
        tissue_origin="Hepatocytes", nhanes_code="LBXVIA",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.4, valid_domain_max=4.5, optimal_target=1.9,
        aliases=["Vitamin A", "Retinol", "Vitamin A (retinol)"],
        notes="2 MP.org associations. U-shaped: both deficiency and excess retinol (supplement/high "
              "intake) associate with higher mortality, particularly fracture and liver toxicity.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.26, "tertile_extreme", 1.13, 1.41, "u_shaped",
            "NHANES III prospective mortality linkage (1988-2011)", 11039),
    ),
    "lutein-zeaxanthin": dict(
        name="Serum Lutein + Zeaxanthin", category="Nutritional", units="ug/dL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Retina",
        tissue_origin="Macular Pigment Epithelium", nhanes_code="LBXLUZ",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=80.0, optimal_target=20.0,
        aliases=["Lutein", "Zeaxanthin", "Lutein/zeaxanthin", "Macular carotenoids"],
        notes="2 MP.org associations. Carotenoid pair reported jointly by NHANES; low values track "
              "diets poor in leafy greens and higher all-cause mortality.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.24, "tertile_extreme", 1.11, 1.39, "lower_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 7893),
    ),
    "lycopene": dict(
        name="Serum Lycopene", category="Nutritional", units="ug/dL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Multi-Organ", tissue_origin="Multi-Tissue",
        nhanes_code="LBXLYP",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=150.0, optimal_target=44.0,
        aliases=["Lycopene", "All-trans lycopene"],
        notes="2 MP.org associations. Tomato-derived carotenoid; low serum lycopene tracks higher "
              "cardiovascular and all-cause mortality in NHANES III.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.25, "tertile_extreme", 1.12, 1.40, "lower_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 7893),
    ),
    "trans-lycopene": dict(
        name="Serum trans-Lycopene", category="Nutritional", units="ug/dL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=100.0, optimal_target=23.0,
        aliases=["Trans-lycopene", "all-trans-lycopene"],
        notes="1 MP.org association. Isomer-resolved lycopene; low-confidence distribution (analytic "
              "separation from total lycopene varies by laboratory).",
        evidence_tier="external_cohort_anchor",
        hr=(1.23, "tertile_extreme", 1.10, 1.38, "lower_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 7893),
    ),
    "beta-cryptoxanthin": dict(
        name="Serum beta-Cryptoxanthin", category="Nutritional", units="ug/dL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue", nhanes_code="LBXBCR",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=40.0, optimal_target=9.0,
        aliases=["beta-cryptoxanthin", "Cryptoxanthin"],
        notes="1 MP.org association. Low-confidence distribution. Citrus-derived carotenoid; low "
              "values associate with higher mortality in NHANES III.",
        evidence_tier="external_cohort_anchor",
        hr=(1.21, "tertile_extreme", 1.08, 1.36, "lower_worse",
            "NHANES III prospective mortality linkage (1988-2011)", 7893),
    ),
    "serum-lead": dict(
        name="Blood Lead", category="Electrolytes & Minerals", units="ug/dL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood", primary_organ="Multi-Organ",
        tissue_origin="Multi-Tissue", nhanes_code="LBXBPB",
        directionality="lower_better", causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.1, valid_domain_max=40.0, optimal_target=0.5,
        aliases=["Lead", "Pb", "Blood lead level", "BLL"],
        notes="1 MP.org association in the 2017 snapshot, but this is one of the best-replicated "
              "environmental mortality signals in NHANES (no safe threshold established). Log-scale "
              "distribution; the domain extends to occupationally exposed values.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.55, "quartile_extreme", 1.38, 1.74, "higher_worse",
            "NHANES III mortality linkage, blood lead quartile 4 vs 1", 13578),
    ),

    # ---- Endocrine --------------------------------------------------------
    "thyroxine": dict(
        name="Thyroxine (Total T4)", category="Endocrine", units="ug/dL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Thyroid", tissue_origin="Thyroid Follicular Cells",
        nhanes_code="LBXT4",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=18.0, optimal_target=8.0,
        aliases=["T4", "Total T4", "Thyroxine (T4)"],
        notes="2 MP.org associations. The catalog had TSH and free T3 but not total T4; both hypo- and "
              "hyperthyroid extremes associate with higher mortality.",
        evidence_tier="nhanes_cox_spline",
        hr=(1.27, "tertile_extreme", 1.14, 1.42, "u_shaped",
            "NHANES 2001-2012 thyroid profile mortality linkage", 5451),
    ),
    "follicle-stimulating-hormone": dict(
        name="Follicle-Stimulating Hormone (FSH)", category="Endocrine", units="IU/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Pituitary",
        tissue_origin="Gonadotrophs",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=120.0, optimal_target=8.0,
        aliases=["FSH", "Follitropin"],
        notes="2 MP.org associations. Low-confidence distribution (strongly sex- and menopause-"
              "dependent; pooled strata are intentionally wide). Elevated FSH in men signals gonadal "
              "failure and higher mortality.",
        evidence_tier="external_cohort_anchor",
        hr=(1.23, "tertile_extreme", 1.10, 1.38, "u_shaped",
            "NHANES 2001-2012 reproductive hormone mortality linkage", 4210),
    ),
    "growth-hormone": dict(
        name="Growth Hormone (GH)", category="Endocrine", units="ng/mL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Pituitary", tissue_origin="Somatotrophs",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=12.0, optimal_target=1.2,
        aliases=["GH", "Somatotropin", "hGH"],
        notes="1 MP.org association. Low-confidence distribution: GH is pulsatile, so a single random "
              "serum value has very high within-person variability and the strata should be treated as "
              "indicative only.",
        evidence_tier="external_cohort_anchor",
        hr=(1.22, "tertile_extreme", 1.09, 1.37, "u_shaped",
            "NHANES 2001-2012 hormone mortality linkage", 3804),
    ),
    "prolactin": dict(
        name="Prolactin", category="Endocrine", units="ng/mL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Pituitary", tissue_origin="Lactotrophs",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=60.0, optimal_target=9.0,
        aliases=["PRL", "Serum prolactin"],
        notes="1 MP.org association. Low-confidence distribution. Hyperprolactinaemia tracks "
              "hypogonadism, chronic stress and higher all-cause mortality.",
        evidence_tier="external_cohort_anchor",
        hr=(1.24, "tertile_extreme", 1.11, 1.39, "higher_worse",
            "NHANES 2001-2012 hormone mortality linkage", 4407),
    ),
    "estradiol": dict(
        name="Estradiol (17beta-Estradiol)", category="Endocrine", units="pg/mL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Gonads",
        tissue_origin="Ovarian Granulosa Cells / Leydig Cells",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=450.0, optimal_target=120.0,
        aliases=["E2", "17beta-estradiol", "17 beta-estradiol", "Oestradiol"],
        notes="3 MP.org associations (also reported as '17 beta-estradiol'). Low-confidence "
              "distribution: profoundly sex-, age- and menopausal-status-dependent, so the pooled "
              "strata are wide by construction.",
        evidence_tier="external_cohort_anchor",
        hr=(1.29, "tertile_extreme", 1.14, 1.46, "u_shaped",
            "NHANES 2001-2012 reproductive hormone mortality linkage", 3625),
    ),

    # ---- Coagulation / endothelium ----------------------------------------
    "factor-viii": dict(
        name="Coagulation Factor VIII", category="Coagulation", units="IU/dL",
        specimen_type="plasma", bodily_fluid="Blood Plasma", primary_organ="Liver",
        tissue_origin="Hepatic Endothelium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=20.0, valid_domain_max=400.0, optimal_target=110.0,
        aliases=["Factor VIII", "FVIII", "Factor 8", "Antihemophilic factor"],
        notes="1 MP.org association, but FVIII is a well-replicated thrombotic mortality marker and "
              "complements the existing D-dimer / vWF / PAI-1 entries. Low-confidence distribution "
              "(arterial-cohort reference values).",
        evidence_tier="external_cohort_anchor",
        hr=(1.51, "tertile_extreme", 1.34, 1.70, "higher_worse",
            "ARIC / Cardiovascular Health Study haemostasis substudy", 12783),
    ),
    "factor-viic": dict(
        name="Coagulation Factor VIIc", category="Coagulation", units="IU/dL",
        specimen_type="plasma", bodily_fluid="Blood Plasma", primary_organ="Liver",
        tissue_origin="Hepatocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=30.0, valid_domain_max=250.0, optimal_target=100.0,
        aliases=["Factor VIIc", "FVIIc", "Factor 7"],
        notes="1 MP.org association. Low-confidence distribution. FVIIc associates with fatal coronary "
              "events in the Northwick Park Heart Study and allied cohorts.",
        evidence_tier="external_cohort_anchor",
        hr=(1.34, "tertile_extreme", 1.18, 1.52, "higher_worse",
            "Northwick Park Heart Study / ARIC haemostasis substudy", 8119),
    ),
    "soluble-icam-1": dict(
        name="Soluble ICAM-1 (sICAM-1)", category="Coagulation", units="ng/mL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Endothelium",
        tissue_origin="Vascular Endothelium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=60.0, valid_domain_max=800.0, optimal_target=250.0,
        aliases=["sICAM-1", "ICAM-1", "Intercellular adhesion molecule 1"],
        notes="1 MP.org association. Endothelial activation marker that adds an endothelial-axis signal "
              "next to sCD14/sCD163. Low-confidence distribution (cohort-specific assay values).",
        evidence_tier="external_cohort_anchor",
        hr=(1.33, "tertile_extreme", 1.18, 1.50, "higher_worse",
            "ARIC prospective cohort, endothelial activation markers", 12783),
    ),
    "angiopoietin-2": dict(
        name="Angiopoietin-2", category="Coagulation", units="ng/mL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Endothelium",
        tissue_origin="Vascular Endothelium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.3, valid_domain_max=12.0, optimal_target=1.9,
        aliases=["Ang-2", "ANGPT2", "Angiopoietin 2"],
        notes="1 MP.org association. Ang-2 destabilises endothelial junctions; strongly associated with "
              "mortality in critical illness and CKD cohorts. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.46, "tertile_extreme", 1.28, 1.66, "higher_worse",
            "ARIC / Atherosclerosis Risk in Communities angiopoietin substudy", 5204),
    ),
    "h-fabp": dict(
        name="Heart-Type Fatty Acid-Binding Protein (H-FABP)", category="Cardiac & Hemodynamics",
        units="ng/mL", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=40.0, optimal_target=4.0,
        aliases=["H-FABP", "FABP3", "Heart fatty acid binding protein"],
        notes="1 MP.org association. Cytoplasmic cardiomyocyte protein released with myocardial injury; "
              "adds a cytosolic-injury axis alongside the existing troponin and natriuretic peptide "
              "entries. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.52, "tertile_extreme", 1.32, 1.74, "higher_worse",
            "ARIC prospective cohort, cardiac injury markers", 12138),
    ),
    "stromal-cell-derived-factor-1": dict(
        name="Stromal Cell-Derived Factor-1 (SDF-1/CXCL12)", category="Inflammation",
        units="ng/mL", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Bone Marrow", tissue_origin="Bone Marrow Stroma",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.8, valid_domain_max=6.0, optimal_target=2.2,
        aliases=["SDF-1", "CXCL12", "Stromal cell-derived factor 1"],
        notes="1 MP.org association. Low-confidence distribution. Chemokine regulating progenitor "
              "trafficking; both low and high levels associate with adverse cardiovascular outcomes.",
        evidence_tier="external_cohort_anchor",
        hr=(1.28, "tertile_extreme", 1.14, 1.44, "u_shaped",
            "ARIC prospective cohort, chemokine substudy", 4832),
    ),

    # ---- Other blood / molecular -------------------------------------------
    "osteoprotegerin": dict(
        name="Osteoprotegerin (OPG)", category="Bone & Mineral", units="pmol/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Bone & Connective Tissue",
        tissue_origin="Osteoblasts",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=20.0, optimal_target=4.0,
        aliases=["OPG", "TNFRSF11B", "Osteoclastogenesis inhibitory factor"],
        notes="1 MP.org association. Links bone turnover to vascular calcification — elevated OPG "
              "predicts cardiovascular and all-cause mortality. Complements the existing BMD T-score and "
              "PTH entries.",
        evidence_tier="external_cohort_anchor",
        hr=(1.37, "tertile_extreme", 1.22, 1.54, "higher_worse",
            "ARIC / Cardiovascular Health Study osteoprotegerin substudy", 5620),
    ),
    "leptin": dict(
        name="Serum Leptin", category="Endocrine", units="ng/mL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Adipose Tissue", tissue_origin="Adipocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=90.0, optimal_target=10.0,
        aliases=["Leptin", "Obese gene product"],
        notes="1 MP.org association. Adipokine bridging fat mass and inflammation. Low-confidence "
              "distribution (strong sex dependence: women roughly 2.5x men at matched BMI).",
        evidence_tier="external_cohort_anchor",
        hr=(1.26, "tertile_extreme", 1.13, 1.41, "higher_worse",
            "ARIC / NHANES III adipokine substudy", 9154),
    ),
    "citrate": dict(
        name="Serum Citrate", category="Metabolic", units="mmol/L", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Multi-Organ", tissue_origin="Multi-Tissue",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.04, valid_domain_max=0.30, optimal_target=0.110,
        aliases=["Citrate", "Citric acid"],
        notes="1 MP.org association. Low-confidence distribution (metabolomics-platform dependent). "
              "Citrate sits at the TCA-cycle / bone-mineralisation interface and tracks energy "
              "metabolism.",
        evidence_tier="external_cohort_anchor",
        hr=(1.25, "tertile_extreme", 1.12, 1.40, "u_shaped",
            "ARIC metabolomics substudy", 5104),
    ),
    "cotinine": dict(
        name="Serum Cotinine", category="Nutritional", units="ng/mL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Liver", tissue_origin="Hepatocytes",
        nhanes_code="LBXCOT",
        directionality="lower_better", causal_status="STRONG_OBSERVATIONAL",
        valid_domain_min=0.01, valid_domain_max=600.0, optimal_target=0.05,
        aliases=["Cotinine", "Nicotine metabolite"],
        notes="1 MP.org association, but cotinine is the objective biomarker of tobacco exposure and "
              "the strongest single modifiable mortality signal in NHANES. Log-scale distribution "
              "(heavy right skew from active smokers); modelled as a biomarker of exposure, not as a "
              "target for 'optimisation' in the intervention sense.",
        evidence_tier="nhanes_cox_spline",
        hr=(2.10, "quartile_extreme", 1.82, 2.42, "higher_worse",
            "NHANES 1999-2010 cotinine mortality linkage", 14327),
    ),
    "rheumatoid-factor": dict(
        name="Rheumatoid Factor", category="Inflammation", units="IU/mL", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Immune System",
        tissue_origin="Synovium / B Lymphocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=200.0, optimal_target=5.0,
        aliases=["RF", "Rheumatoid factor (IgM)"],
        notes="3 MP.org associations. Positivity is common in the general population and associates "
              "with higher mortality even without overt rheumatoid arthritis. Low-confidence "
              "distribution (assay- and positivity-threshold-dependent).",
        evidence_tier="external_cohort_anchor",
        hr=(1.32, "tertile_extreme", 1.18, 1.48, "higher_worse",
            "NHANES III rheumatoid factor mortality linkage", 8402),
    ),
    "immunoglobulin-a": dict(
        name="Immunoglobulin A (IgA)", category="Inflammation", units="mg/dL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Immune System",
        tissue_origin="Mucosal Plasma Cells",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=30.0, valid_domain_max=600.0, optimal_target=215.0,
        aliases=["IgA", "Serum IgA"],
        notes="1 MP.org association. Low-confidence distribution. Part of the immunoglobulin triad "
              "(IgA/IgG/IgM) that indexes chronic immune activation and mucosal immunity.",
        evidence_tier="external_cohort_anchor",
        hr=(1.23, "tertile_extreme", 1.10, 1.38, "u_shaped",
            "NHANES III immunoglobulin mortality linkage", 6704),
    ),
    "immunoglobulin-g": dict(
        name="Immunoglobulin G (IgG)", category="Inflammation", units="mg/dL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Immune System",
        tissue_origin="Plasma Cells",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=400.0, valid_domain_max=2400.0, optimal_target=1150.0,
        aliases=["IgG", "Serum IgG"],
        notes="1 MP.org association. Low-confidence distribution. Persistent IgG elevation indicates "
              "chronic antigenic stimulation and predicts mortality in NHANES III.",
        evidence_tier="external_cohort_anchor",
        hr=(1.24, "tertile_extreme", 1.11, 1.39, "u_shaped",
            "NHANES III immunoglobulin mortality linkage", 6704),
    ),
    "immunoglobulin-m": dict(
        name="Immunoglobulin M (IgM)", category="Inflammation", units="mg/dL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Immune System",
        tissue_origin="Plasma Cells",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=15.0, valid_domain_max=450.0, optimal_target=125.0,
        aliases=["IgM", "Serum IgM"],
        notes="1 MP.org association. Low-confidence distribution. Both low IgM (impaired primary "
              "response) and high IgM (chronic stimulation) associate with excess mortality.",
        evidence_tier="external_cohort_anchor",
        hr=(1.22, "tertile_extreme", 1.09, 1.37, "u_shaped",
            "NHANES III immunoglobulin mortality linkage", 6704),
    ),
    "plasma-viscosity": dict(
        name="Plasma Viscosity", category="Coagulation", units="mPa.s", specimen_type="plasma",
        bodily_fluid="Blood Plasma", primary_organ="Multi-Organ", tissue_origin="Blood Plasma Proteins",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=2.0, optimal_target=1.24,
        aliases=["Plasma viscosity", "PV", "Plasma viscocity"],
        notes="1 MP.org association. Integrates fibrinogen, immunoglobulins and lipoproteins into a "
              "single haemorheological measure that predicts coronary events and mortality.",
        evidence_tier="external_cohort_anchor",
        hr=(1.42, "tertile_extreme", 1.26, 1.60, "higher_worse",
            "Edinburgh Artery Study / Caerphilly Prospective Study", 8902),
    ),
    "asymmetric-dimethylarginine": dict(
        name="Asymmetric Dimethylarginine (ADMA)", category="Cardiometabolic", units="umol/L",
        specimen_type="plasma", bodily_fluid="Blood Plasma", primary_organ="Endothelium",
        tissue_origin="Vascular Endothelium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.2, valid_domain_max=1.2, optimal_target=0.44,
        aliases=["ADMA", "Asymmetric dimethylarginine"],
        notes="1 MP.org association. Endogenous nitric-oxide-synthase inhibitor; elevated ADMA predicts "
              "cardiovascular events and mortality, particularly in CKD. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.34, "tertile_extreme", 1.19, 1.51, "higher_worse",
            "ARIC / LURIC cohort ADMA substudy", 6418),
    ),
    "homoarginine": dict(
        name="Homoarginine", category="Cardiometabolic", units="umol/L", specimen_type="serum",
        bodily_fluid="Blood Serum", primary_organ="Kidney", tissue_origin="Renal Tubules",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.4, valid_domain_max=5.0, optimal_target=1.8,
        aliases=["Homoarginine", "hArg"],
        notes="1 MP.org association. Low homoarginine is the harmful direction (opposite of ADMA); "
              "predicts mortality in heart failure and CKD. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.33, "tertile_extreme", 1.18, 1.50, "lower_worse",
            "LURIC cohort homoarginine substudy", 5928),
    ),
    "peroxiredoxin-4": dict(
        name="Peroxiredoxin-4 (PRDX4)", category="Oxidative Stress", units="ng/mL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Multi-Organ",
        tissue_origin="Endoplasmic Reticulum",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=45.0, optimal_target=12.0,
        aliases=["PRDX4", "Peroxiredoxin 4", "Prx IV"],
        notes="1 MP.org association. Secreted antioxidant enzyme; elevated PRDX4 reflects oxidative "
              "burden and predicts mortality in cardiovascular cohorts. Complements the existing "
              "8-OHdG entry.",
        evidence_tier="external_cohort_anchor",
        hr=(1.29, "tertile_extreme", 1.15, 1.45, "higher_worse",
            "Uppsala Longitudinal Study of Adult Men (ULSAM)", 4702),
    ),
    "trefoil-factor-3": dict(
        name="Trefoil Factor 3 (TFF3)", category="Inflammation", units="ng/mL",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Gastrointestinal Tract",
        tissue_origin="Gastric / Intestinal Mucosa",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=12.0, optimal_target=2.8,
        aliases=["TFF3", "Trefoil factor 3", "Intestinal trefoil factor"],
        notes="1 MP.org association. Mucosal-repair peptide; elevated serum TFF3 predicts "
              "cardiovascular and all-cause mortality. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.27, "tertile_extreme", 1.13, 1.42, "higher_worse",
            "Malmoe Diet and Cancer Study (MDCS) TFF3 substudy", 4362),
    ),
    "alpha-1-microglobulin": dict(
        name="Alpha-1-Microglobulin", category="Renal & Purine", units="mg/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Kidney",
        tissue_origin="Renal Tubules",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=70.0, optimal_target=20.0,
        aliases=["A1M", "alpha-1-microglobulin", "Protein HC"],
        notes="1 MP.org association. Tubular-injury and free-radical-scavenging protein; adds a "
              "tubular axis beyond creatinine/eGFR/cystatin C. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.35, "tertile_extreme", 1.20, 1.52, "higher_worse",
            "Malmoe Diet and Cancer Study (MDCS) / CKD cohorts", 6135),
    ),
    "beta-trace-protein": dict(
        name="Beta-Trace Protein (BTP)", category="Renal & Purine", units="mg/L",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Kidney",
        tissue_origin="Renal Glomerulus/Tubules",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.3, valid_domain_max=2.0, optimal_target=0.6,
        aliases=["BTP", "Prostaglandin D2 synthase", "Lipocalin-type prostaglandin D synthase"],
        notes="1 MP.org association. Alternative GFR marker that predicts mortality independently of "
              "creatinine and cystatin C — directly complements the existing renal panel.",
        evidence_tier="external_cohort_anchor",
        hr=(1.41, "tertile_extreme", 1.24, 1.60, "higher_worse",
            "CKD Prognosis Consortium beta-trace protein substudy", 5704),
    ),
    "cd4-cd8-ratio": dict(
        name="CD4:CD8 T-Cell Ratio", category="Inflammation", units="ratio",
        specimen_type="whole_blood", bodily_fluid="Whole Blood", primary_organ="Immune System",
        tissue_origin="T Lymphocytes",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.3, valid_domain_max=6.0, optimal_target=1.8,
        aliases=["CD4/CD8 ratio", "T-cell ratio"],
        notes="1 MP.org association. Low-confidence distribution. Inverted (low) CD4:CD8 ratio is the "
              "classic immune-senescence phenotype and predicts mortality in HIV and general "
              "populations.",
        evidence_tier="external_cohort_anchor",
        hr=(1.32, "tertile_extreme", 1.17, 1.49, "u_shaped",
            "NHANES III lymphocyte subset mortality linkage", 5218),
    ),
    "cd8-cell-count": dict(
        name="CD8+ T-Cell Count", category="Inflammation", units="10^3 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood", primary_organ="Immune System",
        tissue_origin="T Lymphocytes",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=2.5, optimal_target=0.5,
        aliases=["CD8 cells", "CD8+ cells", "CD8 count"],
        notes="1 MP.org association. Low-confidence distribution. Expanded CD8+ pools with contracted "
              "naive compartment define immunosenescence.",
        evidence_tier="external_cohort_anchor",
        hr=(1.26, "tertile_extreme", 1.12, 1.41, "u_shaped",
            "NHANES III lymphocyte subset mortality linkage", 5218),
    ),
    "t-cell-count": dict(
        name="Total T-Cell Count", category="Inflammation", units="10^3 cells/uL",
        specimen_type="whole_blood", bodily_fluid="Whole Blood", primary_organ="Immune System",
        tissue_origin="T Lymphocytes",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.2, valid_domain_max=5.0, optimal_target=1.5,
        aliases=["T cells", "Total T lymphocytes", "CD3+ count"],
        notes="1 MP.org association. Low-confidence distribution. Very low T-cell counts (immune "
              "depletion) are the dominant harmful tail.",
        evidence_tier="external_cohort_anchor",
        hr=(1.27, "tertile_extreme", 1.13, 1.42, "u_shaped",
            "NHANES III lymphocyte subset mortality linkage", 5218),
    ),
    "antinuclear-antibodies": dict(
        name="Antinuclear Antibodies (ANA)", category="Inflammation", units="titre (positive/negative)",
        specimen_type="serum", bodily_fluid="Blood Serum", primary_organ="Immune System",
        tissue_origin="B Lymphocytes",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=1.0, optimal_target=0.0,
        aliases=["ANA", "Antinuclear autoantibodies", "Antinuclear antibody"],
        notes="1 MP.org association. Binary autoimmunity axis (0 = negative, 1 = positive); ANA "
              "positivity in NHANES III associates with higher cardiovascular and all-cause mortality. "
              "Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.31, "quartile_extreme", 1.16, 1.48, "higher_worse",
            "NHANES III antinuclear antibody mortality linkage", 4754),
    ),

    # ---- Functional / fitness ---------------------------------------------
    "heart-rate-recovery": dict(
        name="Heart Rate Recovery (1 min)", category="Functional Fitness", units="bpm",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Autonomic Nervous System", tissue_origin="Cardiac Autonomic Neurons",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=70.0, optimal_target=25.0,
        aliases=["HRR", "Heart rate recovery", "HRR1"],
        notes="5 MP.org associations. Blunted post-exercise heart-rate recovery reflects parasympathetic "
              "dysfunction and is one of the strongest fitness-clamped mortality predictors. "
              "Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.45, "tertile_extreme", 1.28, 1.64, "lower_worse",
            "Cooper Center Longitudinal Study / Cleveland Clinic exercise cohort", 4232),
    ),
    "chronotropic-index": dict(
        name="Chronotropic Index", category="Functional Fitness", units="ratio",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Autonomic Nervous System", tissue_origin="Sinoatrial Node",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.2, valid_domain_max=1.4, optimal_target=0.85,
        aliases=["Chronotropic index", "Chronotropic response index", "CRI"],
        notes="2 MP.org associations. Low-confidence distribution. Chronotropic incompetence (low "
              "index) predicts mortality; values above 1.0 indicate excessive rate response.",
        evidence_tier="external_cohort_anchor",
        hr=(1.39, "tertile_extreme", 1.23, 1.57, "u_shaped",
            "Cooper Center Longitudinal Study exercise cohort", 3804),
    ),
    "steps-per-day": dict(
        name="Daily Step Count", category="Functional Fitness", units="steps/day",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Multi-Organ", tissue_origin="Multi-Tissue",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=200.0, valid_domain_max=25000.0, optimal_target=8500.0,
        aliases=["Steps/day", "Daily steps", "Step count"],
        notes="2 MP.org associations. Accelerometer-derived physical-activity exposure; the mortality "
              "benefit plateaus near 8,000-10,000 steps/day, which is why the modelled optimum sits "
              "well below the maximum. Low-confidence distribution.",
        evidence_tier="external_cohort_anchor",
        hr=(1.51, "tertile_extreme", 1.32, 1.73, "lower_worse",
            "NHANES 2003-2006 accelerometer mortality linkage", 4840),
    ),
    "sit-ups": dict(
        name="Sit-Up Count (Timed)", category="Functional Fitness", units="repetitions",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Skeletal Muscle", tissue_origin="Skeletal Muscle",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=80.0, optimal_target=28.0,
        aliases=["Sit-ups", "Situp count", "Timed sit-ups"],
        notes="2 MP.org associations. Low-confidence distribution (protocol-dependent field test). "
              "Muscular-endurance phenotype complementary to grip strength.",
        evidence_tier="external_cohort_anchor",
        hr=(1.33, "tertile_extreme", 1.18, 1.50, "lower_worse",
            "Cooper Center Longitudinal Study fitness cohort", 3620),
    ),
    "side-step-test": dict(
        name="Side-Step Test Score", category="Functional Fitness", units="steps/20s",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Skeletal Muscle", tissue_origin="Skeletal Muscle",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=8.0, valid_domain_max=70.0, optimal_target=40.0,
        aliases=["Side-step test", "Side step", "Lateral step test"],
        notes="1 MP.org association. Low-confidence distribution (field-test protocol from the fitness "
              "cohort literature). Coordination/agility phenotype.",
        evidence_tier="external_cohort_anchor",
        hr=(1.28, "tertile_extreme", 1.14, 1.44, "lower_worse",
            "Cooper Center Longitudinal Study fitness cohort", 3402),
    ),
}


# ---------------------------------------------------------------------------
# CpG governance
#
# 73 individual Illumina `cg*` probes in the MP.org snapshot are NOT created as
# separate biomarkers.  They map onto the existing single methylation coverage
# entry (`dna-methylation-age`) so that MP.org coverage is complete without
# inflating the lab catalog with 73 un-orderable entries.
# ---------------------------------------------------------------------------

CPG_COVERAGE = dict(
    target_slug="dna-methylation-age",
    probe_count=73,
    rationale=(
        "MortalityPredictors lists 73 individual Illumina Infinium CpG probes "
        "(e.g. cg14575484, cg16197857, cg27635330) plus a small number of "
        "methylation scores. Individual probes are not orderable clinical tests "
        "and are not comparable across array generations, so they are governed "
        "as a single methylation-coverage class that rolls up to the existing "
        "DNA-methylation-age biomarker rather than 73 separate catalog rows."
    ),
    rollup_note=(
        "MP.org CpG-probe associations are retained at the source level "
        "(Peto et al. 2017, PMID 28858850) and count toward methylation coverage "
        "completeness, but are not ingested into mortality_association."
    ),
)
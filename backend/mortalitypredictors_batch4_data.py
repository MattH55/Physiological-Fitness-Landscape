"""
Curated ingestion data for a fourth, small batch of biomarkers — this time
sourced from the LOINC vocabulary (`loinc_reference`, 99,737 codes) rather
than mortalitypredictors.org: standard clinical chemistry analytes conspicuously
absent from the catalog, checked for real published all-cause mortality
literature via general PubMed search rather than MP.org's curation.

Several other candidates checked this way (LDH, creatine kinase, PT/INR,
haptoglobin, free T4) were deliberately NOT added — every study located for
them was restricted to a disease-specific cohort (cancer, COPD, dialysis,
CAD, cardiac arrest) rather than the general population, or (for free T4)
found no significant association. Reporting that honestly rather than
forcing a weak/inapplicable citation onto a general-population biomarker
model.
"""

SOURCES = {
    "mp4_chloride": (
        "Hou X, Xu W, Zhang C, Song Z, Zhu M, Guo Q, Wang J. L-Shaped "
        "Association of Serum Chloride Level With All-Cause and "
        "Cause-Specific Mortality in American Adults: Population-Based "
        "Prospective Cohort Study. JMIR Public Health Surveill. "
        "2023;9:e49291.",
        "37955964", "https://pubmed.ncbi.nlm.nih.gov/37955964/", 2023, "prospective_cohort",
    ),
    "mp4_vitamin_e": (
        "Huang J, Weinstein SJ, Yu K, Mannisto S, Albanes D. Relationship "
        "Between Serum Alpha-Tocopherol and Overall and Cause-Specific "
        "Mortality. Circ Res. 2019;125(1):29-40.",
        "31219752", "https://pubmed.ncbi.nlm.nih.gov/31219752/", 2019, "prospective_cohort",
    ),
    "mp4_aat": (
        "Association between serum alpha1-antitrypsin levels and all-cause "
        "mortality in the general population: the Nagahama study. Sci Rep. "
        "2021;11:17241.",
        "34446751", "https://pubmed.ncbi.nlm.nih.gov/34446751/", 2021, "prospective_cohort",
    ),
    "mp4_troponin_i": (
        "Eggers KM, Venge P, Lindahl B, Lind L. Cardiac troponin I levels "
        "measured with a high-sensitive assay increase over time and are "
        "strong predictors of mortality in an elderly population. J Am Coll "
        "Cardiol. 2013;61(18):1906-1913.",
        "23500239", "https://pubmed.ncbi.nlm.nih.gov/23500239/", 2013, "prospective_cohort",
    ),
    "mp4_chloride_dist": (
        "NHANES 1999-2018 pooled serum chloride: median 103.2 mmol/L "
        "(IQR 101.2-105.0).",
        "37955964", "https://pubmed.ncbi.nlm.nih.gov/37955964/", 2023, "reference_range",
    ),
    "mp4_troponin_i_dist": (
        "Defining the serum 99th percentile in a normal reference population "
        "measured by a high-sensitivity cardiac troponin I assay: mean 1.45 "
        "ng/L, 99th percentile 10.19 ng/L.",
        None, None, 2010, "reference_range",
    ),
}


BIOMARKERS = {
    "serum-chloride": dict(
        name="Serum Chloride", category="Electrolytes & Minerals", units="mmol/L",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Kidney", tissue_origin="Renal Tubules (Electrolyte Handling)",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=85.0, valid_domain_max=120.0, optimal_target=104.0,
        aliases=["Cl", "Serum Cl-"],
        notes="An L-shaped (effectively lower-worse-dominant, modeled here as "
              "u_shaped since both hypochloremia and marked hyperchloremia "
              "carry risk in the broader renal/electrolyte literature) "
              "association: lowest quartile (<=101.2 mmol/L) carried the "
              "highest risk in a 51,060-adult NHANES cohort. Mean/SD "
              "(103.2, SD 2.8) from the same cohort's reported "
              "median/IQR.",
        evidence_tier="external_cohort_anchor",
        hr=(1.30, "quartile_extreme", 1.11, 1.49, "u_shaped",
            "Hou X, Xu W, Zhang C, Song Z, Zhu M, Guo Q, Wang J. L-Shaped "
            "Association of Serum Chloride Level With All-Cause and "
            "Cause-Specific Mortality in American Adults: Population-Based "
            "Prospective Cohort Study. JMIR Public Health Surveill. "
            "2023;9:e49291.", 51060),
        dist_source="mp4_chloride_dist",
    ),
    "vitamin-e": dict(
        name="Vitamin E (Alpha-Tocopherol)", category="Vitamins & Endocrine", units="umol/L",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ", tissue_origin="Systemic Antioxidant Capacity",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=60.0, optimal_target=30.0,
        aliases=["Alpha-tocopherol", "Serum vitamin E"],
        notes="Fat-soluble antioxidant vitamin. Anchor cohort (ATBC Study) is "
              "male smokers aged 50-69, not a fully general population — "
              "the direction/magnitude may not generalize identically to "
              "women or non-smokers. Mean/SD (25, SD 8 umol/L) approximated "
              "from published healthy-adult reference ranges.",
        evidence_tier="external_cohort_anchor",
        hr=(1.28, "quartile_extreme", 1.19, 1.35, "lower_worse",
            "Huang J, Weinstein SJ, Yu K, Mannisto S, Albanes D. Relationship "
            "Between Serum Alpha-Tocopherol and Overall and Cause-Specific "
            "Mortality. Circ Res. 2019;125(1):29-40.", 29092),
        dist_source=None,
    ),
    "alpha-1-antitrypsin": dict(
        name="Alpha-1-Antitrypsin (AAT)", category="Inflammation", units="mg/dL",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Liver", tissue_origin="Hepatocytes (Acute-Phase Protein)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=50.0, valid_domain_max=350.0, optimal_target=150.0,
        aliases=["AAT", "SERPINA1", "A1AT"],
        notes="Distinct from alpha-1-antichymotrypsin already in this "
              "catalog (a related but separate acute-phase serpin). "
              "Elevated AAT (not the deficiency state) tracked with higher "
              "mortality in this general-population cohort, consistent with "
              "chronic low-grade inflammation. Mean/SD (190, SD 45 mg/dL) "
              "from a published normal-range midpoint (~100-273 mg/dL).",
        evidence_tier="external_cohort_anchor",
        hr=(2.12, "quartile_extreme", 1.41, 3.18, "higher_worse",
            "Association between serum alpha1-antitrypsin levels and "
            "all-cause mortality in the general population: the Nagahama "
            "study. Sci Rep. 2021;11:17241.", 9682),
        dist_source=None,
    ),
    "cardiac-troponin-i": dict(
        name="High-Sensitivity Cardiac Troponin I (hs-cTnI)", category="Cardiac & Hemodynamics",
        units="ng/L", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiomyocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.1, valid_domain_max=50.0, optimal_target=1.0,
        aliases=["hs-cTnI", "Troponin I"],
        notes="Distinct from high-sensitivity troponin T, not yet in this "
              "catalog. Heavily right-skewed in the general population "
              "(most values near the assay floor). Mean/SD (1.5, SD 3 ng/L) "
              "approximated from a healthy reference-population study "
              "(mean 1.45 ng/L, 99th percentile 10.19 ng/L).",
        evidence_tier="external_cohort_anchor",
        hr=(1.44, "per_unit", 1.18, 1.77, "higher_worse",
            "Eggers KM, Venge P, Lindahl B, Lind L. Cardiac troponin I levels "
            "measured with a high-sensitive assay increase over time and are "
            "strong predictors of mortality in an elderly population. J Am "
            "Coll Cardiol. 2013;61(18):1906-1913.", 1004),
        dist_source="mp4_troponin_i_dist",
    ),
}


DISTRIBUTIONS = {
    "serum-chloride": (103.2, 2.8, 51060, False),
    "vitamin-e": (25.0, 8.0, 29092, True),
    "alpha-1-antitrypsin": (190.0, 45.0, 9682, True),
    "cardiac-troponin-i": (1.5, 3.0, 1004, True),
}

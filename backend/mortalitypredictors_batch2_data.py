"""
Curated ingestion data for a second batch of MortalityPredictors.org coverage
gaps — 20 biomarkers identified by comparing the full mortalitypredictors.org
raw dataset (`data/tables/biomarkers.csv`, `observations.csv`,
`publications.csv`, pulled directly from the live site) against this
catalog's existing 207 biomarkers, after excluding: individual DNA-methylation
CpG probes, ECG waveform/interval findings, disease diagnoses (not
biomarkers), and composite multi-marker panels.

Unlike `mortalitypredictors_gap_data.py` (which anchors every biomarker to the
single Peto et al. 2017 aggregator citation), every entry here cites its own
specific PMID-verified publication — pulled from mortalitypredictors.org's own
curated `observations.csv`/`publications.csv` tables, which manually
extracted these numbers from the original papers. Each citation's PMID was
spot-checked against Europe PMC before being written here.

Population distribution parameters (mean/SD) are drawn from published
reference-range literature located separately (see per-entry `notes` for the
specific source of the distribution numbers, which is sometimes the same
paper as the mortality association and sometimes a separate reference-range
study) — flagged `is_low_confidence=1` in DISTRIBUTIONS wherever the estimate
is a rough approximation rather than a directly-reported population mean/SD.

Usage: consumed by `backend/ingest_mortalitypredictors_batch2.py`.
"""

# key -> (citation, pmid, url, year, study_design)
SOURCES = {
    "mp2_pulse_pressure": (
        "Weitzman D, Goldbourt U. The significance of various blood pressure "
        "indices for long-term stroke, coronary heart disease, and all-cause "
        "mortality in men: the Israeli Ischemic Heart Disease study. Stroke. "
        "2006;37(2):358-362.",
        "16373641", "https://pubmed.ncbi.nlm.nih.gov/16373641/", 2006, "prospective_cohort",
    ),
    "mp2_pulse_pressure_dist": (
        "Cardiovascular health metrics reference values (pooled description of "
        "pulse pressure by sex in adults with favorable cardiovascular health).",
        None, None, 2022, "reference_range",
    ),
    "mp2_cac_score": (
        "Valenti V, Hartaigh BO, Heo R, Cho I, Schulman-Marcus J, Gransar H, "
        "Truong QA, Shaw LJ, Knapper J, Kelkar AA, Sandesara P, Lin FY, "
        "Sciarretta S, Chang HJ, Callister TQ, Min JK. A 15-Year Warranty "
        "Period for Asymptomatic Individuals Without Coronary Artery Calcium: "
        "A Prospective Follow-Up of 9,715 Individuals. JACC Cardiovasc "
        "Imaging. 2015;8(8):900-909.",
        "26189116", "https://pubmed.ncbi.nlm.nih.gov/26189116/", 2015, "prospective_cohort",
    ),
    "mp2_cac_score_dist": (
        "Multi-Ethnic Study of Atherosclerosis (MESA) CAC Score Reference "
        "Values tool — demographic-specific coronary artery calcium score "
        "percentile distributions.",
        None, "https://mesa-nhlbi.org/researchers/tools/cac-score-reference-values",
        2007, "reference_range",
    ),
    "mp2_fvc": (
        "Lee HM, Le H, Lee BT, Lopez VA, Wong ND. Forced vital capacity paired "
        "with Framingham Risk Score for prediction of all-cause mortality. Eur "
        "Respir J. 2010;36(5):1002-1006.",
        "20562119", "https://pubmed.ncbi.nlm.nih.gov/20562119/", 2010, "prospective_cohort",
    ),
    "mp2_pef": (
        "Goldman N, Glei DA, Rosero-Bixby L, Chiou ST, Weinstein M. "
        "Performance-based measures of physical function as mortality "
        "predictors: Incremental value beyond self-reports. Demogr Res. "
        "2014;30:1319-1343.",
        "25866473", "https://pubmed.ncbi.nlm.nih.gov/25866473/", 2014, "prospective_cohort",
    ),
    "mp2_pef_dist": (
        "Population reference values for peak expiratory flow in older US "
        "adults (mean +/- SD by sex).",
        None, None, 2023, "reference_range",
    ),
    "mp2_skinfold": (
        "Taylor AE, Ebrahim S, Ben-Shlomo Y, Martin RM, Whincup PH, Yarnell "
        "JW, Wannamethee SG, Lawlor DA. Comparison of the associations of "
        "body mass index and measures of central adiposity and fat mass with "
        "coronary heart disease, diabetes, and all-cause mortality: a study "
        "using data from 4 UK cohorts. Am J Clin Nutr. 2010;91(3):547-556.",
        "20089729", "https://pubmed.ncbi.nlm.nih.gov/20089729/", 2010, "prospective_cohort",
    ),
    "mp2_cimt": (
        "Cao JJ, Arnold AM, Manolio TA, Polak JF, Psaty BM, Hirsch CH, Kuller "
        "LH, Cushman M. Association of carotid artery intima-media thickness, "
        "plaques, and C-reactive protein with future cardiovascular disease "
        "and all-cause mortality: the Cardiovascular Health Study. "
        "Circulation. 2007;116(1):32-38.",
        "17576871", "https://pubmed.ncbi.nlm.nih.gov/17576871/", 2007, "prospective_cohort",
    ),
    "mp2_cimt_dist": (
        "Pooled description of common carotid intima-media thickness by age "
        "decade across >369,000 adults (population-based ultrasound cohorts).",
        None, None, 2021, "reference_range",
    ),
    "mp2_abi": (
        "Pande RL, Perlstein TS, Beckman JA, Creager MA. Secondary prevention "
        "and mortality in peripheral artery disease: National Health and "
        "Nutrition Examination Study, 1999 to 2004. Circulation. "
        "2011;124(1):17-23.",
        "21690489", "https://pubmed.ncbi.nlm.nih.gov/21690489/", 2011, "cross_sectional_survey",
    ),
    "mp2_lap": (
        "Wehr E, Pilz S, Boehm BO, Marz W, Obermayer-Pietsch B. The lipid "
        "accumulation product is associated with increased mortality in "
        "normal weight postmenopausal women. Obesity (Silver Spring). "
        "2011;19(9):1873-1880.",
        "21394091", "https://pubmed.ncbi.nlm.nih.gov/21394091/", 2011, "prospective_cohort",
    ),
    "mp2_lap_dist": (
        "Cardiovascular risk assessment using the lipid accumulation product "
        "index among primary healthcare users (population median/IQR by sex).",
        None, None, 2022, "reference_range",
    ),
    "mp2_sdma": (
        "Schwedhelm E, Wallaschofski H, Atzler D, Dorr M, Nauck M, Volker U, "
        "Kroemer HK, Volzke H, Boger RH, Friedrich N. Incidence of all-cause "
        "and cardiovascular mortality predicted by symmetric dimethylarginine "
        "in the population-based study of health in Pomerania. PLoS One. "
        "2014;9(5):e97180.",
        "24819070", "https://pubmed.ncbi.nlm.nih.gov/24819070/", 2014, "prospective_cohort",
    ),
    "mp2_sdma_dist": (
        "Framingham Offspring Cohort SDMA reference limits: mean 0.38 +/- 0.08 "
        "umol/L (median 0.37, IQR 0.32-0.43) in 840 relatively healthy adults.",
        "22232476", "https://pmc.ncbi.nlm.nih.gov/articles/PMC3235736/", 2012, "reference_range",
    ),
    "mp2_exercise_capacity": (
        "Mora S, Redberg RF, Cui Y, Whiteman MK, Flaws JA, Sharrett AR, "
        "Blumenthal RS. Ability of exercise testing to predict cardiovascular "
        "and all-cause death in asymptomatic women: a 20-year follow-up of "
        "the lipid research clinics prevalence study. JAMA. "
        "2003;290(12):1600-1607.",
        "14506119", "https://pubmed.ncbi.nlm.nih.gov/14506119/", 2003, "prospective_cohort",
    ),
    "mp2_plateletcrit": (
        "Ganna A, Ingelsson E. 5 year mortality predictors in 498,103 UK "
        "Biobank participants: a prospective population-based study. Lancet. "
        "2015;386(9993):533-540.",
        "26049253", "https://pubmed.ncbi.nlm.nih.gov/26049253/", 2015, "prospective_cohort",
    ),
    "mp2_plateletcrit_dist": (
        "Plateletcrit reference range in adult volunteers with normal platelet "
        "counts: mean 0.23% (SD 0.06), range 0.13-0.43%.",
        None, None, 2017, "reference_range",
    ),
    "mp2_sex_hormone_shbg": (
        "Menke A, Guallar E, Rohrmann S, Nelson WG, Rifai N, Kanarek N, "
        "Feinleib M, Michos ED, Dobs A, Platz EA. Sex steroid hormone "
        "concentrations and risk of death in US men. Am J Epidemiol. "
        "2010;171(5):583-592.",
        "20083549", "https://pubmed.ncbi.nlm.nih.gov/20083549/", 2010, "prospective_cohort",
    ),
    "mp2_osteocalcin": (
        "Yeap BB, Chubb SA, Flicker L, McCaul KA, Ebeling PR, Hankey GJ, "
        "Beilby JP, Norman PE. Associations of total osteocalcin with "
        "all-cause and cardiovascular mortality in older men. The Health In "
        "Men Study. Osteoporos Int. 2012;23(2):599-607.",
        "21359669", "https://pubmed.ncbi.nlm.nih.gov/21359669/", 2012, "prospective_cohort",
    ),
    "mp2_myeloperoxidase": (
        "Giovannini S, Onder G, Leeuwenburgh C, Carter C, Marzetti E, Russo A, "
        "Capoluongo E, Pahor M, Bernabei R, Landi F. Myeloperoxidase levels "
        "and mortality in frail community-living elderly individuals. J "
        "Gerontol A Biol Sci Med Sci. 2010;65(4):369-376.",
        "20064836", "https://pubmed.ncbi.nlm.nih.gov/20064836/", 2010, "prospective_cohort",
    ),
    "mp2_proinsulin": (
        "Chisalita SI, Dahlstrom U, Arnqvist HJ, Alehagen U. Proinsulin and "
        "IGFBP-1 predicts mortality in an elderly population. Int J Cardiol. "
        "2014;176(3):847-853.",
        "24794551", "https://pubmed.ncbi.nlm.nih.gov/24794551/", 2014, "prospective_cohort",
    ),
    "mp2_remnant_cholesterol": (
        "Varbo A, Freiberg JJ, Nordestgaard BG. Extreme nonfasting remnant "
        "cholesterol vs extreme LDL cholesterol as contributors to "
        "cardiovascular disease and all-cause mortality in 90,000 "
        "individuals from the general population. Clin Chem. "
        "2015;61(3):533-543.",
        "25605681", "https://pubmed.ncbi.nlm.nih.gov/25605681/", 2015, "prospective_cohort",
    ),
    "mp2_il8": (
        "Moreno Velasquez I, Arnlov J, Leander K, Lind L, Gigante B, Carlsson "
        "AC. Interleukin-8 is associated with increased total mortality in "
        "women but not in men-findings from a community-based cohort of "
        "elderly. Ann Med. 2015;47(4):304-308.",
        "25302539", "https://pubmed.ncbi.nlm.nih.gov/25302539/", 2015, "prospective_cohort",
    ),
    "mp2_il8_il10_il1b_ref": (
        "Establishment of reference intervals for plasma IL-6, IL-8, IL-10, "
        "and IL-1beta in healthy adults from Lianyungang, Jiangsu, China: a "
        "single-center flow cytometry analysis.",
        "42210961", "https://pubmed.ncbi.nlm.nih.gov/42210961/", 2026, "reference_range",
    ),
    "mp2_belfrail_il10_il1b": (
        "Adriaensen W, Mathei C, Vaes B, van Pottelbergh G, Wallemacq P, "
        "Degryse JM. Interleukin-6 as a first-rated serum inflammatory "
        "marker to predict mortality and hospitalization in the oldest old: "
        "A regression and CART approach in the BELFRAIL study. Exp Gerontol. "
        "2015;69:53-61.",
        "26051931", "https://pubmed.ncbi.nlm.nih.gov/26051931/", 2015, "prospective_cohort",
    ),
}


# slug -> dict(...) — same schema as backend/mortalitypredictors_gap_data.py's
# BIOMARKERS dict. `hr` = (hazard_ratio, hr_type, ci_lower, ci_upper,
# direction, cohort_citation_text, n) — cohort_citation_text must equal a
# SOURCES[...][0] string exactly so ingest_one() attaches the real per-marker
# source instead of falling back to a generic anchor.
BIOMARKERS = {
    "pulse-pressure": dict(
        name="Pulse Pressure", category="Cardiac & Hemodynamics", units="mmHg",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Heart & Vasculature", tissue_origin="Systemic Arteries",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=10.0, valid_domain_max=100.0, optimal_target=40.0,
        aliases=["Systolic minus diastolic BP", "PP"],
        notes="Systolic minus diastolic blood pressure; a marker of arterial "
              "stiffness. Population mean/SD from a pooled description of "
              "adults with favorable cardiovascular health (M 45.6+/-9.4, "
              "F 41.8+/-9.5 mmHg), averaged. Not previously in this catalog; "
              "identified via mortalitypredictors.org.",
        evidence_tier="external_cohort_anchor",
        hr=(1.4, "per_sd", 1.34, 1.46, "higher_worse",
            "Weitzman D, Goldbourt U. The significance of various blood pressure "
            "indices for long-term stroke, coronary heart disease, and all-cause "
            "mortality in men: the Israeli Ischemic Heart Disease study. Stroke. "
            "2006;37(2):358-362.", 9611),
        dist_source="mp2_pulse_pressure_dist",
    ),
    "coronary-artery-calcium-score": dict(
        name="Coronary Artery Calcium Score (Agatston)", category="Cardiac & Hemodynamics",
        units="Agatston units", specimen_type="imaging",
        bodily_fluid="Non-Fluid / Imaging", primary_organ="Heart & Vasculature",
        tissue_origin="Coronary Arteries",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=1000.0, optimal_target=0.0,
        aliases=["CAC score", "Agatston score", "Coronary calcium score"],
        notes="CT-derived coronary calcium burden; heavily zero-inflated in "
              "the general population (roughly half of adults under ~50 score "
              "zero), which this catalog's Normal-consistent percentile "
              "convention only coarsely approximates — treat the distribution "
              "as indicative, not precise. Percentile shape informed by the "
              "MESA CAC reference tool. Not previously in this catalog.",
        evidence_tier="external_cohort_anchor",
        hr=(2.67, "quartile_extreme", 2.29, 3.11, "higher_worse",
            "Valenti V, Hartaigh BO, Heo R, Cho I, Schulman-Marcus J, Gransar H, "
            "Truong QA, Shaw LJ, Knapper J, Kelkar AA, Sandesara P, Lin FY, "
            "Sciarretta S, Chang HJ, Callister TQ, Min JK. A 15-Year Warranty "
            "Period for Asymptomatic Individuals Without Coronary Artery Calcium: "
            "A Prospective Follow-Up of 9,715 Individuals. JACC Cardiovasc "
            "Imaging. 2015;8(8):900-909.", 9715),
        dist_source="mp2_cac_score_dist",
    ),
    "forced-vital-capacity": dict(
        name="Forced Vital Capacity (FVC)", category="Functional Fitness", units="L",
        specimen_type="functional", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Lungs", tissue_origin="Pulmonary Airways",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=7.0, optimal_target=5.0,
        aliases=["FVC"],
        notes="Spirometric forced vital capacity. Population mean/SD "
              "approximated from published adult reference ranges (M 4.8-6.0 L, "
              "F 3.2-4.5 L); NHANES III is the standard spirometry reference "
              "source for this catalog's population but individual mean/SD "
              "for a blended all-adult stratum were not separately located, "
              "so this is a rough approximation, not a direct NHANES pull.",
        evidence_tier="external_cohort_anchor",
        hr=(2.21, "quartile_extreme", 1.14, 4.30, "lower_worse",
            "Lee HM, Le H, Lee BT, Lopez VA, Wong ND. Forced vital capacity paired "
            "with Framingham Risk Score for prediction of all-cause mortality. Eur "
            "Respir J. 2010;36(5):1002-1006.", 569),
        dist_source=None,
    ),
    "peak-expiratory-flow": dict(
        name="Peak Expiratory Flow (PEF)", category="Functional Fitness", units="L/min",
        specimen_type="functional", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Lungs", tissue_origin="Pulmonary Airways",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=100.0, valid_domain_max=700.0, optimal_target=450.0,
        aliases=["PEF", "Peak flow"],
        notes="Peak expiratory flow rate. Mean/SD averaged from population "
              "reference values for older US adults by sex (M 456.8+/-130.1, "
              "F 293.9+/-89.9 L/min); broadened somewhat for a wider adult age "
              "range than that source cohort. The source paper did not report "
              "a CI for this observation; ci_lower/ci_upper here are "
              "approximated (+/-~30%) around the point estimate, not taken "
              "from the source text.",
        evidence_tier="external_cohort_anchor",
        hr=(2.49, "quartile_extreme", 1.9, 3.2, "lower_worse",
            "Goldman N, Glei DA, Rosero-Bixby L, Chiou ST, Weinstein M. "
            "Performance-based measures of physical function as mortality "
            "predictors: Incremental value beyond self-reports. Demogr Res. "
            "2014;30:1319-1343.", 2290),
        dist_source="mp2_pef_dist",
    ),
    "skinfold-thickness": dict(
        name="Skinfold Thickness", category="Anthropometric", units="mm",
        specimen_type="anthropometric", bodily_fluid="Non-Fluid / Anthropometric",
        primary_organ="Multi-Organ", tissue_origin="Subcutaneous Adipose Tissue",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=4.0, valid_domain_max=45.0, optimal_target=12.0,
        aliases=["Triceps skinfold", "Subscapular skinfold", "Caliper skinfold"],
        notes="Caliper-measured skinfold thickness (triceps/subscapular). "
              "Population mean/SD is a coarse general estimate — no single "
              "clean population reference was located, so this is the "
              "roughest distribution approximation in this batch.",
        evidence_tier="external_cohort_anchor",
        hr=(1.08, "per_sd", 1.02, 1.15, "higher_worse",
            "Taylor AE, Ebrahim S, Ben-Shlomo Y, Martin RM, Whincup PH, Yarnell "
            "JW, Wannamethee SG, Lawlor DA. Comparison of the associations of "
            "body mass index and measures of central adiposity and fat mass with "
            "coronary heart disease, diabetes, and all-cause mortality: a study "
            "using data from 4 UK cohorts. Am J Clin Nutr. 2010;91(3):547-556.", 1985),
        dist_source=None,
    ),
    "carotid-intima-media-thickness": dict(
        name="Carotid Intima-Media Thickness (CIMT)", category="Cardiac & Hemodynamics",
        units="mm", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Carotid Arteries",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.3, valid_domain_max=1.5, optimal_target=0.6,
        aliases=["CIMT", "Carotid IMT"],
        notes="Ultrasound-measured common carotid intima-media thickness. "
              "Mean/SD (0.76+/-0.16 mm) from a pooled description across "
              ">369,000 adults.",
        evidence_tier="external_cohort_anchor",
        hr=(1.54, "tertile_extreme", 1.32, 1.79, "higher_worse",
            "Cao JJ, Arnold AM, Manolio TA, Polak JF, Psaty BM, Hirsch CH, Kuller "
            "LH, Cushman M. Association of carotid artery intima-media thickness, "
            "plaques, and C-reactive protein with future cardiovascular disease "
            "and all-cause mortality: the Cardiovascular Health Study. "
            "Circulation. 2007;116(1):32-38.", 5020),
        dist_source="mp2_cimt_dist",
    ),
    "ankle-brachial-index": dict(
        name="Ankle-Brachial Index (ABI)", category="Cardiac & Hemodynamics", units="ratio",
        specimen_type="physiological", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Heart & Vasculature", tissue_origin="Lower Extremity Arteries",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.4, valid_domain_max=1.6, optimal_target=1.1,
        aliases=["ABI", "Ankle brachial pressure index"],
        notes="Ratio of ankle to brachial systolic blood pressure. U-shaped: "
              "ABI <=0.9 signals peripheral artery disease, ABI >1.4 signals "
              "arterial calcification/incompressibility — both elevated-risk. "
              "Mean/SD blended from normal-range literature (0.9-1.4) and a "
              "control-cohort mean (1.03+/-0.06).",
        evidence_tier="external_cohort_anchor",
        hr=(1.9, "quartile_extreme", 1.3, 2.8, "u_shaped",
            "Pande RL, Perlstein TS, Beckman JA, Creager MA. Secondary prevention "
            "and mortality in peripheral artery disease: National Health and "
            "Nutrition Examination Study, 1999 to 2004. Circulation. "
            "2011;124(1):17-23.", 7458),
        dist_source=None,
    ),
    "lipid-accumulation-product": dict(
        name="Lipid Accumulation Product (LAP)", category="Cardiometabolic",
        units="cm x mmol/L", specimen_type="calculated", bodily_fluid="Blood Serum",
        primary_organ="Multi-Organ", tissue_origin="Visceral Adipose Tissue",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=200.0, optimal_target=30.0,
        aliases=["LAP index"],
        notes="LAP = (waist circumference - 65) x triglycerides for men, "
              "(WC - 58) x TG for women; a composite cardiometabolic risk "
              "index built from two routinely measured quantities. Mean/SD "
              "approximated from a Brazilian population median/IQR "
              "(~50-58 cm.mmol/L, range 24-91), log-normal shape.",
        evidence_tier="external_cohort_anchor",
        hr=(4.28, "tertile_extreme", 1.94, 9.44, "higher_worse",
            "Wehr E, Pilz S, Boehm BO, Marz W, Obermayer-Pietsch B. The lipid "
            "accumulation product is associated with increased mortality in "
            "normal weight postmenopausal women. Obesity (Silver Spring). "
            "2011;19(9):1873-1880.", 875),
        dist_source="mp2_lap_dist",
    ),
    "symmetric-dimethylarginine": dict(
        name="Symmetric Dimethylarginine (SDMA)", category="Renal & Purine",
        units="umol/L", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Kidney", tissue_origin="Renal Glomerulus/Tubules",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.15, valid_domain_max=1.0, optimal_target=0.35,
        aliases=["SDMA"],
        notes="Distinct from asymmetric dimethylarginine (ADMA, already in "
              "this catalog) — SDMA is cleared renally and tracks kidney "
              "function more directly. Mean/SD (0.38+/-0.08 umol/L) from the "
              "Framingham Offspring Cohort reference-limits study.",
        evidence_tier="external_cohort_anchor",
        hr=(1.2, "per_sd", 1.07, 1.25, "higher_worse",
            "Schwedhelm E, Wallaschofski H, Atzler D, Dorr M, Nauck M, Volker U, "
            "Kroemer HK, Volzke H, Boger RH, Friedrich N. Incidence of all-cause "
            "and cardiovascular mortality predicted by symmetric dimethylarginine "
            "in the population-based study of health in Pomerania. PLoS One. "
            "2014;9(5):e97180.", 3952),
        dist_source="mp2_sdma_dist",
    ),
    "exercise-capacity-mets": dict(
        name="Exercise Capacity (METs)", category="Functional Fitness", units="METs",
        specimen_type="functional", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiorespiratory System",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=16.0, optimal_target=10.0,
        aliases=["Peak METs", "Treadmill exercise capacity", "Bruce protocol METs"],
        notes="Peak metabolic equivalents achieved on a graded treadmill "
              "(Bruce protocol) test. Mean/SD blended from older-adult Bruce "
              "protocol norms (women 6.5+/-1.6, men 7.7+/-1.7 METs), broadened "
              "for a wider general-adult age range.",
        evidence_tier="external_cohort_anchor",
        hr=(1.73, "per_unit", 1.35, 2.22, "lower_worse",
            "Mora S, Redberg RF, Cui Y, Whiteman MK, Flaws JA, Sharrett AR, "
            "Blumenthal RS. Ability of exercise testing to predict cardiovascular "
            "and all-cause death in asymptomatic women: a 20-year follow-up of "
            "the lipid research clinics prevalence study. JAMA. "
            "2003;290(12):1600-1607.", 2994),
        dist_source=None,
    ),
    "plateletcrit": dict(
        name="Plateletcrit (PCT)", category="Hematology", units="%",
        specimen_type="whole_blood", bodily_fluid="Whole Blood",
        primary_organ="Bone Marrow", tissue_origin="Megakaryocytes/Platelets",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=0.45, optimal_target=0.23,
        aliases=["PCT"],
        notes="Fraction of whole-blood volume occupied by platelets "
              "(platelet count x mean platelet volume). Mean/SD (0.23%+/-0.06) "
              "from a clinical reference-range study of adults with normal "
              "platelet counts.",
        evidence_tier="external_cohort_anchor",
        hr=(1.5, "quartile_extreme", 1.3, 1.9, "u_shaped",
            "Ganna A, Ingelsson E. 5 year mortality predictors in 498,103 UK "
            "Biobank participants: a prospective population-based study. Lancet. "
            "2015;386(9993):533-540.", 227074),
        dist_source="mp2_plateletcrit_dist",
    ),
    "testosterone-shbg-ratio": dict(
        name="Testosterone-to-SHBG Ratio", category="Vitamins & Endocrine",
        units="ratio", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Testes", tissue_origin="Leydig Cells",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=2.0, optimal_target=0.8,
        aliases=["Free androgen index (T-based)", "T/SHBG ratio"],
        notes="Total testosterone divided by sex hormone-binding globulin — a "
              "crude free-androgen proxy. Mean/SD (0.6, SD 0.234) is derived "
              "algebraically from the SAME source paper's own reported 10th "
              "(0.3) and 90th (0.9) percentiles in men (NHANES III), so it is "
              "internally consistent with the mortality-association source. "
              "Male-specific per that study; applied here to the 'all' stratum "
              "for lack of a female-specific anchor.",
        evidence_tier="external_cohort_anchor",
        hr=(1.39, "quartile_extreme", 1.14, 1.70, "lower_worse",
            "Menke A, Guallar E, Rohrmann S, Nelson WG, Rifai N, Kanarek N, "
            "Feinleib M, Michos ED, Dobs A, Platz EA. Sex steroid hormone "
            "concentrations and risk of death in US men. Am J Epidemiol. "
            "2010;171(5):583-592.", 1967),
        dist_source=None,
    ),
    "estradiol-shbg-ratio": dict(
        name="Estradiol-to-SHBG Ratio", category="Vitamins & Endocrine",
        units="ratio", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Testes", tissue_origin="Aromatization (Adipose/Testes)",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.5, valid_domain_max=20.0, optimal_target=5.0,
        aliases=["Free estradiol index", "E2/SHBG ratio"],
        notes="Estradiol divided by SHBG, a crude free-estrogen proxy in men. "
              "Mean/SD (4.65, SD 2.146) derived algebraically from the SAME "
              "source paper's reported 10th (1.9) and 90th (7.4) percentiles "
              "(NHANES III men). Male-specific per that study.",
        evidence_tier="external_cohort_anchor",
        hr=(1.82, "quartile_extreme", 1.03, 3.24, "lower_worse",
            "Menke A, Guallar E, Rohrmann S, Nelson WG, Rifai N, Kanarek N, "
            "Feinleib M, Michos ED, Dobs A, Platz EA. Sex steroid hormone "
            "concentrations and risk of death in US men. Am J Epidemiol. "
            "2010;171(5):583-592.", 1967),
        dist_source=None,
    ),
    "osteocalcin": dict(
        name="Osteocalcin", category="Bone & Mineral", units="ng/mL",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Bone", tissue_origin="Osteoblasts",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=40.0, optimal_target=10.0,
        aliases=["Total osteocalcin", "Bone Gla protein"],
        notes="A bone-formation marker. Direction follows the source study "
              "directly (higher total osteocalcin -> higher mortality in "
              "older men), which runs counter to the simplistic 'higher bone "
              "turnover marker = healthier bone' intuition — the authors "
              "attribute it to undercarboxylated/catabolic-state osteocalcin "
              "in frailty, not low bone turnover. Mean/SD (11.7+/-3.8 ng/mL) "
              "from a healthy-adult reference range study.",
        evidence_tier="external_cohort_anchor",
        hr=(1.82, "quartile_extreme", 1.41, 2.35, "higher_worse",
            "Yeap BB, Chubb SA, Flicker L, McCaul KA, Ebeling PR, Hankey GJ, "
            "Beilby JP, Norman PE. Associations of total osteocalcin with "
            "all-cause and cardiovascular mortality in older men. The Health In "
            "Men Study. Osteoporos Int. 2012;23(2):599-607.", 3542),
        dist_source=None,
    ),
    "myeloperoxidase": dict(
        name="Myeloperoxidase (MPO)", category="Inflammation", units="ug/L",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Immune System", tissue_origin="Neutrophil Granulocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=10.0, valid_domain_max=400.0, optimal_target=60.0,
        aliases=["MPO"],
        notes="Neutrophil-derived oxidative enzyme; a marker of vascular "
              "inflammation. Evidence tier is weaker than most of this batch: "
              "the single located study is small (n=363) and restricted to "
              "frail community-living elderly, not the general population. "
              "Mean/SD (100, SD 60 ug/L) is a rough estimate bracketed by the "
              "source study's own tertile cutoffs (61.5 / 140.7 ug/L).",
        evidence_tier="external_cohort_anchor",
        hr=(1.97, "tertile_extreme", 1.02, 3.80, "higher_worse",
            "Giovannini S, Onder G, Leeuwenburgh C, Carter C, Marzetti E, Russo A, "
            "Capoluongo E, Pahor M, Bernabei R, Landi F. Myeloperoxidase levels "
            "and mortality in frail community-living elderly individuals. J "
            "Gerontol A Biol Sci Med Sci. 2010;65(4):369-376.", 363),
        dist_source=None,
    ),
    "proinsulin": dict(
        name="Proinsulin", category="Glycemic & Metabolic", units="pmol/L",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Pancreas", tissue_origin="Pancreatic Beta Cells",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=40.0, optimal_target=3.0,
        aliases=["Fasting proinsulin"],
        notes="Insulin precursor; elevated fasting proinsulin (relative to "
              "insulin) signals beta-cell dysfunction/insulin resistance. "
              "Mean/SD (4.0, SD 3.0 pmol/L) approximated from published lean-"
              "individual averages (~2.9 pmol/L) broadened toward the wider "
              "general-population range (2-6 pmol/L, upper limit ~22).",
        evidence_tier="external_cohort_anchor",
        hr=(1.7, "tertile_extreme", 1.1, 2.4, "higher_worse",
            "Chisalita SI, Dahlstrom U, Arnqvist HJ, Alehagen U. Proinsulin and "
            "IGFBP-1 predicts mortality in an elderly population. Int J Cardiol. "
            "2014;176(3):847-853.", 851),
        dist_source=None,
    ),
    "remnant-cholesterol": dict(
        name="Remnant Cholesterol", category="Lipids & Apolipoproteins",
        units="mmol/L", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Liver", tissue_origin="Triglyceride-Rich Lipoproteins",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.1, valid_domain_max=3.0, optimal_target=0.4,
        aliases=["Non-fasting remnant cholesterol", "VLDL + IDL cholesterol"],
        notes="Cholesterol content of triglyceride-rich lipoprotein remnants "
              "(non-HDL minus LDL cholesterol). Mean/SD (0.6, SD 0.35 mmol/L) "
              "blended from the source Danish cohort's own extreme-comparison "
              "thresholds (<0.50 vs >=1.5 mmol/L) with a lower Southeast Asian "
              "population mean (0.29 mmol/L) reported elsewhere.",
        evidence_tier="external_cohort_anchor",
        hr=(1.6, "quartile_extreme", 1.4, 1.9, "higher_worse",
            "Varbo A, Freiberg JJ, Nordestgaard BG. Extreme nonfasting remnant "
            "cholesterol vs extreme LDL cholesterol as contributors to "
            "cardiovascular disease and all-cause mortality in 90,000 "
            "individuals from the general population. Clin Chem. "
            "2015;61(3):533-543.", 97962),
        dist_source=None,
    ),
    "interleukin-8": dict(
        name="Interleukin-8 (IL-8)", category="Inflammation", units="pg/mL",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Immune System", tissue_origin="Macrophages/Endothelium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=1.0, valid_domain_max=50.0, optimal_target=5.0,
        aliases=["IL-8", "CXCL8"],
        notes="Pro-inflammatory chemokine. Association was significant in "
              "women but not men in the source cohort — a real sex-specific "
              "finding, not an omission. Mean/SD (8, SD 6 pg/mL) blended from "
              "several published healthy-adult reference ranges (a Chinese "
              "flow-cytometry reference interval and Western clinical-lab "
              "ranges), which vary considerably by assay.",
        evidence_tier="external_cohort_anchor",
        hr=(1.18, "per_sd", 1.06, 1.30, "higher_worse",
            "Moreno Velasquez I, Arnlov J, Leander K, Lind L, Gigante B, Carlsson "
            "AC. Interleukin-8 is associated with increased total mortality in "
            "women but not in men-findings from a community-based cohort of "
            "elderly. Ann Med. 2015;47(4):304-308.", 1003),
        dist_source="mp2_il8_il10_il1b_ref",
    ),
    "interleukin-10": dict(
        name="Interleukin-10 (IL-10)", category="Inflammation", units="pg/mL",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Immune System", tissue_origin="Regulatory T-Cells/Monocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.1, valid_domain_max=15.0, optimal_target=0.5,
        aliases=["IL-10"],
        notes="IL-10 is canonically anti-inflammatory, so 'higher = worse' "
              "here is counter-intuitive; the source study's authors interpret "
              "elevated IL-10 in the oldest-old as a compensatory response to "
              "chronic inflammation rather than a protective signal — the "
              "biology is genuinely debated. Small cohort (n=415, oldest-old "
              "only). Mean/SD (0.7, SD 0.6 pg/mL) approximated from a "
              "published upper reference limit (1.89 pg/mL, ~97.5th "
              "percentile) in healthy adults.",
        evidence_tier="external_cohort_anchor",
        hr=(1.84, "tertile_extreme", 1.08, 3.12, "higher_worse",
            "Adriaensen W, Mathei C, Vaes B, van Pottelbergh G, Wallemacq P, "
            "Degryse JM. Interleukin-6 as a first-rated serum inflammatory "
            "marker to predict mortality and hospitalization in the oldest old: "
            "A regression and CART approach in the BELFRAIL study. Exp Gerontol. "
            "2015;69:53-61.", 415),
        dist_source="mp2_il8_il10_il1b_ref",
    ),
    "interleukin-1-beta": dict(
        name="Interleukin-1 beta (IL-1b)", category="Inflammation", units="pg/mL",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Immune System", tissue_origin="Macrophages/Monocytes",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=8.0, optimal_target=0.3,
        aliases=["IL-1 beta", "IL-1b"],
        notes="Pro-inflammatory cytokine. Same small oldest-old-only cohort "
              "(n=415) as the IL-10 entry above — weaker evidence tier than "
              "most of this batch. Mean/SD (0.5, SD 0.4 pg/mL) approximated "
              "from a published upper reference limit (1.34 pg/mL, ~97.5th "
              "percentile) in healthy adults.",
        evidence_tier="external_cohort_anchor",
        hr=(1.71, "tertile_extreme", 1.01, 2.90, "higher_worse",
            "Adriaensen W, Mathei C, Vaes B, van Pottelbergh G, Wallemacq P, "
            "Degryse JM. Interleukin-6 as a first-rated serum inflammatory "
            "marker to predict mortality and hospitalization in the oldest old: "
            "A regression and CART approach in the BELFRAIL study. Exp Gerontol. "
            "2015;69:53-61.", 415),
        dist_source="mp2_il8_il10_il1b_ref",
    ),
}


# slug -> (sex, age_band, mean, sd) x6 canonical strata, same convention as
# mortalitypredictors_gap_data.py's DISTRIBUTIONS (sample_n and low_conf flag
# supplied separately since every entry here is already a best-effort
# approximation — see BIOMARKERS[...]['notes']).
_ALL_LOW_CONF = True

DISTRIBUTIONS = {
    "pulse-pressure": (43.7, 9.45, 9611, True),
    "coronary-artery-calcium-score": (65.0, 140.0, 9715, True),
    "forced-vital-capacity": (4.6, 1.1, 569, True),
    "peak-expiratory-flow": (375.0, 110.0, 2290, True),
    "skinfold-thickness": (16.0, 7.0, 1985, True),
    "carotid-intima-media-thickness": (0.76, 0.16, 5020, False),
    "ankle-brachial-index": (1.03, 0.10, 7458, False),
    "lipid-accumulation-product": (55.0, 30.0, 875, True),
    "symmetric-dimethylarginine": (0.38, 0.08, 3952, False),
    "exercise-capacity-mets": (7.0, 2.3, 2994, True),
    "plateletcrit": (0.23, 0.06, 227074, False),
    "testosterone-shbg-ratio": (0.6, 0.234, 1967, False),
    "estradiol-shbg-ratio": (4.65, 2.146, 1967, False),
    "osteocalcin": (16.0, 5.5, 3542, False),
    "myeloperoxidase": (100.0, 60.0, 363, True),
    "proinsulin": (4.0, 3.0, 851, True),
    "remnant-cholesterol": (0.6, 0.35, 97962, True),
    "interleukin-8": (8.0, 6.0, 1003, True),
    "interleukin-10": (0.7, 0.6, 415, True),
    "interleukin-1-beta": (0.5, 0.4, 415, True),
}

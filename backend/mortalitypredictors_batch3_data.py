"""
Curated ingestion data for a third batch of MortalityPredictors.org coverage
gaps — 21 biomarkers, identified by re-checking the full MP.org catalog
against the (now 213-biomarker) database after batch 2, excluding
duplicates, CpG probes, raw ECG waveform/interval findings, disease
diagnoses, and composite multi-marker panels.

Same conventions as `mortalitypredictors_batch2_data.py`: every mortality
anchor cites its own specific PMID-verified publication from
mortalitypredictors.org's curated `observations.csv`/`publications.csv`
tables (Europe PMC spot-checked before writing).

Several markers here (vascular/valvular calcification presence, extra-
coronary calcification site counts, diastolic dysfunction grade) are
inherently zero-inflated/ordinal in the general population, which this
catalog's Normal-consistent percentile convention only coarsely
approximates — flagged `is_low_confidence=1` throughout this batch.
"""

SOURCES = {
    "mp3_kim1": (
        "O'Seaghdha CM, Hwang SJ, Larson MG, Meigs JB, Vasan RS, Fox CS. "
        "Analysis of a urinary biomarker panel for incident kidney disease "
        "and clinical outcomes. J Am Soc Nephrol. 2013;24(11):1880-1888.",
        "23990678", "https://pubmed.ncbi.nlm.nih.gov/23990678/", 2013, "prospective_cohort",
    ),
    "mp3_kim1_dist": (
        "Urinary biomarkers of renal injury KIM-1 and NGAL: healthy-adult "
        "reference interval, upper limit ~4.19 ug/L.",
        None, None, 2018, "reference_range",
    ),
    "mp3_ngal": (
        "Daniels LB, Barrett-Connor E, Clopton P, Laughlin GA, Ix JH, Maisel "
        "AS. Plasma neutrophil gelatinase-associated lipocalin is "
        "independently associated with cardiovascular disease and mortality "
        "in community-dwelling older adults: The Rancho Bernardo Study. J "
        "Am Coll Cardiol. 2012;59(12):1101-1109.",
        "22421304", "https://pubmed.ncbi.nlm.nih.gov/22421304/", 2012, "prospective_cohort",
    ),
    "mp3_vertical_jump": (
        "Fujita Y, Nakamura Y, Hiraoka J, Kobayashi K, Sakata K, Nagai M, "
        "Yanagawa H. Physical-strength tests and mortality among visitors "
        "to health-promotion centers in Japan. J Clin Epidemiol. "
        "1995;48(11):1349-1359.",
        "7490598", "https://pubmed.ncbi.nlm.nih.gov/7490598/", 1995, "prospective_cohort",
    ),
    "mp3_lvef": (
        "McDonagh TA, Cunningham AD, Morrison CE, McMurray JJ, Ford I, "
        "Morton JJ, Dargie HJ. Left ventricular dysfunction, natriuretic "
        "peptides, and mortality in an urban population. Heart. "
        "2001;86(1):21-26.",
        "11410555", "https://pubmed.ncbi.nlm.nih.gov/11410555/", 2001, "cross_sectional_survey",
    ),
    "mp3_lvef_dist": (
        "What is a normal left ventricular ejection fraction in healthy "
        "adults? A meta-analysis of population-based echocardiographic "
        "studies (pooled n=10,427). J Cardiovasc Imaging. 2025.",
        "41572417", "https://pubmed.ncbi.nlm.nih.gov/41572417/", 2025, "meta_analysis",
    ),
    "mp3_ctx": (
        "Barasch E, Gottdiener JS, Aurigemma G, Kitzman DW, Han J, Kop WJ, "
        "Tracy RP. The relationship between serum markers of collagen "
        "turnover and cardiovascular outcome in the elderly: the "
        "Cardiovascular Health Study. Circ Heart Fail. 2011;4(6):733-739.",
        "21900186", "https://pubmed.ncbi.nlm.nih.gov/21900186/", 2011, "prospective_cohort",
    ),
    "mp3_muscle_density": (
        "Miljkovic I, Kuipers AL, Cauley JA, Prasad T, Lee CG, Ensrud KE, "
        "Cawthon PM, Hoffman AR, Dam TT, Gordon CL, Zmuda JM. Greater "
        "Skeletal Muscle Fat Infiltration Is Associated With Higher "
        "All-Cause and Cardiovascular Mortality in Older Men. J Gerontol A "
        "Biol Sci Med Sci. 2015;70(9):1133-1140.",
        "25838547", "https://pubmed.ncbi.nlm.nih.gov/25838547/", 2015, "prospective_cohort",
    ),
    "mp3_calf": (
        "Mason C, Craig CL, Katzmarzyk PT. Influence of central and "
        "extremity circumferences on all-cause mortality in men and women. "
        "Obesity (Silver Spring). 2008;16(12):2690-2695.",
        "18927548", "https://pubmed.ncbi.nlm.nih.gov/18927548/", 2008, "prospective_cohort",
    ),
    "mp3_calf_dist": (
        "Calf circumference: cutoff values from the NHANES 1999-2006 "
        "(reference population 18-39y, BMI 18.5-24.9).",
        "33742191", "https://pubmed.ncbi.nlm.nih.gov/33742191/", 2021, "reference_range",
    ),
    "mp3_height": (
        "Ganna A, Ingelsson E. 5 year mortality predictors in 498,103 UK "
        "Biobank participants: a prospective population-based study. Lancet. "
        "2015;386(9993):533-540.",
        "26049253", "https://pubmed.ncbi.nlm.nih.gov/26049253/", 2015, "prospective_cohort",
    ),
    "mp3_height_dist": (
        "CDC/NCHS NHANES body measures: adult standing height (mean by sex, "
        "M 176.4cm / F 162.5cm).",
        None, "https://www.cdc.gov/nchs/data/series/sr_03/sr03_039.pdf", 2021, "reference_range",
    ),
    "mp3_bicarbonate": (
        "Park M, Jung SJ, Yoon S, Yun JM, Yoon HJ. Association between the "
        "markers of metabolic acid load and higher all-cause and "
        "cardiovascular mortality in a general population with preserved "
        "renal function. Hypertens Res. 2015;38(6):433-438.",
        "25762414", "https://pubmed.ncbi.nlm.nih.gov/25762414/", 2015, "prospective_cohort",
    ),
    "mp3_anion_gap": (
        "Ahn SY, Ryu J, Baek SH, Han JW, Lee JH, Ahn S, Kim KI, Chin HJ, Na "
        "KY, Chae DW, Kim KW, Kim S. Serum anion gap is predictive of "
        "mortality in an elderly population. Exp Gerontol. "
        "2014;50:122-127.",
        "24333141", "https://pubmed.ncbi.nlm.nih.gov/24333141/", 2014, "prospective_cohort",
    ),
    "mp3_aact": (
        "Bates CJ, Hamer M, Mishra GD. A study of relationships between "
        "bone-related vitamins and minerals, related risk markers, and "
        "subsequent mortality in older British people: the National Diet "
        "and Nutrition Survey of People Aged 65 Years and Over. Osteoporos "
        "Int. 2012;23(2):457-466.",
        "21380638", "https://pubmed.ncbi.nlm.nih.gov/21380638/", 2012, "prospective_cohort",
    ),
    "mp3_renal_calc": (
        "Rifkin DE, Ix JH, Wassel CL, Criqui MH, Allison MA. Renal artery "
        "calcification and mortality among clinically asymptomatic adults. "
        "J Am Coll Cardiol. 2012;60(12):1079-1085.",
        "22939556", "https://pubmed.ncbi.nlm.nih.gov/22939556/", 2012, "prospective_cohort",
    ),
    "mp3_cardiac_calc": (
        "Zhang Y, Safar ME, Iaria P, Lieber A, Peroz J, Protogerou AD, "
        "Rajzbaum G, Blacher J. Cardiac and arterial calcifications and "
        "all-cause mortality in the elderly: the PROTEGER Study. "
        "Atherosclerosis. 2010;209(1):278-283.",
        "20965506", "https://pubmed.ncbi.nlm.nih.gov/20965506/", 2010, "prospective_cohort",
    ),
    "mp3_aac": (
        "Rodondi N, Taylor BC, Bauer DC, Lui LY, Vogt MT, Fink HA, Browner "
        "WS, Cummings SR, Ensrud KE. Association between aortic "
        "calcification and total and cardiovascular mortality in older "
        "women. J Intern Med. 2007;261(4):383-392.",
        "17305646", "https://pubmed.ncbi.nlm.nih.gov/17305646/", 2007, "prospective_cohort",
    ),
    "mp3_tac": (
        "Santos RD, Rumberger JA, Budoff MJ, Shaw LJ, Orakzai SH, Berman D, "
        "Raggi P, Blumenthal RS, Nasir K. Thoracic aorta calcification "
        "detected by electron beam tomography predicts all-cause mortality. "
        "Atherosclerosis. 2010;209(1):131-135.",
        "19782363", "https://pubmed.ncbi.nlm.nih.gov/19782363/", 2010, "prospective_cohort",
    ),
    "mp3_thiols": (
        "Schottker B, Saum KU, Jansen EH, Boffetta P, Trichopoulou A, "
        "Holleczek B, Dieffenbach AK, Brenner H. Oxidative stress markers "
        "and all-cause mortality at older age: a population-based cohort "
        "study. J Gerontol A Biol Sci Med Sci. 2015;70(4):518-524.",
        "25070660", "https://pubmed.ncbi.nlm.nih.gov/25070660/", 2015, "prospective_cohort",
    ),
    "mp3_thiols_dist": (
        "Total plasma thiols (native + disulfide) in healthy controls: "
        "462.0 +/- 58.7 umol/L (spectrophotometric assay).",
        None, None, 2019, "reference_range",
    ),
    "mp3_pericardial_fat": (
        "Larsen BA, Laughlin GA, Saad SD, Barrett-Connor E, Allison MA, "
        "Wassel CL. Pericardial fat is associated with all-cause mortality "
        "but not incident CVD: the Rancho Bernardo Study. Atherosclerosis. "
        "2015;239(2):470-475.",
        "25702617", "https://pubmed.ncbi.nlm.nih.gov/25702617/", 2015, "prospective_cohort",
    ),
    "mp3_extracoronary_calc": (
        "Tison GH, Guo M, Blaha MJ, McClelland RL, Allison MA, Szklo M, "
        "Wong ND, Blumenthal RS, Budoff MJ, Nasir K. Multisite extracoronary "
        "calcification indicates increased risk of coronary heart disease "
        "and all-cause mortality: The Multi-Ethnic Study of Atherosclerosis. "
        "J Cardiovasc Comput Tomogr. 2015;9(5):406-414.",
        "26043963", "https://pubmed.ncbi.nlm.nih.gov/26043963/", 2015, "prospective_cohort",
    ),
    "mp3_gls": (
        "Stanton T, Leano R, Marwick TH. Prediction of all-cause mortality "
        "from global longitudinal speckle strain: comparison with ejection "
        "fraction and wall motion scoring. Circ Cardiovasc Imaging. "
        "2009;2(5):356-364.",
        "19808623", "https://pubmed.ncbi.nlm.nih.gov/19808623/", 2009, "prospective_cohort",
    ),
    "mp3_gls_dist": (
        "Reference range of left ventricular global longitudinal strain in "
        "1,329 healthy adults: -24% to -16% (approx mean -20%).",
        None, None, 2019, "reference_range",
    ),
    "mp3_ivs": (
        "Kardys I, Deckers JW, Stricker BH, Vletter WB, Hofman A, Witteman "
        "JC. Echocardiographic parameters and all-cause mortality: the "
        "Rotterdam Study. Int J Cardiol. 2009;133(2):198-204.",
        "18313776", "https://pubmed.ncbi.nlm.nih.gov/18313776/", 2009, "prospective_cohort",
    ),
    "mp3_diastolic_dysfunction": (
        "Desai CS, Colangelo LA, Liu K, Jacobs DR Jr, Cook NL, Lloyd-Jones "
        "DM, Ogunyankin KO. Prevalence, prospective risk markers, and "
        "prognosis associated with the presence of left ventricular "
        "diastolic dysfunction in young adults: the coronary artery risk "
        "development in young adults study. Am J Epidemiol. "
        "2013;177(4):20-29.",
        "23211639", "https://pubmed.ncbi.nlm.nih.gov/23211639/", 2013, "prospective_cohort",
    ),
}


BIOMARKERS = {
    "kidney-injury-molecule-1": dict(
        name="Kidney Injury Molecule-1 (KIM-1)", category="Renal & Purine", units="ng/mL",
        specimen_type="urine", bodily_fluid="Urine", primary_organ="Kidney",
        tissue_origin="Proximal Tubule Epithelium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.01, valid_domain_max=10.0, optimal_target=0.1,
        aliases=["KIM-1", "HAVCR1"],
        notes="Urinary proximal-tubule injury marker. Mean/SD is a rough "
              "approximation bracketed by a healthy-adult reference interval "
              "upper limit (~4.19 ug/L, ~equiv ng/mL).",
        evidence_tier="external_cohort_anchor",
        hr=(1.17, "per_sd", 1.04, 1.31, "higher_worse",
            "O'Seaghdha CM, Hwang SJ, Larson MG, Meigs JB, Vasan RS, Fox CS. "
            "Analysis of a urinary biomarker panel for incident kidney disease "
            "and clinical outcomes. J Am Soc Nephrol. 2013;24(11):1880-1888.", 2948),
        dist_source="mp3_kim1_dist",
    ),
    "ngal": dict(
        name="Neutrophil Gelatinase-Associated Lipocalin (NGAL)", category="Renal & Purine",
        units="ng/mL", specimen_type="serum", bodily_fluid="Blood Plasma",
        primary_organ="Kidney", tissue_origin="Renal Tubule Epithelium/Neutrophils",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=20.0, valid_domain_max=400.0, optimal_target=70.0,
        aliases=["NGAL", "Lipocalin-2"],
        notes="Plasma NGAL, a marker of both renal tubular stress and "
              "neutrophil activation. Mean/SD (104.0+/-34.7 ng/mL) from a "
              "healthy-adult reference study.",
        evidence_tier="external_cohort_anchor",
        hr=(1.19, "per_sd", 1.07, 1.32, "higher_worse",
            "Daniels LB, Barrett-Connor E, Clopton P, Laughlin GA, Ix JH, Maisel "
            "AS. Plasma neutrophil gelatinase-associated lipocalin is "
            "independently associated with cardiovascular disease and mortality "
            "in community-dwelling older adults: The Rancho Bernardo Study. J "
            "Am Coll Cardiol. 2012;59(12):1101-1109.", 1393),
        dist_source=None,
    ),
    "vertical-jump": dict(
        name="Vertical Jump Height", category="Functional Fitness", units="cm",
        specimen_type="functional", bodily_fluid="Non-Fluid / Functional",
        primary_organ="Skeletal Muscle", tissue_origin="Lower-Extremity Musculature",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=70.0, optimal_target=45.0,
        aliases=["Vertical leap"],
        notes="A power/strength functional-fitness test. Mean/SD is "
              "approximated from published general-adult norms (M ~45cm, "
              "F ~30cm), blended. The source study's CI was not reported for "
              "this observation; ci_lower/ci_upper here are approximated "
              "(+/-~25% around the point estimate).",
        evidence_tier="external_cohort_anchor",
        hr=(2.37, "quartile_extreme", 1.8, 3.1, "lower_worse",
            "Fujita Y, Nakamura Y, Hiraoka J, Kobayashi K, Sakata K, Nagai M, "
            "Yanagawa H. Physical-strength tests and mortality among visitors "
            "to health-promotion centers in Japan. J Clin Epidemiol. "
            "1995;48(11):1349-1359.", 3117),
        dist_source=None,
    ),
    "left-ventricular-ejection-fraction": dict(
        name="Left Ventricular Ejection Fraction (LVEF)", category="Cardiac & Hemodynamics",
        units="%", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Left Ventricle",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=15.0, valid_domain_max=80.0, optimal_target=60.0,
        aliases=["LVEF", "Ejection fraction"],
        notes="Echocardiographic left ventricular ejection fraction. Mean/SD "
              "(62.8+/-5.4%) from a 2025 meta-analysis pooling 10,427 healthy "
              "community-based adults.",
        evidence_tier="external_cohort_anchor",
        hr=(6.0, "quartile_extreme", 2.9, 12.0, "lower_worse",
            "McDonagh TA, Cunningham AD, Morrison CE, McMurray JJ, Ford I, "
            "Morton JJ, Dargie HJ. Left ventricular dysfunction, natriuretic "
            "peptides, and mortality in an urban population. Heart. "
            "2001;86(1):21-26.", 1252),
        dist_source="mp3_lvef_dist",
    ),
    "ctx-bone-resorption": dict(
        name="C-Terminal Telopeptide of Type I Collagen (CTX)", category="Bone & Mineral",
        units="ng/mL", specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Bone", tissue_origin="Osteoclasts",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.05, valid_domain_max=1.0, optimal_target=0.15,
        aliases=["CTX", "Beta-CrossLaps", "beta-CTX", "CTx"],
        notes="A bone-resorption marker (distinct from osteocalcin, a "
              "formation marker, already in this catalog). Mean/SD "
              "approximated from published sex-specific reference ranges "
              "(M 0.100-0.378, F 0.112-0.210 ng/mL).",
        evidence_tier="external_cohort_anchor",
        hr=(1.7, "tertile_extreme", 1.4, 2.0, "higher_worse",
            "Barasch E, Gottdiener JS, Aurigemma G, Kitzman DW, Han J, Kop WJ, "
            "Tracy RP. The relationship between serum markers of collagen "
            "turnover and cardiovascular outcome in the elderly: the "
            "Cardiovascular Health Study. Circ Heart Fail. 2011;4(6):733-739.", 880),
        dist_source=None,
    ),
    "skeletal-muscle-fat-infiltration": dict(
        name="Skeletal Muscle Fat Infiltration", category="Anthropometric", units="index",
        specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Skeletal Muscle", tissue_origin="Intramuscular Adipose Tissue",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=100.0, optimal_target=15.0,
        aliases=["Myosteatosis", "Intramuscular fat"],
        notes="CT-derived intramuscular/intermuscular fat infiltration (the "
              "source paper's 'muscle density' variable tracks fat "
              "infiltration, not lean radiodensity — named for clarity here "
              "to avoid the ambiguity). Mean/SD is a coarse arbitrary-index "
              "approximation; no clean population reference range located.",
        evidence_tier="external_cohort_anchor",
        hr=(1.18, "per_sd", 1.06, 1.33, "higher_worse",
            "Miljkovic I, Kuipers AL, Cauley JA, Prasad T, Lee CG, Ensrud KE, "
            "Cawthon PM, Hoffman AR, Dam TT, Gordon CL, Zmuda JM. Greater "
            "Skeletal Muscle Fat Infiltration Is Associated With Higher "
            "All-Cause and Cardiovascular Mortality in Older Men. J Gerontol A "
            "Biol Sci Med Sci. 2015;70(9):1133-1140.", 1063),
        dist_source=None,
    ),
    "calf-circumference": dict(
        name="Calf Circumference", category="Anthropometric", units="cm",
        specimen_type="anthropometric", bodily_fluid="Non-Fluid / Anthropometric",
        primary_organ="Skeletal Muscle", tissue_origin="Gastrocnemius/Soleus",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=25.0, valid_domain_max=50.0, optimal_target=38.0,
        aliases=["Calf girth"],
        notes="A simple sarcopenia-screening anthropometric measure. Mean/SD "
              "approximated from NHANES 1999-2006 reference-population cutoff "
              "spacing (moderately-low cutoffs ~1 SD below the mean: 34cm M / "
              "33cm F).",
        evidence_tier="external_cohort_anchor",
        hr=(0.86, "per_sd", 0.76, 0.96, "lower_worse",
            "Mason C, Craig CL, Katzmarzyk PT. Influence of central and "
            "extremity circumferences on all-cause mortality in men and women. "
            "Obesity (Silver Spring). 2008;16(12):2690-2695.", 5012),
        dist_source="mp3_calf_dist",
    ),
    "standing-height": dict(
        name="Standing Height", category="Anthropometric", units="cm",
        specimen_type="anthropometric", bodily_fluid="Non-Fluid / Anthropometric",
        primary_organ="Multi-Organ", tissue_origin="Skeletal System",
        directionality="u_shaped", causal_status="OBSERVATIONAL",
        valid_domain_min=140.0, valid_domain_max=210.0, optimal_target=172.0,
        aliases=["Adult height"],
        notes="Modeled u_shaped: very short stature is associated with "
              "frailty/undernutrition risk, while the cited UK Biobank "
              "bin comparison found the tallest bin at higher risk than a "
              "short/mid bin too (an unusual finding worth flagging — most "
              "height-mortality literature finds shorter stature, not "
              "taller, the higher-risk direction; this may reflect the "
              "source study's coarse, arbitrary bin construction rather than "
              "a robust dose-response). Mean/SD (M 176.4cm/F 162.5cm, "
              "blended ~169cm) from CDC/NCHS NHANES body measures.",
        evidence_tier="external_cohort_anchor",
        hr=(2.2, "quartile_extreme", 1.1, 4.3, "u_shaped",
            "Ganna A, Ingelsson E. 5 year mortality predictors in 498,103 UK "
            "Biobank participants: a prospective population-based study. Lancet. "
            "2015;386(9993):533-540.", 195273),
        dist_source="mp3_height_dist",
    ),
    "bicarbonate": dict(
        name="Serum Bicarbonate", category="Electrolytes & Minerals", units="mEq/L",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Kidney", tissue_origin="Renal Tubules (Acid-Base Handling)",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=15.0, valid_domain_max=35.0, optimal_target=26.0,
        aliases=["HCO3", "Serum CO2", "Total CO2"],
        notes="Lower serum bicarbonate reflects chronic low-grade metabolic "
              "acidosis. Mean/SD (25.5+/-2.0 mEq/L) from standard clinical "
              "reference-range literature (22-29 mEq/L typical range).",
        evidence_tier="external_cohort_anchor",
        hr=(1.46, "quartile_extreme", 1.068, 1.995, "lower_worse",
            "Park M, Jung SJ, Yoon S, Yun JM, Yoon HJ. Association between the "
            "markers of metabolic acid load and higher all-cause and "
            "cardiovascular mortality in a general population with preserved "
            "renal function. Hypertens Res. 2015;38(6):433-438.", 31590),
        dist_source=None,
    ),
    "anion-gap-albumin-adjusted": dict(
        name="Albumin-Adjusted Anion Gap", category="Electrolytes & Minerals", units="mEq/L",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Kidney", tissue_origin="Renal Tubules (Acid-Base Handling)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=2.0, valid_domain_max=20.0, optimal_target=8.0,
        aliases=["SAAG", "Corrected anion gap"],
        notes="Anion gap corrected for serum albumin (Corrected AG = "
              "Measured AG + 2.5 x (4.0 - albumin g/dL)). Mean/SD (9, SD 3 "
              "mEq/L) blended from a general-population uncorrected mean "
              "(~7.2) and a higher critically-ill corrected mean (14.1) as "
              "rough bounds.",
        evidence_tier="external_cohort_anchor",
        hr=(1.77, "quartile_extreme", 1.24, 2.52, "higher_worse",
            "Ahn SY, Ryu J, Baek SH, Han JW, Lee JH, Ahn S, Kim KI, Chin HJ, Na "
            "KY, Chae DW, Kim KW, Kim S. Serum anion gap is predictive of "
            "mortality in an elderly population. Exp Gerontol. "
            "2014;50:122-127.", 862),
        dist_source=None,
    ),
    "alpha-1-antichymotrypsin": dict(
        name="Alpha-1-Antichymotrypsin (AACT)", category="Inflammation", units="mg/dL",
        specimen_type="serum", bodily_fluid="Blood Serum",
        primary_organ="Liver", tissue_origin="Hepatocytes (Acute-Phase Protein)",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=50.0, valid_domain_max=350.0, optimal_target=130.0,
        aliases=["AACT", "SERPINA3"],
        notes="A hepatic acute-phase protein, elevated with chronic "
              "inflammation. Mean/SD (155, SD 30 mg/dL) approximated from a "
              "cited normal-range midpoint (~110-205 mg/dL).",
        evidence_tier="external_cohort_anchor",
        hr=(1.21, "per_sd", 1.11, 1.33, "higher_worse",
            "Bates CJ, Hamer M, Mishra GD. A study of relationships between "
            "bone-related vitamins and minerals, related risk markers, and "
            "subsequent mortality in older British people: the National Diet "
            "and Nutrition Survey of People Aged 65 Years and Over. Osteoporos "
            "Int. 2012;23(2):457-466.", 538),
        dist_source=None,
    ),
    "renal-artery-calcification": dict(
        name="Renal Artery Calcification", category="Renal & Purine", units="severity score",
        specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Kidney", tissue_origin="Renal Artery",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=10.0, optimal_target=0.0,
        aliases=["RAC"],
        notes="CT-detected calcification of the renal arteries. Modeled as "
              "an arbitrary 0-10 severity score (the source study reports "
              "presence/absence, not a graded score) since this catalog has "
              "no zero-inflated distribution primitive — a coarse "
              "approximation, like the coronary artery calcium score added "
              "in the previous batch.",
        evidence_tier="external_cohort_anchor",
        hr=(1.63, "quartile_extreme", 1.17, 2.29, "higher_worse",
            "Rifkin DE, Ix JH, Wassel CL, Criqui MH, Allison MA. Renal artery "
            "calcification and mortality among clinically asymptomatic adults. "
            "J Am Coll Cardiol. 2012;60(12):1079-1085.", 4450),
        dist_source=None,
    ),
    "cardiac-calcification": dict(
        name="Cardiac (Valvular/Annular) Calcification", category="Cardiac & Hemodynamics",
        units="severity score", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Cardiac Valves/Annulus",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=10.0, optimal_target=0.0,
        aliases=["Valvular calcification", "Mitral annular calcification"],
        notes="Distinct from the coronary artery calcium score already in "
              "this catalog — this covers valvular/annular calcification. "
              "Modeled as an arbitrary 0-10 severity score (coarse "
              "approximation, source reports high-vs-low categories only).",
        evidence_tier="external_cohort_anchor",
        hr=(1.92, "quartile_extreme", 1.28, 2.87, "higher_worse",
            "Zhang Y, Safar ME, Iaria P, Lieber A, Peroz J, Protogerou AD, "
            "Rajzbaum G, Blacher J. Cardiac and arterial calcifications and "
            "all-cause mortality in the elderly: the PROTEGER Study. "
            "Atherosclerosis. 2010;209(1):278-283.", 331),
        dist_source=None,
    ),
    "abdominal-aortic-calcification": dict(
        name="Abdominal Aortic Calcification (AAC)", category="Cardiac & Hemodynamics",
        units="severity score", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Abdominal Aorta",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=10.0, optimal_target=0.0,
        aliases=["AAC"],
        notes="Radiographic abdominal aortic calcification (Kauppila score "
              "family). Modeled as an arbitrary 0-10 severity score (coarse "
              "approximation, source reports presence/absence).",
        evidence_tier="external_cohort_anchor",
        hr=(1.37, "quartile_extreme", 1.15, 1.64, "higher_worse",
            "Rodondi N, Taylor BC, Bauer DC, Lui LY, Vogt MT, Fink HA, Browner "
            "WS, Cummings SR, Ensrud KE. Association between aortic "
            "calcification and total and cardiovascular mortality in older "
            "women. J Intern Med. 2007;261(4):383-392.", 2056),
        dist_source=None,
    ),
    "thoracic-aorta-calcification": dict(
        name="Thoracic Aorta Calcification (TAC)", category="Cardiac & Hemodynamics",
        units="severity score", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Thoracic Aorta",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=10.0, optimal_target=0.0,
        aliases=["TAC"],
        notes="CT-detected thoracic aortic calcification, distinct from "
              "abdominal aortic and coronary calcification already in this "
              "catalog. Modeled as an arbitrary 0-10 severity score (coarse "
              "approximation, source reports presence/absence).",
        evidence_tier="external_cohort_anchor",
        hr=(1.61, "quartile_extreme", 1.1, 2.27, "higher_worse",
            "Santos RD, Rumberger JA, Budoff MJ, Shaw LJ, Orakzai SH, Berman D, "
            "Raggi P, Blumenthal RS, Nasir K. Thoracic aorta calcification "
            "detected by electron beam tomography predicts all-cause mortality. "
            "Atherosclerosis. 2010;209(1):131-135.", 8401),
        dist_source=None,
    ),
    "total-thiols": dict(
        name="Total Plasma Thiols", category="Oxidative Stress", units="umol/L",
        specimen_type="plasma", bodily_fluid="Blood Plasma",
        primary_organ="Multi-Organ", tissue_origin="Systemic Antioxidant Capacity",
        directionality="higher_better", causal_status="OBSERVATIONAL",
        valid_domain_min=200.0, valid_domain_max=700.0, optimal_target=500.0,
        aliases=["TTL", "Free thiols", "Plasma thiol capacity"],
        notes="A marker of systemic antioxidant/redox capacity (native "
              "thiols + disulfides). Mean/SD (462.0+/-58.7 umol/L) from a "
              "healthy-control reference study.",
        evidence_tier="external_cohort_anchor",
        hr=(0.73, "per_unit", 0.57, 0.93, "lower_worse",
            "Schottker B, Saum KU, Jansen EH, Boffetta P, Trichopoulou A, "
            "Holleczek B, Dieffenbach AK, Brenner H. Oxidative stress markers "
            "and all-cause mortality at older age: a population-based cohort "
            "study. J Gerontol A Biol Sci Med Sci. 2015;70(4):518-524.", 2932),
        dist_source="mp3_thiols_dist",
    ),
    "pericardial-fat": dict(
        name="Pericardial Fat Volume", category="Cardiac & Hemodynamics", units="cm3",
        specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Pericardial Adipose Tissue",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=10.0, valid_domain_max=250.0, optimal_target=60.0,
        aliases=["PFV", "Epicardial/pericardial adipose tissue volume"],
        notes="CT-quantified pericardial fat volume, a visceral-adiposity "
              "proxy distinct from waist circumference/BMI. Mean/SD "
              "(84.9+/-37.7 cm3) from an asymptomatic control cohort.",
        evidence_tier="external_cohort_anchor",
        hr=(1.34, "per_sd", 1.01, 1.78, "higher_worse",
            "Larsen BA, Laughlin GA, Saad SD, Barrett-Connor E, Allison MA, "
            "Wassel CL. Pericardial fat is associated with all-cause mortality "
            "but not incident CVD: the Rancho Bernardo Study. Atherosclerosis. "
            "2015;239(2):470-475.", 343),
        dist_source=None,
    ),
    "extracoronary-calcification-sites": dict(
        name="Extracoronary Calcification Site Count", category="Cardiac & Hemodynamics",
        units="site count", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Aortic Valve/Mitral Annulus/Aorta",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=4.0, optimal_target=0.0,
        aliases=["Extracoronary calcium burden"],
        notes="Composite count (0-4) of calcified extracoronary sites "
              "(aortic valve, mitral annulus, thoracic aorta, ascending "
              "aorta) on cardiac CT — a single coherent burden index, not a "
              "multi-different-biomarker panel.",
        evidence_tier="external_cohort_anchor",
        hr=(2.3, "quartile_extreme", 1.6, 3.31, "higher_worse",
            "Tison GH, Guo M, Blaha MJ, McClelland RL, Allison MA, Szklo M, "
            "Wong ND, Blumenthal RS, Budoff MJ, Nasir K. Multisite extracoronary "
            "calcification indicates increased risk of coronary heart disease "
            "and all-cause mortality: The Multi-Ethnic Study of Atherosclerosis. "
            "J Cardiovasc Comput Tomogr. 2015;9(5):406-414.", 5903),
        dist_source=None,
    ),
    "global-longitudinal-strain": dict(
        name="Left Ventricular Global Longitudinal Strain (GLS)",
        category="Cardiac & Hemodynamics", units="%", specimen_type="imaging",
        bodily_fluid="Non-Fluid / Imaging", primary_organ="Heart & Vasculature",
        tissue_origin="Left Ventricular Myocardium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=-30.0, valid_domain_max=-5.0, optimal_target=-22.0,
        aliases=["GLS", "LV strain"],
        notes="Speckle-tracking-derived myocardial deformation, reported as "
              "a negative percentage by convention (more negative = more "
              "deformation = healthier, hence 'lower' is 'better' on this "
              "signed scale). Mean/SD (-20%, SD 3%) from a pooled reference "
              "range (-24% to -16%) in 1,329 healthy adults.",
        evidence_tier="external_cohort_anchor",
        hr=(1.45, "per_sd", 1.19, 1.77, "higher_worse",
            "Stanton T, Leano R, Marwick TH. Prediction of all-cause mortality "
            "from global longitudinal speckle strain: comparison with ejection "
            "fraction and wall motion scoring. Circ Cardiovasc Imaging. "
            "2009;2(5):356-364.", 546),
        dist_source="mp3_gls_dist",
    ),
    "interventricular-septum-thickness": dict(
        name="Interventricular Septum Thickness", category="Cardiac & Hemodynamics",
        units="mm", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Interventricular Septum",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=5.0, valid_domain_max=16.0, optimal_target=9.0,
        aliases=["IVS thickness", "Septal wall thickness"],
        notes="Echocardiographic interventricular septal wall thickness "
              "(diastolic); a marker of left ventricular hypertrophy. "
              "Mean/SD (8.3+/-1.33 mm) from a published normal-range study.",
        evidence_tier="external_cohort_anchor",
        hr=(1.21, "per_sd", 1.05, 1.39, "higher_worse",
            "Kardys I, Deckers JW, Stricker BH, Vletter WB, Hofman A, Witteman "
            "JC. Echocardiographic parameters and all-cause mortality: the "
            "Rotterdam Study. Int J Cardiol. 2009;133(2):198-204.", 4425),
        dist_source=None,
    ),
    "severe-diastolic-dysfunction": dict(
        name="Left Ventricular Diastolic Dysfunction Grade", category="Cardiac & Hemodynamics",
        units="grade", specimen_type="imaging", bodily_fluid="Non-Fluid / Imaging",
        primary_organ="Heart & Vasculature", tissue_origin="Left Ventricular Myocardium",
        directionality="lower_better", causal_status="OBSERVATIONAL",
        valid_domain_min=0.0, valid_domain_max=3.0, optimal_target=0.0,
        aliases=["Diastolic function grade", "LV diastolic dysfunction"],
        notes="Echocardiographic diastolic function grade (0=normal, "
              "3=severe/restrictive). The source study's outcome is a "
              "composite of MI, heart failure, stroke, and all-cause "
              "mortality, not all-cause mortality alone — noted as a "
              "caveat; still the best located anchor for this marker.",
        evidence_tier="external_cohort_anchor",
        hr=(4.0, "quartile_extreme", 2.14, 7.47, "higher_worse",
            "Desai CS, Colangelo LA, Liu K, Jacobs DR Jr, Cook NL, Lloyd-Jones "
            "DM, Ogunyankin KO. Prevalence, prospective risk markers, and "
            "prognosis associated with the presence of left ventricular "
            "diastolic dysfunction in young adults: the coronary artery risk "
            "development in young adults study. Am J Epidemiol. "
            "2013;177(4):20-29.", 2952),
        dist_source=None,
    ),
}


DISTRIBUTIONS = {
    "kidney-injury-molecule-1": (0.5, 0.8, 2948, True),
    "ngal": (104.0, 34.7, 1393, False),
    "vertical-jump": (40.0, 12.0, 3117, True),
    "left-ventricular-ejection-fraction": (62.8, 5.4, 10427, False),
    "ctx-bone-resorption": (0.25, 0.12, 880, True),
    "skeletal-muscle-fat-infiltration": (30.0, 15.0, 1063, True),
    "calf-circumference": (36.5, 3.3, 17789, True),
    "standing-height": (169.0, 9.5, 195273, True),
    "bicarbonate": (25.2, 1.9, 31590, False),
    "anion-gap-albumin-adjusted": (9.0, 3.0, 862, True),
    "alpha-1-antichymotrypsin": (155.0, 30.0, 538, True),
    "renal-artery-calcification": (2.0, 3.0, 4450, True),
    "cardiac-calcification": (2.5, 3.0, 331, True),
    "abdominal-aortic-calcification": (2.0, 3.0, 2056, True),
    "thoracic-aorta-calcification": (2.0, 3.0, 8401, True),
    "total-thiols": (462.0, 58.7, 2932, False),
    "pericardial-fat": (84.9, 37.7, 343, False),
    "extracoronary-calcification-sites": (1.0, 1.2, 5903, True),
    "global-longitudinal-strain": (-20.0, 3.0, 1329, False),
    "interventricular-septum-thickness": (8.3, 1.33, 4425, False),
    "severe-diastolic-dysfunction": (0.4, 0.6, 2952, True),
}

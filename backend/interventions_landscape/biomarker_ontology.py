"""
Biomarker ontology: canonical names, aliases, synonyms, assay terminology,
biological categories, and measurement terminology for each biomarker.

This is the foundation for the high-recall CT.gov sweep. Before searching,
we expand each biomarker into a full vocabulary so the search matrix can
cover every way a trial might refer to the same analyte.

The ontology is data-driven: each biomarker gets a BiomarkerOntology entry
with all known names, categories, and measurement terms. New biomarkers
are added by appending to BIOMARKER_ONTOLOGY.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class BiomarkerOntology:
    """
    Full vocabulary for one biomarker.

    canonical_name:  the primary name used in our database
    aliases:         common abbreviations and alternative names
    historical:      older names that may appear in older trials
    assay_terms:     terminology used in lab/assay contexts
    biological_category: broader biological class (e.g. "lipid", "inflammatory marker")
    measurement_terms: how the biomarker is described in measurement contexts
    related_biomarkers: other biomarkers often measured alongside
    """
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    historical: List[str] = field(default_factory=list)
    assay_terms: List[str] = field(default_factory=list)
    biological_category: str = ""
    measurement_terms: List[str] = field(default_factory=list)
    related_biomarkers: List[str] = field(default_factory=list)

    def all_search_terms(self) -> List[str]:
        """Every term that should be searched, deduplicated, canonical first."""
        seen = set()
        terms = []
        for t in [self.canonical_name] + self.aliases + self.historical + self.assay_terms:
            tl = t.lower().strip()
            if tl and tl not in seen:
                seen.add(tl)
                terms.append(t)
        return terms

    def measurement_search_terms(self) -> List[str]:
        """Terms combining the biomarker with measurement vocabulary."""
        base = self.canonical_name
        return [f"{base} {m}" for m in self.measurement_terms]


# =======================================================================
# Ontology entries for all 50 biomarkers in the database
# =======================================================================

BIOMARKER_ONTOLOGY: Dict[str, BiomarkerOntology] = {
    # --- Lipids ---
    "ldl_cholesterol": BiomarkerOntology(
        canonical_name="LDL cholesterol",
        aliases=["low-density lipoprotein", "LDL-C", "LDL-C", "low density lipoprotein cholesterol"],
        historical=["beta-lipoprotein"],
        assay_terms=["LDL", "LDL-C", "LDL cholesterol level"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["HDL cholesterol", "total cholesterol", "triglycerides", "lipoprotein(a)"],
    ),
    "hdl_cholesterol": BiomarkerOntology(
        canonical_name="HDL cholesterol",
        aliases=["high-density lipoprotein", "HDL-C", "HDL-C", "high density lipoprotein cholesterol"],
        historical=["alpha-lipoprotein"],
        assay_terms=["HDL", "HDL-C", "HDL cholesterol level"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["LDL cholesterol", "total cholesterol", "triglycerides"],
    ),
    "total_cholesterol": BiomarkerOntology(
        canonical_name="total cholesterol",
        aliases=["TC", "serum cholesterol", "plasma cholesterol"],
        historical=[],
        assay_terms=["cholesterol", "total cholesterol level"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["LDL cholesterol", "HDL cholesterol", "triglycerides"],
    ),
    "triglycerides": BiomarkerOntology(
        canonical_name="triglycerides",
        aliases=["TG", "triglyceride", "triacylglycerol", "triacylglycerols"],
        historical=["neutral fat"],
        assay_terms=["TG", "triglyceride level"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement", "fasting"],
        related_biomarkers=["LDL cholesterol", "HDL cholesterol", "total cholesterol"],
    ),
    "lipoprotein_a)": BiomarkerOntology(
        canonical_name="lipoprotein(a)",
        aliases=["Lp(a)", "LPA", "lipoprotein a", "Lp(a) cholesterol"],
        historical=["Lp(a)"],
        assay_terms=["Lp(a)", "LPA"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["LDL cholesterol", "total cholesterol"],
    ),
    "apolipoprotein_a1": BiomarkerOntology(
        canonical_name="apolipoprotein A1",
        aliases=["ApoA1", "Apo A-I", "ApoAI", "apolipoprotein AI"],
        historical=[],
        assay_terms=["ApoA1", "Apo A-I"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["HDL cholesterol", "apolipoprotein B"],
    ),
    "apolipoprotein_b": BiomarkerOntology(
        canonical_name="apolipoprotein B",
        aliases=["ApoB", "Apo B", "apolipoprotein B-100"],
        historical=[],
        assay_terms=["ApoB", "Apo B"],
        biological_category="lipid",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["LDL cholesterol", "apolipoprotein A1"],
    ),

    # --- Glucose / Insulin ---
    "fasting_glucose": BiomarkerOntology(
        canonical_name="fasting glucose",
        aliases=["fasting blood glucose", "FBG", "fasting plasma glucose", "FPG", "glucose", "blood glucose", "plasma glucose"],
        historical=["blood sugar"],
        assay_terms=["glucose", "glucose level", "glucose concentration"],
        biological_category="glucose metabolism",
        measurement_terms=["serum", "plasma", "blood", "fasting", "concentration", "level", "measurement"],
        related_biomarkers=["HbA1c", "fasting insulin", "HOMA-IR"],
    ),
    "fasting_insulin": BiomarkerOntology(
        canonical_name="fasting insulin",
        aliases=["fasting serum insulin", "FSI", "insulin", "serum insulin", "plasma insulin"],
        historical=[],
        assay_terms=["insulin", "insulin level", "insulin concentration"],
        biological_category="glucose metabolism",
        measurement_terms=["serum", "plasma", "blood", "fasting", "concentration", "level", "measurement"],
        related_biomarkers=["fasting glucose", "HOMA-IR", "HbA1c"],
    ),
    "hba1c": BiomarkerOntology(
        canonical_name="HbA1c",
        aliases=["glycated hemoglobin", "glycosylated hemoglobin", "A1C", "HbA1", "glycated Hb", "Hemoglobin A1c", "HbA1c"],
        historical=["glycosylated hemoglobin"],
        assay_terms=["HbA1c", "A1C", "glycated hemoglobin"],
        biological_category="glucose metabolism",
        measurement_terms=["blood", "hemoglobin", "concentration", "level", "measurement", "percentage"],
        related_biomarkers=["fasting glucose", "fasting insulin"],
    ),
    "homa_ir": BiomarkerOntology(
        canonical_name="HOMA-IR",
        aliases=["homeostatic model assessment of insulin resistance", "HOMA IR", "insulin resistance index"],
        historical=[],
        assay_terms=["HOMA-IR", "HOMA IR"],
        biological_category="glucose metabolism",
        measurement_terms=["calculated", "derived", "index", "score"],
        related_biomarkers=["fasting glucose", "fasting insulin"],
    ),

    # --- Inflammatory markers ---
    "high_sensitivity_crp": BiomarkerOntology(
        canonical_name="high-sensitivity C-reactive protein",
        aliases=["hs-CRP", "hsCRP", "C-reactive protein", "CRP", "CRP", "serum CRP"],
        historical=["C-reactive protein"],
        assay_terms=["CRP", "hs-CRP", "C-reactive protein level"],
        biological_category="inflammatory marker",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["interleukin-6", "fibrinogen", "TNF-alpha", "ESR"],
    ),
    "interleukin_6": BiomarkerOntology(
        canonical_name="interleukin-6",
        aliases=["IL-6", "IL6", "interleukin 6", "IL-6"],
        historical=[],
        assay_terms=["IL-6", "IL6"],
        biological_category="inflammatory marker",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["hs-CRP", "TNF-alpha", "fibrinogen"],
    ),
    "tumor_necrosis_factor_alpha": BiomarkerOntology(
        canonical_name="tumor necrosis factor alpha",
        aliases=["TNF-alpha", "TNFα", "TNF", "tumor necrosis factor", "TNF-a"],
        historical=["cachectin"],
        assay_terms=["TNF-alpha", "TNF"],
        biological_category="inflammatory marker",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["IL-6", "hs-CRP", "fibrinogen"],
    ),
    "fibrinogen": BiomarkerOntology(
        canonical_name="fibrinogen",
        aliases=["FIB", "clotting factor I", "factor I"],
        historical=[],
        assay_terms=["fibrinogen", "fibrinogen level"],
        biological_category="inflammatory marker",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["hs-CRP", "IL-6", "ESR"],
    ),
    "erythrocyte_sedimentation_rate": BiomarkerOntology(
        canonical_name="erythrocyte sedimentation rate",
        aliases=["ESR", "sed rate", "sedimentation rate", "erythrocyte sedimentation"],
        historical=["sed rate"],
        assay_terms=["ESR", "sed rate"],
        biological_category="inflammatory marker",
        measurement_terms=["blood", "rate", "measurement"],
        related_biomarkers=["hs-CRP", "fibrinogen", "IL-6"],
    ),

    # --- Liver ---
    "alanine_aminotransferase": BiomarkerOntology(
        canonical_name="alanine aminotransferase",
        aliases=["ALT", "SGPT", "alanine transaminase", "alanine transaminase"],
        historical=["SGPT"],
        assay_terms=["ALT", "SGPT"],
        biological_category="liver enzyme",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement", "activity"],
        related_biomarkers=["AST", "ALP", "GGT", "total bilirubin"],
    ),
    "aspartate_aminotransferase": BiomarkerOntology(
        canonical_name="aspartate aminotransferase",
        aliases=["AST", "SGOT", "aspartate transaminase", "aspartate transaminase"],
        historical=["SGOT"],
        assay_terms=["AST", "SGOT"],
        biological_category="liver enzyme",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement", "activity"],
        related_biomarkers=["ALT", "ALP", "GGT"],
    ),
    "alkaline_phosphatase": BiomarkerOntology(
        canonical_name="alkaline phosphatase",
        aliases=["ALP", "alk phos", "alkaline phosphatase"],
        historical=[],
        assay_terms=["ALP", "alkaline phosphatase"],
        biological_category="liver enzyme",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement", "activity"],
        related_biomarkers=["ALT", "AST", "GGT", "total bilirubin"],
    ),
    "gamma_glutamyl_transferase": BiomarkerOntology(
        canonical_name="gamma-glutamyl transferase",
        aliases=["GGT", "GGTP", "gamma-GT", "gamma glutamyl transpeptidase", "gamma glutamyltransferase"],
        historical=["GGTP"],
        assay_terms=["GGT", "GGTP"],
        biological_category="liver enzyme",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement", "activity"],
        related_biomarkers=["ALT", "AST", "ALP"],
    ),
    "total_bilirubin": BiomarkerOntology(
        canonical_name="total bilirubin",
        aliases=["bilirubin", "total serum bilirubin", "TSB"],
        historical=[],
        assay_terms=["bilirubin", "total bilirubin"],
        biological_category="liver function",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["ALT", "AST", "ALP", "GGT"],
    ),

    # --- Kidney ---
    "serum_creatinine": BiomarkerOntology(
        canonical_name="serum creatinine",
        aliases=["creatinine", "Cr", "serum Cr", "plasma creatinine"],
        historical=[],
        assay_terms=["creatinine", "Cr"],
        biological_category="kidney function",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["eGFR", "cystatin C", "BUN", "UACR"],
    ),
    "estimated_gfr": BiomarkerOntology(
        canonical_name="estimated glomerular filtration rate",
        aliases=["eGFR", "EGFR", "glomerular filtration rate", "GFR"],
        historical=[],
        assay_terms=["eGFR", "GFR"],
        biological_category="kidney function",
        measurement_terms=["calculated", "derived", "estimated", "rate"],
        related_biomarkers=["serum creatinine", "cystatin C", "UACR"],
    ),
    "cystatin_c": BiomarkerOntology(
        canonical_name="cystatin C",
        aliases=["CysC", "cystatin C", "CST3"],
        historical=[],
        assay_terms=["cystatin C", "CysC"],
        biological_category="kidney function",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum creatinine", "eGFR"],
    ),
    "blood_urea_nitrogen": BiomarkerOntology(
        canonical_name="blood urea nitrogen",
        aliases=["BUN", "urea nitrogen", "serum urea nitrogen", "SUN", "urea"],
        historical=["urea"],
        assay_terms=["BUN", "urea nitrogen"],
        biological_category="kidney function",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum creatinine", "eGFR"],
    ),
    "urine_albumin_creatinine_ratio": BiomarkerOntology(
        canonical_name="urine albumin-to-creatinine ratio",
        aliases=["UACR", "albumin-to-creatinine ratio", "ACR", "urinary albumin-to-creatinine ratio", "albumin creatinine ratio"],
        historical=[],
        assay_terms=["UACR", "ACR"],
        biological_category="kidney function",
        measurement_terms=["urine", "urinary", "ratio", "measurement"],
        related_biomarkers=["serum albumin", "serum creatinine", "eGFR"],
    ),
    "urine_creatinine": BiomarkerOntology(
        canonical_name="urine creatinine",
        aliases=["urinary creatinine", "24-hour urine creatinine"],
        historical=[],
        assay_terms=["urine creatinine"],
        biological_category="kidney function",
        measurement_terms=["urine", "urinary", "concentration", "level", "measurement"],
        related_biomarkers=["UACR", "serum creatinine"],
    ),
    "urine_flow_rate": BiomarkerOntology(
        canonical_name="urine flow rate",
        aliases=["urinary flow rate", "uroflowmetry", "urine flow"],
        historical=[],
        assay_terms=["urine flow rate", "uroflowmetry"],
        biological_category="urinary function",
        measurement_terms=["urine", "urinary", "flow", "rate", "measurement"],
        related_biomarkers=[],
    ),
    "urine_specific_gravity": BiomarkerOntology(
        canonical_name="urine specific gravity",
        aliases=["specific gravity", "urine SG", "urinary specific gravity"],
        historical=[],
        assay_terms=["specific gravity", "urine SG"],
        biological_category="urinary function",
        measurement_terms=["urine", "urinary", "measurement"],
        related_biomarkers=[],
    ),

    # --- Hematology ---
    "hemoglobin": BiomarkerOntology(
        canonical_name="hemoglobin",
        aliases=["Hb", "HGB", "hemoglobin level", "blood hemoglobin"],
        historical=[],
        assay_terms=["Hb", "HGB", "hemoglobin"],
        biological_category="hematology",
        measurement_terms=["blood", "concentration", "level", "measurement"],
        related_biomarkers=["HbA1c", "RDW", "WBC", "platelet count"],
    ),
    "white_blood_cells": BiomarkerOntology(
        canonical_name="white blood cell count",
        aliases=["WBC", "WBC count", "leukocyte count", "white cell count", "leukocytes"],
        historical=["white cell count"],
        assay_terms=["WBC", "leukocyte count"],
        biological_category="hematology",
        measurement_terms=["blood", "count", "measurement"],
        related_biomarkers=["NLR", "platelet count", "hemoglobin"],
    ),
    "platelet_count": BiomarkerOntology(
        canonical_name="platelet count",
        aliases=["PLT", "platelets", "thrombocyte count", "platelet number"],
        historical=["thrombocyte count"],
        assay_terms=["PLT", "platelet count"],
        biological_category="hematology",
        measurement_terms=["blood", "count", "measurement"],
        related_biomarkers=["WBC", "hemoglobin", "NLR"],
    ),
    "red_cell_distribution_width": BiomarkerOntology(
        canonical_name="red cell distribution width",
        aliases=["RDW", "RDW-CV", "red blood cell distribution width", "RBC distribution width"],
        historical=[],
        assay_terms=["RDW", "RDW-CV"],
        biological_category="hematology",
        measurement_terms=["blood", "coefficient of variation", "measurement"],
        related_biomarkers=["hemoglobin", "WBC"],
    ),
    "neutrophil_lymphocyte_ratio": BiomarkerOntology(
        canonical_name="neutrophil-to-lymphocyte ratio",
        aliases=["NLR", "neutrophil lymphocyte ratio", "neutrophil/lymphocyte ratio"],
        historical=[],
        assay_terms=["NLR"],
        biological_category="hematology",
        measurement_terms=["calculated", "derived", "ratio"],
        related_biomarkers=["WBC", "platelet count"],
    ),

    # --- Cardiac ---
    "hs_troponin_t": BiomarkerOntology(
        canonical_name="high-sensitivity troponin T",
        aliases=["hs-cTnT", "hsTnT", "high sensitivity troponin T", "cTnT", "cardiac troponin T", "troponin T"],
        historical=["troponin T"],
        assay_terms=["hs-cTnT", "cTnT", "troponin T"],
        biological_category="cardiac biomarker",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["NT-proBNP", "hs-CRP"],
    ),
    "nt_pro_bnp": BiomarkerOntology(
        canonical_name="NT-proBNP",
        aliases=["N-terminal pro-B-type natriuretic peptide", "NT-pro BNP", "N-terminal proBNP", "proBNP"],
        historical=[],
        assay_terms=["NT-proBNP", "proBNP"],
        biological_category="cardiac biomarker",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["hs-cTnT", "hs-CRP"],
    ),
    "pulse_wave_velocity": BiomarkerOntology(
        canonical_name="pulse wave velocity",
        aliases=["PWV", "arterial stiffness", "aortic PWV", "carotid-femoral PWV", "cf-PWV"],
        historical=[],
        assay_terms=["PWV", "pulse wave velocity"],
        biological_category="cardiovascular",
        measurement_terms=["measurement", "velocity", "arterial"],
        related_biomarkers=["systolic blood pressure", "diastolic blood pressure"],
    ),
    "resting_heart_rate": BiomarkerOntology(
        canonical_name="resting heart rate",
        aliases=["RHR", "heart rate", "resting HR", "baseline heart rate"],
        historical=[],
        assay_terms=["heart rate", "RHR"],
        biological_category="cardiovascular",
        measurement_terms=["rate", "beats per minute", "measurement"],
        related_biomarkers=["systolic blood pressure", "diastolic blood pressure", "VO2 max"],
    ),
    "systolic_blood_pressure": BiomarkerOntology(
        canonical_name="systolic blood pressure",
        aliases=["SBP", "systolic BP", "systolic pressure", "systolic"],
        historical=[],
        assay_terms=["SBP", "systolic BP"],
        biological_category="cardiovascular",
        measurement_terms=["blood pressure", "pressure", "mmHg", "measurement"],
        related_biomarkers=["diastolic blood pressure", "PWV", "RHR"],
    ),
    "diastolic_blood_pressure": BiomarkerOntology(
        canonical_name="diastolic blood pressure",
        aliases=["DBP", "diastolic BP", "diastolic pressure", "diastolic"],
        historical=[],
        assay_terms=["DBP", "diastolic BP"],
        biological_category="cardiovascular",
        measurement_terms=["blood pressure", "pressure", "mmHg", "measurement"],
        related_biomarkers=["systolic blood pressure", "PWV", "RHR"],
    ),

    # --- Electrolytes / Minerals ---
    "serum_potassium": BiomarkerOntology(
        canonical_name="serum potassium",
        aliases=["potassium", "K", "K+", "serum K", "plasma potassium"],
        historical=[],
        assay_terms=["potassium", "K+"],
        biological_category="electrolyte",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum sodium", "serum calcium", "serum phosphate"],
    ),
    "serum_sodium": BiomarkerOntology(
        canonical_name="serum sodium",
        aliases=["sodium", "Na", "Na+", "serum Na", "plasma sodium"],
        historical=[],
        assay_terms=["sodium", "Na+"],
        biological_category="electrolyte",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum potassium", "serum calcium"],
    ),
    "serum_calcium": BiomarkerOntology(
        canonical_name="serum calcium",
        aliases=["calcium", "Ca", "Ca2+", "serum Ca", "total calcium", "ionized calcium"],
        historical=[],
        assay_terms=["calcium", "Ca2+"],
        biological_category="mineral",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum phosphate", "serum 25-hydroxyvitamin D", "serum albumin"],
    ),
    "serum_phosphate": BiomarkerOntology(
        canonical_name="serum phosphate",
        aliases=["phosphate", "phosphorus", "P", "serum P", "inorganic phosphate"],
        historical=["phosphorus"],
        assay_terms=["phosphate", "phosphorus"],
        biological_category="mineral",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum calcium", "serum 25-hydroxyvitamin D"],
    ),
    "serum_25_hydroxyvitamin_d": BiomarkerOntology(
        canonical_name="serum 25-hydroxyvitamin D",
        aliases=["25(OH)D", "25-hydroxyvitamin D", "vitamin D", "25-OH-D", "25-hydroxycholecalciferol", "vitamin D3", "cholecalciferol"],
        historical=["vitamin D"],
        assay_terms=["25(OH)D", "25-hydroxyvitamin D", "vitamin D"],
        biological_category="vitamin",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum calcium", "serum phosphate", "serum albumin"],
    ),

    # --- Other ---
    "serum_albumin": BiomarkerOntology(
        canonical_name="serum albumin",
        aliases=["albumin", "serum albumin level", "total protein albumin"],
        historical=[],
        assay_terms=["albumin", "serum albumin"],
        biological_category="protein",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum 25-hydroxyvitamin D", "serum calcium"],
    ),
    "serum_ferritin": BiomarkerOntology(
        canonical_name="serum ferritin",
        aliases=["ferritin", "serum ferritin level", "ferritin level"],
        historical=[],
        assay_terms=["ferritin", "serum ferritin"],
        biological_category="iron metabolism",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["hemoglobin", "serum albumin"],
    ),
    "serum_uric_acid": BiomarkerOntology(
        canonical_name="serum uric acid",
        aliases=["uric acid", "UA", "serum UA", "plasma uric acid"],
        historical=[],
        assay_terms=["uric acid", "UA"],
        biological_category="purine metabolism",
        measurement_terms=["serum", "plasma", "blood", "concentration", "level", "measurement"],
        related_biomarkers=["serum creatinine", "eGFR"],
    ),
    "grip_strength": BiomarkerOntology(
        canonical_name="grip strength",
        aliases=["hand grip strength", "handgrip strength", "dynapometry", "hand dynamometry"],
        historical=[],
        assay_terms=["grip strength", "handgrip"],
        biological_category="musculoskeletal",
        measurement_terms=["force", "measurement", "kg", "newtons"],
        related_biomarkers=["VO2 max", "sarcopenia"],
    ),
    "vo2_max": BiomarkerOntology(
        canonical_name="VO2 max",
        aliases=["maximal oxygen uptake", "peak oxygen uptake", "VO2peak", "maximal oxygen consumption", "peak VO2", "aerobic capacity", "cardiorespiratory fitness"],
        historical=["maximal oxygen uptake"],
        assay_terms=["VO2 max", "VO2peak", "peak VO2"],
        biological_category="cardiorespiratory fitness",
        measurement_terms=["oxygen uptake", "consumption", "mL/kg/min", "measurement"],
        related_biomarkers=["grip strength", "resting heart rate"],
    ),
}


def get_ontology(biomarker_id: str) -> BiomarkerOntology:
    """Look up the ontology for a biomarker by its database slug."""
    if biomarker_id not in BIOMARKER_ONTOLOGY:
        raise KeyError(
            f"No ontology for biomarker '{biomarker_id}'. "
            f"Add it to BIOMARKER_ONTOLOGY in biomarker_ontology.py. "
            f"Known: {sorted(BIOMARKER_ONTOLOGY.keys())}"
        )
    return BIOMARKER_ONTOLOGY[biomarker_id]


def all_biomarker_ids() -> List[str]:
    return sorted(BIOMARKER_ONTOLOGY.keys())
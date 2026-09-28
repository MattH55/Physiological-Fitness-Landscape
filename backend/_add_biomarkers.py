"""Add missing strong-evidence mortality biomarkers to the database."""
import sqlite3
import json
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"
conn = sqlite3.connect(db)

# New biomarkers to add: (slug, name, aliases, category, units, specimen_type, directionality, causal_status, valid_min, valid_max, optimal_target, notes)
NEW_BIOMARKERS = [
    # Inflammation / Immune
    ("gdf-15", "Growth Differentiation Factor-15 (GDF-15)",
     json.dumps(["GDF15", "C19", "NAP-1"]),
     "Inflammation", "pg/mL", "serum", "lower_better", "probable",
     0, 2000, 100,
     "One of the strongest all-cause mortality predictors in recent cohorts (Kivimaki et al. 2015, UK Biobank). Strongly elevated in heart failure, CKD, and cancer."),
    
    ("stnfr1", "Soluble Tumor Necrosis Factor Receptor 1 (sTNFR1)",
     json.dumps(["TNFRSF1A", "p55", "CD120a"]),
     "Inflammation", "pg/mL", "serum", "lower_better", "probable",
     0, 5000, 500,
     "Soluble TNF receptor with strong mortality signal in cardiovascular and cancer cohorts. Marker of chronic TNF-driven inflammation."),
    
    ("lmr", "Lymphocyte-to-Monocyte Ratio (LMR)",
     json.dumps(["LMR"]),
     "Inflammation", "ratio", "blood", "higher_better", "probable",
     0.1, 20, 5,
     "Inverse predictor of mortality across multiple meta-analyses. Low LMR indicates immune dysregulation and chronic inflammation."),
    
    ("ykl-40", "YKL-40 (CHI3L1)",
     json.dumps(["YKL-40", "CHI3L1", "Chitinase-3-like protein 1"]),
     "Inflammation", "ng/mL", "serum", "lower_better", "probable",
     0, 500, 50,
     "Chitinase-3-like protein 1. Strong mortality predictor in cardiovascular disease, COPD, and cancer cohorts. Marker of tissue remodeling and inflammation."),
    
    # Renal
    ("beta2-microglobulin", "Beta-2 Microglobulin",
     json.dumps(["B2M", "β2-microglobulin"]),
     "Renal & Purine", "mg/L", "serum", "lower_better", "probable",
     0.5, 10, 2.0,
     "Independent mortality predictor beyond creatinine-eGFR. Elevated in CKD, myeloma, and chronic inflammation. Strong signal in dialysis populations."),
    
    # Cardiac / Vascular
    ("galectin-3", "Galectin-3",
     json.dumps(["Gal-3", "Lectin X"]),
     "Cardiac & Hemodynamics", "ng/mL", "serum", "lower_better", "probable",
     0, 20, 7,
     "Beta-galactoside-binding lectin. Strong independent predictor of heart failure progression and all-cause mortality. Elevated in fibrosis and inflammation."),
    
    ("sst2", "ST2 Soluble (sST2)",
     json.dumps(["sST2", "IL-1RL1", "ST2L"]),
     "Cardiac & Hemodynamics", "ng/mL", "serum", "lower_better", "probable",
     0, 10000, 100,
     "Interleukin-1-like receptor 1. Strong predictor of adverse cardiovascular outcomes and mortality. FDA-cleared for heart failure risk stratification."),
    
    ("mr-proadm", "Mid-Regional Pro-Adrenomedullin (MR-proADM)",
     json.dumps(["MR-proADM", "Adrenomedullin"]),
     "Cardiac & Hemodynamics", "pmol/L", "serum", "lower_better", "probable",
     0, 100, 5,
     "Vasodilatory peptide. Strong mortality predictor in sepsis, heart failure, and general population cohorts. Reflects endothelial stress and sympathetic activation."),
    
    ("copeptin", "Copeptin",
     json.dumps(["Copeptin", "Vasopressin-related peptide"]),
     "Cardiac & Hemodynamics", "pmol/L", "serum", "lower_better", "probable",
     0, 100, 5,
     "Co-secreted with vasopressin. Stable surrogate for vasopressin release. Strong mortality predictor in sepsis, ACS, and heart failure."),
    
    # Metabolic / Hepatic
    ("homocysteine", "Homocysteine",
     json.dumps(["Hcy", "Total homocysteine"]),
     "Metabolic", "umol/L", "serum", "lower_better", "probable",
     0, 100, 10,
     "Amino acid metabolite. Elevated levels associated with cardiovascular mortality, cognitive decline, and fracture risk. U-shaped curve in some cohorts."),
    
    ("fib-4", "FIB-4 Index (NAFLD Fibrosis Score)",
     json.dumps(["FIB-4", "NAFLD fibrosis score"]),
     "Liver & Nutritional", "index", "serum", "lower_better", "probable",
     0, 20, 1.46,
     "Composite index: (Age x AST) / (Platelets x sqrt(ALT)). Non-invasive fibrosis marker. Strong mortality predictor in NAFLD/MASLD populations. Cutoffs: <1.3 low risk, >3.25 high risk."),
    
    # Endocrine
    ("free-t3", "Free Triiodothyronine (Free T3)",
     json.dumps(["FT3", "Free T3"]),
     "Vitamins & Endocrine", "pg/mL", "serum", "u_shaped", "probable",
     0.2, 10, 3.1,
     "Active thyroid hormone. U-shaped mortality curve: both low (hypothyroidism) and high (hyperthyroidism) associated with increased mortality. Strong signal in elderly."),
    
    ("tsh", "Thyroid-Stimulating Hormone (TSH)",
     json.dumps(["TSH", "Thyrotropin"]),
     "Vitamins & Endocrine", "mIU/L", "serum", "u_shaped", "probable",
     0.01, 50, 2.5,
     "U-shaped mortality curve well characterized. Both subclinical hypothyroidism (high TSH) and subclinical hyperthyroidism (low TSH) associated with increased mortality, especially in elderly."),
    
    ("igf-1", "Insulin-like Growth Factor 1 (IGF-1)",
     json.dumps(["IGF-1", "Somatomedin C"]),
     "Vitamins & Endocrine", "ng/mL", "serum", "u_shaped", "probable",
     0, 1000, 200,
     "U-shaped mortality curve. Both very low (anorexia, aging, malnutrition) and very high (cancer risk) associated with increased mortality. Strong in elderly cohorts."),
    
    ("dhea-s", "Dehydroepiandrosterone Sulfate (DHEA-S)",
     json.dumps(["DHEA-S", "DHEAS"]),
     "Vitamins & Endocrine", "ug/dL", "serum", "higher_better", "probable",
     0, 1000, 200,
     "Adrenal androgen precursor. Low levels associated with increased all-cause mortality, especially in elderly. Declines with age. Potential protective role against cardiovascular disease."),
    
    # Hematologic
    ("mpv", "Mean Platelet Volume (MPV)",
     json.dumps(["MPV"]),
     "Hematology", "fL", "blood", "u_shaped", "probable",
     5, 20, 10,
     "Average platelet size. U-shaped mortality association: both very low and very high MPV associated with increased cardiovascular mortality. Marker of platelet activation and turnover."),
    
    ("eosinophil-count", "Eosinophil Count",
     json.dumps(["Eosinophils", "Absolute eosinophil count"]),
     "Hematology", "10^3 cells/uL", "blood", "higher_better", "probable",
     0, 20, 0.3,
     "Low eosinophil count associated with increased mortality in multiple large cohorts (UK Biobank, ARIC). Very low/absent eosinophils indicate immune senescence or chronic stress."),
    
    # Oxidative stress / Aging
    ("8-ohdg", "8-Hydroxy-2'-deoxyguanosine (8-OHdG)",
     json.dumps(["8-OHdG", "8-OHdG", "8-hydroxydG"]),
     "Oxidative Stress", "pmol/mol DNA", "urine", "lower_better", "probable",
     0, 50, 5,
     "DNA oxidation marker. Elevated levels indicate oxidative DNA damage. Associated with increased cancer risk, cardiovascular disease, and all-cause mortality."),
    
    # Nutritional
    ("folate", "Serum Folate",
     json.dumps(["Folate", "Vitamin B9", "Folic acid"]),
     "Vitamins & Endocrine", "ng/mL", "serum", "higher_better", "probable",
     0, 100, 10,
     "Vitamin B9. Low levels associated with increased mortality, cardiovascular disease, and cognitive decline. Important for one-carbon metabolism and DNA synthesis."),
    
    ("vitamin-b12", "Vitamin B12 (Cobalamin)",
     json.dumps(["B12", "Cobalamin", "Vitamin B12"]),
     "Vitamins & Endocrine", "pg/mL", "serum", "higher_better", "probable",
     0, 2000, 500,
     "Essential vitamin. Deficiency associated with increased mortality, neurological damage, and megaloblastic anemia. U-shaped curve in some cohorts."),
    
    ("selenium", "Serum Selenium",
     json.dumps(["Selenium", "Se"]),
     "Electrolytes & Minerals", "ug/L", "serum", "u_shaped", "probable",
     0, 500, 100,
     "Trace mineral and antioxidant (glutathione peroxidase cofactor). U-shaped mortality curve: both deficiency and excess associated with increased mortality. Strong in cardiovascular cohorts."),
    
    ("zinc", "Serum Zinc",
     json.dumps(["Zinc", "Zn"]),
     "Electrolytes & Minerals", "ug/dL", "serum", "u_shaped", "probable",
     0, 300, 100,
     "Trace mineral. U-shaped mortality association. Deficiency associated with immune dysfunction, increased infection risk, and mortality. Excess may be harmful."),
]

# Check existing slugs
existing = {r[0] for r in conn.execute("SELECT slug FROM biomarker").fetchall()}
print(f"Existing biomarkers: {len(existing)}")

added = 0
for slug, name, aliases, category, units, specimen, directionality, causal_status, vmin, vmax, optimal, notes in NEW_BIOMARKERS:
    if slug in existing:
        print(f"  SKIP (exists): {name}")
        continue
    
    conn.execute("""
        INSERT INTO biomarker (slug, name, aliases, category, units, specimen_type, directionality, causal_status, valid_domain_min, valid_domain_max, optimal_target, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (slug, name, aliases, category, units, specimen, directionality, causal_status, vmin, vmax, optimal, notes))
    added += 1
    print(f"  ADDED: {name} (id={conn.execute('SELECT last_insert_rowid()').fetchone()[0]})")

conn.commit()
print(f"\nTotal added: {added}")
print(f"New total: {conn.execute('SELECT COUNT(*) FROM biomarker').fetchone()[0]}")
conn.close()
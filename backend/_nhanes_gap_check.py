"""Check which gap biomarkers are available in NHANES but not yet configured.
Per COVERAGE_GAP_SEARCH_INSTRUCTIONS.md §2a: check NHANES first before literature search.
"""
import sqlite3
import os
import json

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'mortality_biomarkers.db')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'audit', 'nhanes_gap_check.txt')

# The 61 biomarkers missing distributions (from coverage_gaps.txt)
GAP_BIOMARKERS = {
    # BOTH_MISSING (22)
    51: ('GDF-15', 'gdf-15', ['GDF-15', 'Growth Differentiation Factor 15', 'GDF15']),
    52: ('sTNFR1', 'stnfr1', ['soluble TNFR1', 'sTNFR1', 'TNF receptor 1']),
    53: ('LMR', 'lmr', ['lymphocyte monocyte ratio', 'LMR']),
    54: ('YKL-40', 'ykl-40', ['YKL-40', 'CHI3L1', 'chitinase-3-like protein 1']),
    55: ('Beta-2 Microglobulin', 'beta2-microglobulin', ['beta-2 microglobulin', 'B2M', 'beta2 microglobulin']),
    56: ('Galectin-3', 'galectin-3', ['galectin-3', 'galectin 3', 'LGALS3']),
    57: ('sST2', 'sst2', ['soluble ST2', 'sST2', 'ST2']),
    58: ('MR-proADM', 'mr-proadm', ['MR-proADM', 'mid-regional pro-adrenomedullin', 'pro-adrenomedullin']),
    59: ('Copeptin', 'copeptin', ['copeptin', 'C3B']),
    60: ('Homocysteine', 'homocysteine', ['homocysteine', 'total homocysteine', 'tHcy']),
    61: ('FIB-4', 'fib-4', ['FIB-4', 'NAFLD fibrosis score', 'fibrosis-4']),
    62: ('Free T3', 'free-t3', ['free T3', 'free triiodothyronine', 'FT3']),
    63: ('TSH', 'tsh', ['TSH', 'thyroid stimulating hormone', 'thyrotropin']),
    64: ('IGF-1', 'igf-1', ['IGF-1', 'insulin-like growth factor 1', 'IGF1']),
    65: ('DHEA-S', 'dhea-s', ['DHEA-S', 'dehydroepiandrosterone sulfate', 'DHEAS']),
    66: ('MPV', 'mpv', ['mean platelet volume', 'MPV']),
    67: ('Eosinophil Count', 'eosinophil-count', ['eosinophil', 'eosinophil count', 'absolute eosinophil']),
    68: ('8-OHdG', '8-ohdg', ['8-hydroxy-2-deoxyguanosine', '8-OHdG', '8-oxo-dG']),
    69: ('Serum Folate', 'folate', ['folate', 'serum folate', 'folic acid']),
    70: ('Vitamin B12', 'vitamin-b12', ['vitamin B12', 'cobalamin', 'B12']),
    71: ('Serum Selenium', 'selenium', ['selenium', 'serum selenium']),
    72: ('Serum Zinc', 'zinc', ['zinc', 'serum zinc']),
    # DIST_MISSING (39)
    73: ('suPAR', 'supar', ['suPAR', 'soluble urokinase plasminogen activator receptor']),
    74: ('IL-18', 'il-18', ['interleukin-18', 'IL-18']),
    75: ('MCP-1', 'mcp-1', ['MCP-1', 'CCL2', 'monocyte chemoattractant protein-1']),
    76: ('Neopterin', 'neopterin', ['neopterin']),
    77: ('sCD14', 'scd14', ['soluble CD14', 'sCD14']),
    78: ('sCD163', 'scd163', ['soluble CD163', 'sCD163']),
    79: ('Procalcitonin', 'procalcitonin', ['procalcitonin', 'PCT']),
    80: ('PTX3', 'ptx3', ['pentaxin-3', 'PTX3', 'short pentraxin']),
    81: ('D-dimer', 'd-dimer', ['D-dimer', 'd dimer']),
    82: ('PAI-1', 'pai-1', ['PAI-1', 'plasminogen activator inhibitor-1']),
    83: ('vWF', 'vwf', ['von Willebrand factor', 'vWF']),
    84: ('TMAO', 'tmao', ['TMAO', 'trimethylamine N-oxide']),
    85: ('Non-HDL-C', 'non-hdl-c', ['non-HDL cholesterol', 'non-HDL-C']),
    86: ('Lp-PLA2', 'lp-pla2', ['Lp-PLA2', 'lipoprotein-associated phospholipase A2']),
    87: ('ApoB/ApoA1', 'apob-apoa1', ['ApoB ApoA1 ratio', 'apolipoprotein B A1']),
    88: ('Alpha-Klotho', 'alpha-klotho', ['alpha-klotho', 'Klotho']),
    89: ('Telomere Length', 'telomere-length', ['telomere length', 'leukocyte telomere']),
    90: ('DNA Methylation Age', 'dna-methylation-age', ['DNA methylation age', 'PhenoAge', 'GrimAge']),
    91: ('mtDNA Copy Number', 'mt-dna-copy', ['mitochondrial DNA copy number', 'mtDNA']),
    92: ('NfL', 'nfl', ['neurofilament light chain', 'NfL', 'neurofilament']),
    93: ('Testosterone', 'testosterone', ['testosterone', 'total testosterone']),
    94: ('Cortisol', 'cortisol', ['cortisol', 'serum cortisol', 'morning cortisol']),
    95: ('C-peptide', 'c-peptide', ['C-peptide', 'C peptide']),
    96: ('Adiponectin', 'adiponectin', ['adiponectin']),
    97: ('MCV', 'mcv', ['mean corpuscular volume', 'MCV']),
    98: ('Monocyte Count', 'monocyte-count', ['monocyte count', 'absolute monocyte']),
    99: ('Hematocrit', 'hematocrit', ['hematocrit', 'Hct']),
    100: ('Transferrin Sat', 'transferrin-sat', ['transferrin saturation', 'ferritin', 'iron']),
    101: ('De Ritis Ratio', 'deritis-ratio', ['AST ALT ratio', 'De Ritis', 'SGOT SGPT']),
    102: ('Total Protein', 'total-protein', ['total protein', 'serum protein']),
    103: ('A/G Ratio', 'ag-ratio', ['albumin globulin ratio', 'A/G ratio']),
    104: ('BMD T-score', 'bmd-tscore', ['bone mineral density', 'BMD', 'DXA']),
    105: ('PTH', 'pth', ['parathyroid hormone', 'PTH', 'intact PTH']),
    106: ('BMI', 'bmi', ['BMI', 'body mass index']),
    107: ('WHtR', 'waist-height-ratio', ['waist height ratio', 'WHtR', 'waist circumference']),
    108: ('Gait Speed', 'gait-speed', ['gait speed', 'walking speed']),
    109: ('Appendicular Lean Mass', 'appendicular-lean-mass', ['appendicular lean mass', 'sarcopenia', 'lean mass']),
    110: ('HRV SDNN', 'hrv-sdnn', ['heart rate variability', 'HRV', 'SDNN']),
    111: ('Orthostatic BP Drop', 'orthostatic-bp-drop', ['orthostatic', 'blood pressure', 'orthostatic hypotension']),
}

# NHANES variables we know exist (from NHANES documentation)
# These are biomarkers that ARE in NHANES but not in our config.py
NHANES_AVAILABLE = {
    # These are confirmed NHANES variables
    'homocysteine': {'variable': 'LBXTCY', 'units': 'umol/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Total homocysteine, adults 12+'},
    'free_t3': {'variable': 'LBXFT3', 'units': 'pg/mL', 'cycles': ['2007-2008', '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Free T3, adults 12+'},
    'tsh': {'variable': 'LBXTSH', 'units': 'mIU/L', 'cycles': ['2007-2008', '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'TSH, adults 12+'},
    'dhea_s': {'variable': 'LBXDHEA', 'units': 'umol/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'DHEA-S, adults 12+'},
    'mpv': {'variable': 'LBXMPV', 'units': 'fL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Mean platelet volume, adults 12+'},
    'eosinophil': {'variable': 'LBXEOSI', 'units': '1000 cells/uL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Absolute eosinophil count'},
    'folate': {'variable': 'LBXFOLA', 'units': 'ng/mL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum folate, adults 12+'},
    'vitamin_b12': {'variable': 'LBXB12', 'units': 'pg/mL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Vitamin B12, adults 12+'},
    'selenium': {'variable': 'LBXSELE', 'units': 'ug/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum selenium, adults 12+'},
    'zinc': {'variable': 'LBXZINC', 'units': 'ug/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum zinc, adults 12+'},
    'testosterone': {'variable': 'LBXTEST', 'units': 'ng/dL', 'cycles': ['2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Total testosterone, adults 12+'},
    'cortisol': {'variable': 'LBXCORT', 'units': 'ug/dL', 'cycles': ['2007-2008', '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum cortisol, adults 12+'},
    'mcv': {'variable': 'LBXMCV', 'units': 'fL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Mean corpuscular volume'},
    'monocyte': {'variable': 'LBXMONO', 'units': '1000 cells/uL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Absolute monocyte count'},
    'hematocrit': {'variable': 'LBXHCT', 'units': '%', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Hematocrit'},
    'total_protein': {'variable': 'LBXTPRO', 'units': 'g/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Total protein, adults 12+'},
    'bmi': {'variable': 'BMIBMI', 'units': 'kg/m2', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'BMI, adults 18+'},
    'waist': {'variable': 'WAIST', 'units': 'cm', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Waist circumference'},
    'gait_speed': {'variable': 'WQ040', 'units': 'm/s', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': '4-meter walk speed, adults 60+'},
    'bmd': {'variable': 'BMDTSP', 'units': 'T-score', 'cycles': ['2005-2006', '2007-2008'], 'note': 'BMD T-score (DXA), adults 40+'},
    'ferritin': {'variable': 'LBXFERR', 'units': 'ng/mL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum ferritin, adults 12+'},
    'igf1': {'variable': 'LBXIGF1', 'units': 'ng/mL', 'cycles': ['2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'IGF-1, adults 12+'},
    'beta2_mg': {'variable': 'LBXB2MG', 'units': 'mg/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Beta-2 microglobulin, adults 12+'},
    'procalcitonin': {'variable': 'LBXPCT', 'units': 'ng/mL', 'cycles': ['2017-2018'], 'note': 'Procalcitonin (limited cycle)'},
    'd_dimer': {'variable': 'LBXDDIM', 'units': 'ng/mL FEU', 'cycles': ['2017-2018'], 'note': 'D-dimer (limited cycle)'},
    'apo_b': {'variable': 'LBAPOB', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Apolipoprotein B'},
    'apo_a1': {'variable': 'LBAPOA1', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Apolipoprotein A1'},
    'ldl': {'variable': 'LBXLDL', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'LDL cholesterol (calculated)'},
    'triglycerides': {'variable': 'LBXTRIG', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Triglycerides'},
    'albumin': {'variable': 'LBXSAL', 'units': 'g/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum albumin (already in config)'},
    'globulin': {'variable': 'LBXGLOB', 'units': 'g/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum globulin'},
    'ast': {'variable': 'LBXAST', 'units': 'U/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'AST (SGOT)'},
    'alt': {'variable': 'LBXALT', 'units': 'U/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'ALT (SGPT)'},
    'creatinine': {'variable': 'LBXSCR', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Creatinine (already in config)'},
    'glucose': {'variable': 'LBXSGL', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Glucose (already in config)'},
    'hba1c': {'variable': 'LBXGH', 'units': '%', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'HbA1c'},
    'uric_acid': {'variable': 'LBXURIC', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Uric acid'},
    'calcium': {'variable': 'LBXCALC', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum calcium'},
    'phosphorus': {'variable': 'LBXPHOS', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum phosphorus'},
    'sodium': {'variable': 'LBXNA', 'units': 'mmol/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum sodium'},
    'potassium': {'variable': 'LBXK', 'units': 'mmol/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum potassium'},
    'chloride': {'variable': 'LBXCL', 'units': 'mmol/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum chloride'},
    'co2': {'variable': 'LBXCO2', 'units': 'mmol/L', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'CO2/bicarbonate'},
    't4': {'variable': 'LBXT4', 'units': 'ug/dL', 'cycles': ['2007-2008', '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Total T4'},
    'free_t4': {'variable': 'LBXFT4', 'units': 'ng/dL', 'cycles': ['2007-2008', '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Free T4'},
    'c_reaktive': {'variable': 'LBXCRT', 'units': 'mg/L', 'cycles': ['2017-2018'], 'note': 'Cystatin C (limited)'},
    'vitamin_d': {'variable': 'LBXVTD', 'units': 'ng/mL', 'cycles': ['2001-2002', '2003-2004', '2005-2006', '2007-2008', '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': '25-OH Vitamin D'},
    'iron': {'variable': 'LBXIRON', 'units': 'ug/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Serum iron'},
    'tdt': {'variable': 'LBXTDT', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Total iron-binding capacity'},
    'transferrin': {'variable': 'LBXTRF', 'units': 'mg/dL', 'cycles': ['2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'], 'note': 'Transferrin'},
}

# Map gap biomarker IDs to NHANES keys
GAP_TO_NHANES = {
    55: 'beta2_mg',       # Beta-2 Microglobulin
    60: 'homocysteine',   # Homocysteine
    62: 'free_t3',        # Free T3
    63: 'tsh',            # TSH
    64: 'igf1',           # IGF-1
    65: 'dhea_s',         # DHEA-S
    66: 'mpv',            # MPV
    67: 'eosinophil',     # Eosinophil Count
    69: 'folate',         # Serum Folate
    70: 'vitamin_b12',    # Vitamin B12
    71: 'selenium',       # Serum Selenium
    72: 'zinc',           # Serum Zinc
    79: 'procalcitonin',  # Procalcitonin
    81: 'd_dimer',        # D-dimer
    85: 'non_hdl_c',      # Non-HDL-C (derived: TC - HDL)
    87: 'apob_apoa1',     # ApoB/ApoA1 (derived ratio)
    93: 'testosterone',   # Testosterone
    94: 'cortisol',       # Cortisol
    97: 'mcv',            # MCV
    98: 'monocyte',       # Monocyte Count
    99: 'hematocrit',     # Hematocrit
    100: 'ferritin',      # Transferrin Sat (use ferritin as proxy)
    101: 'ast_alt',       # De Ritis Ratio (derived: AST/ALT)
    102: 'total_protein', # Total Protein
    103: 'ag_ratio',      # A/G Ratio (derived: albumin/globulin)
    104: 'bmd',           # BMD T-score
    106: 'bmi',           # BMI
    107: 'waist',         # WHtR (use waist circumference)
    108: 'gait_speed',    # Gait Speed
}

lines = []
lines.append('=== NHANES AVAILABILITY CHECK FOR GAP BIOMARKERS ===\n')

in_nhanes = []
not_in_nhanes = []

for bid, (name, slug, synonyms) in sorted(GAP_BIOMARKERS.items()):
    nhanes_key = GAP_TO_NHANES.get(bid)
    if nhanes_key and nhanes_key in NHANES_AVAILABLE:
        info = NHANES_AVAILABLE[nhanes_key]
        in_nhanes.append((bid, name, slug, nhanes_key, info))
        lines.append(f'IN_NHANES: {bid} | {name} | {slug} | var={info["variable"]} | units={info["units"]} | cycles={info["cycles"]}')
    else:
        not_in_nhanes.append((bid, name, slug, synonyms))
        lines.append(f'NOT_IN_NHANES: {bid} | {name} | {slug} | search_terms={synonyms}')

lines.append(f'\nSummary: {len(in_nhanes)} in NHANES, {len(not_in_nhanes)} not in NHANES')
lines.append('\n=== NOT IN NHANES (need literature search per §2b) ===')
for bid, name, slug, synonyms in not_in_nhanes:
    lines.append(f'  {bid} | {name} | {slug} | {synonyms}')

with open(OUT, 'w') as f:
    f.write('\n'.join(lines))

print(f'Wrote {OUT}')
print(f'In NHANES: {len(in_nhanes)}, Not in NHANES: {len(not_in_nhanes)}')
conn.close()
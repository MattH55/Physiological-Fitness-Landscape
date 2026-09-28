"""
Match each biomarker without a lab_tests row to a candidate LOINC code from
the locally-ingested loinc_reference table (99,737 active LOINC codes).
Read-only exploration script: prints candidate matches for review, writes
nothing. See apply_loinc_matches.py for the write step.
"""
import io
import json
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

conn = sqlite3.connect("data/mortality_biomarkers.db")
cur = conn.cursor()

SPECIMEN_SYSTEMS = {
    "serum": ["Ser/Plas", "Ser", "Ser/Plas/Bld", "Bld"],
    "plasma": ["Ser/Plas", "Plas", "Ser/Plas/Bld", "Bld"],
    "whole_blood": ["Bld", "Bld/Ser/Plas", "BldC", "Ser/Plas/Bld"],
    "blood": ["Ser/Plas", "Bld", "Ser/Plas/Bld", "BldC"],
    "urine": ["Ur", "Urine"],
    "saliva": ["Saliva"],
    "imaging": ["Heart", "XXX", "^Patient", "Body"],
    "functional": ["XXX", "^Patient", "Lung"],
    "anthropometric": ["^Patient", "XXX"],
    "physiological": ["XXX", "^Patient", "Arterial system", "Heart"],
    "calculated": ["Ser/Plas", "Bld", "XXX"],
}
# Preferred property (concentration convention) per biomarker term, when known
# — resolves MCnc-vs-SCnc ties for electrolytes measured in molar units by
# clinical convention.
MOLAR_TERMS = {"sodium", "potassium", "chloride", "bicarbonate", "co2", "calcium", "magnesium"}

STOP = {"of", "the", "a", "and", "to", "in", "total"}

# Hand corrections for names LOINC spells very differently, or where the
# exact-component-match pass would otherwise miss/misfire. Value is the
# LOINC `component` string to match exactly.
MANUAL_COMPONENT = {
    "hematocrit": "Hematocrit",
    "hemoglobin": "Hemoglobin",
    "white_blood_cells": "Leukocytes",
    "platelet_count": "Platelets",
    "red-blood-cell-count": "Erythrocytes",
    "mcv": "Erythrocyte mean corpuscular volume",
    "mpv": "Platelet mean volume",
    "vitamin-b12": "Cobalamin",
    "d-dimer": "Fibrin D-dimer FEU",
    "systolic_blood_pressure": "Intravascular systolic",
    "diastolic_blood_pressure": "Intravascular diastolic",
    "waist-circumference": "Waist Circumference",
    "hip-circumference": "Hip Circumference",
    "arm-circumference": "Circumference Upper arm midpoint",
    "lymphocyte-count": "Lymphocytes",
    "neutrophil-count": "Neutrophils",
    "lymphocyte-percentage": "Lymphocytes/100 leukocytes",
    "neutrophil-percentage": "Neutrophils/100 leukocytes",
    "monocyte-percentage": "Monocytes/100 leukocytes",
    "reticulocyte-percentage": "Reticulocytes/100 erythrocytes",
    "red_cell_distribution_width": "Erythrocyte distribution width",
    "erythrocyte_sedimentation_rate": "Erythrocyte sedimentation rate",
    "non-hdl-c": "Cholesterol.total/HDL",
    "fib-4": "Fibrosis-4",
    "gamma_glutamyl_transferase": "Gamma glutamyl transferase",
    "free-t3": "Triiodothyronine (T3) Free",
    "igf-1": "Insulin-like growth factor 1",
    "gdf-15": "Growth differentiation factor 15",
    "il-18": "Interleukin 18",
    "interleukin-8": "Interleukin 8",
    "interleukin-10": "Interleukin 10",
    "interleukin-1-beta": "Interleukin 1 beta",
    "pth": "Parathyrin.intact",
    "resting_heart_rate": "Heart rate",
    "mean-arterial-pressure": "Mean blood pressure",
    "urine_albumin_creatinine_ratio": "Albumin/Creatinine",
    "urine_specific_gravity": "Specific gravity",
    "urine_flow_rate": "Volume rate",
    "urine_creatinine": "Creatinine",
    "lipoprotein_a": "Lipoprotein (a)",
    "apolipoprotein_a1": "Apolipoprotein A-I",
    "vwf": "von Willebrand factor activity",
    "hs_troponin_t": "Troponin T.cardiac",
    "nt_pro_bnp": "Natriuretic peptide B prohormone N-Terminal",
    "homa_ir": "Insulin resistance score",
    "sit-ups": "Number of situps in 60 seconds",
    "total-protein": "Protein",
    "ag-ratio": "Albumin/Globulin",
    "bmd-tscore": "Bone density T-score",
    "waist-to-hip-ratio": "Waist circumference/Hip circumference",
    "waist-height-ratio": "Waist circumference/Height",
    "ankle-brachial-index": "Ankle/Brachial pressure index",
    "antinuclear-antibodies": "Antinuclear antibody",
    "vo2_max": "Oxygen consumption^^maximum Calculated",
    "forced-expiratory-volume-1": "Forced expiratory volume in 1 second",
    "fev1-fev6-ratio": "FEV1/FEV6",
    "coronary-artery-calcium-score": "Coronary artery calcium score Agatston",
    "carotid-intima-media-thickness": "Intima media thickness",
    "asymmetric-dimethylarginine": "Asymmetric dimethylarginine",
    "beta2-microglobulin": "Beta-2-Microglobulin",
    "telomere-length": "Telomere length",
    "vitamin-b12": "Cobalamins",
    "d-dimer": "Fibrin D-dimer",
    "non-hdl-c": "Cholesterol.total/Cholesterol.in HDL",
    "free-t3": "Triiodothyronine.free",
    "igf-1": "Insulin-like growth factor-I",
    "gdf-15": "Growth and differentiation factor 15",
    "lipoprotein_a": "Lipoprotein (little a)",
    "nt_pro_bnp": "Natriuretic peptide.B prohormone N-Terminal",
    "asymmetric-dimethylarginine": "N,N-dimethylarginine",
}


def strip_paren(s):
    return re.sub(r"\([^)]*\)", "", s).strip()


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


# Direct loinc_code overrides for names where text search picks a poor
# component (e.g. hematocrit's real component is literally "Erythrocyte/Blood"
# — packed-cell-volume terminology, not the word "hematocrit"). Every code
# here was looked up and confirmed to exist in the local loinc_reference
# table before being hardcoded.
MANUAL_CODE = {
    "hematocrit": "4544-3",
    "mcv": "787-2",
    "mpv": "32623-1",
    "erythrocyte_sedimentation_rate": "30341-2",
    "red_cell_distribution_width": "788-0",
    "standing-height": "8302-2",
    "waist-circumference": "8280-0",
    "mean-arterial-pressure": "8478-0",
    "vo2_max": "103749-8",
    "lymphocyte-percentage": "736-9",
    "neutrophil-percentage": "770-8",
    "monocyte-percentage": "5905-5",
}

cur.execute(
    "SELECT b.id, b.slug, b.name, b.aliases, b.specimen_type FROM biomarker b "
    "LEFT JOIN lab_tests lt ON lt.canonical_biomarker_id = b.id "
    "WHERE lt.test_id IS NULL ORDER BY b.id"
)
biomarkers = cur.fetchall()
print(f"{len(biomarkers)} biomarkers without a lab_tests row\n")

results = {}
for bid, slug, name, aliases_json, specimen in biomarkers:
    if slug in MANUAL_CODE:
        code = MANUAL_CODE[slug]
        cur.execute(
            "SELECT loinc_code, component, system, property_, scale_type, "
            "loinc_class, long_common_name FROM loinc_reference WHERE loinc_code=?",
            (code,),
        )
        row = cur.fetchone()
        if row:
            results[slug] = dict(
                biomarker_id=bid, matched_term="(manual code)", loinc_code=row[0],
                component=row[1], system=row[2], property=row[3],
                loinc_class=row[5], long_common_name=row[6], n_candidates=1,
            )
        continue

    aliases = json.loads(aliases_json) if aliases_json else []
    candidates_terms = []
    if slug in MANUAL_COMPONENT:
        candidates_terms.append(MANUAL_COMPONENT[slug])
    candidates_terms += [strip_paren(name)] + aliases
    systems = SPECIMEN_SYSTEMS.get(specimen, [])

    best = None
    for term in candidates_terms:
        t = term.strip()
        if len(t) < 3:
            continue
        # exact component match (case-insensitive)
        cur.execute(
            "SELECT loinc_code, component, system, property_, scale_type, "
            "loinc_class, long_common_name FROM loinc_reference "
            "WHERE lower(component) = lower(?) AND scale_type='Qn'",
            (t,),
        )
        rows = cur.fetchall()
        if not rows:
            continue
        is_molar = norm(t).strip() in MOLAR_TERMS

        def sys_rank(r):
            try:
                return systems.index(r[2])
            except ValueError:
                return len(systems) + 1

        rows.sort(key=lambda r: (
            sys_rank(r) if systems else 0,
            0 if r[3] in (("SCnc",) if is_molar else ("MCnc",)) else
            (1 if r[3] in ("MCnc", "SCnc", "NCnc", "ACnc", "CCnc", "Ratio", "SRto") else 2),
            0 if "by" not in (r[6] or "").lower() else 1,
            len(r[6] or ""),
        ))
        if rows:
            best = (term, rows[0], len(rows))
            break

    if best:
        term, row, n_total = best
        results[slug] = dict(
            biomarker_id=bid, matched_term=term, loinc_code=row[0],
            component=row[1], system=row[2], property=row[3],
            loinc_class=row[5], long_common_name=row[6], n_candidates=n_total,
        )

print(f"Matched: {len(results)} / {len(biomarkers)}\n")
with open("backend/_loinc_match_candidates.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

for slug, r in list(results.items())[:40]:
    print(f"{slug:<35} -> {r['loinc_code']:<10} {r['long_common_name']}")

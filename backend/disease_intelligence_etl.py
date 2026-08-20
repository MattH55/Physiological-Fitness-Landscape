"""
Disease Intelligence ETL Pipeline for Physiological Fitness Landscape.
Parses structured disease intelligence HTML files from OpenSourceMedicine research tracker,
extracts disease burden, remission profiles, ontology cross-references, and multi-scale alterations
(Molecular, Lab/Clinical Biomarkers, Scales/PROs, Pathology, Functional),
and maps alterations directly to Physiological Fitness Landscape biomarkers.
"""

import os
import glob
import re
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.models import (
    Disease,
    DiseaseAlteration,
    Biomarker,
    get_engine,
    init_db
)

# Standard mapping dictionary from common alteration names/aliases to Biomarker slugs
BIOMARKER_NAME_MAPPINGS = {
    # Lipids
    "serum total cholesterol": "serum-total-cholesterol",
    "total cholesterol": "serum-total-cholesterol",
    "cholesterol": "serum-total-cholesterol",
    "hypercholesterolemia": "serum-total-cholesterol",
    "hdl cholesterol": "hdl-cholesterol",
    "hdl-c": "hdl-cholesterol",
    "high density lipoprotein": "hdl-cholesterol",
    "ldl cholesterol": "ldl-cholesterol",
    "ldl-c": "ldl-cholesterol",
    "low density lipoprotein": "ldl-cholesterol",
    "hypercholesterolaemia": "serum-total-cholesterol",
    "triglycerides": "triglycerides",
    "serum triglycerides": "triglycerides",
    "hypertriglyceridemia": "triglycerides",
    
    # Metabolic & Glycemic
    "hba1c": "hba1c",
    "glycated hemoglobin": "hba1c",
    "hemoglobin a1c": "hba1c",
    "fasting blood glucose": "fasting-glucose",
    "fasting glucose": "fasting-glucose",
    "blood glucose": "fasting-glucose",
    "hyperglycemia": "fasting-glucose",
    "hypoglycemia": "fasting-glucose",
    "fasting insulin": "fasting-insulin",
    "serum insulin": "fasting-insulin",
    "hyperinsulinemia": "fasting-insulin",
    "homa-ir": "homa-ir",
    "insulin resistance": "homa-ir",
    
    # Inflammation & Immune
    "high-sensitivity c-reactive protein": "high-sensitivity-crp",
    "c-reactive protein": "high-sensitivity-crp",
    "crp": "high-sensitivity-crp",
    "hscrp": "high-sensitivity-crp",
    "elevated c-reactive protein": "high-sensitivity-crp",
    "interleukin-6": "interleukin-6",
    "il-6": "interleukin-6",
    "il6": "interleukin-6",
    "homocysteine": "homocysteine",
    "hyperhomocysteinemia": "homocysteine",
    "serum ferritin": "serum-ferritin",
    "ferritin": "serum-ferritin",
    "hyperferritinemia": "serum-ferritin",
    
    # Renal / Kidney
    "serum creatinine": "serum-creatinine",
    "creatinine": "serum-creatinine",
    "estimated gfr": "estimated-gfr",
    "egfr": "estimated-gfr",
    "decreased egfr": "estimated-gfr",
    "decreased glomerular filtration rate": "estimated-gfr",
    "blood urea nitrogen": "blood-urea-nitrogen",
    "bun": "blood-urea-nitrogen",
    "urea": "blood-urea-nitrogen",
    "urinary albumin-to-creatinine ratio": "urinary-albumin-creatinine-ratio",
    "uacr": "urinary-albumin-creatinine-ratio",
    "microalbuminuria": "urinary-albumin-creatinine-ratio",
    "proteinuria": "urinary-albumin-creatinine-ratio",
    "albuminuria": "urinary-albumin-creatinine-ratio",
    "cystatin c": "cystatin-c",
    "cystatin-c": "cystatin-c",
    "cst3": "cystatin-c",
    
    # Hepatic / Liver
    "alanine aminotransferase": "alanine-aminotransferase",
    "alt": "alanine-aminotransferase",
    "sgpt": "alanine-aminotransferase",
    "elevated alanine aminotransferase": "alanine-aminotransferase",
    "aspartate aminotransferase": "aspartate-aminotransferase",
    "ast": "aspartate-aminotransferase",
    "sgot": "aspartate-aminotransferase",
    "elevated aspartate aminotransferase": "aspartate-aminotransferase",
    "gamma-glutamyl transferase": "gamma-glutamyl-transferase",
    "ggt": "gamma-glutamyl-transferase",
    "serum albumin": "serum-albumin",
    "hypoalbuminemia": "serum-albumin",
    "total bilirubin": "total-bilirubin",
    "bilirubin": "total-bilirubin",
    "hyperbilirubinemia": "total-bilirubin",
    
    # Cardiovascular & Hemodynamic
    "systolic blood pressure": "systolic-blood-pressure",
    "systolic hypertension": "systolic-blood-pressure",
    "diastolic blood pressure": "diastolic-blood-pressure",
    "pulse pressure": "pulse-pressure",
    "resting heart rate": "resting-heart-rate",
    "heart rate": "resting-heart-rate",
    "tachycardia": "resting-heart-rate",
    "bradycardia": "resting-heart-rate",
    "heart rate variability": "heart-rate-variability-sdnn",
    "hrv": "heart-rate-variability-sdnn",
    
    # Hematology
    "white blood cell count": "white-blood-cell-count",
    "wbc count": "white-blood-cell-count",
    "leukocytosis": "white-blood-cell-count",
    "leukopenia": "white-blood-cell-count",
    "neutrophil-to-lymphocyte ratio": "neutrophil-to-lymphocyte-ratio",
    "nlr": "neutrophil-to-lymphocyte-ratio",
    "hemoglobin": "hemoglobin",
    "anemia": "hemoglobin",
    "platelet count": "platelet-count",
    "thrombocytopenia": "platelet-count",
    "thrombocytosis": "platelet-count",
    "red cell distribution width": "red-cell-distribution-width",
    "rdw": "red-cell-distribution-width",
    
    # Electrolytes & Minerals
    "serum sodium": "serum-sodium",
    "hyponatremia": "serum-sodium",
    "hypernatremia": "serum-sodium",
    "serum potassium": "serum-potassium",
    "hypokalemia": "serum-potassium",
    "hyperkalemia": "serum-potassium",
    "serum calcium": "serum-calcium",
    "hypocalcemia": "serum-calcium",
    "hypercalcemia": "serum-calcium",
    "serum magnesium": "serum-magnesium",
    "hypomagnesemia": "serum-magnesium",
    "serum uric acid": "serum-uric-acid",
    "uric acid": "serum-uric-acid",
    "hyperuricemia": "serum-uric-acid",
    
    # Endocrine & Vitamins
    "serum 25-hydroxyvitamin d": "serum-25-hydroxyvitamin-d",
    "vitamin d": "serum-25-hydroxyvitamin-d",
    "25-hydroxyvitamin d": "serum-25-hydroxyvitamin-d",
    "vitamin d deficiency": "serum-25-hydroxyvitamin-d",
    "thyroid-stimulating hormone": "thyroid-stimulating-hormone",
    "tsh": "thyroid-stimulating-hormone",
    "hypothyroidism": "thyroid-stimulating-hormone",
    "hyperthyroidism": "thyroid-stimulating-hormone",
    
    # Functional & Physical Fitness
    "vo2 max": "vo2-max",
    "cardiorespiratory fitness": "vo2-max",
    "handgrip strength": "handgrip-strength",
    "grip strength": "handgrip-strength",
    "decreased grip strength": "handgrip-strength",
    "gait speed": "gait-speed",
    "slow gait speed": "gait-speed",
    "walking speed": "gait-speed"
}


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy string matching."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def find_matching_biomarker(
    alt_name: str,
    alt_sub: str,
    biomarkers_by_slug: Dict[str, Biomarker],
    biomarkers_by_name: Dict[str, Biomarker]
) -> Optional[Biomarker]:
    """
    Intelligently matches an alteration name or sub-description to a known fitness landscape biomarker.
    """
    norm_name = normalize_text(alt_name)
    norm_sub = normalize_text(alt_sub) if alt_sub else ""

    # 1. Direct dictionary match
    if norm_name in BIOMARKER_NAME_MAPPINGS:
        slug = BIOMARKER_NAME_MAPPINGS[norm_name]
        if slug in biomarkers_by_slug:
            return biomarkers_by_slug[slug]

    if norm_sub in BIOMARKER_NAME_MAPPINGS:
        slug = BIOMARKER_NAME_MAPPINGS[norm_sub]
        if slug in biomarkers_by_slug:
            return biomarkers_by_slug[slug]

    # 2. Exact name match
    if norm_name in biomarkers_by_name:
        return biomarkers_by_name[norm_name]

    # 3. Substring / alias search
    for slug, bm in biomarkers_by_slug.items():
        bm_norm = normalize_text(bm.name)
        if bm_norm == norm_name:
            return bm
        if len(norm_name) > 4 and (norm_name in bm_norm or bm_norm in norm_name):
            return bm
        # check aliases
        for alias in (bm.aliases or []):
            alias_norm = normalize_text(alias)
            if alias_norm == norm_name or alias_norm == norm_sub:
                return bm
            if len(alias_norm) > 4 and (alias_norm in norm_name or norm_name in alias_norm):
                return bm

    return None


def parse_disease_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single disease intelligence HTML document.
    """
    fname = os.path.basename(file_path)
    if fname in ["index.html", "gene-therapy-mapper.html", "right-to-try.html"]:
        return None

    with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
        html_content = fp.read()
    soup = BeautifulSoup(html_content, "html.parser")

    h1 = soup.find("h1")
    disease_name = h1.text.strip() if h1 else fname.replace(".html", "").replace("-", " ").title()

    # Burden metrics
    burden = {}
    for b_stat in soup.find_all("div", class_="hero-burden-stat"):
        lbl = b_stat.find("span", class_="hero-burden-label")
        val = b_stat.find("span", class_="hero-burden-value")
        sub = b_stat.find("span", class_="hero-burden-sub")
        if lbl and val:
            lbl_k = lbl.text.strip()
            val_v = val.text.strip()
            sub_v = sub.text.strip() if sub else ""
            burden[lbl_k] = {"value": val_v, "sub": sub_v}

    # Remission metrics
    rem_details = {}
    for r_stat in soup.find_all("div", class_="hero-rem-stat"):
        lbl = r_stat.find("span", class_="hero-rem-label")
        val = r_stat.find("span", class_="hero-rem-value")
        if lbl and val:
            rem_details[lbl.text.strip()] = val.text.strip()

    rem_sec = soup.find("section", id="remission")
    if rem_sec:
        for cell in rem_sec.find_all("div", class_="rem-cell"):
            lbl = cell.find("div", class_="label")
            val = cell.find("div", class_="value")
            if lbl and val:
                rem_details[lbl.text.strip()] = val.text.strip()
        barrier = rem_sec.find("div", class_="barrier-note")
        if barrier:
            rem_details["barrier_note"] = barrier.text.strip().replace("Barrier detail:", "").strip()
        for p in rem_sec.find_all("p", class_="meta-line"):
            if "Last SoC change:" in p.text:
                rem_details["soc_change"] = p.text.strip().replace("Last SoC change:", "").strip()

    # Identifiers
    identifiers = {}
    for p in soup.find_all("p", class_="meta-line"):
        if "Identifiers:" in p.text:
            text = p.text.strip()
            # Parse MONDO: MONDO:0005148 · EFO: EFO_0001360 etc.
            tokens = text.split("·")
            for tok in tokens:
                tok = tok.replace("Identifiers:", "").strip()
                if ":" in tok:
                    parts = tok.split(":", 1)
                    k = parts[0].strip()
                    v = parts[1].strip()
                    identifiers[k] = v

    # Alterations
    alterations = []
    alt_sec = soup.find("section", id="alterations")
    if alt_sec:
        for tr in alt_sec.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue
            name_cell = tds[0]
            strong = name_cell.find("strong")
            alt_name = strong.text.strip() if strong else name_cell.text.strip()
            sub = name_cell.find("div", class_="sub")
            alt_sub = sub.text.strip() if sub else ""

            alt_type = tds[1].text.strip()
            subtype = tds[2].text.strip()
            direction = tds[3].text.strip()
            freq = tds[4].text.strip()
            evidence = tds[5].text.strip()
            sources = tds[6].text.strip()

            links = []
            if len(tds) >= 8:
                for a in tds[7].find_all("a"):
                    links.append({"text": a.text.strip(), "url": a.get("href")})

            alterations.append({
                "name": alt_name,
                "sub_name": alt_sub,
                "alteration_type": alt_type,
                "alteration_type_code": tr.get("data-type", ""),
                "subtype": subtype,
                "direction": direction,
                "frequency": freq,
                "evidence_level": evidence,
                "sources": sources,
                "links": links
            })

    # Therapeutics count
    therapeutics_count = 0
    ther_sec = soup.find("section", id="therapeutics") or soup.find("div", id="therapeutics")
    if ther_sec:
        ther_rows = ther_sec.find_all("tr")
        therapeutics_count = max(0, len(ther_rows) - 1)

    return {
        "slug": fname.replace(".html", ""),
        "name": disease_name,
        "burden": burden,
        "remission_details": rem_details,
        "identifiers": identifiers,
        "alterations_count": len(alterations),
        "therapeutics_count": therapeutics_count,
        "alterations": alterations
    }


def ingest_disease_intelligence(
    db_session: Session,
    source_folder: str = r"C:\Users\matth\OneDrive\Documents\OpenSourceMed\Opensource Medicine (1)\research-tracker\disease-intelligence"
) -> Dict[str, int]:
    """
    Main ETL ingestion routine: iterates over all HTML files in disease-intelligence directory,
    creates Disease and DiseaseAlteration records, and maps them to Physiological Fitness Landscape Biomarkers.
    """
    if not os.path.exists(source_folder):
        raise FileNotFoundError(f"Disease intelligence directory not found at {source_folder}")

    # Build biomarker lookup tables
    biomarkers = db_session.query(Biomarker).all()
    biomarkers_by_slug = {b.slug: b for b in biomarkers}
    biomarkers_by_name = {normalize_text(b.name): b for b in biomarkers}

    html_files = glob.glob(os.path.join(source_folder, "*.html"))
    total_diseases_created = 0
    total_alterations_created = 0
    total_biomarker_matches = 0

    print(f"[*] Found {len(html_files)} intelligence files. Parsing and populating database...")

    for file_path in html_files:
        parsed = parse_disease_file(file_path)
        if not parsed:
            continue

        slug = parsed["slug"]
        
        # Check if disease already exists
        existing_disease = db_session.query(Disease).filter_by(slug=slug).first()
        if existing_disease:
            db_session.delete(existing_disease)
            db_session.flush()

        burden = parsed["burden"]
        rem = parsed["remission_details"]

        disease = Disease(
            slug=slug,
            name=parsed["name"],
            category="Chronic Disease",
            us_dalys=burden.get("US DALYs", {}).get("value"),
            global_dalys=burden.get("Global DALYs", {}).get("value"),
            us_mortality=burden.get("US mortality", {}).get("value"),
            global_mortality=burden.get("Global mortality", {}).get("value"),
            nih_funding=burden.get("NIH funding", {}).get("value"),
            funding_level=burden.get("Funding level", {}).get("value"),
            spontaneous_remission=rem.get("Spontaneous remission") or rem.get("Spontaneous Remission"),
            best_intervention_remission=rem.get("Best-intervention remission") or rem.get("Best-Intervention Remission"),
            gap_size=rem.get("Gap size") or rem.get("Gap Size"),
            primary_barrier=rem.get("Primary barrier") or rem.get("Primary Barrier"),
            barrier_detail=rem.get("barrier_note"),
            soc_change=rem.get("soc_change"),
            identifiers=parsed["identifiers"],
            alterations_count=parsed["alterations_count"],
            therapeutics_count=parsed["therapeutics_count"]
        )
        db_session.add(disease)
        db_session.flush()

        for alt in parsed["alterations"]:
            matched_bm = find_matching_biomarker(
                alt["name"],
                alt["sub_name"],
                biomarkers_by_slug,
                biomarkers_by_name
            )

            is_match = 1 if matched_bm else 0
            if is_match:
                total_biomarker_matches += 1

            alt_record = DiseaseAlteration(
                disease_id=disease.id,
                biomarker_id=matched_bm.id if matched_bm else None,
                name=alt["name"],
                sub_name=alt["sub_name"],
                alteration_type=alt["alteration_type"],
                alteration_type_code=alt["alteration_type_code"],
                subtype=alt["subtype"],
                direction=alt["direction"],
                frequency=alt["frequency"],
                evidence_level=alt["evidence_level"],
                sources=alt["sources"],
                links=alt["links"],
                is_biomarker_match=is_match
            )
            db_session.add(alt_record)
            total_alterations_created += 1

        total_diseases_created += 1

    db_session.commit()
    print(f"[SUCCESS] Ingested {total_diseases_created} diseases and {total_alterations_created} alterations ({total_biomarker_matches} mapped to fitness landscape biomarkers).")

    return {
        "diseases": total_diseases_created,
        "alterations": total_alterations_created,
        "biomarker_matches": total_biomarker_matches
    }


if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mortality_biomarkers.db")
    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)
    from sqlalchemy.orm import sessionmaker
    SessionMaker = sessionmaker(bind=engine)
    session = SessionMaker()
    stats = ingest_disease_intelligence(session)
    print("Ingestion stats:", stats)

"""
Build a CSV of every biomarker with: distribution provenance, mortality-
association provenance, LOINC code + identifiers, and (from
backend/_mesh_cache.json, populated by _fetch_mesh_terms.py) the MeSH
heading ClinicalTrials.gov indexes studies against.

Usage: python backend/build_provenance_csv.py [output.csv]
"""
import csv
import json
import sqlite3
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "biomarker_provenance.csv"

conn = sqlite3.connect("data/mortality_biomarkers.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

try:
    with open("backend/_mesh_cache.json", encoding="utf-8") as f:
        mesh_cache = json.load(f)
except FileNotFoundError:
    mesh_cache = {}

cur.execute("SELECT * FROM biomarker ORDER BY category, name")
biomarkers = cur.fetchall()

rows = []
for b in biomarkers:
    bid = b["id"]

    # --- Distribution provenance: all/all stratum's source ---
    cur.execute(
        """
        SELECT s.citation, s.pmid, s.doi, s.identifier_type, s.identifier,
               pd.survey_cycle, pd.sample_n, pd.is_low_confidence
        FROM population_distribution pd
        LEFT JOIN source s ON s.id = pd.source_id
        WHERE pd.biomarker_id=? AND pd.sex='all' AND pd.age_band='all'
        LIMIT 1
        """,
        (bid,),
    )
    dist = cur.fetchone()
    dist_citation = dist["citation"] if dist else None
    dist_ident = (dist["pmid"] or dist["doi"] or dist["identifier"]) if dist else None
    dist_n = dist["sample_n"] if dist else None
    dist_low_conf = bool(dist["is_low_confidence"]) if dist and dist["is_low_confidence"] is not None else None

    # Known pre-existing defect: the original bulk seeding pass (ids 51-111)
    # left population_distribution.source_id pointing at source id=2 (the
    # Ridker 2000 CRP paper) as an unexamined default for ~35 biomarkers that
    # have nothing to do with CRP. Rather than print that citation as if it
    # were real provenance, flag it. hs-CRP itself is the one legitimate use.
    if dist and dist["citation"] and "C-Reactive Protein and Other Markers" in dist["citation"] and b["slug"] != "high_sensitivity_crp":
        dist_citation = "MISMATCHED PROVENANCE (pre-existing DB defect: source_id defaults to an unrelated CRP paper) - not a real citation for this distribution"
        dist_ident = ""

    # --- Mortality-association provenance: all linked sources, deduped ---
    cur.execute(
        """
        SELECT DISTINCT s.citation, s.pmid, s.doi, s.identifier_type, s.identifier
        FROM mortality_association ma
        LEFT JOIN source s ON s.id = ma.source_id
        WHERE ma.biomarker_id=?
        ORDER BY ma.id
        """,
        (bid,),
    )
    assoc_rows = cur.fetchall()
    if assoc_rows:
        mort_citations = "; ".join(r["citation"] or "" for r in assoc_rows if r["citation"])
        mort_idents = "; ".join(
            (r["pmid"] or r["doi"] or r["identifier"] or "") for r in assoc_rows
        )
    else:
        # No association row: check whether the HR curve declares an
        # explicit unsourced/placeholder provenance instead of silence.
        cur.execute(
            "SELECT citation_summary FROM biomarker_hr_curve WHERE biomarker_id=? "
            "AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        )
        curve = cur.fetchone()
        note = curve["citation_summary"] if curve else None
        mort_citations = f"UNSOURCED - {note}" if note else "UNSOURCED - no provenance recorded"
        mort_idents = ""

    # --- LOINC + other identifiers ---
    cur.execute(
        "SELECT loinc_code, loinc_version, loinc_status, canonical_unit, specimen "
        "FROM lab_tests WHERE canonical_biomarker_id=? LIMIT 1",
        (bid,),
    )
    lt = cur.fetchone()
    loinc_code = lt["loinc_code"] if lt else None
    loinc_status = lt["loinc_status"] if lt else None

    cur.execute(
        """
        SELECT lti.identifier_type, lti.identifier FROM lab_test_identifiers lti
        JOIN lab_tests t ON t.test_id = lti.test_id
        WHERE t.canonical_biomarker_id=?
        """,
        (bid,),
    )
    other_ids = "; ".join(f"{r['identifier_type']}:{r['identifier']}" for r in cur.fetchall())
    if b["nhanes_code"]:
        other_ids = (other_ids + "; " if other_ids else "") + f"NHANES:{b['nhanes_code']}"

    mesh = mesh_cache.get(b["slug"]) or {}

    rows.append(dict(
        biomarker_id=bid,
        slug=b["slug"],
        name=b["name"],
        category=b["category"],
        directionality=b["directionality"],
        distribution_provenance=dist_citation or "",
        distribution_identifier=dist_ident or "",
        distribution_sample_n=dist_n or "",
        distribution_low_confidence="Y" if dist_low_conf else ("" if dist_low_conf is None else "N"),
        mortality_association_provenance=mort_citations,
        mortality_association_identifier=mort_idents,
        loinc_code=loinc_code or "",
        loinc_status=loinc_status or "",
        other_identifiers=other_ids,
        clinicaltrials_gov_mesh_term=mesh.get("mesh_term") or "",
        clinicaltrials_gov_mesh_id=mesh.get("mesh_id") or "",
    ))

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to {OUT}")
mesh_found = sum(1 for r in rows if r["clinicaltrials_gov_mesh_term"])
loinc_found = sum(1 for r in rows if r["loinc_code"])
unsourced = sum(1 for r in rows if r["mortality_association_provenance"].startswith("UNSOURCED"))
print(f"  LOINC coverage: {loinc_found}/{len(rows)}")
print(f"  MeSH coverage: {mesh_found}/{len(rows)}")
print(f"  Unsourced mortality association: {unsourced}/{len(rows)}")

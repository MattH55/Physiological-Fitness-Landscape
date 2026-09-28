"""
Apply the LOINC matches found by _match_loinc.py: for each matched biomarker,
create a `lab_tests` row (test_id, canonical_biomarker_id, test_name,
specimen, canonical_unit, loinc_code, loinc_version, loinc_status) plus the
matching `lab_test_identifiers` GENERIC/LOINC row, following the same
convention the 10 pre-existing entries use. Also stamps
`biomarker.loinc_to_test_id` with the same code for quick lookup.

test_type/method are deliberately left NULL: this pass verifies which LOINC
code identifies each analyte, not what assay technique produces it -
inventing an assay method would be exactly the kind of unverified guess that
produced the wrong hs-CRP/Vitamin D/Ferritin codes this session found and
fixed. A future pass can fill those in from real assay documentation.

Idempotent: skips any biomarker that already has a lab_tests row.

Usage:
  python backend/apply_loinc_matches.py [--dry-run]
"""
import argparse
import json
import re
import sqlite3


def slug_to_test_id(slug: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")
    return f"test_{s}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open("backend/_loinc_match_candidates.json", encoding="utf-8") as f:
        matches = json.load(f)

    conn = sqlite3.connect("data/mortality_biomarkers.db")
    cur = conn.cursor()

    applied = 0
    for slug, m in sorted(matches.items()):
        bid = m["biomarker_id"]
        # Skip if a lab_tests row already exists (idempotency / no clobber).
        cur.execute("SELECT 1 FROM lab_tests WHERE canonical_biomarker_id=?", (bid,))
        if cur.fetchone():
            continue

        cur.execute("SELECT name FROM biomarker WHERE id=?", (bid,))
        row = cur.fetchone()
        if not row:
            continue
        name = row[0]
        cur.execute(
            "SELECT example_ucum_units, loinc_version FROM loinc_reference WHERE loinc_code=?",
            (m["loinc_code"],),
        )
        lr = cur.fetchone()
        unit = lr[0] if lr else None
        loinc_version = lr[1] if lr else None

        test_id = slug_to_test_id(slug)
        print(f"  + {test_id:<45} {m['loinc_code']:<10} {m['long_common_name'][:60]}")

        if args.dry_run:
            applied += 1
            continue

        cur.execute(
            """
            INSERT OR IGNORE INTO lab_tests
            (test_id, canonical_biomarker_id, test_name, test_type, specimen, method,
             canonical_unit, loinc_code, loinc_version, loinc_status)
            VALUES (?, ?, ?, NULL, ?, NULL, ?, ?, ?, 'VERIFIED')
            """,
            (test_id, bid, name, m["system"], unit, m["loinc_code"], loinc_version),
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO lab_test_identifiers
            (test_id, laboratory, identifier_type, identifier)
            VALUES (?, 'GENERIC', 'LOINC', ?)
            """,
            (test_id, m["loinc_code"]),
        )
        cur.execute(
            "UPDATE biomarker SET loinc_to_test_id=? WHERE id=?",
            (json.dumps({"loinc_code": m["loinc_code"], "test_id": test_id}), bid),
        )
        applied += 1

    if not args.dry_run:
        conn.commit()
    print(f"\n{'Would apply' if args.dry_run else 'Applied'}: {applied} biomarkers")
    conn.close()


if __name__ == "__main__":
    main()

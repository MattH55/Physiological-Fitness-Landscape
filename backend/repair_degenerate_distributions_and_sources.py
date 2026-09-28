"""
Repair two metadata defects left by the bulk gap-fill pass.

A. Degenerate population distributions
   ``dna-methylation-age`` has a perfectly good ``normal(loc=0, scale=6.67)``
   DistributionFit, but every stored percentile was written as 0.0. That
   flattens the distribution so HR(P5) == HR(P95) for every probe, which makes
   a monotone hazard curve untestable and silently zeroes the VOI layer for
   that marker. The percentiles are regenerated from the marker's own
   DistributionFit rather than invented.

B. Sources with no verifiable identifier
   Seven ``source`` rows carry a citation and a URL but neither a PMID nor a
   DOI. They are genuine grey-literature / institutional-report references
   (CDC NHANES data files, CDC nutrition and exposure reports, laboratory
   reference-interval pages), so they are not fabrication — they simply predate
   the requirement that every source carry a resolvable identifier. Each is
   stamped with ``identifier_type`` / ``identifier`` derived from its own URL so
   the provenance is machine-checkable.

Both repairs are idempotent.

Usage:
  python backend/repair_degenerate_distributions_and_sources.py
  python backend/repair_degenerate_distributions_and_sources.py --dry-run
"""

import math
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

# Standard normal quantiles for the percentiles the schema stores.
Z = {"p5": -1.6448536269514722, "p25": -0.6744897501960817,
     "p50": 0.0, "p75": 0.6744897501960817, "p95": 1.6448536269514722}

# Institutional / grey-literature sources keyed by their existing URL. The
# identifier is derived from the URL the row already carries, never invented.
URL_IDENTIFIERS = {
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles/FOLFMS_G.htm":
        ("NHANES_DATA_FILE", "FOLFMS_G"),
    "https://www.cdc.gov/nutrition-report/media/pdfs/2026/06/"
    "Trace-Elements-Zinc-508.pdf":
        ("INSTITUTIONAL_REPORT", "CDC-NUTRITION-TRACE-ELEMENTS-ZINC"),
    "https://www.cdc.gov/exposurereport/report/pdf/"
    "Metals%20and%20Metalloids%20NHANES-p.pdf":
        ("INSTITUTIONAL_REPORT", "CDC-EXPOSURE-REPORT-METALS-METALLOIDS"),
    "https://en.wikipedia.org/wiki/Eosinophil":
        ("WEB_REFERENCE", "wikipedia:Eosinophil"),
    "https://en.wikipedia.org/wiki/Reference_ranges_for_blood_tests":
        ("WEB_REFERENCE", "wikipedia:Reference_ranges_for_blood_tests"),
    "https://www.labcorp.com/tests/010181/b2-microglobulin":
        ("LABORATORY_REFERENCE", "labcorp:010181"),
}
# The CDC Second National Report is published as a book with a DOI.
CDC_NUTRITION_DOI = "10.15620/cdc:106318"


def repair_degenerate_distributions(c, dry_run=False):
    """Regenerate all-zero percentiles from the marker's own DistributionFit.

    ``distribution_fit.parameters`` is a JSON blob that already stores the
    fitted mean/sd plus the standard-normal percentiles, so the population row
    is repaired from that source of truth rather than from invented numbers.
    """
    import json

    print("[A] repairing degenerate population distributions...")
    fixed = 0
    rows = c.execute(
        "SELECT biomarker_id, sex, age_band, MIN(p5), MAX(p95) "
        "FROM population_distribution GROUP BY biomarker_id, sex, age_band"
    ).fetchall()
    for bid, sex, age, p5, p95 in rows:
        if p5 is None or p95 is None or p5 != p95:
            continue
        slug = c.execute("SELECT slug FROM biomarker WHERE id=?", (bid,)).fetchone()
        slug = slug[0] if slug else str(bid)

        fit = c.execute(
            "SELECT fit_type, parameters FROM distribution_fit "
            "WHERE biomarker_id=? AND sex=? AND age_band=?",
            (bid, sex, age),
        ).fetchone()
        if not fit:
            print(f"  SKIP {slug} {sex}/{age}: degenerate but no DistributionFit")
            continue
        fit_type, params_raw = fit
        try:
            params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
        except (TypeError, ValueError):
            params = {}
        if fit_type != "normal":
            print(f"  SKIP {slug} {sex}/{age}: fit_type={fit_type} unsupported")
            continue

        mean = params.get("mean")
        sd = params.get("sd")
        if mean is None or sd is None or sd <= 0:
            print(f"  SKIP {slug} {sex}/{age}: fit params lack mean/sd ({params})")
            continue

        vals = {k: params.get(k) for k in ("p5", "p25", "p50", "p75", "p95")}
        if any(v is None for v in vals.values()):
            vals = {k: round(mean + z * sd, 4) for k, z in Z.items()}

        print(f"  {slug:<22} {sex}/{age:<7} "
              f"p5={vals['p5']} p25={vals['p25']} p50={vals['p50']} "
              f"p75={vals['p75']} p95={vals['p95']}")
        if not dry_run:
            c.execute(
                "UPDATE population_distribution SET mean=?, sd=?, p5=?, p25=?, "
                "p50=?, p75=?, p95=? WHERE biomarker_id=? AND sex=? AND age_band=?",
                (mean, sd, vals["p5"], vals["p25"], vals["p50"], vals["p75"],
                 vals["p95"], bid, sex, age),
            )
        fixed += 1
    if not dry_run:
        c.commit()
    print(f"[A] {'would fix' if dry_run else 'fixed'} {fixed} distribution(s)")
    return fixed


def column_exists(c, table, col):
    return any(r[1] == col for r in c.execute(f"PRAGMA table_info({table})"))


def repair_sources(c, dry_run=False):
    """Stamp identifiers on grey-literature sources, or fold them together."""
    print("[B] repairing sources without PMID/DOI...")
    if not column_exists(c, "source", "identifier_type"):
        print("  (adding identifier_type / identifier columns to source)")
        if not dry_run:
            c.execute("ALTER TABLE source ADD COLUMN identifier_type VARCHAR(50)")
            c.execute("ALTER TABLE source ADD COLUMN identifier VARCHAR(200)")

    fixed = 0
    has_ident = column_exists(c, "source", "identifier")
    sql = (
        "SELECT id, url, citation FROM source "
        "WHERE (pmid IS NULL OR pmid='') AND (doi IS NULL OR doi='')"
    )
    if has_ident:
        # Skip rows already stamped by a previous run so this stays idempotent.
        sql += " AND (identifier IS NULL OR identifier='')"
    rows = c.execute(sql).fetchall()
    for sid, url, citation in rows:
        if sid == 318:
            # The reference file whose identifiers back the raw NHANES data
            # files. Not a publication, so it is stamped rather than merged.
            print(f"  {sid:<4} -> reference_data_for={CDC_NUTRITION_DOI} "
                  f"({citation[:44]!r})")
            if not dry_run:
                c.execute(
                    "UPDATE source SET identifier_type=?, identifier=?, "
                    "study_design='reference_data_document' WHERE id=?",
                    ("REFERENCE_DATA_FOR", CDC_NUTRITION_DOI, sid),
                )
            fixed += 1
            continue

        ident = URL_IDENTIFIERS.get(url)
        if not ident:
            print(f"  SKIP {sid}: no identifier derivable for url={url!r}")
            continue
        itype, ivalue = ident
        print(f"  {sid:<4} -> {itype}={ivalue} ({citation[:44]!r})")
        if not dry_run:
            c.execute(
                "UPDATE source SET identifier_type=?, identifier=? WHERE id=?",
                (itype, ivalue, sid),
            )
        fixed += 1

    if not dry_run:
        c.commit()
    print(f"[B] {'would fix' if dry_run else 'fixed'} {fixed} source(s)")
    return fixed


def main():
    dry_run = "--dry-run" in sys.argv
    if not os.path.exists(DB_PATH):
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 2

    if not dry_run:
        bak = DB_PATH + ".bak_degen"
        if not os.path.exists(bak):
            import shutil
            shutil.copy2(DB_PATH, bak)
            print(f"[backup] {os.path.basename(bak)}")

    conn = sqlite3.connect(DB_PATH)
    try:
        repair_degenerate_distributions(conn, dry_run=dry_run)
        print()
        repair_sources(conn, dry_run=dry_run)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


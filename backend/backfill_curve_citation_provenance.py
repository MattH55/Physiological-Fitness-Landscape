"""
Record why 31 gap-fill HR curves have no citation summary.

``biomarker_hr_curve.citation_summary`` is meant to hold the study the curve was
derived from. The bulk gap-fill pass left it NULL for the markers whose curve was
synthesized from a placeholder hazard ratio (``default_assumed`` HR=1.25) rather
than from a published dose-response estimate — which is the honest state, but a
NULL is indistinguishable from "someone forgot".

This script writes an explicit provenance string that says plainly that no study
stands behind the curve, and names the placeholder it was built from. It never
invents a citation. Curves that already carry a summary are untouched, so the
script is idempotent.

Usage:
  python backend/backfill_curve_citation_provenance.py
  python backend/backfill_curve_citation_provenance.py --dry-run
"""

import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

PLACEHOLDER_SUMMARY = (
    "NO PUBLISHED SOURCE. This curve was synthesized from a placeholder hazard "
    "ratio (HR=1.25 quartile_extreme, 'default_assumed') because no "
    "dose-response estimate had been curated for this marker. The displayed "
    "hazard shape is therefore illustrative, not evidence-based, and must be "
    "replaced once a real study is extracted."
)
UNSOURCED_SUMMARY = (
    "NO PUBLISHED SOURCE. No dose-response estimate has been curated for this "
    "marker, so the HR curve carries no study attribution. The displayed hazard "
    "shape is illustrative, not evidence-based."
)


def classify(c, bid):
    """Return the provenance string appropriate to this marker's curves."""
    notes = [r[0] or "" for r in c.execute(
        "SELECT fit_quality_note FROM hr_function WHERE biomarker_id=?", (bid,))]
    blob = " ".join(notes).lower()
    if "default_assumed" in blob or "assumed hr" in blob or \
            "no mortality_association row" in blob:
        return PLACEHOLDER_SUMMARY
    return UNSOURCED_SUMMARY


def repair(c, dry_run=False):
    print("[repair] writing explicit provenance for curves with no summary...")
    rows = c.execute(
        "SELECT hc.id, hc.biomarker_id, b.slug FROM biomarker_hr_curve hc "
        "JOIN biomarker b ON b.id = hc.biomarker_id "
        "WHERE hc.citation_summary IS NULL OR TRIM(hc.citation_summary) = '' "
        "ORDER BY b.id"
    ).fetchall()
    fixed = 0
    seen = {}
    for cid, bid, slug in rows:
        if bid not in seen:
            seen[bid] = classify(c, bid)
        summary = seen[bid]
        kind = "placeholder" if summary is PLACEHOLDER_SUMMARY else "unsourced"
        print(f"  id={cid:<4} {slug:<24} {kind}")
        if not dry_run:
            c.execute(
                "UPDATE biomarker_hr_curve SET citation_summary=? WHERE id=?",
                (summary, cid),
            )
        fixed += 1
    if not dry_run:
        c.commit()
    print(f"[repair] {'would fix' if dry_run else 'fixed'} {fixed} curve(s) "
          f"across {len(seen)} biomarker(s)")
    return fixed


def main():
    dry_run = "--dry-run" in sys.argv
    if not os.path.exists(DB_PATH):
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 2

    if not dry_run:
        bak = DB_PATH + ".bak_prov"
        if not os.path.exists(bak):
            import shutil
            shutil.copy2(DB_PATH, bak)
            print(f"[backup] {os.path.basename(bak)}")

    conn = sqlite3.connect(DB_PATH)
    try:
        repair(conn, dry_run=dry_run)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Repair HR functions whose guardrail domain is inconsistent with the
biomarker's own population distribution, which breaks the
HR(reference_value) == 1.0 normalization contract.

``evaluate_hr_function`` clips the probe value into ``[domain_min, domain_max]``
before evaluating. When a curve's ``reference_value`` falls OUTSIDE its own
guardrail domain, the reference is silently clipped up to the domain floor and
the normalization anchor moves, so HR(reference) explodes instead of being 1.0.

The concrete instance: ``stnfr1`` survives on a ng/mL unit system (population
mean 12.5) but its HR function carries ``domain_min=200``, a leftover from the
duplicated pg/mL rows that were removed as outliers. The reference of 12.0 sits
below the floor, so HR(12) evaluated as 403 instead of 1.0.

This script widens the domain to a physiologically sane envelope around the
marker's own population distribution, and never narrows an existing domain.
It is idempotent.

Usage:
  python backend/repair_hr_function_domain_guardrails.py
  python backend/repair_hr_function_domain_guardrails.py --dry-run
"""

import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")


def find_broken(c):
    """HR functions whose reference_value lies outside their own domain."""
    rows = c.execute(
        "SELECT f.id, f.biomarker_id, b.slug, f.sex, f.age_band, "
        "       f.reference_value, f.domain_min, f.domain_max "
        "FROM hr_function f JOIN biomarker b ON b.id = f.biomarker_id "
        "WHERE f.reference_value IS NOT NULL "
        "  AND f.domain_min IS NOT NULL AND f.domain_max IS NOT NULL "
        "ORDER BY b.id"
    ).fetchall()
    for fid, bid, slug, sex, age, ref, dmin, dmax in rows:
        if ref < dmin or ref > dmax:
            yield fid, bid, slug, sex, age, ref, dmin, dmax


def proposed_domain(c, bid, dmin, dmax):
    """Widen the domain to cover the marker's own distribution envelope.

    Uses the all/all population percentiles when present, expanded by 25% of
    the observed span on each side so the guardrails never bind inside the
    population the curve is meant to describe. Existing wider bounds win.
    """
    row = c.execute(
        "SELECT MIN(p5), MAX(p95), MIN(mean), MAX(sd) FROM population_distribution "
        "WHERE biomarker_id=?",
        (bid,),
    ).fetchone()
    p5, p95, mean, sd = row
    if p5 is None or p95 is None:
        return dmin, dmax

    span = max(p95 - p5, abs(mean or 0.0), 1e-9)
    pad = 0.25 * span
    new_min = min(dmin, p5 - pad)
    new_max = max(dmax, p95 + pad)
    return round(new_min, 6), round(new_max, 6)


def repair(c, dry_run=False):
    print("[repair] widening HR-function domains that exclude their reference...")
    fixed = 0
    for fid, bid, slug, sex, age, ref, dmin, dmax in find_broken(c):
        nmin, nmax = proposed_domain(c, bid, dmin, dmax)
        if nmin <= ref <= nmax and (nmin, nmax) != (dmin, dmax):
            pass
        elif nmin <= ref <= nmax:
            nmin, nmax = dmin, dmax
        if not (nmin <= ref <= nmax):
            print(f"  SKIP {slug} ({sex}/{age}): cannot cover ref={ref} "
                  f"with distribution envelope [{nmin},{nmax}]")
            continue
        if (nmin, nmax) == (dmin, dmax):
            continue
        print(f"  {slug:<24} {sex}/{age:<6} ref={ref} "
              f"domain [{dmin},{dmax}] -> [{nmin},{nmax}]")
        if not dry_run:
            c.execute(
                "UPDATE hr_function SET domain_min=?, domain_max=? WHERE id=?",
                (nmin, nmax, fid),
            )
        fixed += 1
    if not dry_run:
        c.commit()
    print(f"[repair] {'would fix' if dry_run else 'fixed'} {fixed} function(s)")
    return fixed


def main():
    dry_run = "--dry-run" in sys.argv
    if not os.path.exists(DB_PATH):
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 2

    if not dry_run:
        bak = DB_PATH + ".bak_domain"
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

"""
Repair U-shaped biomarkers whose HR curve is actually a monotone ramp.

``selenium`` is documented as U-shaped ("both deficiency and excess associated
with increased mortality", ``optimal_target=100``), and its optimization model
correctly declares ``U_SHAPED``. Its seeded curve, however, is a monotone
``linear_log`` with a negative beta, so HR runs from 19.2 at the domain floor to
0.007 at the ceiling — a straight ramp that never rises again. The directionality
assertions compare the optimum against both domain endpoints, which such a ramp
can never satisfy.

The curve is rebuilt on the same quadratic convention the other U-shaped markers
use (see ``add_missing_curves_and_expected_values.py``):

    ln(HR(x)) = a * (x - x_opt)^2 - a * (reference - x_opt)^2

with ``x_opt`` taken from the biomarker's own ``optimal_target`` and ``a``
calibrated so the 1-SD effect matches the marker's per-SD log(HR) magnitude.
Idempotent: curves already using a U-shaped fit type are left alone.

Usage:
  python backend/repair_ushaped_monotone_curves.py
  python backend/repair_ushaped_monotone_curves.py --dry-run
"""

import json
import math
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

# Fit types that genuinely express a non-monotone (U / J) relationship.
USHAPED_FITS = ("quadratic", "quadratic_u_shaped", "u_shaped")
MONOTONE_FITS = ("linear_log", "log_linear_per_sd", "log_linear_per_unit",
                 "log_log", "power")


def _per_sd_loghr(c, bid):
    """Reuse the marker's own strongest per-SD log(HR) as the magnitude."""
    row = c.execute(
        "SELECT hazard_ratio, hr_type FROM mortality_association "
        "WHERE biomarker_id=? "
        "ORDER BY CASE hr_type WHEN 'per_sd' THEN 0 ELSE 1 END, hazard_ratio DESC "
        "LIMIT 1",
        (bid,),
    ).fetchone()
    if not row or not row[0] or row[0] <= 0:
        return 0.174  # the documented default_assumed placeholder magnitude
    hr, hr_type = row
    log_hr = math.log(hr)
    if hr_type == "quartile_extreme":
        log_hr /= 1.2816
    return log_hr


def find_targets(c):
    """Biomarkers declared U/J shaped whose curve is monotone."""
    rows = c.execute(
        "SELECT b.id, b.slug, b.optimal_target, b.valid_domain_min, "
        "       b.valid_domain_max, o.relationship_type, hc.id, hc.curve_type, "
        "       hc.reference_value "
        "FROM biomarker b "
        "JOIN biomarker_optimization_model o ON o.biomarker_id = b.id "
        "JOIN biomarker_hr_curve hc ON hc.biomarker_id = b.id "
        "WHERE UPPER(o.relationship_type) IN ('U_SHAPED','J_SHAPED') "
        "ORDER BY b.id"
    ).fetchall()
    for (bid, slug, opt_target, dmin, dmax, rel, cid, ctype, ref) in rows:
        if ctype in USHAPED_FITS or ctype not in MONOTONE_FITS:
            continue
        yield bid, slug, opt_target, dmin, dmax, rel, cid, ctype, ref


def repair(c, dry_run=False):
    print("[repair] rebuilding monotone curves on U-shaped markers...")
    fixed = 0
    seen_bids = set()
    for bid, slug, opt_target, dmin, dmax, rel, cid, ctype, ref in find_targets(c):
        if bid in seen_bids:
            continue
        seen_bids.add(bid)
        dist = c.execute(
            "SELECT mean, sd, p50 FROM population_distribution "
            "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        if not dist or not dist[1] or dist[1] <= 0:
            print(f"  SKIP {slug}: no usable population sd")
            continue
        mean, sd, p50 = dist

        # Nadir: the marker's own documented optimum, else the population median.
        x_opt = opt_target if opt_target is not None else (
            p50 if p50 is not None else mean)
        # Reference: anchor the curve where the population actually sits, so
        # HR(reference) == 1.0 lands inside the observed distribution.
        new_ref = p50 if p50 is not None else mean
        if dmin is not None and new_ref < dmin:
            new_ref = dmin
        if dmax is not None and new_ref > dmax:
            new_ref = dmax

        # Calibrate `a` from the per-SD magnitude: one SD away from the nadir
        # the log-HR equals the marker's own per-SD log(HR).
        log_hr_sd = _per_sd_loghr(c, bid)
        a = max(1e-9, log_hr_sd / (sd ** 2))

        params = json.dumps({"a": round(a, 9), "x_opt": round(float(x_opt), 6)})
        print(f"  {bid:>3} {slug:<20} {ctype:<12} -> quadratic "
              f"a={a:.9f} x_opt={x_opt} ref={new_ref} (was ref={ref}, {rel})")
        if not dry_run:
            c.execute(
                "UPDATE biomarker_hr_curve SET curve_type='quadratic', "
                "parameters=?, reference_value=?, optimal_value=?, "
                "citation_summary=COALESCE(NULLIF(TRIM(citation_summary),''), ?) "
                "WHERE biomarker_id=?",
                (params, round(float(new_ref), 6), float(x_opt),
                 f"Quadratic U-shaped fit with nadir at the marker's documented "
                 f"optimal target ({x_opt}); magnitude calibrated to its own "
                 f"per-SD log(HR)={log_hr_sd:.4f}.", bid),
            )
            c.execute(
                "UPDATE hr_function SET fit_type='quadratic_u_shaped', "
                "parameters=?, reference_value=?, nadir_value=?, "
                "shape='u_shaped' WHERE biomarker_id=?",
                (params, round(float(new_ref), 6), float(x_opt), bid),
            )
        fixed += 1
    if not dry_run:
        c.commit()
    print(f"[repair] {'would fix' if dry_run else 'fixed'} {fixed} curve(s)")
    return fixed


def main():
    dry_run = "--dry-run" in sys.argv
    if not os.path.exists(DB_PATH):
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 2

    if not dry_run:
        bak = DB_PATH + ".bak_ushape"
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

"""
Repair directionally-inverted HR curves whose beta sign contradicts the
biomarker's own ``directionality`` flag.

The bulk gap-fill pass synthesized ``log_log`` curves as
``ln(HR) = beta * ln(x / reference)`` but wrote a POSITIVE beta for several
markers whose ``directionality`` is ``higher_better``. A positive beta means
the hazard RISES with the value, which is the opposite of "higher is better",
so the engine reports short telomeres (etc.) as protective. The
``relationship_type`` was flipped to match, which is why the catalog's own
directionality-consistency check did not catch it: the two fields were wrong
together and agreed with each other.

This script flips the sign of beta for those curves only, preserving the
per-SD magnitude the original fit produced. It is idempotent: a curve whose
sign already agrees with its directionality is left alone.

Usage:
  python backend/repair_inverted_curve_signs.py
  python backend/repair_inverted_curve_signs.py --dry-run
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

# ``log_log`` is parameterized as ln(HR) = beta * ln(x / reference).
# Slope sign the directionality requires.
EXPECTED_SIGN = {
    "higher_better": -1,   # hazard falls as x rises
    "lower_better": +1,    # hazard rises as x rises
}


def _expected_loghr_sign(directionality):
    return EXPECTED_SIGN.get((directionality or "").strip().lower())


def find_inverted(c):
    """Yield (id, slug, curve_type, parameters) for sign-inverted curves."""
    rows = c.execute(
        "SELECT b.id, b.slug, b.directionality, "
        "       hc.curve_type, hc.parameters, hc.reference_value "
        "FROM biomarker b "
        "JOIN biomarker_hr_curve hc ON hc.biomarker_id = b.id "
        "ORDER BY b.id"
    ).fetchall()
    for bid, slug, direction, ctype, params_raw, ref in rows:
        want = _expected_loghr_sign(direction)
        if want is None:
            continue
        if ctype != "log_log":
            continue
        params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
        beta = params.get("beta")
        if beta is None or beta == 0.0:
            continue
        # Only flag a genuine sign inversion, never a zero/missing beta.
        if math.copysign(1.0, beta) != want:
            yield bid, slug, direction, ctype, params, ref, want


def repair(c, dry_run=False):
    print("[repair] flipping sign-inverted log_log curves...")
    fixed = 0
    for bid, slug, direction, ctype, params, ref, want in find_inverted(c):
        new_beta = -float(params["beta"])
        new_params = dict(params)
        new_params["beta"] = round(new_beta, 6)
        shape = ("monotonic_decreasing" if want < 0 else "monotonic_increasing")
        note = (
            f"Sign corrected: directionality={direction} requires "
            f"ln(HR) to {'fall' if want < 0 else 'rise'} with x; the seeded "
            f"beta had the opposite sign."
        )
        print(f"  {bid:>3} {slug:<26} beta {params['beta']:+.6f} -> "
              f"{new_beta:+.6f}  shape={shape}")
        if not dry_run:
            c.execute(
                "UPDATE biomarker_hr_curve SET parameters=? WHERE biomarker_id=?",
                (json.dumps(new_params), bid),
            )
            c.execute(
                "UPDATE hr_function SET parameters=?, shape=?, "
                "fit_quality_note=COALESCE(fit_quality_note,'') || ' ' || ? "
                "WHERE biomarker_id=?",
                (json.dumps(new_params), shape, note, bid),
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

    # Back up before the first mutating run so the change is reversible.
    if not dry_run:
        bak = DB_PATH + ".bak_signfix"
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

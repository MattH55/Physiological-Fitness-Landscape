"""
Recalculate mortality HR functions that are effectively flat (HR ≈ constant).

A previous quadratic recalibration bisected `a` until E[HR_0] = 1. For U-shaped
curves normalized at the population median, E[HR_0] is always ≥ 1, so that
bisection drove `a` → 0 and flattened the landscape.

This script:
  1. Detects pooled (all, all) curves whose HR barely moves over p5–p95
     or whose 1-SD RHR is ~0.
  2. Refits them from mortality_association (quartile/per-SD HR) using the
     same conventions as fit_curve_for_biomarker.
  3. For U-shaped markers, sets a so HR(nadir + 1 SD) / HR(nadir) equals the
     published per-SD HR — not so E[HR_0] = 1.
  4. Regenerates the 11 derived sex × age-band curves from the new pooled fit.

Usage:
  python -m backend.recalculate_flat_hr_curves
  python -m backend.recalculate_flat_hr_curves --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.add_missing_curves_and_expected_values import (
    _insert_expected_value_row,
    fit_curve_for_biomarker,
)
from backend.generate_stratum_hr_curves import generate_stratum_curves
from backend.optimization_engine import (
    compute_baseline_expected_hazard,
    compute_shift_optimization,
    evaluate_hr,
    generate_population_distribution,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

HR_RATIO_FLAT = 1.08
RHR_FLAT = 0.02


def _params(params_json) -> dict:
    if not params_json:
        return {}
    if isinstance(params_json, dict):
        return dict(params_json)
    try:
        p = json.loads(params_json)
        return p if isinstance(p, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _curve_span(ctype, ref, opt, params, mean, sd, p5, p50, p95, direction, vmin, vmax):
    xs = []
    for x in (p5, p50, p95, mean - 2 * sd if sd else None, mean + 2 * sd if sd else None, mean):
        if x is not None and math.isfinite(x):
            xs.append(float(x))
    if not xs:
        return 1.0, 0.0
    hrs = [evaluate_hr(x, ctype, ref or 0.0, params, opt) for x in xs]
    lo, hi = min(hrs), max(hrs)
    ratio = (hi / lo) if lo > 0 else 999.0

    if sd is None or sd <= 0:
        return ratio, 0.0
    v_min = vmin if vmin is not None else mean - 4.5 * sd
    v_max = vmax if vmax is not None else mean + 4.5 * sd
    xbins, probs = generate_population_distribution(
        mean, sd, v_min, v_max, n_bins=80, p5=p5, p50=p50, p95=p95
    )
    e0 = e1 = 0.0
    d = (direction or "").lower()
    for x, p in zip(xbins, probs):
        hr0 = evaluate_hr(x, ctype, ref or 0.0, params, opt)
        if d in ("u_shaped", "j_shaped", "inverted_u"):
            target = opt if opt is not None else (p50 if p50 is not None else mean)
            step = min(abs(target - x), sd)
            xsft = x + (1.0 if target > x else -1.0) * step
        elif d in ("lower_better", "monotonic_increasing", "higher_worse"):
            xsft = x - sd
        else:
            xsft = x + sd
        if vmin is not None:
            xsft = max(xsft, vmin)
        if vmax is not None:
            xsft = min(xsft, vmax)
        e0 += p * hr0
        e1 += p * evaluate_hr(xsft, ctype, ref or 0.0, params, opt)
    rhr = (1.0 - e1 / e0) if e0 > 0 else 0.0
    return ratio, rhr


def find_flat_biomarkers(c: sqlite3.Connection):
    rows = c.execute(
        """
        SELECT bm.id, bm.slug, bm.name, bm.directionality,
               bm.valid_domain_min, bm.valid_domain_max,
               cv.curve_type, cv.reference_value, cv.optimal_value, cv.parameters,
               pd.mean, pd.sd, pd.p5, pd.p50, pd.p95
        FROM biomarker bm
        JOIN biomarker_hr_curve cv ON cv.biomarker_id = bm.id
          AND cv.sex = 'all' AND cv.age_band = 'all'
        JOIN population_distribution pd ON pd.biomarker_id = bm.id
          AND pd.sex = 'all' AND pd.age_band = 'all'
        ORDER BY bm.slug
        """
    ).fetchall()
    flat = []
    for row in rows:
        (bid, slug, name, direction, vmin, vmax, ctype, ref, opt, params_json,
         mean, sd, p5, p50, p95) = row
        params = _params(params_json)
        if mean is None or sd is None or sd <= 0:
            continue
        ratio, rhr = _curve_span(
            ctype, ref, opt, params, mean, sd, p5, p50, p95, direction, vmin, vmax
        )
        a = abs(float(params.get("a") or 0.0))
        beta = abs(float(params.get("beta") or 0.0))
        sl = abs(float(params.get("slope_low") or 0.0)) + abs(float(params.get("slope_high") or 0.0))
        is_flat = (
            ratio < HR_RATIO_FLAT
            or abs(rhr) < RHR_FLAT
            or (ctype == "quadratic" and a < 1e-8)
        )
        if is_flat:
            flat.append({
                "id": bid, "slug": slug, "name": name, "direction": direction,
                "curve_type": ctype, "ratio": ratio, "rhr": rhr,
                "a": a, "beta": beta, "slopes": sl,
            })
    return flat


def _u_shaped_a(log_hr_per_sd: float, sd: float) -> float:
    """a such that HR(nadir + 1 SD) / HR(nadir) = exp(log_hr_per_sd)."""
    if sd <= 0:
        return 0.0
    a = log_hr_per_sd / (sd * sd)
    # Keep 3-SD log-HR from hitting the evaluate_hr clip of 5.
    a_max = 4.5 / ((3.0 * sd) ** 2)
    return min(max(a, 1e-12), a_max)


def refit_pooled(c: sqlite3.Connection, bid: int, dry_run: bool) -> dict | None:
    curve = fit_curve_for_biomarker(c, bid)
    if not curve:
        return None

    dist = c.execute(
        "SELECT mean, sd, p50 FROM population_distribution "
        "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
        (bid,),
    ).fetchone()
    mean, sd, p50 = dist if dist else (None, None, None)

    if curve["curve_type"] == "quadratic" and sd and sd > 0:
        log_hr = float(curve.get("log_hr_per_sd") or 0.223)
        x_opt = curve.get("optimal_value")
        if x_opt is None:
            x_opt = p50 if p50 is not None else mean
        a = _u_shaped_a(log_hr, sd)
        curve["parameters"] = {"a": round(a, 8), "x_opt": round(float(x_opt), 4)}
        curve["optimal_value"] = round(float(x_opt), 4)
        if p50 is not None:
            curve["reference_value"] = round(float(p50), 4)

    params_json = json.dumps(curve["parameters"])
    fit_type_map = {
        "log_log": "log_log",
        "linear_log": "log_linear_per_sd",
        "quadratic": "quadratic_u_shaped",
        "piecewise": "piecewise_linear",
    }
    fit_type = fit_type_map.get(curve["curve_type"], curve["curve_type"])
    d = (curve.get("directionality") or "").lower()
    if curve["curve_type"] == "quadratic":
        shape = "u_shaped"
    elif d == "higher_better":
        shape = "monotonic_decreasing"
    else:
        shape = "monotonic_increasing"

    note = (
        f"Recalculated from mortality_association "
        f"(HR={curve.get('source_hazard_ratio')} {curve.get('source_hr_type')}); "
        f"per-SD log(HR)={curve.get('log_hr_per_sd')}."
    )

    if not dry_run:
        c.execute(
            """
            UPDATE biomarker_hr_curve
            SET curve_type=?, reference_value=?, optimal_value=?, parameters=?,
                citation_summary=?
            WHERE biomarker_id=? AND sex='all' AND age_band='all'
            """,
            (
                curve["curve_type"],
                curve["reference_value"],
                curve["optimal_value"],
                params_json,
                note[:300],
                bid,
            ),
        )
        c.execute(
            """
            UPDATE hr_function
            SET fit_type=?, parameters=?, reference_value=?, shape=?,
                nadir_value=?, fit_quality_note=?
            WHERE biomarker_id=? AND sex='all' AND age_band='all'
            """,
            (
                fit_type,
                params_json,
                curve["reference_value"],
                shape,
                curve["optimal_value"],
                note[:300],
                bid,
            ),
        )
    return curve


def recompute_expected_for(c: sqlite3.Connection, bids: list[int], dry_run: bool):
    scenarios = c.execute(
        "SELECT id, slug, shift_type, shift_magnitude FROM optimization_scenario"
    ).fetchall()
    cur = c.cursor()
    for bid in bids:
        b = cur.execute(
            "SELECT name, directionality, valid_domain_min, valid_domain_max, optimal_target "
            "FROM biomarker WHERE id=?",
            (bid,),
        ).fetchone()
        d = cur.execute(
            "SELECT mean, sd, p5, p50, p95 FROM population_distribution "
            "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        curve = cur.execute(
            "SELECT curve_type, reference_value, optimal_value, parameters, valid_min, valid_max "
            "FROM biomarker_hr_curve WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        if not b or not d or not curve or not d[1]:
            continue
        name, direction, v_min, v_max, optimal = b
        mean, sd, p5, p50, p95 = d
        curve_type, ref, curve_opt, params_json, cv_min, cv_max = curve
        params = _params(params_json)
        v_min_eff = v_min if v_min is not None else (cv_min if cv_min is not None else mean - 4.5 * sd)
        v_max_eff = v_max if v_max is not None else (cv_max if cv_max is not None else mean + 4.5 * sd)
        if v_max_eff <= v_min_eff:
            v_min_eff, v_max_eff = mean - 4.5 * sd, mean + 4.5 * sd
        x_bins, probs = generate_population_distribution(
            mean, sd, v_min_eff, v_max_eff, n_bins=300, p5=p5, p50=p50, p95=p95
        )
        base_ehr, base_hrs = compute_baseline_expected_hazard(
            x_bins, probs, curve_type, ref, params, curve_opt
        )
        if dry_run:
            print(f"    (dry-run) {name}: base EHR={base_ehr:.3f}")
            continue
        cur.execute("DELETE FROM biomarker_expected_value WHERE biomarker_id=?", (bid,))
        rhr100 = None
        for sc_id, sc_slug, sc_type, sc_mag in scenarios:
            res = compute_shift_optimization(
                x_bins=x_bins,
                probabilities=probs,
                baseline_hrs=base_hrs,
                curve_type=curve_type,
                reference_value=ref,
                parameters=params,
                valid_min=v_min_eff,
                valid_max=v_max_eff,
                directionality=direction,
                pop_sd=sd,
                shift_type=sc_type,
                shift_magnitude=sc_mag,
                optimal_value=curve_opt,
                pop_median=p50,
            )
            _insert_expected_value_row(cur, bid, sc_id, res)
            if sc_slug == "sd_100":
                rhr100 = res["relative_hazard_reduction"]
        print(f"    {name}: base EHR={base_ehr:.3f}  1-SD RHR={(rhr100 or 0)*100:.1f}%")
    if not dry_run:
        c.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    c = sqlite3.connect(DB_PATH)
    flat = find_flat_biomarkers(c)
    print(f"Found {len(flat)} flat pooled HR curves:\n")
    print(f"{'slug':32} {'type':12} {'ratio':8} {'RHR':8}")
    for f in flat:
        print(f"{f['slug'][:32]:32} {f['curve_type']:12} {f['ratio']:8.3f} {f['rhr']:8.3f}")

    updated = []
    print("\nRefitting pooled (all, all) curves...")
    for f in flat:
        curve = refit_pooled(c, f["id"], dry_run=args.dry_run)
        if not curve:
            print(f"  ! {f['slug']}: could not refit")
            continue
        print(
            f"  {f['slug'][:32]:32} {curve['curve_type']:10} "
            f"p={curve['parameters']} ref={curve['reference_value']}"
        )
        updated.append(f["id"])
    if not args.dry_run:
        c.commit()

    if updated and not args.dry_run:
        print("\nRegenerating sex × age-band curves from new pooled fits...")
        c.close()
        generate_stratum_curves(DB_PATH)
        c = sqlite3.connect(DB_PATH)
        print("\nRecomputing expected-value / RHR rows for refit biomarkers...")
        recompute_expected_for(c, updated, dry_run=False)

        still = find_flat_biomarkers(c)
        print(f"\nRemaining flat after refit: {len(still)}")
        for f in still:
            print(f"  {f['slug']} ratio={f['ratio']:.3f} RHR={f['rhr']:.3f}")
    elif args.dry_run:
        print("\n(dry-run: no writes)")

    c.close()


if __name__ == "__main__":
    main()

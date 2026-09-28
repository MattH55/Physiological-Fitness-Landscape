"""
Add missing HR curves (biomarker_hr_curve + hr_function) for biomarkers that
lack them, then recompute biomarker_expected_value for ALL biomarkers so every
one has a 1.0-SD RHR (relative hazard reduction) to display.

Two gaps in the current DB:
  1. 36 biomarkers have NO HR curve at all (they were never seeded with one).
     We synthesize a log_log (or quadratic for U-shaped) curve calibrated from
     their mortality_association HRs using the standard quartile_extreme
     approximation:  per-SD log(HR) = ln(HR_quartile) / 1.2816.
  2. Only 50 of 125 biomarkers have rows in biomarker_expected_value.
     We run the existing optimization_engine on all 125 to generate the
     full 6-scenario set.

Usage:
  python backend/add_missing_curves_and_expected_values.py
  python backend/add_missing_curves_and_expected_values.py --dry-run
"""

import json
import math
import os
import sqlite3
import sys

# Force UTF-8 stdout/stderr so PowerShell does not crash on unicode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.optimization_engine import (
    generate_population_distribution,
    compute_baseline_expected_hazard,
    compute_shift_optimization,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

QUARTILE_LOGSD = 1.2816  # ln(HR_per_sd) ≈ ln(HR_quartile) / 1.2816


def round_sig(x, sig=6):
    """Round to `sig` significant figures instead of fixed decimal places,
    so small-magnitude coefficients (large-domain biomarkers) don't collapse
    to 0.0 the way round(x, 6) does."""
    if x == 0:
        return 0.0
    return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


# =======================================================================
# Part 1: Add missing HR curves
# =======================================================================

def fit_curve_for_biomarker(c: sqlite3.Connection, bid: int):
    """
    Return (curve_dict, fit_note) or None if not enough information.
    Curve params follow the same conventions as existing biomarker_hr_curve rows:
      log_log:    {"beta": <per-SD log(HR) scaled>}
      linear_log: {"beta": <per-unit log(HR)>}
      quadratic:  {"a": <a>, "x_opt": <optimal>}
    """
    row = c.execute(
        "SELECT id, name, directionality, valid_domain_min, valid_domain_max, "
        "optimal_target, notes FROM biomarker WHERE id=?",
        (bid,),
    ).fetchone()
    if not row:
        return None
    _, name, direction, v_min, v_max, optimal, notes = row

    # Population distribution (all/all)
    dist = c.execute(
        "SELECT mean, sd, p5, p50, p95 FROM population_distribution "
        "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
        (bid,),
    ).fetchone()
    if not dist or dist[1] is None or dist[1] <= 0:
        return None
    mean, sd, p5, p50, p95 = dist

    # HR from mortality_association. Prefer per_sd if available, else quartile_extreme.
    assoc = c.execute(
        "SELECT hazard_ratio, hr_type, hr_unit_scale, direction, notes "
        "FROM mortality_association WHERE biomarker_id=? "
        "ORDER BY CASE hr_type WHEN 'per_sd' THEN 0 WHEN 'quartile_extreme' THEN 1 "
        "WHEN 'tertile_extreme' THEN 2 ELSE 3 END, hazard_ratio DESC LIMIT 1",
        (bid,),
    ).fetchone()
    if assoc and assoc[0] and assoc[0] != 1.0:
        hr_reported, hr_type, hr_unit, direction_assoc, assoc_notes = assoc
    else:
        # No association data. Fall back to a modest default per-SD HR of 1.25.
        hr_reported, hr_type, hr_unit, direction_assoc, assoc_notes = (
            1.25, "default_assumed", 1.0, direction,
            "No mortality_association row; assumed HR=1.25 (quartile_extreme).",
        )

    # Compute per-SD log(HR)
    if hr_type == "per_sd":
        log_hr_per_sd = math.log(hr_reported) / (hr_unit or 1.0)
    elif hr_type == "tertile_extreme":
        log_hr_per_sd = math.log(hr_reported) / (QUARTILE_LOGSD * 1.15)
    else:  # quartile_extreme or unknown
        log_hr_per_sd = math.log(hr_reported) / QUARTILE_LOGSD

    # Magnitude only: the sign is reassigned below purely from the biomarker's
    # own directionality, so a protective (HR<1) per-SD association must be
    # abs()'d here rather than clamped straight to the 0.05 floor.
    log_hr_per_sd = abs(log_hr_per_sd)
    # Sanity bounds: 0.05 - 2.0 per SD
    log_hr_per_sd = max(0.05, min(2.0, log_hr_per_sd))

    # Shape is decided by the biomarker's own curated directionality, not by
    # the association's reported direction: a study can report a u_shaped
    # (or otherwise mismatched) effect in a narrow subgroup/disease cohort
    # while the biomarker itself is curated as monotonic in the general
    # population (e.g. MCP-1, testosterone) - the curated value wins.
    u_shaped = direction == "u_shaped"

    # Reference value: p50 of the population if positive, else mid-domain
    ref = p50 if (p50 is not None and p50 > 0) else (mean if mean > 0 else (v_min + v_max) / 2)

    if u_shaped:
        x_opt = optimal if (optimal is not None and optimal > 0) else ref
        target_log_hr = log_hr_per_sd * 2.0
        offset = max(abs(ref - x_opt), 0.5 * sd, 1e-3)
        a = target_log_hr / (offset * offset)
        # Guard against a domain edge far from x_opt turning a curve
        # calibrated on a narrow (ref, x_opt, sd) offset into an
        # exponential blowup: cap so HR at the farthest domain boundary
        # never exceeds 8x (a generous allowance for a physiological
        # extreme, well outside the [0.5, 5.0] range expected near the
        # population's typical spread).
        worst_offset = max(abs(v_min - x_opt), abs(v_max - x_opt)) if (v_min is not None and v_max is not None) else offset
        if worst_offset > 0:
            max_log_hr_at_boundary = math.log(8.0)
            a = min(a, max_log_hr_at_boundary / (worst_offset * worst_offset))
        curve_type = "quadratic"
        # round(a, 6) silently zeroes "a" out for biomarkers with a large
        # native domain (mtDNA copy number, appendicular lean mass, etc.),
        # where a is legitimately ~1e-7 or smaller, producing a flat curve.
        # Round to significant figures instead of fixed decimal places.
        params = {"a": round_sig(a, 6), "x_opt": round(x_opt, 4)}
        optimal_value = round(x_opt, 4)
    else:
        if v_min is not None and v_min <= 0:
            curve_type = "linear_log"
            beta = log_hr_per_sd / sd
        else:
            curve_type = "log_log"
            beta = log_hr_per_sd * ref / sd if sd > 0 else log_hr_per_sd
        params = {"beta": round(beta, 6)}
        optimal_value = None

    if curve_type != "quadratic":
        if direction == "higher_better":
            params["beta"] = -abs(params["beta"])
        elif direction == "lower_better":
            params["beta"] = abs(params["beta"])

    return {
        "biomarker_id": bid,
        "name": name,
        "curve_type": curve_type,
        "reference_value": round(float(ref), 4),
        "optimal_value": optimal_value,
        "parameters": params,
        "valid_min": v_min,
        "valid_max": v_max,
        "directionality": direction,
        "source_hazard_ratio": hr_reported,
        "source_hr_type": hr_type,
        "log_hr_per_sd": round(log_hr_per_sd, 4),
        "citation_summary": (
            f"Synthesized from mortality_association (HR={hr_reported} {hr_type}); "
            f"per-SD log(HR)={log_hr_per_sd:.3f}. {assoc_notes[:150] if assoc_notes else ''}"
        ),
    }


STRATA = [
    ("all", "all"),
    ("M", "all"),
    ("F", "all"),
    ("all", "20-39"),
    ("all", "40-59"),
    ("all", "60+"),
]


def insert_missing_curves(c: sqlite3.Connection, dry_run=False):
    existing = set(
        r[0] for r in c.execute("SELECT DISTINCT biomarker_id FROM biomarker_hr_curve")
    )
    all_bm = set(r[0] for r in c.execute("SELECT id FROM biomarker"))
    to_add = sorted(all_bm - existing)

    print(f"[Part 1] {len(to_add)} biomarkers missing curves: {to_add}")

    cur = c.cursor()
    for bid in to_add:
        curve = fit_curve_for_biomarker(c, bid)
        if not curve:
            print(f"  ! {bid}: could not fit (missing data)")
            continue
        print(
            f"  + {bid} {curve['name'][:45]:<45} {curve['curve_type']:<10} "
            f"p={curve['parameters']} "
            f"ref={curve['reference_value']:<8} "
            f"opt={curve['optimal_value']} "
            f"(HR {curve['source_hazard_ratio']} {curve['source_hr_type']})"
        )
        if dry_run:
            continue

        for sex, age in STRATA:
            cur.execute(
                """
                INSERT OR IGNORE INTO biomarker_hr_curve
                (biomarker_id, sex, age_band, curve_type, reference_value, optimal_value,
                 parameters, valid_min, valid_max, citation_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bid, sex, age,
                    curve["curve_type"],
                    curve["reference_value"],
                    curve["optimal_value"],
                    json.dumps(curve["parameters"]),
                    curve["valid_min"],
                    curve["valid_max"],
                    curve["citation_summary"],
                ),
            )

        fit_type_map = {
            "log_log": "log_log",
            "linear_log": "log_linear_per_sd",
            "quadratic": "quadratic_u_shaped",
        }
        fit_type = fit_type_map[curve["curve_type"]]
        shape = (
            "u_shaped"
            if curve["curve_type"] == "quadratic"
            else ("monotonic_increasing" if curve["directionality"] == "lower_better"
                  else "monotonic_decreasing")
        )
        for sex, age in STRATA:
            cur.execute(
                """
                INSERT OR IGNORE INTO hr_function
                (biomarker_id, sex, age_band, fit_type, parameters, domain_min, domain_max,
                 reference_value, shape, nadir_value, source_id, fit_quality_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    bid, sex, age,
                    fit_type,
                    json.dumps(curve["parameters"]),
                    curve["valid_min"],
                    curve["valid_max"],
                    curve["reference_value"],
                    shape,
                    curve["optimal_value"],
                    curve["citation_summary"],
                ),
            )
    c.commit()


# =======================================================================
# Part 2: Recompute expected values for all biomarkers
# =======================================================================

def compute_and_insert_expected_values(c: sqlite3.Connection, dry_run=False):
    print("\n[Part 2] Computing expected values for all biomarkers...")
    scenarios = c.execute(
        "SELECT id, slug, shift_type, shift_magnitude FROM optimization_scenario"
    ).fetchall()
    all_bm = [r[0] for r in c.execute("SELECT id FROM biomarker ORDER BY id")]
    cur = c.cursor()
    ok = 0
    fail = 0

    for bid in all_bm:
        b = cur.execute(
            "SELECT name, directionality, valid_domain_min, valid_domain_max, optimal_target "
            "FROM biomarker WHERE id=?",
            (bid,),
        ).fetchone()
        if not b:
            continue
        name, direction, v_min, v_max, optimal = b

        d = cur.execute(
            "SELECT mean, sd, p5, p50, p95 FROM population_distribution "
            "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        if not d or d[0] is None or d[1] is None or d[1] <= 0:
            print(f"  ! {bid} {name[:45]}: no population distribution")
            fail += 1
            continue
        mean, sd, p5, p50, p95 = d

        curve = cur.execute(
            "SELECT curve_type, reference_value, optimal_value, parameters, valid_min, valid_max "
            "FROM biomarker_hr_curve WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        if not curve:
            print(f"  ! {bid} {name[:45]}: no curve")
            fail += 1
            continue
        curve_type, ref, curve_opt, params_json, cv_min, cv_max = curve
        params = json.loads(params_json) if params_json else {}
        if curve_opt is not None:
            params.setdefault("x_opt", curve_opt)

        # Use the biomarker's own physiological domain (v_min/v_max) when it
        # is strictly inside the curve's evaluation domain, otherwise fall
        # back to the curve's domain.
        if cv_min is None:
            v_min_eff = v_min if v_min is not None else (0.0 if mean > 0 else -5 * sd)
        elif v_min is None:
            v_min_eff = cv_min
        else:
            v_min_eff = v_min if v_min >= cv_min else cv_min
        if cv_max is None:
            v_max_eff = v_max if v_max is not None else (mean + 5 * sd)
        elif v_max is None:
            v_max_eff = cv_max
        else:
            v_max_eff = v_max if v_max <= cv_max else cv_max
        if v_max_eff <= v_min_eff:
            v_min_eff = 0.0 if mean > 0 else -5 * sd
            v_max_eff = mean + 5 * sd

        x_bins, probs = generate_population_distribution(
            mean=mean, sd=sd, valid_min=v_min_eff, valid_max=v_max_eff,
            n_bins=300, p5=p5, p50=p50, p95=p95,
        )
        base_ehr, base_hrs = compute_baseline_expected_hazard(
            x_bins, probs, curve_type, ref, params, curve_opt
        )

        rows = []
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
                pop_p25=None,
                pop_p75=None,
            )
            rows.append((bid, sc_id, res))

        sd100 = next((r for r in rows if r[1] == 3), None)
        if sd100:
            rhr = sd100[2]["relative_hazard_reduction"] * 100
            print(f"  {bid:>3} {name[:45]:<45} 1SD RHR = {rhr:5.2f}%  (base {base_ehr:.3f})")
        ok += 1

        if not dry_run:
            cur.execute(
                "DELETE FROM biomarker_expected_value WHERE biomarker_id=?", (bid,)
            )
            for bid_r, sc_id, res in rows:
                _insert_expected_value_row(cur, bid_r, sc_id, res)

    c.commit()
    print(f"\n  {ok} biomarkers computed, {fail} failed.")
    if not dry_run:
        n = cur.execute("SELECT COUNT(*) FROM biomarker_expected_value").fetchone()[0]
        n_bm = cur.execute(
            "SELECT COUNT(DISTINCT biomarker_id) FROM biomarker_expected_value"
        ).fetchone()[0]
        print(f"  Inserted {n} expected_value rows covering {n_bm} biomarkers.")


def _insert_expected_value_row(cur, bid, sc_id, res):
    cur.execute(
        """
        INSERT INTO biomarker_expected_value
        (biomarker_id, scenario_id, baseline_expected_hr, optimized_expected_hr,
         delta_hr, relative_hazard_reduction, domain_status, fraction_out_of_domain,
         mean_individual_benefit, median_individual_benefit, p10_benefit, p25_benefit,
         p75_benefit, p90_benefit, max_individual_benefit, fraction_benefiting,
         fraction_harmed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bid, sc_id,
            res["baseline_expected_hr"],
            res["optimized_expected_hr"],
            res["delta_hr"],
            res["relative_hazard_reduction"],
            res["domain_status"],
            res["fraction_out_of_domain"],
            res["mean_individual_benefit"],
            res["median_individual_benefit"],
            res["p10_benefit"],
            res["p25_benefit"],
            res["p75_benefit"],
            res["p90_benefit"],
            res["max_individual_benefit"],
            res["fraction_benefiting"],
            res["fraction_harmed"],
        ),
    )


# =======================================================================
# Part 0: Data curation -- fix out-of-domain distributions and
#         directionally-incorrect monotonic curves BEFORE curve fitting.
# =======================================================================

# Out-of-domain / implausible seeded distributions, corrected in-place.
# The engine integrates a normal density over the VALID DOMAIN (see
# generate_population_distribution), so a distribution whose mass lies
# outside the domain yields a degenerate grid and implausibly large
# relative hazard reductions.  Fixing the distribution (and the domain
# where the seeded one was wrong) restores an in-domain density whose
# integral over the evaluated range is 1.
DISTRIBUTION_OVERRIDES = {
    # Waist-to-Height Ratio: ratio, not cm.
    107: dict(mean=0.52, sd=0.08, unit="ratio"),
    # Transferrin Saturation: the 30% / 9 SD stratum had implausible
    # percentiles; keep the mean and rebuild the quantiles from the normal.
    100: dict(mean=30.0, sd=9.0, unit="%", rebuild_quantiles=True),
    # DNA methylation age acceleration is centered at 0 by construction.
    90:  dict(mean=0.0, sd=4.0, unit="years"),
    # D-dimer: distribution was seeded in ng/mL (FEU) while the curve and
    # valid domain use ug/mL.
    81:  dict(mean=0.28, sd=0.25, unit="ug/mL"),
    # suPAR: distribution was seeded in ng/mL while the curve and valid
    # domain (0-20) use ng/L.  All strata rescaled by /1000.
    73:  dict(mean=3.2, sd=1.8, unit="ng/L"),
    # Free T3 (pg/mL assay): the U-curve optimum was seeded below the
    # population center; move it to the clinical mid-normal (3.2 pg/mL).
    62:  dict(mean=3.1, sd=0.7, unit="pg/mL", x_opt=3.2),
    # Transferrin saturation (%): U-curve optimum was seeded at 98%
    # (outside the 5-80% domain); move to the population center.
    114: dict(mean=25.0, sd=10.0, unit="%", x_opt=25.0),
}

# Domains that were seeded with the wrong magnitude and must be rescaled
# for the corrected distributions to be in-frame.
DOMAIN_FIXES = {
    # D-dimer: valid domain was seeded 0-10 (ug/mL scale); the distribution
    # in ng/mL needs the domain in the same unit.
    81:  (0.0, 1500.0),
}


def _apply_distribution_overrides(c: sqlite3.Connection, dry_run=False):
    print("\n[Part 0a] Applying distribution overrides for out-of-domain data...")
    cur = c.cursor()
    for bid, fix in DISTRIBUTION_OVERRIDES.items():
        # Rescale a seeded domain that was in the wrong unit/magnitude.
        if bid in DOMAIN_FIXES:
            new_dmin, new_dmax = DOMAIN_FIXES[bid]
            currow = c.execute(
                "SELECT valid_domain_min, valid_domain_max FROM biomarker WHERE id=?",
                (bid,),
            ).fetchone()
            if currow and (currow[0], currow[1]) != (new_dmin, new_dmax):
                if not dry_run:
                    cur.execute(
                        "UPDATE biomarker SET valid_domain_min=?, valid_domain_max=? WHERE id=?",
                        (new_dmin, new_dmax, bid),
                    )
                    # Keep the curve evaluation domains consistent.
                    cur.execute(
                        "UPDATE biomarker_hr_curve SET valid_min=?, valid_max=? "
                        "WHERE biomarker_id=? AND (valid_min IS NULL OR valid_max IS NULL)",
                        (new_dmin, new_dmax, bid),
                    )
                    cur.execute(
                        "UPDATE hr_function SET domain_min=?, domain_max=? "
                        "WHERE biomarker_id=? AND (domain_min IS NULL OR domain_max IS NULL)",
                        (new_dmin, new_dmax, bid),
                    )
                print(f"  {bid:>3} domain rescaled -> [{new_dmin}, {new_dmax}]")

        # Relocate a U-curve optimum that was seeded outside the
        # population domain (or below the population center).
        if "x_opt" in fix:
            params = c.execute(
                "SELECT parameters FROM biomarker_hr_curve "
                "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
                (bid,),
            ).fetchone()
            if params and params[0]:
                p = json.loads(params[0])
                old = p.get("x_opt")
                if old != fix["x_opt"]:
                    p["x_opt"] = fix["x_opt"]
                    if not dry_run:
                        cur.execute(
                            "UPDATE biomarker_hr_curve SET parameters=?, optimal_value=? "
                            "WHERE biomarker_id=?",
                            (json.dumps(p), fix["x_opt"], bid),
                        )
                        cur.execute(
                            "UPDATE hr_function SET parameters=?, nadir_value=? "
                            "WHERE biomarker_id=?",
                            (json.dumps(p), fix["x_opt"], bid),
                        )
                    print(f"  {bid:>3} U-curve optimum {old} -> {fix['x_opt']}")
        nrow = c.execute("SELECT name FROM biomarker WHERE id=?", (bid,)).fetchone()
        name = nrow[0] if nrow else "?"
        domain = c.execute(
            "SELECT valid_domain_min, valid_domain_max FROM biomarker WHERE id=?",
            (bid,),
        ).fetchone()
        v_min, v_max = domain if domain else (None, None)
        rows = cur.execute(
            "SELECT id, mean, sd, p5, p25, p50, p75, p95, unit "
            "FROM population_distribution WHERE biomarker_id=? ORDER BY id",
            (bid,),
        ).fetchall()
        fixed = 0
        for rid, mean, sd, p5, p25, p50, p75, p95, unit in rows:
            if mean is None or sd is None or sd <= 0:
                continue
            # Skip only strata already at the override target (idempotence).
            # NOTE: the earlier "skip if mean in domain" guard was WRONG:
            # after a previous run rescaled the valid domain (e.g. D-dimer
            # -> [0, 1500]) the seeded ng/mL distribution (mean=285) sat
            # INSIDE the domain yet was still the wrong unit, so the
            # conversion to the override unit (ug/mL) never ran.  Compare
            # against the target mean instead.
            if abs(mean - fix["mean"]) <= 1e-9 * max(1.0, abs(fix["mean"])):
                continue
            scale = fix["mean"] / mean if mean else 1.0
            nsd = max(fix["sd"], 1e-6)
            if fix.get("rebuild_quantiles"):
                # The stratum's percentiles are implausible; rebuild them
                # from the (corrected) normal mean/sd.
                n_p5 = fix["mean"] - 1.645 * nsd
                n_p25 = fix["mean"] - 0.674 * nsd
                n_p50 = fix["mean"]
                n_p75 = fix["mean"] + 0.674 * nsd
                n_p95 = fix["mean"] + 1.645 * nsd
            else:
                n_p5 = p5 * scale if p5 is not None else fix["mean"] - 1.645 * nsd
                n_p25 = p25 * scale if p25 is not None else fix["mean"] - 0.674 * nsd
                n_p50 = p50 * scale if p50 is not None else fix["mean"]
                n_p75 = p75 * scale if p75 is not None else fix["mean"] + 0.674 * nsd
                n_p95 = p95 * scale if p95 is not None else fix["mean"] + 1.645 * nsd
            if not dry_run:
                cur.execute(
                    "UPDATE population_distribution SET mean=?, sd=?, p5=?, p25=?, "
                    "p50=?, p75=?, p95=?, unit=? WHERE id=?",
                    (round(fix["mean"], 4), round(nsd, 4), round(n_p5, 4),
                     round(n_p25, 4), round(n_p50, 4), round(n_p75, 4),
                     round(n_p95, 4), fix["unit"], rid),
                )
            fixed += 1
        print(f"  {bid:>3} {name[:42]:<42} -> mean={fix['mean']} sd={fix['sd']} "
              f"({fixed} strata)")
    if not dry_run:
        c.commit()
        print(f"  Corrected {len(DISTRIBUTION_OVERRIDES)} biomarkers across strata.")
    else:
        print("  (dry-run: no writes made)")


def _per_sd_loghr_for(bid: int, c: sqlite3.Connection, default: float = 0.58) -> float:
    """
    Per-SD log(HR) magnitude for a biomarker, derived from its strongest
    mortality_association row.  Used to rescale seeded monotonic curves
    whose direction is correct but whose magnitude is too extreme (or too
    flat) to produce plausible 1-SD hazard reductions.
    """
    assoc = c.execute(
        "SELECT hazard_ratio, hr_type, hr_unit_scale FROM mortality_association "
        "WHERE biomarker_id=? ORDER BY hazard_ratio DESC LIMIT 1",
        (bid,),
    ).fetchone()
    if not assoc or not assoc[0] or assoc[0] <= 1.0:
        return default
    hr, hr_type, hr_unit = assoc
    if hr_type == "per_sd":
        per_sd = math.log(hr) / (hr_unit or 1.0)
    elif hr_type == "tertile_extreme":
        per_sd = math.log(hr) / (QUARTILE_LOGSD * 1.15)
    else:  # quartile_extreme or unknown
        per_sd = math.log(hr) / QUARTILE_LOGSD
    return max(0.05, min(2.0, per_sd))


def _fix_monotonic_curve_signs(c: sqlite3.Connection, dry_run=False):
    """Fix higher_better monotonic curves whose seeded log_log form points the
    wrong way / is undefined over part of the domain.

    * #124 (beta-2 microglobulin) and #104 (BMD T-score): replace with a
      linear_log curve whose hazard DECREASES as x increases (negative
      beta in the ln(HR)=beta*(x-ref) convention), with the per-SD
      magnitude rescaled from the strongest mortality_association row so
      the resulting 1-SD hazard reduction is plausible (~10-40%).
    * #71 (serum selenium): seeded curve points the wrong way
      (higher_better with POSITIVE beta).  Rebuild the same way."""
    print("\n[Part 0b] Fixing directionally-incorrect monotonic curves...")
    cur = c.cursor()
    for bid in (124, 104, 71):
        b = c.execute(
            "SELECT name, valid_domain_min, valid_domain_max FROM biomarker WHERE id=?",
            (bid,),
        ).fetchone()
        if not b:
            continue
        stat = c.execute(
            "SELECT mean, sd, p50 FROM population_distribution "
            "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        if not stat or stat[1] is None or stat[1] <= 0:
            continue
        mean, sd, p50 = stat
        # For a higher_better marker the hazard must DECREASE as x
        # increases, which requires a NEGATIVE beta in the linear_log
        # form ln(HR)=beta*(x-ref) (same sign convention as
        # fit_curve_for_biomarker).  Magnitude comes from the
        # biomarker's own mortality association (plausible per-SD HR).
        log_hr_per_sd = _per_sd_loghr_for(bid, c)
        beta = -log_hr_per_sd / sd
        ref = p50 if (p50 is not None and p50 > 0) else mean
        params_json = json.dumps({"beta": round(beta, 6)})
        if not dry_run:
            cur.execute(
                "UPDATE biomarker_hr_curve SET curve_type='linear_log', "
                "parameters=?, reference_value=?, optimal_value=NULL "
                "WHERE biomarker_id=?",
                (params_json, round(ref, 4), bid),
            )
            cur.execute(
                "UPDATE hr_function SET fit_type='log_linear_per_sd', "
                "parameters=?, reference_value=?, nadir_value=NULL, "
                "shape='monotonic_decreasing' WHERE biomarker_id=?",
                (params_json, round(ref, 4), bid),
            )
        print(f"  {bid:>3} {b[0][:42]:<42} -> linear_log beta={beta:.4f} "
              f"ref={ref:.3f} (higher_better)")
    if not dry_run:
        c.commit()
    else:
        print("  (dry-run: no writes made)")


def apply_data_curation(c: sqlite3.Connection, dry_run=False):
    _apply_distribution_overrides(c, dry_run=dry_run)
    _fix_monotonic_curve_signs(c, dry_run=dry_run)


# =======================================================================
# Part 3: Generalized recalibration of over-steep quadratic U-curves
# =======================================================================

def _effective_domain_quad(v_min, v_max, cv_min, cv_max, mean, sd):
    """
    Compute the effective evaluation domain for a quadratic curve, using the
    EXACT same logic as compute_and_insert_expected_values so that Part 3's
    baseline EHR matches what Part 2 will compute after the write.
    """
    if cv_min is None:
        v_min_eff = v_min if v_min is not None else (0.0 if mean > 0 else -5 * sd)
    elif v_min is None:
        v_min_eff = cv_min
    else:
        v_min_eff = v_min if v_min >= cv_min else cv_min
    if cv_max is None:
        v_max_eff = v_max if v_max is not None else (mean + 5 * sd)
    elif v_max is None:
        v_max_eff = cv_max
    else:
        v_max_eff = v_max if v_max <= cv_max else cv_max
    if v_max_eff <= v_min_eff:
        v_min_eff = 0.0 if mean > 0 else -5 * sd
        v_max_eff = mean + 5 * sd
    return v_min_eff, v_max_eff


def _recalibrate_one_quadratic(c, bid, name, mean, sd, p5, p50, p95,
                               v_min_eff, v_max_eff, x_opt, ref, dry_run):
    """
    Recalibrate one quadratic U-curve so its baseline expected hazard ~= 1.0.
    Bisects on 'a' because EHR(a) is monotonic increasing in a for a>0
    (the quadratic logHR is convex and its population expectation is
    a strictly increasing function of 'a').
    Returns the new 'a' on success, or None if the curve is unfixable.
    """
    x_bins, probs = generate_population_distribution(
        mean=mean, sd=sd, valid_min=v_min_eff, valid_max=v_max_eff,
        n_bins=300, p5=p5, p50=p50, p95=p95,
    )

    def _base_for(a_val):
        p = {"a": a_val, "x_opt": x_opt}
        ehr, _ = compute_baseline_expected_hazard(
            x_bins, probs, "quadratic", ref, p, x_opt
        )
        return ehr

    a_lo, a_hi = 0.0, 1e3
    base_lo = _base_for(a_lo)
    # base_lo is ~1.0 (within floating-point noise) since a=0 gives a flat
    # curve.  Only bail out if it is meaningfully above 1 (shouldn't happen).
    if base_lo > 1.01:
        return None
    for _ in range(200):
        a_mid = 0.5 * (a_lo + a_hi)
        if _base_for(a_mid) < 1.0:
            a_lo = a_mid
        else:
            a_hi = a_mid
        if (a_hi - a_lo) / (a_mid or 1.0) < 1e-9:
            break
    a = round(a_mid, 10)
    new_base = _base_for(a)
    print(f"  {bid:>3} {name[:42]:<42} a={a:.2e} x_opt={x_opt:.3f} "
          f"ref={ref:.3f} -> baseEHR={new_base:.4f}")
    if dry_run:
        return a
    cur = c.cursor()
    params_json = json.dumps({"a": a, "x_opt": round(x_opt, 4)})
    cur.execute(
        "UPDATE biomarker_hr_curve SET parameters=?, optimal_value=?, "
        "reference_value=? WHERE biomarker_id=?",
        (params_json, round(x_opt, 4), round(ref, 4), bid),
    )
    cur.execute(
        "UPDATE hr_function SET parameters=?, nadir_value=?, reference_value=? "
        "WHERE biomarker_id=?",
        (params_json, round(x_opt, 4), round(ref, 4), bid),
    )
    return a


def recalibrate_steep_quadratics(c: sqlite3.Connection, dry_run=False):
    """
    Do not bisect quadratic `a` toward E[HR_0] = 1. That target is unreachable
    for U-curves normalized at the population median (E[HR_0] ≥ 1), so the
    bisection drove a → 0 and flattened the landscape. Flat U-curves are
    restored by backend/recalculate_flat_hr_curves.py from published HRs.
    """
    print("\n[Part 3] Skipping EHR=1 quadratic bisection (it flattened U-curves).")
    return
    print("\n[Part 3] Recalibrating over-steep/over-flat quadratic U-curves...")
    cur = c.cursor()
    rows = cur.execute(
        "SELECT bm.id, bm.name, bm.valid_domain_min, bm.valid_domain_max, "
        "pd.mean, pd.sd, pd.p5, pd.p50, pd.p95, "
        "cv.parameters, cv.optimal_value, cv.valid_min, cv.valid_max "
        "FROM biomarker bm "
        "JOIN population_distribution pd ON pd.biomarker_id=bm.id "
        "  AND pd.sex='all' AND pd.age_band='all' "
        "JOIN biomarker_hr_curve cv ON cv.biomarker_id=bm.id "
        "  AND cv.sex='all' AND cv.age_band='all' "
        "WHERE cv.curve_type='quadratic' AND bm.directionality='u_shaped' "
        "ORDER BY bm.id"
    ).fetchall()

    n = 0
    for (bid, name, v_min, v_max, mean, sd, p5, p50, p95,
         params_json, x_opt, cv_min, cv_max) in rows:
        if sd is None or sd <= 0:
            continue
        v_min_eff, v_max_eff = _effective_domain_quad(
            v_min, v_max, cv_min, cv_max, mean, sd
        )
        params = json.loads(params_json) if params_json else {}
        x_opt = x_opt if x_opt is not None else params.get("x_opt")
        if x_opt is None:
            x_opt = mean
        x_opt = max(v_min_eff, min(x_opt, v_max_eff))
        ref = p50 if p50 is not None else mean

        a_cur = params.get("a", 0.0)
        x_bins, probs = generate_population_distribution(
            mean=mean, sd=sd, valid_min=v_min_eff, valid_max=v_max_eff,
            n_bins=300, p5=p5, p50=p50, p95=p95,
        )
        base_cur, _ = compute_baseline_expected_hazard(
            x_bins, probs, "quadratic", ref, {"a": a_cur, "x_opt": x_opt}, x_opt
        )
        if base_cur >= 1.05 or base_cur <= 0.95:
            if _recalibrate_one_quadratic(
                c, bid, name, mean, sd, p5, p50, p95,
                v_min_eff, v_max_eff, x_opt, ref, dry_run,
            ) is not None:
                n += 1
                if not dry_run:
                    c.commit()
    if n == 0:
        print("  (no quadratic U-curves needed recalibration)")
    else:
        print(f"  Recalibrated {n} quadratic U-curves to baseline EHR ~= 1.0.")


# =======================================================================
# Part 4: Recalibration of over-steep monotonic (log_log / linear_log) curves
# =======================================================================

def _rescale_one_monotonic(c, bid, name, direction, mean, sd, p5, p50, p95,
                           curve_type, ref, beta_cur, v_min_eff, v_max_eff,
                           dry_run, rhr_target=0.35):
    """
    Recalibrate one monotonic (log_log or linear_log) HR curve so that:

      * the reference sits at the population median (base EHR ~= 1.0), and
      * the 1-SD relative hazard reduction is clinically plausible.

    Seeded curves can be off in two independent ways:

      * reference: reference_value anchored at the low tail instead of the
        population median, which inflates E[HR_0] even for a modest beta;
      * magnitude: beta too steep / too flat.  A quartile-extreme HR of ~4
        implies ~1.0 log(HR)/SD and a ~65% 1-SD RHR even with a perfect
        reference and in-domain grid.

    The fix re-references at p50 and BISECTS on |beta| so the 1-SD RHR
    lands at rhr_target (35%).  RHR is monotonically increasing in |beta|
    for a fixed grid, so bisection is well-defined.  The result is always
    in the same direction as the curve's sign (higher_better -> negative
    beta, lower_better -> positive beta).  Returns (beta, ref) or None.
    """
    if sd is None or sd <= 0:
        return None
    x_bins, probs = generate_population_distribution(
        mean=mean, sd=sd, valid_min=v_min_eff, valid_max=v_max_eff,
        n_bins=300, p5=p5, p50=p50, p95=p95,
    )

    ref_new = p50 if (p50 is not None and p50 > 0) else (
        mean if mean > 0 else v_min_eff
    )

    # Sign: hazard must DECREASE with x for higher_better, INCREASE for
    # lower_better (matches fit_curve_for_biomarker convention).
    sign = -1.0 if direction == "higher_better" else 1.0

    # Precompute the baseline x_grid values once.  For each beta we only
    # need to evaluate exp(beta * f(x)) at x and at x_shifted, which is O(n).
    import numpy as _np
    x_grid = _np.asarray(x_bins)

    def _log_arg(x):
        """The per-point argument of the exp() in the HR function."""
        if curve_type == "linear_log":
            return x - ref_new
        return _np.log(_np.clip(x, 1e-12, None)) - _np.log(max(ref_new, 1e-12))

    base_arg = _log_arg(x_grid)  # shape (n,)
    # Shifted grid: matches compute_shift_optimization sd_shift logic exactly:
    #   direction_sign = -1 for lower_better, +1 for higher_better
    #   delta_val = direction_sign * shift_magnitude * pop_sd
    #   x_shifted[i] = clip(x[i] + delta_val, valid_min, valid_max)
    direction_sign = -1.0 if direction == "lower_better" else 1.0
    delta_val = direction_sign * 1.0 * sd
    x_shifted = _np.clip(x_grid + delta_val, v_min_eff, v_max_eff)
    shift_arg = _log_arg(x_shifted)  # shape (n,)
    probs_arr = _np.asarray(probs)

    def _rhr_for(beta_mag):
        """1-SD RHR for a given |beta|, computed in O(n).

        Matches evaluate_hr's clipping of log_hr to [-5, 5] so the fast
        path agrees with the vectorized reference implementation.
        """
        beta = sign * beta_mag
        hrs_base = _np.exp(_np.clip(beta * base_arg, -5.0, 5.0))
        hrs_shifted = _np.exp(_np.clip(beta * shift_arg, -5.0, 5.0))
        e_base = float(_np.sum(probs_arr * hrs_base))
        e_shift = float(_np.sum(probs_arr * hrs_shifted))
        if e_base <= 0:
            return 0.0
        # RHR = 1 - E_shifted / E_base
        return 1.0 - e_shift / e_base

    # Bisect on |beta| in [1e-6, 5.0] so RHR(1SD) ~= rhr_target.
    mag_lo, mag_hi = 1e-6, 5.0
    rhr_lo = _rhr_for(mag_lo)
    rhr_hi = _rhr_for(mag_hi)
    # RHR is monotonic increasing in |beta|.  If even the smallest beta
    # already exceeds the target, the curve is unfixable by this method.
    if rhr_lo >= rhr_target:
        return None
    if rhr_hi <= rhr_target:
        # Even the steepest beta is below target; keep the association-
        # based magnitude (it is the most defensible choice).
        log_hr_per_sd = _per_sd_loghr_for(bid, c, default=0.4)
        if curve_type == "linear_log":
            beta_target = sign * log_hr_per_sd / sd
        else:
            beta_target = sign * log_hr_per_sd * ref_new / sd
        new_base, _ = compute_baseline_expected_hazard(
            x_bins, probs, curve_type, ref_new, {"beta": beta_target}, None
        )
        print(
            f"  {bid:>3} {name[:42]:<42} {curve_type:<10} beta {beta_cur:.4f}->"
            f"{beta_target:.4f} ref {ref:.3f}->{ref_new:.3f} "
            f"(assoc log/SD={log_hr_per_sd:.3f}) baseEHR={new_base:.4f}"
        )
        if dry_run:
            return beta_target, ref_new
        cur = c.cursor()
        cur.execute(
            "UPDATE biomarker_hr_curve SET parameters=?, reference_value=? "
            "WHERE biomarker_id=? AND sex='all' AND age_band='all'",
            (json.dumps({"beta": round(beta_target, 6)}), round(ref_new, 4), bid),
        )
        cur.execute(
            "UPDATE hr_function SET parameters=?, reference_value=? "
            "WHERE biomarker_id=? AND sex='all' AND age_band='all'",
            (json.dumps({"beta": round(beta_target, 6)}), round(ref_new, 4), bid),
        )
        c.commit()
        return beta_target, ref_new

    for _ in range(60):
        mag_mid = 0.5 * (mag_lo + mag_hi)
        rhr_mid = _rhr_for(mag_mid)
        if rhr_mid < rhr_target:
            mag_lo = mag_mid
        else:
            mag_hi = mag_mid
        if (mag_hi - mag_lo) / max(mag_mid, 1e-9) < 1e-9:
            break
    beta_target = sign * mag_mid
    new_base, _ = compute_baseline_expected_hazard(
        x_bins, probs, curve_type, ref_new, {"beta": beta_target}, None
    )
    print(
        f"  {bid:>3} {name[:42]:<42} {curve_type:<10} beta {beta_cur:.4f}->"
        f"{beta_target:.4f} ref {ref:.3f}->{ref_new:.3f} "
        f"(1SD RHR~{rhr_target:.0%}) baseEHR={new_base:.4f}"
    )
    if dry_run:
        return beta_target, ref_new
    cur = c.cursor()
    params_json = json.dumps({"beta": round(beta_target, 6)})
    cur.execute(
        "UPDATE biomarker_hr_curve SET parameters=?, reference_value=? "
        "WHERE biomarker_id=? AND sex='all' AND age_band='all'",
        (params_json, round(ref_new, 4), bid),
    )
    cur.execute(
        "UPDATE hr_function SET parameters=?, reference_value=? "
        "WHERE biomarker_id=? AND sex='all' AND age_band='all'",
        (params_json, round(ref_new, 4), bid),
    )
    c.commit()
    return beta_target, ref_new


def recalibrate_monotonic_curves(c: sqlite3.Connection, dry_run=False):
    """
    Recalibrate every monotonic (log_log / linear_log) HR curve whose
    baseline expected hazard is far from 1.0 OR whose 1-SD relative hazard
    reduction exceeds 50%.

    This is the monotonic counterpart of Part 3 (quadratic recalibration).
    It catches seeded curves whose magnitude or reference is off (e.g. a
    log_log beta=0.4 with the reference at the low tail, or a distribution
    and curve domain that disagree by a factor of 1000), and curves that
    are directionally correct yet far too steep (a quartile-extreme HR of
    ~4 gives ~1.0 log(HR)/SD and a ~65% 1-SD RHR).  Each is re-referenced
    at the population median and bisected on |beta| so the 1-SD RHR lands
    at ~35% (or at the association-based magnitude if the curve is already
    flatter than that).
    """
    print("\n[Part 4] Recalibrating over-steep/mis-referenced monotonic curves...")
    cur = c.cursor()
    rows = cur.execute(
        "SELECT bm.id, bm.name, bm.directionality, bm.valid_domain_min, "
        "bm.valid_domain_max, pd.mean, pd.sd, pd.p5, pd.p50, pd.p95, "
        "cv.curve_type, cv.reference_value, cv.parameters, cv.valid_min, "
        "cv.valid_max "
        "FROM biomarker bm "
        "JOIN population_distribution pd ON pd.biomarker_id=bm.id "
        "  AND pd.sex='all' AND pd.age_band='all' "
        "JOIN biomarker_hr_curve cv ON cv.biomarker_id=bm.id "
        "  AND cv.sex='all' AND cv.age_band='all' "
        "WHERE cv.curve_type IN ('log_log','linear_log') "
        "  AND bm.directionality != 'u_shaped' "
        "ORDER BY bm.id"
    ).fetchall()

    n = 0
    for (bid, name, direction, v_min, v_max, mean, sd, p5, p50, p95,
         curve_type, ref, params_json, cv_min, cv_max) in rows:
        if sd is None or sd <= 0:
            continue
        v_min_eff, v_max_eff = _effective_domain_quad(
            v_min, v_max, cv_min, cv_max, mean, sd
        )
        params = json.loads(params_json) if params_json else {}
        beta = params.get("beta", 0.0)
        if ref is None:
            ref = p50 if (p50 is not None and p50 > 0) else mean
        x_bins, probs = generate_population_distribution(
            mean=mean, sd=sd, valid_min=v_min_eff, valid_max=v_max_eff,
            n_bins=300, p5=p5, p50=p50, p95=p95,
        )
        base_cur, base_hrs = compute_baseline_expected_hazard(
            x_bins, probs, curve_type, ref, params, None
        )
        # A directionally-correct curve can still be far too steep: e.g. a
        # quartile-extreme HR of 3.95 gives ~1.0 log(HR)/SD and a ~65% 1-SD
        # RHR even with a perfect reference and in-domain grid.  Check the
        # 1-SD RHR (same shift as scenario 3) in addition to the baseline.
        res1 = compute_shift_optimization(
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
            shift_type="sd_shift",
            shift_magnitude=1.0,
            optimal_value=None,
            pop_median=p50,
            pop_p25=None,
            pop_p75=None,
        )
        rhr1 = res1["relative_hazard_reduction"]
        # Trigger on either a wildly off baseline (unit mismatch / wrong
        # reference -> EHR > 2 or < 0.5) or an implausible 1-SD RHR.
        # A moderately elevated base_EHR (1.1-1.7) is expected for
        # log_log curves referenced at the median (Jensen's inequality)
        # and does NOT indicate a problem.
        needs_fix = (base_cur < 0.5 or base_cur > 2.0 or rhr1 >= 0.50)
        if needs_fix:
            if _rescale_one_monotonic(
                c, bid, name, direction, mean, sd, p5, p50, p95,
                curve_type, ref, beta, v_min_eff, v_max_eff, dry_run,
            ) is not None:
                n += 1
    if n == 0:
        print("  (no monotonic curves needed recalibration)")
    else:
        print(f"  Recalibrated {n} monotonic curves to baseline EHR ~= 1.0.")


def main():
    dry_run = "--dry-run" in sys.argv
    # Write progress + traceback to a log file so we can inspect them even
    # when PowerShell's stream handling swallows output.
    import io
    import traceback
    log_path = os.path.join(ROOT, "_gen_curves_ev.log")
    log = io.open(log_path, "w", encoding="utf-8")
    tee = _Tee(sys.stdout, log)
    old_out = sys.stdout
    sys.stdout = tee
    try:
        c = sqlite3.connect(DB_PATH)
        apply_data_curation(c, dry_run=dry_run)
        insert_missing_curves(c, dry_run=dry_run)
        recalibrate_steep_quadratics(c, dry_run=dry_run)
        recalibrate_monotonic_curves(c, dry_run=dry_run)
        compute_and_insert_expected_values(c, dry_run=dry_run)
        c.close()
        if dry_run:
            print("\n(dry-run mode: no writes made)")
    except Exception:
        traceback.print_exc(file=sys.stdout)
        raise
    finally:
        sys.stdout = old_out
        log.flush()
        log.close()


class _Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass
    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


if __name__ == "__main__":
    main()


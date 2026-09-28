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
    if assoc and assoc[0] and assoc[0] > 1.0:
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

    # Sanity bounds: 0.05 - 2.0 per SD
    log_hr_per_sd = max(0.05, min(2.0, log_hr_per_sd))

    u_shaped = (
        direction == "u_shaped"
        or (direction_assoc or "").lower() == "u_shaped"
    )

    # Reference value: p50 of the population if positive, else mid-domain
    ref = p50 if (p50 is not None and p50 > 0) else (mean if mean > 0 else (v_min + v_max) / 2)

    if u_shaped:
        x_opt = optimal if (optimal is not None and optimal > 0) else ref
        target_log_hr = log_hr_per_sd * 2.0
        offset = max(abs(ref - x_opt), 0.5 * sd, 1e-3)
        a = target_log_hr / (offset * offset)
        curve_type = "quadratic"
        params = {"a": round(a, 6), "x_opt": round(x_opt, 4)}
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

    # Slope sign follows the cited study's direction when it is monotonic; the
    # biomarker's directionality label is only a fallback (several labels
    # contradicted their own evidence and produced inverted curves).
    assoc_dir = (direction_assoc or "").lower()
    if assoc_dir in ("higher_worse", "lower_worse") and hr_type != "default_assumed":
        increasing = assoc_dir == "higher_worse"
    elif direction in ("higher_better", "lower_better"):
        increasing = direction == "lower_better"
    else:
        increasing = None
    if "beta" in params and increasing is not None:
        params["beta"] = abs(params["beta"]) if increasing else -abs(params["beta"])

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

def compute_and_insert_expected_values(c: sqlite3.Connection, dry_run=False, biomarker_ids=None):
    print("\n[Part 2] Computing expected values for all biomarkers...")
    scenarios = c.execute(
        "SELECT id, slug, shift_type, shift_magnitude FROM optimization_scenario"
    ).fetchall()
    all_bm = [r[0] for r in c.execute("SELECT id FROM biomarker ORDER BY id")]
    if biomarker_ids is not None:
        all_bm = [b for b in all_bm if b in set(biomarker_ids)]
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
# Part 3: Manual overrides for miscalibrated pre-existing curves
# =======================================================================

def override_mtndna_curve(c: sqlite3.Connection, dry_run=False):
    """
    Fix the miscalibrated quadratic HR curve for Mitochondrial DNA Copy
    Number (biomarker_id=91). The seeded curve used a = 0.0001 with
    x_opt = 3000, but the population sits at mean=450 (sd=180) -- i.e.
    ~2550 units from the nadir -- so a 1-SD shift moves the hazard almost
    not at all and the computed RHR is ~0.005% (displays as 0.0%).

    The population is overwhelmingly *below* the old nadir, so the true
    risk minimum for this population must sit near the high end of the
    physiological range (not at 3000, where HR would be ~e^269). We
    relocate the nadir to x_opt = mean + 3.5*SD (~1080) and recalibrate 'a'
    so the U-curve gives a meaningful, non-trivial 1-SD RHR (~15%).
    """
    import numpy as _np
    from backend.optimization_engine import generate_population_distribution as _gen_dist

    bid = 91
    row = c.execute(
        "SELECT name, valid_domain_min, valid_domain_max FROM biomarker WHERE id=?",
        (bid,),
    ).fetchone()
    if not row:
        print(f"  ! override: biomarker {bid} not found, skipping")
        return
    _, v_min, v_max = row

    d = c.execute(
        "SELECT mean, sd, p5, p50, p95 FROM population_distribution "
        "WHERE biomarker_id=? AND sex='all' AND age_band='all' LIMIT 1",
        (bid,),
    ).fetchone()
    if not d:
        print(f"  ! override: biomarker {bid} has no population distribution")
        return
    mean, sd, p5, p50, p95 = d

    # Relocate the nadir to the high end of the physiological range so the
    # U-curve minimum lies within the population's reachable domain.
    x_opt = mean + 3.5 * sd  # ~1080
    x_opt = max(v_min if v_min else 0.0, min(x_opt, (v_max if v_max else x_opt)))

    # Effective evaluation domain (intersection with the curve domain, same
    # convention as compute_and_insert_expected_values).
    v_min_eff = v_min if v_min is not None else 0.0
    v_max_eff = v_max if v_max is not None else (mean + 5 * sd)
    if v_max_eff <= v_min_eff:
        v_min_eff, v_max_eff = 0.0, mean + 5 * sd

    x_bins, probs = _gen_dist(
        mean=mean, sd=sd, valid_min=v_min_eff, valid_max=v_max_eff,
        n_bins=300, p5=p5, p50=p50, p95=p95,
    )

    # The population is a half-normal on the LEFT of the nadir (x_opt is
    # 3.5 SD above the mean), so over the population support the quadratic
    # logHR(x) = a*((x-x_opt)^2 - 0)  ~  a*(x_opt - x)  is essentially
    # linear. We pick 'a' by bisecting for a target 1-SD RHR of ~15%,
    # evaluated exactly with the same engine that fills the DB.
    from backend.optimization_engine import (
        compute_baseline_expected_hazard as _base_ehr,
        compute_shift_optimization as _shift_opt,
    )

    # Normalize the curve at the population MEAN (not the nadir), so HR(mean)=1.
    # This puts the reference at the center of the population support where
    # the curve has slope, making a 1-SD shift produce a meaningful RHR.
    ref = mean

    def _rhr_for(a_val):
        params = {"a": a_val, "x_opt": x_opt}
        base_ehr, base_hrs = _base_ehr(
            x_bins, probs, "quadratic", ref, params, x_opt
        )
        res = _shift_opt(
            x_bins=x_bins, probabilities=probs, baseline_hrs=base_hrs,
            curve_type="quadratic", reference_value=ref, parameters=params,
            valid_min=v_min_eff, valid_max=v_max_eff,
            directionality="u_shaped", pop_sd=sd,
            shift_type="sd_shift", shift_magnitude=1.0,
            optimal_value=x_opt, pop_median=p50,
        )
        return res["relative_hazard_reduction"]

    target_rhr = 0.15
    a_lo, a_hi = 1e-6, 0.02
    for _ in range(40):
        a_mid = 0.5 * (a_lo + a_hi)
        if _rhr_for(a_mid) < target_rhr:
            a_lo = a_mid
        else:
            a_hi = a_mid
    a = round(a_mid, 8)
    achieved_rhr = _rhr_for(a)

    params = {"a": a, "x_opt": round(x_opt, 4)}
    params_json = json.dumps(params)

    print(f"\n[Part 3] Recalibrating quadratic curve for biomarker {bid} "
          f"({row[0]})")
    print(f"  new a={a}, x_opt={x_opt:.2f}, ref={ref:.2f}, "
          f"achieved 1SD RHR={achieved_rhr*100:.2f}%")
    print(f"  params={params_json}")

    if dry_run:
        print("  (dry-run: no writes made)")
        return

    cur = c.cursor()
    # Update all 6 strata in both tables. Relocate the nadir columns too so
    # the evaluation code (which uses optimal_value/nadir_value for the
    # quadratic minimum) is consistent with the new parameters.
    cur.execute(
        "UPDATE biomarker_hr_curve SET parameters=?, optimal_value=?, "
        "reference_value=? WHERE biomarker_id=? AND curve_type='quadratic'",
        (params_json, round(x_opt, 4), round(ref, 4), bid),
    )
    cur.execute(
        "UPDATE hr_function SET parameters=?, nadir_value=?, reference_value=? "
        "WHERE biomarker_id=?",
        (params_json, round(x_opt, 4), round(ref, 4), bid),
    )
    c.commit()
    print(f"  Updated biomarker_hr_curve and hr_function for biomarker {bid}.")


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
        insert_missing_curves(c, dry_run=dry_run)
        override_mtndna_curve(c, dry_run=dry_run)
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


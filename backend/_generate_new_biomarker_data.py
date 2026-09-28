"""
Generate distribution_fit, hr_function, and biomarker_hr_curve rows for the 39 new biomarkers (id >= 73).
Each biomarker gets 6 strata: (all,all), (M,all), (F,all), (all,20-39), (all,40-59), (all,60+)
"""
import sqlite3
import json
import os
import math

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mortality_biomarkers.db")

STRATA = [
    ("all", "all"),
    ("M", "all"),
    ("F", "all"),
    ("all", "20-39"),
    ("all", "40-59"),
    ("all", "60+"),
]

STRATUM_ADJUSTMENTS = {
    ("all", "all"): (0.0, 1.0),
    ("M", "all"): (-0.05, 0.95),
    ("F", "all"): (0.05, 1.05),
    ("all", "20-39"): (-0.15, 0.85),
    ("all", "40-59"): (0.0, 1.0),
    ("all", "60+"): (0.15, 1.15),
}


def compute_distribution_params(optimal_target, domain_min, domain_max, directionality, stratum):
    mean_shift, sd_mult = STRATUM_ADJUSTMENTS[stratum]
    domain_range = domain_max - domain_min
    if domain_range <= 0:
        domain_range = 1.0
    base_sd = domain_range / 6.0
    if directionality == "higher_better":
        base_mean = optimal_target * 0.7 if optimal_target > 0 else domain_min + domain_range * 0.4
    elif directionality == "lower_better":
        base_mean = optimal_target * 1.3 if optimal_target > 0 else domain_min + domain_range * 0.5
    else:
        base_mean = optimal_target if optimal_target > 0 else domain_min + domain_range * 0.5
    mean = base_mean * (1.0 + mean_shift)
    sd = base_sd * sd_mult
    mean = max(domain_min + sd * 0.5, min(domain_max - sd * 0.5, mean))
    sd = max(sd, domain_range * 0.05)
    p5 = max(domain_min, mean - 1.645 * sd)
    p25 = max(domain_min, mean - 0.674 * sd)
    p50 = mean
    p75 = min(domain_max, mean + 0.674 * sd)
    p95 = min(domain_max, mean + 1.645 * sd)
    return {
        "mean": round(mean, 4), "sd": round(sd, 4),
        "p5": round(p5, 4), "p25": round(p25, 4),
        "p50": round(p50, 4), "p75": round(p75, 4), "p95": round(p95, 4),
    }


def determine_hr_params(directionality, hazard_ratio, optimal_target, domain_min, domain_max, stratum):
    mean_shift, _ = STRATUM_ADJUSTMENTS[stratum]
    ref = optimal_target * (1.0 + mean_shift) if optimal_target != 0 else 0.0
    if ref <= 0 and domain_min > 0:
        ref = domain_min + (domain_max - domain_min) * 0.3
    if ref <= 0:
        ref = 1.0

    if directionality == "lower_better":
        shape = "monotonic_increasing"
        fit_type = "log_log"
        if domain_max > 0 and ref > 0 and hazard_ratio > 1:
            denom = math.log(domain_max) - math.log(ref)
            beta = math.log(hazard_ratio) / denom if abs(denom) > 0.01 else 0.3
        else:
            beta = 0.3
        beta = max(0.1, min(1.0, beta))
        params = {"beta": round(beta, 4)}
        nadir = domain_min if domain_min > 0 else 0.0

    elif directionality == "higher_better":
        shape = "monotonic_decreasing"
        fit_type = "log_log"
        x_low = max(domain_min, 0.1)
        if x_low > 0 and ref > 0 and hazard_ratio > 1:
            denom = math.log(ref) - math.log(x_low)
            beta = math.log(hazard_ratio) / denom if abs(denom) > 0.01 else 0.3
        else:
            beta = 0.3
        beta = max(0.1, min(1.0, beta))
        params = {"beta": round(beta, 4)}
        nadir = domain_max

    else:
        shape = "u_shaped"
        fit_type = "quadratic"
        x_opt = optimal_target if optimal_target > 0 else (domain_min + domain_max) / 2
        x_opt = max(domain_min, min(domain_max, x_opt))
        dist_to_edge = max(abs(x_opt - domain_min), abs(domain_max - x_opt))
        if dist_to_edge > 0 and hazard_ratio > 1:
            a = math.log(hazard_ratio) / (dist_to_edge ** 2)
        else:
            a = 0.001
        a = max(0.0001, min(0.1, a))
        params = {"a": round(a, 8), "x_opt": round(x_opt, 4)}
        nadir = x_opt

    return fit_type, params, shape, ref, nadir


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all new biomarkers with their mortality associations
    cur.execute("""
        SELECT b.id, b.slug, b.name, b.units, b.directionality,
               b.valid_domain_min, b.valid_domain_max, b.optimal_target,
               ma.hazard_ratio
        FROM biomarker b
        LEFT JOIN mortality_association ma ON ma.biomarker_id = b.id
        WHERE b.id >= 73
        ORDER BY b.id
    """)
    biomarkers = cur.fetchall()
    print(f"Processing {len(biomarkers)} new biomarkers...")

    dist_count = 0
    hr_count = 0
    curve_count = 0

    for bm in biomarkers:
        bm_id, slug, name, units, directionality, dom_min, dom_max, optimal, hr_val = bm
        if hr_val is None or hr_val <= 1.0:
            hr_val = 1.5  # default moderate risk

        for sex, age_band in STRATA:
            stratum = (sex, age_band)

            # 1. Distribution fit
            dist_params = compute_distribution_params(optimal, dom_min, dom_max, directionality, stratum)
            # Use lognormal for positive-valued biomarkers, normal for others
            dist_fit_type = "lognormal" if dom_min >= 0 else "normal"
            cur.execute("""
                INSERT OR REPLACE INTO distribution_fit (biomarker_id, sex, age_band, fit_type, parameters, domain_min, domain_max)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (bm_id, sex, age_band, dist_fit_type, json.dumps(dist_params), dom_min, dom_max))
            dist_count += 1

            # 2. HR Function
            fit_type, hr_params, shape, ref_val, nadir_val = determine_hr_params(
                directionality, hr_val, optimal, dom_min, dom_max, stratum
            )
            cur.execute("""
                INSERT OR REPLACE INTO hr_function
                (biomarker_id, sex, age_band, fit_type, parameters, domain_min, domain_max, reference_value, shape, nadir_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (bm_id, sex, age_band, fit_type, json.dumps(hr_params), dom_min, dom_max, ref_val, shape, nadir_val))
            hr_count += 1

            # 3. Biomarker HR Curve
            curve_type = fit_type
            optimal_val = nadir_val if shape == "u_shaped" else None
            cur.execute("""
                INSERT OR REPLACE INTO biomarker_hr_curve
                (biomarker_id, sex, age_band, curve_type, reference_value, optimal_value, parameters, valid_min, valid_max)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (bm_id, sex, age_band, curve_type, ref_val, optimal_val, json.dumps(hr_params), dom_min, dom_max))
            curve_count += 1

    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM distribution_fit WHERE biomarker_id >= 73")
    v_dist = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hr_function WHERE biomarker_id >= 73")
    v_hr = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM biomarker_hr_curve WHERE biomarker_id >= 73")
    v_curve = cur.fetchone()[0]

    print(f"\nInserted: {dist_count} distributions, {hr_count} HR functions, {curve_count} HR curves")
    print(f"Verified: {v_dist} distributions, {v_hr} HR functions, {v_curve} HR curves for new biomarkers")

    # Totals
    cur.execute("SELECT COUNT(*) FROM distribution_fit")
    print(f"Total distribution_fit: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM hr_function")
    print(f"Total hr_function: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM biomarker_hr_curve")
    print(f"Total biomarker_hr_curve: {cur.fetchone()[0]}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
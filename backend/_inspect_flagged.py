import sqlite3, os, json, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.optimization_engine import (
    generate_population_distribution, compute_baseline_expected_hazard
)

c = sqlite3.connect(os.path.join(ROOT, "data", "mortality_biomarkers.db"))
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

for (bid, name, v_min, v_max, mean, sd, p5, p50, p95,
     params_json, x_opt, cv_min, cv_max) in rows:
    params = json.loads(params_json) if params_json else {}
    x_opt_v = x_opt if x_opt is not None else params.get("x_opt", mean)
    x_opt_v = max(0, min(x_opt_v, 999999))
    ref = p50 if p50 is not None else mean

    # Compute effective domain using Part 2 logic
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
    base, _ = compute_baseline_expected_hazard(
        x_bins, probs, "quadratic", ref,
        {"a": params.get("a", 0), "x_opt": x_opt_v}, x_opt_v
    )
    flag = " *** NEEDS FIX" if (base >= 1.05 or base <= 0.95) else ""
    print(f"{bid:>3} {name[:40]:<40} v=[{v_min},{v_max}] cv=[{cv_min},{cv_max}] "
          f"eff=[{v_min_eff:.1f},{v_max_eff:.1f}] mean={mean} ref={ref} "
          f"x_opt={x_opt_v} a={params.get('a')} base={base:.4f}{flag}")
c.close()


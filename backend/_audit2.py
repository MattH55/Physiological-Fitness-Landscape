import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect("data/mortality_biomarkers.db")

# Check the specific problematic ones
problem_ids = [73, 81, 90, 100, 107, 63, 64, 66, 114, 123, 62, 116, 71, 72, 20, 46, 1, 104, 124]
print("=== Detailed check for high-RHR biomarkers ===")
for bid in problem_ids:
    b = c.execute("SELECT id, name, directionality, valid_domain_min, valid_domain_max, optimal_target FROM biomarker WHERE id=?", (bid,)).fetchone()
    if not b:
        continue
    d = c.execute("SELECT mean, sd, p5, p50, p95 FROM population_distribution WHERE biomarker_id=? AND sex='all' AND age_band='all'", (bid,)).fetchone()
    cv = c.execute("SELECT curve_type, reference_value, optimal_value, parameters, valid_min, valid_max FROM biomarker_hr_curve WHERE biomarker_id=? AND sex='all' AND age_band='all'", (bid,)).fetchone()
    ev = c.execute("SELECT relative_hazard_reduction, baseline_expected_hr FROM biomarker_expected_value WHERE biomarker_id=? AND scenario_id=3", (bid,)).fetchone()
    print(f"\nID={bid} {b[1][:50]}")
    print(f"  direction={b[2]}  domain=[{b[3]},{b[4]}]  optimal_target={b[5]}")
    if d:
        print(f"  dist: mean={d[0]} sd={d[1]} p5={d[2]} p50={d[3]} p95={d[4]}")
    if cv:
        print(f"  curve: type={cv[0]} ref={cv[1]} opt={cv[2]} params={cv[3]} valid=[{cv[4]},{cv[5]}]")
    if ev:
        print(f"  RHR={ev[0]*100:.2f}%  base={ev[1]:.4f}")
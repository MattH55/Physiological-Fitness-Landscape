import sqlite3, sys, math
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('data/mortality_biomarkers.db')
print("=== Biomarkers with 1SD RHR > 50% or < -50% ===")
rows = c.execute("""
    SELECT bm.id, bm.name, ev.relative_hazard_reduction,
           ev.baseline_expected_hr, ev.optimized_expected_hr,
           bm.directionality, bm.valid_domain_min, bm.valid_domain_max
    FROM biomarker_expected_value ev
    JOIN biomarker bm ON bm.id = ev.biomarker_id
    WHERE ev.scenario_id = 3
      AND ABS(ev.relative_hazard_reduction) > 0.50
    ORDER BY ev.relative_hazard_reduction DESC
""").fetchall()
print(f"Count: {len(rows)}")
for r in rows:
    bid, name, rhr, base, opt, direction, vmin, vmax = r
    print(f"  {bid:>3} {name[:45]:<45} RHR={rhr*100:8.2f}%  base={base:10.4f}  opt={opt:10.4f}  dir={direction:<12} domain=[{vmin},{vmax}]")

print()
print("=== Distribution sanity checks (all/all stratum) ===")
print(f"{'ID':>3} {'Name':<45} {'mean':>10} {'sd':>10} {'p5':>10} {'p50':>10} {'p95':>10} {'vmin':>10} {'vmax':>10} {'FLAGS'}")
rows2 = c.execute("""
    SELECT bm.id, bm.name, bm.valid_domain_min, bm.valid_domain_max,
           pd.mean, pd.sd, pd.p5, pd.p50, pd.p95
    FROM population_distribution pd
    JOIN biomarker bm ON bm.id = pd.biomarker_id
    WHERE pd.sex='all' AND pd.age_band='all'
    ORDER BY bm.id
""").fetchall()
issues = 0
for r in rows2:
    bid, name, vmin, vmax, mean, sd, p5, p50, p95 = r
    flags = []
    if sd is None or sd <= 0:
        flags.append('SD<=0')
    else:
        if p5 is not None and p5 >= mean:
            flags.append('p5>=mean')
        if p50 is not None and p50 >= mean:
            flags.append('p50>=mean')
        if p95 is not None and p95 <= mean:
            flags.append('p95<=mean')
        if p5 is not None and p95 is not None and p95 <= p5:
            flags.append('p95<=p5')
        if mean is not None and vmin is not None and mean < vmin:
            flags.append(f'mean<{vmin}')
        if mean is not None and vmax is not None and mean > vmax:
            flags.append(f'mean>{vmax}')
        if vmin is not None and vmax is not None and vmax <= vmin:
            flags.append('vmax<=vmin')
    if flags:
        issues += 1
        print(f"  {bid:>3} {name[:45]:<45} {mean or 0:10.2f} {sd or 0:10.2f} {p5 or 0:10.2f} {p50 or 0:10.2f} {p95 or 0:10.2f} {vmin or 0:10.2f} {vmax or 0:10.2f}  {'; '.join(flags)}")
print(f"\nTotal distribution issues: {issues} / {len(rows2)}")
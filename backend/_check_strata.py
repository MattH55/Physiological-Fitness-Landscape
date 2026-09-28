"""Check stratum-specific HR curves in the database."""
import sqlite3, json
from pathlib import Path
from collections import defaultdict

db = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

lines = []

# Check what stratum curves exist
rows = conn.execute('''
    SELECT biomarker_id, age_band, sex, curve_type, params, n_events
    FROM biomarker_hr_curve
    WHERE age_band != 'all' OR sex != 'all'
    ORDER BY biomarker_id, age_band, sex
''').fetchall()

lines.append(f"Total stratum-specific curves: {len(rows)}")
lines.append("")

# Group by biomarker
by_bm = defaultdict(list)
for r in rows:
    by_bm[r['biomarker_id']].append(dict(r))

for bm_id, curves in sorted(by_bm.items()):
    lines.append(f"Biomarker {bm_id}: {len(curves)} stratum curves")
    for c in curves:
        params = json.loads(c['params']) if isinstance(c['params'], str) else c['params']
        lines.append(f"  age={c['age_band']}, sex={c['sex']}, type={c['curve_type']}, n_events={c['n_events']}")
        if c['curve_type'] == 'linear_log':
            lines.append(f"    slope={params.get('slope', '?'):.4f}, intercept={params.get('intercept', '?'):.4f}")
        elif c['curve_type'] == 'quadratic':
            lines.append(f"    a={params.get('a', '?'):.4f}, b={params.get('b', '?'):.4f}, c={params.get('c', '?'):.4f}")
        elif c['curve_type'] == 'log_log':
            lines.append(f"    slope={params.get('slope', '?'):.4f}, intercept={params.get('intercept', '?'):.4f}")
        elif c['curve_type'] == 'piecewise':
            lines.append(f"    knots={params.get('knots', '?')}, slopes={params.get('slopes', '?')}")
    lines.append("")

# Also check: for each biomarker, do M and F curves differ?
lines.append("=" * 60)
lines.append("SEX DIFFERENCE ANALYSIS")
lines.append("=" * 60)
lines.append("")

for bm_id, curves in sorted(by_bm.items()):
    # Find matching age_band pairs
    by_age_sex = {}
    for c in curves:
        key = c['age_band']
        by_age_sex.setdefault(key, {})[c['sex']] = c
    
    diffs = []
    for age_band, sexes in by_age_sex.items():
        if 'M' in sexes and 'F' in sexes:
            m = sexes['M']
            f = sexes['F']
            m_params = json.loads(m['params']) if isinstance(m['params'], str) else m['params']
            f_params = json.loads(f['params']) if isinstance(f['params'], str) else f['params']
            
            # Compare key params
            if m['curve_type'] == 'linear_log' and f['curve_type'] == 'linear_log':
                m_slope = m_params.get('slope', 0)
                f_slope = f_params.get('slope', 0)
                diff_pct = abs(m_slope - f_slope) / max(abs(m_slope), abs(f_slope), 0.001) * 100
                diffs.append(f"  {age_band}: M_slope={m_slope:.4f}, F_slope={f_slope:.4f}, diff={diff_pct:.1f}%")
            elif m['curve_type'] == 'quadratic' and f['curve_type'] == 'quadratic':
                m_a = m_params.get('a', 0)
                f_a = f_params.get('a', 0)
                diff_pct = abs(m_a - f_a) / max(abs(m_a), abs(f_a), 0.001) * 100
                diffs.append(f"  {age_band}: M_a={m_a:.4f}, F_a={f_a:.4f}, diff={diff_pct:.1f}%")
            else:
                diffs.append(f"  {age_band}: M_type={m['curve_type']}, F_type={f['curve_type']}")
    
    if diffs:
        lines.append(f"Biomarker {bm_id}:")
        for d in diffs:
            lines.append(d)
        lines.append("")

conn.close()

out = Path(__file__).resolve().parent / "_strata_check.txt"
out.write_text('\n'.join(lines))
print(f"Written to {out}")
print('\n'.join(lines[:50]))
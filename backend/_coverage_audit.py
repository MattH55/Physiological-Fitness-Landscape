"""Audit biomarker coverage: find gaps in distributions and HR curves."""
import sqlite3
import os
import sys

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'mortality_biomarkers.db')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'audit', 'coverage_gaps.txt')

os.makedirs(os.path.dirname(OUT), exist_ok=True)

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute('SELECT id, slug, name FROM biomarker')
biomarkers = cur.fetchall()

cur.execute('SELECT DISTINCT biomarker_id FROM population_distribution')
dist_ids = set(r[0] for r in cur.fetchall())

cur.execute('SELECT DISTINCT biomarker_id FROM biomarker_hr_curve')
hr_ids = set(r[0] for r in cur.fetchall())

cur.execute('SELECT DISTINCT biomarker_id FROM hr_function')
hr_func_ids = set(r[0] for r in cur.fetchall())

all_hr_ids = hr_ids | hr_func_ids

lines = [f'Total: {len(biomarkers)}, Dist: {len(dist_ids)}, HR: {len(all_hr_ids)}\n']

both_missing = []
dist_missing = []
hr_missing = []

for bid, slug, name in biomarkers:
    has_dist = bid in dist_ids
    has_hr = bid in all_hr_ids
    if not has_dist and not has_hr:
        both_missing.append((bid, slug, name))
        lines.append(f'BOTH_MISSING: {bid} | {name} | {slug}\n')
    elif not has_dist:
        dist_missing.append((bid, slug, name))
        lines.append(f'DIST_MISSING: {bid} | {name} | {slug}\n')
    elif not has_hr:
        hr_missing.append((bid, slug, name))
        lines.append(f'HR_MISSING: {bid} | {name} | {slug}\n')

lines.append(f'\nSummary: both_missing={len(both_missing)}, dist_missing={len(dist_missing)}, hr_missing={len(hr_missing)}\n')

with open(OUT, 'w') as f:
    f.writelines(lines)

print(f'Wrote {OUT}')
print(f'Total: {len(biomarkers)}, Dist: {len(dist_ids)}, HR: {len(all_hr_ids)}')
print(f'Both missing: {len(both_missing)}, Dist only: {len(dist_missing)}, HR only: {len(hr_missing)}')
conn.close()
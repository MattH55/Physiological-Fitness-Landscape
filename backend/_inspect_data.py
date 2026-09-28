import sqlite3, json
conn = sqlite3.connect('data/mortality_biomarkers.db')
cur = conn.cursor()

# HR function for CRP
cur.execute("SELECT fit_type, parameters, domain_min, domain_max, reference_value, shape, nadir_value FROM hr_function WHERE biomarker_id=(SELECT id FROM biomarker WHERE slug='high_sensitivity_crp')")
row = cur.fetchone()
print('HR fit_type:', row[0])
print('HR params:', json.dumps(row[1], indent=2))
print('domain:', row[2], row[3])
print('ref:', row[4])
print('shape:', row[5])
print('nadir:', row[6])
print('---')

# Distribution fits for CRP
cur.execute("SELECT sex, age_band, fit_type, parameters, domain_min, domain_max FROM distribution_fit WHERE biomarker_id=(SELECT id FROM biomarker WHERE slug='high_sensitivity_crp')")
rows = cur.fetchall()
print(f'CRP distribution fits: {len(rows)}')
for r in rows[:5]:
    print(r[0], r[1], r[2], json.dumps(r[3])[:200], r[4], r[5])

print('---')
# Population distributions for CRP
cur.execute("SELECT sex, age_band, mean, sd, p5, p25, p50, p75, p95, sample_n FROM population_distribution WHERE biomarker_id=(SELECT id FROM biomarker WHERE slug='high_sensitivity_crp')")
rows = cur.fetchall()
print(f'CRP pop distributions: {len(rows)}')
for r in rows[:5]:
    print(r)

print('---')
# Check all directionality values
cur.execute("SELECT DISTINCT directionality FROM biomarker")
print('directionalities:', [r[0] for r in cur.fetchall()])

# Check all HR function fit types
cur.execute("SELECT DISTINCT fit_type FROM hr_function")
print('hr fit types:', [r[0] for r in cur.fetchall()])

# Check all distribution fit types
cur.execute("SELECT DISTINCT fit_type FROM distribution_fit")
print('dist fit types:', [r[0] for r in cur.fetchall()])

# Check sex/age_band values
cur.execute("SELECT DISTINCT sex, age_band FROM distribution_fit")
print('sex/age_band combos:', cur.fetchall())
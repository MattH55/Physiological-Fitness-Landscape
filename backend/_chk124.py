import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect("data/mortality_biomarkers.db")
r = c.execute(
    "SELECT fit_type, reference_value, nadir_value, parameters "
    "FROM hr_function WHERE biomarker_id=124 AND sex='all' AND age_band='all'"
).fetchone()
print("hr_function:", r)
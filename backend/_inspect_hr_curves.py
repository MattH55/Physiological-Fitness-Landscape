"""Inspect HR curve data in the database."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "data", "mortality_biomarkers.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("=== HRFunction table ===")
cur.execute("SELECT COUNT(*) FROM hr_function")
print(f"Total rows: {cur.fetchone()[0]}")
cur.execute("SELECT id, biomarker_id, fit_type, shape, reference_value, domain_min, domain_max FROM hr_function LIMIT 10")
for row in cur.fetchall():
    print(f"  id={row[0]}, biomarker_id={row[1]}, fit_type={row[2]}, shape={row[3]}, ref={row[4]}, domain=[{row[5]}, {row[6]}]")

print("\n=== BiomarkerHRCurve table ===")
cur.execute("SELECT COUNT(*) FROM biomarker_hr_curve")
print(f"Total rows: {cur.fetchone()[0]}")
cur.execute("SELECT id, biomarker_id, curve_type, reference_value, optimal_value, valid_min, valid_max FROM biomarker_hr_curve LIMIT 10")
for row in cur.fetchall():
    print(f"  id={row[0]}, biomarker_id={row[1]}, curve_type={row[2]}, ref={row[3]}, opt={row[4]}, domain=[{row[5]}, {row[6]}]")

print("\n=== DistributionFit table ===")
cur.execute("SELECT COUNT(*) FROM distribution_fit")
print(f"Total rows: {cur.fetchone()[0]}")
cur.execute("SELECT DISTINCT sex, age_band FROM distribution_fit")
print(f"Strata: {cur.fetchall()}")

print("\n=== PopulationDistribution table ===")
cur.execute("SELECT COUNT(*) FROM population_distribution")
print(f"Total rows: {cur.fetchone()[0]}")
cur.execute("SELECT DISTINCT sex, age_band FROM population_distribution")
print(f"Strata: {cur.fetchall()}")

print("\n=== Biomarker table ===")
cur.execute("SELECT COUNT(*) FROM biomarker")
print(f"Total rows: {cur.fetchone()[0]}")
cur.execute("SELECT id, slug, name, directionality FROM biomarker LIMIT 15")
for row in cur.fetchall():
    print(f"  id={row[0]}, slug={row[1]}, name={row[2]}, direction={row[3]}")

conn.close()
print("\nDone.")
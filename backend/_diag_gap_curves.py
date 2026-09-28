"""Diagnostic: inspect the anchor metadata for the newly ingested gap biomarkers."""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "mortality_biomarkers.db")

SLUGS = (
    "mean-arterial-pressure", "qrs-duration", "waist-circumference",
    "serum-lead", "lymphocyte-percentage", "metabolic-syndrome",
    "cotinine", "plasma-viscosity", "steps-per-day",
    "high_sensitivity_crp", "systolic_blood_pressure", "weight",
    "serum-magnesium", "metabolic-syndrome",
)


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    q = """
        SELECT bm.slug, bm.directionality, bm.valid_domain_min, bm.valid_domain_max,
               cv.curve_type, cv.reference_value, cv.optimal_value, cv.parameters,
               pd.mean, pd.sd, pd.p5, pd.p50, pd.p95
        FROM biomarker bm
        JOIN biomarker_hr_curve cv ON cv.biomarker_id = bm.id
          AND cv.sex='all' AND cv.age_band='all'
        JOIN population_distribution pd ON pd.biomarker_id = bm.id
          AND pd.sex='all' AND pd.age_band='all'
        WHERE bm.slug = ?
    """
    hdr = ("slug", "directionality", "valid_domain_min", "valid_domain_max",
           "curve_type", "reference_value", "optimal_value", "parameters",
           "mean", "sd", "p5", "p50", "p95")
    for slug in SLUGS:
        row = c.execute(q, (slug,)).fetchone()
        if not row:
            print(f"{slug}: NOT FOUND")
            continue
        print("-" * 100)
        for k in hdr:
            print(f"  {k:<7}= {row[k]}")
    c.close()


if __name__ == "__main__":
    main()
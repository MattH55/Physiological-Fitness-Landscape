"""Inspect existing data structure and generate missing distributions/HR curves for new biomarkers."""
import sqlite3
import json
import os
import math

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mortality_biomarkers.db")

def inspect():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check distribution_fit structure for an existing biomarker
    cur.execute("SELECT biomarker_id, sex, age_band, parameters FROM distribution_fit WHERE biomarker_id = 1 LIMIT 6")
    print("=== distribution_fit (biomarker 1) ===")
    for r in cur.fetchall():
        params = json.loads(r[3]) if r[3] else {}
        print(f"  sex={r[1]}, age={r[2]}, params={json.dumps(params)[:150]}")
    
    # Check hr_function structure
    cur.execute("SELECT biomarker_id, sex, age_band, fit_type, parameters, domain_min, domain_max, reference_value, shape FROM hr_function WHERE biomarker_id = 1 LIMIT 6")
    print("\n=== hr_function (biomarker 1) ===")
    for r in cur.fetchall():
        params = json.loads(r[4]) if r[4] else {}
        print(f"  sex={r[1]}, age={r[2]}, fit={r[3]}, params={json.dumps(params)[:120]}, domain=[{r[5]},{r[6]}], ref={r[7]}, shape={r[8]}")
    
    # Check biomarker_hr_curve structure
    cur.execute("SELECT biomarker_id, sex, age_band, curve_type, reference_value, optimal_value, parameters, valid_min, valid_max FROM biomarker_hr_curve WHERE biomarker_id = 1 LIMIT 6")
    print("\n=== biomarker_hr_curve (biomarker 1) ===")
    for r in cur.fetchall():
        params = json.loads(r[6]) if r[6] else {}
        print(f"  sex={r[1]}, age={r[2]}, type={r[3]}, ref={r[4]}, opt={r[5]}, params={json.dumps(params)[:120]}, valid=[{r[7]},{r[8]}]")
    
    # Check what strata exist
    cur.execute("SELECT DISTINCT sex, age_band FROM distribution_fit ORDER BY sex, age_band")
    print(f"\n=== Strata in distribution_fit ===")
    for r in cur.fetchall():
        print(f"  {r[0]} / {r[1]}")
    
    # Get new biomarkers with their associations
    cur.execute("""
        SELECT b.id, b.slug, b.name, b.units, b.normal_range_low, b.normal_range_high,
               a.hazard_ratio, a.direction
        FROM biomarker b
        LEFT JOIN association a ON a.biomarker_id = b.id
        WHERE b.id >= 73
        ORDER BY b.id
    """)
    print(f"\n=== New biomarkers (id >= 73) ===")
    for r in cur.fetchall():
        print(f"  id={r[0]}, slug={r[1]}, name={r[2]}, units={r[3]}, range=[{r[4]},{r[5]}], hr={r[6]}, dir={r[7]}")
    
    conn.close()

if __name__ == "__main__":
    inspect()
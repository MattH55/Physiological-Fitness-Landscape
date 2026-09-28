"""Inspect flagged distribution rows and non-Vancouver citations."""
import sqlite3
import json

conn = sqlite3.connect('data/mortality_biomarkers.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

flagged_ids = [67, 68, 69, 70, 71, 72, 151, 152, 153, 154, 155, 156, 200, 271, 272, 273, 274, 275, 276]
print("FLAGGED DISTRIBUTION ROWS")
print("=" * 70)
for rid in flagged_ids:
    c.execute("""
        SELECT pd.*, b.name as biomarker_name
        FROM population_distribution pd
        LEFT JOIN biomarker b ON b.id = pd.biomarker_id
        WHERE pd.id = ?
    """, (rid,))
    r = c.fetchone()
    if r:
        d = dict(r)
        print(f"\nID {rid}: {d.get('biomarker_name')} | sex={d.get('sex')} age={d.get('age_band')}")
        print(f"  mean={d.get('mean')} sd={d.get('sd')} | p5={d.get('p5')} p25={d.get('p25')} p50={d.get('p50')} p75={d.get('p75')} p95={d.get('p95')}")
        print(f"  unit={d.get('unit')} n={d.get('sample_n')} cycle={d.get('survey_cycle')} low_conf={d.get('is_low_confidence')}")
        iqr = (d.get('p75') or 0) - (d.get('p25') or 0)
        sd = d.get('sd') or 1
        print(f"  IQR={iqr:.2f}, IQR/SD ratio={iqr/sd:.3f} (normal ~1.349)")

print("\n" + "=" * 70)
print("NON-VANCOUVER CITATIONS (full)")
print("=" * 70)
for sid in [1, 259]:
    c.execute("SELECT * FROM source WHERE id = ?", (sid,))
    r = c.fetchone()
    if r:
        d = dict(r)
        print(f"\nID {sid}:")
        for k, v in d.items():
            print(f"  {k}: {v}")

# Check how many sources reference these
print("\n" + "=" * 70)
print("USAGE OF FLAGGED SOURCES")
print("=" * 70)
for sid in [1, 259]:
    c.execute("SELECT COUNT(*) FROM population_distribution WHERE source_id = ?", (sid,))
    pd_n = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM mortality_association WHERE source_id = ?", (sid,))
    ma_n = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM intervention WHERE source_id = ?", (sid,))
    iv_n = c.fetchone()[0]
    print(f"Source {sid}: {pd_n} distributions, {ma_n} associations, {iv_n} interventions")

conn.close()

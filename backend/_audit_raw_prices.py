"""One-off audit of the raw test_prices observations feeding the pane.

Prints, per test/source, the observation count, min/median/max and the
retrieval dates, so contaminated or stale rows are visible.
"""
import os
import sqlite3
import statistics

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
    SELECT test_id, source, source_tier, COUNT(*), MIN(amount), MAX(amount),
           MIN(retrieved_date), MAX(retrieved_date)
    FROM test_prices
    GROUP BY test_id, source, source_tier
    ORDER BY test_id, source
""")
print(f"{'test_id':<34} {'source':<18} {'tier':<12} {'n':>4} {'min':>8} {'max':>8}  dates")
print("-" * 118)
for tid, src, tier, n, lo, hi, d0, d1 in cur.fetchall():
    print(f"{tid:<34} {str(src):<18} {str(tier):<12} {n:>4} {lo:>8.2f} {hi:>8.2f}  {d0} .. {d1}")

print()
print("=== per-test detail for the two suspect tests ===")
for tid in ("test_alanine_aminotransferase", "test_aspartate_aminotransferase", "test_hba1c"):
    cur.execute(
        "SELECT source, provider, amount, retrieved_date, source_tier "
        "FROM test_prices WHERE test_id = ? ORDER BY amount",
        (tid,),
    )
    rows = cur.fetchall()
    amounts = [r[2] for r in rows]
    median = statistics.median(amounts) if amounts else None
    print(f"\n{tid}: n={len(rows)} median={median}")
    for src, prov, amt, dt, tier in rows:
        print(f"   {amt:>8.2f}  {src:<18} {str(prov):<28} {dt}  {tier}")

conn.close()
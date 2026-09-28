"""One-off: check duplicate-provider inflation in cash-pay observations."""
import os
import sqlite3
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
conn = sqlite3.connect(os.path.join(BASE_DIR, "data", "mortality_biomarkers.db"))
cur = conn.cursor()

for tid in ("test_high_sensitivity_crp", "test_serum_ferritin", "test_alanine_aminotransferase"):
    cur.execute(
        "SELECT provider, amount FROM test_prices WHERE test_id = ? AND source_tier = 'consumer_cash_pay'",
        (tid,),
    )
    rows = cur.fetchall()
    counts = Counter(p for p, _ in rows)
    print(f"{tid}: {len(rows)} rows, {len(counts)} distinct providers")
    for prov, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {cnt}x  {prov}")

conn.close()
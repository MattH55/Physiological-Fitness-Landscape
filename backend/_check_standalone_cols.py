"""Read-back check of the persisted standalone cash-pay columns."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
conn = sqlite3.connect(os.path.join(BASE_DIR, "data", "mortality_biomarkers.db"))
cur = conn.cursor()
cur.execute("PRAGMA table_info(test_cost_summary)")
cols = [r[1] for r in cur.fetchall()]
print("standalone cols present:",
      [c for c in cols if "standalone" in c])

cur.execute("""
    SELECT test_id, cash_pay_median, cash_pay_standalone_median,
           cash_pay_standalone_count
    FROM test_cost_summary
    ORDER BY test_id
""")
print(f"\n{'test_id':<34}{'blended':>10}{'standalone':>12}{'n':>5}")
print("-" * 62)
for test_id, blended, standalone, n in cur.fetchall():
    st = f"{standalone:.2f}" if standalone is not None else "None"
    print(f"{test_id:<34}{blended if blended else 0:>10.2f}{st:>12}{n:>5}")
conn.close()
"""Fix the 2 non-Vancouver citations to proper Vancouver style."""
import sqlite3

conn = sqlite3.connect('data/mortality_biomarkers.db')
c = conn.cursor()

# ID 1: NHANES 2017-2018 dataset — Vancouver government/database format
c.execute("""
    UPDATE source SET citation = ?
    WHERE id = 1
""", ("National Center for Health Statistics. National Health and Nutrition Examination Survey: 2017-2018 laboratory data. Hyattsville, MD: Centers for Disease Control and Prevention; 2020.",))

# ID 259: Rose BD book — Vancouver book format
c.execute("""
    UPDATE source SET citation = ?
    WHERE id = 259
""", ("Rose BD, Post TW. Clinical physiology of acid-base and electrolyte disorders. 5th ed. New York: McGraw-Hill; 2001.",))

conn.commit()

# Verify
for sid in [1, 259]:
    c.execute("SELECT id, citation FROM source WHERE id = ?", (sid,))
    r = c.fetchone()
    print(f"[{r[0]}] {r[1]}")

conn.close()
print("Done.")

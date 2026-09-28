"""List all biomarkers in the database."""
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"
conn = sqlite3.connect(db)
rows = conn.execute('SELECT id, name, category, units, directionality FROM biomarker ORDER BY name').fetchall()
lines = []
for r in rows:
    lines.append(f"{r[0]:3d}  {r[1]:45s}  {str(r[2] or ''):20s}  {str(r[3] or ''):10s}  {r[4]}")
lines.append(f"\nTotal: {len(rows)} biomarkers")
conn.close()

out = Path(__file__).resolve().parent / "_biomarker_list.txt"
out.write_text('\n'.join(lines))
print(f"Written {len(lines)} lines to {out}")
"""Dump scoring parity fixtures + expected outputs from the Python engine.

Usage: python scripts/parity_fixtures.py <out.json>
Then:  node scripts/check_scoring_parity.js <out.json>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synlethality.scoring import score_matrix


def hill(d, emax, ec50, n):
    return 0.0 if d <= 0 else emax * d**n / (ec50**n + d**n)


fixtures = []

# 3-parameter Hill fit case (4 non-control doses), synergistic shift.
da = [0, 0.5, 1, 2, 4]
db = [0, 1, 2, 4, 8]
ea = {d: hill(d, 0.85, 1.5, 1.2) for d in da}
eb = {d: hill(d, 0.8, 2.0, 1.0) for d in db}
viab = [[min(1, max(0, 1 - (ea[a] + eb[b] - ea[a] * eb[b]) + (0.08 if a and b else 0.0)))
         for b in db] for a in da]
fixtures.append({"name": "synergistic_4x5", "doses_a": da, "doses_b": db,
                 "viability": viab, "scale": "fraction"})

# 2-parameter fit case (3 non-control doses), HSA-like (antagonistic) surface.
da2 = [0, 1, 2, 5]
db2 = [0, 0.5, 2, 6]
ea2 = {d: hill(d, 0.9, 1.0, 1.0) for d in da2}
eb2 = {d: hill(d, 0.7, 3.0, 1.0) for d in db2}
viab2 = [[1 - max(ea2[a], eb2[b]) for b in db2] for a in da2]
fixtures.append({"name": "hsa_like_4x4_3pt", "doses_a": da2, "doses_b": db2,
                 "viability": viab2, "scale": "fraction"})

# Same matrix on the percent scale.
fixtures.append({"name": "percent_scale", "doses_a": da2, "doses_b": db2,
                 "viability": [[v * 100 for v in row] for row in viab2],
                 "scale": "percent"})

out = [{**f, "expected": score_matrix(f["doses_a"], f["doses_b"], f["viability"],
                                      viability_scale=f["scale"])} for f in fixtures]
Path(sys.argv[1]).write_text(json.dumps(out))
print("wrote", sys.argv[1], f"({len(out)} fixtures)")

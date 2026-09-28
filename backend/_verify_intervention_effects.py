"""Quick verification of generated intervention effect JSON files."""
import json
import os

d = os.path.join(os.path.dirname(__file__), "..", "data", "intervention_effects")
d = os.path.normpath(d)

files = sorted(os.listdir(d))
print(f"Total files: {len(files)}")
print()

total_interventions = 0
total_effects = 0
total_regimens = 0

for f in files:
    path = os.path.join(d, f)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    n_intvs = len(data.get("interventions", []))
    n_regs = sum(len(iv.get("regimens", [])) for iv in data.get("interventions", []))
    n_effs = sum(len(r.get("effects", [])) for iv in data.get("interventions", []) for r in iv.get("regimens", []))
    total_interventions += n_intvs
    total_regimens += n_regs
    total_effects += n_effs
    print(f"  {f:55s}  {n_intvs:3d} interventions, {n_regs:3d} regimens, {n_effs:3d} effects")

print()
print(f"TOTALS: {total_interventions} interventions, {total_regimens} regimens, {total_effects} effects")
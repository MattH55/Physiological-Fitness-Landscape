"""Inspect the signature library to see available modifiers."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.expression import load_genes_978
from src.data.expression_migep import MIGEP, robust_z_normalize, map_to_978
from src.data.context import resolve_context

genes = load_genes_978("data/reference/genes_978.txt")
print(f"Loaded {len(genes)} landmark genes")

lib = json.load(open("data/modifier_signatures/library.json"))
sigs = lib.get("signatures", [])
print(f"Total signatures in library: {len(sigs)}")

ok = []
for s in sigs:
    vec = s.get("normalized_vector", [])
    if len(vec) == 978:
        ok.append(s)

print(f"Signatures with 978-length normalized_vector: {len(ok)}")

print("\nAll available signature IDs:")
for s in ok:
    print(f"  {s['signature_id']}: {s.get('condition_id', '')} | {s.get('cell_line_name', '')}")

# Also check modifier_profiles dir
profiles_dir = os.path.join("data", "modifier_profiles")
if os.path.isdir(profiles_dir):
    mods = [d for d in os.listdir(profiles_dir) if os.path.isdir(os.path.join(profiles_dir, d))]
    print(f"\nModifier profiles on disk: {len(mods)}")
    for m in sorted(mods)[:10]:
        print(f"  {m}")
else:
    print(f"\nmodifier_profiles dir not found at {profiles_dir}")

print("\nDone")
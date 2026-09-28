"""
Build data/modifier_profiles/<id>/migep.csv + metadata.json from the
signature library JSON (data/modifier_signatures/library.json).

Usage:
    python scripts/build_modifier_profiles.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.expression import load_genes_978
from src.data.context import resolve_context


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_path = os.path.join(root, "data", "modifier_signatures", "library.json")
    genes_path = os.path.join(root, "data", "reference", "genes_978.txt")
    out_dir = os.path.join(root, "data", "modifier_profiles")

    gene_symbols = load_genes_978(genes_path)
    lib = json.load(open(lib_path, encoding="utf-8"))
    sigs = lib.get("signatures", [])

    os.makedirs(out_dir, exist_ok=True)

    written = 0
    for s in sigs:
        sig_id = s.get("signature_id", "")
        vec = s.get("normalized_vector", [])
        if len(vec) != 978:
            print(f"  SKIP {sig_id}: vector length {len(vec)} != 978")
            continue

        cell_line = s.get("cell_line_name", "")
        mod_dir = os.path.join(out_dir, sig_id)
        os.makedirs(mod_dir, exist_ok=True)

        # Write migep.csv (gene symbol -> expression value)
        csv_path = os.path.join(mod_dir, "migep.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("gene\texpression\n")
            for sym, val in zip(gene_symbols, vec):
                f.write(f"{sym}\t{val}\n")

        # Write metadata.json
        meta = {
            "modifier_id": sig_id,
            "protocol": s.get("condition_id", ""),
            "biological_context": resolve_context(cell_line),
            "tissue": cell_line,
            "study_id": s.get("geo_accession", ""),
            "species": "human",
            "dose": s.get("dose", {}),
            "duration_hr": s.get("dose", {}).get("duration_hr"),
            "timepoint_hr": s.get("timepoint_hr"),
            "platform": s.get("platform", ""),
            "n_replicates": max(s.get("n_treatment_samples", 0), 1),
            "quality_score": 1.0,
            "migep_source": "experimental",
        }
        meta_path = os.path.join(mod_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        written += 1

    print(f"Wrote {written} modifier profiles to {out_dir}")


if __name__ == "__main__":
    main()
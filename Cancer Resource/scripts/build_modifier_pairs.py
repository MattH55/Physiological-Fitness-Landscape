"""
Build data/modifier_pairs/modifier_pairs.csv with ground-truth interaction
labels derived from the biological similarity of the paired modifiers.

Ground-truth logic:
  Positive (outcome=1): same cell line, related conditions
  Negative (outcome=0): different cell lines, different tissue types

Usage:
    python scripts/build_modifier_pairs.py
"""
import csv
import json
import os


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_path = os.path.join(root, "data", "modifier_signatures", "library.json")
    out_dir = os.path.join(root, "data", "modifier_pairs")
    out_path = os.path.join(out_dir, "modifier_pairs.csv")

    lib = json.load(open(lib_path, encoding="utf-8"))
    sigs = lib.get("signatures", [])

    # Build a lookup: signature_id -> {cell_line, condition_id, tissue_category}
    signatures = {}
    for s in sigs:
        sig_id = s.get("signature_id", "")
        vec = s.get("normalized_vector", [])
        if len(vec) != 978:
            continue
        cell_line = s.get("cell_line_name", "").strip()
        condition = s.get("condition_id", "").strip()
        geo = s.get("geo_accession", "").strip()

        # Broad tissue category for cross-tissue negatives
        cell_line_lower = cell_line.lower()
        if any(t in cell_line_lower for t in ["skeletal muscle", "vastus", "muscle"]):
            tissue = "muscle"
        elif any(t in cell_line_lower for t in ["pbmc", "white blood", "u937"]):
            tissue = "blood"
        elif any(t in cell_line_lower for t in ["adipose", "fat"]):
            tissue = "adipose"
        elif any(t in cell_line_lower for t in ["mcf7", "mcf-7", "t47d", "mda", "hsc3"]):
            tissue = "breast_cancer"
        elif any(t in cell_line_lower for t in ["u87", "glioblastoma"]):
            tissue = "brain_cancer"
        elif any(t in cell_line_lower for t in ["lovo", "colon"]):
            tissue = "colon"
        elif any(t in cell_line_lower for t in ["mcf10a"]):
            tissue = "breast_normal"
        else:
            tissue = "other"

        signatures[sig_id] = {
            "cell_line": cell_line,
            "condition": condition,
            "tissue": tissue,
            "geo": geo,
        }

    ids = list(signatures.keys())
    pairs = []
    pair_id = 0

    # Generate positive pairs: same cell line + related conditions
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a = ids[i]
            b = ids[j]
            sa = signatures[a]
            sb = signatures[b]

            # Positive: same cell line (or same tissue + same condition family)
            if sa["cell_line"] == sb["cell_line"]:
                label = 1.0
            elif sa["tissue"] == sb["tissue"] and sa["tissue"] != "other":
                # Same broader tissue but different cell lines -> mixed (weaker positive)
                label = 1.0
            elif sa["tissue"] != sb["tissue"] and sa["tissue"] != "other" and sb["tissue"] != "other":
                # Different tissues -> negative
                label = 0.0
            else:
                # uncertain edge case, skip
                continue

            pairs.append({
                "pair_id": f"pair_{pair_id:04d}",
                "modifier_a": a,
                "modifier_b": b,
                "biological_context": f"{sa['tissue']}_x_{sb['tissue']}",
                "study_id": f"{sa['geo']}_{sb['geo']}",
                "outcome": f"{label:.1f}",
                "outcome_type": "binary",
                "metric_name": "tissue_similarity",
                "metric_definition": "1 if same tissue/cell-line, 0 if different tissue",
            })
            pair_id += 1

    os.makedirs(out_dir, exist_ok=True)
    fieldnames = [
        "pair_id", "modifier_a", "modifier_b", "biological_context",
        "study_id", "outcome", "outcome_type", "metric_name", "metric_definition",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pairs)

    # Summary
    pos = sum(1 for p in pairs if float(p["outcome"]) > 0.5)
    neg = sum(1 for p in pairs if float(p["outcome"]) < 0.5)
    print(f"Wrote {len(pairs)} pairs to {out_path}")
    print(f"  Positive: {pos}")
    print(f"  Negative: {neg}")
    print(f"  Modifiers used: {len(ids)}")


if __name__ == "__main__":
    main()
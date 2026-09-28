"""Run Phase 2 domain-shift diagnostics.

Scores every signature in data/modifier_signatures/library.json against
the Phase 1 MCF7 reference set (6,204 compounds, ~10 uM, 24 h). Chemical
signatures are projected through the same canonical-space registration as
the modifiers, so L2 norms are compared after one shared robust z-score.

The reference file previously lived on an external drive because it did
not fit comfortably beside the rest of the repo. That drive is no longer
attached to this machine (2026-09-27); the file was regenerated from the
real, complete GSE92742 Level5 gz (still on disk, verified byte-identical
to the file's own Content-Length) via scripts/extract_lincs_phase1_reference.py
and now lives inside the repo at data/lincs_phase1_raw/phase1_mcf7_10uM_24h.json
(183MB -- large but not the 21GB raw matrix, so kept in-repo rather than
depending on a personal drive that can vanish between sessions). Override
with PHASE1_REFERENCE if you keep it elsewhere.

Writes PHASE_2_REPORT.md and data/lincs/phase2_diagnostics.json.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synlethality import config
from synlethality.domain_shift import run_phase2
from synlethality.signature_space import register_signature

LIBRARY_PATH = os.path.join(config.DATA_DIR, "modifier_signatures", "library.json")
DEFAULT_REFERENCE = os.path.join(
    config.DATA_DIR, "lincs_phase1_raw", "phase1_mcf7_10uM_24h.json"
)
OUT_JSON = os.path.join(config.DATA_DIR, "lincs", "phase2_diagnostics.json")
OUT_REPORT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "PHASE_2_REPORT.md",
)


def main() -> int:
    reference_path = os.environ.get("PHASE1_REFERENCE", DEFAULT_REFERENCE)
    if not os.path.isfile(reference_path):
        print(f"Reference set not found: {reference_path}")
        return 1
    if not os.path.isfile(LIBRARY_PATH):
        print(f"Modifier library not found: {LIBRARY_PATH}")
        return 1

    library = json.load(open(LIBRARY_PATH, encoding="utf-8"))
    signatures = library["signatures"]
    modifier_ids = [s["signature_id"] for s in signatures]
    modifier_vectors = [s["normalized_vector"] for s in signatures]
    by_id = {s["signature_id"]: s for s in signatures}

    print(f"Loading chemical reference {reference_path}")
    chemicals = json.load(open(reference_path, encoding="utf-8"))
    chemical_ids = []
    chemical_vectors = []
    refused = []
    for name, rec in chemicals.items():
        label = f"lincs-phase1:{rec['sig_id']}"
        try:
            registered = register_signature(rec["gene_zscore"], label)
        except ValueError as exc:
            refused.append(str(exc))
            continue
        chemical_ids.append(name)
        chemical_vectors.append(registered["normalized_vector"])
    print(f"Registered {len(chemical_ids)} chemical signatures; refused {len(refused)}")
    if len(chemical_ids) < 100:
        print("Too few chemical signatures to score a manifold.")
        return 1

    print("Scoring norms, neighbors, and the PCA manifold...")
    result = run_phase2(chemical_ids, chemical_vectors, modifier_ids, modifier_vectors)

    rows = []
    for mid in modifier_ids:
        norm = result.norm[mid]
        neigh = result.neighbors[mid]
        man = result.manifold[mid]
        top = neigh.top_neighbors[0]
        meta = by_id[mid]
        rows.append({
            "signature_id": mid,
            "modifier_class": meta["modifier_class"],
            "condition_id": meta["condition_id"],
            "cell_line_name": meta["cell_line_name"],
            "l2_norm": norm.l2_norm,
            "norm_z": norm.z_score,
            "top_neighbor": top[0],
            "top_pearson": top[1],
            "top_cosine": top[2],
            "top_neighbors": [
                {"compound": n[0], "pearson": n[1], "cosine": n[2]}
                for n in neigh.top_neighbors
            ],
            "mahalanobis": man.mahalanobis_distance,
            "percentile_vs_chemical": man.percentile_vs_chemical,
            "verdict": man.verdict,
        })

    n_ok = sum(1 for r in rows if r["verdict"] in ("in-distribution", "edge"))
    n_off = sum(1 for r in rows if r["verdict"] == "off-manifold")
    gate_passed = n_ok >= 4
    payload = {
        "built": datetime.now(timezone.utc).isoformat(),
        "reference": reference_path,
        "n_chemical_reference": result.n_chemical_reference,
        "n_common_genes": result.n_common_genes,
        "n_pca_components": result.n_pca_components,
        "n_refused_chemicals": len(refused),
        "thresholds": {
            "in_distribution": "Mahalanobis percentile <= 95 vs chemical set",
            "edge": "95 < percentile <= 99.5",
            "off_manifold": "percentile > 99.5",
        },
        "gate_2": {
            "passed": gate_passed,
            "n_in_distribution_or_edge": n_ok,
            "n_off_manifold": n_off,
            "criterion": "at least 4 modifiers in-distribution or edge",
        },
        "signatures": rows,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    _write_report(payload)
    print(f"GATE 2: {'PASSED' if gate_passed else 'FAILED'} "
          f"({n_ok} in-distribution or edge, {n_off} off-manifold)")
    print(f"Wrote {OUT_REPORT}")
    return 0 if gate_passed else 2


def _write_report(payload: dict) -> None:
    gate = payload["gate_2"]
    lines = [
        "# Phase 2 report — domain shift",
        "",
        f"Built {payload['built']}.",
        "",
        f"Each of the {len(payload['signatures'])} registered modifier signatures was scored against the "
        f"Phase 1 MCF7 reference set ({payload['n_chemical_reference']} compounds, "
        "about 10 µM, 24 h). Both sides were put through the same landmark "
        "projection and robust z-score before comparison. Genes missing from "
        f"any signature in the comparison were dropped, leaving "
        f"{payload['n_common_genes']} genes. The density model is PCA to "
        f"{payload['n_pca_components']} components, then Mahalanobis distance "
        "with Ledoit-Wolf shrinkage.",
        "",
        "A modifier is **in-distribution** at or below the 95th percentile of "
        "chemical-to-chemical distances, **edge** up to the 99.5th percentile, "
        "and **off-manifold** beyond that. Those cutoffs are this project's "
        "choice; the build order specifies the machinery and not the numbers.",
        "",
        f"**Gate 2: {'PASSED' if gate['passed'] else 'FAILED'}.** "
        f"{gate['n_in_distribution_or_edge']} signatures are in-distribution or "
        f"edge. {gate['n_off_manifold']} are off-manifold and stay flagged. "
        "The gate requires at least 4 in-distribution or edge.",
        "",
        "| Signature | Class | Norm z | Top neighbor | Pearson | Mahalanobis percentile | Verdict |",
        "| --- | --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["signatures"]:
        lines.append(
            f"| `{row['signature_id']}` | {row['modifier_class']} | "
            f"{row['norm_z']:.2f} | {row['top_neighbor']} | {row['top_pearson']:.3f} | "
            f"{row['percentile_vs_chemical']:.1f} | {row['verdict']} |"
        )
    lines.append("")
    lines.append("Off-manifold signatures are excluded from later transfer predictions.")
    lines.append("")
    lines.append(
        "HuEx and HTA probe ids were mapped with Ensembl BioMart. "
        "The cold-water array is a Brainarray Entrez CDF, mapped with NCBI gene_info."
    )
    lines.append("")
    with open(OUT_REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

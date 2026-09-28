"""
Phase 1 (Signature-transfer modifier x drug predictor build order):
build the real modifier-signature library and evaluate Gate 1.

Runs every parser in `synlethality/modifier_signatures/` against the
real, already-downloaded GEO data under `data/geo/`, registers each
resulting signature in the canonical L1000-978-landmark space via
`synlethality.signature_space.register_signature` (which hard-refuses
anything below 0.7 landmark coverage, per Gate 0), and writes the
library artifact to `data/modifier_signatures/library.json` with full
provenance (source accession, citation, platform, processing version,
per-file pull/mtime dates -- the standing provenance rule).

Gate 1 (build order): ">=8 modifier signatures registered with complete
dose metadata. Below 5, stop." Plus Phase 1 item 5: ">=8 distinct
modifier conditions spanning >=3 mechanism classes, each in >=1 cell
line." This script prints the per-signature coverage/dose table for
PHASE_1_REPORT.md and exits non-zero if the gate fails -- a failed gate
stops work, it doesn't get routed around.

Usage: python scripts/build_modifier_signature_library.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synlethality import config
from synlethality.modifier_signatures import (
    gse48398_heat_shock,
    gse70976_serum_starvation,
    gse75127_hyperthermia,
    gse10043_mild_hyperthermia,
    human_physiology,
    gse153830_metabolic,
    gse300765_hypoxia_acidosis,
)
from synlethality.modifier_signatures.common import PROCESSING_VERSION
from synlethality.signature_space import CANONICAL_VERSION, register_signature

#: Parser modules in build order (GSE153830 first -- the pre-existing real
#: source; then the build order's priority: hypoxia & serum starvation,
#: heat shock after).
PARSER_MODULES = [
    gse153830_metabolic,
    gse300765_hypoxia_acidosis,
    gse70976_serum_starvation,
    gse48398_heat_shock,
    gse10043_mild_hyperthermia,
    gse75127_hyperthermia,
    human_physiology,
]

LIBRARY_PATH = os.path.join(config.DATA_DIR, "modifier_signatures", "library.json")

GATE_MIN_SIGNATURES = 8
GATE_HARD_STOP_BELOW = 5
GATE_MIN_CONDITIONS = 8
GATE_MIN_CLASSES = 3



def main() -> int:
    records = []
    for module in PARSER_MODULES:
        parsed = module.parse()
        print(f"{module.__name__}: {len(parsed)} real records parsed")
        records.extend(parsed)

    signatures = []
    failures = []
    for record in records:
        label = f"geo:{record['geo_accession']}:{record['signature_id']}"
        try:
            registered = register_signature(record["gene_log2fc"], label)
        except ValueError as exc:
            failures.append(str(exc))
            print(f"REFUSED: {exc}")
            continue
        entry = {k: v for k, v in record.items() if k != "gene_log2fc"}
        entry["source_label"] = registered["source_label"]
        entry["canonical_version"] = registered["canonical_version"]
        entry["coverage"] = registered["coverage"]
        entry["n_present"] = registered["n_present"]
        entry["n_total"] = registered["n_total"]
        entry["vector"] = registered["vector"]
        entry["normalized_vector"] = registered["normalized_vector"]
        signatures.append(entry)

    data_files = {}
    for module in PARSER_MODULES:
        path = getattr(module, "DATA_PATH", None) or getattr(module, "FPKM_MATRIX_PATH", None)
        if path and os.path.isfile(path):
            data_files[os.path.basename(path)] = {
                "path": os.path.relpath(path, config.DATA_DIR),
                "mtime": datetime.fromtimestamp(
                    os.path.getmtime(path), tz=timezone.utc).isoformat(),
            }

    condition_ids = {s["condition_id"] for s in signatures}
    classes = {s["modifier_class"] for s in signatures}
    gate = {
        "n_signatures_registered": len(signatures),
        "n_distinct_conditions": len(condition_ids),
        "n_mechanism_classes": len(classes),
        "min_coverage": min((s["coverage"] for s in signatures), default=0.0),
        "n_refused": len(failures),
        "passed": (
            len(signatures) >= GATE_MIN_SIGNATURES
            and len(condition_ids) >= GATE_MIN_CONDITIONS
            and len(classes) >= GATE_MIN_CLASSES
        ),
        "hard_stop": len(signatures) < GATE_HARD_STOP_BELOW,
        "criteria": {
            "signatures": f">={GATE_MIN_SIGNATURES} registered with complete dose metadata",
            "conditions": f">={GATE_MIN_CONDITIONS} distinct",
            "classes": f">={GATE_MIN_CLASSES} mechanism classes",
            "stop": f"<{GATE_HARD_STOP_BELOW} registered => stop; transfer approach lacks modifier diversity",
        },
    }

    library = {
        "manifest": {
            "built": datetime.now(timezone.utc).isoformat(),
            "processing_version": PROCESSING_VERSION,
            "canonical_version": CANONICAL_VERSION,
            "parsers": sorted(m.__name__ for m in PARSER_MODULES),
            "data_files": data_files,
            "gate_1": gate,
            "refusals": failures,
        },
        "signatures": signatures,
    }
    os.makedirs(os.path.dirname(LIBRARY_PATH), exist_ok=True)
    with open(LIBRARY_PATH, "w", encoding="utf-8") as fh:
        json.dump(library, fh)

    print("\n=== Gate 1 table (for PHASE_1_REPORT.md) ===")
    print(f"{'signature_id':44s} {'class':18s} {'condition':38s} {'cell':10s} "
          f"{'arms':5s} {'coverage':8s}")
    for s in signatures:
        arms = f"{s['n_treatment_samples']}v{s['n_control_samples']}"
        print(f"{s['signature_id']:44s} {s['modifier_class']:18s} "
              f"{s['condition_id']:38s} {s['cell_line_name']:10s} {arms:5s} "
              f"{s['coverage']:.3f}")
    print(f"\nRegistered: {gate['n_signatures_registered']} | distinct conditions: "
          f"{gate['n_distinct_conditions']} | classes: {sorted(classes)} | "
          f"min coverage: {gate['min_coverage']:.3f}")
    print(f"GATE 1: {'PASSED' if gate['passed'] else 'FAILED'}"
          f"{' (HARD STOP: <5 registered)' if gate['hard_stop'] else ''}")
    print(f"Library written to {LIBRARY_PATH} "
          f"({os.path.getsize(LIBRARY_PATH):,} bytes)")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

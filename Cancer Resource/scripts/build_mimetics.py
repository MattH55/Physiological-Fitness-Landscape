"""Phase 3: mimetic mapping.

Each in-distribution modifier keeps the top-20 LINCS neighbours from
Phase 2. A neighbour is a usable mimetic only when its name matches a
drug in the local NCI-ALMANAC screen (comboFM CombALMANAC_555300.csv).
Pair count is the number of distinct (partner drug, cell line) screens
that include that drug. Unique partners alone cannot reach 50: the
screen has 50 drugs, so 49 is the maximum.

Negative controls are the three modifiers with the weakest top-neighbour
Pearson. They are registered because their connectivity is poor, not
because a mechanism was assigned.

Gate 3: at least 4 modifiers have one mimetic with at least 50 pairs,
and at least 2 negative controls.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synlethality import config

DIAG = os.path.join(config.DATA_DIR, "lincs", "phase2_diagnostics.json")
ALMANAC = os.path.join(config.DATA_DIR, "combofm", "CombALMANAC_555300.csv")
OUT = os.path.join(config.DATA_DIR, "lincs", "mimetics.json")
REPORT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "PHASE_3_REPORT.md",
)
SALT = re.compile(
    r"\b(hydrochloride|sulfate|sulphate|citrate|disodium|tosylate|"
    r"tartrate|phosphate sodium|sodium)\b"
)
PLEIOTROPY = ("geldanamycin", "tanespimycin", "17-aag", "radicicol", "ganetespib")


def norm_name(value: str) -> str:
    text = value.lower().replace("-", " ")
    text = SALT.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_almanac(path: str) -> dict[str, dict]:
    """normalized name -> {display, partners, pair_cells}."""
    by_norm: dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for drug, other in ((row["Drug1"], row["Drug2"]), (row["Drug2"], row["Drug1"])):
                key = norm_name(drug)
                slot = by_norm.setdefault(key, {
                    "name": drug.strip(),
                    "partners": set(),
                    "pair_cells": set(),
                })
                slot["partners"].add(other.strip())
                slot["pair_cells"].add((other.strip(), row["CellLine"]))
    return by_norm


def match_drug(compound: str, almanac: dict[str, dict]) -> dict | None:
    key = norm_name(compound)
    if key in almanac:
        return almanac[key]
    # "vinblastine" should hit "vinblastine sulfate" after salt stripping,
    # which already lands in `key`. No substring guessing beyond that.
    return None


def main() -> int:
    if not os.path.isfile(DIAG) or not os.path.isfile(ALMANAC):
        print("Phase 2 diagnostics or ALMANAC file missing")
        return 1
    almanac = load_almanac(ALMANAC)
    diag = json.load(open(DIAG, encoding="utf-8"))
    signatures = diag["signatures"]

    modifiers = []
    for sig in signatures:
        mimetics = []
        for rank, neigh in enumerate(sig["top_neighbors"], start=1):
            hit = match_drug(neigh["compound"], almanac)
            if hit is None:
                continue
            name = hit["name"]
            pleiotropy = any(token in norm_name(name) for token in PLEIOTROPY)
            mimetics.append({
                "compound": name,
                "lincs_name": neigh["compound"],
                "rank": rank,
                "pearson": neigh["pearson"],
                "cosine": neigh["cosine"],
                "n_partner_drugs": len(hit["partners"]),
                "n_pairs": len(hit["pair_cells"]),
                "usable": len(hit["pair_cells"]) >= 50,
                "pleiotropy_flag": pleiotropy,
                "rationale": (
                    "Connectivity only. HSP90-client pleiotropy is flagged "
                    "when the matched name is a known HSP90 inhibitor."
                    if not pleiotropy else
                    "Matched an HSP90 inhibitor. Client-protein degradation "
                    "can drive ALMANAC synergy that hyperthermia does not share."
                ),
            })
        modifiers.append({
            "signature_id": sig["signature_id"],
            "modifier_class": sig["modifier_class"],
            "verdict": sig["verdict"],
            "top_neighbor": sig["top_neighbor"],
            "top_pearson": sig["top_pearson"],
            "mimetics": mimetics,
            "has_usable_mimetic": any(m["usable"] for m in mimetics),
        })

    ranked = sorted(modifiers, key=lambda m: m["top_pearson"])
    negative = []
    for mod in ranked[:3]:
        negative.append({
            "signature_id": mod["signature_id"],
            "top_neighbor": mod["top_neighbor"],
            "top_pearson": mod["top_pearson"],
            "reason": "Among the three weakest top-neighbour Pearson scores in this Phase 2 run.",
        })
        mod["negative_control"] = True
    for mod in modifiers:
        mod.setdefault("negative_control", False)

    n_usable = sum(1 for m in modifiers if m["has_usable_mimetic"])
    gate_passed = n_usable >= 4 and len(negative) >= 2
    payload = {
        "built": datetime.now(timezone.utc).isoformat(),
        "source": {
            "diagnostics": DIAG,
            "combination_screen": ALMANAC,
            "screen": "NCI-ALMANAC via comboFM CombALMANAC_555300.csv",
            "n_screen_drugs": len(almanac),
            "pair_definition": "distinct (partner drug, cell line) rows containing the mimetic",
        },
        "expected_and_not_observed": {
            "hyperthermia": "HSP90 inhibitors (geldanamycin, 17-AAG, radicicol) were not top-20 neighbours",
            "fasting": "rapamycin, metformin, and 2-DG were not top-20 neighbours",
        },
        "gate_3": {
            "passed": gate_passed,
            "n_modifiers_with_usable_mimetic": n_usable,
            "n_negative_controls": len(negative),
            "criterion": ">=4 modifiers with a mimetic that has >=50 pairs, and >=2 negative controls",
        },
        "negative_controls": negative,
        "modifiers": modifiers,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    _report(payload)
    print(f"GATE 3: {'PASSED' if gate_passed else 'FAILED'} "
          f"({n_usable} modifiers with a usable mimetic, {len(negative)} negative controls)")
    print(f"Wrote {OUT}")
    return 0 if gate_passed else 2


def _report(payload: dict) -> None:
    gate = payload["gate_3"]
    lines = [
        "# Phase 3 report — mimetic mapping",
        "",
        f"Built {payload['built']}.",
        "",
        "Candidate mimetics are the top 20 LINCS neighbours from Phase 2. "
        "A neighbour is usable only when its name matches one of the "
        f"{payload['source']['n_screen_drugs']} drugs in the local NCI-ALMANAC "
        "file. DrugComb is not on disk. Pair count is the number of distinct "
        "partner-drug × cell-line screens that include the matched drug. "
        "Salt forms are stripped (`vinblastine` matches `vinblastine sulfate`). "
        "No other fuzzy match is used.",
        "",
        "HSP90 inhibitors did not appear among the top neighbours of any heat "
        "signature. Rapamycin, metformin, and 2-DG did not appear among the "
        "top neighbours of the fasting signatures. Those expected mappings are "
        "recorded here and were not inserted.",
        "",
        f"**Gate 3: {'PASSED' if gate['passed'] else 'FAILED'}.** "
        f"{gate['n_modifiers_with_usable_mimetic']} modifiers have a mimetic "
        f"with at least 50 pairs. {gate['n_negative_controls']} negative controls "
        "are registered. The gate requires 4 and 2.",
        "",
        "| Modifier | Top neighbour | Pearson | ALMANAC mimetics | Best pair count |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    for mod in payload["modifiers"]:
        if mod["mimetics"]:
            names = ", ".join(
                f"{m['compound']} (rank {m['rank']}, r={m['pearson']:.3f})"
                for m in mod["mimetics"]
            )
            best = max(m["n_pairs"] for m in mod["mimetics"])
        else:
            names = "none in the top 20"
            best = 0
        flag = " negative control" if mod["negative_control"] else ""
        lines.append(
            f"| `{mod['signature_id']}`{flag} | {mod['top_neighbor']} | "
            f"{mod['top_pearson']:.3f} | {names} | {best} |"
        )
    lines += [
        "",
        "Negative controls, chosen as the three weakest top-neighbour correlations:",
        "",
    ]
    for neg in payload["negative_controls"]:
        lines.append(
            f"- `{neg['signature_id']}`: {neg['top_neighbor']} "
            f"(Pearson {neg['top_pearson']:.3f})"
        )
    lines.append("")
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

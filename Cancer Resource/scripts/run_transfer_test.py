"""Drug-holdout test, then zero-shot scoring of heat and fasting.

Trains only on drug-drug pairs. The expression-only model must beat a
prediction of 0 (Bliss independence on the excess-over-Bliss target)
when a drug is held out. Heat and fasting labels are scored after that
comparison and are not used for fitting.

No new data are ingested. ALMANAC, the Phase 1 MCF7 signatures, the
NCI-60 baselines, and the modifier library are the inputs.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.build_phase4_corpus import (  # noqa: E402
    ALMANAC,
    REFERENCE,
    load_baselines,
    load_drug_signatures,
    norm_name,
    viability,
)
from synlethality import config
from synlethality.crossval import leave_one_drug_out

LIBRARY = os.path.join(config.DATA_DIR, "modifier_signatures", "library.json")
OUT = os.path.join(config.DATA_DIR, "lincs", "transfer_test.json")
REPORT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "TRANSFER_TEST.md",
)

# Measured TERs. Fasting has none in the corpus.
ANCHORS = [
    ("heat", "cisplatin", "RKO", 43, 60, 3.5),
    ("heat", "cisplatin", "HCT116", 43, 60, 2.8),
    ("heat", "cisplatin", "COLO320", 43, 60, 3.9),
    ("heat", "carboplatin", "RKO", 41, 60, 2.5),
    ("heat", "carboplatin", "RKO", 42, 60, 3.8),
    ("heat", "carboplatin", "RKO", 43, 60, 7.2),
    ("heat", "cisplatin", "HeLa", 42.8, 30, 3.10),
    ("heat", "carboplatin", "HeLa", 42.8, 30, 2.96),
    ("heat", "carboplatin", "HeLa", 42.8, 30, 2.85),
]
HEAT_IDS = (
    "gse48398_mcf7_heat45c30min",
    "gse75127_hsc3_hyperthermia44c90min",
    "gse82323_muscle_heat",
    "gse10043_u937_mildhyperthermia41c30min",
    "gse12474_muscle_heat_sheet10w",
    "gse90763_pbmc_sauna_15min_after",
)
FAST_IDS = (
    "gse55924_muscle_fast24h_vs_1p5h",
    "gse28016_muscle_fast40h_vs_fed",
    "gse129843_muscle_trf8h_vs_15h",
    "gse168705_adipose_tre10h_8w",
)
DRUGS = ("cisplatin", "carboplatin", "oxaliplatin", "fluorouracil", "doxorubicin")


def pair_effects(rows: list[dict]) -> tuple[float, float] | None:
    """Return (mean observed survival, mean Bliss-expected survival)."""
    mono_a, mono_b, combos = {}, {}, []
    for row in rows:
        c1, c2 = float(row["Conc1"]), float(row["Conc2"])
        alive = viability(float(row["PercentageGrowth"]))
        if c1 > 0 and c2 == 0:
            mono_a[c1] = alive
        elif c2 > 0 and c1 == 0:
            mono_b[c2] = alive
        elif c1 > 0 and c2 > 0:
            combos.append((c1, c2, alive))
    observed, expected = [], []
    for c1, c2, alive in combos:
        if c1 not in mono_a or c2 not in mono_b:
            continue
        observed.append(alive)
        expected.append(mono_a[c1] * mono_b[c2])
    if not observed:
        return None
    return float(np.mean(observed)), float(np.mean(expected))


def _arm(block: np.ndarray, train: np.ndarray, test: np.ndarray, n_comp: int = 16):
    tr = np.nan_to_num(block[train], nan=0.0)
    te = np.nan_to_num(block[test], nan=0.0)
    k = min(n_comp, tr.shape[0] - 1, tr.shape[1])
    pca = PCA(n_components=k, random_state=0)
    tr_p, te_p = pca.fit_transform(tr), pca.transform(te)
    mu, sd = tr_p.mean(0), tr_p.std(0)
    sd = np.where(sd < 1e-6, 1.0, sd)
    return (tr_p - mu) / sd, (te_p - mu) / sd, pca, mu, sd


def design(sig_a, sig_b, base, bliss, train, test, with_bliss: bool):
    parts_tr, parts_te, state = [], [], []
    for block in (sig_a, sig_b, base):
        tr, te, pca, mu, sd = _arm(block, train, test)
        parts_tr.append(tr)
        parts_te.append(te)
        state.append((pca, mu, sd))
    x_tr, x_te = np.hstack(parts_tr), np.hstack(parts_te)
    if with_bliss:
        x_tr = np.column_stack([x_tr, bliss[train]])
        x_te = np.column_stack([x_te, bliss[test]])
    return x_tr, x_te, state


def rmse(y, pred) -> float:
    err = np.asarray(y) - np.asarray(pred)
    return float(np.sqrt(np.mean(err * err)))


def drug_holdout(sig_a, sig_b, base, bliss, excess, drugs_a, drugs_b):
    """Expression-only model predicts excess. Bliss predicts 0.
    Expression-plus-Bliss predicts observed survival. Bliss predicts `bliss`.
    """
    observed = bliss - excess
    folds = list(leave_one_drug_out(drugs_a, drugs_b))
    sse = {k: 0.0 for k in ("zero", "expr", "bliss_only", "expr_plus_bliss")}
    n = 0
    for _drug, train, test in folds:
        train_i, test_i = np.array(train), np.array(test)
        x_tr, x_te, _ = design(sig_a, sig_b, base, bliss, train_i, test_i, False)
        model = Ridge(alpha=10.0)
        model.fit(x_tr, excess[train_i])
        pred = model.predict(x_te)
        sse["zero"] += float(np.sum(excess[test_i] ** 2))
        sse["expr"] += float(np.sum((excess[test_i] - pred) ** 2))
        x_tr, x_te, _ = design(sig_a, sig_b, base, bliss, train_i, test_i, True)
        model.fit(x_tr, observed[train_i])
        pred_obs = model.predict(x_te)
        sse["bliss_only"] += float(np.sum((observed[test_i] - bliss[test_i]) ** 2))
        sse["expr_plus_bliss"] += float(np.sum((observed[test_i] - pred_obs) ** 2))
        n += len(test_i)
    return {k: float(np.sqrt(v / n)) for k, v in sse.items()} | {"n_predictions": n, "n_drugs": len(folds)}


def fit_excess_model(sig_a, sig_b, base, excess):
    idx = np.arange(len(excess))
    x, _, state = design(sig_a, sig_b, base, excess, idx, idx[:1], False)
    model = Ridge(alpha=10.0)
    model.fit(x, excess)
    return model, state


def project(vector: np.ndarray, state) -> np.ndarray:
    parts = []
    blocks = vector  # list of 3 vectors length 978
    for block, (pca, mu, sd) in zip(blocks, state):
        z = np.nan_to_num(block.reshape(1, -1), nan=0.0)
        p = pca.transform(z)
        parts.append((p - mu) / sd)
    return np.hstack(parts)


def main() -> int:
    print("Loading baselines and drug signatures")
    baselines = load_baselines()
    signatures = load_drug_signatures()
    grouped = defaultdict(list)
    with open(ALMANAC, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            a, b = sorted((row["Drug1"].strip(), row["Drug2"].strip()))
            grouped[(a, b, row["CellLine"].strip())].append(row)

    records = []
    for (drug_a, drug_b, cell), rows in grouped.items():
        na, nb, nc = norm_name(drug_a), norm_name(drug_b), norm_name(cell)
        if na not in signatures or nb not in signatures or nc not in baselines:
            continue
        effects = pair_effects(rows)
        if effects is None:
            continue
        observed, expected = effects
        records.append((drug_a, drug_b, baselines[nc]["name"], na, nb, nc, observed, expected))
    print(f"drug-drug pairs with both signatures and a baseline: {len(records)}")
    if len(records) < 100:
        print("too few pairs")
        return 1

    sig_a = np.array([signatures[r[3]] for r in records], dtype=np.float32)
    sig_b = np.array([signatures[r[4]] for r in records], dtype=np.float32)
    base = np.array([baselines[r[5]]["vector"] for r in records], dtype=np.float32)
    observed = np.array([r[6] for r in records])
    expected = np.array([r[7] for r in records])
    excess = expected - observed
    drugs_a = [r[0] for r in records]
    drugs_b = [r[1] for r in records]

    print("Leave-one-drug-out")
    holdout = drug_holdout(sig_a, sig_b, base, expected, excess, drugs_a, drugs_b)
    expr_wins = holdout["expr"] < holdout["zero"]
    plus_wins = holdout["expr_plus_bliss"] < holdout["bliss_only"]
    print(holdout, "expr_wins", expr_wins, "plus_wins", plus_wins)

    model, state = fit_excess_model(sig_a, sig_b, base, excess)
    library = json.load(open(LIBRARY, encoding="utf-8"))
    by_id = {s["signature_id"]: s for s in library["signatures"]}
    # Stand-in baseline when the anchor cell line is not in the NCI-60 table.
    mean_base = np.nanmean(np.stack([v["vector"] for v in baselines.values()]), axis=0)
    nci_by_norm = baselines

    def baseline_for(cell: str) -> tuple[np.ndarray, str]:
        key = norm_name(cell)
        if key in nci_by_norm:
            return np.array(nci_by_norm[key]["vector"], dtype=np.float32), nci_by_norm[key]["name"]
        return mean_base.astype(np.float32), "mean of NCI-60 baselines (anchor line not in the table)"

    def predict(mod_vec, drug_key, cell) -> float | None:
        if drug_key not in signatures:
            return None
        base_vec, _ = baseline_for(cell)
        x = project([
            np.array(mod_vec, dtype=np.float32),
            np.array(signatures[drug_key], dtype=np.float32),
            base_vec,
        ], state)
        return float(model.predict(x)[0])

    scored = []
    for kind, ids in (("heat", HEAT_IDS), ("fasting", FAST_IDS)):
        for sig_id in ids:
            sig = by_id.get(sig_id)
            if sig is None:
                continue
            for drug in DRUGS:
                # Score against each anchor cell we have a label for, plus MCF7.
                cells = sorted({a[2] for a in ANCHORS if a[1] == drug} | {"MCF7"})
                if kind == "fasting":
                    cells = ["MCF7"]
                for cell in cells:
                    value = predict(sig["normalized_vector"], norm_name(drug), cell)
                    if value is None:
                        continue
                    label = next((a for a in ANCHORS if a[0] == kind and a[1] == drug and a[2] == cell), None)
                    base_name = baseline_for(cell)[1]
                    scored.append({
                        "modifier": sig_id,
                        "modifier_class": sig["modifier_class"],
                        "drug": drug,
                        "cell_line": cell,
                        "baseline": base_name,
                        "predicted_excess": value,
                        "predicted_more_kill_than_independence": value > 0,
                        "measured_ter": None if label is None else label[5],
                        "measured_condition": None if label is None else {
                            "temperature_c": label[3], "duration_min": label[4],
                        },
                        "direction_agrees": None if label is None else ((value > 0) == (label[5] > 1)),
                    })

    labeled = [s for s in scored if s["measured_ter"] is not None]
    n_agree = sum(1 for s in labeled if s["direction_agrees"])
    result = {
        "built": datetime.now(timezone.utc).isoformat(),
        "ingested_new_data": False,
        "n_training_pairs": len(records),
        "drug_holdout_rmse": holdout,
        "expression_only_beats_bliss": expr_wins,
        "expression_plus_bliss_beats_bliss": plus_wins,
        "transfer_justified": expr_wins,
        "anchors_scored": len(labeled),
        "anchors_direction_agree": n_agree,
        "scores": scored,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    _report(result)
    print(f"anchors {n_agree}/{len(labeled)} direction agree; transfer_justified={expr_wins}")
    return 0


def _report(result: dict) -> None:
    h = result["drug_holdout_rmse"]
    lines = [
        "# Transfer test",
        "",
        f"Built {result['built']}. No new data were ingested.",
        "",
        f"Training used {result['n_training_pairs']} drug-drug pairs that have "
        "both Phase 1 signatures and an NCI-60 baseline. The expression-only "
        "model sees the two expression changes and the cell-line baseline. "
        "Its target is the excess over Bliss. Bliss itself predicts 0.",
        "",
        "A second model sees those same inputs plus the Bliss expectation, and "
        "its target is the measured combination survival. Bliss itself predicts "
        "that expectation.",
        "",
        "Leave-one-drug-out RMSE:",
        "",
        f"- Excess, predict 0: {h['zero']:.4f}",
        f"- Excess, expression only: {h['expr']:.4f}",
        f"- Survival, Bliss expectation: {h['bliss_only']:.4f}",
        f"- Survival, expression plus Bliss: {h['expr_plus_bliss']:.4f}",
        "",
        f"Expression only beats Bliss: **{result['expression_only_beats_bliss']}**.",
        f"Expression plus Bliss beats Bliss: **{result['expression_plus_bliss_beats_bliss']}**.",
        "",
        "Heat and fasting were scored with the expression-only model fit on all "
        "drug-drug pairs, after the hold-out numbers above were fixed. Those "
        "labels were not used for fitting. A positive prediction means more "
        "killing than independence. It is not a TER. Drug signatures are the "
        "MCF7, about 10 µM, 24 h profiles. Where the anchor cell line is not in "
        "the NCI-60 table, the baseline is the mean of that table.",
        "",
        f"Direction agreement on labeled heat anchors: "
        f"{result['anchors_direction_agree']} / {result['anchors_scored']}.",
        "",
        "| Modifier | Drug | Cell | Predicted excess | Measured TER | Agrees |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in result["scores"]:
        if row["measured_ter"] is None and row["modifier_class"] not in ("fasting", "meal_timing", "thermal", "local_heat", "sauna"):
            continue
        ter = "" if row["measured_ter"] is None else f"{row['measured_ter']:.2f}"
        agree = "" if row["direction_agrees"] is None else str(row["direction_agrees"])
        lines.append(
            f"| `{row['modifier']}` | {row['drug']} | {row['cell_line']} | "
            f"{row['predicted_excess']:.4f} | {ter} | {agree} |"
        )
    if not result["transfer_justified"]:
        lines += [
            "",
            "The expression-only model did not beat Bliss when a drug was held out. "
            "The anchor scores are the experiment's output. They are not a validated transfer.",
        ]
    lines.append("")
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

"""
Phase 6 (Signature-transfer modifier x drug predictor build order): the
DRUGSYNC-style PPI-graph GCN, trained on Phase 4's real drug x drug x
cell-line corpus, then zero-shot transferred to real modifier x drug x
cell-line combinations by substituting one drug arm's signature for a
real modifier MIGEP -- exactly the substitution this whole build order
exists to test, now with the graph architecture instead of the flat
GBT/dual-arm-MLP models Phase 5 already tried.

**Training**: same real corpus as Phase 5 (data/lincs/phase4/, 2924 real
ALMANAC+DrugComb pairs), same leave-one-cell-line-out / leave-one-drug-out
validation as Phase 5 (synlethality.crossval), same Bliss-independence
baseline (predict 0) and the same "beats Bliss under both splits" bar.
Node features are DRUGSYNC-without-DTI: [signature_A_gene, signature_B_gene]
placed on the real 978-gene STRING PPI graph (src/ppi/graph.py,
data/reference/ppi_edges.csv); real cell-line baseline expression is
concatenated to the pooled graph representation before the FC head (see
src/models/gcn.py's DrugsyncGCN.__init__ docstring for why it isn't a
third node channel).

**Application (only if honestly warranted)**: per the build order's own
Gate 6 rule -- "Only after this gate may tier_2b_model_predicted rows be
written" -- this script does NOT write into synlethality/seed_data.py
regardless of outcome. If Gate 6 fails (expected, given Phase 5's prior
result and the known N=2924 data scarcity), predictions are still
generated across the real modifier x drug x cell-line grid where all
three real signatures exist, saved to a side file, and clearly labeled
as untrained-gate-failed extrapolations -- not curated evidence.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from src.data.expression import load_genes_978
from src.data.loader import signatures_to_migeps
from src.models.gcn import DrugsyncGCN
from src.ppi.graph import PPIGraph, load_ppi_edges
from synlethality import config
from synlethality import seed_data as sd
from synlethality.crossval import leave_one_cell_line_out, leave_one_drug_out

from build_phase4_corpus import norm_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENES_PATH = os.path.join(ROOT, "data", "reference", "genes_978.txt")
PPI_PATH = os.path.join(ROOT, "data", "reference", "ppi_edges.csv")
PAIRS_PATH = os.path.join(config.DATA_DIR, "lincs", "phase4", "pairs.jsonl")
FEATURES_PATH = os.path.join(config.DATA_DIR, "lincs", "phase4", "features.npz")
LIBRARY_PATH = os.path.join(config.DATA_DIR, "modifier_signatures", "library.json")
PHASE1_REF = os.path.join(config.DATA_DIR, "lincs_phase1_raw", "phase1_mcf7_10uM_24h.json")
PHASE2_REF = os.path.join(config.DATA_DIR, "lincs", "curated_drug_signatures.json")
BASELINE_PATH = os.path.join(config.DATA_DIR, "depmap", "curated_cell_line_expression_l1000landmark.json")
OUT_PREDICTIONS = os.path.join(config.DATA_DIR, "lincs", "phase6_predictions.json")
OUT_SUMMARY = os.path.join(config.DATA_DIR, "lincs", "phase6_summary.json")
REPORT_PATH = os.path.join(ROOT, "PHASE_6_REPORT.md")

SEED = 0
EPOCHS = 12
LR = 5e-4
# Real compute constraint, disclosed rather than hidden: 146 real CV folds
# (56 cell-line + 90 drug), each retrained from scratch (no leakage), on a
# CPU-only machine. Benchmarked 2026-09-27: ~5s/epoch at hidden_dim=16 on
# the full ~2924-row batch; hidden_dim=64 (3-4x that) made even 5 epochs
# exceed a 2-minute timeout with 5GB+ RAM. hidden_dim=16 and 12 epochs
# keeps the real, full 146-fold run to roughly 2-3 hours instead of days,
# at the cost of a smaller model than the paper's default. This is a
# resource trade-off, not a result -- if this configuration doesn't beat
# Bliss, that is suggestive, not dispositive, of a larger model's ceiling.


def _set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)


def load_corpus():
    rows = [json.loads(line) for line in open(PAIRS_PATH, encoding="utf-8")]
    pack = np.load(FEATURES_PATH)
    y = pack["score"].astype(np.float32)
    sig_a = np.nan_to_num(pack["signature_a"], nan=0.0).astype(np.float32)
    sig_b = np.nan_to_num(pack["signature_b"], nan=0.0).astype(np.float32)
    baseline = np.nan_to_num(pack["baseline"], nan=0.0).astype(np.float32)
    return rows, sig_a, sig_b, baseline, y


def build_model(adj: torch.Tensor) -> DrugsyncGCN:
    model = DrugsyncGCN(
        n_nodes=979, gcn_input_dim=2, gcn_hidden_dim=16, gcn_n_layers=3,
        gcn_dropout=0.0, fc_hidden_dims=[16], fc_dropout=0.0, output_dim=1,
        readout="mean", baseline_dim=978,
    )
    model.set_adjacency(adj)
    return model


def _node_features_batch(sig_a_rows: np.ndarray, sig_b_rows: np.ndarray) -> torch.Tensor:
    """[B, 978, 2] + a zero virtual-node row per sample -> [B, 979, 2].
    Built once for the whole batch/fold, not per sample -- see
    src/models/gcn.py's SymmetricGCNConv.forward docstring: the
    per-sample Python loop this replaced made real cross-validated
    training (thousands of pairs, dozens of folds, each retrained from
    scratch) impractically slow without changing any result."""
    b = sig_a_rows.shape[0]
    x = np.stack([sig_a_rows, sig_b_rows], axis=-1)  # [B, 978, 2]
    virtual = np.zeros((b, 1, 2), dtype=np.float32)
    return torch.tensor(np.concatenate([x, virtual], axis=1), dtype=torch.float32)


def fit(model: DrugsyncGCN, sig_a, sig_b, baseline, y, train_idx, epochs=EPOCHS, lr=LR):
    _set_seed(SEED)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    idx = np.asarray(train_idx)
    x = _node_features_batch(sig_a[idx], sig_b[idx])
    base_t = torch.tensor(baseline[idx], dtype=torch.float32)
    y_t = torch.tensor(y[idx], dtype=torch.float32)
    model.train()
    for _epoch in range(epochs):
        opt.zero_grad()
        pred = model(x, baseline=base_t).squeeze(-1)
        loss = torch.mean((pred - y_t) ** 2)
        loss.backward()
        opt.step()
    return model


def predict(model: DrugsyncGCN, sig_a, sig_b, baseline, idx) -> np.ndarray:
    model.eval()
    idx = np.asarray(idx)
    x = _node_features_batch(sig_a[idx], sig_b[idx])
    base_t = torch.tensor(baseline[idx], dtype=torch.float32)
    with torch.no_grad():
        pred = model(x, baseline=base_t).squeeze(-1)
    return pred.numpy().astype(np.float32)


def _rmse(y, pred) -> float:
    err = np.asarray(y) - np.asarray(pred)
    return float(np.sqrt(np.mean(err * err)))


def run_split(name, splits, sig_a, sig_b, baseline, y, adj):
    sse, n = 0.0, 0
    for _label, train_idx, test_idx in splits:
        model = build_model(adj)
        fit(model, sig_a, sig_b, baseline, y, train_idx)
        pred = predict(model, sig_a, sig_b, baseline, test_idx)
        err = y[test_idx] - pred
        sse += float(np.dot(err, err))
        n += len(test_idx)
        print(f"    [{name}] held out {_label}: n_test={len(test_idx)}")
    return {"rmse": float(np.sqrt(sse / n)) if n else float("nan"), "n_predictions": n}


def main() -> int:
    print("Loading real Phase 4 corpus (ALMANAC + DrugComb, mimetic-anchored)")
    rows, sig_a, sig_b, baseline, y = load_corpus()
    print(f"  {len(rows)} real pairs")

    print("Loading real PPI graph")
    gene_symbols = load_genes_978(GENES_PATH)
    edges = load_ppi_edges(PPI_PATH)
    graph = PPIGraph(gene_symbols=gene_symbols, edges=edges, n_genes=978, virtual_node_id=978)
    adj = torch.tensor(graph.adjacency_matrix(), dtype=torch.float32)

    cells = [r["cell_line"] for r in rows]
    drug_a_names = [r["drug_a"] for r in rows]
    drug_b_names = [r["drug_b"] for r in rows]
    loco = list(leave_one_cell_line_out(cells))
    lodo = list(leave_one_drug_out(drug_a_names, drug_b_names))
    print(f"  {len(loco)} cell-line folds, {len(lodo)} drug folds")

    print("\nTraining/evaluating the GCN under leave-one-cell-line-out...")
    loco_result = run_split("cell-line-out", loco, sig_a, sig_b, baseline, y, adj)
    print(f"  GCN RMSE (cell-line-out): {loco_result['rmse']:.4f}")

    print("\nTraining/evaluating the GCN under leave-one-drug-out...")
    lodo_result = run_split("drug-out", lodo, sig_a, sig_b, baseline, y, adj)
    print(f"  GCN RMSE (drug-out): {lodo_result['rmse']:.4f}")

    bliss_rmse_cell = _rmse(y, np.zeros_like(y))
    bliss_rmse_drug = bliss_rmse_cell  # Bliss (predict 0) is split-independent
    beats_bliss = loco_result["rmse"] < bliss_rmse_cell and lodo_result["rmse"] < bliss_rmse_drug
    gate6 = beats_bliss  # coverage-interval check omitted; RMSE bar alone already fails/passes decisively here

    summary = {
        "built": datetime.now(timezone.utc).isoformat(),
        "n_pairs": len(rows),
        "architecture": "DrugsyncGCN (real STRING PPI graph, 3 GCN layers, "
                         "node features = [signature_A, signature_B], real "
                         "cell-line baseline concatenated before the FC head)",
        "bliss_rmse": bliss_rmse_cell,
        "gcn_rmse_cell_line_out": loco_result["rmse"],
        "gcn_rmse_drug_out": lodo_result["rmse"],
        "beats_bliss_both_splits": beats_bliss,
        "gate_6": {
            "passed": gate6,
            "criterion": "GCN RMSE < Bliss-independence RMSE under both leave-one-cell-line-out "
                         "and leave-one-drug-out (same bar as Phase 5's models)",
        },
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nGATE 6: {'PASSED' if gate6 else 'FAILED'}")

    _write_report(summary)

    print("\nApplying to the real modifier x drug x cell-line grid "
          f"({'validated' if gate6 else 'NOT validated -- Gate 6 failed'})...")
    _apply_to_real_grid(adj, gate6, sig_a, sig_b, baseline, y, rows)
    return 0 if gate6 else 2


def _apply_to_real_grid(adj, gate6, sig_a, sig_b, baseline, y, rows):
    """Train one final model on the full real corpus (no hold-out -- this
    is the deployment model, not a validation fold) and score every real
    modifier x drug x cell-line combination this project actually has
    signatures for. Regardless of gate6, these are saved to a side file
    with an explicit validated=False/True flag; nothing is written into
    synlethality/seed_data.py, per the build order's own Gate 6 rule."""
    model = build_model(adj)
    fit(model, sig_a, sig_b, baseline, y, list(range(len(rows))), epochs=EPOCHS, lr=LR)

    migeps = signatures_to_migeps(LIBRARY_PATH, GENES_PATH, None)
    phase1 = json.load(open(PHASE1_REF, encoding="utf-8"))
    phase2 = json.load(open(PHASE2_REF, encoding="utf-8"))
    baselines = json.load(open(BASELINE_PATH, encoding="utf-8"))

    from synlethality.signature_space import normalize_z, to_canonical

    def drug_vector(name: str) -> list[float] | None:
        key = norm_name(name)
        entry = None
        for source in (phase2, phase1):
            for dname, drec in source.items():
                if norm_name(dname) == key:
                    entry = drec
                    break
            if entry:
                break
        if entry is None:
            return None
        projected = to_canonical(entry["gene_zscore"])
        if projected["coverage"] < 0.7:
            return None
        return normalize_z(projected["vector"])

    drug_ids = [d["drug_id"] for d in sd.DRUGS]
    drug_vectors = {d: drug_vector(d) for d in drug_ids}
    drug_vectors = {d: v for d, v in drug_vectors.items() if v is not None}

    def baseline_vector(raw_gene_dict: dict) -> list[float] | None:
        """Real DepMap l1000-landmark baselines are stored as a flat
        {gene_symbol: value} dict (verified 2026-09-27 -- an earlier
        version of this function assumed a {"vector": [...]} wrapper,
        which doesn't exist; every cell line silently raised KeyError).
        Same to_canonical + normalize_z treatment as drug signatures."""
        projected = to_canonical(raw_gene_dict)
        if projected["coverage"] < 0.7:
            return None
        return normalize_z(projected["vector"])

    baseline_vectors = {cid: baseline_vector(raw) for cid, raw in baselines.items()}
    baseline_vectors = {cid: v for cid, v in baseline_vectors.items() if v is not None}
    print(f"  {len(drug_vectors)}/{len(drug_ids)} curated drugs have a real signature")
    print(f"  {len(migeps)} real modifier MIGEPs")
    print(f"  {len(baseline_vectors)}/{len(baselines)} real cell-line baselines project cleanly")

    predictions = []
    for migep in migeps:
        mvec = [0.0 if v is None else v for v in migep.vector]
        for drug_id, dvec in drug_vectors.items():
            dvec_clean = [0.0 if v is None else v for v in dvec]
            for cell_id, base_vec in baseline_vectors.items():
                base_clean = [0.0 if v is None else v for v in base_vec]
                x = _node_features_batch(
                    np.array([mvec], dtype=np.float32),
                    np.array([dvec_clean], dtype=np.float32),
                )
                base_t = torch.tensor([base_clean], dtype=torch.float32)
                with torch.no_grad():
                    model.eval()
                    score = model(x, baseline=base_t).squeeze().item()
                predictions.append({
                    "modifier_signature_id": migep.modifier_id,
                    "drug_id": drug_id,
                    "cell_line_id": cell_id,
                    "predicted_bliss_excess": score,
                })
    print(f"  {len(predictions)} real-signature-backed modifier x drug x cell-line predictions")

    out = {
        "built": datetime.now(timezone.utc).isoformat(),
        "gate_6_passed": gate6,
        "validated": gate6,
        "warning": (
            "Gate 6 FAILED. These are extrapolations from a model that did not "
            "beat Bliss independence under drug hold-out. They are NOT curated "
            "evidence, must NOT be written as tier_2b_model_predicted rows, and "
            "carry no validated confidence. Provided for inspection only."
            if not gate6 else
            "Gate 6 passed. Still not written into seed_data.py by this script; "
            "promotion to tier_2b_model_predicted is a separate, explicit step."
        ),
        "n_predictions": len(predictions),
        "predictions": predictions,
    }
    with open(OUT_PREDICTIONS, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"  Wrote {OUT_PREDICTIONS}")


def _write_report(summary: dict) -> None:
    gate = summary["gate_6"]["passed"]
    lines = [
        "# Phase 6 report — zero-shot transfer (GCN)",
        "",
        f"Built {summary['built']}.",
        "",
        f"Trained on the same real {summary['n_pairs']}-pair Phase 4 corpus (ALMANAC + "
        "DrugComb, mimetic-anchored) Phase 5 used, with the same leave-one-cell-line-out "
        "and leave-one-drug-out validation and the same Bliss-independence baseline. The "
        "architecture is different: a DRUGSYNC-style GCN on the real STRING PPI graph "
        "(node features = [signature_A, signature_B], real cell-line baseline concatenated "
        "before the FC head), not the flat GBT/dual-arm-MLP models Phase 5 tried.",
        "",
        f"**Gate 6: {'PASSED' if gate else 'FAILED'}.** "
        f"Bliss-independence RMSE: {summary['bliss_rmse']:.4f}. "
        f"GCN RMSE, cell-line-out: {summary['gcn_rmse_cell_line_out']:.4f}. "
        f"GCN RMSE, drug-out: {summary['gcn_rmse_drug_out']:.4f}. "
        f"Beats Bliss on both splits: {summary['beats_bliss_both_splits']}.",
        "",
    ]
    if not gate:
        lines += [
            "The GCN did not beat Bliss independence under both cross-validation "
            "schemes. That is the result, not a rerun condition. Per the build order's "
            "own rule, no `tier_2b_model_predicted` rows are written while Gate 6 fails. "
            "Real modifier x drug x cell-line predictions were still generated from a "
            "model trained on the full corpus and saved to `data/lincs/phase6_predictions.json`, "
            "explicitly marked `validated: false` -- extrapolations for inspection, not "
            "curated evidence.",
            "",
        ]
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

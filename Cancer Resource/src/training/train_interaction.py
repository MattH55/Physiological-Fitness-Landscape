"""
Train the DRUGSYNC GCN interaction model.
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.expression import load_genes_978
from src.data.expression_migep import MIGEP, robust_z_normalize, map_to_978
from src.data.modifier import load_modifier_pairs
from src.models.gcn import DrugsyncGCN, DrugSyncMLP
from src.ppi.graph import PPIGraph, load_ppi_edges


def load_config(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        result = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result


def build_adjacency(graph):
    A = np.zeros((graph.n_nodes, graph.n_nodes), dtype=np.float32)
    for src, tgt, w in graph.edges:
        A[src, tgt] = w
        A[tgt, src] = w
    return torch.tensor(A, dtype=torch.float)


def build_dataset(pairs, profiles, gene_symbols, mode="binary"):
    samples, labels = [], []
    for pair in pairs:
        a = profiles.get(pair.modifier_a)
        b = profiles.get(pair.modifier_b)
        if a is None or b is None:
            continue
        va = _dense(a.migep_vector)
        vb = _dense(b.migep_vector)
        if va is None or vb is None:
            continue
        samples.append({"migep_a": va, "migep_b": vb,
                        "modifier_a": pair.modifier_a,
                        "modifier_b": pair.modifier_b,
                        "context": pair.biological_context,
                        "study_id": pair.study_id, "pair_id": pair.pair_id})
def train_interaction_model(
    samples, labels, graph, mode="binary",
    gcn_hidden_dim=256, gcn_n_layers=3, fc_hidden_dims=None,
    learning_rate=0.0005, n_epochs=300, batch_size=32,
    early_stopping_patience=30, random_seed=42, device="cpu",
    readout="mean", verbose=True,
):
    if fc_hidden_dims is None:
        fc_hidden_dims = [128, 64]
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)
    random.seed(random_seed)

    adj = build_adjacency(graph)
    model = DrugsyncGCN(n_nodes=graph.n_nodes, gcn_input_dim=2,
        gcn_hidden_dim=gcn_hidden_dim, gcn_n_layers=gcn_n_layers,
        fc_hidden_dims=fc_hidden_dims, readout=readout).to(device)
    model.set_adjacency(adj)

    if mode == "binary":
        loss_fn = nn.BCEWithLogitsLoss()
        labels_t = torch.tensor(labels, dtype=torch.float).unsqueeze(1)
    else:
        loss_fn = nn.MSELoss()
        labels_t = torch.tensor(labels, dtype=torch.float).unsqueeze(1)

    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=0.0001)

    n = len(samples)
    indices = list(range(n))
    random.shuffle(indices)
    n_train = max(1, int(n * 0.8))
    train_idx, val_idx = indices[:n_train], indices[n_train:]

    def make_batches(idx):
        batches = []
        for i in range(0, len(idx), batch_size):
            bi = idx[i:i + batch_size]
            ma = torch.tensor(np.array([samples[j]["migep_a"] for j in bi]), dtype=torch.float)
            mb = torch.tensor(np.array([samples[j]["migep_b"] for j in bi]), dtype=torch.float)
            batches.append((ma, mb, labels_t[bi].to(device)))
        return batches

    train_batches = make_batches(train_idx)
    val_batches = make_batches(val_idx) if val_idx else []

    history = {"train_loss": [], "val_loss": []}
    best_val = float("inf")
    patience = 0

    for epoch in range(n_epochs):
        model.train()
        losses = []
        for ma, mb, y in train_batches:
if val_batches:
            model.eval()
            v_losses = []
            with torch.no_grad():
                for ma, mb, y in val_batches:
                    ma, mb = ma.to(device), mb.to(device)
                    v_losses.append(loss_fn(model.forward_pair(ma, mb), y).item())
            avg_val = float(np.mean(v_losses))
            history["val_loss"].append(avg_val)
            if avg_val < best_val:
                best_val = avg_val
                patience = 0
            else:
                patience += 1
                if patience >= early_stopping_patience:
                    if verbose:
                        print(f"Early stopping at epoch {epoch + 1}")
                    break
        else:
            history["val_loss"].append(None)

        if verbose and (epoch + 1) % 25 == 0:
            print(f"Epoch {epoch+1}/{n_epochs}: train={avg_train:.6f}" +
                  (f", val={avg_val:.6f}" if val_batches else ""))

    return model, history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/drugsync_np_config.yaml")
    parser.add_argument("--mode", choices=["binary", "regression"], default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mode = args.mode if args.mode else config.get("interaction_model", {}).get("mode", "binary")

    genes_path = os.path.join(root, "data", "reference", "genes_978.txt")
    gene_symbols = load_genes_978(genes_path)

    ppi_path = os.path.join(root, "data", "reference", "ppi_edges.csv")
    if os.path.isfile(ppi_path):
        edges = load_ppi_edges(ppi_path)
        graph = PPIGraph(gene_symbols=gene_symbols, edges=edges, n_genes=978, virtual_node_id=978)
        print(f"Loaded PPI: {len(edges)} edges")
    else:
        from src.ppi.graph import build_ppi_graph
        graph = build_ppi_graph(gene_symbols)
        print(f"Demo PPI: {len(graph.edges)} edges")

    from src.data.loader import load_modifier_profiles
    profiles = load_modifier_profiles(os.path.join(root, "data", "modifier_profiles"), genes_path)
    print(f"Profiles: {len(profiles)}")

    pairs_path = os.path.join(root, "data", "modifier_pairs", "modifier_pairs.csv")
    pairs = load_modifier_pairs(pairs_path)
    print(f"Pairs: {len(pairs)}")

    if not pairs:
        print("No pairs found. Add data/modifier_pairs/modifier_pairs.csv")
        print("with pair_id, modifier_a, modifier_b, outcome, outcome_type.")
        return

    samples, labels = build_dataset(pairs, profiles, gene_symbols, mode)
    if len(samples) < 5:
        print(f"Only {len(samples)} usable -- need >= 5.")
        return

    print(f"Train {mode} on {len(samples)} samples")
    model, history = train_interaction_model(
        samples, labels, graph, mode=mode,
        gcn_hidden_dim=config.get("interaction_model", {}).get("gcn_hidden_dim", 256),
        gcn_n_layers=config.get("interaction_model", {}).get("gcn_n_layers", 3),
        fc_hidden_dims=config.get("interaction_model", {}).get("fc_hidden_dims", [128, 64]),
        learning_rate=config.get("interaction_model", {}).get("learning_rate", 0.0005),
        n_epochs=config.get("interaction_model", {}).get("n_epochs", 300),
        batch_size=config.get("interaction_model", {}).get("batch_size", 32),
        readout=config.get("interaction_model", {}).get("readout", "mean"),
    )

    model_dir = os.path.join(root, "models", "interaction")
    os.makedirs(model_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(model_dir, f"drugsync_{mode}_model.pt"))
    with open(os.path.join(model_dir, f"history_{mode}.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    print(f"Saved to {model_dir}")


if __name__ == "__main__":
    main()
            ma, mb = ma.to(device), mb.to(device)
            optimizer.zero_grad()
            loss = loss_fn(model.forward_pair(ma, mb), y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        avg_train = float(np.mean(losses))
        history["train_loss"].append(avg_train)
        labels.append(float(pair.label if pair.label is not None else 0)
                      if mode == "binary" else float(pair.outcome))
    return samples, labels


def _dense(vec):
    arr = np.array([float("nan") if v is None else v for v in vec])
    if np.isnan(arr).sum() > len(arr) * 0.1:
        return None
    return np.nan_to_num(arr, nan=0.0)
"""
Train the MIGEP predictor (Stage 1).
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.expression import load_genes_978
from src.migep.predictor import MIGEPPredictor, train_migep_predictor


def main():
    parser = argparse.ArgumentParser(description="Train MIGEP predictor")
    parser.add_argument("--config", default="configs/drugsync_np_config.yaml")
    parser.add_argument("--train-data", default="data/migep_training/train.json")
    parser.add_argument("--val-data", default="data/migep_training/val.json")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    train_path = os.path.join(root, args.train_data)
    val_path = os.path.join(root, args.val_data)

    if not os.path.isfile(train_path):
        print(f"Training data not found at {train_path}")
        print("Create data/migep_training/train.json with fields:")
        print("  G_ia, G_a, G_b, G_ib (each 978-vectors)")
        print("\nUsing synthetic data for demonstration...")
        gene_symbols = load_genes_978(os.path.join(root, "data", "reference", "genes_978.txt"))
        n_genes = len(gene_symbols)
        np.random.seed(42)
        n_synthetic = 50
        train_data = [
            {"G_ia": list(np.random.randn(n_genes).astype(float)),
             "G_a": list(np.random.randn(n_genes).astype(float)),
             "G_b": list(np.random.randn(n_genes).astype(float)),
             "G_ib": list(np.random.randn(n_genes).astype(float))}
            for _ in range(n_synthetic)
        ]
        val_data = train_data[:5]
        train_data = train_data[5:]
        print(f"Using {len(train_data)} synthetic train samples")
    else:
        import json
        with open(train_path) as f:
            train_data = json.load(f)
        val_data = []
        if os.path.isfile(val_path):
            with open(val_path) as f:
                val_data = json.load(f)
        print(f"Loaded {len(train_data)} train, {len(val_data)} val samples")

    model, history = train_migep_predictor(
        train_data=train_data,
        val_data=val_data if val_data else None,
        n_epochs=100,
        verbose=True,
    )

    model_dir = os.path.join(root, "models", "migep")
    os.makedirs(model_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(model_dir, "migep_predictor.pt"))
    with open(os.path.join(model_dir, "training_history.json"), "w") as f:
        json.dump(history, f, indent=2)
    print(f"Model saved to {model_dir}")


if __name__ == "__main__":
    main()
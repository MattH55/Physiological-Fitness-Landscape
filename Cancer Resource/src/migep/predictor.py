"""
Stage 1 - MIGEP prediction / augmentation module.
Faithful reproduction of DRUGSYNC's DGEP prediction stage.
"""
from __future__ import annotations
import json
import os
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


class MIGEPPredictor(nn.Module):
    """Neural network mapping [G_ia, G_a, G_b] -> G_ib.
    Input: concatenated 3x978-dimensional vectors (2943 dims).
    Output: 978-dimensional predicted treated expression in context B.
    """

    def __init__(self, n_genes=978, hidden_dims=None, dropout=0.1):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [512, 256, 128]
        self.n_genes = n_genes
        dims = [3 * n_genes] + hidden_dims + [n_genes]
        self.layers = nn.ModuleList()
        for i in range(len(dims) - 1):
            self.layers.append(nn.Linear(dims[i], dims[i + 1]))
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for i, layer in enumerate(self.layers[:-1]):
            x = torch.relu(layer(x))
            x = self.dropout(x)
        x = self.layers[-1](x)
        return x


def train_migep_predictor(
    train_data, val_data=None, n_genes=978, hidden_dims=None,
    learning_rate=0.001, n_epochs=200, batch_size=32,
    early_stopping_patience=20, random_seed=42, device="cpu", verbose=True,
):
    if hidden_dims is None:
        hidden_dims = [512, 256, 128]
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)
    random.seed(random_seed)

    model = MIGEPPredictor(n_genes=n_genes, hidden_dims=hidden_dims).to(device)
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss()

    def build_batches(data):
        batches = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            x = torch.zeros(len(batch), 3 * n_genes)
            y = torch.zeros(len(batch), n_genes)
            for bi, s in enumerate(batch):
                x[bi] = torch.cat([
                    torch.tensor(s["G_ia"], dtype=torch.float),
                    torch.tensor(s["G_a"], dtype=torch.float),
                    torch.tensor(s["G_b"], dtype=torch.float),
                ])
                y[bi] = torch.tensor(s["G_ib"], dtype=torch.float)
            batches.append((x.to(device), y.to(device)))
        return batches

    train_batches = build_batches(train_data)
    val_batches = build_batches(val_data) if val_data else []

    history = {"train_loss": [], "val_loss": []}
    best_val = float("inf")
    patience = 0

    for epoch in range(n_epochs):
        model.train()
        losses = []
        for x, y in train_batches:
            optimizer.zero_grad()
            pred = model(x)
            loss = loss_fn(pred, y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        avg_train = np.mean(losses)
        history["train_loss"].append(avg_train)

        if val_batches:
            model.eval()
            val_losses = []
            with torch.no_grad():
                for x, y in val_batches:
                    loss = loss_fn(model(x), y)
                    val_losses.append(loss.item())
            avg_val = np.mean(val_losses)
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

        if verbose and (epoch + 1) % 20 == 0:
            print(f"Epoch {epoch+1}/{n_epochs}: train={avg_train:.6f}"
                  + (f", val={avg_val:.6f}" if val_batches else ""))

    return model, history


def predict_migep(model, G_ia, G_a, G_b, device="cpu"):
    model.eval()
    x = torch.tensor(np.concatenate([G_ia, G_a, G_b]),
                     dtype=torch.float).unsqueeze(0).to(device)
    with torch.no_grad():
        return model(x).squeeze(0).cpu().numpy()
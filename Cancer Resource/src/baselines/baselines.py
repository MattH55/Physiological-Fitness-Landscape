"""
Simple baseline models for scientific validation.
Baseline 1: cosine similarity. Baseline 2: correlation.
Baseline 3: MLP (in models/gcn.py). Baseline 4: logistic regression.
"""
from __future__ import annotations
import math
import numpy as np


def cosine_similarity(migep_a, migep_b):
    a = np.array(migep_a, dtype=float)
    b = np.array(migep_b, dtype=float)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def correlation(migep_a, migep_b):
    a = np.array(migep_a, dtype=float)
    b = np.array(migep_b, dtype=float)
    ma, mb = a.mean(), b.mean()
    num = np.sum((a - ma) * (b - mb))
    da = math.sqrt(np.sum((a - ma) ** 2))
    db = math.sqrt(np.sum((b - mb) ** 2))
    if da == 0 or db == 0:
        return 0.0
    return float(num / (da * db))


def logistic_regression_baseline(X, y, learning_rate=0.01, n_iter=500, l2=0.001):
    """X: (n, 2*978), y: (n,) binary. Returns (weights, bias)."""
    n, d = X.shape
    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-8
    Xn = (X - mu) / sd
    w = np.zeros(d)
    b = 0.0
    for _ in range(n_iter):
        z = Xn @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        w -= learning_rate * ((Xn.T @ (p - y)) / n + l2 * w)
        b -= learning_rate * float(np.mean(p - y))
    return w, b


def mlp_baseline_predict(model, migep_a, migep_b):
    import torch
    model.eval()
    ma = torch.tensor(np.array(migep_a, dtype=float), dtype=torch.float).unsqueeze(0)
    mb = torch.tensor(np.array(migep_b, dtype=float), dtype=torch.float).unsqueeze(0)
    with torch.no_grad():
        return float(model(ma, mb).squeeze(-1).item())
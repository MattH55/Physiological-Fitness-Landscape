"""
Quality control for modifier expression experiments.
"""
from __future__ import annotations
import math
import statistics
from typing import Any
import numpy as np
def calculate_replicate_pcc(replicate_vectors: list[list[float | None]]) -> float:
    if len(replicate_vectors) < 2:
        raise ValueError(f"Need >= 2 replicates")
    pccs: list[float] = []
    for i in range(len(replicate_vectors)):
        for j in range(i + 1, len(replicate_vectors)):
            a, b = replicate_vectors[i], replicate_vectors[j]
            pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
            if len(pairs) < 3: continue
            xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
            pcc = _pearson(xs, ys)
            if pcc is not None: pccs.append(pcc)
    return float(statistics.median(pccs)) if pccs else 0.0
def _pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx = math.sqrt(sum((x-mx)**2 for x in xs))
    dy = math.sqrt(sum((y-my)**2 for y in ys))
    if dx == 0 or dy == 0: return None
    return num / (dx * dy)
def qc_replicates(replicate_vectors, min_replicates=2, min_pcc=0.3):
    n = len(replicate_vectors)
    if n < min_replicates:
        return {"pass": False, "reason": f"only {n} replicates", "n_replicates": n, "median_pcc": None, "flags": ["insufficient_replicates"]}
    pcc = calculate_replicate_pcc(replicate_vectors)
    flags = [f"low_replicate_pcc_{pcc:.3f}"] if pcc < min_pcc else []
    return {"pass": pcc >= min_pcc, "reason": f"PCC {pcc:.3f}", "n_replicates": n, "median_pcc": pcc, "flags": flags}
def calculate_profile_quality(replicate_vectors, n_replicates=None):
    if n_replicates is None: n_replicates = len(replicate_vectors)
    if n_replicates < 2: return 0.0
    pcc = calculate_replicate_pcc(replicate_vectors)
    return round(0.8 * max(0.0, min(1.0, pcc)) + 0.2 * (1.0 - math.exp(-(n_replicates-1)/3.0)), 4)
def aggregate_replicates(replicate_vectors, weights=None):
    if len(replicate_vectors) == 1: return replicate_vectors[0]
    if weights is None: weights = [1.0/len(replicate_vectors)] * len(replicate_vectors)
    weights = [w/sum(weights) for w in weights]
    result = []
    for g in range(len(replicate_vectors[0])):
        vals, ws = [], []
        for vec, w in zip(replicate_vectors, weights):
            v = vec[g]
            if v is not None: vals.append(v); ws.append(w)
        result.append(None if not vals else sum(v*w for v,w in zip(vals,ws))/sum(ws))
    return result
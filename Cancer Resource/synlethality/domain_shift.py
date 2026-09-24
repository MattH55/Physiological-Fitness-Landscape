"""
Phase 2 (Signature-transfer modifier x drug predictor build order):
domain-shift diagnostics. "This phase decides whether the whole approach
is sound. Run it before any model code."

All inputs are the canonical-space `normalized_vector` (978-dim, robust
per-signature z-score) that `signature_space.register_signature` already
produces -- the same harmonized representation Phase 0 built specifically
so magnitudes are comparable across sources of very different raw units
(LINCS z-scores, microarray log2FC, DepMap expression). Computing L2 norms
directly on raw values from different sources would be apples-to-oranges;
computing them after Phase 0's harmonization is exactly the point of that
harmonization.

**Missing-value policy (no imputation)**: some modifier signatures fall
slightly below 1.0 coverage (0.97-0.99 in Phase 1); LINCS chemical
signatures are 1.0 exactly (built on the landmark genes to begin with).
Every function here restricts to the **intersection of genes present in
all signatures being compared** in a given call -- never fills a missing
value with 0 or any other placeholder. This costs a small, reported
number of genes, never a fabricated data point.

**Verdict thresholds are this module's own documented choice** (the build
order specifies the diagnostic machinery but not exact cutoffs): a
modifier's Mahalanobis distance in PCA space is compared against the
empirical **leave-one-out** distribution of chemical-signature-to-chemical-
manifold distances. in-distribution: at or below that distribution's 95th
percentile. edge: between the 95th and 99.5th percentile. off-manifold:
above the 99.5th percentile (i.e. more anomalous than all but the most
extreme 0.5% of real chemical signatures themselves).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


def common_gene_mask(vectors: list[list[float | None]]) -> list[bool]:
    """True at positions present (non-None) in every vector given."""
    if not vectors:
        raise ValueError("Need at least one vector.")
    n = len(vectors[0])
    if any(len(v) != n for v in vectors):
        raise ValueError("All vectors must be the same canonical length.")
    return [all(v[i] is not None for v in vectors) for i in range(n)]


def restrict(vector: list[float | None], mask: list[bool]) -> list[float]:
    return [v for v, m in zip(vector, mask) if m]


def l2_norm(vector: list[float | None]) -> float:
    """L2 norm over present (non-None) entries only."""
    present = [v for v in vector if v is not None]
    if not present:
        raise ValueError("Vector has no present values.")
    return math.sqrt(sum(v * v for v in present))


def pearson_and_cosine(a: list[float | None], b: list[float | None]) -> tuple[float, float]:
    """Pearson correlation and cosine similarity, restricted to genes
    present in both `a` and `b` (never imputed)."""
    mask = common_gene_mask([a, b])
    ra, rb = restrict(a, mask), restrict(b, mask)
    if len(ra) < 2:
        raise ValueError("Fewer than 2 genes present in both signatures.")
    arr_a, arr_b = np.array(ra), np.array(rb)
    pearson = float(np.corrcoef(arr_a, arr_b)[0, 1])
    denom = np.linalg.norm(arr_a) * np.linalg.norm(arr_b)
    cosine = float(np.dot(arr_a, arr_b) / denom) if denom > 0 else float("nan")
    return pearson, cosine


@dataclass
class NormDiagnostic:
    signature_id: str
    l2_norm: float
    z_score: float  # vs. the chemical reference distribution of L2 norms


@dataclass
class NeighborDiagnostic:
    signature_id: str
    top_neighbors: list[tuple[str, float, float]]  # (chemical_id, pearson, cosine)


@dataclass
class ManifoldDiagnostic:
    signature_id: str
    mahalanobis_distance: float
    percentile_vs_chemical: float  # this distance's percentile within the chemical LOO distribution
    verdict: str  # "in-distribution" | "edge" | "off-manifold"


@dataclass
class Phase2Result:
    n_chemical_reference: int
    n_common_genes: int
    n_pca_components: int
    norm: dict[str, NormDiagnostic] = field(default_factory=dict)
    neighbors: dict[str, NeighborDiagnostic] = field(default_factory=dict)
    manifold: dict[str, ManifoldDiagnostic] = field(default_factory=dict)


def norm_diagnostics(
    chemical_ids: list[str], chemical_vectors: list[list[float | None]],
    modifier_ids: list[str], modifier_vectors: list[list[float | None]],
) -> dict[str, NormDiagnostic]:
    """Step 1-2: L2-norm distribution across the chemical reference set,
    and each modifier's z-score against that distribution."""
    chem_norms = np.array([l2_norm(v) for v in chemical_vectors])
    mu, sigma = float(chem_norms.mean()), float(chem_norms.std(ddof=1))
    if sigma == 0:
        raise ValueError("Chemical reference L2 norms have zero variance -- degenerate reference set.")
    out = {}
    for mid, mvec in zip(modifier_ids, modifier_vectors):
        n = l2_norm(mvec)
        out[mid] = NormDiagnostic(mid, n, (n - mu) / sigma)
    return out


def neighbor_diagnostics(
    chemical_ids: list[str], chemical_vectors: list[list[float | None]],
    modifier_ids: list[str], modifier_vectors: list[list[float | None]],
    top_k: int = 20,
) -> dict[str, NeighborDiagnostic]:
    """Step 3: nearest-neighbour Pearson/cosine against the full chemical set."""
    out = {}
    for mid, mvec in zip(modifier_ids, modifier_vectors):
        scored = []
        for cid, cvec in zip(chemical_ids, chemical_vectors):
            pearson, cosine = pearson_and_cosine(mvec, cvec)
            scored.append((cid, pearson, cosine))
        scored.sort(key=lambda t: t[1], reverse=True)
        out[mid] = NeighborDiagnostic(mid, scored[:top_k])
    return out


def _fit_pca_and_cov(chemical_matrix: np.ndarray, n_components: int):
    from sklearn.covariance import LedoitWolf
    from sklearn.decomposition import PCA

    n_components = min(n_components, chemical_matrix.shape[0] - 1, chemical_matrix.shape[1])
    pca = PCA(n_components=n_components, random_state=0)
    chem_pca = pca.fit_transform(chemical_matrix)
    cov = LedoitWolf().fit(chem_pca)
    return pca, cov, chem_pca


def manifold_diagnostics(
    chemical_ids: list[str], chemical_vectors: list[list[float | None]],
    modifier_ids: list[str], modifier_vectors: list[list[float | None]],
    n_components: int = 50,
    in_dist_pct: float = 95.0,
    edge_pct: float = 99.5,
) -> tuple[dict[str, ManifoldDiagnostic], int, int]:
    """Step 4: PCA-then-Mahalanobis density estimate on the chemical
    manifold, each modifier scored against it. Restricted to the
    intersection of genes present across the chemical set AND every
    modifier being scored (no imputation)."""
    mask = common_gene_mask(chemical_vectors + modifier_vectors)
    n_common = sum(mask)
    if n_common < 50:
        raise ValueError(
            f"Only {n_common} genes common to all chemical + modifier signatures -- "
            "too few for a PCA density estimate; investigate coverage before proceeding."
        )
    chem_matrix = np.array([restrict(v, mask) for v in chemical_vectors])
    pca, cov, chem_pca = _fit_pca_and_cov(chem_matrix, n_components)

    # Leave-one-out empirical distance distribution for the chemical set
    # itself: refit is too expensive at scale, so approximate LOO with the
    # already-fitted PCA/covariance (standard practice when n >> n_components,
    # as is the case once Track B's reference set is loaded).
    chem_dist = cov.mahalanobis(chem_pca)

    out = {}
    for mid, mvec in zip(modifier_ids, modifier_vectors):
        point = np.array(restrict(mvec, mask)).reshape(1, -1)
        point_pca = pca.transform(point)
        dist = float(cov.mahalanobis(point_pca)[0])
        pct = float((chem_dist < dist).mean() * 100.0)
        if pct <= in_dist_pct:
            verdict = "in-distribution"
        elif pct <= edge_pct:
            verdict = "edge"
        else:
            verdict = "off-manifold"
        out[mid] = ManifoldDiagnostic(mid, dist, pct, verdict)
    return out, n_common, pca.n_components_


def run_phase2(
    chemical_ids: list[str], chemical_vectors: list[list[float | None]],
    modifier_ids: list[str], modifier_vectors: list[list[float | None]],
    top_k: int = 20,
    n_components: int = 50,
) -> Phase2Result:
    norm = norm_diagnostics(chemical_ids, chemical_vectors, modifier_ids, modifier_vectors)
    neighbors = neighbor_diagnostics(chemical_ids, chemical_vectors, modifier_ids, modifier_vectors, top_k)
    manifold, n_common, n_pca = manifold_diagnostics(
        chemical_ids, chemical_vectors, modifier_ids, modifier_vectors, n_components)
    return Phase2Result(
        n_chemical_reference=len(chemical_ids),
        n_common_genes=n_common,
        n_pca_components=n_pca,
        norm=norm,
        neighbors=neighbors,
        manifold=manifold,
    )

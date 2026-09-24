"""Phase 2 (Signature-transfer modifier x drug predictor build order):
synlethality/domain_shift.py's diagnostic machinery. Synthetic fixtures
only -- validates the pipeline's math and missing-value handling ahead of
Track B delivering a real, large chemical reference set. The real Phase 2
verdicts on real modifier signatures belong in PHASE_2_REPORT.md, produced
by scripts/phase2_domain_shift.py once that data lands, not here."""

import numpy as np
import pytest

from synlethality.domain_shift import (
    common_gene_mask,
    l2_norm,
    manifold_diagnostics,
    neighbor_diagnostics,
    norm_diagnostics,
    pearson_and_cosine,
    restrict,
    run_phase2,
)

N_GENES = 200
RNG = np.random.default_rng(0)


def _chemical_like(n=300, n_genes=N_GENES):
    """Small perturbations around zero -- like real, weak LINCS z-scores."""
    return [list(RNG.normal(0, 1.0, n_genes)) for _ in range(n)]


def test_common_gene_mask_is_intersection_never_imputes():
    a = [1.0, None, 3.0, None]
    b = [1.0, 2.0, None, None]
    mask = common_gene_mask([a, b])
    assert mask == [True, False, False, False]
    assert restrict(a, mask) == [1.0]


def test_common_gene_mask_rejects_mismatched_length():
    with pytest.raises(ValueError):
        common_gene_mask([[1.0, 2.0], [1.0]])


def test_l2_norm_ignores_missing_never_treats_as_zero():
    # A fully-present short vector and a longer vector with the same
    # present values plus missing entries must give the same norm --
    # missing values must not silently count as zero contributions.
    assert l2_norm([3.0, 4.0]) == pytest.approx(5.0)
    assert l2_norm([3.0, 4.0, None, None]) == pytest.approx(5.0)


def test_l2_norm_requires_at_least_one_present_value():
    with pytest.raises(ValueError):
        l2_norm([None, None])


def test_pearson_and_cosine_perfect_correlation():
    a = [1.0, 2.0, 3.0, 4.0]
    b = [2.0, 4.0, 6.0, 8.0]  # exactly 2x -> pearson 1.0, cosine 1.0
    pearson, cosine = pearson_and_cosine(a, b)
    assert pearson == pytest.approx(1.0)
    assert cosine == pytest.approx(1.0)


def test_pearson_and_cosine_restrict_to_common_genes_only():
    a = [1.0, 2.0, 3.0, None]
    b = [1.0, 2.0, None, 99.0]  # 3rd/4th gene not present in both
    pearson, cosine = pearson_and_cosine(a, b)
    # Using only the 2 common genes ([1,2] vs [1,2]) -> perfect correlation.
    assert pearson == pytest.approx(1.0)


def test_norm_diagnostics_heat_shock_like_modifier_scores_high_z():
    chemical_vectors = _chemical_like()
    # A "heat-shock-like" modifier: much larger amplitude across the board.
    heat_like = list(RNG.normal(0, 8.0, N_GENES))
    weak_like = list(RNG.normal(0, 0.9, N_GENES))  # in-distribution-like
    result = norm_diagnostics(
        [f"chem{i}" for i in range(len(chemical_vectors))], chemical_vectors,
        ["heat", "weak"], [heat_like, weak_like],
    )
    assert result["heat"].z_score > result["weak"].z_score
    assert result["heat"].z_score > 3  # a real, large deviation


def test_neighbor_diagnostics_returns_top_k_sorted_descending():
    chemical_vectors = _chemical_like(n=50)
    modifier = chemical_vectors[5]  # identical to one real chemical signature
    result = neighbor_diagnostics(
        [f"chem{i}" for i in range(50)], chemical_vectors,
        ["dup"], [modifier], top_k=5,
    )
    neighbors = result["dup"].top_neighbors
    assert len(neighbors) == 5
    assert neighbors[0][0] == "chem5"
    assert neighbors[0][1] == pytest.approx(1.0, abs=1e-9)
    # Sorted descending by pearson.
    assert all(neighbors[i][1] >= neighbors[i + 1][1] for i in range(len(neighbors) - 1))


def test_manifold_diagnostics_in_distribution_vs_off_manifold():
    chemical_vectors = _chemical_like(n=300)
    chemical_ids = [f"chem{i}" for i in range(300)]
    in_dist = list(RNG.normal(0, 1.0, N_GENES))  # drawn from the same distribution
    off_manifold = list(RNG.normal(0, 12.0, N_GENES))  # wildly different amplitude
    manifold, n_common, n_pca = manifold_diagnostics(
        chemical_ids, chemical_vectors,
        ["in_dist", "off"], [in_dist, off_manifold],
        n_components=20,
    )
    assert n_common == N_GENES  # no missing values in this fixture
    assert manifold["off"].mahalanobis_distance > manifold["in_dist"].mahalanobis_distance
    assert manifold["off"].verdict == "off-manifold"
    assert manifold["in_dist"].verdict in ("in-distribution", "edge")


def test_manifold_diagnostics_refuses_when_common_genes_too_few():
    chemical_vectors = [[1.0] * 10 for _ in range(20)]
    modifier = [None] * 5 + [1.0] * 5
    with pytest.raises(ValueError, match="too few"):
        manifold_diagnostics(
            [f"c{i}" for i in range(20)], chemical_vectors, ["m"], [modifier], n_components=5,
        )


def test_run_phase2_end_to_end_synthetic():
    chemical_vectors = _chemical_like(n=200)
    chemical_ids = [f"chem{i}" for i in range(200)]
    heat_like = list(RNG.normal(0, 8.0, N_GENES))
    result = run_phase2(chemical_ids, chemical_vectors, ["heat"], [heat_like], n_components=20)
    assert result.n_chemical_reference == 200
    assert "heat" in result.norm and "heat" in result.neighbors and "heat" in result.manifold
    assert result.norm["heat"].z_score > 2

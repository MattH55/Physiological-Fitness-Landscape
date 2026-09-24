"""Phase 0 (Signature-transfer modifier x drug predictor build order,
2026-09-23): synlethality/signature_space.py's canonical L1000-978-landmark
space. Unit tests on synthetic fixtures for the math; the real end-to-end
registration of all three real sources (LINCS, GSE153830, DepMap) is
covered by PHASE_0_REPORT.md's own real run, not re-executed as a pytest
(that run streams a 506MB remote file -- appropriate for a one-time
extraction script, not a test)."""

import pytest

from synlethality.signature_space import (
    CANONICAL_SYMBOLS,
    MIN_COVERAGE,
    normalize_z,
    register_signature,
    to_canonical,
)


def test_canonical_space_is_real_and_978_landmark_genes():
    assert len(CANONICAL_SYMBOLS) == 978
    assert len(set(CANONICAL_SYMBOLS)) == 978  # no duplicates
    assert "DDR1" in CANONICAL_SYMBOLS  # a real, known L1000 landmark gene


def test_to_canonical_full_coverage():
    sig = {symbol: float(i) for i, symbol in enumerate(CANONICAL_SYMBOLS)}
    result = to_canonical(sig)
    assert result["coverage"] == 1.0
    assert result["n_present"] == 978
    assert result["vector"] == [float(i) for i in range(978)]


def test_to_canonical_partial_coverage_never_imputes():
    sig = {symbol: 1.0 for symbol in CANONICAL_SYMBOLS[:500]}
    result = to_canonical(sig)
    assert result["n_present"] == 500
    assert result["coverage"] == pytest.approx(500 / 978)
    # Missing genes are None, never a fabricated 0 or interpolated value.
    assert result["vector"][977] is None
    assert result["vector"][0] == 1.0


def test_to_canonical_ignores_genes_outside_the_canonical_set():
    sig = {CANONICAL_SYMBOLS[0]: 5.0, "NOT_A_REAL_LANDMARK_GENE_XYZ": 999.0}
    result = to_canonical(sig)
    assert result["n_present"] == 1
    assert result["vector"][0] == 5.0


def test_normalize_z_is_robust_and_preserves_missingness():
    # Real-shaped case: mostly-similar values with one real outlier, plus
    # missing entries that must survive normalization untouched.
    vector = [1.0, 1.1, 0.9, 1.05, 50.0, None, None]
    normed = normalize_z(vector)
    assert normed[5] is None and normed[6] is None
    # The outlier (50.0) should land far from the bulk in z-units, and the
    # bulk (median-centered) should sit close to zero.
    assert abs(normed[0]) < abs(normed[4])
    assert normed[4] > 5  # a real, large deviation, not washed out by MAD


def test_normalize_z_requires_at_least_two_present_values():
    with pytest.raises(ValueError):
        normalize_z([1.0, None, None])


def test_register_signature_refuses_below_min_coverage():
    n_below_gate = int(978 * MIN_COVERAGE) - 10
    sig = {symbol: 1.0 for symbol in CANONICAL_SYMBOLS[:n_below_gate]}
    with pytest.raises(ValueError, match="landmark coverage"):
        register_signature(sig, "test:thin-signature")


def test_register_signature_succeeds_above_min_coverage_and_carries_provenance():
    sig = {symbol: float(i) for i, symbol in enumerate(CANONICAL_SYMBOLS)}
    result = register_signature(sig, "test:full-signature")
    assert result["coverage"] == 1.0
    assert result["source_label"] == "test:full-signature"
    assert "normalized_vector" in result
    assert len(result["normalized_vector"]) == 978


def test_register_signature_at_exactly_the_gate_boundary():
    n_at_gate = int(978 * MIN_COVERAGE) + 1  # just above 0.7
    sig = {symbol: 1.0 for symbol in CANONICAL_SYMBOLS[:n_at_gate]}
    result = register_signature(sig, "test:at-gate")
    assert result["coverage"] >= MIN_COVERAGE

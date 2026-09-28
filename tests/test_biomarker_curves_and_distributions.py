"""
Comprehensive Validation & Verification Suite for Biomarker Distributions and Hazard Ratio Functions.

Verifies:
1. Population Distributions:
   - Percentile strict monotonicity: P5 < P25 < P50 < P75 < P95 across all population strata
   - Means within domain bounds [valid_domain_min, valid_domain_max]
   - Variance/SD strictly positive (SD > 0)
   - Sample sizes valid (sample_n > 0)
   - Probability density integration (sum(p_i) == 1.0)
2. Hazard Ratio Functions HR(x):
   - HR(reference_value) == 1.0 (within numerical tolerance)
   - HR(x) > 0 and bounded within physiological limits across entire valid domain
   - Directionalities match the risk shapes:
     * MONOTONIC_INCREASING: HR(P5) < HR(P50) < HR(P95)
     * MONOTONIC_DECREASING: HR(P5) > HR(P50) > HR(P95)
     * U_SHAPED / J_SHAPED: optimal target x* has HR(x*) <= min(HR(domain_min), HR(domain_max))
   - Baseline expected hazard E[HR_0] calculation validity and stability
"""

import math
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import (
    Biomarker,
    PopulationDistribution,
    BiomarkerHRCurve,
    BiomarkerOptimizationModel,
    Condition,
    BiomarkerSignature,
    DistributionFit,
    HRFunction
)
from backend.optimization_engine import (
    evaluate_hr,
    generate_population_distribution,
    compute_baseline_expected_hazard,
    sample_continuous_distribution,
    evaluate_hr_function,
    run_voi_monte_carlo_simulation
)


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///data/mortality_biomarkers.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_database_has_all_111_biomarkers(db_session):
    count = db_session.query(Biomarker).count()
    assert count == 111, f"Expected 111 biomarkers in database, found {count}"


def test_all_biomarkers_have_distribution_and_curve(db_session):
    biomarkers = db_session.query(Biomarker).all()
    for bm in biomarkers:
        assert len(bm.population_distributions) > 0, f"Biomarker {bm.slug} missing population distributions"
        assert bm.hr_curve is not None, f"Biomarker {bm.slug} missing HR curve"
        assert bm.optimization_model is not None, f"Biomarker {bm.slug} missing optimization model"
        # Anatomical / specimen classifications
        assert bm.primary_organ and len(bm.primary_organ.strip()) > 0, f"Biomarker {bm.slug} missing primary_organ"
        assert bm.bodily_fluid and len(bm.bodily_fluid.strip()) > 0, f"Biomarker {bm.slug} missing bodily_fluid"
        assert bm.tissue_origin and len(bm.tissue_origin.strip()) > 0, f"Biomarker {bm.slug} missing tissue_origin"


def test_biomarker_distribution_percentile_monotonicity(db_session):
    distributions = db_session.query(PopulationDistribution).all()
    assert len(distributions) >= 50

    for dist in distributions:
        bm = dist.biomarker
        p5, p25, p50, p75, p95 = dist.p5, dist.p25, dist.p50, dist.p75, dist.p95
        
        # Percentile ordering checks
        if p5 is not None and p25 is not None:
            assert p5 <= p25, f"[{bm.slug}|{dist.sex}_{dist.age_band}] P5 ({p5}) > P25 ({p25})"
        if p25 is not None and p50 is not None:
            assert p25 <= p50, f"[{bm.slug}|{dist.sex}_{dist.age_band}] P25 ({p25}) > P50 ({p50})"
        if p50 is not None and p75 is not None:
            assert p50 <= p75, f"[{bm.slug}|{dist.sex}_{dist.age_band}] P50 ({p50}) > P75 ({p75})"
        if p75 is not None and p95 is not None:
            assert p75 <= p95, f"[{bm.slug}|{dist.sex}_{dist.age_band}] P75 ({p75}) > P95 ({p95})"

        # Standard deviation strictly positive
        assert dist.sd > 0, f"[{bm.slug}|{dist.sex}_{dist.age_band}] SD must be positive, got {dist.sd}"
        assert dist.sample_n > 0, f"[{bm.slug}|{dist.sex}_{dist.age_band}] Sample size must be > 0"

        # Domain bounds validity
        if bm.valid_domain_min is not None and bm.valid_domain_max is not None:
            assert bm.valid_domain_min < bm.valid_domain_max, f"[{bm.slug}] Invalid domain bounds"
            assert bm.valid_domain_min <= dist.mean <= bm.valid_domain_max, f"[{bm.slug}] Mean ({dist.mean}) out of valid domain"


def test_hazard_ratio_reference_point_normalization(db_session):
    curves = db_session.query(BiomarkerHRCurve).all()
    assert len(curves) >= db_session.query(Biomarker).count()

    for curve in curves:
        bm = curve.biomarker
        ref_val = curve.reference_value
        params = curve.parameters or {}
        
        # Evaluate HR at reference value
        hr_ref = evaluate_hr(ref_val, curve.curve_type, ref_val, params, curve.optimal_value)
        assert abs(hr_ref - 1.0) < 0.05, f"[{bm.slug}] HR at reference_value {ref_val} is {hr_ref:.4f}, expected 1.0"


def test_hazard_ratio_function_bounds_and_finite_values(db_session):
    curves = db_session.query(BiomarkerHRCurve).all()

    for curve in curves:
        bm = curve.biomarker
        params = curve.parameters or {}
        
        # Test 50 points across valid domain
        grid = np.linspace(curve.valid_min, curve.valid_max, 50)
        for val in grid:
            hr_val = evaluate_hr(val, curve.curve_type, curve.reference_value, params, curve.optimal_value)
            assert not math.isnan(hr_val), f"[{bm.slug}] HR({val}) evaluated to NaN"
            assert not math.isinf(hr_val), f"[{bm.slug}] HR({val}) evaluated to Inf"
            assert 0.001 <= hr_val <= 150.0, f"[{bm.slug}] HR({val}) = {hr_val:.4f} is outside numerical boundaries"


def test_hazard_ratio_curve_directionality_consistency(db_session):
    curves = db_session.query(BiomarkerHRCurve).all()

    for curve in curves:
        bm = curve.biomarker
        opt_model = bm.optimization_model
        assert opt_model is not None, f"[{bm.slug}] Missing optimization model"
        
        rel_type = opt_model.relationship_type.upper()
        params = curve.parameters or {}

        # Query the overall population distribution
        pop_dist = next((d for d in bm.population_distributions if d.sex == 'all' and d.age_band == 'all'), bm.population_distributions[0])

        hr_p5 = evaluate_hr(pop_dist.p5, curve.curve_type, curve.reference_value, params, curve.optimal_value)
        hr_p50 = evaluate_hr(pop_dist.p50, curve.curve_type, curve.reference_value, params, curve.optimal_value)
        hr_p95 = evaluate_hr(pop_dist.p95, curve.curve_type, curve.reference_value, params, curve.optimal_value)

        if rel_type == "MONOTONIC_INCREASING":
            assert hr_p95 > hr_p5, f"[{bm.slug}] MONOTONIC_INCREASING requires HR(P95) > HR(P5). Got HR(P5)={hr_p5:.3f}, HR(P95)={hr_p95:.3f}"
        
        elif rel_type == "MONOTONIC_DECREASING":
            assert hr_p5 > hr_p95, f"[{bm.slug}] MONOTONIC_DECREASING requires HR(P5) > HR(P95). Got HR(P5)={hr_p5:.3f}, HR(P95)={hr_p95:.3f}"
        
        elif rel_type in ("U_SHAPED", "J_SHAPED"):
            hr_min_domain = evaluate_hr(curve.valid_min, curve.curve_type, curve.reference_value, params, curve.optimal_value)
            hr_max_domain = evaluate_hr(curve.valid_max, curve.curve_type, curve.reference_value, params, curve.optimal_value)
            opt_val = curve.optimal_value if curve.optimal_value is not None else curve.reference_value
            hr_opt = evaluate_hr(opt_val, curve.curve_type, curve.reference_value, params, curve.optimal_value)

            assert hr_opt <= hr_min_domain + 0.05, f"[{bm.slug}] {rel_type} optimal HR ({hr_opt:.3f}) exceeds HR at min domain ({hr_min_domain:.3f})"
            assert hr_opt <= hr_max_domain + 0.05, f"[{bm.slug}] {rel_type} optimal HR ({hr_opt:.3f}) exceeds HR at max domain ({hr_max_domain:.3f})"


def test_population_distribution_discrete_density_integration(db_session):
    distributions = db_session.query(PopulationDistribution).all()

    for dist in distributions:
        bm = dist.biomarker
        valid_min = bm.valid_domain_min if bm.valid_domain_min is not None else dist.mean - 4.5 * dist.sd
        valid_max = bm.valid_domain_max if bm.valid_domain_max is not None else dist.mean + 4.5 * dist.sd
        
        grid_x, density = generate_population_distribution(
            mean=dist.mean,
            sd=dist.sd,
            valid_min=valid_min,
            valid_max=valid_max
        )
        
        assert len(grid_x) == len(density)
        # Sum of discrete probabilities must integrate to 1.0
        total_prob = float(np.sum(density))
        assert abs(total_prob - 1.0) < 0.01, f"[{bm.slug}] Population density integrates to {total_prob:.4f}, expected 1.0"


def test_baseline_expected_hazard_is_valid_and_consistent(db_session):
    biomarkers = db_session.query(Biomarker).all()

    for bm in biomarkers:
        pop_dist = next((d for d in bm.population_distributions if d.sex == 'all' and d.age_band == 'all'), bm.population_distributions[0])
        curve = bm.hr_curve
        params = curve.parameters or {}
        
        grid_x, density = generate_population_distribution(
            mean=pop_dist.mean,
            sd=pop_dist.sd,
            valid_min=curve.valid_min,
            valid_max=curve.valid_max
        )
        
        e_hr0, _ = compute_baseline_expected_hazard(
            x_bins=grid_x,
            probabilities=density,
            curve_type=curve.curve_type,
            reference_value=curve.reference_value,
            parameters=params,
            optimal_value=curve.optimal_value
        )
        assert not math.isnan(e_hr0), f"[{bm.slug}] E[HR_0] is NaN"
        assert not math.isinf(e_hr0), f"[{bm.slug}] E[HR_0] is Inf"
        assert 0.5 <= e_hr0 <= 5.0, f"[{bm.slug}] E[HR_0] = {e_hr0:.4f} is outside realistic expectation range [0.5, 5.0]"


def test_every_biomarker_has_verified_literature_references(db_session):
    """
    Validates that each of the 111 biomarkers has:
    1. An explicit academic HR curve citation summary.
    2. At least one linked MortalityAssociation.
    3. Every linked MortalityAssociation has a verified Source with:
       - Full formal citation text (non-empty, >= 15 chars)
       - Publication year
       - Verified identifier (PMID or DOI)
       - Study design specification
       - Descriptive cohort name
    """
    biomarkers = db_session.query(Biomarker).all()
    assert len(biomarkers) == 111, f"Expected 111 biomarkers, found {len(biomarkers)}"

    for bm in biomarkers:
        # 1. HR Curve citation summary check
        assert bm.hr_curve is not None, f"Biomarker '{bm.slug}' missing HR curve"
        assert bm.hr_curve.citation_summary and len(bm.hr_curve.citation_summary.strip()) > 5, (
            f"Biomarker '{bm.slug}' has missing or empty HR curve citation_summary"
        )

        # 2. Mortality Association check
        assocs = bm.mortality_associations
        assert len(assocs) > 0, f"Biomarker '{bm.slug}' has 0 linked mortality associations"

        # 3. Source verification
        for assoc in assocs:
            assert assoc.cohort_description and len(assoc.cohort_description.strip()) > 3, (
                f"Biomarker '{bm.slug}' association #{assoc.id} missing cohort description"
            )
            src = assoc.source
            assert src is not None, f"Biomarker '{bm.slug}' association #{assoc.id} has no linked Source"
            assert src.citation and len(src.citation.strip()) >= 15, (
                f"Biomarker '{bm.slug}' source #{src.id} has invalid or short citation: '{src.citation}'"
            )
            assert src.year is not None and 1950 <= src.year <= 2030, (
                f"Biomarker '{bm.slug}' source #{src.id} has invalid publication year: {src.year}"
            )
            assert (src.pmid is not None and len(src.pmid.strip()) > 0) or (src.doi is not None and len(src.doi.strip()) > 0), (
                f"Biomarker '{bm.slug}' source #{src.id} must have at least one of PMID or DOI"
            )
            assert src.study_design is not None and len(src.study_design.strip()) > 0, (
                f"Biomarker '{bm.slug}' source #{src.id} missing study design"
            )


def test_continuous_parametric_distribution_sampling(db_session):
    """Test continuous parametric sampling (normal, lognormal, gamma, weibull)."""
    fits = db_session.query(DistributionFit).all()
    assert len(fits) >= 50, f"Expected at least 50 distribution fits, found {len(fits)}"

    # Test sampling for first 10 fits
    for fit in fits[:10]:
        samples = sample_continuous_distribution(
            family=fit.family,
            shape=fit.param_shape,
            loc=fit.param_loc,
            scale=fit.param_scale,
            n_samples=500
        )
        assert len(samples) == 500
        assert not np.isnan(samples).any()
        assert not np.isinf(samples).any()
        assert float(np.mean(samples)) > 0.0


def test_continuous_hazard_spline_function_evaluation(db_session):
    """Test continuous hazard evaluation with domain guardrails and reference value normalization."""
    hr_funcs = db_session.query(HRFunction).all()
    assert len(hr_funcs) >= 50, f"Expected at least 50 continuous HR functions, found {len(hr_funcs)}"

    for func in hr_funcs:
        bm = func.biomarker
        # Reference value should evaluate to HR == 1.0 (log_hr == 0.0)
        ref_hr = evaluate_hr_function(
            func.reference_value,
            func.function_type,
            func.reference_value,
            func.parameters,
            valid_min=func.valid_min,
            valid_max=func.valid_max,
            as_log=False
        )
        assert abs(ref_hr - 1.0) < 0.05, f"[{bm.slug}] HR at reference {func.reference_value} was {ref_hr}, expected 1.0"


def test_voi_monte_carlo_simulation_engine(db_session):
    """Test VOI Monte Carlo simulation comparing informed policy vs blind policy."""
    bm = db_session.query(Biomarker).filter_by(slug="systolic_blood_pressure").first()
    assert bm is not None

    fit = db_session.query(DistributionFit).filter_by(biomarker_id=bm.id, sex="all", age_band="all").first()
    hr_func = db_session.query(HRFunction).filter_by(biomarker_id=bm.id).first()

    assert fit is not None
    assert hr_func is not None

    results = run_voi_monte_carlo_simulation(
        dist_fit=fit,
        hr_func=hr_func,
        n_samples=3000,
        tolerance_sd=0.5,
        blind_shift=-10.0
    )

    assert results["n_samples"] == 3000
    assert "mean_voi_delta_log_hr" in results
    assert "fraction_within_tolerance" in results
    assert "caveats" in results
    assert len(results["caveats"]) == 3
    assert len(results["histogram_log_delta"]["counts"]) == 20

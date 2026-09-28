"""
Regression tests for the Monte Carlo Biomarker Optimization Model.

Tests:
1. Synthetic validation (zero change, positive effect, age effect, reference HR)
2. API endpoint integration test
3. Edge cases (clipping, U-shaped, higher_better)
"""

import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.monte_carlo_engine import (
    run_monte_carlo_optimization,
    synthetic_validation_test,
    baseline_hazard,
    baseline_survival,
    expected_remaining_life,
    evaluate_hr_with_params,
    sample_hr_params,
    optimize_by_one_sd,
)


# =======================================================================
# Test 1: Synthetic Validation
# =======================================================================

class TestSyntheticValidation:
    """Tests the synthetic validation suite."""

    def test_zero_change_yields_zero_ylg(self):
        """When HR_current = HR_optimized, YLG should be ~0."""
        results = synthetic_validation_test()
        assert results["test_zero_change"]["pass"], f"Zero change test failed: {results['test_zero_change']}"
        assert abs(results["test_zero_change"]["ylg_mean"]) < 0.01

    def test_positive_effect_yields_positive_ylg(self):
        """When HR_current > HR_optimized, YLG should be positive."""
        results = synthetic_validation_test()
        assert results["test_positive_effect"]["pass"], f"Positive effect test failed: {results['test_positive_effect']}"
        assert results["test_positive_effect"]["ylg_mean"] > 0
        assert results["test_positive_effect"]["prob_positive"] > 0.9

    def test_age_reduces_remaining_life(self):
        """Increasing age should reduce remaining life expectancy."""
        results = synthetic_validation_test()
        assert results["test_age_effect"]["pass"], f"Age effect test failed: {results['test_age_effect']}"
        assert results["test_age_effect"]["le_40_median"] > results["test_age_effect"]["le_70_median"]

    def test_reference_value_yields_hr_1(self):
        """At the reference value, HR should be ~1."""
        results = synthetic_validation_test()
        assert results["test_reference_hr"]["pass"], f"Reference HR test failed: {results['test_reference_hr']}"
        assert abs(results["test_reference_hr"]["hr_current_median"] - 1.0) < 0.1

    def test_all_synthetic_tests_pass(self):
        """All synthetic validation tests should pass."""
        results = synthetic_validation_test()
        assert results["all_pass"], f"Not all synthetic tests passed: {results}"


# =======================================================================
# Test 2: Baseline Mortality Model
# =======================================================================

class TestBaselineMortality:
    """Tests the Gompertz baseline mortality model."""

    def test_hazard_increases_with_age(self):
        """Mortality hazard should increase with age."""
        h_40 = baseline_hazard(40, "M")
        h_60 = baseline_hazard(60, "M")
        h_80 = baseline_hazard(80, "M")
        assert h_40 < h_60 < h_80

    def test_female_lower_hazard_than_male(self):
        """Females should have lower mortality hazard than males at same age."""
        h_m = baseline_hazard(60, "M")
        h_f = baseline_hazard(60, "F")
        assert h_f < h_m

    def test_survival_decreases_with_time(self):
        """Survival probability should decrease with time."""
        s_1 = baseline_survival(60, "M", 1.0)
        s_5 = baseline_survival(60, "M", 5.0)
        s_10 = baseline_survival(60, "M", 10.0)
        assert s_1 > s_5 > s_10
        assert 0 < s_10 < 1

    def test_expected_remaining_life_decreases_with_age(self):
        """Expected remaining life should decrease with age."""
        le_40 = expected_remaining_life(40, "M")
        le_60 = expected_remaining_life(60, "M")
        le_80 = expected_remaining_life(80, "M")
        assert le_40 > le_60 > le_80

    def test_expected_remaining_life_reasonable(self):
        """Expected remaining life should be in a reasonable range."""
        le_60 = expected_remaining_life(60, "M")
        assert 10 < le_60 < 30, f"Expected remaining life at 60 should be 10-30 years, got {le_60}"


# =======================================================================
# Test 3: HR Function Evaluation
# =======================================================================

class TestHREvaluation:
    """Tests HR function evaluation."""

    def test_linear_hr_at_reference(self):
        """HR at reference value should be 1.0."""
        hr = evaluate_hr_with_params(
            x=1.0,
            fit_type="log_linear_per_sd",
            reference_value=1.0,
            parameters={"beta": 0.5},
        )
        assert abs(hr - 1.0) < 0.01

    def test_linear_hr_increases_with_x(self):
        """For lower_better biomarker, HR should increase with x."""
        hr_low = evaluate_hr_with_params(
            x=1.0,
            fit_type="log_linear_per_sd",
            reference_value=1.0,
            parameters={"beta": 0.5},
        )
        hr_high = evaluate_hr_with_params(
            x=3.0,
            fit_type="log_linear_per_sd",
            reference_value=1.0,
            parameters={"beta": 0.5},
        )
        assert hr_high > hr_low

    def test_log_log_hr_at_reference(self):
        """Log-log HR at reference value should be 1.0."""
        hr = evaluate_hr_with_params(
            x=1.0,
            fit_type="log_log",
            reference_value=1.0,
            parameters={"beta": 0.4},
        )
        assert abs(hr - 1.0) < 0.01

    def test_quadratic_hr_at_nadir(self):
        """Quadratic HR at nadir should be minimal."""
        hr_nadir = evaluate_hr_with_params(
            x=5.0,
            fit_type="quadratic_u_shaped",
            reference_value=3.0,
            parameters={"a": 0.01},
            nadir_value=5.0,
        )
        hr_off_nadir = evaluate_hr_with_params(
            x=8.0,
            fit_type="quadratic_u_shaped",
            reference_value=3.0,
            parameters={"a": 0.01},
            nadir_value=5.0,
        )
        assert hr_nadir < hr_off_nadir

    def test_domain_clipping(self):
        """HR should be clipped to valid domain."""
        hr_clipped = evaluate_hr_with_params(
            x=100.0,
            fit_type="log_linear_per_sd",
            reference_value=1.0,
            parameters={"beta": 0.5},
            domain_min=0.0,
            domain_max=10.0,
        )
        hr_at_max = evaluate_hr_with_params(
            x=10.0,
            fit_type="log_linear_per_sd",
            reference_value=1.0,
            parameters={"beta": 0.5},
            domain_min=0.0,
            domain_max=10.0,
        )
        assert abs(hr_clipped - hr_at_max) < 0.01


# =======================================================================
# Test 4: 1-SD Optimization
# =======================================================================

class TestOneSDOptimization:
    """Tests the 1-SD optimization logic."""

    def test_lower_better_decreases_value(self):
        """For lower_better, optimized value should be lower."""
        optimized, clipped = optimize_by_one_sd(
            observed_value=5.0,
            population_sd=1.0,
            directionality="lower_better",
        )
        assert optimized == 4.0
        assert not clipped

    def test_higher_better_increases_value(self):
        """For higher_better, optimized value should be higher."""
        optimized, clipped = optimize_by_one_sd(
            observed_value=5.0,
            population_sd=1.0,
            directionality="higher_better",
        )
        assert optimized == 6.0
        assert not clipped

    def test_clipping_to_valid_min(self):
        """Optimized value should be clipped to valid_min."""
        optimized, clipped = optimize_by_one_sd(
            observed_value=0.5,
            population_sd=1.0,
            directionality="lower_better",
            valid_min=0.0,
        )
        assert optimized == 0.0
        assert clipped

    def test_clipping_to_valid_max(self):
        """Optimized value should be clipped to valid_max."""
        optimized, clipped = optimize_by_one_sd(
            observed_value=9.5,
            population_sd=1.0,
            directionality="higher_better",
            valid_max=10.0,
        )
        assert optimized == 10.0
        assert clipped


# =======================================================================
# Test 5: Monte Carlo Simulation
# =======================================================================

class TestMonteCarloSimulation:
    """Tests the full Monte Carlo simulation."""

    def test_simulation_returns_all_fields(self):
        """Simulation should return all required fields."""
        result = run_monte_carlo_optimization(
            biomarker_slug="test",
            observed_value=5.0,
            age=60,
            sex="M",
            hr_function={
                "fit_type": "log_linear_per_sd",
                "reference_value": 1.0,
                "parameters": {"beta": 0.5},
                "shape": "monotonic_increasing",
                "nadir_value": None,
                "domain_min": 0.0,
                "domain_max": 10.0,
            },
            population_distribution={"mean": 5.0, "sd": 1.0},
            directionality="lower_better",
            valid_min=0.0,
            valid_max=10.0,
            n_simulations=100,
            seed=42,
        )

        # Check all required fields
        assert "current_hr" in result
        assert "optimized_hr" in result
        assert "remaining_life" in result
        assert "years_life_gained" in result
        assert "probability_positive_benefit" in result
        assert "probability_of_harm" in result
        assert "histograms" in result
        assert "metadata" in result
        assert "disclaimer" in result

        # Check HR stats
        assert "mean" in result["current_hr"]
        assert "median" in result["current_hr"]
        assert "uncertainty_95" in result["current_hr"]

        # Check YLG stats
        assert "mean" in result["years_life_gained"]
        assert "median" in result["years_life_gained"]
        assert "uncertainty_95" in result["years_life_gained"]

        # Check histograms
        assert "current_hr" in result["histograms"]
        assert "optimized_hr" in result["histograms"]
        assert "years_life_gained" in result["histograms"]

    def test_simulation_reproducible(self):
        """Same seed should produce same results."""
        kwargs = {
            "biomarker_slug": "test",
            "observed_value": 5.0,
            "age": 60,
            "sex": "M",
            "hr_function": {
                "fit_type": "log_linear_per_sd",
                "reference_value": 1.0,
                "parameters": {"beta": 0.5},
                "shape": "monotonic_increasing",
                "nadir_value": None,
                "domain_min": 0.0,
                "domain_max": 10.0,
            },
            "population_distribution": {"mean": 5.0, "sd": 1.0},
            "directionality": "lower_better",
            "valid_min": 0.0,
            "valid_max": 10.0,
            "n_simulations": 100,
            "seed": 42,
        }
        result1 = run_monte_carlo_optimization(**kwargs)
        result2 = run_monte_carlo_optimization(**kwargs)
        assert result1["years_life_gained"]["mean"] == result2["years_life_gained"]["mean"]
        assert result1["current_hr"]["median"] == result2["current_hr"]["median"]

    def test_different_seeds_different_results(self):
        """Different seeds should produce different results."""
        kwargs = {
            "biomarker_slug": "test",
            "observed_value": 5.0,
            "age": 60,
            "sex": "M",
            "hr_function": {
                "fit_type": "log_linear_per_sd",
                "reference_value": 1.0,
                "parameters": {"beta": 0.5},
                "shape": "monotonic_increasing",
                "nadir_value": None,
                "domain_min": 0.0,
                "domain_max": 10.0,
            },
            "population_distribution": {"mean": 5.0, "sd": 1.0},
            "directionality": "lower_better",
            "valid_min": 0.0,
            "valid_max": 10.0,
            "n_simulations": 100,
        }
        result1 = run_monte_carlo_optimization(seed=42, **kwargs)
        result2 = run_monte_carlo_optimization(seed=123, **kwargs)
        # With 100 simulations, results should differ slightly
        assert result1["years_life_gained"]["mean"] != result2["years_life_gained"]["mean"]

    def test_probability_sum_consistency(self):
        """Probabilities should be consistent."""
        result = run_monte_carlo_optimization(
            biomarker_slug="test",
            observed_value=5.0,
            age=60,
            sex="M",
            hr_function={
                "fit_type": "log_linear_per_sd",
                "reference_value": 1.0,
                "parameters": {"beta": 0.5},
                "shape": "monotonic_increasing",
                "nadir_value": None,
                "domain_min": 0.0,
                "domain_max": 10.0,
            },
            population_distribution={"mean": 5.0, "sd": 1.0},
            directionality="lower_better",
            valid_min=0.0,
            valid_max=10.0,
            n_simulations=1000,
            seed=42,
        )
        # prob_positive + prob_harm should be <= 1 (some may be exactly 0)
        assert result["probability_positive_benefit"] + result["probability_of_harm"] <= 1.0 + 1e-6
        # prob_positive should be >= prob_gt_1
        assert result["probability_positive_benefit"] >= result["probability_gain_over_1_year"]

    def test_u_shaped_direction(self):
        """U-shaped biomarker should move toward nadir."""
        result = run_monte_carlo_optimization(
            biomarker_slug="test_u",
            observed_value=8.0,  # Above nadir
            age=60,
            sex="M",
            hr_function={
                "fit_type": "quadratic_u_shaped",
                "reference_value": 5.0,
                "parameters": {"a": 0.01},
                "shape": "u_shaped",
                "nadir_value": 5.0,
                "domain_min": 0.0,
                "domain_max": 15.0,
            },
            population_distribution={"mean": 5.0, "sd": 1.0},
            directionality="u_shaped",
            valid_min=0.0,
            valid_max=15.0,
            n_simulations=100,
            seed=42,
        )
        # Should move toward nadir (decrease from 8.0)
        assert result["optimized_value"] < 8.0

    def test_measurement_error(self):
        """Measurement error should add uncertainty."""
        result_no_error = run_monte_carlo_optimization(
            biomarker_slug="test_me",
            observed_value=5.0,
            age=60,
            sex="M",
            hr_function={
                "fit_type": "log_linear_per_sd",
                "reference_value": 1.0,
                "parameters": {"beta": 0.5},
                "shape": "monotonic_increasing",
                "nadir_value": None,
                "domain_min": 0.0,
                "domain_max": 10.0,
            },
            population_distribution={"mean": 5.0, "sd": 1.0},
            directionality="lower_better",
            valid_min=0.0,
            valid_max=10.0,
            n_simulations=1000,
            seed=42,
            measurement_error_enabled=False,
        )
        result_with_error = run_monte_carlo_optimization(
            biomarker_slug="test_me",
            observed_value=5.0,
            age=60,
            sex="M",
            hr_function={
                "fit_type": "log_linear_per_sd",
                "reference_value": 1.0,
                "parameters": {"beta": 0.5},
                "shape": "monotonic_increasing",
                "nadir_value": None,
                "domain_min": 0.0,
                "domain_max": 10.0,
            },
            population_distribution={"mean": 5.0, "sd": 1.0},
            directionality="lower_better",
            valid_min=0.0,
            valid_max=10.0,
            n_simulations=1000,
            seed=42,
            measurement_error_enabled=True,
            test_measurement_error=0.5,
        )
        # With measurement error, HR uncertainty should be larger
        assert result_with_error["current_hr"]["sd"] >= result_no_error["current_hr"]["sd"]


# =======================================================================
# Test 6: API Endpoint Integration
# =======================================================================

class TestAPIEndpoint:
    """Tests the API endpoint integration."""

    def test_api_endpoint_exists(self):
        """The API endpoint should be registered."""
        from backend.main import app
        routes = [r.path for r in app.routes]
        assert "/api/nhanes/optimization" in routes

    def test_api_endpoint_with_real_data(self):
        """Test the API endpoint with real biomarker data."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        # Use a real biomarker from the database
        response = client.post("/api/nhanes/optimization", json={
            "biomarker": "high_sensitivity_crp",
            "observed_value": 3.0,
            "age": 60,
            "sex": "M",
            "n_simulations": 100,
        })

        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()

        # Check response structure
        assert "current_hr" in data
        assert "optimized_hr" in data
        assert "years_life_gained" in data
        assert "probability_positive_benefit" in data
        assert "biomarker_name" in data
        assert data["biomarker_name"] == "High-Sensitivity C-Reactive Protein" or "CRP" in data["biomarker_name"]

    def test_api_endpoint_not_found(self):
        """Test 404 for non-existent biomarker."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post("/api/nhanes/optimization", json={
            "biomarker": "nonexistent_biomarker_xyz",
            "observed_value": 3.0,
            "age": 60,
            "sex": "M",
        })

        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
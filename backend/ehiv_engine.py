"""
Expected Hazard Information Value (EHIV) Calculation Engine.

Implements the EHIV/REHIV calculations from TEST_COST_BUILD_SPEC.md §3.

EHIV = E[|HR_i - E[HR]|]
  - Mean absolute deviation of individual hazard ratios from the expected HR
  - Units: hazard ratio units (dimensionless)
  - Interpretation: "On average, knowing this biomarker changes an individual's
    estimated mortality hazard by this amount relative to the population mean."

REHIV = EHIV / E[HR]
  - Relative EHIV, for cross-biomarker comparison
  - Units: fraction (dimensionless)
  - Interpretation: "The test reveals X% heterogeneity in mortality risk."

CRITICAL: This is INFORMATION VALUE, not economic value.
- Do NOT combine with price
- Do NOT call it "ROI" or "cost-effectiveness"
- A descriptive ratio (rehiv / price) is fine but must be labeled
  "hazard-information units per dollar"
"""

import numpy as np
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass


@dataclass
class EHIVResult:
    """Result of an EHIV calculation."""
    expected_hr: float
    hr_sd: float
    ehiv: float
    rehiv: float
    population_n: int
    hr_min: float
    hr_max: float
    hr_median: float
    hr_p10: float
    hr_p90: float


def compute_ehiv_from_hr_distribution(
    hr_values: np.ndarray,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from a distribution of individual HR values.
    
    Parameters
    ----------
    hr_values : np.ndarray
        Array of individual hazard ratios (one per simulated individual or
        observed individual in the population).
    population_n : int, optional
        Total population size (defaults to len(hr_values)).
    
    Returns
    -------
    EHIVResult
        Contains expected_hr, hr_sd, ehiv, rehiv, and distribution stats.
    """
    hr_values = np.asarray(hr_values, dtype=float)
    hr_values = hr_values[np.isfinite(hr_values)]
    
    if len(hr_values) == 0:
        raise ValueError("No valid HR values provided")
    
    expected_hr = float(np.mean(hr_values))
    hr_sd = float(np.std(hr_values, ddof=1)) if len(hr_values) > 1 else 0.0
    
    # EHIV: mean absolute deviation from expected HR
    ehiv = float(np.mean(np.abs(hr_values - expected_hr)))
    
    # REHIV: relative EHIV
    rehiv = ehiv / expected_hr if expected_hr > 0 else 0.0
    
    return EHIVResult(
        expected_hr=expected_hr,
        hr_sd=hr_sd,
        ehiv=ehiv,
        rehiv=rehiv,
        population_n=population_n or len(hr_values),
        hr_min=float(np.min(hr_values)),
        hr_max=float(np.max(hr_values)),
        hr_median=float(np.median(hr_values)),
        hr_p10=float(np.percentile(hr_values, 10)),
        hr_p90=float(np.percentile(hr_values, 90)),
    )


def compute_ehiv_from_normal(
    mean_hr: float,
    sd_hr: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from a normal distribution of HR values.
    
    This is useful when you have a parametric model of the HR distribution
    (e.g., from a Cox model with known coefficients and variance).
    
    Parameters
    ----------
    mean_hr : float
        Mean hazard ratio.
    sd_hr : float
        Standard deviation of hazard ratios.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    rng = np.random.default_rng(seed)
    hr_values = rng.normal(mean_hr, sd_hr, size=n_simulations)
    # HR must be positive
    hr_values = np.maximum(hr_values, 0.01)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_lognormal(
    log_mean: float,
    log_sd: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from a log-normal distribution of HR values.
    
    This is often more appropriate for HR distributions since HR > 0
    and is often right-skewed.
    
    Parameters
    ----------
    log_mean : float
        Mean of log(HR).
    log_sd : float
        Standard deviation of log(HR).
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    rng = np.random.default_rng(seed)
    log_hr_values = rng.normal(log_mean, log_sd, size=n_simulations)
    hr_values = np.exp(log_hr_values)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_biomarker_distribution(
    biomarker_values: np.ndarray,
    hr_function: callable,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV by applying an HR function to a distribution of
    biomarker values.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values (one per individual).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    hr_values = np.array([hr_function(x) for x in biomarker_values])
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_linear_log_hr(
    biomarker_values: np.ndarray,
    beta: float,
    x_ref: float,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV using a linear-log HR model:
    HR(x) = exp(beta * (x - x_ref))
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values.
    beta : float
        Log-HR coefficient per unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    log_hr = beta * (np.asarray(biomarker_values, dtype=float) - x_ref)
    hr_values = np.exp(log_hr)
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_quadratic_hr(
    biomarker_values: np.ndarray,
    a: float,
    x_opt: float,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV using a quadratic HR model:
    HR(x) = exp(a * (x - x_opt)^2)
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values.
    a : float
        Quadratic coefficient (positive for U-shaped).
    x_opt : float
        Optimal value (nadir of risk).
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    log_hr = a * (np.asarray(biomarker_values, dtype=float) - x_opt) ** 2
    hr_values = np.exp(log_hr)
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_log_log_hr(
    biomarker_values: np.ndarray,
    beta: float,
    x_ref: float,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV using a log-log HR model:
    HR(x) = exp(beta * (ln(x) - ln(x_ref)))
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values (must be > 0).
    beta : float
        Log-HR coefficient per log-unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    log_hr = beta * (np.log(biomarker_values) - np.log(x_ref))
    hr_values = np.exp(log_hr)
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_piecewise_linear_hr(
    biomarker_values: np.ndarray,
    knots: List[float],
    log_hr_at_knots: List[float],
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV using a piecewise linear HR model in log-HR space.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values.
    knots : List[float]
        Knot locations (sorted).
    log_hr_at_knots : List[float]
        Log-HR values at each knot.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    log_hr_values = np.interp(biomarker_values, knots, log_hr_at_knots)
    hr_values = np.exp(log_hr_values)
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_hr(
    biomarker_values: np.ndarray,
    hr_lookup: Dict[float, float],
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV using an empirical HR lookup table.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values.
    hr_lookup : Dict[float, float]
        Mapping from biomarker value -> HR.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    # Interpolate from lookup table
    sorted_keys = sorted(hr_lookup.keys())
    hr_values = np.interp(biomarker_values, sorted_keys, [hr_lookup[k] for k in sorted_keys])
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_function: callable,
    population_n: Optional[int] = None,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    strata = np.asarray(strata)
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        hr_values = np.array([hr_function(x) for x in biomarker_values[mask]])
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=int(mask.sum())
        )
    
    return results


def compute_ehiv_from_cox_model(
    biomarker_values: np.ndarray,
    cox_coefficients: Dict[str, float],
    reference_values: Dict[str, float],
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from a Cox model with multiple covariates.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of biomarker values.
    cox_coefficients : Dict[str, float]
        Cox model coefficients (log-HR per unit).
    reference_values : Dict[str, float]
        Reference values for each covariate.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    
    # Compute log-HR from biomarker only (other covariates held at reference)
    biomarker_coef = cox_coefficients.get("biomarker", 0.0)
    biomarker_ref = reference_values.get("biomarker", 0.0)
    
    log_hr = biomarker_coef * (biomarker_values - biomarker_ref)
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_monte_carlo(
    biomarker_mean: float,
    biomarker_sd: float,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV via Monte Carlo simulation.
    
    Simulates biomarker values from a normal distribution and applies
    the HR function to get individual HR values.
    
    Parameters
    ----------
    biomarker_mean : float
        Mean biomarker value.
    biomarker_sd : float
        Standard deviation of biomarker values.
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    rng = np.random.default_rng(seed)
    biomarker_values = rng.normal(biomarker_mean, biomarker_sd, size=n_simulations)
    
    hr_values = np.array([hr_function(x) for x in biomarker_values])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_monte_carlo_lognormal(
    biomarker_log_mean: float,
    biomarker_log_sd: float,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV via Monte Carlo simulation with log-normal biomarker
    distribution (more realistic for many biomarkers).
    
    Parameters
    ----------
    biomarker_log_mean : float
        Mean of log(biomarker).
    biomarker_log_sd : float
        Standard deviation of log(biomarker).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    rng = np.random.default_rng(seed)
    log_biomarker_values = rng.normal(biomarker_log_mean, biomarker_log_sd, size=n_simulations)
    biomarker_values = np.exp(log_biomarker_values)
    
    hr_values = np.array([hr_function(x) for x in biomarker_values])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker(
    biomarker_values: np.ndarray,
    hr_function: callable,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values (e.g., from NHANES).
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    hr_values = np.array([hr_function(x) for x in biomarker_values])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_lognormal(
    biomarker_values: np.ndarray,
    hr_function: callable,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values, assuming log-normal
    distribution for the HR function.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    
    hr_values = np.array([hr_function(x) for x in biomarker_values])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_piecewise(
    biomarker_values: np.ndarray,
    knots: List[float],
    log_hr_at_knots: List[float],
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values using a piecewise
    linear HR model in log-HR space.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    knots : List[float]
        Knot locations (sorted).
    log_hr_at_knots : List[float]
        Log-HR values at each knot.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    log_hr_values = np.interp(biomarker_values, knots, log_hr_at_knots)
    hr_values = np.exp(log_hr_values)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_log_log(
    biomarker_values: np.ndarray,
    beta: float,
    x_ref: float,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values using a log-log HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    beta : float
        Log-HR coefficient per log-unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    
    log_hr = beta * (np.log(biomarker_values) - np.log(x_ref))
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_quadratic(
    biomarker_values: np.ndarray,
    a: float,
    x_opt: float,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values using a quadratic HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    a : float
        Quadratic coefficient (positive for U-shaped).
    x_opt : float
        Optimal value (nadir of risk).
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    log_hr = a * (biomarker_values - x_opt) ** 2
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_linear_log(
    biomarker_values: np.ndarray,
    beta: float,
    x_ref: float,
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values using a linear-log HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    beta : float
        Log-HR coefficient per unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    log_hr = beta * (biomarker_values - x_ref)
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_empirical_hr(
    biomarker_values: np.ndarray,
    hr_lookup: Dict[float, float],
    population_n: Optional[int] = None,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values using an empirical HR lookup.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    hr_lookup : Dict[float, float]
        Mapping from biomarker value -> HR.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    sorted_keys = sorted(hr_lookup.keys())
    hr_values = np.interp(biomarker_values, sorted_keys, [hr_lookup[k] for k in sorted_keys])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=population_n)


def compute_ehiv_from_empirical_biomarker_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_function: callable,
    population_n: Optional[int] = None,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values, stratified by a
    categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    population_n : int, optional
        Total population size.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    # Filter to valid biomarker values
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        hr_values = np.array([hr_function(x) for x in biomarker_values[mask]])
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=int(mask.sum())
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo(
    biomarker_values: np.ndarray,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    rng = np.random.default_rng(seed)
    # Bootstrap resample
    resampled = rng.choice(biomarker_values, size=n_simulations, replace=True)
    
    hr_values = np.array([hr_function(x) for x in resampled])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_lognormal(
    biomarker_values: np.ndarray,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, assuming log-normal distribution.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    
    # Fit log-normal parameters
    log_values = np.log(biomarker_values)
    log_mean = float(np.mean(log_values))
    log_sd = float(np.std(log_values, ddof=1))
    
    rng = np.random.default_rng(seed)
    log_resampled = rng.normal(log_mean, log_sd, size=n_simulations)
    resampled = np.exp(log_resampled)
    
    hr_values = np.array([hr_function(x) for x in resampled])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_piecewise(
    biomarker_values: np.ndarray,
    knots: List[float],
    log_hr_at_knots: List[float],
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a piecewise linear HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    knots : List[float]
        Knot locations (sorted).
    log_hr_at_knots : List[float]
        Log-HR values at each knot.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    rng = np.random.default_rng(seed)
    resampled = rng.choice(biomarker_values, size=n_simulations, replace=True)
    
    log_hr_values = np.interp(resampled, knots, log_hr_at_knots)
    hr_values = np.exp(log_hr_values)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_log_log(
    biomarker_values: np.ndarray,
    beta: float,
    x_ref: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a log-log HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    beta : float
        Log-HR coefficient per log-unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    
    rng = np.random.default_rng(seed)
    resampled = rng.choice(biomarker_values, size=n_simulations, replace=True)
    
    log_hr = beta * (np.log(resampled) - np.log(x_ref))
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_quadratic(
    biomarker_values: np.ndarray,
    a: float,
    x_opt: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a quadratic HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    a : float
        Quadratic coefficient (positive for U-shaped).
    x_opt : float
        Optimal value (nadir of risk).
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    rng = np.random.default_rng(seed)
    resampled = rng.choice(biomarker_values, size=n_simulations, replace=True)
    
    log_hr = a * (resampled - x_opt) ** 2
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_linear_log(
    biomarker_values: np.ndarray,
    beta: float,
    x_ref: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a linear-log HR model.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    beta : float
        Log-HR coefficient per unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    rng = np.random.default_rng(seed)
    resampled = rng.choice(biomarker_values, size=n_simulations, replace=True)
    
    log_hr = beta * (resampled - x_ref)
    hr_values = np.exp(log_hr)
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_empirical_hr(
    biomarker_values: np.ndarray,
    hr_lookup: Dict[float, float],
    n_simulations: int = 100000,
    seed: int = 42,
) -> EHIVResult:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using an empirical HR lookup.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    hr_lookup : Dict[float, float]
        Mapping from biomarker value -> HR.
    n_simulations : int
        Number of Monte Carlo simulations.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    EHIVResult
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    
    rng = np.random.default_rng(seed)
    resampled = rng.choice(biomarker_values, size=n_simulations, replace=True)
    
    sorted_keys = sorted(hr_lookup.keys())
    hr_values = np.interp(resampled, sorted_keys, [hr_lookup[k] for k in sorted_keys])
    
    return compute_ehiv_from_hr_distribution(hr_values, population_n=n_simulations)


def compute_ehiv_from_empirical_biomarker_monte_carlo_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        hr_values = np.array([hr_function(x) for x in resampled])
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_lognormal_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, assuming log-normal distribution, stratified by a
    categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        # Fit log-normal parameters for this stratum
        log_values = np.log(biomarker_values[mask])
        log_mean = float(np.mean(log_values))
        log_sd = float(np.std(log_values, ddof=1))
        
        rng = np.random.default_rng(seed)
        log_resampled = rng.normal(log_mean, log_sd, size=n_simulations)
        resampled = np.exp(log_resampled)
        
        hr_values = np.array([hr_function(x) for x in resampled])
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_piecewise_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    knots: List[float],
    log_hr_at_knots: List[float],
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a piecewise linear HR model, stratified by a
    categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    knots : List[float]
        Knot locations (sorted).
    log_hr_at_knots : List[float]
        Log-HR values at each knot.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr_values = np.interp(resampled, knots, log_hr_at_knots)
        hr_values = np.exp(log_hr_values)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_log_log_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    beta: float,
    x_ref: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a log-log HR model, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    beta : float
        Log-HR coefficient per log-unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr = beta * (np.log(resampled) - np.log(x_ref))
        hr_values = np.exp(log_hr)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_quadratic_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    a: float,
    x_opt: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a quadratic HR model, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    a : float
        Quadratic coefficient (positive for U-shaped).
    x_opt : float
        Optimal value (nadir of risk).
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr = a * (resampled - x_opt) ** 2
        hr_values = np.exp(log_hr)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_linear_log_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    beta: float,
    x_ref: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a linear-log HR model, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    beta : float
        Log-HR coefficient per unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr = beta * (resampled - x_ref)
        hr_values = np.exp(log_hr)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_empirical_hr_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_lookup: Dict[float, float],
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using an empirical HR lookup, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_lookup : Dict[float, float]
        Mapping from biomarker value -> HR.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        sorted_keys = sorted(hr_lookup.keys())
        hr_values = np.interp(resampled, sorted_keys, [hr_lookup[k] for k in sorted_keys])
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_lognormal_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_function: callable,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, assuming log-normal distribution, stratified by a
    categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_function : callable
        Function that maps biomarker value -> hazard ratio.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        # Fit log-normal parameters for this stratum
        log_values = np.log(biomarker_values[mask])
        log_mean = float(np.mean(log_values))
        log_sd = float(np.std(log_values, ddof=1))
        
        rng = np.random.default_rng(seed)
        log_resampled = rng.normal(log_mean, log_sd, size=n_simulations)
        resampled = np.exp(log_resampled)
        
        hr_values = np.array([hr_function(x) for x in resampled])
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_piecewise_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    knots: List[float],
    log_hr_at_knots: List[float],
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a piecewise linear HR model, stratified by a
    categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    knots : List[float]
        Knot locations (sorted).
    log_hr_at_knots : List[float]
        Log-HR values at each knot.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr_values = np.interp(resampled, knots, log_hr_at_knots)
        hr_values = np.exp(log_hr_values)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_log_log_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    beta: float,
    x_ref: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a log-log HR model, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    beta : float
        Log-HR coefficient per log-unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    biomarker_values = np.maximum(biomarker_values, 0.01)  # avoid log(0)
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr = beta * (np.log(resampled) - np.log(x_ref))
        hr_values = np.exp(log_hr)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_quadratic_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    a: float,
    x_opt: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a quadratic HR model, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    a : float
        Quadratic coefficient (positive for U-shaped).
    x_opt : float
        Optimal value (nadir of risk).
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr = a * (resampled - x_opt) ** 2
        hr_values = np.exp(log_hr)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_linear_log_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    beta: float,
    x_ref: float,
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using a linear-log HR model, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    beta : float
        Log-HR coefficient per unit change in biomarker.
    x_ref : float
        Reference value where HR = 1.0.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        log_hr = beta * (resampled - x_ref)
        hr_values = np.exp(log_hr)
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results


def compute_ehiv_from_empirical_biomarker_monte_carlo_empirical_hr_stratified(
    biomarker_values: np.ndarray,
    strata: np.ndarray,
    hr_lookup: Dict[float, float],
    n_simulations: int = 100000,
    seed: int = 42,
) -> Dict[str, EHIVResult]:
    """
    Compute EHIV/REHIV from empirical biomarker values via Monte Carlo
    resampling, using an empirical HR lookup, stratified by a categorical variable.
    
    Parameters
    ----------
    biomarker_values : np.ndarray
        Array of observed biomarker values.
    strata : np.ndarray
        Array of stratum labels (same length as biomarker_values).
    hr_lookup : Dict[float, float]
        Mapping from biomarker value -> HR.
    n_simulations : int
        Number of Monte Carlo simulations per stratum.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    Dict[str, EHIVResult]
        EHIV results keyed by stratum label.
    """
    biomarker_values = np.asarray(biomarker_values, dtype=float)
    biomarker_values = biomarker_values[np.isfinite(biomarker_values)]
    strata = np.asarray(strata)
    
    valid_mask = np.isfinite(biomarker_values)
    biomarker_values = biomarker_values[valid_mask]
    strata = strata[valid_mask]
    
    results = {}
    for stratum in np.unique(strata):
        mask = strata == stratum
        if mask.sum() < 10:
            continue
        
        rng = np.random.default_rng(seed)
        resampled = rng.choice(biomarker_values[mask], size=n_simulations, replace=True)
        
        sorted_keys = sorted(hr_lookup.keys())
        hr_values = np.interp(resampled, sorted_keys, [hr_lookup[k] for k in sorted_keys])
        
        results[str(stratum)] = compute_ehiv_from_hr_distribution(
            hr_values, population_n=n_simulations
        )
    
    return results
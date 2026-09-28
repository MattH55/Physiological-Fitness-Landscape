"""
Monte Carlo Biomarker Optimization Model
=========================================
Estimates the distribution of expected years of life gained (YLG) if a person's
biomarker could be shifted by 1 SD toward the favorable direction.

This is a COUNTERFACTUAL biomarker optimization scenario, NOT a causal
intervention model. The 1-SD shift represents a hypothetical improvement in
the biomarker, not proof that an intervention causing that shift produces the
predicted survival benefit.

Architecture:
    biomarker value
        -> continuous HR function (with model uncertainty)
        -> hypothetical 1-SD biomarker shift
        -> age-specific baseline mortality
        -> survival curves
        -> expected remaining life
        -> distribution of years of life gained

Key components:
    1. Baseline age-specific mortality (Gompertz model, calibrated to US life tables)
    2. HR function evaluation with parameter uncertainty
    3. Monte Carlo simulation propagating model uncertainty
    4. Numerical integration of survival curves for life expectancy
"""

import math
import numpy as np
from typing import Dict, Any, List, Optional, Tuple


# =======================================================================
# Section 1: Baseline Age-Specific Mortality Model
# =======================================================================

# US all-cause mortality rates per 100,000 by age and sex
# Source: NCHS / CDC Period Life Tables 2019 (approximate)
# These are used to calibrate the Gompertz model.
_US_MORTALITY_RATES = {
    "M": {
        20: 100, 25: 150, 30: 250, 35: 400, 40: 650, 45: 1000,
        50: 1600, 55: 2600, 60: 4200, 65: 6800, 70: 11000,
        75: 18000, 80: 30000, 85: 50000, 90: 80000, 95: 120000,
    },
    "F": {
        20: 80, 25: 100, 30: 150, 35: 200, 40: 300, 45: 450,
        50: 700, 55: 1200, 60: 2000, 65: 3500, 70: 6000,
        75: 11000, 80: 20000, 85: 35000, 90: 60000, 95: 100000,
    },
}


def _gompertz_hazard(age: float, b: float, c: float) -> float:
    """Gompertz mortality hazard: h(age) = b * exp(c * age)."""
    return b * math.exp(c * age)


def _calibrate_gompertz(sex: str) -> Tuple[float, float]:
    """
    Calibrate Gompertz parameters (b, c) to US mortality rates for a given sex.
    Uses least-squares fitting on log(hazard) vs age.
    """
    rates = _US_MORTALITY_RATES.get(sex, _US_MORTALITY_RATES["M"])
    ages = np.array(list(rates.keys()), dtype=float)
    # Convert per-100,000 rates to per-year hazard (approximate)
    hazards = np.array(list(rates.values()), dtype=float) / 100000.0

    # Log-linear regression: ln(h) = ln(b) + c * age
    log_h = np.log(hazards)
    # Least squares: c = cov(age, log_h) / var(age)
    c = float(np.cov(ages, log_h, bias=True)[0, 1] / np.var(ages, ddof=0))
    log_b = float(np.mean(log_h) - c * np.mean(ages))
    b = math.exp(log_b)

    return b, c


# Pre-compute Gompertz parameters for each sex
_GOMPERTZ_PARAMS = {
    "M": _calibrate_gompertz("M"),
    "F": _calibrate_gompertz("F"),
}


def baseline_hazard(age: float, sex: str = "M") -> float:
    """
    Returns the baseline all-cause mortality hazard at a given attained age.
    Uses a Gompertz model calibrated to US life table data.
    """
    b, c = _GOMPERTZ_PARAMS.get(sex, _GOMPERTZ_PARAMS["M"])
    return _gompertz_hazard(age, b, c)


def baseline_survival(age: float, sex: str = "M", t: float = 1.0) -> float:
    """
    Returns the baseline survival probability from age to age+t.
    S(t) = exp(-integral_0^t h(age+u) du)
    For Gompertz: integral = (b/c) * (exp(c*(age+t)) - exp(c*age))
    """
    b, c = _GOMPERTZ_PARAMS.get(sex, _GOMPERTZ_PARAMS["M"])
    if c == 0:
        cum_hazard = b * t
    else:
        cum_hazard = (b / c) * (math.exp(c * (age + t)) - math.exp(c * age))
    return math.exp(-cum_hazard)


def expected_remaining_life(age: float, sex: str = "M", t_max: float = 100.0) -> float:
    """
    Calculates expected remaining life from a given age using the baseline
    Gompertz mortality model.
    LE = integral_0^Tmax S(t) dt
    For Gompertz: LE = (b/c) * (exp(c*age) - exp(c*(age+Tmax))) / exp(c*age)
                 = (1/c) * (1 - exp(-c*Tmax))
    (The age-dependent terms cancel in the Gompertz model, but we use
    numerical integration for generality and to support non-Gompertz models.)
    """
    # Numerical integration with 1-year steps
    n_steps = int(t_max)
    if n_steps < 1:
        return 0.0

    dt = 1.0
    le = 0.0
    for i in range(n_steps):
        t_mid = (i + 0.5) * dt
        s = baseline_survival(age, sex, t_mid)
        le += s * dt

    return le


# =======================================================================
# Section 2: HR Function Evaluation with Uncertainty
# =======================================================================

def evaluate_hr_with_params(
    x: float,
    fit_type: str,
    reference_value: float,
    parameters: Dict[str, Any],
    shape: str = "monotonic_increasing",
    nadir_value: Optional[float] = None,
    domain_min: Optional[float] = None,
    domain_max: Optional[float] = None,
) -> float:
    """
    Evaluates HR(x) using the given parameters.
    Returns HR in linear space (not log).
    """
    if math.isnan(x) or math.isinf(x):
        return 1.0

    # Clip to domain
    if domain_min is not None and domain_max is not None and domain_max > domain_min:
        x = max(domain_min, min(domain_max, x))
    elif domain_min is not None:
        x = max(domain_min, x)
    elif domain_max is not None:
        x = min(domain_max, x)

    ref = float(reference_value)
    f_type = (fit_type or "log_linear_per_sd").lower()

    if f_type in ["quadratic", "quadratic_u_shaped", "u_shaped"]:
        a = float(parameters.get("a", 0.005))
        x_opt = float(nadir_value if nadir_value is not None else parameters.get("x_opt", ref))
        log_hr = a * ((x - x_opt) ** 2) - a * ((ref - x_opt) ** 2)

    elif f_type in ["log_log"]:
        beta = float(parameters.get("beta", 0.3))
        x_safe = max(x, 1e-4)
        ref_safe = max(ref, 1e-4)
        log_hr = beta * (math.log(x_safe) - math.log(ref_safe))

    elif f_type in ["piecewise_linear", "piecewise"]:
        x_opt = float(nadir_value if nadir_value is not None else parameters.get("x_opt", ref))
        slope_low = float(parameters.get("slope_low", 0.0))
        slope_high = float(parameters.get("slope_high", 0.0))
        if slope_low == 0.0 and slope_high == 0.0:
            # Fallback: use beta if available
            beta = float(parameters.get("beta", 0.3))
            log_hr = beta * (x - ref)
        else:
            def _pw(val):
                return slope_low * (x_opt - val) if val < x_opt else slope_high * (val - x_opt)
            log_hr = _pw(x) - _pw(ref)

    elif f_type in ["log_linear_per_sd", "log_linear_per_unit", "linear", "linear_log"]:
        beta = float(parameters.get("beta", 0.3))
        log_hr = beta * (x - ref)

    else:
        beta = float(parameters.get("beta", 0.3))
        log_hr = beta * (x - ref)

    return float(np.exp(np.clip(log_hr, -6.0, 6.0)))


def sample_hr_params(
    fit_type: str,
    reference_value: float,
    parameters: Dict[str, Any],
    shape: str = "monotonic_increasing",
    nadir_value: Optional[float] = None,
    n_samples: int = 1,
    rng: Optional[np.random.RandomState] = None,
) -> np.ndarray:
    """
    Samples HR model parameters to capture model uncertainty.

    For the first version, we use a simplified approach:
    - For linear/log-linear models: sample beta from N(beta_hat, sigma_beta^2)
      where sigma_beta is estimated from the curvature of the HR function.
    - For quadratic models: sample 'a' similarly.
    - For log_log: sample beta similarly.

    The uncertainty is calibrated so that the 95% interval of HR at the
    population median spans a reasonable range (approximately +/- 30%).
    """
    if rng is None:
        rng = np.random.RandomState(42)

    f_type = (fit_type or "log_linear_per_sd").lower()
    ref = float(reference_value)

    # Determine the key parameter and its uncertainty
    if f_type in ["quadratic", "quadratic_u_shaped", "u_shaped"]:
        a_hat = float(parameters.get("a", 0.005))
        # Uncertainty: 30% relative
        sigma_a = abs(a_hat) * 0.30
        a_samples = rng.normal(a_hat, sigma_a, size=n_samples)
        return np.column_stack([a_samples])

    elif f_type in ["log_log"]:
        beta_hat = float(parameters.get("beta", 0.3))
        sigma_beta = abs(beta_hat) * 0.30
        beta_samples = rng.normal(beta_hat, sigma_beta, size=n_samples)
        return np.column_stack([beta_samples])

    elif f_type in ["piecewise_linear", "piecewise"]:
        slope_low = float(parameters.get("slope_low", 0.0))
        slope_high = float(parameters.get("slope_high", 0.0))
        if slope_low == 0.0 and slope_high == 0.0:
            beta_hat = float(parameters.get("beta", 0.3))
            sigma_beta = abs(beta_hat) * 0.30
            beta_samples = rng.normal(beta_hat, sigma_beta, size=n_samples)
            return np.column_stack([beta_samples])
        else:
            sigma_sl = abs(slope_low) * 0.30 if slope_low != 0 else 0.01
            sigma_sh = abs(slope_high) * 0.30 if slope_high != 0 else 0.01
            sl_samples = rng.normal(slope_low, sigma_sl, size=n_samples)
            sh_samples = rng.normal(slope_high, sigma_sh, size=n_samples)
            return np.column_stack([sl_samples, sh_samples])

    else:
        # log_linear_per_sd, log_linear_per_unit, linear, linear_log
        beta_hat = float(parameters.get("beta", 0.3))
        sigma_beta = abs(beta_hat) * 0.30
        beta_samples = rng.normal(beta_hat, sigma_beta, size=n_samples)
        return np.column_stack([beta_samples])


def evaluate_hr_with_sampled_params(
    x: float,
    fit_type: str,
    reference_value: float,
    sampled_params: np.ndarray,
    shape: str = "monotonic_increasing",
    nadir_value: Optional[float] = None,
    domain_min: Optional[float] = None,
    domain_max: Optional[float] = None,
) -> float:
    """
    Evaluates HR(x) using a single sampled parameter vector.
    """
    f_type = (fit_type or "log_linear_per_sd").lower()
    ref = float(reference_value)

    if math.isnan(x) or math.isinf(x):
        return 1.0

    if domain_min is not None and domain_max is not None and domain_max > domain_min:
        x = max(domain_min, min(domain_max, x))
    elif domain_min is not None:
        x = max(domain_min, x)
    elif domain_max is not None:
        x = min(domain_max, x)

    if f_type in ["quadratic", "quadratic_u_shaped", "u_shaped"]:
        a = float(sampled_params[0])
        x_opt = float(nadir_value if nadir_value is not None else ref)
        log_hr = a * ((x - x_opt) ** 2) - a * ((ref - x_opt) ** 2)

    elif f_type in ["log_log"]:
        beta = float(sampled_params[0])
        x_safe = max(x, 1e-4)
        ref_safe = max(ref, 1e-4)
        log_hr = beta * (math.log(x_safe) - math.log(ref_safe))

    elif f_type in ["piecewise_linear", "piecewise"]:
        if len(sampled_params) >= 2:
            slope_low = float(sampled_params[0])
            slope_high = float(sampled_params[1])
        else:
            slope_low = 0.0
            slope_high = float(sampled_params[0])
        x_opt = float(nadir_value if nadir_value is not None else ref)
        if slope_low == 0.0 and slope_high == 0.0:
            log_hr = 0.0
        else:
            def _pw(val):
                return slope_low * (x_opt - val) if val < x_opt else slope_high * (val - x_opt)
            log_hr = _pw(x) - _pw(ref)

    else:
        beta = float(sampled_params[0])
        log_hr = beta * (x - ref)

    return float(np.exp(np.clip(log_hr, -6.0, 6.0)))


# =======================================================================
# Section 3: 1-SD Optimization
# =======================================================================

def optimize_by_one_sd(
    observed_value: float,
    population_sd: float,
    directionality: str,
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
    p1: Optional[float] = None,
    p99: Optional[float] = None,
) -> Tuple[float, bool]:
    """
    Calculates the optimized biomarker value after a 1-SD shift in the
    favorable direction.

    Returns (optimized_value, was_clipped).
    """
    if directionality == "lower_better":
        optimized = observed_value - population_sd
    elif directionality == "higher_better":
        optimized = observed_value + population_sd
    else:
        # U-shaped or J-shaped: move toward the optimal target
        # For the first version, treat as lower_better if value > median
        optimized = observed_value - population_sd

    was_clipped = False

    # Clip to valid domain
    if valid_min is not None and optimized < valid_min:
        optimized = valid_min
        was_clipped = True
    if valid_max is not None and optimized > valid_max:
        optimized = valid_max
        was_clipped = True

    # Clip to empirical domain (P1-P99) if available
    if p1 is not None and optimized < p1:
        optimized = p1
        was_clipped = True
    if p99 is not None and optimized > p99:
        optimized = p99
        was_clipped = True

    return float(optimized), was_clipped


# =======================================================================
# Section 4: Survival and Life Expectancy Calculation
# =======================================================================

def survival_under_hr(
    age: float,
    sex: str,
    hr: float,
    t_grid: np.ndarray,
) -> np.ndarray:
    """
    Calculates survival S(t) = exp(-HR * integral_0^t h0(age+u) du)
    where h0 is the baseline Gompertz hazard.

    For Gompertz: integral_0^t h0(age+u) du = (b/c) * (exp(c*(age+t)) - exp(c*age))
    """
    b, c = _GOMPERTZ_PARAMS.get(sex, _GOMPERTZ_PARAMS["M"])
    if c == 0:
        cum_hazard = b * t_grid
    else:
        cum_hazard = (b / c) * (np.exp(c * (age + t_grid)) - np.exp(c * age))

    # Clip to avoid overflow
    cum_hazard = np.clip(cum_hazard, 0, 50)
    return np.exp(-hr * cum_hazard)


def integrate_survival(survival: np.ndarray, dt: float = 1.0) -> float:
    """
    Numerically integrates the survival curve to get expected remaining life.
    Uses the trapezoidal rule.
    """
    return float(np.trapezoid(survival, dx=dt))


# =======================================================================
# Section 5: Monte Carlo Simulation
# =======================================================================

def run_monte_carlo_optimization(
    biomarker_slug: str,
    observed_value: float,
    age: int,
    sex: str,
    hr_function: Dict[str, Any],
    population_distribution: Dict[str, Any],
    directionality: str,
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
    p1: Optional[float] = None,
    p99: Optional[float] = None,
    optimization_sd: float = 1.0,
    n_simulations: int = 10000,
    seed: Optional[int] = 20260821,
    t_max: float = 100.0,
    measurement_error_enabled: bool = False,
    test_measurement_error: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Runs the Monte Carlo biomarker optimization simulation.

    Parameters:
        biomarker_slug: slug of the biomarker
        observed_value: the person's observed biomarker value
        age: age at test
        sex: 'M' or 'F'
        hr_function: dict with fit_type, parameters, reference_value, shape, nadir_value, domain_min, domain_max
        population_distribution: dict with mean, sd, p5, p25, p50, p75, p95
        directionality: 'lower_better', 'higher_better', 'u_shaped'
        valid_min, valid_max: biomarker valid domain
        p1, p99: empirical domain bounds for clipping
        optimization_sd: number of SDs to shift (default 1.0)
        n_simulations: number of Monte Carlo iterations
        seed: random seed for reproducibility
        t_max: maximum follow-up age (default 100)
        measurement_error_enabled: whether to include measurement uncertainty
        test_measurement_error: sigma of test measurement error

    Returns:
        dict with all simulation results
    """
    rng = np.random.RandomState(seed)

    # Extract HR function parameters
    fit_type = hr_function.get("fit_type", "log_linear_per_sd")
    reference_value = float(hr_function.get("reference_value", 1.0))
    parameters = hr_function.get("parameters", {})
    shape = hr_function.get("shape", "monotonic_increasing")
    nadir_value = hr_function.get("nadir_value")
    hr_domain_min = hr_function.get("domain_min", valid_min)
    hr_domain_max = hr_function.get("domain_max", valid_max)

    # Extract population distribution
    pop_sd = float(population_distribution.get("sd", 1.0))
    if pop_sd <= 0:
        pop_sd = 1.0
    pop_mean = float(population_distribution.get("mean", 0.0))

    # Determine optimization direction
    # For U-shaped, we need to know which direction is favorable
    # For the first version, use the directionality field
    if directionality == "u_shaped":
        # Move toward the nadir
        nadir = float(nadir_value if nadir_value is not None else reference_value)
        if observed_value > nadir:
            direction_sign = -1.0  # lower is better
        else:
            direction_sign = 1.0  # higher is better
    elif directionality == "lower_better":
        direction_sign = -1.0
    elif directionality == "higher_better":
        direction_sign = 1.0
    else:
        direction_sign = -1.0

    # Calculate optimized value
    shift_delta = direction_sign * optimization_sd * pop_sd
    raw_optimized = observed_value + shift_delta

    # Clip to valid domain
    optimized_value = raw_optimized
    was_clipped = False
    if valid_min is not None and optimized_value < valid_min:
        optimized_value = valid_min
        was_clipped = True
    if valid_max is not None and optimized_value > valid_max:
        optimized_value = valid_max
        was_clipped = True
    if p1 is not None and optimized_value < p1:
        optimized_value = p1
        was_clipped = True
    if p99 is not None and optimized_value > p99:
        optimized_value = p99
        was_clipped = True

    # Time grid for survival integration
    t_grid = np.arange(0, t_max - age + 1, 1.0)
    if len(t_grid) < 2:
        t_grid = np.array([0.0, 1.0])

    # Pre-compute baseline cumulative hazard on the time grid
    b, c = _GOMPERTZ_PARAMS.get(sex, _GOMPERTZ_PARAMS["M"])
    if c == 0:
        baseline_cum_hazard = b * t_grid
    else:
        baseline_cum_hazard = (b / c) * (np.exp(c * (age + t_grid)) - np.exp(c * age))
    baseline_cum_hazard = np.clip(baseline_cum_hazard, 0, 50)

    # Sample HR model parameters
    sampled_params = sample_hr_params(
        fit_type=fit_type,
        reference_value=reference_value,
        parameters=parameters,
        shape=shape,
        nadir_value=nadir_value,
        n_samples=n_simulations,
        rng=rng,
    )

    # Arrays to store results
    hr_current_arr = np.zeros(n_simulations)
    hr_optimized_arr = np.zeros(n_simulations)
    le_current_arr = np.zeros(n_simulations)
    le_optimized_arr = np.zeros(n_simulations)
    ylg_arr = np.zeros(n_simulations)

    # Measurement error sampling
    if measurement_error_enabled and test_measurement_error is not None and test_measurement_error > 0:
        x_true_arr = rng.normal(observed_value, test_measurement_error, size=n_simulations)
        # Clip to valid domain
        if valid_min is not None:
            x_true_arr = np.maximum(x_true_arr, valid_min)
        if valid_max is not None:
            x_true_arr = np.minimum(x_true_arr, valid_max)
    else:
        x_true_arr = np.full(n_simulations, observed_value)

    for i in range(n_simulations):
        # 1. Evaluate HR at current biomarker
        hr_current_arr[i] = evaluate_hr_with_sampled_params(
            x=x_true_arr[i],
            fit_type=fit_type,
            reference_value=reference_value,
            sampled_params=sampled_params[i],
            shape=shape,
            nadir_value=nadir_value,
            domain_min=hr_domain_min,
            domain_max=hr_domain_max,
        )

        # 2. Calculate optimized biomarker for this simulation
        if measurement_error_enabled and test_measurement_error is not None and test_measurement_error > 0:
            x_opt_i = x_true_arr[i] + shift_delta
            if valid_min is not None:
                x_opt_i = max(valid_min, x_opt_i)
            if valid_max is not None:
                x_opt_i = min(valid_max, x_opt_i)
            if p1 is not None:
                x_opt_i = max(p1, x_opt_i)
            if p99 is not None:
                x_opt_i = min(p99, x_opt_i)
        else:
            x_opt_i = optimized_value

        # 3. Evaluate HR at optimized biomarker
        hr_optimized_arr[i] = evaluate_hr_with_sampled_params(
            x=x_opt_i,
            fit_type=fit_type,
            reference_value=reference_value,
            sampled_params=sampled_params[i],
            shape=shape,
            nadir_value=nadir_value,
            domain_min=hr_domain_min,
            domain_max=hr_domain_max,
        )

        # 4. Calculate survival curves
        survival_current = np.exp(-hr_current_arr[i] * baseline_cum_hazard)
        survival_optimized = np.exp(-hr_optimized_arr[i] * baseline_cum_hazard)

        # 5. Integrate survival for life expectancy
        le_current_arr[i] = integrate_survival(survival_current, dt=1.0)
        le_optimized_arr[i] = integrate_survival(survival_optimized, dt=1.0)

        # 6. Calculate YLG
        ylg_arr[i] = le_optimized_arr[i] - le_current_arr[i]

    # =======================================================================
    # Section 6: Summary Statistics
    # =======================================================================

    def _summary_stats(arr: np.ndarray) -> Dict[str, float]:
        return {
            "mean": round(float(np.mean(arr)), 4),
            "median": round(float(np.median(arr)), 4),
            "sd": round(float(np.std(arr)), 4),
            "p2_5": round(float(np.percentile(arr, 2.5)), 4),
            "p5": round(float(np.percentile(arr, 5)), 4),
            "p25": round(float(np.percentile(arr, 25)), 4),
            "p75": round(float(np.percentile(arr, 75)), 4),
            "p95": round(float(np.percentile(arr, 95)), 4),
            "p97_5": round(float(np.percentile(arr, 97.5)), 4),
        }

    hr_current_stats = _summary_stats(hr_current_arr)
    hr_optimized_stats = _summary_stats(hr_optimized_arr)
    le_current_stats = _summary_stats(le_current_arr)
    le_optimized_stats = _summary_stats(le_optimized_arr)
    ylg_stats = _summary_stats(ylg_arr)

    # Probability calculations
    prob_positive = float(np.mean(ylg_arr > 0))
    prob_gt_0_25 = float(np.mean(ylg_arr > 0.25))
    prob_gt_0_5 = float(np.mean(ylg_arr > 0.5))
    prob_gt_1 = float(np.mean(ylg_arr > 1.0))
    prob_harm = float(np.mean(ylg_arr < 0))

    # Histogram data for visualization (20 bins)
    def _histogram(arr: np.ndarray, n_bins: int = 20) -> Dict[str, List]:
        counts, bin_edges = np.histogram(arr, bins=n_bins)
        return {
            "counts": [int(c) for c in counts],
            "bin_edges": [round(float(e), 4) for e in bin_edges],
        }

    hr_current_hist = _histogram(hr_current_arr)
    hr_optimized_hist = _histogram(hr_optimized_arr)
    ylg_hist = _histogram(ylg_arr)

    # Baseline life expectancy (no biomarker effect)
    baseline_le = expected_remaining_life(age, sex, t_max)

    return {
        "biomarker": biomarker_slug,
        "observed_value": round(float(observed_value), 4),
        "population_sd": round(pop_sd, 4),
        "optimization_delta": round(shift_delta, 4),
        "optimized_value": round(float(optimized_value), 4),
        "optimization_clipped": was_clipped,
        "age": age,
        "sex": sex,
        "directionality": directionality,

        "current_hr": {
            **hr_current_stats,
            "uncertainty_95": [hr_current_stats["p2_5"], hr_current_stats["p97_5"]],
        },
        "optimized_hr": {
            **hr_optimized_stats,
            "uncertainty_95": [hr_optimized_stats["p2_5"], hr_optimized_stats["p97_5"]],
        },
        "remaining_life": {
            "current": le_current_stats,
            "optimized": le_optimized_stats,
            "current_median": le_current_stats["median"],
            "optimized_median": le_optimized_stats["median"],
            "baseline_no_biomarker": round(baseline_le, 2),
        },
        "years_life_gained": {
            **ylg_stats,
            "uncertainty_95": [ylg_stats["p2_5"], ylg_stats["p97_5"]],
        },
        "probability_positive_benefit": round(prob_positive, 4),
        "probability_gain_over_0_25_years": round(prob_gt_0_25, 4),
        "probability_gain_over_0_5_years": round(prob_gt_0_5, 4),
        "probability_gain_over_1_year": round(prob_gt_1, 4),
        "probability_of_harm": round(prob_harm, 4),

        "histograms": {
            "current_hr": hr_current_hist,
            "optimized_hr": hr_optimized_hist,
            "years_life_gained": ylg_hist,
        },

        "metadata": {
            "n_simulations": n_simulations,
            "mortality_source": "Gompertz model calibrated to US NCHS Period Life Tables 2019",
            "model_type": f"HR function: {fit_type}",
            "optimization_type": "hypothetical_1SD",
            "causal_intervention": False,
            "simulation_seed": seed,
            "t_max": t_max,
            "measurement_error_enabled": measurement_error_enabled,
            "test_measurement_error": test_measurement_error,
            "hr_function": {
                "fit_type": fit_type,
                "reference_value": reference_value,
                "shape": shape,
                "nadir_value": nadir_value,
                "domain_min": hr_domain_min,
                "domain_max": hr_domain_max,
            },
            "population_distribution": {
                "mean": pop_mean,
                "sd": pop_sd,
            },
        },

        "disclaimer": (
            "This simulation estimates the expected survival difference associated with a "
            "hypothetical 1-SD improvement in the biomarker. It does not establish that an "
            "intervention capable of producing this change would necessarily produce the "
            "modeled mortality benefit. The Monte Carlo uncertainty reflects statistical "
            "uncertainty in the biomarker-mortality relationship, not uncertainty about "
            "the causal effect of changing the biomarker."
        ),
    }


# =======================================================================
# Section 7: Synthetic Validation
# =======================================================================

def synthetic_validation_test() -> Dict[str, Any]:
    """
    Runs synthetic validation tests to verify the Monte Carlo engine.

    Test 1: HR_current = HR_optimized -> YLG should be ~0
    Test 2: HR_current > HR_optimized -> YLG should be positive
    Test 3: Increasing age should reduce remaining life expectancy
    """
    results = {}

    # Test 1: Zero biomarker change -> YLG ~ 0
    # Use a simple linear HR function with beta=0 (no effect)
    hr_func_no_effect = {
        "fit_type": "log_linear_per_sd",
        "reference_value": 1.0,
        "parameters": {"beta": 0.0},
        "shape": "monotonic_increasing",
        "nadir_value": None,
        "domain_min": 0.0,
        "domain_max": 10.0,
    }
    pop_dist = {"mean": 5.0, "sd": 1.0}

    res1 = run_monte_carlo_optimization(
        biomarker_slug="test_no_effect",
        observed_value=5.0,
        age=60,
        sex="M",
        hr_function=hr_func_no_effect,
        population_distribution=pop_dist,
        directionality="lower_better",
        valid_min=0.0,
        valid_max=10.0,
        n_simulations=1000,
        seed=42,
    )
    results["test_zero_change"] = {
        "ylg_mean": res1["years_life_gained"]["mean"],
        "ylg_median": res1["years_life_gained"]["median"],
        "pass": abs(res1["years_life_gained"]["mean"]) < 0.01,
    }

    # Test 2: HR_current > HR_optimized -> YLG positive
    hr_func_effect = {
        "fit_type": "log_linear_per_sd",
        "reference_value": 1.0,
        "parameters": {"beta": 0.5},
        "shape": "monotonic_increasing",
        "nadir_value": None,
        "domain_min": 0.0,
        "domain_max": 10.0,
    }
    res2 = run_monte_carlo_optimization(
        biomarker_slug="test_effect",
        observed_value=5.0,
        age=60,
        sex="M",
        hr_function=hr_func_effect,
        population_distribution=pop_dist,
        directionality="lower_better",
        valid_min=0.0,
        valid_max=10.0,
        n_simulations=1000,
        seed=42,
    )
    results["test_positive_effect"] = {
        "hr_current_median": res2["current_hr"]["median"],
        "hr_optimized_median": res2["optimized_hr"]["median"],
        "ylg_mean": res2["years_life_gained"]["mean"],
        "ylg_median": res2["years_life_gained"]["median"],
        "prob_positive": res2["probability_positive_benefit"],
        "pass": res2["years_life_gained"]["mean"] > 0 and res2["probability_positive_benefit"] > 0.9,
    }

    # Test 3: Increasing age reduces remaining life
    res3_40 = run_monte_carlo_optimization(
        biomarker_slug="test_age",
        observed_value=5.0,
        age=40,
        sex="M",
        hr_function=hr_func_effect,
        population_distribution=pop_dist,
        directionality="lower_better",
        valid_min=0.0,
        valid_max=10.0,
        n_simulations=500,
        seed=42,
    )
    res3_70 = run_monte_carlo_optimization(
        biomarker_slug="test_age",
        observed_value=5.0,
        age=70,
        sex="M",
        hr_function=hr_func_effect,
        population_distribution=pop_dist,
        directionality="lower_better",
        valid_min=0.0,
        valid_max=10.0,
        n_simulations=500,
        seed=42,
    )
    results["test_age_effect"] = {
        "le_40_median": res3_40["remaining_life"]["current_median"],
        "le_70_median": res3_70["remaining_life"]["current_median"],
        "pass": res3_40["remaining_life"]["current_median"] > res3_70["remaining_life"]["current_median"],
    }

    # Test 4: Reference value -> HR ~ 1
    res4 = run_monte_carlo_optimization(
        biomarker_slug="test_ref",
        observed_value=1.0,  # reference value
        age=60,
        sex="M",
        hr_function=hr_func_effect,
        population_distribution=pop_dist,
        directionality="lower_better",
        valid_min=0.0,
        valid_max=10.0,
        n_simulations=1000,
        seed=42,
    )
    results["test_reference_hr"] = {
        "hr_current_median": res4["current_hr"]["median"],
        "pass": abs(res4["current_hr"]["median"] - 1.0) < 0.1,
    }

    results["all_pass"] = all(r["pass"] for r in results.values() if isinstance(r, dict) and "pass" in r)

    return results


if __name__ == "__main__":
    print("Running synthetic validation tests...")
    results = synthetic_validation_test()
    for name, res in results.items():
        if isinstance(res, dict) and "pass" in res:
            status = "PASS" if res["pass"] else "FAIL"
            print(f"  {name}: {status}")
            for k, v in res.items():
                if k != "pass":
                    print(f"    {k}: {v}")
        else:
            print(f"  {name}: {res}")
    print(f"\nAll tests passed: {results['all_pass']}")
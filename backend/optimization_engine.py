"""
Derived Analytics Optimization Engine for Mortality Biomarkers.

Calculates:
1. HR Curve evaluation: HR(x) given curve parameters and model type.
2. Discrete population distribution sampling / density binning: f(x) over valid domain.
3. Baseline Expected Hazard: E[HR_0] = \\sum_i p_i HR(x_i)
4. Population Shift Scenarios:
   - Optimal Target Nadir Shift: shifting towards argmin HR(x)
   - Standardized SD Shifts: +0.25 SD, +0.50 SD, +1.00 SD, +1.50 SD, +2.00 SD
   - Percentile Transformations: Truncating lower/upper tail towards median
5. Optimized Expected Hazard: E[HR_delta] = \\sum_i p_i HR(x_shifted_i)
6. Differences:
   - Absolute Hazard Delta: \\Delta HR = E[HR_0] - E[HR_delta]
   - Relative Hazard Reduction: RHR = 1 - (E[HR_delta] / E[HR_0])
7. Individual Benefit Distribution:
   - Benefit per bin i: B_i = HR(x_i) - HR(x_shifted_i)
   - Percentiles of benefit (P10, P25, P50, P75, P90, Max)
   - Fraction benefiting (B_i > 0) vs Fraction harmed (B_i < 0)
8. Physiological Domain Guardrails:
   - Tracks fraction clamped/out of domain: IN_DOMAIN, BOUNDARY_REACHED, OUT_OF_DOMAIN.
"""

import math
import numpy as np
from typing import Dict, Any, List, Tuple, Optional


def evaluate_hr(x: float, curve_type: str, reference_value: float, parameters: Dict[str, Any], optimal_value: Optional[float] = None) -> float:
    """
    Computes Hazard Ratio HR(x) for a given value x.
    """
    if math.isnan(x) or math.isinf(x):
        return 1.0

    if curve_type == "linear_log":
        # ln(HR(x)) = beta * (x - reference_value)
        beta = parameters.get("beta", 0.0)
        log_hr = beta * (x - reference_value)
        return float(np.exp(np.clip(log_hr, -5.0, 5.0)))

    elif curve_type == "quadratic":
        # ln(HR(x)) = a * (x - x_opt)^2 - a * (reference_value - x_opt)^2
        # Normalized so HR(reference_value) == 1.0 (log_hr == 0.0 at the reference).
        a = parameters.get("a", 0.001)
        x_opt = optimal_value if optimal_value is not None else parameters.get("x_opt", reference_value)
        log_hr = a * ((x - x_opt) ** 2) - a * ((reference_value - x_opt) ** 2)
        return float(np.exp(np.clip(log_hr, -5.0, 5.0)))

    elif curve_type == "log_log":
        # ln(HR(x)) = beta * (ln(x) - ln(reference_value))
        beta = parameters.get("beta", 0.0)
        x_safe = max(x, 1e-4)
        ref_safe = max(reference_value, 1e-4)
        log_hr = beta * (math.log(x_safe) - math.log(ref_safe))
        return float(np.exp(np.clip(log_hr, -5.0, 5.0)))

    elif curve_type == "piecewise":
        # Piecewise spline/linear:
        # f(v) = slope_low * (x_opt - v) if v < x_opt else slope_high * (v - x_opt)
        # Normalized so HR(reference_value) == 1.0 -> ln(HR(x)) = f(x) - f(reference_value)
        x_opt = optimal_value if optimal_value is not None else parameters.get("x_opt", reference_value)
        slope_low = parameters.get("slope_low", 0.0)
        slope_high = parameters.get("slope_high", 0.0)
        def _piecewise_f(val: float) -> float:
            return slope_low * (x_opt - val) if val < x_opt else slope_high * (val - x_opt)
        log_hr = _piecewise_f(x) - _piecewise_f(reference_value)
        return float(np.exp(np.clip(log_hr, -5.0, 5.0)))

    else:
        # Fallback linear log
        beta = parameters.get("beta", 0.0)
        log_hr = beta * (x - reference_value)
        return float(np.exp(np.clip(log_hr, -5.0, 5.0)))


def generate_population_distribution(
    mean: float,
    sd: float,
    valid_min: float,
    valid_max: float,
    n_bins: int = 300,
    p5: Optional[float] = None,
    p50: Optional[float] = None,
    p95: Optional[float] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates discrete density bins (x_values, probabilities) representing the population distribution.
    Uses truncated normal or empirical distribution bounded within physiological boundaries [valid_min, valid_max].
    """
    if sd <= 0:
        sd = max(mean * 0.15, 0.1)

    # Grid covering 4.5 SDs or valid domain
    grid_min = max(valid_min, mean - 4.5 * sd)
    grid_max = min(valid_max, mean + 4.5 * sd)

    if grid_max <= grid_min:
        grid_min = valid_min
        grid_max = valid_max

    x_bins = np.linspace(grid_min, grid_max, n_bins)
    
    # Gaussian density pdf
    pdf = np.exp(-0.5 * ((x_bins - mean) / sd) ** 2)
    sum_pdf = np.sum(pdf)
    if sum_pdf > 0:
        probabilities = pdf / sum_pdf
    else:
        probabilities = np.ones(n_bins) / n_bins

    return x_bins, probabilities


def compute_baseline_expected_hazard(
    x_bins: np.ndarray,
    probabilities: np.ndarray,
    curve_type: str,
    reference_value: float,
    parameters: Dict[str, Any],
    optimal_value: Optional[float] = None,
    **_unused: Any,
) -> Tuple[float, np.ndarray]:
    """
    Computes E[HR_0] = \\sum_i p_i HR(x_i)
    """
    hrs = np.array([
        evaluate_hr(x, curve_type, reference_value, parameters, optimal_value)
        for x in x_bins
    ])
    baseline_ehr = float(np.sum(probabilities * hrs))
    return baseline_ehr, hrs


def compute_shift_optimization(
    x_bins: np.ndarray,
    probabilities: np.ndarray,
    baseline_hrs: np.ndarray,
    curve_type: str,
    reference_value: float,
    parameters: Dict[str, Any],
    valid_min: float,
    valid_max: float,
    directionality: str,
    pop_sd: float,
    shift_type: str,
    shift_magnitude: float,
    optimal_value: Optional[float] = None,
    pop_median: Optional[float] = None,
    pop_p25: Optional[float] = None,
    pop_p75: Optional[float] = None
) -> Dict[str, Any]:
    """
    Performs population shift calculation under a specific scenario.
    """
    n_bins = len(x_bins)
    x_shifted = np.zeros(n_bins)
    clamped_count = 0

    direction_sign = -1.0 if directionality == "lower_better" else (1.0 if directionality == "higher_better" else 0.0)

    if shift_type == "sd_shift":
        # Shift each bin towards beneficial direction by magnitude * SD
        if directionality in ["u_shaped", "j_shaped", "inverted_u"]:
            # Move towards optimal target nadir x*
            target = optimal_value if optimal_value is not None else reference_value
            step_size = shift_magnitude * pop_sd
            for i, x in enumerate(x_bins):
                dist_to_target = target - x
                if abs(dist_to_target) <= step_size:
                    val = target
                else:
                    val = x + np.sign(dist_to_target) * step_size
                # Clamp to domain
                if val < valid_min or val > valid_max:
                    clamped_count += 1
                x_shifted[i] = np.clip(val, valid_min, valid_max)
        else:
            delta_val = direction_sign * shift_magnitude * pop_sd
            for i, x in enumerate(x_bins):
                val = x + delta_val
                if val < valid_min or val > valid_max:
                    clamped_count += 1
                x_shifted[i] = np.clip(val, valid_min, valid_max)

    elif shift_type == "percentile_shift":
        # Example: Bring worst quartile individuals to median
        target = pop_median if pop_median is not None else reference_value
        threshold_25 = pop_p25 if pop_p25 is not None else (reference_value - 0.674 * pop_sd)
        threshold_75 = pop_p75 if pop_p75 is not None else (reference_value + 0.674 * pop_sd)

        for i, x in enumerate(x_bins):
            if directionality == "lower_better":
                # High values worse -> those > threshold_75 shifted to median
                if x > threshold_75:
                    x_shifted[i] = target
                else:
                    x_shifted[i] = x
            elif directionality == "higher_better":
                # Low values worse -> those < threshold_25 shifted to median
                if x < threshold_25:
                    x_shifted[i] = target
                else:
                    x_shifted[i] = x
            else:
                # U/J shape -> extremes outside [p25, p75] shifted to median/optimum
                opt = optimal_value if optimal_value is not None else target
                if x < threshold_25:
                    x_shifted[i] = opt
                elif x > threshold_75:
                    x_shifted[i] = opt
                else:
                    x_shifted[i] = x
            x_shifted[i] = np.clip(x_shifted[i], valid_min, valid_max)

    elif shift_type == "target_nadir":
        # Population shifted 100% to optimal nadir target
        target = optimal_value if optimal_value is not None else reference_value
        x_shifted[:] = np.clip(target, valid_min, valid_max)

    else:
        # Default 0.5 SD shift
        delta_val = direction_sign * 0.5 * pop_sd
        x_shifted = np.clip(x_bins + delta_val, valid_min, valid_max)

    # Calculate optimized HR for each shifted bin
    opt_hrs = np.array([
        evaluate_hr(x, curve_type, reference_value, parameters, optimal_value)
        for x in x_shifted
    ])

    baseline_ehr = float(np.sum(probabilities * baseline_hrs))
    optimized_ehr = float(np.sum(probabilities * opt_hrs))
    delta_hr = baseline_ehr - optimized_ehr
    rhr = (delta_hr / baseline_ehr) if baseline_ehr > 0 else 0.0

    # Individual benefit calculation: B_i = HR_0(x_i) - HR_opt(x_shifted_i)
    # Benefit > 0 means mortality hazard was reduced for individual at x_i
    benefit_distribution = baseline_hrs - opt_hrs
    mean_benefit = float(np.sum(probabilities * benefit_distribution))

    # Calculate weighted percentiles of benefit
    sorted_indices = np.argsort(benefit_distribution)
    sorted_benefits = benefit_distribution[sorted_indices]
    sorted_probs = probabilities[sorted_indices]
    cum_probs = np.cumsum(sorted_probs)

    def get_weighted_percentile(p: float) -> float:
        idx = np.searchsorted(cum_probs, p)
        idx = min(idx, len(sorted_benefits) - 1)
        return float(sorted_benefits[idx])

    p10_b = get_weighted_percentile(0.10)
    p25_b = get_weighted_percentile(0.25)
    p50_b = get_weighted_percentile(0.50)
    p75_b = get_weighted_percentile(0.75)
    p90_b = get_weighted_percentile(0.90)
    max_b = float(np.max(benefit_distribution))

    # Fractions benefiting vs harmed
    benefiting_mask = benefit_distribution > 1e-4
    harmed_mask = benefit_distribution < -1e-4
    fraction_benefiting = float(np.sum(probabilities[benefiting_mask]))
    fraction_harmed = float(np.sum(probabilities[harmed_mask]))

    # Boundary status
    fraction_clamped = clamped_count / n_bins
    if fraction_clamped == 0:
        domain_status = "IN_DOMAIN"
    elif fraction_clamped < 0.25:
        domain_status = "BOUNDARY_REACHED"
    else:
        domain_status = "OUT_OF_DOMAIN"

    return {
        "baseline_expected_hr": baseline_ehr,
        "optimized_expected_hr": optimized_ehr,
        "delta_hr": delta_hr,
        "relative_hazard_reduction": rhr,
        "domain_status": domain_status,
        "fraction_out_of_domain": fraction_clamped,
        "mean_individual_benefit": mean_benefit,
        "median_individual_benefit": p50_b,
        "p10_benefit": p10_b,
        "p25_benefit": p25_b,
        "p75_benefit": p75_b,
        "p90_benefit": p90_b,
        "max_individual_benefit": max_b,
        "fraction_benefiting": fraction_benefiting,
        "fraction_harmed": fraction_harmed,
        "x_bins": x_bins.tolist(),
        "probabilities": probabilities.tolist(),
        "baseline_hrs": baseline_hrs.tolist(),
        "x_shifted": x_shifted.tolist(),
        "opt_hrs": opt_hrs.tolist(),
        "benefit_distribution": benefit_distribution.tolist()
    }


# =======================================================================
# Section 7: Value-of-Information (VOI) Monte Carlo Simulation Module
# =======================================================================

def sample_continuous_distribution(
    fit_type: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    domain_min: Optional[float] = None,
    domain_max: Optional[float] = None,
    n_samples: int = 5000,
    random_seed: Optional[int] = None,
    family: Optional[str] = None,
    shape: Optional[float] = None,
    loc: Optional[float] = None,
    scale: Optional[float] = None,
    mean: Optional[float] = None,
    sd: Optional[float] = None,
    **kwargs
) -> np.ndarray:
    """
    Samples N values from a continuous parametric distribution.
    Supports call signatures:
    - (family, shape, loc, scale, n_samples)
    - (fit_type, parameters, domain_min, domain_max, n_samples)
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    fam = (family or fit_type or "normal").lower()
    params = parameters or {}

    # Extract location/scale/shape
    loc_val = loc if loc is not None else params.get("loc", params.get("mean", mean if mean is not None else 0.0))
    scale_val = scale if scale is not None else params.get("scale", params.get("sd", params.get("sigma", sd if sd is not None else 1.0)))
    shape_val = shape if shape is not None else params.get("shape", params.get("mu", params.get("a", 1.0)))

    if scale_val is None or scale_val <= 0:
        scale_val = 1.0

    if fam in ["normal", "gaussian"]:
        raw = np.random.normal(loc=loc_val, scale=scale_val, size=n_samples)
    elif fam in ["lognormal", "log_normal"]:
        # In lognormal: shape_val or mu is log-mean, scale_val or sigma is log-sd
        # If loc_val is positive and mu is not given, mu = log(loc_val)
        if "mu" in params:
            mu_val = params["mu"]
        elif shape is not None:
            mu_val = shape_val
        elif loc_val is not None and loc_val > 0:
            mu_val = float(np.log(loc_val))
        else:
            mu_val = 0.0
        sigma_val = scale_val if scale_val is not None and scale_val > 0 else 0.5
        raw = np.random.lognormal(mean=mu_val, sigma=sigma_val, size=n_samples)
    elif fam == "gamma":
        a_val = shape_val if shape_val is not None and shape_val > 0 else 2.0
        raw = np.random.gamma(shape=a_val, scale=scale_val, size=n_samples) + (loc_val or 0.0)
    elif fam in ["weibull", "weibull_min"]:
        a_val = shape_val if shape_val is not None and shape_val > 0 else 1.5
        raw = np.random.weibull(a_val, size=n_samples) * scale_val + (loc_val or 0.0)
    elif fam in ["empirical_ecdf", "kde"]:
        knots = params.get("knots")
        probs = params.get("probs")
        if knots and probs and len(knots) == len(probs):
            raw = np.random.choice(knots, size=n_samples, p=probs)
            j_sd = scale_val * 0.05
            raw += np.random.normal(0, j_sd, size=n_samples)
        else:
            raw = np.random.normal(loc=loc_val, scale=scale_val, size=n_samples)
    else:
        raw = np.random.normal(loc=loc_val, scale=scale_val, size=n_samples)

    if domain_min is not None and domain_max is not None and domain_max > domain_min:
        raw = np.clip(raw, domain_min, domain_max)
    elif domain_min is not None:
        raw = np.maximum(raw, domain_min)
    elif domain_max is not None:
        raw = np.minimum(raw, domain_max)

    return raw


def evaluate_hr_function(
    x: Any = None,
    fit_type: Optional[str] = None,
    reference_value: float = 1.0,
    parameters: Optional[Dict[str, Any]] = None,
    domain_min: Optional[float] = None,
    domain_max: Optional[float] = None,
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
    shape: str = "monotonic_increasing",
    nadir_value: Optional[float] = None,
    as_log: bool = False,
    function_type: Optional[str] = None,
    **kwargs
) -> Any:
    """
    Evaluates Hazard Ratio HR(x) continuously in log(HR) or HR space.
    Guards domain strictly and normalizes HR(reference_value) == 1.0 (log_hr == 0.0).
    Supports scalar float or np.ndarray for x.
    """
    f_type = (function_type or fit_type or "log_linear_per_sd").lower()
    params = parameters or {}
    d_min = valid_min if valid_min is not None else domain_min
    d_max = valid_max if valid_max is not None else domain_max

    is_scalar = isinstance(x, (int, float, np.floating, np.integer))
    x_arr = np.array([x], dtype=float) if is_scalar else np.asarray(x, dtype=float)

    if d_min is not None and d_max is not None and d_max > d_min:
        x_clipped = np.clip(x_arr, d_min, d_max)
    elif d_min is not None:
        x_clipped = np.maximum(x_arr, d_min)
    elif d_max is not None:
        x_clipped = np.minimum(x_arr, d_max)
    else:
        x_clipped = x_arr

    ref_val = float(reference_value)

    if f_type in ["quadratic", "u_shaped"]:
        a = float(params.get("a", 0.005))
        x_opt = float(nadir_value if nadir_value is not None else params.get("x_opt", ref_val))
        # log_hr = a * (x - x_opt)^2 - a * (ref - x_opt)^2 -> ensures log_hr(ref) == 0.0
        log_hr = a * ((x_clipped - x_opt) ** 2) - a * ((ref_val - x_opt) ** 2)
    elif f_type in ["restricted_cubic_spline", "spline", "piecewise_linear", "piecewise"]:
        # Normalized spline / piecewise
        knots = params.get("knots", [ref_val])
        beta = float(params.get("beta", 0.3 if shape != "monotonic_decreasing" else -0.3))
        # If quadratic spline coefficients present:
        if "a" in params:
            a = float(params.get("a", 0.005))
            x_opt = float(nadir_value if nadir_value is not None else ref_val)
            log_hr = a * ((x_clipped - x_opt) ** 2) - a * ((ref_val - x_opt) ** 2)
        else:
            log_hr = beta * (x_clipped - ref_val)
    elif f_type in ["log_linear_per_sd", "log_linear_per_unit", "linear", "linear_log"]:
        beta = float(params.get("beta", 0.3 if shape != "monotonic_decreasing" else -0.3))
        log_hr = beta * (x_clipped - ref_val)
    elif f_type in ["log_log", "power"]:
        # ln(HR) = beta * ln(x / reference). Normalized so HR(reference) == 1.0.
        # Must mirror evaluate_hr() exactly: the two evaluators are used
        # interchangeably across the VOI/Monte-Carlo stack and any divergence
        # silently desynchronizes baseline EHR from the curve it describes.
        beta = float(params.get("beta", 0.3 if shape != "monotonic_decreasing" else -0.3))
        x_safe = np.maximum(x_clipped, 1e-4)
        ref_safe = max(ref_val, 1e-4)
        log_hr = beta * (np.log(x_safe) - math.log(ref_safe))
    else:
        beta = float(params.get("beta", 0.3 if shape != "monotonic_decreasing" else -0.3))
        log_hr = beta * (x_clipped - ref_val)

    if as_log:
        out = log_hr
    else:
        out = np.exp(np.clip(log_hr, -6.0, 6.0))

    if is_scalar:
        return float(out[0])
    return out


def run_voi_monte_carlo_simulation(
    dist_fit: Any = None,
    hr_func: Any = None,
    distribution_fit: Any = None,
    hr_function: Any = None,
    n_samples: int = 5000,
    n_simulations: Optional[int] = None,
    tolerance_sd: float = 0.5,
    tolerance: Optional[float] = None,
    blind_shift: Optional[float] = None,
    blind_intervention_shift: Optional[float] = None,
    random_seed: int = 42,
    **kwargs
) -> Dict[str, Any]:
    """
    Implements Spec Section 7: Value-of-Information (VOI) Monte Carlo Module.
    Accepts object models (DistributionFit, HRFunction) or dictionaries.
    """
    df = dist_fit if dist_fit is not None else distribution_fit
    hf = hr_func if hr_func is not None else hr_function

    if hasattr(df, "to_dict"):
        df_dict = df.to_dict()
    elif isinstance(df, dict):
        df_dict = df
    else:
        df_dict = {}

    if hasattr(hf, "to_dict"):
        hf_dict = hf.to_dict()
    elif isinstance(hf, dict):
        hf_dict = hf
    else:
        hf_dict = {}

    N = n_simulations if n_simulations is not None else n_samples

    # Distribution parameters
    family = df_dict.get("family") or df_dict.get("fit_type", "normal")
    param_shape = df_dict.get("param_shape")
    param_loc = df_dict.get("param_loc")
    param_scale = df_dict.get("param_scale")
    dist_params = df_dict.get("parameters", {})
    if not dist_params and (param_shape is not None or param_loc is not None or param_scale is not None):
        dist_params = {
            "shape": param_shape,
            "loc": param_loc,
            "scale": param_scale,
            "mean": param_loc or 0.0,
            "sd": param_scale or 1.0
        }

    d_min = df_dict.get("domain_min")
    d_max = df_dict.get("domain_max")
    pop_sd = float(dist_params.get("sd", dist_params.get("scale", param_scale or 1.0)))
    if pop_sd <= 0:
        pop_sd = 1.0
    pop_mean = float(dist_params.get("mean", dist_params.get("loc", param_loc or 0.0)))

    # HR function parameters
    hr_type = hf_dict.get("function_type") or hf_dict.get("fit_type", "quadratic")
    hr_params = hf_dict.get("parameters", {})
    hr_ref = float(hf_dict.get("reference_value", pop_mean if pop_mean != 0.0 else 1.0))
    hr_valid_min = hf_dict.get("valid_min", d_min)
    hr_valid_max = hf_dict.get("valid_max", d_max)
    hr_shape = hf_dict.get("shape", "monotonic_increasing")
    hr_nadir = hf_dict.get("nadir_value")

    # 1. Sample N baseline draws x0
    x0 = sample_continuous_distribution(
        family=family,
        shape=param_shape if param_shape is not None else dist_params.get("shape"),
        loc=param_loc if param_loc is not None else dist_params.get("loc"),
        scale=param_scale if param_scale is not None else dist_params.get("scale"),
        fit_type=family,
        parameters=dist_params,
        domain_min=hr_valid_min,
        domain_max=hr_valid_max,
        n_samples=N,
        random_seed=random_seed
    )

    # 2. Baseline log(HR0) and HR0
    log_hr0 = evaluate_hr_function(
        x0, fit_type=hr_type, parameters=hr_params,
        reference_value=hr_ref, valid_min=hr_valid_min,
        valid_max=hr_valid_max, shape=hr_shape, nadir_value=hr_nadir, as_log=True
    )
    hr0 = np.exp(np.clip(log_hr0, -6.0, 6.0))

    # 3. Informed Policy Shift
    tol_sd = tolerance if tolerance is not None else tolerance_sd
    tol_val = tol_sd * pop_sd

    x1_informed = np.zeros(N)
    within_tol_mask = np.zeros(N, dtype=bool)

    if hr_shape == "u_shaped":
        x_target = float(hr_nadir if hr_nadir is not None else hr_ref)
    elif hr_shape == "monotonic_decreasing":
        x_target = float(hr_valid_max if hr_valid_max is not None else (pop_mean + 3 * pop_sd))
    else:  # monotonic_increasing
        x_target = float(hr_valid_min if hr_valid_min is not None else (pop_mean - 3 * pop_sd))

    for i, val in enumerate(x0):
        dist_to_target = abs(x_target - val)
        if dist_to_target <= tol_val:
            within_tol_mask[i] = True

        if hr_shape == "u_shaped":
            direction = 1.0 if (x_target - val) > 0 else -1.0
        elif hr_shape == "monotonic_decreasing":
            direction = 1.0
        else:
            direction = -1.0

        step = min(1.0 * pop_sd, dist_to_target)
        shifted = val + direction * step
        if hr_valid_min is not None and hr_valid_max is not None:
            shifted = np.clip(shifted, hr_valid_min, hr_valid_max)
        x1_informed[i] = shifted

    log_hr1_informed = evaluate_hr_function(
        x1_informed, fit_type=hr_type, parameters=hr_params,
        reference_value=hr_ref, valid_min=hr_valid_min,
        valid_max=hr_valid_max, shape=hr_shape, nadir_value=hr_nadir, as_log=True
    )
    hr1_informed = np.exp(np.clip(log_hr1_informed, -6.0, 6.0))

    log_delta_informed = log_hr0 - log_hr1_informed  # positive = benefit

    # 4. Blind Policy Shift
    if blind_intervention_shift is not None:
        b_shift = float(blind_intervention_shift)
    elif blind_shift is not None:
        b_shift = float(blind_shift)
    else:
        primary_dir = -1.0 if hr_shape == "monotonic_increasing" else (1.0 if hr_shape == "monotonic_decreasing" else -0.5)
        b_shift = primary_dir * (1.0 * pop_sd)

    x1_blind = x0 + b_shift
    if hr_valid_min is not None and hr_valid_max is not None:
        x1_blind = np.clip(x1_blind, hr_valid_min, hr_valid_max)

    log_hr1_blind = evaluate_hr_function(
        x1_blind, fit_type=hr_type, parameters=hr_params,
        reference_value=hr_ref, valid_min=hr_valid_min,
        valid_max=hr_valid_max, shape=hr_shape, nadir_value=hr_nadir, as_log=True
    )
    hr1_blind = np.exp(np.clip(log_hr1_blind, -6.0, 6.0))
    log_delta_blind = log_hr0 - log_hr1_blind

    # Metrics
    mean_voi_delta_log_hr = float(np.mean(log_delta_informed))
    median_voi_delta_log_hr = float(np.median(log_delta_informed))
    fraction_within_tolerance = float(np.mean(within_tol_mask))

    informed_rrr = float(1.0 - np.exp(-max(mean_voi_delta_log_hr, 0.0)))
    blind_rrr = float(1.0 - np.exp(-max(float(np.mean(log_delta_blind)), 0.0)))

    # Histogram: 20 bins
    counts, bin_edges = np.histogram(log_delta_informed, bins=20)
    hist_dict = {
        "counts": [int(c) for c in counts],
        "bin_edges": [round(float(e), 4) for e in bin_edges]
    }

    histogram_data = []
    for count, b_left, b_right in zip(counts, bin_edges[:-1], bin_edges[1:]):
        histogram_data.append({
            "bin_start": round(float(b_left), 3),
            "bin_end": round(float(b_right), 3),
            "count": int(count),
            "fraction": round(float(count) / N, 4)
        })

    caveats = [
        "Observational & Causal Validity: Risk curves reflect observational epidemiology; interventions may not produce risk reductions identical to natural variations.",
        "Testing Burden & Cost-Effectiveness: Testing provides informational value only when biomarker-targeted interventions shift clinical decision-making vs empiric treatment.",
        "Subgroup & Stratum Specificity: Distribution and hazard characteristics vary across age, sex, and ethnicity strata, which should inform localized clinical risk stratifications."
    ]

    return {
        "n_samples": N,
        "n_simulations": N,
        "mean_voi_delta_log_hr": round(mean_voi_delta_log_hr, 4),
        "median_voi_delta_log_hr": round(median_voi_delta_log_hr, 4),
        "fraction_within_tolerance": round(fraction_within_tolerance, 4),
        "histogram_log_delta": hist_dict,
        "caveats": caveats,
        "interpretive_caveats": caveats,
        "informed_policy": {
            "mean_log_delta": round(mean_voi_delta_log_hr, 4),
            "median_log_delta": round(median_voi_delta_log_hr, 4),
            "mean_relative_risk_reduction": round(informed_rrr, 4),
            "percent_hazard_reduction": round(informed_rrr * 100.0, 2),
            "fraction_already_optimal": round(fraction_within_tolerance, 4),
            "fraction_benefiting": round(float(np.mean(log_delta_informed > 1e-4)), 4),
            "fraction_harmed": round(float(np.mean(log_delta_informed < -1e-4)), 4),
        },
        "blind_policy": {
            "mean_log_delta": round(float(np.mean(log_delta_blind)), 4),
            "mean_relative_risk_reduction": round(blind_rrr, 4),
            "percent_hazard_reduction": round(blind_rrr * 100.0, 2),
            "fraction_benefiting": round(float(np.mean(log_delta_blind > 1e-4)), 4),
            "fraction_harmed": round(float(np.mean(log_delta_blind < -1e-4)), 4),
        },
        "value_of_information": {
            "voi_hazard_reduction_gap": round(max(0.0, informed_rrr - blind_rrr), 4),
            "voi_percentage_points": round(max(0.0, informed_rrr - blind_rrr) * 100.0, 2),
            "information_gain_description": f"Testing and personalized targeting yields +{round(max(0.0, informed_rrr - blind_rrr) * 100.0, 2)}% incremental relative hazard reduction over blind population action."
        },
        "histogram": histogram_data
    }

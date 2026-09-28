"""
Hazard Curve Service — evaluates parametric HRFunction models on a value grid
and returns age/sex-conditional hazard ratio curves.

The existing HRFunction table stores parametric models (log_log, log_linear_per_sd,
quadratic_u_shaped, piecewise_linear) with 12 strata per biomarker — the full
sex × age-band grid:
  (all, all), (M, all), (F, all),
  (all, 20-39), (all, 40-59), (all, 60+),
  (M, 20-39), (F, 20-39), (M, 40-59), (F, 40-59), (M, 60+), (F, 60+)

This service:
1. Resolves the best-matching stratum for a given (age, sex) query
2. Evaluates the parametric HR function on a 100-point grid
3. Returns curve points with a `curve_specificity` flag indicating whether
   the curve is stratum-specific or a population-level fallback
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.models import HRFunction, Biomarker


# Age band boundaries for mapping a continuous age to a band
AGE_BANDS = [
    ("20-39", 20, 39),
    ("40-59", 40, 59),
    ("60+", 60, 120),
]

# Number of grid points for curve evaluation
GRID_SIZE = 100


def resolve_age_band(age: Optional[float]) -> str:
    """Map a continuous age to the nearest age band."""
    if age is None:
        return "all"
    for band, lo, hi in AGE_BANDS:
        if lo <= age <= hi:
            return band
    # If age is outside all bands, return "all"
    return "all"


def resolve_stratum(
    db, biomarker_id: int, age: Optional[float], sex: Optional[str]
) -> Tuple[HRFunction, str, bool]:
    """
    Resolve the best-matching HRFunction stratum for a given (age, sex).
    
    Returns (hr_function, stratum_name, is_specific) where is_specific
    indicates whether the curve is truly stratum-specific (not a fallback).
    
    Priority:
    1. Exact sex + age_band match
    2. Sex match, age_band='all'
    3. age_band match, sex='all'
    4. (all, all) fallback
    """
    age_band = resolve_age_band(age)
    sex_norm = sex.upper() if sex and sex != "all" else "all"
    
    # Try exact match
    candidates = [
        (sex_norm, age_band),
        (sex_norm, "all"),
        ("all", age_band),
        ("all", "all"),
    ]
    
    for s, ab in candidates:
        hf = (
            db.query(HRFunction)
            .filter(
                HRFunction.biomarker_id == biomarker_id,
                HRFunction.sex == s,
                HRFunction.age_band == ab,
            )
            .first()
        )
        if hf:
            is_specific = (s != "all" or ab != "all")
            stratum_name = f"{s}_{ab}"
            return hf, stratum_name, is_specific
    
    raise ValueError(f"No HRFunction found for biomarker_id={biomarker_id}")


def evaluate_hr_function(hf: HRFunction, value: float) -> float:
    """
    Evaluate the parametric HR function at a single value.
    Returns HR (not log-HR).
    """
    params = hf.parameters or {}
    fit_type = hf.fit_type
    ref = hf.reference_value
    
    if fit_type in ("log_log", "log_linear_per_sd", "log_linear_per_unit", "linear_log"):
        # log(HR) = beta * (log(x) - log(x_ref))  or  beta * (x - x_ref) / sd
        beta = params.get("beta", 0.0)
        sd = params.get("sd", 1.0)
        
        if fit_type in ("log_log",):
            if value <= 0 or ref <= 0:
                return 1.0
            log_hr = beta * (math.log(value) - math.log(ref))
        else:
            # linear in value, scaled by SD
            log_hr = beta * (value - ref) / sd if sd != 0 else 0.0
        
        return math.exp(log_hr)
    
    elif fit_type in ("quadratic_u_shaped", "quadratic"):
        # log(HR) = a * (x - x_opt)^2
        a = params.get("a", 0.0)
        x_opt = params.get("x_opt", ref)
        log_hr = a * (value - x_opt) ** 2
        return math.exp(log_hr)
    
    elif fit_type in ("piecewise_linear", "piecewise"):
        # Piecewise linear: segments defined by breakpoints
        segments = params.get("segments", [])
        if not segments:
            return 1.0
        # Find the segment containing value
        for seg in segments:
            x0 = seg.get("x0", 0)
            x1 = seg.get("x1", float("inf"))
            hr0 = seg.get("hr0", 1.0)
            hr1 = seg.get("hr1", 1.0)
            if x0 <= value <= x1:
                if x1 == x0:
                    return hr0
                t = (value - x0) / (x1 - x0)
                # Linear interpolation in log-space
                log_hr = (1 - t) * math.log(hr0) + t * math.log(hr1)
                return math.exp(log_hr)
        # Outside all segments, return 1.0
        return 1.0
    
    else:
        # Unknown fit type, return 1.0
        return 1.0


def compute_curve_grid(
    hf: HRFunction,
    n_points: int = GRID_SIZE,
) -> List[Dict[str, float]]:
    """
    Evaluate the HR function on a uniform grid from domain_min to domain_max.
    Returns list of {value, hr} dicts.
    """
    domain_min = hf.domain_min
    domain_max = hf.domain_max
    
    if domain_max <= domain_min:
        return []
    
    values = np.linspace(domain_min, domain_max, n_points)
    points = []
    for v in values:
        hr = evaluate_hr_function(hf, float(v))
        points.append({"value": round(float(v), 4), "hr": round(hr, 6)})
    
    return points


def get_hazard_curve(
    db,
    biomarker: Biomarker,
    age: Optional[float] = None,
    sex: Optional[str] = None,
    n_points: int = GRID_SIZE,
) -> Dict[str, Any]:
    """
    Main entry point: resolve stratum, compute curve grid, return response dict.
    
    Args:
        db: SQLAlchemy session
        biomarker: Biomarker ORM object
        age: Optional continuous age (e.g., 45.0)
        sex: Optional sex ('M' or 'F')
        n_points: Number of grid points (default 100)
    
    Returns:
        Dict with curve points, stratum info, and specificity flag.
    """
    hf, stratum_name, is_specific = resolve_stratum(
        db, biomarker.id, age, sex
    )
    
    points = compute_curve_grid(hf, n_points)
    
    # Determine curve_specificity label
    if is_specific:
        curve_specificity = "stratum_specific"
    else:
        curve_specificity = "population_fallback"
    
    return {
        "biomarker_id": biomarker.id,
        "biomarker_name": biomarker.name,
        "units": biomarker.units,
        "age": age,
        "sex": sex,
        "age_band": resolve_age_band(age),
        "stratum": stratum_name,
        "curve_specificity": curve_specificity,
        "fit_type": hf.fit_type,
        "shape": hf.shape,
        "reference_value": hf.reference_value,
        "domain_min": hf.domain_min,
        "domain_max": hf.domain_max,
        "nadir_value": hf.nadir_value,
        "points": points,
    }
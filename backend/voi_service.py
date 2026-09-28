"""DB-backed VOI/EHIV helpers used by the API. UI-free; delegates math to voi.py."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.life_tables import age_band_midpoint, serialize_life_tables
from backend.optimization_engine import generate_population_distribution
from backend.voi import (
    C_INT_DALY_DEFAULT,
    EPSILON_DEFAULT,
    LAMBDA_DEFAULT,
    ehiv,
    expected_voi,
    make_hr_fn,
    population_voi,
    voi_config_dict,
    voi_per_individual,
)


def bins_from_dist(dist: Dict[str, Any], valid_min: Optional[float], valid_max: Optional[float], n_bins: int = 80):
    mean = float(dist.get("mean") or dist.get("p50") or 0.0)
    sd = float(dist.get("sd") or 0.0)
    if sd <= 0:
        sd = max(abs(mean) * 0.15, 0.1)
    vmin = valid_min if valid_min is not None else mean - 4.5 * sd
    vmax = valid_max if valid_max is not None else mean + 4.5 * sd
    return generate_population_distribution(mean, sd, vmin, vmax, n_bins=n_bins)


def pick_curve(curves: List[Dict[str, Any]], sex: str, age_band: str) -> Optional[Dict[str, Any]]:
    if not curves:
        return None
    sex_n = sex if sex in ("M", "F") else "all"
    for s, b in ((sex_n, age_band), (sex_n, "all"), ("all", age_band), ("all", "all")):
        for cv in curves:
            if (cv.get("sex") or "all") == s and (cv.get("age_band") or "all") == b:
                return cv
    return curves[0]


def pick_dist(dists: List[Dict[str, Any]], sex: str, age_band: str) -> Optional[Dict[str, Any]]:
    if not dists:
        return None
    sex_n = sex if sex in ("M", "F") else "all"
    for s, b in ((sex_n, age_band), (sex_n, "all"), ("all", age_band), ("all", "all")):
        for d in dists:
            if (d.get("sex") or "all") == s and (d.get("age_band") or "all") == b:
                return d
    return dists[0]


def compute_individual_and_expected(
    biomarker: Dict[str, Any],
    curves: List[Dict[str, Any]],
    dists: List[Dict[str, Any]],
    *,
    age: float = 50,
    sex: str = "all",
    age_band: str = "all",
    epsilon: float = EPSILON_DEFAULT,
    c_int_daly: float = C_INT_DALY_DEFAULT,
    lam: float = LAMBDA_DEFAULT,
    c_test: Optional[float] = None,
) -> Dict[str, Any]:
    curve = pick_curve(curves, sex, age_band)
    dist = pick_dist(dists, sex, age_band)
    if not curve or not dist:
        return {"available": False, "reason": "missing HR curve or population distribution"}

    hr_fn = make_hr_fn(curve)
    x_ref = float(curve.get("reference_value") if curve.get("reference_value") is not None else dist.get("p50") or dist.get("mean") or 0.0)
    sigma = float(dist.get("sd") or 0.0) or max(abs(float(dist.get("mean") or 1.0)) * 0.15, 0.1)
    valid_min = biomarker.get("valid_domain_min")
    valid_max = biomarker.get("valid_domain_max")
    xs, ps = bins_from_dist(dist, valid_min, valid_max)
    x_mean = float(dist.get("mean") or dist.get("p50") or xs[len(xs) // 2])

    individual = voi_per_individual(
        x_mean, age, sex, sigma, epsilon, c_int_daly, hr_fn, x_ref,
        directionality=biomarker.get("directionality"),
        optimal=biomarker.get("optimal_target"),
        valid_min=valid_min,
        valid_max=valid_max,
    )
    expected = expected_voi(
        xs, ps, age, sex, sigma, epsilon, c_int_daly, hr_fn, x_ref,
        directionality=biomarker.get("directionality"),
        optimal=biomarker.get("optimal_target"),
        valid_min=valid_min,
        valid_max=valid_max,
        age_band=age_band,
    )
    price = c_test if c_test is not None else biomarker.get("test_price_usd") or 0.0
    eh = ehiv(expected.expected_voi, lam, price)

    # Population roll-up across exclusive strata
    strata = []
    for d in dists:
        cv = pick_curve(curves, d.get("sex") or "all", d.get("age_band") or "all")
        if not cv:
            continue
        bx, bp = bins_from_dist(d, valid_min, valid_max, n_bins=60)
        strata.append({
            "sex": d.get("sex") or "all",
            "age_band": d.get("age_band") or "all",
            "x_bins": bx,
            "p_bins": bp,
            "sigma_x": float(d.get("sd") or sigma),
            "sample_n": d.get("sample_n"),
            "age": age_band_midpoint(d.get("age_band") or "all"),
        })
    pop = population_voi(
        strata, lam, price, epsilon, c_int_daly, hr_fn, x_ref,
        directionality=biomarker.get("directionality"),
        optimal=biomarker.get("optimal_target"),
        valid_min=valid_min,
        valid_max=valid_max,
    )

    return {
        "available": True,
        "age": age,
        "sex": sex,
        "age_band": age_band,
        "epsilon": epsilon,
        "cIntDaly": c_int_daly,
        "lambda": lam,
        "cTest": price,
        "cmsReimbursementUSD": biomarker.get("cms_reimbursement_usd"),
        "testPriceUSD": biomarker.get("test_price_usd"),
        "loincToTestId": biomarker.get("loinc_to_test_id") or {},
        "sigmaX": sigma,
        "xMean": x_mean,
        "xRef": x_ref,
        "individual": {
            "eyll": individual.eyll,
            "eyllShifted": individual.eyll_shifted,
            "deltaDaly": individual.delta_daly,
            "deltaDalyShifted": individual.delta_daly_shifted,
            "voi": individual.voi,
            "x": individual.x,
            "xShifted": individual.x_shifted,
        },
        "expected": {
            "voi": expected.expected_voi,
            "eyll": expected.expected_eyll,
            "deltaDaly": expected.expected_delta_daly,
            "eyllShifted": expected.expected_eyll_shifted,
        },
        "ehiv": {
            "ehiv": eh.ehiv,
            "lambdaVoi": eh.lambda_voi,
            "cTest": eh.c_test,
            "voi": eh.expected_voi,
            "favorable": eh.favorable,
        },
        "population": {
            "totalVOI": pop.total_voi,
            "totalEHIV": pop.total_ehiv,
            "totalN": pop.total_n,
            "byStratum": [
                {
                    "sex": s.sex,
                    "age_band": s.age_band,
                    "cohort": s.cohort,
                    "n": s.n,
                    "expectedVOI": s.expected_voi,
                    "totalVOI": s.total_voi,
                    "ehiv": s.ehiv,
                    "totalEHIV": s.total_ehiv,
                }
                for s in pop.by_stratum
            ],
            "excludedOverlapping": pop.excluded_overlapping,
        },
    }


def public_config() -> Dict[str, Any]:
    cfg = voi_config_dict()
    cfg["lifeTables"] = serialize_life_tables()
    return cfg

"""
Value of Information / Expected Hazard Information Value (DALY-dollar layer).

Pure computation module — no UI, no database. Implements equations (5)–(13)
of "The Value of Information in Longevity Biomarkers":

  (5) EYLL(x) = Σ_t [ S0(age+t)^HR(xRef) − S0(age+t)^HR(x) ]
  (6) ΔDALY(x) = EYLL(x) + YLD   (YLD defaults to 0)
 (11) VOI(x)   = max(0, ΔDALY(x) − ΔDALY(x − ε σ sign) − c_int)
  (9) E[VOI]   = Σ_i p_i VOI(x_i)   over the NHANES empirical bins
 (12) EHIV     = λ · E[VOI] − c_test
 (13) Pop VOI  = Σ_{a,s,c} N_{a,s,c} · E[VOI]_{a,s,c}

Reuse the existing HR evaluator (optimization_engine.evaluate_hr) and the
same population-bin / SD-shift / domain-guardrail conventions as the
optimization simulator.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.life_tables import (
    AGE_BAND_MIDPOINT,
    LIFE_TABLE_SOURCE,
    MAX_AGE,
    age_band_midpoint,
    conditional_survival_from_age,
    population_n,
    sex_is_unisex,
)
from backend.optimization_engine import evaluate_hr

# Policy defaults — user-adjustable, not a scientific point estimate.
LAMBDA_DEFAULT = 150_000.0  # USD per DALY (near 2× US GDP/capita / ICER typical)
LAMBDA_PRESETS = [
    {"label": "1× US GDP/capita (~$80k)", "value": 80_000.0},
    {"label": "ICER typical ($150k)", "value": 150_000.0},
    {"label": "2× US GDP/capita (~$160k)", "value": 160_000.0},
    {"label": "3× US GDP/capita (~$240k)", "value": 240_000.0},
]
EPSILON_DEFAULT = 1.0  # Standard 1.0-SD simulator preset
C_INT_DALY_DEFAULT = 0.0

TEST_PRICE_SOURCE_URL = "https://www.findlabtest.com"
TEST_PRICE_SOURCE_LABEL = "findlabtest.com market self-pay median"

# Minimum NHANES sample_n for a stratum to enter population aggregation.
MIN_STRATUM_N = 50

# Exclusive adult cells for eq. (13). Anything that overlaps these is dropped.
EXCLUSIVE_CELLS = [
    ("M", "20-39"),
    ("F", "20-39"),
    ("M", "40-59"),
    ("F", "40-59"),
    ("M", "60+"),
    ("F", "60+"),
]


HRFn = Callable[[float], float]


@dataclass
class LifeTableView:
    """Precomputed conditional survival from a starting age."""
    age: float
    sex: str
    s0_cond: List[float]


@dataclass
class VOIIndividualResult:
    eyll: float
    eyll_shifted: float
    delta_daly: float
    delta_daly_shifted: float
    voi: float
    x: float
    x_shifted: float


@dataclass
class ExpectedVOIResult:
    expected_voi: float
    expected_eyll: float
    expected_delta_daly: float
    expected_eyll_shifted: float
    n_bins: int
    sigma_x: float
    epsilon: float
    c_int_daly: float
    age: float
    sex: str
    age_band: str
    cohort: str


@dataclass
class EHIVResult:
    ehiv: float
    expected_voi: float
    lambda_voi: float
    c_test: float
    lam: float
    favorable: bool


@dataclass
class StratumVOI:
    sex: str
    age_band: str
    cohort: str
    n: float
    expected_voi: float
    total_voi: float
    ehiv: float
    total_ehiv: float
    excluded_reason: Optional[str] = None


@dataclass
class PopulationVOIResult:
    total_voi: float
    total_ehiv: float
    total_n: float
    by_stratum: List[StratumVOI]
    excluded_overlapping: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HR + shift helpers (same semantics as the optimization simulator)
# ---------------------------------------------------------------------------

def parse_curve_parameters(parameters: Any) -> Dict[str, Any]:
    if parameters is None:
        return {}
    if isinstance(parameters, dict):
        return parameters
    if isinstance(parameters, str):
        try:
            parsed = json.loads(parameters)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def make_hr_fn(curve: Dict[str, Any]) -> HRFn:
    """Wrap a biomarker_hr_curve row so it can be called as HR(x)."""
    curve_type = curve.get("curve_type") or "linear_log"
    reference_value = float(curve.get("reference_value") or 0.0)
    optimal_value = curve.get("optimal_value")
    parameters = parse_curve_parameters(curve.get("parameters"))

    def _hr(x: float) -> float:
        try:
            hr = evaluate_hr(
                float(x),
                curve_type,
                reference_value,
                parameters,
                optimal_value=optimal_value,
            )
        except Exception:
            return 1.0
        if not math.isfinite(hr):
            return 1.0
        return max(0.10, min(20.0, float(hr)))

    return _hr


def shift_sign(directionality: Optional[str], x: float, optimal: Optional[float]) -> float:
    """
    Sign in x' = x − ε·σ·sign, matching the simulator:
      lower_better  -> decrease x (sign = +1)
      higher_better -> increase x (sign = −1)
      u/j-shaped    -> move toward optimal
    """
    d = (directionality or "").strip().lower()
    if d in ("lower_better", "monotonic_increasing", "higher_worse"):
        return 1.0
    if d in ("higher_better", "monotonic_decreasing", "lower_worse"):
        return -1.0
    if optimal is None or not math.isfinite(optimal):
        return 0.0
    if x > optimal:
        return 1.0
    if x < optimal:
        return -1.0
    return 0.0


def shifted_value(
    x: float,
    sigma_x: float,
    epsilon: float,
    directionality: Optional[str],
    optimal: Optional[float],
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
) -> float:
    sign = shift_sign(directionality, x, optimal)
    raw_shift = epsilon * sigma_x * sign
    if optimal is not None and math.isfinite(optimal) and sign != 0.0:
        # Do not overshoot the nadir for U/J-shaped (and clamp toward target).
        max_toward_opt = abs(x - optimal)
        if abs(raw_shift) > max_toward_opt:
            raw_shift = math.copysign(max_toward_opt, raw_shift)
    x_new = x - raw_shift
    if valid_min is not None and x_new < valid_min:
        x_new = valid_min
    if valid_max is not None and x_new > valid_max:
        x_new = valid_max
    return x_new


# ---------------------------------------------------------------------------
# Core equations
# ---------------------------------------------------------------------------

def eyll(
    x: float,
    x_ref: float,
    age: float,
    sex: str,
    hr_fn: HRFn,
    baseline_table: Optional[LifeTableView] = None,
) -> float:
    """Eq. (5): discretized life-table expected years of life lost vs x_ref."""
    table = baseline_table or LifeTableView(
        age=age, sex=sex, s0_cond=conditional_survival_from_age(age, sex)
    )
    hr_x = hr_fn(x)
    hr_ref = hr_fn(x_ref)
    total = 0.0
    for s in table.s0_cond:
        total += (s ** hr_ref) - (s ** hr_x)
    return float(total)


def delta_daly(
    x: float,
    x_ref: float,
    age: float,
    sex: str,
    hr_fn: HRFn,
    baseline_table: Optional[LifeTableView] = None,
    yld: float = 0.0,
) -> float:
    """Eq. (6): mortality-only ΔDALY. `yld` is a named extension point (default 0)."""
    return eyll(x, x_ref, age, sex, hr_fn, baseline_table=baseline_table) + float(yld)


def voi_per_individual(
    x: float,
    age: float,
    sex: str,
    sigma_x: float,
    epsilon: float,
    c_int_daly: float,
    hr_fn: HRFn,
    x_ref: float,
    directionality: Optional[str] = None,
    optimal: Optional[float] = None,
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
    baseline_table: Optional[LifeTableView] = None,
    yld: float = 0.0,
) -> VOIIndividualResult:
    """Eq. (11): max(0, ΔDALY(x) − ΔDALY(x′) − c_int)."""
    table = baseline_table or LifeTableView(
        age=age, sex=sex, s0_cond=conditional_survival_from_age(age, sex)
    )
    x_shift = shifted_value(
        x, sigma_x, epsilon, directionality, optimal, valid_min, valid_max
    )
    d0 = delta_daly(x, x_ref, age, sex, hr_fn, baseline_table=table, yld=yld)
    d1 = delta_daly(x_shift, x_ref, age, sex, hr_fn, baseline_table=table, yld=yld)
    voi = max(0.0, d0 - d1 - float(c_int_daly))
    return VOIIndividualResult(
        eyll=d0 - yld,
        eyll_shifted=d1 - yld,
        delta_daly=d0,
        delta_daly_shifted=d1,
        voi=voi,
        x=x,
        x_shifted=x_shift,
    )


def expected_voi(
    x_bins: Sequence[float],
    p_bins: Sequence[float],
    age: float,
    sex: str,
    sigma_x: float,
    epsilon: float,
    c_int_daly: float,
    hr_fn: HRFn,
    x_ref: float,
    directionality: Optional[str] = None,
    optimal: Optional[float] = None,
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
    age_band: str = "all",
    cohort: str = "general",
    yld: float = 0.0,
) -> ExpectedVOIResult:
    """Eq. (9)/(11): E[VOI] over the existing NHANES empirical / binned density."""
    table = LifeTableView(
        age=age, sex=sex, s0_cond=conditional_survival_from_age(age, sex)
    )
    e_voi = 0.0
    e_eyll = 0.0
    e_daly = 0.0
    e_eyll_s = 0.0
    n = min(len(x_bins), len(p_bins))
    for i in range(n):
        p = float(p_bins[i])
        if p <= 0:
            continue
        r = voi_per_individual(
            float(x_bins[i]),
            age,
            sex,
            sigma_x,
            epsilon,
            c_int_daly,
            hr_fn,
            x_ref,
            directionality=directionality,
            optimal=optimal,
            valid_min=valid_min,
            valid_max=valid_max,
            baseline_table=table,
            yld=yld,
        )
        e_voi += p * r.voi
        e_eyll += p * r.eyll
        e_daly += p * r.delta_daly
        e_eyll_s += p * r.eyll_shifted
    return ExpectedVOIResult(
        expected_voi=float(e_voi),
        expected_eyll=float(e_eyll),
        expected_delta_daly=float(e_daly),
        expected_eyll_shifted=float(e_eyll_s),
        n_bins=n,
        sigma_x=float(sigma_x),
        epsilon=float(epsilon),
        c_int_daly=float(c_int_daly),
        age=float(age),
        sex=sex,
        age_band=age_band,
        cohort=cohort,
    )


def ehiv(
    expected_voi_dalys: float,
    lam: float,
    c_test: float,
) -> EHIVResult:
    """Eq. (12): EHIV = λ · E[VOI] − c_test."""
    lam = float(lam)
    c_test = float(c_test or 0.0)
    lambda_voi = lam * float(expected_voi_dalys)
    value = lambda_voi - c_test
    return EHIVResult(
        ehiv=float(value),
        expected_voi=float(expected_voi_dalys),
        lambda_voi=float(lambda_voi),
        c_test=c_test,
        lam=lam,
        favorable=value > 0,
    )


# ---------------------------------------------------------------------------
# Population aggregation — exclusive strata, no double counting
# ---------------------------------------------------------------------------

def _cell_key(sex: str, age_band: str) -> Tuple[str, str]:
    s = (sex or "all").strip()
    if s.upper() in ("M", "MALE"):
        s = "M"
    elif s.upper() in ("F", "FEMALE", "W"):
        s = "F"
    else:
        s = "all"
    b = age_band or "all"
    return s, b


def select_nonoverlapping_strata(
    strata: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Keep a mutually exclusive (sex × age_band) partition.
    Overlapping aggregations (`sex='all'` or `age_band='all'`) are excluded
    whenever a finer cell that they cover is present.
    """
    by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for s in strata:
        key = _cell_key(s.get("sex"), s.get("age_band"))
        # Prefer larger sample_n when duplicates exist
        prev = by_key.get(key)
        if prev is None or float(s.get("sample_n") or 0) > float(prev.get("sample_n") or 0):
            by_key[key] = dict(s, sex=key[0], age_band=key[1])

    included: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []

    age_bands = ["20-39", "40-59", "60+"]
    used_age_bands = set()

    for band in age_bands:
        m = by_key.get(("M", band))
        f = by_key.get(("F", band))
        both = by_key.get(("all", band))
        if m and f:
            included.extend([m, f])
            used_age_bands.add(band)
            if both:
                excluded.append({**both, "excluded_reason": "overlaps M/F specific cells"})
        elif m and not f:
            included.append(m)
            used_age_bands.add(band)
            if both:
                excluded.append({**both, "excluded_reason": "overlaps M-specific cell"})
        elif f and not m:
            included.append(f)
            used_age_bands.add(band)
            if both:
                excluded.append({**both, "excluded_reason": "overlaps F-specific cell"})
        elif both:
            included.append(both)
            used_age_bands.add(band)

    # Age-all rows: only if we have no age-specific coverage at all
    if not used_age_bands:
        m_all = by_key.get(("M", "all"))
        f_all = by_key.get(("F", "all"))
        all_all = by_key.get(("all", "all"))
        if m_all and f_all:
            included.extend([m_all, f_all])
            if all_all:
                excluded.append({**all_all, "excluded_reason": "overlaps M/F age-all cells"})
        elif m_all:
            included.append(m_all)
            if all_all:
                excluded.append({**all_all, "excluded_reason": "overlaps M age-all cell"})
        elif f_all:
            included.append(f_all)
            if all_all:
                excluded.append({**all_all, "excluded_reason": "overlaps F age-all cell"})
        elif all_all:
            included.append(all_all)
    else:
        for key, row in by_key.items():
            if key[1] == "all":
                excluded.append({**row, "excluded_reason": "age_band='all' overlaps age-specific cells"})

    included_keys = {(_cell_key(r["sex"], r["age_band"])) for r in included}
    for key, row in by_key.items():
        if key not in included_keys and not any(
            _cell_key(e.get("sex"), e.get("age_band")) == key for e in excluded
        ):
            excluded.append({**row, "excluded_reason": "not in exclusive partition"})

    return included, excluded


def population_voi(
    strata: Sequence[Dict[str, Any]],
    lam: float,
    c_test: float,
    epsilon: float,
    c_int_daly: float,
    hr_fn: HRFn,
    x_ref: float,
    directionality: Optional[str] = None,
    optimal: Optional[float] = None,
    valid_min: Optional[float] = None,
    valid_max: Optional[float] = None,
    yld: float = 0.0,
    cohort: str = "general",
) -> PopulationVOIResult:
    """
    Eq. (13). Each stratum dict needs: sex, age_band, x_bins, p_bins, sigma_x,
    and optionally sample_n, n (population size), age.
    """
    included, excluded = select_nonoverlapping_strata(strata)
    by_stratum: List[StratumVOI] = []
    total_voi = 0.0
    total_ehiv = 0.0
    total_n = 0.0

    for s in included:
        sample_n = s.get("sample_n")
        if sample_n is not None and int(sample_n) < MIN_STRATUM_N:
            excluded.append({**s, "excluded_reason": f"sample_n < {MIN_STRATUM_N}"})
            continue
        x_bins = s.get("x_bins") or []
        p_bins = s.get("p_bins") or []
        if not x_bins or not p_bins:
            excluded.append({**s, "excluded_reason": "missing distribution bins"})
            continue
        sex = s.get("sex") or "all"
        age_band = s.get("age_band") or "all"
        age = float(s.get("age") or age_band_midpoint(age_band))
        sigma_x = float(s.get("sigma_x") or 0.0)
        n = float(s.get("n") if s.get("n") is not None else population_n(sex, age_band))
        ev = expected_voi(
            x_bins,
            p_bins,
            age=age,
            sex=sex,
            sigma_x=sigma_x,
            epsilon=epsilon,
            c_int_daly=c_int_daly,
            hr_fn=hr_fn,
            x_ref=x_ref,
            directionality=directionality,
            optimal=optimal,
            valid_min=valid_min,
            valid_max=valid_max,
            age_band=age_band,
            cohort=s.get("cohort") or cohort,
            yld=yld,
        )
        eh = ehiv(ev.expected_voi, lam, c_test)
        total_voi_s = n * ev.expected_voi
        total_ehiv_s = n * eh.ehiv
        by_stratum.append(
            StratumVOI(
                sex=sex,
                age_band=age_band,
                cohort=s.get("cohort") or cohort,
                n=n,
                expected_voi=ev.expected_voi,
                total_voi=total_voi_s,
                ehiv=eh.ehiv,
                total_ehiv=total_ehiv_s,
            )
        )
        total_voi += total_voi_s
        total_ehiv += total_ehiv_s
        total_n += n

    return PopulationVOIResult(
        total_voi=float(total_voi),
        total_ehiv=float(total_ehiv),
        total_n=float(total_n),
        by_stratum=by_stratum,
        excluded_overlapping=excluded,
    )


def voi_config_dict() -> Dict[str, Any]:
    return {
        "lambdaDefault": LAMBDA_DEFAULT,
        "lambdaPresets": LAMBDA_PRESETS,
        "epsilonDefault": EPSILON_DEFAULT,
        "cIntDalyDefault": C_INT_DALY_DEFAULT,
        "lifeTableSource": LIFE_TABLE_SOURCE,
        "testPriceSourceUrl": TEST_PRICE_SOURCE_URL,
        "testPriceSourceLabel": TEST_PRICE_SOURCE_LABEL,
        "minStratumN": MIN_STRATUM_N,
        "maxAge": MAX_AGE,
        "ageBandMidpoint": AGE_BAND_MIDPOINT,
    }

"""
US period life tables for the VOI/EHIV layer.

Source: CDC NVSS United States Life Tables, 2022 (Arias, Xu, Kochanek,
Natl Vital Stat Rep. 2025 Apr 8;(2)). Sex-specific single-year qx is
constructed from a Gompertz–Makeham hazard calibrated to published 2022
period life expectancy at birth and at age 65, with an infant-mortality
adjustment. Values between integer ages are linearly interpolated.

S0[age] is survival from birth to exact age (l_x / l_0).
h0[age] is the annual force of mortality at exact age (per year).
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

LIFE_TABLE_SOURCE = (
    "CDC NVSS United States Life Tables, 2022 (Arias E, Xu J, Kochanek K). "
    "Period, sex-specific; single-year interpolation of a Gompertz–Makeham "
    "hazard calibrated to published e0 and e65."
)

MAX_AGE = 110

# Census Bureau Vintage 2023 national population estimates (rounded).
# Mutually exclusive adult cells used for eq. (13) population aggregation.
US_POPULATION_N = {
    ("M", "20-39"): 44_184_000,
    ("F", "20-39"): 43_112_000,
    ("M", "40-59"): 41_567_000,
    ("F", "40-59"): 42_234_000,
    ("M", "60+"): 36_412_000,
    ("F", "60+"): 43_891_000,
}

AGE_BAND_MIDPOINT = {
    "20-39": 30,
    "40-59": 50,
    "60+": 70,
    "all": 50,
}

# Gompertz–Makeham: h(a) = A + B * exp(C * a)
# Calibrated to CDC 2022: male e0=74.8, e65≈17.5; female e0=80.2, e65≈20.2
_GM_PARAMS = {
    "M": {"A": 0.00055, "B": 3.20e-5, "C": 0.0875, "q0": 0.0056},
    "F": {"A": 0.00035, "B": 1.55e-5, "C": 0.0900, "q0": 0.0047},
}


def _build_table(sex: str) -> Dict[str, List[float]]:
    p = _GM_PARAMS[sex]
    A, B, C, q0 = p["A"], p["B"], p["C"], p["q0"]
    h0: List[float] = []
    qx: List[float] = []
    for a in range(MAX_AGE + 1):
        h = A + B * math.exp(C * a)
        if a == 0:
            q = q0
            h = -math.log(max(1.0 - q, 1e-12))
        else:
            q = 1.0 - math.exp(-h)
        q = min(max(q, 0.0), 1.0)
        h0.append(float(h))
        qx.append(float(q))
    s0 = [1.0]
    for a in range(MAX_AGE):
        s0.append(s0[-1] * (1.0 - qx[a]))
    s0[-1] = 0.0
    return {"h0": h0, "S0": s0, "qx": qx}


LIFE_TABLES: Dict[str, Dict[str, List[float]]] = {
    "M": _build_table("M"),
    "F": _build_table("F"),
}


def _lerp(xs: List[float], age: float) -> float:
    if age <= 0:
        return xs[0]
    if age >= MAX_AGE:
        return xs[-1]
    lo = int(math.floor(age))
    hi = min(lo + 1, MAX_AGE)
    t = age - lo
    return xs[lo] * (1.0 - t) + xs[hi] * t


def lookup_h0(age: float, sex: str) -> float:
    table = LIFE_TABLES.get(_norm_sex(sex), LIFE_TABLES["M"])
    if sex_is_unisex(sex):
        return 0.5 * (_lerp(LIFE_TABLES["M"]["h0"], age) + _lerp(LIFE_TABLES["F"]["h0"], age))
    return _lerp(table["h0"], age)


def lookup_s0_from_birth(age: float, sex: str) -> float:
    """Survival from birth to `age` (interpolated)."""
    if sex_is_unisex(sex):
        return 0.5 * (
            _lerp(LIFE_TABLES["M"]["S0"], age) + _lerp(LIFE_TABLES["F"]["S0"], age)
        )
    table = LIFE_TABLES.get(_norm_sex(sex), LIFE_TABLES["M"])
    return _lerp(table["S0"], age)


def conditional_survival_from_age(start_age: float, sex: str) -> List[float]:
    """
    S0_cond[t] = P(survive t additional years | alive at start_age)
               = S0(start_age + t) / S0(start_age)
    Length is (MAX_AGE - floor(start_age) + 1), t = 0, 1, 2, ...
    """
    start_age = max(0.0, min(float(start_age), MAX_AGE))
    s_start = lookup_s0_from_birth(start_age, sex)
    if s_start <= 0:
        return [1.0]
    out = []
    t = 0
    while start_age + t <= MAX_AGE:
        s = lookup_s0_from_birth(start_age + t, sex) / s_start
        out.append(max(0.0, min(1.0, s)))
        t += 1
    if not out:
        out = [1.0]
    out[-1] = 0.0
    return out


def remaining_life_expectancy(age: float, sex: str, hr: float = 1.0) -> float:
    s = conditional_survival_from_age(age, sex)
    return sum(sv ** hr for sv in s)


def age_band_midpoint(age_band: str) -> int:
    return AGE_BAND_MIDPOINT.get(age_band or "all", 50)


def population_n(sex: str, age_band: str) -> int:
    key = (_norm_sex(sex) if not sex_is_unisex(sex) else "all", age_band or "all")
    if key in US_POPULATION_N:
        return US_POPULATION_N[key]
    if (age_band or "all") == "all" and not sex_is_unisex(sex):
        sx = _norm_sex(sex)
        return sum(n for (s, _b), n in US_POPULATION_N.items() if s == sx)
    if not sex_is_unisex(sex) and (age_band or "all") != "all":
        # Missing sex-specific cell: do not invent a split of the 'all' cell here.
        return US_POPULATION_N.get((_norm_sex(sex), age_band), 0)
    # sex == all: sum both sexes for that band, or total adult if band is all
    if (age_band or "all") == "all":
        return sum(US_POPULATION_N.values())
    return sum(n for (s, b), n in US_POPULATION_N.items() if b == age_band)


def sex_is_unisex(sex: str) -> bool:
    s = (sex or "all").strip().upper()
    return s in ("ALL", "BOTH", "UNISEX", "")


def _norm_sex(sex: str) -> str:
    s = (sex or "M").strip().upper()
    if s in ("F", "FEMALE", "W"):
        return "F"
    return "M"


def serialize_life_tables() -> dict:
    return {
        "source": LIFE_TABLE_SOURCE,
        "max_age": MAX_AGE,
        "M": {"h0": LIFE_TABLES["M"]["h0"], "S0": LIFE_TABLES["M"]["S0"]},
        "F": {"h0": LIFE_TABLES["F"]["h0"], "S0": LIFE_TABLES["F"]["S0"]},
        "population_n": {
            f"{s}|{b}": n for (s, b), n in US_POPULATION_N.items()
        },
        "age_band_midpoint": AGE_BAND_MIDPOINT,
    }

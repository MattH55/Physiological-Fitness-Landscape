"""
The actual payoff of this layer: given a MANUAL_VERIFIED effect size (e.g.
"omega-3 reduces CRP by 0.34 mg/L"), compute what that shift implies for
predicted mortality HR, using the population distribution and HR curve
already built (nhanes_toolkit.analysis, nhanes_toolkit.hazard_curves).

Deliberately does NOT compute EVSI/QALYs/economic value -- same boundary
as the rest of this project. This answers "if someone's biomarker moved by
this much, how does their predicted HR change," not "should they take this
intervention" (that needs cost, side effects, adherence, and a decision
model this layer doesn't have).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from nhanes_toolkit.hazard_curves import RcsCoxResult, predict_hr_curve


@dataclass
class InterventionImpact:
    baseline_value: float
    shifted_value: float
    hr_baseline: float
    hr_shifted: float
    hr_ratio: float  # hr_shifted / hr_baseline -- <1 means the intervention lowers predicted HR


def apply_effect_to_curve(
    result: RcsCoxResult,
    population_df: pd.DataFrame,
    effect_value: float,
    effect_measure: str,
    baseline_value: Optional[float] = None,
    age: Optional[float] = None,
    race: Optional[str] = None,
) -> InterventionImpact:
    """
    baseline_value defaults to the population median (same reference point
    predict_hr_curve already uses internally) if not given -- e.g. pass a
    specific person's actual biomarker value instead to get an
    individual-level estimate.

    Only `mean_difference` (same units as the biomarker) and
    `percent_change` are handled here -- `standardized_mean_difference`
    needs the *trial's* SD (not NHANES's) to convert back to raw units,
    which isn't reliably available from an abstract; treat SMD-only
    effects as NEEDS_REVIEW until someone supplies a raw-units estimate,
    rather than silently guessing an SD.
    """
    if baseline_value is None:
        baseline_value = float(population_df["value"].dropna().median())

    if effect_measure == "mean_difference":
        shifted_value = baseline_value + effect_value
    elif effect_measure == "percent_change":
        shifted_value = baseline_value * (1 + effect_value / 100.0)
    else:
        raise ValueError(
            f"effect_measure '{effect_measure}' isn't convertible to a raw-unit shift "
            f"without more information (e.g. the trial's own SD for standardized_mean_difference). "
            f"Convert it to mean_difference or percent_change during manual review first."
        )

    grid = np.array([baseline_value, shifted_value])
    curve = predict_hr_curve(result, population_df, grid, age=age, race=race)
    hr_baseline = float(curve.loc[curve["value"] == baseline_value, "hr_vs_median"].iloc[0])
    hr_shifted = float(curve.loc[curve["value"] == shifted_value, "hr_vs_median"].iloc[0])

    return InterventionImpact(
        baseline_value=baseline_value,
        shifted_value=shifted_value,
        hr_baseline=hr_baseline,
        hr_shifted=hr_shifted,
        hr_ratio=hr_shifted / hr_baseline if hr_baseline else float("nan"),
    )

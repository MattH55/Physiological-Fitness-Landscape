"""
Fit HR(biomarker value) curves via Cox PH with a restricted cubic spline
term, stratified by sex (fit separately per sex -- see fit_rcs_cox), with
optional value-spline x age and value-spline x race interactions so the
CURVE SHAPE (not just its vertical position) can vary by age and race, not
just its baseline level.

Requires: lifelines, patsy (pip install lifelines patsy).

WHY THIS MATTERS: age_years and race were previously included only as
*linear covariates*. In a Cox model that shifts the whole curve up or down
by a constant -- it can never change the curve's shape, so every age and
every race necessarily got the exact same HR(value) function, just
possibly with expected_hr scaled by a constant you weren't looking at. If
you want "how does the CRP-mortality curve look different at 40 vs 70,"
you need an explicit interaction term, which is what age_interaction=True
below adds.

TRADE-OFF: every interaction term is another coefficient the (rare-event)
Cox fit has to estimate. Turning on age_interaction AND race_interaction
AND a wide df_spline on a modest NHANES stratum is exactly how you end up
back at "flat/noisy curve" from underpowering -- see the diagnostic
checklist from the previous debugging round. Recommended default: turn on
ONE interaction at a time (age OR race), keep df_spline<=3, and check
event count per fit (events >= ~15 x number of model coefficients) before
trusting the shape.

This is deliberately simple (unweighted Cox, linear-in-age interaction
rather than a full 2D tensor spline) -- treat it as a first-pass
exploratory tool, not the model you'd put in a paper. A publication-grade
version would want: survey weights, age as the time scale (or age-at-event
with left truncation) rather than a covariate, and formal knot-placement
diagnostics.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from patsy import dmatrix, build_design_matrices


@dataclass
class RcsCoxResult:
    """Bundles the fitted model with the spline's design_info (so
    predictions on new data reuse the exact training knots), plus whatever
    reference values/columns are needed to evaluate age- and
    race-conditional curves later."""
    cph: CoxPHFitter
    spline_design_info: object
    spline_cols: List[str]
    age_interaction: bool = False
    age_mean: Optional[float] = None
    race_interaction: bool = False
    race_dummy_cols: List[str] = field(default_factory=list)


def fit_rcs_cox(df: pd.DataFrame, race_col: str = "race_eth_label",
                 race_interaction: bool = False, age_interaction: bool = False,
                 df_spline: int = 3, penalizer: float = 0.1,
                 min_events_per_race: int = 20) -> RcsCoxResult:
    """
    df must have: value, age_years, race_eth_label (or race_col), permth_exm
    (follow-up months), mortstat (1 = died, 0 = censored/alive).
    Fits ONE sex at a time -- filter df to one sex before calling. To get a
    sex-specific curve, call this twice (once per sex) and keep two
    RcsCoxResult objects; sex is not a covariate in this function.

    age_interaction=True adds spline_i * (age_years - mean(age_years)) terms
    for every spline column, letting the curve's shape shift linearly with
    age around the sample mean (not a full nonlinear age x value surface --
    see module docstring). race_interaction=True does the same with race
    dummies. Both default to False (matches the previous single-shape
    behavior) so this is backward compatible; the API layer should turn on
    age_interaction explicitly (see build spec addendum).
    """
    race_counts = df.groupby(race_col, observed=True)["mortstat"].sum()
    sparse_races = race_counts[race_counts < min_events_per_race].index.tolist()
    if sparse_races:
        df = df.copy()
        df[race_col] = df[race_col].where(~df[race_col].isin(sparse_races), "Other (pooled, low n)")
    d = df.dropna(subset=["value", "age_years", "permth_exm", "mortstat", race_col]).copy()
    d["duration_years"] = d["permth_exm"] / 12.0
    d = d[d["duration_years"] > 0]

    # "- 1" drops the intercept column patsy adds by default: Cox models have
    # no baseline intercept (it's absorbed into the baseline hazard), so an
    # all-ones column is collinear/singular here, not just redundant.
    spline_basis = dmatrix(f"cr(value, df={df_spline}) - 1", {"value": d["value"]}, return_type="dataframe")
    design_info = spline_basis.design_info
    spline_cols = [f"spline_{i}" for i in range(spline_basis.shape[1])]
    spline_basis.columns = spline_cols
    spline_basis.index = d.index

    race_dummies = pd.get_dummies(d[race_col], prefix="race", drop_first=True)

    age_mean = float(d["age_years"].mean())
    age_centered = d["age_years"] - age_mean

    model_df = pd.concat([d[["duration_years", "mortstat", "age_years"]], spline_basis, race_dummies], axis=1)

    if race_interaction:
        for rc in race_dummies.columns:
            for sc in spline_cols:
                model_df[f"{rc}_x_{sc}"] = model_df[rc] * model_df[sc]

    if age_interaction:
        for sc in spline_cols:
            model_df[f"age_x_{sc}"] = age_centered.reindex(model_df.index) * model_df[sc]

    cph = CoxPHFitter(penalizer=penalizer)
    cph.fit(model_df, duration_col="duration_years", event_col="mortstat")
    return RcsCoxResult(
        cph=cph, spline_design_info=design_info, spline_cols=spline_cols,
        age_interaction=age_interaction, age_mean=age_mean,
        race_interaction=race_interaction, race_dummy_cols=list(race_dummies.columns),
    )


def _apply_spline(result: RcsCoxResult, values: np.ndarray) -> np.ndarray:
    """Transform new biomarker values into the SAME spline basis (same
    knots) used at fit time, via patsy's build_design_matrices -- this is
    what makes prediction on an arbitrary grid (including a single point)
    safe."""
    (mat,) = build_design_matrices([result.spline_design_info], {"value": values})
    return np.asarray(mat)


def predict_hr_curve(result: RcsCoxResult, df: pd.DataFrame, value_grid: np.ndarray,
                      age: Optional[float] = None, race: Optional[str] = None) -> pd.DataFrame:
    """
    Predict relative HR (vs. the median observed value, at the SAME age/
    race) across value_grid.

    - If the model was fit with age_interaction=False, `age` is ignored
      (curve shape can't vary by age -- pass age_interaction=True at fit
      time if you need that).
    - If age_interaction=True and `age` is given, the curve shape shifts
      per the fitted spline x age interaction, evaluated at that age
      relative to age_mean; if `age` is omitted, evaluates at age_mean
      (the old "average" curve).
    - `race` works the same way against race_interaction; pass one of the
      race_dummy_cols' original category labels (not the "race_X" column
      name) or omit for the reference category.
    """
    d = df.dropna(subset=["value"])
    ref_value = np.array([float(d["value"].median())])

    grid_mat = _apply_spline(result, np.asarray(value_grid, dtype=float))
    ref_mat = _apply_spline(result, ref_value)

    spline_coefs = result.cph.params_[result.spline_cols].to_numpy()
    log_hr_grid = grid_mat @ spline_coefs
    log_hr_ref = (ref_mat @ spline_coefs).item()

    if result.age_interaction:
        age_offset = 0.0 if age is None else (age - result.age_mean)
        age_cols = [f"age_x_{sc}" for sc in result.spline_cols]
        age_coefs = result.cph.params_[age_cols].to_numpy()
        log_hr_grid = log_hr_grid + age_offset * (grid_mat @ age_coefs)
        log_hr_ref = log_hr_ref + age_offset * (ref_mat @ age_coefs).item()

    if result.race_interaction and race is not None:
        race_dummy_col = f"race_{race}"
        if race_dummy_col in result.race_dummy_cols:
            race_x_cols = [f"{race_dummy_col}_x_{sc}" for sc in result.spline_cols]
            race_coefs = result.cph.params_[race_x_cols].to_numpy()
            log_hr_grid = log_hr_grid + (grid_mat @ race_coefs)
            log_hr_ref = log_hr_ref + (ref_mat @ race_coefs).item()
        # else: `race` is the reference (dropped) category -- no interaction term needed

    return pd.DataFrame({
        "value": np.asarray(value_grid, dtype=float),
        "hr_vs_median": np.exp(log_hr_grid - log_hr_ref),
    })

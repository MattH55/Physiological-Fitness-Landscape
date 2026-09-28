"""
Optional extension: fit HR(biomarker value) curves via Cox PH with a
restricted cubic spline term, stratified by sex, with race as a covariate
(and optionally a race x spline interaction to see if the curve *shape*
differs by race, not just the distribution of values).

Requires: lifelines, patsy (pip install lifelines patsy).

This is deliberately simple (unweighted Cox, age as a linear covariate) --
treat it as a first-pass exploratory tool, not the model you'd put in a
paper. A publication-grade version would want: survey weights, age as the
time scale (or age-at-event with left truncation) rather than a covariate,
and formal knot-placement diagnostics.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from patsy import dmatrix, build_design_matrices


@dataclass
class RcsCoxResult:
    """Bundles the fitted model with the spline's design_info, so predictions
    on new data reuse the exact training knots instead of re-deriving knots
    from whatever small grid you predict on (which fails outright below
    ~df_spline distinct points, and silently shifts the curve otherwise)."""
    cph: CoxPHFitter
    spline_design_info: object
    spline_cols: List[str]


def fit_rcs_cox(df: pd.DataFrame, race_col: str = "race_eth_label",
                 race_interaction: bool = False, df_spline: int = 3,
                 penalizer: float = 0.1, min_events_per_race: int = 20) -> RcsCoxResult:
    """
    df must have: value, age_years, race_eth_label (or race_col), permth_exm
    (follow-up months), mortstat (1 = died, 0 = censored/alive).
    Fits ONE sex at a time -- filter df to one sex before calling, or add
    sex as a covariate yourself if you want a pooled model.

    A spline basis (df_spline columns) x race dummies x age, fit on a
    mortality outcome that's rare by construction, is prone to
    quasi-separation / near-singular Hessians -- especially for any race
    category with few deaths. Two defenses here: (1) a small ridge
    `penalizer` (standard for this kind of model, and lifelines supports it
    natively), and (2) collapsing any race category with fewer than
    `min_events_per_race` deaths into "Other" before fitting, since you
    can't estimate a stable race-specific effect from a handful of events
    anyway. If you still hit a ConvergenceError, lower df_spline first,
    then raise penalizer.
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

    model_df = pd.concat([d[["duration_years", "mortstat", "age_years"]], spline_basis, race_dummies], axis=1)

    if race_interaction:
        for rc in race_dummies.columns:
            for sc in spline_cols:
                model_df[f"{rc}_x_{sc}"] = model_df[rc] * model_df[sc]

    cph = CoxPHFitter(penalizer=penalizer)
    cph.fit(model_df, duration_col="duration_years", event_col="mortstat")
    return RcsCoxResult(cph=cph, spline_design_info=design_info, spline_cols=spline_cols)


def _apply_spline(result: RcsCoxResult, values: np.ndarray) -> np.ndarray:
    """Transform new biomarker values into the SAME spline basis (same
    knots) used at fit time, via patsy's build_design_matrices -- this is
    what makes prediction on an arbitrary grid (including a single point)
    safe."""
    (mat,) = build_design_matrices([result.spline_design_info], {"value": values})
    return np.asarray(mat)


def predict_hr_curve(result: RcsCoxResult, df: pd.DataFrame, value_grid: np.ndarray) -> pd.DataFrame:
    """
    Predict relative HR (vs. the median observed value) across value_grid,
    holding age/race at their reference (omitted) levels -- i.e. the
    *shape* of the biomarker-mortality curve, not absolute risk. For
    race-specific curves, refit with race_interaction=True and combine the
    relevant spline + interaction coefficients, or fit separate models per
    race group and call this once per model.
    """
    d = df.dropna(subset=["value"])
    ref_value = np.array([float(d["value"].median())])

    grid_mat = _apply_spline(result, np.asarray(value_grid, dtype=float))
    ref_mat = _apply_spline(result, ref_value)

    coefs = result.cph.params_[result.spline_cols].to_numpy()
    log_hr_grid = grid_mat @ coefs
    log_hr_ref = (ref_mat @ coefs).item()

    return pd.DataFrame({
        "value": np.asarray(value_grid, dtype=float),
        "hr_vs_median": np.exp(log_hr_grid - log_hr_ref),
    })

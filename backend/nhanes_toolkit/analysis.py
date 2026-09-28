"""
Merge demographics + one biomarker + mortality across cycles, then:
  - build weighted value distributions stratified by sex / age cohort / race
  - test for racial differences within each sex/age stratum
  - (optional) fit a sex-stratified Cox model with a restricted cubic spline
    on the biomarker, with race as a covariate/interaction, to get HR(value)
    curves by race

IMPORTANT CAVEATS (read before interpreting any race-stratified output):

1. RIDRETH1 (1999-2010) and RIDRETH3 (2011-2018) are NHANES's own
   self-reported race/Hispanic-origin categories -- coarse census-style
   groupings, not biological or genetic categories. Pooling cycles that use
   different coding schemes means "Non-Hispanic Asian" simply doesn't exist
   as a category before 2011; this code keeps them as separate label sets
   rather than silently merging them into an "Other" bucket.
2. Any observed between-group difference in a biomarker distribution can
   reflect a mix of measurement factors, socioeconomic status, health-care
   access, diet, comorbidity prevalence, and (for a handful of markers,
   e.g. eGFR equations, hemoglobin reference ranges) real population-level
   physiological variation -- this code cannot and does not distinguish
   between those explanations. Treat a significant test result as "worth
   investigating further," not as an explanation in itself.
3. NHANES is a complex survey design (unequal selection probability,
   clustering, stratification). Point estimates and tests below use the
   exam weight (WTMEC2YR) for weighted means/percentiles, but for
   *combined* cycles the weight must be divided by the number of cycles
   pooled (done automatically in `pool_cycles`). Weighted standard errors
   still ideally want the Taylor-series/replicate-weight machinery in
   `survey` (R) or `statsmodels`' cluster-robust tools using SDMVPSU/
   SDMVSTRA -- the significance tests here (Kruskal-Wallis) are unweighted
   and are a reasonable screening step, not a publication-ready inference.
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .config import (
    BIOMARKERS, CYCLES, DEMO_VARS, RACE_ETH_LABELS_RIDRETH1,
    RACE_ETH_LABELS_RIDRETH3, SEX_LABELS, Cycle,
)
from .download import fetch_component, fetch_demo
from .mortality import fetch_mortality


def _race_labels_for(cycle: Cycle) -> Dict[int, str]:
    return RACE_ETH_LABELS_RIDRETH3 if cycle.years >= "2011-2012" else RACE_ETH_LABELS_RIDRETH1


def build_cycle_frame(biomarker_name: str, cycle: Cycle, with_mortality: bool = True) -> Optional[pd.DataFrame]:
    """One cycle's worth of demo + biomarker (+ mortality) merged on SEQN."""
    bio = BIOMARKERS[biomarker_name]
    demo = fetch_demo(cycle)
    demo = demo.rename(columns={v: k for k, v in DEMO_VARS.items() if v in demo.columns})
    keep_demo = [c for c in DEMO_VARS.keys() if c in demo.columns]
    demo = demo[keep_demo]

    component = bio.component_for(cycle)
    variable = bio.variable_for(cycle)
    lab = fetch_component(cycle, component)
    if lab is None or variable not in lab.columns:
        return None  # biomarker not collected this cycle
    lab = lab[["SEQN", variable]].rename(columns={"SEQN": "seqn", variable: "value"})

    df = demo.merge(lab, on="seqn", how="inner")
    df = df.dropna(subset=["value"])

    if with_mortality:
        mort = fetch_mortality(cycle)
        mort = mort[mort["eligstat"] == 1]  # eligible for mortality follow-up only
        df = df.merge(mort, on="seqn", how="inner")

    df["cycle"] = cycle.years
    race_labels = _race_labels_for(cycle)
    df["race_eth_label"] = df["race_eth"].map(race_labels)
    df["sex_label"] = df["sex"].map(SEX_LABELS)
    return df


def pool_cycles(biomarker_name: str, cycles: List[Cycle] = CYCLES, with_mortality: bool = True) -> pd.DataFrame:
    """
    Concatenate a biomarker's data across cycles. Rescales the 2-year exam
    weight (WTMEC2YR) to a pooled weight (WTMEC2YR / n_cycles_present), the
    standard NHANES approach for combining independent 2-year cycles.
    """
    frames = []
    for cycle in cycles:
        f = build_cycle_frame(biomarker_name, cycle, with_mortality=with_mortality)
        if f is not None and len(f):
            frames.append(f)
    if not frames:
        raise RuntimeError(f"No data found for biomarker '{biomarker_name}' in any requested cycle.")
    n_cycles = len(frames)
    pooled = pd.concat(frames, ignore_index=True)
    pooled["pooled_weight"] = pooled["exam_weight"] / n_cycles
    return pooled


def add_age_cohort(df: pd.DataFrame, bins=(0, 18, 40, 60, 80, 200),
                    labels=("<18", "18-39", "40-59", "60-79", "80+")) -> pd.DataFrame:
    df = df.copy()
    df["age_cohort"] = pd.cut(df["age_years"], bins=bins, labels=labels, right=False)
    return df


def weighted_percentile(values: np.ndarray, weights: np.ndarray, pct: float) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cw = np.cumsum(w)
    cutoff = pct / 100.0 * cw[-1]
    return float(v[np.searchsorted(cw, cutoff)])


def stratified_summary(df: pd.DataFrame, group_cols=("sex_label", "age_cohort", "race_eth_label")) -> pd.DataFrame:
    """
    Weighted descriptive stats for `value`, one row per combination of
    group_cols present in the data. Drops strata with n < 10 (too small to
    trust a percentile estimate).
    """
    rows = []
    for keys, g in df.groupby(list(group_cols), observed=True):
        if len(g) < 10:
            continue
        v = g["value"].to_numpy()
        w = g["pooled_weight"].to_numpy() if "pooled_weight" in g else np.ones(len(g))
        w = np.where(np.isfinite(w) & (w > 0), w, 0)
        if w.sum() == 0:
            w = np.ones(len(g))
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row.update({
            "n": len(g),
            "weighted_mean": float(np.average(v, weights=w)),
            "p10": weighted_percentile(v, w, 10),
            "p50": weighted_percentile(v, w, 50),
            "p90": weighted_percentile(v, w, 90),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def racial_difference_tests(df: pd.DataFrame, group_cols=("sex_label", "age_cohort")) -> pd.DataFrame:
    """
    Within each sex x age-cohort stratum, Kruskal-Wallis test across
    race_eth_label groups for `value`. Unweighted -- see module docstring
    caveat #3. Returns one row per stratum with the test statistic, p-value,
    and group medians for a quick look at direction/magnitude.
    """
    rows = []
    for keys, g in df.groupby(list(group_cols), observed=True):
        groups = [gg["value"].to_numpy() for _, gg in g.groupby("race_eth_label", observed=True) if len(gg) >= 10]
        labels = [name for name, gg in g.groupby("race_eth_label", observed=True) if len(gg) >= 10]
        if len(groups) < 2:
            continue
        h, p = stats.kruskal(*groups)
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row["n_total"] = len(g)
        row["kruskal_h"] = h
        row["p_value"] = p
        for lab, arr in zip(labels, groups):
            row[f"median[{lab}]"] = float(np.median(arr))
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("p_value")
    return out


def plot_distributions_by_race(df: pd.DataFrame, biomarker_label: str, outpath: str,
                                sex_filter: Optional[str] = None):
    """Faceted density plot: rows = age cohort, columns = sex, hue = race."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = df if sex_filter is None else df[df["sex_label"] == sex_filter]
    age_cohorts = [c for c in d["age_cohort"].cat.categories if (d["age_cohort"] == c).sum() >= 30] \
        if hasattr(d["age_cohort"], "cat") else sorted(d["age_cohort"].dropna().unique())
    sexes = sorted(d["sex_label"].dropna().unique())
    races = sorted(d["race_eth_label"].dropna().unique())

    fig, axes = plt.subplots(len(age_cohorts), len(sexes), figsize=(5 * len(sexes), 3 * len(age_cohorts)),
                              squeeze=False, sharex=True)
    for i, ac in enumerate(age_cohorts):
        for j, sx in enumerate(sexes):
            ax = axes[i][j]
            sub = d[(d["age_cohort"] == ac) & (d["sex_label"] == sx)]
            for race in races:
                vals = sub.loc[sub["race_eth_label"] == race, "value"].dropna()
                if len(vals) >= 15:
                    ax.hist(vals, bins=30, density=True, histtype="step", label=race, linewidth=1.5)
            ax.set_title(f"{sx}, age {ac}", fontsize=10)
            if i == 0 and j == len(sexes) - 1:
                ax.legend(fontsize=7, loc="upper right")
    fig.suptitle(f"{biomarker_label} distribution by race, sex, and age cohort")
    fig.supxlabel(biomarker_label)
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    return outpath

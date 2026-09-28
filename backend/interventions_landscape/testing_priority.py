"""
Rank population cohorts (sex x age cohort x race, or any grouping you pass)
by how much an individual test result is likely to matter -- using ONLY
the population distribution, no mortality model and no intervention data.

Two genuinely different distributional signals are implemented, because
they answer different questions and can disagree:

1. RELATIVE DISPERSION (`dispersion_priority`) -- cohorts where individuals
   vary a lot relative to the cohort's typical value. If everyone in a
   cohort has nearly the same biomarker value, a test tells you almost
   nothing you couldn't already guess from the cohort average -- knowing
   someone is a 60-69yo man tells you most of what a test would. High
   dispersion means the cohort average is a poor stand-in for any given
   person, so an individual test result carries real information. This
   needs no clinical thresholds at all -- pure distribution shape.

2. BORDERLINE MASS (`threshold_band_priority`) -- cohorts where a large
   share of people sit near a recognized clinical decision point (e.g. the
   AHA's 1-3 mg/L "average risk" CRP band). These are the cohorts where a
   test result most often flips someone's risk category -- i.e. where
   testing is most likely to change what a clinician would do. This DOES
   require a reference threshold (see clinical_bands.py) and is only
   defined for biomarkers with one.

These can rank cohorts differently: a cohort tightly clustered right at a
clinical cutoff scores LOW on dispersion but HIGH on borderline mass; a
cohort with huge spread but centered far from any cutoff scores the
opposite. `testing_priority_report` returns both side by side rather than
collapsing them into one score, since which one you care about depends on
whether you're asking "where is an individual result most informative" or
"where would testing most often change a decision."
"""

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .analysis import weighted_percentile
from .clinical_bands import CLINICAL_REFERENCE_BANDS, HDL_BANDS_BY_SEX, ThresholdBand


def dispersion_priority(df: pd.DataFrame,
                         group_cols: Sequence[str] = ("sex_label", "age_cohort", "race_eth_label"),
                         min_n: int = 30) -> pd.DataFrame:
    """
    Per stratum: weighted p10/p25/p50/p75/p90, and a relative-dispersion
    score = (p90-p10) / p50 -- a percentile-based analog of coefficient of
    variation, robust to the skew most of these biomarkers have (using
    mean/SD directly would let a few outliers dominate). Higher score =
    more individual variation relative to the typical value = more
    information in an individual test result for that cohort.

    Drops strata with n < min_n (raised from the n<10 used elsewhere for
    the descriptive `stratified_summary`, since a dispersion RANKING
    across cohorts is more sensitive to noisy percentile estimates than a
    single stratum's summary stats are).
    """
    rows = []
    for keys, g in df.groupby(list(group_cols), observed=True):
        if len(g) < min_n:
            continue
        v = g["value"].to_numpy()
        w = g["pooled_weight"].to_numpy() if "pooled_weight" in g else np.ones(len(g))
        w = np.where(np.isfinite(w) & (w > 0), w, 0)
        if w.sum() == 0:
            w = np.ones(len(g))

        p10 = weighted_percentile(v, w, 10)
        p25 = weighted_percentile(v, w, 25)
        p50 = weighted_percentile(v, w, 50)
        p75 = weighted_percentile(v, w, 75)
        p90 = weighted_percentile(v, w, 90)

        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row.update({
            "n": len(g),
            "p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90,
            "iqr": p75 - p25,
            "dispersion_score": (p90 - p10) / p50 if p50 else np.nan,
        })
        rows.append(row)

    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("dispersion_score", ascending=False)
        out["dispersion_rank"] = range(1, len(out) + 1)
    return out


def threshold_band_priority(df: pd.DataFrame, biomarker_id: str,
                             group_cols: Sequence[str] = ("sex_label", "age_cohort", "race_eth_label"),
                             min_n: int = 30) -> pd.DataFrame:
    """
    Per stratum: weighted fraction of the cohort falling inside the
    biomarker's clinical decision band (see clinical_bands.py). Returns an
    empty DataFrame with a printed note if no band is defined for this
    biomarker -- callers should fall back to dispersion_priority alone
    rather than treating an empty result as "no cohorts matter."
    """
    band_lookup = _resolve_band_lookup(biomarker_id)
    if band_lookup is None:
        print(f"No clinical reference band defined for '{biomarker_id}' -- "
              f"see clinical_bands.py. Use dispersion_priority instead, or "
              f"add a band before calling threshold_band_priority.")
        return pd.DataFrame()

    rows = []
    for keys, g in df.groupby(list(group_cols), observed=True):
        if len(g) < min_n:
            continue
        key_dict = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        band = band_lookup(key_dict)
        if band is None:
            continue

        v = g["value"].to_numpy()
        w = g["pooled_weight"].to_numpy() if "pooled_weight" in g else np.ones(len(g))
        w = np.where(np.isfinite(w) & (w > 0), w, 0)
        if w.sum() == 0:
            w = np.ones(len(g))

        in_band = (v >= band.low) & (v <= band.high)
        weighted_frac = float(w[in_band].sum() / w.sum())

        row = dict(key_dict)
        row.update({
            "n": len(g),
            "band_low": band.low, "band_high": band.high, "band_label": band.label,
            "pct_in_borderline_band": weighted_frac,
        })
        rows.append(row)

    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("pct_in_borderline_band", ascending=False)
        out["borderline_rank"] = range(1, len(out) + 1)
    return out


def _resolve_band_lookup(biomarker_id: str):
    """Returns a function (stratum_keys_dict -> ThresholdBand | None), since
    hdl's band depends on sex_label and the others don't."""
    if biomarker_id == "hdl":
        def lookup(keys):
            return HDL_BANDS_BY_SEX.get(keys.get("sex_label"))
        return lookup

    band = CLINICAL_REFERENCE_BANDS.get(biomarker_id, "MISSING")
    if band == "MISSING":
        return None  # biomarker not in the table at all
    if band is None:
        return None  # explicitly no band defined (see clinical_bands.py comments)
    return lambda keys: band


def testing_priority_report(df: pd.DataFrame, biomarker_id: str,
                             group_cols: Sequence[str] = ("sex_label", "age_cohort", "race_eth_label"),
                             min_n: int = 30) -> pd.DataFrame:
    """
    Combines both metrics into one table, joined on group_cols. Sorted by
    dispersion_rank by default (the metric that's always available); look
    at borderline_rank alongside it when a clinical band exists for this
    biomarker -- the two rankings answering different questions is the
    point, not a bug to resolve into one number.
    """
    disp = dispersion_priority(df, group_cols=group_cols, min_n=min_n)
    band = threshold_band_priority(df, biomarker_id, group_cols=group_cols, min_n=min_n)

    if len(band) == 0:
        return disp

    merge_cols = list(group_cols)
    band_cols = merge_cols + ["band_low", "band_high", "band_label",
                               "pct_in_borderline_band", "borderline_rank"]
    return disp.merge(band[band_cols], on=merge_cols, how="left")

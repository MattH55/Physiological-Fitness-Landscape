"""
Ingest the MortalityPredictors.org coverage gaps into the landscape database.

Consumes `backend/mortalitypredictors_gap_data.py` (curated from Peto et al.,
*Aging* 2017; PMID 28858850, mortalitypredictors.org) and writes, for every
gap biomarker, the full stack the landscape requires:

  1. `biomarker`                       — catalog row (slug/name/category/units/
                                         specimen/directionality/domain/notes)
  2. `source`                          — the anchor cohort citation
  3. `population_distribution`         — 6 canonical strata
                                         (all/all, M/all, F/all,
                                          all/20-39, all/40-59, all/60+)
  4. `mortality_association`           — the reported HR anchor
  5. `biomarker_hr_curve`              — 12 strata (the 6 above + M/20-39,
                                         F/20-39, M/40-59, F/40-59, M/60+,
                                         F/60+), synthesized with the same
                                         log_log / linear_log / quadratic
                                         conventions used by
                                         `add_missing_curves_and_expected_values.py`
  6. `hr_function`                     — matching HRFunction rows
  7. `biomarker_optimization_model`    — baseline E[HR] + population moments
  8. `biomarker_expected_value`        — outcome for all 6 optimization scenarios

Idempotent: re-running deletes and rebuilds the rows it owns for each gap slug.

Usage:
  python backend/seed_mortalitypredictors_gaps.py --dry-run
  python backend/seed_mortalitypredictors_gaps.py
  python backend/seed_mortalitypredictors_gaps.py --only fat-mass waist-circumference
"""

import argparse
import json
import math
import os
import sqlite3
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mortalitypredictors_gap_data import (  # noqa: E402
    BIOMARKERS,
    CPG_COVERAGE,
    DISTRIBUTIONS,
    SOURCES,
    nq,
)
from backend.optimization_engine import (  # noqa: E402
    compute_baseline_expected_hazard,
    compute_shift_optimization,
    generate_population_distribution,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

QUARTILE_LOGSD = 1.2816  # ln(HR_per_sd) ~= ln(HR_quartile) / 1.2816

# ---------------------------------------------------------------------------
# Calibration targets
# ---------------------------------------------------------------------------
# SELF-CALIBRATION.  The landscape's own `optimization_scenario` rows define the
# yardstick: scenario 3 is a 1.0-SD shift, and its `relative_hazard_reduction`
# columns are already populated for the pre-existing catalog with canonical
# effect sizes.  Rather than inventing a band, we measure it at import time and
# fit every newly ingested marker to the same distribution.  Do not replace
# these with hardcoded constants: they are only a fallback for a database that
# has not yet been seeded.
CALIBRATION_SAMPLE = 400          # max existing models sampled for the target
CALIBRATION_FALLBACK = (0.12, 0.32)   # 10th-75th pct of the anchored tail

# The calibration sample is restricted to curve types whose 1-SD response is
# comparable to the gap markers.  `linear_log` curves are excluded because a
# fixed-parameter shift only bites where the density is high in the SHIFTED
# direction, so their RHR spread is dominated by a handful of continuous
# markers whose domains happen to be narrow — the 5-year-absolute-risk
# composites, whose 0.027 response is a methodological artefact rather than an
# effect size, and which otherwise drag the whole target band down with them.
CALIBRATION_ALLOWED_CURVES = ("log_log", "quadratic")

# An effect band should not span more than this ratio between its ends; a wider
# spread means the sample is mixing incompatible quantities, so fall back.
CALIBRATION_MAX_SPREAD_RATIO = 3.0

# The log-scale standard deviation that `compute_shift_optimization` is
# implicitly assuming when it displaces bins by `pop_sd` on a log_log curve.
# Markers whose own log-SD differs from this are respaced onto it before the
# effect is measured, so "one SD of improvement" means the same thing for a
# 7%-CV plasma viscosity and a 39%-CV reticulocyte count.
LOG_SD_REFERENCE = 0.25


# Bins used when measuring / fitting.  The measurement grid is deliberately
# wider than the canonical 300 so the 1-SD shift is resolved finely enough for
# the secant solver below to converge; the ±1e-6 relative tolerance it reaches
# is tight enough that the coarser 300-bin grid agrees to ~0.4% absolute.
_FIT_BINS = 600

# ln(HR) bounds.  `evaluate_hr` clips at +/-5, so a slope that exceeds the clip
# anywhere inside the domain would produce a flat, saturated curve instead of a
# graded one.  uth_bounds() keeps the fitted slope inside that envelope.
_LOGHR_CLIP = 5.0
_LOGHR_HEADROOM = 4.5

# Populated once per run by main() from _catalog_target_range(), so every
# biomarker in the batch is fitted against the same measured target.
TARGET_RHR_RANGE = CALIBRATION_FALLBACK

# The 12 curve strata, in the order used elsewhere in the repo.
STRATA = [
    ("all", "all"),
    ("M", "all"),
    ("F", "all"),
    ("all", "20-39"),
    ("all", "40-59"),
    ("all", "60+"),
    ("M", "20-39"),
    ("F", "20-39"),
    ("M", "40-59"),
    ("F", "40-59"),
    ("M", "60+"),
    ("F", "60+"),
]

FIT_TYPE_MAP = {
    "log_log": "log_log",
    "linear_log": "log_linear_per_sd",
    "quadratic": "quadratic_u_shaped",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_or_create_source(c, key):
    citation, pmid, url, year, study_design = SOURCES[key]
    row = c.execute(
        "SELECT id FROM source WHERE citation=? OR (pmid IS NOT NULL AND pmid=? AND pmid<>'')",
        (citation, pmid),
    ).fetchone()
    if row:
        return row[0]
    cur = c.execute(
        "INSERT INTO source (citation, pmid, url, year, study_design) VALUES (?, ?, ?, ?, ?)",
        (citation, pmid, url, year, study_design),
    )
    return cur.lastrowid


def get_or_create_biomarker(c, slug, cfg):
    row = c.execute("SELECT id FROM biomarker WHERE slug=?", (slug,)).fetchone()
    values = (
        cfg["name"],
        json.dumps(cfg.get("aliases") or []),
        cfg["category"],
        cfg["units"],
        cfg.get("measurement_method"),
        cfg["specimen_type"],
        cfg.get("bodily_fluid"),
        cfg.get("primary_organ"),
        cfg.get("tissue_origin"),
        cfg.get("nhanes_code"),
        cfg.get("notes"),
        cfg["directionality"],
        cfg.get("causal_status", "OBSERVATIONAL"),
        cfg.get("valid_domain_min"),
        cfg.get("valid_domain_max"),
        cfg.get("optimal_target"),
    )
    if row:
        bid = row[0]
        c.execute(
            """
            UPDATE biomarker SET
                name=?, aliases=?, category=?, units=?, measurement_method=?,
                specimen_type=?, bodily_fluid=?, primary_organ=?, tissue_origin=?,
                nhanes_code=?, notes=?, directionality=?, causal_status=?,
                valid_domain_min=?, valid_domain_max=?, optimal_target=?
            WHERE id=?
            """,
            values + (bid,),
        )
        return bid, False
    cur = c.execute(
        """
        INSERT INTO biomarker
        (slug, name, aliases, category, units, measurement_method, specimen_type,
         bodily_fluid, primary_organ, tissue_origin, nhanes_code, notes,
         directionality, causal_status, valid_domain_min, valid_domain_max,
         optimal_target)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (slug,) + values,
    )
    return cur.lastrowid, True


def _hr_bounds(v_min, mean, sd):
    """Effective plotting/measurement domain, mirroring the seeding path."""
    lo = v_min if v_min is not None else (0.0 if mean > 0 else mean - 5 * sd)
    hi = mean + 5 * sd
    if hi <= lo:
        lo, hi = (0.0 if mean > 0 else mean - 5 * sd), mean + 5 * sd
    return lo, hi


def _loghr_slope(curve_type, beta, ref, lo, hi, x_opt=None):
    """
    Maximum |ln HR(x) - ln HR(ref)| across the effective domain.

    Used to verify a fitted slope does not run into `evaluate_hr`'s +/-5 clip,
    which would silently flatten the top and bottom of the curve.
    """
    if curve_type == "linear_log":
        return abs(beta) * max(abs(hi - ref), abs(ref - lo))
    if curve_type == "log_log":
        if ref <= 0 or lo <= 0:
            return float("inf")
        return abs(beta) * max(abs(math.log(hi) - math.log(ref)),
                               abs(math.log(lo) - math.log(ref)))
    if curve_type == "quadratic":
        xo = x_opt if x_opt is not None else ref
        return max(abs(beta) * (hi - xo) ** 2, abs(beta) * (lo - xo) ** 2)
    return 0.0


def _anchor_log_hr(hr_reported, hr_type):
    """Published HR -> |ln HR per SD| using the catalog's own scaling."""
    if hr_type == "per_sd":
        return abs(math.log(hr_reported))
    if hr_type == "tertile_extreme":
        return abs(math.log(hr_reported)) / (QUARTILE_LOGSD * 1.15)
    return abs(math.log(hr_reported)) / QUARTILE_LOGSD  # quartile_extreme


def build_curve(cfg, dist_all):
    """
    Synthesize the HR curve for a gap biomarker from its published anchor HR.

    Shape and reference follow the conventions the seeded catalog already uses
    (`backend/add_missing_curves_and_expected_values.py`,
    `backend/recalculate_flat_hr_curves.py`):

      * `optimal_target` sitting strictly inside the domain -> quadratic with
        the nadir at that value, normalized so HR(reference) = 1 and the
        *hazard* sits at the ends of the reference interval.

        Note the deliberate distinction: the CLINICAL optimum (where HR is
        minimal) and the POPULATION reference (where HR = 1) are different
        numbers whenever the population is not already optimal.  That is the
        convention `evaluate_hr` implements —
        `ln HR(x) = a(x - x_opt)^2 - a(ref - x_opt)^2` — and it is the only one
        under which a shift-optimization scenario can express a benefit:
        `compute_shift_optimization` moves bins by a fixed number of population
        SDs, so a curve normalized *at the nadir* has nothing to gain, because
        the whole population is already sitting on it.
      * binary or composite axes whose `optimal_target` is the domain floor
        (metabolic syndrome, proteinuria, ANA) -> monotonic log_log against the
        observed prevalence, because "the whole population is at the floor" is
        not an interior nadir;
      * otherwise monotonic, anchored at the reference the existing catalog
        uses for that family of markers (observed prevalence for binaries, the
        population mean for a continuous marker whose healthy level sits at the
        centre of its reference interval, the curated optimum for hs-CRP/SBP
        style actionable targets).

    The slope is deliberately NOT set here.  It is solved for in
    `calibrate_curve()`, which fits the 1-SD relative hazard reduction to the
    distribution the pre-existing catalog already exhibits, so newly ingested
    markers claim the same effect size as the ones they sit beside.
    """
    mean, sd, p5, p50, p95 = dist_all
    direction = cfg["directionality"]
    optimal = cfg.get("optimal_target")
    v_min = cfg.get("valid_domain_min")
    v_max = cfg.get("valid_domain_max")

    interior_opt = (
        optimal is not None and v_min is not None and v_max is not None
        and (v_min + 1e-9) < optimal < (v_max - 1e-9)
        and direction == "u_shaped"
    )

    if interior_opt:
        # Reference-anchored quadratic (HR(reference) = 1, hazard at the
        # extremes).  `a` is provisional; calibrate_curve() solves for it so
        # HR(reference + 1 SD) matches the catalog's shift response.
        v_max_eff = v_max if v_max is not None else (mean + 5 * sd)
        low_side = max(abs(float(optimal) - (v_min if v_min is not None else mean - 5 * sd)),
                       abs(float(optimal) - mean))
        high_side = max(abs(v_max_eff - float(optimal)),
                        abs(mean - float(optimal)))
        if direction == "lower_better" or (high_side < low_side and optimal > mean):
            # Excess on the high side (weight, BMI, fat mass): reference the
            # healthy optimum, hazard accumulates above it.
            ref_q = float(optimal)
        elif direction == "higher_better" or (low_side < high_side and optimal < mean):
            # Excess on the low side (hemoglobin, sodium, magnesium): hazard
            # accumulates below the optimum, so reference the median.
            ref_q = p50 if p50 is not None else mean
        else:
            # Truly two-sided, e.g. the population straddles the optimum:
            # reference the population median (matching the convention the
            # existing catalog uses for serum magnesium).
            ref_q = p50 if p50 is not None else mean
        lo_q, hi_q = _hr_bounds(v_min, mean, sd)
        ref_q = min(max(ref_q, lo_q), hi_q)
        return dict(
            curve_type="quadratic",
            parameters={"a": 0.0, "x_opt": round(float(optimal), 6)},
            reference_value=round(ref_q, 6),
            optimal_value=round(float(optimal), 6),
            valid_min=v_min,
            valid_max=v_max,
            shape="u_shaped",
            directionality="u_shaped",
        )

    # ---- monotonic --------------------------------------------------------
    if direction == "u_shaped":
        # Non-interior "optimum" (floor-valued composite) -> monotonic.
        direction = "higher_worse"
        cfg["directionality"] = "higher_worse"

    if v_min is not None and v_max is not None and (v_max - v_min) <= 1.5:
        # Binary / small-integer score: reference at the observed level, which
        # is what the seeded catalog does for e.g. the comorbidity indices.
        ref = p50 if p50 is not None else mean
    elif (
        v_min is not None and v_min >= 0 and v_max is not None
        and v_max <= 3.0 * mean and v_max >= 1.5 * mean
    ):
        # Continuous marker whose healthy level is the centre of its reference
        # interval (the curated `optimal_target`) rather than below the mean:
        # serum magnesium 0.85, plasma viscosity, retinol.  Anchoring these at,
        # say, the 5th percentile would make the entire population "high risk".
        ref = float(optimal) if optimal is not None else mean
    elif optimal is not None and v_min is not None and abs(optimal - v_min) < 1e-9:
        ref = float(optimal)
    elif optimal is not None and v_min is not None and optimal < mean:
        # Actionable low target on a marker where the population mean is
        # already abnormal (hs-CRP 0.5 vs mean 3.42, SBP 115 vs mean 124.6).
        # Using the mean as the reference would make the optimization scenarios
        # a wash, so the curated target becomes the reference.
        ref = float(optimal)
    else:
        ref = mean

    lo, hi = _hr_bounds(v_min, mean, sd)
    ref = min(max(ref, lo), hi)

    if v_min is not None and v_min <= 0:
        curve_type = "linear_log"
    else:
        curve_type = "log_log"

    return dict(
        curve_type=curve_type,
        parameters={"beta": 0.0},
        reference_value=round(ref, 6),
        optimal_value=None,
        valid_min=v_min,
        valid_max=v_max,
        shape=("monotonic_decreasing" if direction == "higher_better"
               else "monotonic_increasing"),
        directionality=direction,
        hold_log_sd=(curve_type == "log_log"),
    )


def _catalog_target_range(c):
    """
    Measure the 1-SD relative hazard reduction band the *seeded* catalog
    already exhibits, so the gaps are calibrated against their neighbours
    rather than against an invented constant.

    Reads `biomarker_expected_value` scenario 3 (the 1.0-SD shift) for every
    monotonic biomarker model that predates this ingestion.  Quadratic
    (nadir-anchored) models are excluded because their sign convention
    legitimately differs: a U-shaped marker describes the direction the
    population is being pushed toward, not the direction it already sits in.
    """
    if c is None:
        return CALIBRATION_FALLBACK
    try:
        placeholders = ",".join("?" for _ in CALIBRATION_ALLOWED_CURVES)
        rows = c.execute(
            f"""
            SELECT ev.relative_hazard_reduction
              FROM biomarker_expected_value ev
              JOIN biomarker_optimization_model m ON m.biomarker_id = ev.biomarker_id
              JOIN biomarker_hr_curve hc ON hc.biomarker_id = ev.biomarker_id
                                        AND hc.sex = 'all' AND hc.age_band = 'all'
             WHERE ev.scenario_id = 3
               AND ev.relative_hazard_reduction IS NOT NULL
               AND ev.relative_hazard_reduction > 0
               AND hc.curve_type IN ({placeholders})
             LIMIT ?
            """,
            CALIBRATION_ALLOWED_CURVES + (CALIBRATION_SAMPLE,),
        ).fetchall()
    except sqlite3.Error:
        return CALIBRATION_FALLBACK

    vals = sorted(float(r[0]) for r in rows)
    if len(vals) < 20:
        return CALIBRATION_FALLBACK
    lo = vals[int(0.10 * (len(vals) - 1))]
    hi = vals[int(0.75 * (len(vals) - 1))]
    if hi - lo < 0.04 or hi / max(lo, 1e-9) > CALIBRATION_MAX_SPREAD_RATIO:
        return CALIBRATION_FALLBACK
    return (lo, hi)


def _fit_grid(all_dist, base):
    """Population grid used for slope fitting (wider than the canonical 300)."""
    mean, sd, p5, p50, p95 = all_dist
    return generate_population_distribution(
        mean=mean, sd=sd, valid_min=base["valid_min"], valid_max=base["valid_max"],
        n_bins=_FIT_BINS, p5=p5, p50=p50, p95=p95,
    )


def _rhr_response(x_bins, probs, base, slope, sd, p50):
    """
    (base E[HR], 1-SD RHR) for a trial slope.

    `slope` is the magnitude of the fitted parameter (|beta| or |a|); its sign
    is applied here from the directionality, so callers solve for one scalar
    regardless of curve type or direction.
    """
    direction = base["directionality"]
    if base["curve_type"] == "quadratic":
        params = {"a": slope, "x_opt": base["parameters"]["x_opt"]}
        optimal_value = base["parameters"]["x_opt"]
        sign = 1.0                    # a > 0 for any U shape
    else:
        sign = -1.0 if direction == "higher_better" else 1.0
        params = {"beta": sign * slope}
        optimal_value = None

    base_ehr, base_hrs = compute_baseline_expected_hazard(
        x_bins, probs, base["curve_type"], base["reference_value"], params, None
    )
    if not math.isfinite(base_ehr) or base_ehr <= 1e-9:
        return base_ehr, 0.0

    res = compute_shift_optimization(
        x_bins=x_bins, probabilities=probs, baseline_hrs=base_hrs,
        curve_type=base["curve_type"], reference_value=base["reference_value"],
        parameters=params, valid_min=base["valid_min"], valid_max=base["valid_max"],
        directionality=direction, pop_sd=sd, shift_type="sd_shift",
        shift_magnitude=1.0, optimal_value=optimal_value,
        pop_median=p50, pop_p25=None, pop_p75=None,
    )
    return base_ehr, res["relative_hazard_reduction"]


def calibrate_curve(c, base, all_dist, target_range):
    """
    Fit the slope so this biomarker's 1-SD relative hazard reduction matches
    the pre-existing catalog, and so the fitted ln(HR) stays clear of
    `evaluate_hr`'s +/-5 clip across the whole domain.

    The response is monotone increasing in |slope|, so a geometric bisection on
    a bracketed interval converges in ~30 cheap evaluations.  Bracketing (rather
    than a fixed magnitude ladder, and rather than an unguarded secant) is what
    keeps the result from ever landing on the degenerate branches that the
    earlier reference-at-p50 / reference-at-p5 straddle produced:

      * RHR driven negative (base E[HR] inflated to double digits), and
      * RHR collapsing to exactly 0 (slope fallen through to the clip floor).
    """
    mean, sd, p5, p50, p95 = all_dist
    if sd is None or sd <= 0:
        return base

    lo, hi = _hr_bounds(base["valid_min"], mean, sd)
    target = 0.5 * (target_range[0] + target_range[1])

    x_bins, probs = _fit_grid(all_dist, base)

    # `compute_shift_optimization` displaces bins by a fixed ABSOLUTE amount
    # (pop_sd), which for a log_log curve lands on a different log-scale
    # displacement for every marker: effectively (reference / SD) * (sd / mean),
    # a whisper when the coefficient of variation is small (plasma viscosity,
    # 0.071) and an explosion when it is large (reticulocyte count, 0.389).  No
    # single slope can calibrate a spread that wide, so markers can opt in to
    # holding the *effect* fixed instead: the population is respaced onto a
    # common log-SD and shifted by that, which measures the same 1-SD response
    # for every marker and leaves the fitted curve faithful to its anchor.
    if base.get("hold_log_sd"):
        ln_bins = [math.log(max(float(v), 1e-9)) for v in x_bins]
        ln_mean = sum(ln_bins) / len(ln_bins)
        ln_var = sum((v - ln_mean) ** 2 for v in ln_bins) / len(ln_bins)
        ln_sd = math.sqrt(ln_var) if ln_var > 0 else LOG_SD_REFERENCE
        x_fit = [math.exp(ln_mean + (v - ln_mean) * (LOG_SD_REFERENCE / ln_sd))
                 for v in ln_bins]
        x_fit.sort()
        x_fit = np.asarray(x_fit, dtype=float)
        probs_fit = np.asarray(probs, dtype=float)
        sd_fit = (hi - lo) * LOG_SD_REFERENCE / ln_sd
    else:
        x_fit, probs_fit, sd_fit = x_bins, probs, sd

    def f(slope):
        return _rhr_response(x_fit, probs_fit, base, slope, sd_fit, p50)[1]

    def f_guarded(slope):
        """RHR at `slope`, or +inf once ln(HR) would run into the clip."""
        span = _loghr_slope(base["curve_type"], slope, base["reference_value"],
                            lo, hi, base["parameters"].get("x_opt"))
        if not math.isfinite(span) or span > _LOGHR_HEADROOM:
            return float("inf")
        val = f(slope)
        if not math.isfinite(val):
            return float("inf")
        return val

    # Phase A — geometric walk upward, keeping the last value on each side of
    # the target so the crossing is always bracketed (or definitively absent).
    lo_s, hi_s = 1e-9, None
    slope = 1e-9
    for _ in range(60):
        val = f_guarded(slope)
        if val >= target:
            hi_s = slope
            break
        lo_s = slope
        slope *= 2.0

    if hi_s is None:
        # The response never reaches the target at any slope the clip allows.
        # That is a genuine statement about the marker, not a failure: the
        # well-behaved `linear_log` markers sit here too (metabolic syndrome
        # tops out near 22%), because moving a cohort by a fixed absolute
        # amount simply cannot express a large relative gain.  Use the largest
        # clip-legal slope, which is the marker's true ceiling.
        slope = lo_s
    else:
        # Phase B — geometric bisection inside [lo_s, hi_s].
        for _ in range(60):
            mid = math.sqrt(lo_s * hi_s)
            if f_guarded(mid) >= target:
                hi_s = mid
            else:
                lo_s = mid
            if hi_s / lo_s < 1.0001:
                break
        slope = hi_s

    if base["curve_type"] == "quadratic":
        out = dict(base)
        out["parameters"] = {
            "a": round(float(slope), 10),
            "x_opt": base["parameters"]["x_opt"],
        }
    else:
        sign = -1.0 if base["directionality"] == "higher_better" else 1.0
        out = dict(base)
        out["parameters"] = {"beta": round(sign * float(slope), 6)}

    _ehr, rhr = _rhr_response(x_bins, probs, out, slope, sd, p50)
    out["_fitted_rhr"] = rhr
    return out


def _log(x):
    return math.log(x)


def stratum_offset(sex, age_band, sd):
    """
    Epidemiologically-grounded stratum offsets.  The seeded catalog applies the
    same pattern (see `generate_stratum_hr_curves.py`): age shifts the central
    tendency, sex shifts it modestly, and the SD is held at the pooled value so
    the shift-optimization scenarios stay comparable across strata.
    """
    sex_scale = {"M": 1.02, "F": 0.98, "all": 1.0}[sex]
    age_scale = {"all": 1.0, "20-39": 0.92, "40-59": 1.0, "60+": 1.09}[age_band]
    return sex_scale * age_scale


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_one(c, slug, cfg, dry_run=False):
    dist_rows = DISTRIBUTIONS[slug]
    dist_key, sample_n, dist_specs, low_conf = dist_rows
    source_row = cfg["hr"]

    # Anchor source + (optionally) a separate distribution source.
    anchor_key = source_row[5]
    # Map each entry back to a SOURCES key by matching the citation fragment.
    anchor_source_key = _source_key_for(dist_key)

    anchor_source_id = get_or_create_source(c, "peto2017")
    cohort_source_id = anchor_source_id
    for key, src in SOURCES.items():
        if src[0] == cfg["hr"][5]:
            cohort_source_id = get_or_create_source(c, key)
            break

    bid, created = get_or_create_biomarker(c, slug, cfg)
    action = "ADD" if created else "UPD"
    print(f"  [{action}] {slug:<42} {cfg['name'][:46]}")

    if dry_run:
        return dict(slug=slug, created=created, biomarker_id=bid, dry_run=True)

    # ---- distributions (6 canonical strata) --------------------------------
    c.execute("DELETE FROM population_distribution WHERE biomarker_id=?", (bid,))
    dist_ids = {}
    all_dist = None
    for (sex, age_band, mean, sd) in dist_specs:
        # Apply the shared stratum offset for sex/age-specific rows so the
        # curated pooled mean is respected but strata stay internally coherent.
        scale = stratum_offset(sex, age_band, sd)
        if (sex, age_band) != ("all", "all"):
            mean = mean * scale
        p5, p25, p50, p75, p95 = nq(mean, sd)
        cur = c.execute(
            """
            INSERT INTO population_distribution
            (biomarker_id, source_id, sex, age_band, mean, sd, p5, p25, p50, p75,
             p95, unit, sample_n, survey_cycle, is_low_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bid, anchor_source_id, sex, age_band, round(mean, 4), round(sd, 4),
             p5, p25, p50, p75, p95, cfg["units"], sample_n,
             "Peto et al. 2017 (MortalityPredictors.org) anchor cohort",
             1 if low_conf else 0),
        )
        dist_ids[(sex, age_band)] = cur.lastrowid
        if (sex, age_band) == ("all", "all"):
            all_dist = (mean, sd, p5, p50, p95)

    if all_dist is None:
        raise ValueError(f"{slug}: missing all/all distribution stratum")

    # ---- mortality association --------------------------------------------
    hr, hr_type, ci_lo, ci_hi, direction, cohort, n = cfg["hr"]
    c.execute(
        "DELETE FROM mortality_association WHERE biomarker_id=? AND source_id=?",
        (bid, cohort_source_id),
    )
    c.execute(
        """
        INSERT INTO mortality_association
        (biomarker_id, source_id, hazard_ratio, hr_type, hr_unit_scale, ci_lower,
         ci_upper, p_value, direction, cohort_description, n, events,
         follow_up_years, population_type, adjustment_covariates, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (bid, cohort_source_id, hr, hr_type, 1.0, ci_lo, ci_hi, None, direction,
         cohort, n, None, None, "general",
         "Age, sex, and study-specific covariates (see source)", cfg["notes"]),
    )

    # ---- HR curves + HRFunction + optimization model ----------------------
    base = build_curve(cfg, all_dist)
    mean_all, sd_all, _, p50_all, _ = all_dist

    base = calibrate_curve(c, base, all_dist, TARGET_RHR_RANGE)

    c.execute("DELETE FROM biomarker_hr_curve WHERE biomarker_id=?", (bid,))
    c.execute("DELETE FROM hr_function WHERE biomarker_id=?", (bid,))
    for (sex, age_band) in STRATA:
        scale = stratum_offset(sex, age_band, sd_all)
        mean_s = mean_all * (scale if (sex, age_band) != ("all", "all") else 1.0)
        sd_s = sd_all
        ref_s = base["reference_value"] * (
            scale if (sex, age_band) != ("all", "all") else 1.0
        )

        params = dict(base["parameters"])
        if base["curve_type"] == "quadratic":
            x_opt = params.get("x_opt", ref_s)
            if (sex, age_band) != ("all", "all"):
                x_opt = x_opt * scale
                a = (base["parameters"].get("a", 0.0))
                params = {"a": a, "x_opt": round(x_opt, 6)}
            optimal_value = round(params["x_opt"], 6)
        else:
            # Preserve the per-SD log(HR) the pooled fit was calibrated to.
            # For log_log, d(ln HR)/d(x) = beta / x, so a stratum whose
            # reference is `ref_s` needs beta_s = (ln HR per SD) * ref_s / sd.
            # For linear_log the slope does not scale with the reference.
            sign = -1.0 if base["directionality"] == "higher_better" else 1.0
            beta_pooled = base["parameters"]["beta"]
            if base["curve_type"] == "log_log" and sd_s > 0:
                slope_per_ln = abs(beta_pooled) / max(base["reference_value"], 1e-9)
                params = {"beta": round(sign * slope_per_ln * ref_s / sd_s, 6)}
            else:
                params = {"beta": round(beta_pooled, 6)}
            optimal_value = None

        note = f"Peto et al. 2017 (PMID 28858850) anchor; {cfg['evidence_tier']}" + (
            f" [stratum {sex}/{age_band} derived from pooled HR]" if (sex, age_band) != ("all", "all") else ""
        )
        c.execute(
            """
            INSERT INTO biomarker_hr_curve
            (biomarker_id, sex, age_band, curve_type, reference_value, optimal_value,
             parameters, valid_min, valid_max, citation_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bid, sex, age_band, base["curve_type"], round(ref_s, 6), optimal_value,
             json.dumps(params), base["valid_min"], base["valid_max"], note),
        )
        c.execute(
            """
            INSERT OR REPLACE INTO hr_function
            (biomarker_id, sex, age_band, fit_type, parameters, domain_min,
             domain_max, reference_value, shape, nadir_value, source_id,
             fit_quality_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bid, sex, age_band, FIT_TYPE_MAP[base["curve_type"]], json.dumps(params),
             base["valid_min"], base["valid_max"], round(ref_s, 6), base["shape"],
             optimal_value, anchor_source_id,
             f"{cfg['evidence_tier']}: synthesized from anchor HR={hr} ({hr_type})"),
        )

    # ---- optimization model + expected values -----------------------------
    c.execute("DELETE FROM biomarker_optimization_model WHERE biomarker_id=?", (bid,))
    c.execute("DELETE FROM biomarker_expected_value WHERE biomarker_id=?", (bid,))

    if all_dist[1] <= 0:
        print(f"      ! {slug}: unusable SD, skipping optimization layer")
        return dict(slug=slug, created=created, biomarker_id=bid)

    curve_row = c.execute(
        "SELECT curve_type, reference_value, optimal_value, parameters, valid_min, valid_max "
        "FROM biomarker_hr_curve WHERE biomarker_id=? AND sex='all' AND age_band='all'",
        (bid,),
    ).fetchone()
    curve_type, ref, curve_opt, params_json, cv_min, cv_max = curve_row
    params = json.loads(params_json) if params_json else {}
    if curve_opt is not None:
        params.setdefault("x_opt", curve_opt)

    v_min_eff = cv_min if cv_min is not None else (0.0 if mean_all > 0 else -5 * sd_all)
    v_max_eff = cv_max if cv_max is not None else (mean_all + 5 * sd_all)
    if v_max_eff <= v_min_eff:
        v_min_eff = 0.0 if mean_all > 0 else -5 * sd_all
        v_max_eff = mean_all + 5 * sd_all

    x_bins, probs = generate_population_distribution(
        mean=mean_all, sd=sd_all, valid_min=v_min_eff, valid_max=v_max_eff,
        n_bins=300, p5=all_dist[2], p50=all_dist[3], p95=all_dist[4],
    )
    base_ehr, base_hrs = compute_baseline_expected_hazard(
        x_bins, probs, curve_type, ref, params, curve_opt
    )

    p25_row = c.execute(
        "SELECT p25, p75 FROM population_distribution "
        "WHERE biomarker_id=? AND sex='all' AND age_band='all'", (bid,)
    ).fetchone()
    pop_p25, pop_p75 = p25_row if p25_row else (None, None)

    c.execute(
        """
        INSERT INTO biomarker_optimization_model
        (biomarker_id, relationship_type, causal_status, baseline_expected_hr,
         pop_mean, pop_sd, pop_median, pop_p25, pop_p75, optimal_target)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (bid, base["shape"].upper(), cfg.get("causal_status", "OBSERVATIONAL"),
         base_ehr, mean_all, sd_all, all_dist[3],
         pop_p25 if pop_p25 is not None else all_dist[3],
         pop_p75 if pop_p75 is not None else all_dist[3],
         curve_opt if curve_opt is not None else all_dist[3]),
    )

    scenarios = c.execute(
        "SELECT id, shift_type, shift_magnitude FROM optimization_scenario"
    ).fetchall()
    for sc_id, sc_type, sc_mag in scenarios:
        res = compute_shift_optimization(
            x_bins=x_bins, probabilities=probs, baseline_hrs=base_hrs,
            curve_type=curve_type, reference_value=ref, parameters=params,
            valid_min=v_min_eff, valid_max=v_max_eff,
            directionality=cfg["directionality"], pop_sd=sd_all,
            shift_type=sc_type, shift_magnitude=sc_mag,
            optimal_value=curve_opt, pop_median=all_dist[3],
            pop_p25=pop_p25, pop_p75=pop_p75,
        )
        c.execute(
            """
            INSERT INTO biomarker_expected_value
            (biomarker_id, scenario_id, baseline_expected_hr, optimized_expected_hr,
             delta_hr, relative_hazard_reduction, domain_status,
             fraction_out_of_domain, mean_individual_benefit,
             median_individual_benefit, p10_benefit, p25_benefit, p75_benefit,
             p90_benefit, max_individual_benefit, fraction_benefiting,
             fraction_harmed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bid, sc_id, res["baseline_expected_hr"], res["optimized_expected_hr"],
             res["delta_hr"], res["relative_hazard_reduction"], res["domain_status"],
             res["fraction_out_of_domain"], res["mean_individual_benefit"],
             res["median_individual_benefit"], res["p10_benefit"], res["p25_benefit"],
             res["p75_benefit"], res["p90_benefit"], res["max_individual_benefit"],
             res["fraction_benefiting"], res["fraction_harmed"]),
        )

    rhr1 = c.execute(
        "SELECT relative_hazard_reduction FROM biomarker_expected_value "
        "WHERE biomarker_id=? AND scenario_id=3", (bid,)
    ).fetchone()
    if rhr1:
        print(f"      1-SD RHR = {rhr1[0] * 100:6.2f}%   base E[HR] = {base_ehr:6.3f}"
              f"   curve={curve_type:<10} "
              f"{json.dumps(base['parameters'], separators=(',', ':'))}")

    return dict(slug=slug, created=created, biomarker_id=bid)


def _source_key_for(dist_key):
    return dist_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Restrict to these biomarker slugs")
    args = parser.parse_args()

    slugs = sorted(BIOMARKERS)
    if args.only:
        missing = [s for s in args.only if s not in BIOMARKERS]
        if missing:
            raise SystemExit(f"Unknown slugs: {missing}")
        slugs = args.only

    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys=ON")

    global TARGET_RHR_RANGE
    TARGET_RHR_RANGE = _catalog_target_range(c)

    print(f"[MortalityPredictors gap ingestion] {len(slugs)} biomarkers"
          f"{' (dry run)' if args.dry_run else ''}")
    print(f"  CpG governance: {CPG_COVERAGE['probe_count']} probes roll up to "
          f"'{CPG_COVERAGE['target_slug']}' (no new catalog rows)")
    print(f"  Calibration target: 1-SD RHR in "
          f"{TARGET_RHR_RANGE[0] * 100:.1f}-{TARGET_RHR_RANGE[1] * 100:.1f}% "
          f"(measured from the pre-existing catalog)")
    print()

    added = updated = 0
    for slug in slugs:
        res = ingest_one(c, slug, BIOMARKERS[slug], dry_run=args.dry_run)
        if res.get("dry_run"):
            continue
        if res["created"]:
            added += 1
        else:
            updated += 1

    if not args.dry_run:
        c.commit()
        total = c.execute("SELECT COUNT(*) FROM biomarker").fetchone()[0]
        with_dist = c.execute(
            "SELECT COUNT(DISTINCT biomarker_id) FROM population_distribution"
        ).fetchone()[0]
        with_curve = c.execute(
            "SELECT COUNT(DISTINCT biomarker_id) FROM biomarker_hr_curve"
        ).fetchone()[0]
        with_ev = c.execute(
            "SELECT COUNT(DISTINCT biomarker_id) FROM biomarker_expected_value"
        ).fetchone()[0]
        print()
        print(f"  biomarkers added={added} updated={updated}")
        print(f"  catalog total          : {total}")
        print(f"  with distribution      : {with_dist}")
        print(f"  with HR curve          : {with_curve}")
        print(f"  with expected values   : {with_ev}")
    else:
        print("\n  (dry run: no writes made)")
    c.close()


if __name__ == "__main__":
    main()
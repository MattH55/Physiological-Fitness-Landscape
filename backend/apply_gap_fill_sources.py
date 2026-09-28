"""
Apply real, verified literature sources to the 55 gap-fill biomarkers (ids
51-111) that previously carried only a placeholder HR=1.25 "default_assumed"
mortality association (see backfill_mortality_associations.py and
add_missing_curves_and_expected_values.py for why that placeholder exists).

Input: five JSON files produced by literature-research passes, each keyed by
biomarker slug, with fields: found, citation, pmid, doi, year, cohort, hr,
hr_ci_low, hr_ci_high, comparison, outcome, direction, notes. Every entry was
independently spot-checked against PubMed/Europe PMC before this script was
written; comparison types are converted to hr_type/hr_unit_scale as follows:

  per_sd            -> hr_type='per_sd', hr_unit_scale=1.0, hazard_ratio as-is
  quartile_extreme  -> hr_type='quartile_extreme'
  tertile_extreme   -> hr_type='tertile_extreme'
  per_unit          -> converted to an equivalent per-SD HR using the
                       biomarker's own population SD (log_hr_per_sd =
                       log(hr_per_unit) * sd_native_units), stored as per_sd
  per_doubling      -> converted to per-SD via log(hr)/log(2) * (sd/mean)
                       (log-normal approximation), stored as per_sd
  threshold         -> stored as quartile_extreme (coarse category
                       approximation, consistent with how every other
                       dichotomous/threshold association in this database is
                       already handled by fit_curve_for_biomarker)

A biomarker whose entry has found=false (currently only pai-1) is left
untouched — it keeps its honest "no published source" declaration from
backfill_curve_citation_provenance.py.

This script is idempotent: it will not insert a duplicate mortality_association
for a biomarker that already has one sourced from the same PMID/DOI, and reruns
simply update the curve/function rows to match.

Usage:
    python backend/apply_gap_fill_sources.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "mortality_biomarkers.db"
RESEARCH_DIR = Path(
    r"C:\Users\matth\AppData\Local\Temp\claude\c--Users-matth-OneDrive-Documents-OpenSourceMed-Physiological-Fitness-Landscape"
    r"\01fef164-2781-4754-96d2-b623593ac0f9\scratchpad\gap_research"
)

sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3

from backend.add_missing_curves_and_expected_values import (
    STRATA,
    fit_curve_for_biomarker,
)

QUARTILE_LOGSD = 1.2816

# For "per_unit" comparisons where the study's reported increment is not
# literally 1 native unit (e.g. "per 0.1 m/s", "per 5-year increment"),
# override the increment size here so the per-SD conversion is correct.
PER_UNIT_INCREMENT_OVERRIDE = {
    "waist-height-ratio": 0.1,
    "gait-speed": 0.1,
    "monocyte-count": 0.1,
    "dna-methylation-age": 5.0,
}

# testosterone's "per_unit" entry is not a real per-native-unit Cox slope —
# the research notes are explicit that it's a coarse summary effect from a
# nonlinear/U-shaped dose-response curve, not a single per-ng/dL multiplier.
# Compounding that across ~200 ng/dL of SD collapses the HR toward zero, so
# route it through the same coarse-category math as quartile_extreme instead.
FORCE_QUARTILE_EXTREME = {"testosterone"}


def load_research() -> dict:
    merged = {}
    for i in range(1, 6):
        path = RESEARCH_DIR / f"batch{i}.json"
        with open(path, encoding="utf-8") as f:
            merged.update(json.load(f))
    return merged


def convert_to_stored_hr(entry: dict, slug: str, sd: float, mean: float) -> tuple[float, str, float]:
    """Return (hazard_ratio, hr_type, hr_unit_scale) in this DB's convention."""
    comparison = entry["comparison"]
    hr = float(entry["hr"])

    if slug in FORCE_QUARTILE_EXTREME:
        return hr, "quartile_extreme", 1.0
    if comparison == "per_sd":
        return hr, "per_sd", 1.0
    if comparison in ("quartile_extreme", "tertile_extreme"):
        return hr, comparison, 1.0
    if comparison == "threshold":
        # Coarse extreme-category approximation, consistent with how the
        # rest of this codebase treats dichotomous associations.
        return hr, "quartile_extreme", 1.0
    if comparison == "per_unit":
        if not sd or sd <= 0:
            return hr, "quartile_extreme", 1.0
        increment = PER_UNIT_INCREMENT_OVERRIDE.get(slug, 1.0)
        log_hr_per_native_unit = math.log(hr) / increment
        log_hr_per_sd = log_hr_per_native_unit * sd
        return math.exp(log_hr_per_sd), "per_sd", 1.0
    if comparison == "per_doubling":
        if not sd or not mean or mean <= 0:
            return hr, "quartile_extreme", 1.0
        # log-normal approx: a doubling ~= exp(sd/mean) in relative terms
        log_hr_per_doubling = math.log(hr)
        log_hr_per_sd = log_hr_per_doubling * (sd / mean) / math.log(2)
        return math.exp(log_hr_per_sd), "per_sd", 1.0
    return hr, "quartile_extreme", 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    research = load_research()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    applied, skipped_found_false, skipped_existing = [], [], []

    for slug, entry in sorted(research.items()):
        row = cur.execute(
            "SELECT id, directionality FROM biomarker WHERE slug=?", (slug,)
        ).fetchone()
        if not row:
            print(f"  ! {slug}: no biomarker row found, skipping")
            continue
        bid, direction = row

        if not entry.get("found"):
            skipped_found_false.append(slug)
            continue

        existing = cur.execute(
            "SELECT ma.id FROM mortality_association ma JOIN source s ON ma.source_id = s.id "
            "WHERE ma.biomarker_id=? AND (s.pmid=? OR (s.doi IS NOT NULL AND s.doi=?))",
            (bid, entry.get("pmid"), entry.get("doi")),
        ).fetchone()
        if existing:
            skipped_existing.append(slug)
            continue

        dist = cur.execute(
            "SELECT mean, sd FROM population_distribution WHERE biomarker_id=? "
            "AND sex='all' AND age_band='all' LIMIT 1",
            (bid,),
        ).fetchone()
        mean, sd = (dist or (None, None))

        if entry.get("hr") is None:
            skipped_found_false.append(f"{slug} (no verified numeric HR)")
            continue

        hr_stored, hr_type, hr_unit_scale = convert_to_stored_hr(entry, slug, sd, mean)

        ci_lower, ci_upper = entry.get("hr_ci_low"), entry.get("hr_ci_high")
        ci_note = ""
        if ci_lower is None or ci_upper is None:
            # CI not confirmable from available text; approximate +/-15% around
            # the point estimate on the reported (not converted) HR so the
            # NOT NULL constraint is satisfiable without inventing precision.
            ci_lower, ci_upper = round(entry["hr"] * 0.85, 3), round(entry["hr"] * 1.15, 3)
            ci_note = " [CI approximated +/-15% around point estimate; not from source text.]"

        print(
            f"  + {slug:<26} HR={entry['hr']:<6} ({entry['comparison']:<16}) "
            f"-> stored HR={hr_stored:.3f} {hr_type:<16} dir={entry['direction']} "
            f"pmid={entry.get('pmid')}"
        )

        if args.dry_run:
            applied.append(slug)
            continue

        cur.execute(
            """
            INSERT INTO source (citation, pmid, doi, year, study_design, identifier_type, identifier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["citation"],
                entry.get("pmid"),
                entry.get("doi"),
                entry.get("year"),
                entry.get("cohort", ""),
                "pmid" if entry.get("pmid") else ("doi" if entry.get("doi") else None),
                entry.get("pmid") or entry.get("doi"),
            ),
        )
        source_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO mortality_association
            (biomarker_id, source_id, hazard_ratio, hr_type, hr_unit_scale,
             ci_lower, ci_upper, direction, cohort_description, population_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'general', ?)
            """,
            (
                bid, source_id, hr_stored, hr_type, hr_unit_scale,
                ci_lower, ci_upper,
                entry["direction"], entry.get("cohort", ""),
                (
                    f"Reported as {entry['comparison']} HR={entry['hr']} for "
                    f"{entry.get('outcome', 'all-cause mortality')}.{ci_note} {entry.get('notes', '')}"
                )[:500],
            ),
        )

        # Recompute the HR curve/function from this real association,
        # replacing the default_assumed=1.25 placeholder.
        curve = fit_curve_for_biomarker(conn, bid)
        if curve:
            fit_type_map = {
                "log_log": "log_log",
                "linear_log": "log_linear_per_sd",
                "quadratic": "quadratic_u_shaped",
            }
            fit_type = fit_type_map[curve["curve_type"]]
            shape = (
                "u_shaped"
                if curve["curve_type"] == "quadratic"
                else ("monotonic_increasing" if curve["directionality"] == "lower_better"
                      else "monotonic_decreasing")
            )
            for sex, age in STRATA:
                cur.execute(
                    """
                    UPDATE biomarker_hr_curve
                    SET curve_type=?, reference_value=?, optimal_value=?, parameters=?,
                        valid_min=?, valid_max=?, citation_summary=?
                    WHERE biomarker_id=? AND sex=? AND age_band=?
                    """,
                    (
                        curve["curve_type"], curve["reference_value"], curve["optimal_value"],
                        json.dumps(curve["parameters"]), curve["valid_min"], curve["valid_max"],
                        curve["citation_summary"], bid, sex, age,
                    ),
                )
                cur.execute(
                    """
                    UPDATE hr_function
                    SET fit_type=?, parameters=?, domain_min=?, domain_max=?, reference_value=?,
                        shape=?, nadir_value=?, source_id=?, fit_quality_note=?
                    WHERE biomarker_id=? AND sex=? AND age_band=?
                    """,
                    (
                        fit_type, json.dumps(curve["parameters"]), curve["valid_min"],
                        curve["valid_max"], curve["reference_value"], shape,
                        curve["optimal_value"], source_id, curve["citation_summary"],
                        bid, sex, age,
                    ),
                )
        applied.append(slug)

    if not args.dry_run:
        conn.commit()
    conn.close()

    print(f"\nApplied: {len(applied)}  Skipped (found=false): {skipped_found_false}  "
          f"Skipped (already sourced): {skipped_existing}")


if __name__ == "__main__":
    main()

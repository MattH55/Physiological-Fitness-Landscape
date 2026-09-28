"""
One-off data repair for mortality_biomarkers.db:

  1. Unit fixes: population distributions stored in a different unit from the
     biomarker (and its HR curve), which put the population far outside the
     valid domain.
  2. Duplicate biomarkers: 14 markers entered twice under different slugs.
     The hyphen-slug entry is kept (full sex/age strata, existing links); the
     duplicate's cited mortality study moves onto it and its own synthetic
     distributions/curves are dropped.
  3. Duplicate distribution strata: markers with two competing rows for the
     same (sex, age_band). Rows whose citation never measured the marker
     (source 2 = Ridker 2000, a CRP paper) are dropped in favour of the
     marker-specific set; NHANES sets are kept over supplementary ones.
  4. Curves invalidated by the above (or by log_log on a signed domain) are
     refitted with fit_curve_for_biomarker and expected values recomputed.

Usage:
  python backend/fix_units_and_merge_duplicates.py [--db PATH]
"""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.add_missing_curves_and_expected_values import (
    DB_PATH,
    insert_missing_curves,
    compute_and_insert_expected_values,
)

DIST_VALUE_COLS = ("mean", "sd", "p5", "p25", "p50", "p75", "p95")

# (keep_slug, duplicate_slug)
DUPLICATES = [
    ("gdf-15", "gdf15"),
    ("ykl-40", "ykl40"),
    ("beta2-microglobulin", "beta2_microglobulin"),
    ("fib-4", "fib4"),
    ("free-t3", "free_t3"),
    ("igf-1", "igf1"),
    ("dhea-s", "dhea_s"),
    ("eosinophil-count", "eosinophil_count"),
    ("8-ohdg", "8ohdg"),
    ("folate", "serum_folate"),
    ("vitamin-b12", "vitamin_b12"),
    ("selenium", "serum_selenium"),
    ("zinc", "serum_zinc"),
    ("transferrin-sat", "transferrin_saturation"),
]

# Rows of a duplicate that describe the same quantity and are superseded by the kept marker's.
DUPLICATE_DROP_TABLES = [
    "population_distribution",
    "biomarker_hr_curve",
    "hr_function",
    "biomarker_expected_value",
    "distribution_fit",
    "biomarker_optimization_model",
]
# Links that carry over to the kept marker.
DUPLICATE_MOVE_TABLES = [
    ("mortality_association", "biomarker_id"),
    ("intervention", "biomarker_id"),
    ("biomarker_signature", "biomarker_id"),
    ("disease_alteration", "biomarker_id"),
    ("biomarker_test_value", "biomarker_id"),
    ("intervention_biomarker_effect", "biomarker_id"),
    ("biomarker_intervention_effects", "biomarker_id"),
    ("intervention_hazard_impact", "biomarker_id"),
    ("lab_tests", "canonical_biomarker_id"),
]

# Approximate adult mean heights (cm) used to turn waist circumference into waist/height.
HEIGHT_CM = {"M": 175.5, "F": 161.5, "all": 168.5}


def bid_of(c, slug):
    row = c.execute("SELECT id FROM biomarker WHERE slug=?", (slug,)).fetchone()
    return row[0] if row else None


def scale_distributions(c, bid, factor_for_row):
    """Multiply every distribution value column by factor_for_row(sex, age_band)."""
    rows = c.execute(
        "SELECT id, sex, age_band FROM population_distribution WHERE biomarker_id=?", (bid,)
    ).fetchall()
    for rid, sex, age in rows:
        f = factor_for_row(sex, age)
        sets = ", ".join(f"{col} = ROUND({col} * ?, 4)" for col in DIST_VALUE_COLS)
        c.execute(
            f"UPDATE population_distribution SET {sets} WHERE id=?",
            (*([f] * len(DIST_VALUE_COLS)), rid),
        )
    return len(rows)


def drop_curves(c, bid):
    c.execute("DELETE FROM biomarker_hr_curve WHERE biomarker_id=?", (bid,))
    c.execute("DELETE FROM hr_function WHERE biomarker_id=?", (bid,))


def fix_units(c, refit, recompute):
    print("[1] Unit fixes")

    # D-dimer: distribution in ng/mL FEU, marker and curve in ug/mL.
    bid = bid_of(c, "d-dimer")
    n = scale_distributions(c, bid, lambda s, a: 0.001)
    print(f"  d-dimer: {n} rows ng/mL -> ug/mL")
    recompute.add(bid)

    # Waist-to-height ratio: distribution is waist circumference in cm.
    bid = bid_of(c, "waist-height-ratio")
    n = scale_distributions(c, bid, lambda s, a: 1.0 / HEIGHT_CM.get(s, HEIGHT_CM["all"]))
    print(f"  waist-height-ratio: {n} rows waist cm -> waist/height (mean adult heights)")
    recompute.add(bid)

    # DHEA-S: distribution in umol/L, marker in ug/dL (1 umol/L = 36.85 ug/dL).
    bid = bid_of(c, "dhea-s")
    n = scale_distributions(c, bid, lambda s, a: 36.85)
    print(f"  dhea-s: {n} rows umol/L -> ug/dL")
    recompute.add(bid)

    # DNA methylation age: marker is age *acceleration* (years, -20..20) but the
    # distribution held chronological age. Use the acceleration fits already
    # stored in distribution_fit for the same strata.
    bid = bid_of(c, "dna-methylation-age")
    fits = {
        (s, a): json.loads(p)
        for s, a, p in c.execute(
            "SELECT sex, age_band, parameters FROM distribution_fit WHERE biomarker_id=?", (bid,)
        )
    }
    rows = c.execute(
        "SELECT id, sex, age_band FROM population_distribution WHERE biomarker_id=?", (bid,)
    ).fetchall()
    for rid, sex, age in rows:
        p = fits.get((sex, age)) or fits[("all", "all")]
        c.execute(
            "UPDATE population_distribution SET mean=?, sd=?, p5=?, p25=?, p50=?, p75=?, p95=? WHERE id=?",
            (p["mean"], p["sd"], p["p5"], p["p25"], p["p50"], p["p75"], p["p95"], rid),
        )
    print(f"  dna-methylation-age: {len(rows)} rows chronological age -> age acceleration")
    refit.add(bid)

    # BMD T-score: log_log curve on a signed domain (ln of negative T-scores) — refit.
    refit.add(bid_of(c, "bmd-tscore"))
    print("  bmd-tscore: log_log curve on signed domain -> refit")

    # 8-OHdG: values (~4 ng/mg creatinine) and specimen are urinary; unit label was DNA-based.
    c.execute("UPDATE biomarker SET units='ng/mg creatinine' WHERE slug='8-ohdg'")
    print("  8-ohdg: unit label pmol/mol DNA -> ng/mg creatinine")


def dedupe_strata(c, refit, recompute):
    print("[2] Duplicate distribution strata")
    # Placeholder rows citing a paper that never measured the marker.
    for slug in ("supar", "stnfr1", "lmr"):
        bid = bid_of(c, slug)
        n = c.execute(
            "DELETE FROM population_distribution WHERE biomarker_id=? AND source_id=2", (bid,)
        ).rowcount
        print(f"  {slug}: dropped {n} placeholder rows (source 2)")
        recompute.add(bid)
    # sTNFR1 and LMR curves were anchored on the dropped placeholder medians.
    refit.update({bid_of(c, "stnfr1"), bid_of(c, "lmr")})

    # Remaining duplicates: keep the first (NHANES) row per stratum.
    dup = c.execute(
        """SELECT p.id FROM population_distribution p
           WHERE EXISTS (SELECT 1 FROM population_distribution q
                         WHERE q.biomarker_id=p.biomarker_id AND q.sex=p.sex
                           AND q.age_band=p.age_band AND q.id < p.id)"""
    ).fetchall()
    for (rid,) in dup:
        bid = c.execute("SELECT biomarker_id FROM population_distribution WHERE id=?", (rid,)).fetchone()[0]
        recompute.add(bid)
        c.execute("DELETE FROM population_distribution WHERE id=?", (rid,))
    print(f"  dropped {len(dup)} supplementary rows duplicating an NHANES stratum")


def merge_duplicates(c, refit, recompute):
    print("[3] Duplicate biomarkers")
    for keep_slug, dup_slug in DUPLICATES:
        keep, dup = bid_of(c, keep_slug), bid_of(c, dup_slug)
        if keep is None or dup is None:
            print(f"  skip {keep_slug}/{dup_slug} (already merged)")
            continue
        k = c.execute("SELECT aliases, notes, directionality FROM biomarker WHERE id=?", (keep,)).fetchone()
        d = c.execute("SELECT name, aliases, notes, units FROM biomarker WHERE id=?", (dup,)).fetchone()

        aliases = json.loads(k[0] or "[]")
        for a in [dup_slug, d[0], *json.loads(d[1] or "[]")]:
            if a and a not in aliases:
                aliases.append(a)
        notes = k[1] or ""
        if d[2] and d[2] not in notes:
            notes = (notes + " " if notes else "") + d[2]
        c.execute("UPDATE biomarker SET aliases=?, notes=? WHERE id=?", (json.dumps(aliases), notes, keep))

        # Transferrin saturation: the kept distribution is not a saturation (mean 138%).
        if keep_slug == "transferrin-sat":
            c.execute("DELETE FROM population_distribution WHERE biomarker_id=?", (keep,))
            c.execute("UPDATE population_distribution SET biomarker_id=? WHERE biomarker_id=?", (keep, dup))

        # Monotonic label contradicting the (now attached) cited study follows the study.
        assoc_dir = c.execute(
            "SELECT direction FROM mortality_association WHERE biomarker_id=? LIMIT 1", (dup,)
        ).fetchone()
        if assoc_dir and k[2] in ("higher_better", "lower_better") and assoc_dir[0] in ("higher_worse", "lower_worse"):
            label = "lower_better" if assoc_dir[0] == "higher_worse" else "higher_better"
            if label != k[2]:
                c.execute("UPDATE biomarker SET directionality=? WHERE id=?", (label, keep))
                print(f"  {keep_slug}: directionality {k[2]} -> {label} (per cited study)")

        for table, col in DUPLICATE_MOVE_TABLES:
            c.execute(f"UPDATE {table} SET {col}=? WHERE {col}=?", (keep, dup))
        for table in DUPLICATE_DROP_TABLES:
            c.execute(f"DELETE FROM {table} WHERE biomarker_id=?", (dup,))
        c.execute("DELETE FROM biomarker WHERE id=?", (dup,))
        print(f"  {dup_slug} ({d[3]}) -> {keep_slug}")
        refit.add(keep)


def main():
    db_path = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else DB_PATH
    c = sqlite3.connect(db_path)
    refit, recompute = set(), set()

    fix_units(c, refit, recompute)
    dedupe_strata(c, refit, recompute)
    merge_duplicates(c, refit, recompute)

    print(f"[4] Refitting curves for {len(refit)} biomarkers")
    for bid in refit:
        drop_curves(c, bid)
    insert_missing_curves(c)  # fits every biomarker left without a curve
    compute_and_insert_expected_values(c, biomarker_ids=refit | recompute)

    c.commit()
    c.execute("VACUUM")
    c.close()


if __name__ == "__main__":
    main()

"""
Ingest the second MortalityPredictors.org gap batch (20 biomarkers, see
`backend/mortalitypredictors_batch2_data.py`) using the exact same pipeline
`backend/seed_mortalitypredictors_gaps.py` already uses for the first 82
(biomarker -> source -> population_distribution -> mortality_association ->
biomarker_hr_curve -> hr_function -> biomarker_optimization_model ->
biomarker_expected_value), reused via import rather than duplicated.

One deliberate fix over the original pipeline: `ingest_one()` always attaches
`population_distribution.source_id` to the generic Peto et al. 2017 anchor
citation, regardless of what a marker's own distribution numbers were
actually drawn from. Since every marker in this batch has real citations for
its own distribution parameters (see `dist_source` in BIOMARKERS), this
script re-points `population_distribution.source_id` to that real source
after ingestion, for this batch's biomarkers only — the original 82 are left
untouched.

Usage:
  python backend/ingest_mortalitypredictors_batch2.py --dry-run
  python backend/ingest_mortalitypredictors_batch2.py
"""

import argparse
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.seed_mortalitypredictors_gaps as smp  # noqa: E402
from backend.mortalitypredictors_batch3_data import (  # noqa: E402
    BIOMARKERS as NEW_BIOMARKERS,
    DISTRIBUTIONS as NEW_DIST,
    SOURCES as NEW_SOURCES,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mortality_biomarkers.db")

STRATA = smp.STRATA


def build_dist_specs(mean, sd):
    """Same pooled mean/sd for every canonical stratum; ingest_one() applies
    the shared sex/age stratum_offset() on top of this, exactly as it does
    for the pre-existing 82-biomarker batch when only a pooled estimate is
    available."""
    return [(sex, age_band, mean, sd) for (sex, age_band) in STRATA]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    # Splice this batch's sources/biomarkers into the imported module's
    # globals so the reused ingest_one() can resolve them via SOURCES[key] /
    # BIOMARKERS[slug] lookups exactly as it does for the first 82.
    smp.SOURCES.update(NEW_SOURCES)
    smp.BIOMARKERS.update(NEW_BIOMARKERS)
    for slug, (mean, sd, n, low_conf) in NEW_DIST.items():
        smp.DISTRIBUTIONS[slug] = ("mp2_pooled", n, build_dist_specs(mean, sd), low_conf)

    slugs = sorted(NEW_BIOMARKERS)
    if args.only:
        missing = [s for s in args.only if s not in NEW_BIOMARKERS]
        if missing:
            raise SystemExit(f"Unknown slugs: {missing}")
        slugs = args.only

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")

    smp.TARGET_RHR_RANGE = smp._catalog_target_range(conn)
    print(f"[MortalityPredictors batch 3] {len(slugs)} biomarkers"
          f"{' (dry run)' if args.dry_run else ''}")
    print(f"  Calibration target: 1-SD RHR in "
          f"{smp.TARGET_RHR_RANGE[0] * 100:.1f}-{smp.TARGET_RHR_RANGE[1] * 100:.1f}%\n")

    added = updated = 0
    for slug in slugs:
        res = smp.ingest_one(conn, slug, NEW_BIOMARKERS[slug], dry_run=args.dry_run)
        if res.get("dry_run"):
            continue
        if res["created"]:
            added += 1
        else:
            updated += 1

    if args.dry_run:
        print("\nDry run - no changes written.")
        return

    # Re-point population_distribution.source_id to each marker's own real
    # distribution citation, where one was identified (dist_source), instead
    # of the generic Peto anchor ingest_one() always uses.
    cur = conn.cursor()
    repointed = 0
    for slug, cfg in NEW_BIOMARKERS.items():
        dist_source_key = cfg.get("dist_source")
        if not dist_source_key:
            continue
        source_id = smp.get_or_create_source(conn, dist_source_key)
        bid = cur.execute("SELECT id FROM biomarker WHERE slug=?", (slug,)).fetchone()[0]
        cur.execute(
            "UPDATE population_distribution SET source_id=? WHERE biomarker_id=?",
            (source_id, bid),
        )
        repointed += 1
    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM biomarker").fetchone()[0]
    print(f"\nAdded: {added}  Updated: {updated}  "
          f"Distribution sources re-pointed to real citations: {repointed}")
    print(f"Total biomarkers in catalog: {total}")
    conn.close()


if __name__ == "__main__":
    main()

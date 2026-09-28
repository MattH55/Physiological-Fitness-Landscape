"""Refresh baseline E[HR_0] for every biomarker_optimization_model row.

Run after a change to ``optimization_engine`` that affects HR evaluation: the
stored ``baseline_expected_hr`` is the value the optimization simulator and the
leaderboard compare against, so it must be recomputed from the current engine
rather than left at whatever the seeding pass happened to write.

Usage:
    python backend/recompute_baseline_expected_hr.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.backfill_optimization_models import build_model_row
from backend.models import Biomarker, BiomarkerOptimizationModel

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"


def recompute_all(db: Session, dry_run: bool = False) -> dict:
    stats = {"checked": 0, "updated": 0, "skipped": 0, "out_of_range": []}
    rows = (
        db.query(BiomarkerOptimizationModel)
        .join(Biomarker, Biomarker.id == BiomarkerOptimizationModel.biomarker_id)
        .order_by(BiomarkerOptimizationModel.biomarker_id)
        .all()
    )
    for row in rows:
        bm = db.get(Biomarker, row.biomarker_id)
        fresh = build_model_row(bm)
        stats["checked"] += 1
        if fresh is None:
            stats["skipped"] += 1
            continue
        old = float(row.baseline_expected_hr or 0.0)
        new = float(fresh.baseline_expected_hr)
        changed = abs(new - old) > 1e-9
        if changed:
            stats["updated"] += 1
            print(f"  [{bm.slug}] E[HR_0] {old:.4f} -> {new:.4f}")
            if not dry_run:
                row.baseline_expected_hr = new
                row.pop_mean = fresh.pop_mean
                row.pop_sd = fresh.pop_sd
                row.pop_median = fresh.pop_median
                row.pop_p25 = fresh.pop_p25
                row.pop_p75 = fresh.pop_p75
                row.relationship_type = fresh.relationship_type
                row.optimal_target = fresh.optimal_target
        if not (0.5 <= new <= 5.0):
            stats["out_of_range"].append((bm.slug, new))
    if not dry_run:
        db.commit()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")
    SessionFactory = sessionmaker(bind=engine)
    db: Session = SessionFactory()
    try:
        print(f"[*] Recomputing baseline E[HR_0] in {args.db}")
        stats = recompute_all(db, dry_run=args.dry_run)
        print(
            f"[+] checked={stats['checked']} updated={stats['updated']} "
            f"skipped={stats['skipped']}"
        )
        if stats["out_of_range"]:
            print("[!] Outside the [0.5, 5.0] review band:")
            for slug, val in stats["out_of_range"]:
                print(f"      {slug}: {val:.4f}")
        if not args.dry_run:
            print("[+] Committed.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
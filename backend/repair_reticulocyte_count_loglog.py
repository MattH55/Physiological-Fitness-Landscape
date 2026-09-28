"""
Repair the malformed ``log_log`` fit for the reticulocyte-count series.

Defect
------
``reticulocyte-count`` is measured in 10^6 cells/uL (as a fraction: mean 0.054,
p5 0.0195, p95 0.0885, domain [0.005, 0.25]). Its ``hr_function`` and
``biomarker_hr_curve`` rows carry ``fit_type="log_log"`` with beta in the
5.7-7.1 range, synthesized by ``add_missing_curves_and_expected_values.py``
from the external-cohort anchor ``HR=1.24 (tertile_extreme)``.

A log_log fit of ln(HR) = beta * (ln x - ln ref) with beta ~ 6 makes HR a
function of the *fold-change* over the full reported range, so across the
population's own spread (p95/p5 = 4.5x) it produces HR ~ e^9 -- far outside the
numerator the beta was derived from. The anchor itself implies the correct
slope: with ref at the population median, the tertile-extreme contrast is
HR ~ 1.24 across roughly the p5-p95 span, i.e.

    beta = ln(1.24) / ln(p95 / ref) ~ 0.44   (all/all)

The stored coefficient is ~14x steeper than its own anchor, which drives
E[HR_0] to 5.07 across a distribution whose members sit at HR ~ 1 by
construction.

Repair
------
Re-derive beta from the documented anchor rather than inventing a new one, and
rescale the whole sex/age series by the same factor so the fitted pattern is
preserved while the magnitude is corrected:

    beta_new = beta_old * (target_beta_allall / beta_old_allall)

``is_low_confidence`` on the population distributions means the shape is
already flagged as weakly supported, so only the magnitude is repairable here.

Usage:
    python backend/repair_reticulocyte_count_loglog.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.models import Biomarker, BiomarkerHRCurve, HRFunction
from backend.recompute_baseline_expected_hr import recompute_all

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"

SLUG = "reticulocyte-count"
ANCHOR_HR = 1.24


def _params(raw):
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def target_beta(dist_p50: float, dist_p95: float, ref: float) -> float:
    """beta implied by the anchor: ln(HR) = beta * ln(p95/ref) at p95."""
    return math.log(ANCHOR_HR) / math.log(dist_p95 / ref)


def restore() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")
    SessionFactory = sessionmaker(bind=engine)
    db: Session = SessionFactory()
    try:
        bm = db.query(Biomarker).filter(Biomarker.slug == SLUG).first()
        if bm is None:
            print(f"[!] {SLUG} not found")
            return 1

        all_dist = next(
            (d for d in bm.population_distributions if d.sex == "all" and d.age_band == "all"),
            None,
        )
        if all_dist is None or all_dist.p95 is None or all_dist.p50 is None:
            print(f"[!] {SLUG} missing all/all distribution percentiles")
            return 1

        anchor_func = next(
            (
                f
                for f in db.query(HRFunction)
                .filter(HRFunction.biomarker_id == bm.id)
                .all()
                if (f.sex or "all") == "all" and (f.age_band or "all") == "all"
            ),
            None,
        )
        if anchor_func is None:
            print(f"[!] {SLUG} missing all/all hr_function")
            return 1

        old_beta = float(_params(anchor_func.parameters).get("beta", 0.0))
        want_beta = target_beta(float(all_dist.p50), float(all_dist.p95), float(anchor_func.reference_value))
        scale = want_beta / old_beta if old_beta else 0.0
        print(
            f"[*] {SLUG}: anchor HR={ANCHOR_HR} over p50={all_dist.p50} -> p95={all_dist.p95}\n"
            f"    all/all beta {old_beta:.6f} -> {want_beta:.6f} (scale {scale:.6f})"
        )

        stats = {"hr_function": 0, "hr_curve": 0}
        for func in db.query(HRFunction).filter(HRFunction.biomarker_id == bm.id).all():
            params = _params(func.parameters)
            if func.fit_type != "log_log" or "beta" not in params:
                continue
            new_beta = float(params["beta"]) * scale
            stats["hr_function"] += 1
            print(f"    hr_function id={func.id} {func.sex}|{func.age_band} beta "
                  f"{float(params['beta']):.6f} -> {new_beta:.6f}")
            if not args.dry_run:
                func.parameters = {**params, "beta": new_beta}

        for curve in db.query(BiomarkerHRCurve).filter(BiomarkerHRCurve.biomarker_id == bm.id).all():
            params = _params(curve.parameters)
            if curve.curve_type != "log_log" or "beta" not in params:
                continue
            new_beta = float(params["beta"]) * scale
            stats["hr_curve"] += 1
            print(f"    biomarker_hr_curve id={curve.id} {curve.sex}|{curve.age_band} beta "
                  f"{float(params['beta']):.6f} -> {new_beta:.6f}")
            if not args.dry_run:
                curve.parameters = {**params, "beta": new_beta}

        if not args.dry_run:
            db.commit()
            print("[*] Refreshing baseline E[HR_0]:")
            rec = recompute_all(db)
            print(f"[+] baselines: {rec}")
            print("[+] Committed.")
        else:
            print("[dry-run] No changes written.")
        print(f"[+] rows: {stats}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(restore())

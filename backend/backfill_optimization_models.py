"""
Backfill missing BiomarkerOptimizationModel rows.

Gap: biomarkers 51-125 (the post-catalog gap-fill set) were seeded with HR
curves, continuous HR functions, and population distributions, but without the
precomputed ``biomarker_optimization_model`` row. 75 biomarkers are affected.
Consumers of that table — the baseline-E[HR_0] / optimization leaderboard path
and ``optimization_engine.compute_shift_optimization`` — silently skip those
markers, so this is a real analytical gap, not just a test-fixture problem.

This script rebuilds the missing rows using exactly the same math and the same
population conventions as ``backend.seed_data``:

  * population moments come from the biomarker's ``sex='all', age_band='all'``
    population_distribution (mean / sd / p25 / p50 / p75),
  * E[HR_0] is computed on 300 discrete bins spanning the HR curve's
    [valid_min, valid_max] domain via ``compute_baseline_expected_hazard``,
  * ``relationship_type`` is the existing ``BiomarkerHRCurve.shape`` /
    ``biomarker.directionality`` mapped onto the four canonical labels,
  * ``optimal_target`` falls back to the HR curve's ``optimal_value`` and then
    to ``biomarker.optimal_target``, and finally to the reference value for
    monotonic markers (where the reference point is the target anchor).

Idempotent: existing rows are left untouched. Re-runnable.

Usage:
    python backend/backfill_optimization_models.py [--dry-run]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.models import (
    Biomarker,
    BiomarkerHRCurve,
    BiomarkerOptimizationModel,
)
from backend.optimization_engine import (
    compute_baseline_expected_hazard,
    generate_population_distribution,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"

# Canonical relationship_type vocabulary (BiomarkerOptimizationModel docstring)
_MONOTONIC_INC = "MONOTONIC_INCREASING"
_MONOTONIC_DEC = "MONOTONIC_DECREASING"
_U_SHAPED = "U_SHAPED"
_J_SHAPED = "J_SHAPED"

# curve.shape values written by generate_stratum_hr_curves / seed_new_biomarkers
_SHAPE_MAP = {
    "monotonic_increasing": _MONOTONIC_INC,
    "monotonic_decreasing": _MONOTONIC_DEC,
    "u_shaped": _U_SHAPED,
    "j_shaped": _J_SHAPED,
    "inverted_u": _U_SHAPED,
}

# biomarker.directionality fallback when the curve carries no shape
_DIRECTIONALITY_MAP = {
    "lower_better": _MONOTONIC_INC,
    "higher_better": _MONOTONIC_DEC,
    "u_shaped": _U_SHAPED,
    "j_shaped": _J_SHAPED,
    "inverted_u": _U_SHAPED,
}


def _finite(v: Any) -> bool:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def _infer_from_slope(curve: BiomarkerHRCurve) -> str:
    """Sample the curve at the domain edges and in the middle to classify it."""
    from backend.optimization_engine import evaluate_hr

    params = curve.parameters or {}
    lo = float(curve.valid_min)
    hi = float(curve.valid_max)
    mid = 0.5 * (lo + hi)

    def hr(v: float) -> float:
        return evaluate_hr(v, curve.curve_type, curve.reference_value, params, curve.optimal_value)

    hr_lo, hr_mid, hr_hi = hr(lo), hr(mid), hr(hi)
    if hr_mid < hr_lo and hr_mid < hr_hi:
        return _U_SHAPED
    if hr_mid < hr_hi and hr_lo < hr_mid:
        return _J_SHAPED
    return _MONOTONIC_INC if hr_hi >= hr_lo else _MONOTONIC_DEC


def classify_relationship(curve: BiomarkerHRCurve, bm: Biomarker) -> str:
    """Map the stored curve shape / directionality onto the canonical vocabulary."""
    shape = (getattr(curve, "shape", None) or "").strip().lower()
    if shape in _SHAPE_MAP:
        return _SHAPE_MAP[shape]

    ctype = (curve.curve_type or "").strip().lower()
    if ctype in ("quadratic", "quadratic_u_shaped"):
        return _U_SHAPED

    direction = (bm.directionality or "").strip().lower()
    if direction in _DIRECTIONALITY_MAP:
        return _DIRECTIONALITY_MAP[direction]

    return _infer_from_slope(curve)


def pick_optimal_target(
    curve: BiomarkerHRCurve, bm: Biomarker, relationship_type: str
) -> float:
    """
    Resolve x* for the optimization model.

    U/J-shaped markers need a genuine interior optimum, so prefer
    ``optimal_value`` / ``optimal_target`` and only fall back to the curve's
    nadir. Monotonic markers have no interior optimum — their reference value
    is the clinically normal anchor and is what the optimizer moves toward.
    """
    for candidate in (curve.optimal_value, bm.optimal_target):
        if candidate is not None and _finite(candidate):
            return float(candidate)

    if relationship_type in (_U_SHAPED, _J_SHAPED):
        nadir = getattr(curve, "nadir_value", None)
        if nadir is not None and _finite(nadir):
            return float(nadir)

    return float(curve.reference_value)


def resolve_population_moments(
    bm: Biomarker,
) -> Optional[Tuple[float, float, float, float, float]]:
    """Return (mean, sd, p25, p50, p75) from the all/all distribution."""
    dist = next(
        (d for d in bm.population_distributions if d.sex == "all" and d.age_band == "all"),
        None,
    )
    if dist is None:
        # Fall back to any distribution so the marker is not silently dropped.
        dist = bm.population_distributions[0] if bm.population_distributions else None
    if dist is None or dist.mean is None:
        return None

    mean = float(dist.mean)
    sd = float(dist.sd) if dist.sd else 0.0
    if not _finite(sd) or sd <= 0:
        # Mirror seed_data.py: derive an SD when the stored one is unusable.
        if dist.p90 is not None and dist.p10 is not None and dist.p90 > dist.p10:
            sd = (float(dist.p90) - float(dist.p10)) / 2.56
        elif mean > 0:
            sd = mean * 0.25
        else:
            sd = 1.0

    p25 = float(dist.p25) if dist.p25 is not None else mean - 0.674 * sd
    p50 = float(dist.p50) if dist.p50 is not None else mean
    p75 = float(dist.p75) if dist.p75 is not None else mean + 0.674 * sd
    return mean, sd, p25, p50, p75


def build_model_row(bm: Biomarker) -> Optional[BiomarkerOptimizationModel]:
    """Construct (but do not add) a BiomarkerOptimizationModel for this biomarker."""
    curve = bm.hr_curve
    if curve is None:
        return None
    moments = resolve_population_moments(bm)
    if moments is None:
        return None
    mean, sd, p25, p50, p75 = moments

    domain_min = curve.valid_min
    domain_max = curve.valid_max
    if domain_min is None or domain_max is None or not float(domain_max) > float(domain_min):
        domain_min = bm.valid_domain_min
        domain_max = bm.valid_domain_max
    if domain_min is None or domain_max is None or not float(domain_max) > float(domain_min):
        domain_min = mean - 4.0 * sd
        domain_max = mean + 4.0 * sd

    x_bins, probs = generate_population_distribution(
        mean=mean,
        sd=sd,
        valid_min=float(domain_min),
        valid_max=float(domain_max),
        n_bins=300,
    )
    baseline_ehr, _ = compute_baseline_expected_hazard(
        x_bins=x_bins,
        probabilities=probs,
        curve_type=curve.curve_type,
        reference_value=float(curve.reference_value),
        parameters=curve.parameters or {},
        optimal_value=curve.optimal_value,
        domain_min=curve.valid_min,
    )

    relationship_type = classify_relationship(curve, bm)
    return BiomarkerOptimizationModel(
        biomarker_id=bm.id,
        relationship_type=relationship_type,
        causal_status=bm.causal_status or "STRONG_OBSERVATIONAL",
        baseline_expected_hr=baseline_ehr,
        pop_mean=mean,
        pop_sd=sd,
        pop_median=p50,
        pop_p25=p25,
        pop_p75=p75,
        optimal_target=pick_optimal_target(curve, bm, relationship_type),
    )


def backfill(db: Session, dry_run: bool = False) -> Dict[str, int]:
    biomarkers = (
        db.query(Biomarker)
        .outerjoin(
            BiomarkerOptimizationModel,
            BiomarkerOptimizationModel.biomarker_id == Biomarker.id,
        )
        .filter(BiomarkerOptimizationModel.id.is_(None))
        .order_by(Biomarker.id)
        .all()
    )

    stats = {"candidates": len(biomarkers), "created": 0, "skipped": 0}
    for bm in biomarkers:
        row = build_model_row(bm)
        if row is None:
            stats["skipped"] += 1
            print(f"  [skip] {bm.slug}: no usable HR curve or population distribution")
            continue
        if dry_run:
            print(
                f"  [dry] {bm.slug}: {row.relationship_type} "
                f"E[HR_0]={row.baseline_expected_hr:.4f} x*={row.optimal_target}"
            )
        else:
            db.add(row)
        stats["created"] += 1

    if not dry_run:
        db.commit()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    ap.add_argument("--db", default=str(DB_PATH), help="sqlite database path")
    args = ap.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")
    SessionFactory = sessionmaker(bind=engine)
    db: Session = SessionFactory()
    try:
        print(f"[*] Backfilling biomarker_optimization_model in {args.db}")
        stats = backfill(db, dry_run=args.dry_run)
        print(
            f"[+] candidates={stats['candidates']} created={stats['created']} "
            f"skipped={stats['skipped']}"
        )
        if stats["skipped"]:
            print("[!] Skipped biomarkers need a curve/distribution before backfilling.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

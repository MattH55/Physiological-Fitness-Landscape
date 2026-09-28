"""
Repair two coupled data defects in the gap-fill biomarker set.

Defect A — duplicate population-distribution cells.
-----------------------------------------------
Several biomarkers have more than one ``population_distribution`` row per
``(sex, age_band)`` because two ingest passes both wrote to the table. The
duplicates are not harmless: readers that take "the" cell for a stratum
(``main.py``'s ``.filter(...).first()`` paths and ``voi_service.pick_dist``)
arbitrarily pick whichever row SQLite returns first, so the same cohort can
report different means on different requests.

Defect B — the ``stnfr1`` unit-system contradiction.
---------------------------------------------------
For sTNFR1 the two passes disagree about units:

  * ``seed_new_biomarkers.seed_stnfr1`` writes pg/mL, median 835, domain
    [200, 5000]  (5 rows, sample_n 100-500, survey_cycle "Healthy controls
    in clinical cohorts"),
  * the deferred gap-distribution pass writes ng/mL, mean ~12.5, with
    domain [0.005, 2000] (5 rows, sample_n 1050-3200).

Every other artifact for sTNFR1 — the ``biomarker.units`` ("pg/mL"), the
``valid_domain_min/max`` (200/5000), the ``biomarker_hr_curve`` reference
(12.0 ... which is itself the ng/mL median, a third inconsistency) and the
``hr_function`` reference (835 = pg/mL median), and the literature citation
("Example healthy median 835 pg/mL, IQR 795-1,083") — is anchored to pg/mL.
Only the 5 gap-pass rows are in ng/mL, so those are the outliers.

Repair
------
  1. Pick one surviving row per ``(biomarker, sex, age_band)``: the row whose
     magnitude agrees with the biomarker's declared ``valid_domain`` and whose
     ``sample_n`` is highest (ties broken deterministically by id).
  2. Re-derive the continuous-FIT reference value (``hr_function``, and the
     equivalent ``biomarker_hr_curve`` all/all row) that lives in the same
     unit system as the surviving distribution, so that HR(reference) == 1.0
     holds for the population that is actually reported.
  3. Recompute the ``biomarker_optimization_model`` baseline E[HR_0] for the
     markers whose distributions changed.

Idempotent: re-running after a clean pass reports zero work.

Usage:
    python backend/repair_duplicate_distributions.py [--dry-run]
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.models import (
    Biomarker,
    BiomarkerHRCurve,
    BiomarkerOptimizationModel,
    HRFunction,
    PopulationDistribution,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"

# Rows accepted by this repair must have all five percentiles present so the
# planner can validate percentile ordering against the declared domain.
REQUIRED_PERCENTILES = ("p5", "p25", "p50", "p75", "p95")


class Candidate:
    """A surviving-row option plus its domain-agreement score."""

    def __init__(self, row: PopulationDistribution, biomarker: Biomarker):
        self.row = row
        self.biomarker = biomarker
        self.percentiles_ok = all(getattr(row, k) is not None for k in REQUIRED_PERCENTILES)
        self.domain_ok = _within_declared_domain(biomarker, row)
        self.sample_n = float(row.sample_n or 0.0)
        self.flat_band = abs(float(row.sd or 1.0)) < 0.05

    @property
    def rank_key(self) -> Tuple[int, int, int, int]:
        """
        Highest rank wins.

        1. percentile completeness  — needed for plotting / integration
        2. declared-domain agreement — catches cross-unit-system rows
        3. non-degenerate spread     — rejects sd ~ 0 placeholder rows
        4. sample size               — more observations preferred
        """
        return (
            1 if self.percentiles_ok else 0,
            1 if self.domain_ok else 0,
            0 if self.flat_band else 1,
            int(self.sample_n),
        )


def _within_declared_domain(biomarker: Biomarker, row: PopulationDistribution) -> bool:
    """True when every reported percentile fits the biomarker's valid domain."""
    lo = biomarker.valid_domain_min
    hi = biomarker.valid_domain_max
    if lo is None or hi is None:
        return True
    span = float(hi) - float(lo)
    if span <= 0:
        return True
    # 1% of span of slack absorbs rounding in hand-transcribed reference rows.
    slack = 0.01 * span
    for key in REQUIRED_PERCENTILES:
        v = getattr(row, key)
        if v is None:
            return True  # completeness is scored separately
        if float(v) < float(lo) - slack or float(v) > float(hi) + slack:
            return False
    return True


def group_duplicate_cells(
    db: Session,
) -> Dict[int, Dict[Tuple[str, str], List[PopulationDistribution]]]:
    """Map biomarker_id -> (sex, age_band) -> rows, keeping only duplicated cells."""
    by_biomarker: Dict[int, Dict[Tuple[str, str], List[PopulationDistribution]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for dist in db.query(PopulationDistribution).all():
        by_biomarker[dist.biomarker_id][(dist.sex or "all", dist.age_band or "all")].append(dist)

    return {
        bm_id: {cell: rows for cell, rows in cells.items() if len(rows) > 1}
        for bm_id, cells in by_biomarker.items()
        if any(len(rows) > 1 for rows in cells.values())
    }


def choose_survivor(candidates: Sequence[Candidate]) -> Candidate:
    """
    Deterministically pick the row that represents the cell.

    Rank is (percentile completeness, domain agreement, non-degenerate spread,
    sample size), ties broken by row id for reproducibility. A cell is decided
    by the whole-cell evidence, so every duplicate row in one cell maps to the
    same survivor as long as it wins on merit.
    """
    return sorted(
        candidates,
        key=lambda c: (c.rank_key, -int(c.row.id)),
        reverse=True,
    )[0]


def plan_repair(db: Session) -> List[Tuple[int, PopulationDistribution]]:
    """Return the list of (row_id, row) that should be deleted."""
    duplicates = group_duplicate_cells(db)
    doomed: List[Tuple[int, PopulationDistribution]] = []
    for bm_id, cells in duplicates.items():
        bm = db.get(Biomarker, bm_id)
        for cell, rows in sorted(cells.items()):
            candidates = [Candidate(r, bm) for r in rows]
            winner = choose_survivor(candidates)
            for cand in candidates:
                if cand.row.id != winner.row.id:
                    doomed.append((cand.row.id, cand.row))
            print(
                f"  [{bm.slug} {cell[0]}|{cell[1]}] "
                f"keep id={winner.row.id} (mean={winner.row.mean}, "
                f"sample_n={winner.sample_n:.0f}, domain_ok={winner.domain_ok}) "
                f"drop {[c.row.id for c in candidates if c.row.id != winner.row.id]}"
            )
    return doomed


def candidate_reference_values(dist: PopulationDistribution) -> List[float]:
    """Unit-system-agnostic reference candidates, most robust first."""
    out: List[float] = []
    for v in (dist.p50, dist.mean):
        if v is None:
            continue
        f = float(v)
        if math.isfinite(f) and f > 0 and all(abs(f - o) > 1e-9 for o in out):
            out.append(f)
    return out


def _reference_is_in_band(ref: float, dist: PopulationDistribution) -> bool:
    """True when ref sits inside the distribution's own reporting range."""
    lo = dist.p5 if dist.p5 is not None else (dist.mean or 0.0) - 4.0 * (dist.sd or 1.0)
    hi = dist.p95 if dist.p95 is not None else (dist.mean or 0.0) + 4.0 * (dist.sd or 1.0)
    if lo is None or hi is None or float(hi) <= float(lo):
        return False
    slack = 0.01 * (float(hi) - float(lo))
    return float(lo) - slack <= float(ref) <= float(hi) + slack


def needs_reference_repair(
    ref: Optional[float],
    dist: PopulationDistribution,
    domain: Tuple[float, float],
) -> bool:
    """
    A reference value needs rewriting when it does not describe this distribution.

    Two failure modes: the reference lies outside the surviving distribution's
    reporting range (a different unit system), or it violates the HR curve's
    declared domain (which would make evaluate_hr clip it and destroy the
    HR(reference) == 1.0 normalization).
    """
    if ref is None:
        return True
    if not _reference_is_in_band(float(ref), dist):
        return True
    lo, hi = domain
    if lo is not None and hi is not None and float(hi) > float(lo):
        if not (float(lo) <= float(ref) <= float(hi)):
            return True
    return False


def pick_reference(dist: PopulationDistribution) -> Optional[float]:
    """First candidate that lies inside the surviving distribution's range."""
    for cand in candidate_reference_values(dist):
        if _reference_is_in_band(cand, dist):
            return cand
    return None


def series_needing_repair(db: Session) -> Dict[int, List[HRFunction]]:
    """
    Every HR-function series whose reference value cannot represent it.

    This is evaluated across the WHOLE catalog, not just the markers that
    happened to have duplicate distribution cells: identical unit-system
    mismatches exist wherever a fit was transcribed from a source whose units
    disagree with its own measured domain.

    Series that carry no information anyway are skipped, so the classifier does
    not churn degenerate placeholder fits. ``dna-methylation-age`` is the
    canonical example: a ``log_log`` fit over ``[-20, 20]`` with an all-zero
    population distribution, where every transform is a no-op and HR is a flat
    1.0 across the domain.
    """
    out: Dict[int, List[HRFunction]] = defaultdict(list)
    for func in db.query(HRFunction).all():
        bm = db.get(Biomarker, func.biomarker_id)
        if bm is None:
            continue
        dist = _matching_distribution(bm, func.sex, func.age_band)
        if dist is None:
            continue
        if not needs_reference_repair(
            func.reference_value, dist, (func.domain_min, func.domain_max)
        ):
            continue
        if _is_informationless_series(func, dist):
            print(
                f"  [{bm.slug} {func.sex}|{func.age_band}] skipping degenerate series "
                f"id={func.id} (fit_type={func.fit_type}, ref={func.reference_value}, "
                f"domain=[{func.domain_min}, {func.domain_max}], dist median={dist.p50}); "
                f"HR is flat across the domain"
            )
            continue
        out[func.biomarker_id].append(func)
    return out


def _matching_distribution(
    bm: Biomarker, sex: Optional[str], age_band: Optional[str]
) -> Optional[PopulationDistribution]:
    """Distribution for the exact stratum, then the progressively wider ones."""
    dists = list(bm.population_distributions)
    for want_sex, want_band in (
        (sex or "all", age_band or "all"),
        (sex or "all", "all"),
        ("all", age_band or "all"),
        ("all", "all"),
    ):
        for d in dists:
            if (d.sex or "all") == want_sex and (d.age_band or "all") == want_band:
                return d
    return dists[0] if dists else None



def _is_informationless_series(
    func: HRFunction, dist: PopulationDistribution
) -> bool:
    """
    True when the series' transform cannot produce a non-degenerate HR curve.

    Two independent tells: the fit is a log-domain transform while the domain
    itself spans non-positive values (so every input is clamped to 1e-4), or
    every reported percentile collapses onto one value (so the population has
    no spread to describe).
    """
    lo = func.domain_min
    hi = func.domain_max
    log_domain_transform = (func.fit_type or "").lower() in (
        "log_log",
        "exponential",
        "power",
    )
    if log_domain_transform and lo is not None and float(lo) <= 0.0:
        return True

    vals = [dist.p5, dist.p25, dist.p50, dist.p75, dist.p95]
    present = [float(v) for v in vals if v is not None]
    if present and max(present) - min(present) <= 1e-9:
        return True
    return False



def clamp_series(
    db: Session, funcs: Sequence[HRFunction], dry_run: bool = False
) -> int:
    """
    Bring a fixed reference value into the series' own measured domain.

    Called only when no distribution-derived reference agrees with the series'
    domain, e.g. the pg/mL-recorded biomarker_hr_curve domains (200-5000) that
    were paired with the all/all reference 12.0. The series' measured domain is
    the ground truth for itself, so the reference is pinned inside it. The
    headroom below ``domain_min`` is preserved so the pre-existing domain
    coverage is not silently shrunk.
    """
    by_bm: Dict[int, List[HRFunction]] = defaultdict(list)
    for func in funcs:
        by_bm[func.biomarker_id].append(func)

    changed = 0
    for bm_id, group in sorted(by_bm.items()):
        bm = db.get(Biomarker, bm_id)
        print(f"  [{bm.slug}] no distribution-derived reference fits the series domain")
        for func in sorted(group, key=lambda f: f.id):
            lo, hi = float(func.domain_min), float(func.domain_max)
            if not hi > lo:
                continue
            orig = float(func.reference_value)
            target = min(max(orig, lo), hi)
            if abs(target - orig) < 1e-9:
                continue
            changed += 1
            headroom = target - lo
            new_lo = lo - headroom if headroom > 0 else lo
            print(
                f"    id={func.id} reference {orig} -> {target}; "
                f"domain [{lo}, {hi}] -> [{new_lo}, {hi}]"
            )
            if not dry_run:
                func.reference_value = target
                func.domain_min = new_lo
    return changed



def repair_references(
    db: Session, biomarker_ids: Sequence[int], dry_run: bool = False
) -> Dict[str, int]:
    """
    Re-point continuous-fit reference values at the surviving unit system.

    ``biomarker_ids`` scopes the population-distribution repair (the markers
    whose strata were just rewritten). Series that are inconsistent for the
    independent domain reason are found catalog-wide by ``series_needing_repair``.
    """
    stats = {
        "hr_function_updated": 0,
        "hr_curve_updated": 0,
        "hr_function_clamped": 0,
    }
    scoped = set(biomarker_ids) | set(series_needing_repair(db).keys())

    unrepaired: List[HRFunction] = []
    for bm_id in sorted(scoped):
        bm = db.get(Biomarker, bm_id)
        all_dist = next(
            (
                d
                for d in bm.population_distributions
                if d.sex == "all" and d.age_band == "all"
            ),
            None,
        )
        if all_dist is None:
            continue

        new_ref = pick_reference(all_dist)

        for func in db.query(HRFunction).filter(
            HRFunction.biomarker_id == bm_id,
        ).all():
            # Each series is judged against the distribution for its own
            # stratum, not the all/all roll-up: a sex-specific fit can be
            # offset from the pooled median without being wrong.
            stratum_dist = _matching_distribution(bm, func.sex, func.age_band) or all_dist
            domain = (func.domain_min, func.domain_max)
            if not needs_reference_repair(func.reference_value, stratum_dist, domain):
                continue
            target = sub_ref if (sub_ref := pick_reference(stratum_dist)) is not None else new_ref
            if target is None or needs_reference_repair(target, stratum_dist, domain):
                # The distribution-derived value does not fit this series'
                # domain either, so fall through to the clamp pass.
                unrepaired.append(func)
                continue
            stats["hr_function_updated"] += 1
            print(
                f"  [{bm.slug} {func.sex}|{func.age_band}] hr_function id={func.id} "
                f"reference {func.reference_value} -> {target}"
            )
            if not dry_run:
                func.reference_value = float(target)

        for curve in db.query(BiomarkerHRCurve).filter(
            BiomarkerHRCurve.biomarker_id == bm_id,
            BiomarkerHRCurve.sex == "all",
            BiomarkerHRCurve.age_band == "all",
        ).all():
            domain = (curve.valid_min, curve.valid_max)
            if not needs_reference_repair(curve.reference_value, all_dist, domain):
                continue
            if new_ref is None or not needs_reference_repair(new_ref, all_dist, domain):
                continue
            stats["hr_curve_updated"] += 1
            print(
                f"  [{bm.slug}] biomarker_hr_curve id={curve.id} reference "
                f"{curve.reference_value} -> {new_ref}"
            )
            if not dry_run:
                curve.reference_value = float(new_ref)

    if unrepaired:
        stats["hr_function_clamped"] = clamp_series(db, unrepaired, dry_run=dry_run)
    return stats



def recompute_optimization_models(
    db: Session, biomarker_ids: Sequence[int], dry_run: bool = False
) -> int:
    """Refresh baseline E[HR_0] for markers whose inputs just changed."""
    from backend.backfill_optimization_models import build_model_row

    updated = 0
    for bm_id in sorted(biomarker_ids):
        bm = db.get(Biomarker, bm_id)
        existing = db.query(BiomarkerOptimizationModel).filter(
            BiomarkerOptimizationModel.biomarker_id == bm_id
        ).first()
        if existing is None:
            continue
        fresh = build_model_row(bm)
        if fresh is None:
            continue
        updated += 1
        print(
            f"  [{bm.slug}] E[HR_0] {existing.baseline_expected_hr:.4f} -> "
            f"{fresh.baseline_expected_hr:.4f}"
        )
        if not dry_run:
            existing.baseline_expected_hr = fresh.baseline_expected_hr
            existing.pop_mean = fresh.pop_mean
            existing.pop_sd = fresh.pop_sd
            existing.pop_median = fresh.pop_median
            existing.pop_p25 = fresh.pop_p25
            existing.pop_p75 = fresh.pop_p75
            existing.relationship_type = fresh.relationship_type
            existing.optimal_target = fresh.optimal_target
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    ap.add_argument("--db", default=str(DB_PATH), help="sqlite database path")
    args = ap.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")
    SessionFactory = sessionmaker(bind=engine)
    db: Session = SessionFactory()
    try:
        print(f"[*] Repairing duplicate population distributions in {args.db}")
        print("[1] Duplicate cells (survivor selection):")
        doomed = plan_repair(db)
        affected = sorted({row.biomarker_id for _row_id, row in doomed})
        print(f"    -> {len(doomed)} rows to remove across {len(affected)} biomarkers")

        if doomed and not args.dry_run:
            for row_id, _row in doomed:
                db.query(PopulationDistribution).filter(
                    PopulationDistribution.id == row_id
                ).delete(synchronize_session=False)
            db.flush()
            db.expire_all()

        print("[2] Continuous-fit reference values:")
        ref_stats = repair_references(db, affected, dry_run=args.dry_run)
        print(f"    -> {ref_stats}")

        print("[3] Optimization-model baselines:")
        n_models = recompute_optimization_models(db, affected, dry_run=args.dry_run)
        print(f"    -> {n_models} baselines refreshed")

        if not args.dry_run:
            db.commit()
            print("[+] Committed.")
        else:
            print("[dry-run] No changes written.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





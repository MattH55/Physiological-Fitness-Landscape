"""
Cell-line / cancer-type opportunity scoring -- reconciling the "NPxP
Interaction Predictor" build spec's section 6 into this codebase.

**Why this is a new module, not a rewrite of prioritization.py**: the two
answer genuinely different questions, at different granularities, with a
genuinely different formula structure -- not a cosmetic difference to
paper over by picking one:

  - `synlethality.prioritization.PriorityScorer` (build spec v6): "which
    specific candidate ROW (this drug x modifier x cell-line triple) is
    worth studying next" -- a weighted SUM of five independent signals
    (convergent evidence, coverage gap, trial saturation, tumor
    representativeness, low-resource boost). Additive: a row can still
    rank reasonably even if one component is weak, as long as others are
    strong.
  - This module (new spec, 2026-09-23): "which whole CELL LINE (or
    cancer type) has the most to gain from non-pharm research effort" --
    a PRODUCT of exactly two terms, `predicted_uplift x gap_weight`.
    Multiplicative: a cell line with strong predicted uplift but already
    well-studied scores low (gap_weight suppresses it), and a poorly-
    studied cell line with no real synergy signal at all scores low too
    (predicted_uplift suppresses it) -- neither term can be "rescued" by
    the other the way prioritization.py's additive terms can be.

Both are real, both stay -- prioritization.py's `priority_score` for "what
specific thing to test next," this module's `opportunity_score` for
"where is research effort most under-allocated relative to what's already
been found."

**Scoped down from the full spec, documented explicitly**: the spec's own
`predicted_uplift` is "the best predicted or observed synergy score across
all tested/predicted non-pharm interventions paired with that cell line's
relevant standard-of-care drugs" -- which needs a `standard_of_care_for`
mapping this build doesn't have (the spec's own Open Questions admit there
's no machine-readable NCCN source either). This implementation uses ALL
of a cell line's real interactions (not just standard-of-care drugs) and
defines predicted_uplift as the real, bounded [0, 1] fraction of its
genuinely-tested (tier_1_direct or tier_2_inferred) interactions that are
synergistic -- deliberately not a magnitude estimate blended from
differently-scaled real numbers (a Thermal Enhancement Ratio and an IC50
fold-shift and a qualitative call aren't comparable on one scale without
real work to make them so; see seed_data.py's REAL_COMBINED_EFFECT_METRICS
for why those two metric types are kept explicitly distinct already).

`gap_weight` uses the spec's own formula, `1 / (1 + log(1 + e1_count))` --
here `e1_count` is real `tier_1_direct` rows for that cell line specifically
(the spec's own "E1" tier), not counting tier_2c/tier_3/tier_4 generated
rows as if they were direct evidence.
"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from synlethality.models import CellLine, EvidenceTier, InteractionEffect, InteractionType


def _predicted_uplift(rows: list[InteractionEffect]) -> float:
    """Real, bounded [0, 1]: fraction of this cell line's genuinely-tested
    (tier_1_direct or tier_2_inferred) interactions that are synergistic.
    0.0 (not "no data") when there are no real rows at all -- distinguished
    from a genuine "tested and found nothing synergistic" via
    `n_real_interactions` in the returned row, so a caller can tell the
    two apart rather than reading a bare 0.0 as "no upside anywhere"."""
    real = [r for r in rows if r.evidence_tier in (EvidenceTier.tier_1_direct, EvidenceTier.tier_2_inferred)]
    if not real:
        return 0.0
    synergistic = sum(1 for r in real if r.interaction_type == InteractionType.synergistic)
    return synergistic / len(real)


def _gap_weight(tier_1_count: int) -> float:
    """Spec's own formula: 1 / (1 + log(1 + e1_assay_count))."""
    return 1.0 / (1.0 + math.log(1.0 + tier_1_count))


def compute_cell_line_opportunity_scores(session: Session) -> list[dict]:
    """One row per cell line with >=1 interaction_effect of any tier (a
    cell line with zero rows at all has no basis for either term and is
    omitted, not scored as a fabricated 0). Sorted by opportunity_score
    descending."""
    all_rows = session.execute(select(InteractionEffect)).scalars().all()
    by_cell_line: dict[str, list[InteractionEffect]] = {}
    for r in all_rows:
        by_cell_line.setdefault(r.cell_line_id, []).append(r)

    cell_lines = {cl.cell_line_id: cl for cl in session.execute(select(CellLine)).scalars().all()}

    results = []
    for cell_line_id, rows in by_cell_line.items():
        cl = cell_lines.get(cell_line_id)
        if cl is None:
            continue
        tier_1_count = sum(1 for r in rows if r.evidence_tier == EvidenceTier.tier_1_direct)
        uplift = _predicted_uplift(rows)
        gap_weight = _gap_weight(tier_1_count)
        n_real = sum(1 for r in rows
                     if r.evidence_tier in (EvidenceTier.tier_1_direct, EvidenceTier.tier_2_inferred))
        results.append({
            "cell_line_id": cell_line_id,
            "cell_line_name": cl.name,
            "tissue_origin": cl.tissue_origin,
            "oncotree_primary_disease": cl.oncotree_primary_disease,
            "predicted_uplift": round(uplift, 4),
            "gap_weight": round(gap_weight, 4),
            "opportunity_score": round(uplift * gap_weight, 4),
            "n_real_interactions": n_real,
            "tier_1_direct_count": tier_1_count,
            "n_total_interactions": len(rows),
        })

    results.sort(key=lambda r: r["opportunity_score"], reverse=True)
    return results


def compute_cancer_type_opportunity_scores(session: Session) -> list[dict]:
    """Roll up compute_cell_line_opportunity_scores by
    oncotree_primary_disease: mean and max opportunity_score, and the
    cell-line count backing the estimate (spec: "a cancer type represented
    by one cell line gets flagged as low-confidence, not hidden"). Cell
    lines with no oncotree_primary_disease (not yet backfilled, or
    genuinely out of OncoTree's scope -- see models.py CellLine docstring)
    are grouped under "unassigned" rather than silently dropped."""
    cell_line_scores = compute_cell_line_opportunity_scores(session)
    by_disease: dict[str, list[dict]] = {}
    for r in cell_line_scores:
        key = r["oncotree_primary_disease"] or "unassigned"
        by_disease.setdefault(key, []).append(r)

    results = []
    for disease, rows in by_disease.items():
        scores = [r["opportunity_score"] for r in rows]
        results.append({
            "oncotree_primary_disease": disease,
            "mean_opportunity_score": round(sum(scores) / len(scores), 4),
            "max_opportunity_score": round(max(scores), 4),
            "n_cell_lines": len(rows),
            "low_confidence": len(rows) < 2,
            "cell_line_ids": [r["cell_line_id"] for r in rows],
        })
    results.sort(key=lambda r: r["mean_opportunity_score"], reverse=True)
    return results

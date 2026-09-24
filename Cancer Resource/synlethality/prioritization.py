"""
Prioritization Schema (build spec v6).

Purpose (spec): rank candidates for "what should get studied next," with
the weighting transparent and auditable rather than a black box. The spec
is explicit that the weights/formula must be published, not just embedded
in code -- see PRIORITY_WEIGHTS below and `GET /api/prioritization/methodology`
in main.py, which serves this same dict so the frontend renders it rather
than hardcoding a second copy.

Every component the spec lists is implemented against data this build
actually has, with one deliberate, documented exception: **disease burden /
unmet need has weight 0.0**. The spec itself leaves the data source as an
open question for Matt (GLOBOCAN vs. the Right to Try / Montana SB 535
therapeutic-adequacy work) -- wiring in a number from memory here would be
exactly the kind of fabricated-looking precision this project has
consistently avoided elsewhere (PubChem CIDs, OncoTree codes, etc.). The
weight is present and set to 0.0, not silently deleted, so turning it on
later is a one-line change once a source is confirmed.

`low_resource_relevance` and `priority_score` are computed here, not stored
columns (see models.py InteractionEffect docstring for why) -- both are
attached to the API payload the same way other derived fields already are.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from synlethality.coverage_gaps import compute_coverage_gap_matrix
from synlethality.models import (
    CellLine,
    ClinicalEvidence,
    CostAccessibilityTier,
    Drug,
    InfrastructureRequirement,
    InteractionEffect,
    Modifier,
    TumorConcordanceFlag,
)

#: Published weights (spec: "publish the weights and formula on the
#: methodology page, not just in code"). Sum of active (non-zero) weights
#: need not be 1.0 -- priority_score is a relative ranking signal, not a
#: probability.
PRIORITY_WEIGHTS = {
    "convergent_evidence": 0.35,
    "coverage_gap": 0.30,
    "trial_saturation_inverse": 0.15,
    "tumor_representativeness": 0.10,
    "low_resource_boost": 0.10,
    "disease_burden": 0.0,  # pending data-source confirmation (spec Open Questions)
}

PRIORITY_COMPONENT_DESCRIPTIONS = {
    "convergent_evidence": "How many independent signals agree for this row "
        "(mechanism-signature link, resistance-mechanism link, a quantitative "
        "combined-effect metric) -- more signals is more confident, scored 0-1.",
    "coverage_gap": "From the Coverage Gap Analysis: resistance-mechanism "
        "richness for this drug relative to how little has been tested "
        "against it in this modifier_type, normalized 0-1.",
    "trial_saturation_inverse": "Inverse of how many clinical_evidence rows "
        "already exist for this drug -- heavily-trialed combinations score "
        "lower, since the gap is already being addressed.",
    "tumor_representativeness": "cell_line.tumor_concordance_score-based: "
        "good_model=1.0, unassessed=0.5 (neutral, not yet assessed), "
        "poor_model_mesenchymal_shift=0.0.",
    "low_resource_boost": "1.0 if low_resource_relevance is true, else 0.0 "
        "-- a configurable boost per the spec, not a hard filter.",
    "disease_burden": "NOT YET WIRED (weight 0.0): pending confirmation of "
        "a data source (GLOBOCAN vs. OSMF's Right to Try / Montana SB 535 "
        "therapeutic-adequacy work) -- see build spec Open Questions.",
}


def compute_low_resource_relevance(drug: Drug | None, modifier: Modifier | None) -> bool:
    """spec: true when cost_accessibility_tier is essential_generic/
    generic_available AND infrastructure_requirement is minimal/low."""
    if drug is None or modifier is None:
        return False
    cost_ok = drug.cost_accessibility_tier in (
        CostAccessibilityTier.essential_generic, CostAccessibilityTier.generic_available,
    )
    infra_ok = modifier.infrastructure_requirement in (
        InfrastructureRequirement.minimal, InfrastructureRequirement.low,
    )
    return bool(cost_ok and infra_ok)


def _convergent_evidence_score(it: InteractionEffect) -> float:
    signals = sum([
        it.mechanism_link is not None,
        it.resistance_mechanism_link is not None,
        it.combined_effect_metric is not None,
    ])
    return signals / 3.0


def _tumor_representativeness_score(cell_line: CellLine | None) -> float:
    if cell_line is None or cell_line.tumor_concordance_flag is None:
        return 0.5
    return {
        TumorConcordanceFlag.good_model: 1.0,
        TumorConcordanceFlag.poor_model_mesenchymal_shift: 0.0,
        TumorConcordanceFlag.unassessed: 0.5,
    }.get(cell_line.tumor_concordance_flag, 0.5)


class PriorityScorer:
    """Precomputes the per-drug/modifier_type gap matrix and per-drug trial
    counts once, then scores many interaction rows cheaply. Build one per
    request rather than querying the gap matrix per row.
    """

    def __init__(self, session: Session, tumor_type: str | None = None):
        self.session = session
        gap_rows = compute_coverage_gap_matrix(session, tumor_type=tumor_type)
        max_gap = max((r["gap_score"] for r in gap_rows), default=0.0) or 1.0
        self._gap_by_key = {
            (r["drug_id"], r["modifier_type"]): r["gap_score"] / max_gap for r in gap_rows
        }
        trial_counts = dict(
            session.execute(
                select(InteractionEffect.drug_id, func.count(ClinicalEvidence.id))
                .join(ClinicalEvidence,
                      ClinicalEvidence.linked_interaction_effect_id == InteractionEffect.id)
                .group_by(InteractionEffect.drug_id)
            ).all()
        )
        self._trial_counts = trial_counts

    def score(self, it: InteractionEffect, drug: Drug | None, modifier: Modifier | None,
              cell_line: CellLine | None) -> dict:
        low_resource = compute_low_resource_relevance(drug, modifier)
        convergent = _convergent_evidence_score(it)
        gap = self._gap_by_key.get(
            (it.drug_id, modifier.modifier_type.value if modifier and modifier.modifier_type else ""),
            0.0,
        )
        trial_count = self._trial_counts.get(it.drug_id, 0)
        saturation_inverse = 1.0 / (1 + trial_count)
        tumor_rep = _tumor_representativeness_score(cell_line)

        score = (
            PRIORITY_WEIGHTS["convergent_evidence"] * convergent
            + PRIORITY_WEIGHTS["coverage_gap"] * gap
            + PRIORITY_WEIGHTS["trial_saturation_inverse"] * saturation_inverse
            + PRIORITY_WEIGHTS["tumor_representativeness"] * tumor_rep
            + PRIORITY_WEIGHTS["low_resource_boost"] * (1.0 if low_resource else 0.0)
            # disease_burden term omitted: weight is 0.0, see module docstring
        )
        return {
            "low_resource_relevance": low_resource,
            "priority_score": round(score, 4),
            "priority_components": {
                "convergent_evidence": round(convergent, 4),
                "coverage_gap": round(gap, 4),
                "trial_saturation_inverse": round(saturation_inverse, 4),
                "tumor_representativeness": round(tumor_rep, 4),
                "low_resource_boost": 1.0 if low_resource else 0.0,
                "disease_burden": None,
            },
        }

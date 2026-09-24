"""
Coverage Gap Analysis (build spec v6).

Purpose (spec): "the single most differentiating feature of NPxP -- most
resources show what's known; this shows what's missing." For each drug with
resistance-mechanism annotation, how many modifiers (by type) have any
interaction_effect row against it, and how much resistance-mechanism
richness exists relative to that -- a drug with rich mechanism annotation
but near-zero modifier coverage is a citable gap, not just an empty cell.

Implemented as a drug x modifier_type matrix (not a flat drug list) because
that's what the frontend spec item actually calls for ("a matrix view
(drugs x modifier types), shaded by coverage density") and it gives a much
more actionable gap signal than a single per-drug number: mechanism
richness is constant across a drug's row, but interaction coverage varies
meaningfully per modifier_type column.

gap_score formula, exactly as specified: mechanism-annotation richness
(count of drug_resistance_mechanism rows for that drug) / (1 + existing
interaction_effect count for that (drug, modifier_type) pair). Higher score
= more resistance-mechanism understanding relative to how little has
actually been tested against it -- i.e. a bigger gap.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from synlethality.models import (
    CellLine,
    Drug,
    DrugResistanceMechanism,
    InteractionEffect,
    Modifier,
    ModifierType,
)


def compute_coverage_gap_matrix(session: Session, tumor_type: str | None = None) -> list[dict]:
    """Return one row per (drug with >=1 resistance mechanism) x modifier_type.

    `tumor_type` (a tissue_origin substring, same tumor-type proxy used by
    /interactions/candidates until oncotree_subtype is populated) restricts
    which interaction_effect rows count toward *coverage* -- mechanism
    richness stays drug-level and is not filtered by tumor type, since
    resistance-mechanism annotation isn't tied to a specific cell line.
    """
    mechanism_counts = dict(
        session.execute(
            select(DrugResistanceMechanism.drug_id, func.count())
            .group_by(DrugResistanceMechanism.drug_id)
        ).all()
    )
    if not mechanism_counts:
        return []

    drugs = {
        d.drug_id: d
        for d in session.execute(
            select(Drug).where(Drug.drug_id.in_(mechanism_counts))
        ).scalars().all()
    }

    interaction_stmt = (
        select(Modifier.modifier_type, InteractionEffect.drug_id, func.count())
        .join(Modifier, InteractionEffect.modifier_id == Modifier.modifier_id)
        .where(InteractionEffect.drug_id.in_(mechanism_counts))
        .group_by(Modifier.modifier_type, InteractionEffect.drug_id)
    )
    if tumor_type:
        interaction_stmt = interaction_stmt.join(
            CellLine, InteractionEffect.cell_line_id == CellLine.cell_line_id
        ).where(CellLine.tissue_origin.ilike(f"%{tumor_type}%"))
    interaction_counts: dict[tuple[ModifierType, str], int] = {
        (mt, drug_id): n for mt, drug_id, n in session.execute(interaction_stmt).all()
    }

    rows = []
    for drug_id, mech_count in mechanism_counts.items():
        drug = drugs.get(drug_id)
        for mt in ModifierType:
            interaction_count = interaction_counts.get((mt, drug_id), 0)
            gap_score = mech_count / (1 + interaction_count)
            rows.append({
                "drug_id": drug_id,
                "drug_name": drug.name if drug else drug_id,
                "modifier_type": mt.value,
                "mechanism_count": mech_count,
                "interaction_count": interaction_count,
                "gap_score": round(gap_score, 4),
            })
    rows.sort(key=lambda r: r["gap_score"], reverse=True)
    return rows

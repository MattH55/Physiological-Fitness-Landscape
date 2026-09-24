"""
Heuristic target-match bridging (Tier 4) -- built at the user's explicit
request to compute *something* between every modifier and the full ~7,000-
compound DepMap registry (synlethality/ingest/depmap_prism.py), after
confirming they understood and accepted the tradeoff: this is real source
data (DepMap's own target/mechanism-of-action annotation) run through a
mechanical, unverified keyword heuristic, not per-drug curated evidence.

**Why this is a different, weaker thing than synlethality/bridging.py**:
the real Mechanistic Bridging module matches a modifier's induced signature
against a *resistance mechanism* -- a specific, cited claim about what
protects a cell from a given drug (e.g. "high SLC7A11 protects against
metformin-induced ferroptosis," cited to Yang et al. 2021). Reproducing
that per-drug research for ~7,000 compounds isn't feasible by hand in a
session, so this module does something categorically weaker instead:
checks whether a compound's own DepMap-supplied `target`/`drug_class` text
(its mechanism of action, not a resistance mechanism) shares a keyword with
one of the five signature panels. "This drug's target and this modifier's
induced pathway are both loosely in the DNA-damage domain" is not the same
claim as "this drug's resistance mechanism runs through this modifier's
suppressed pathway" -- it's a much weaker, purely textual co-occurrence.

Consequences, all deliberate:
  - `evidence_tier` is always `tier_4_heuristic_target_match`, never
    `tier_3_mechanism_only` -- so a viewer filtering for Tier 3 (which
    implies a real cited mechanism) never sees these.
  - `interaction_type` is always `unknown`: a keyword match says nothing
    about whether the modifier would help or hurt the drug's effect.
  - `resistance_mechanism_link` is always NULL: no
    `drug_resistance_mechanism` row is fabricated for the ~6,990 bulk
    compounds (that table's own rows require a real per-row citation,
    enforced by test_drug_resistance_mechanisms_are_cited).
  - Drugs that already have a real, cited `drug_resistance_mechanism`
    entry are skipped entirely here -- they already get the stronger,
    correctly-tiered treatment from bridging.py; layering a weaker
    heuristic claim on top of a real one would only create confusion.
  - `source_study` cites the real modifier evidence plus the real DepMap
    release DOI (the only "source" that's actually true of a heuristic
    match against DepMap's own data) -- never a fabricated per-drug paper.

The keyword lists below are a transparent, documented, approximate mapping
-- not validated against a gold standard, and known to have both false
positives (e.g. a coincidental substring match) and false negatives (real
mechanistic overlap the keywords don't happen to catch). They are printed
here in full specifically so anyone can audit exactly what produced a given
Tier 4 row, rather than treating it as an opaque black box.

Deliberately NOT wired into `seed_data.seed()` (unlike bridging.py, which
runs on every app start): this is explicitly the most speculative content
in the database, and per the same "risky bulk step stays opt-in" pattern
already used for the DepMap ingestion itself, it's invoked separately (see
scripts/export_static.py and tests/test_heuristic_bridging.py), never
automatically.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from synlethality.models import (
    Directionality,
    Drug,
    DrugResistanceMechanism,
    EvidenceTier,
    InteractionEffect,
    InteractionType,
    Modifier,
    SignaturePanel,
    StressSignatureScore,
)

#: Real DOI for the actual data release this heuristic reads from (verified
#: 2026-09-22 -- see ingest/depmap_prism.py). This is the only citation that
#: can honestly accompany a Tier 4 row's drug-side claim.
DEPMAP_RELEASE_CITATION = "doi:10.25452/figshare.plus.27993248.v1"

#: Transparent, documented, approximate panel <-> keyword mapping. Matched
#: case-insensitively as a substring against the concatenation of a drug's
#: `target` (DepMap GeneSymbolOfTargets) and `drug_class` (DepMap
#: TargetOrMechanism) fields. Order matters only for which keyword is
#: reported first in curator_notes when several match.
PANEL_KEYWORDS: dict[SignaturePanel, list[str]] = {
    SignaturePanel.dna_damage: [
        "TOPOISOMERASE", "TOP1", "TOP2", "ALKYLAT", "CROSSLINK", "PARP",
        "DNA-PK", "DNA POLYMERASE", "ATR ", "ATM ", "CHK1", "CHK2",
    ],
    SignaturePanel.nrf2_ferroptosis: [
        "GPX4", "GPX", "XCT", "SLC7A11", "GLUTATHIONE", "FERROPTOSIS",
        "NRF2", "NFE2L2", "SYSTEM XC",
    ],
    SignaturePanel.hsf1_hsp: [
        "HSP90", "HSP70", "HSF1", "CHAPERONE", "HEAT SHOCK",
    ],
    SignaturePanel.isr_upr: [
        "PERK", "EIF2", "ATF4", "ATF6", "IRE1", "UNFOLDED PROTEIN",
        "ER STRESS", "GCN2",
    ],
    SignaturePanel.senescence: [
        "CDK4", "CDK6", "SENESCEN", "MDM2",
    ],
}

HEURISTIC_NOTE_TEMPLATE = (
    "[Tier 4 -- mechanical heuristic, NOT a verified resistance-mechanism "
    "claim] {drug_name}'s DepMap-supplied target/mechanism annotation "
    "({drug_annotation!r}) contains the keyword {keyword!r}, which this "
    "build's keyword list maps to the {panel} signature panel. {modifier_agent} "
    "induces a {panel} signature ({directionality}) in {cell_line_name}. This "
    "is a purely textual co-occurrence between the drug's own mechanism of "
    "action and the modifier's induced pathway category -- it is NOT a claim "
    "that either affects the other's resistance, has not been reviewed by a "
    "curator, and predicts no direction (recorded as interaction_type = "
    "unknown). Treat as a keyword-matched lead for someone to investigate, "
    "not as evidence."
)


def _match_panel(text: str) -> tuple[SignaturePanel, str] | None:
    upper = text.upper()
    for panel, keywords in PANEL_KEYWORDS.items():
        for kw in keywords:
            if kw in upper:
                return panel, kw
    return None


def _existing_pairs(session: Session) -> set[tuple[str, str, str]]:
    rows = session.execute(
        select(
            InteractionEffect.modifier_id,
            InteractionEffect.drug_id,
            InteractionEffect.cell_line_id,
        )
    ).all()
    return {(m, d, c) for m, d, c in rows}


def generate_heuristic_matches(session: Session) -> dict:
    """Run the Tier 4 keyword match and insert new interaction_effect rows.

    Idempotent, like bridging.generate_candidates: never inserts a
    (modifier_id, drug_id, cell_line_id) triple that already exists.
    Skips any drug that already has a real drug_resistance_mechanism row
    (it gets the stronger, correctly-cited Tier 3 treatment instead).
    """
    scores = session.execute(
        select(StressSignatureScore).where(
            StressSignatureScore.signature_panel != SignaturePanel.other,
            StressSignatureScore.directionality != Directionality.ambiguous,
        )
    ).scalars().all()

    drugs_with_real_mechanism = {
        row[0] for row in session.execute(select(DrugResistanceMechanism.drug_id)).all()
    }
    drugs = session.execute(
        select(Drug).where(~Drug.drug_id.in_(drugs_with_real_mechanism))
    ).scalars().all()

    # Pre-index drugs by matched panel so we don't re-scan the whole
    # ~7,000-row registry once per signature score.
    drugs_by_panel: dict[SignaturePanel, list[tuple[Drug, str]]] = {}
    for drug in drugs:
        annotation = f"{drug.target or ''} {drug.drug_class or ''}".strip()
        if not annotation:
            continue
        match = _match_panel(annotation)
        if match is None:
            continue
        panel, keyword = match
        drugs_by_panel.setdefault(panel, []).append((drug, keyword))

    existing = _existing_pairs(session)
    modifier_cache: dict[str, Modifier] = {}
    counts = {"generated": 0, "skipped": 0, "drugs_matched": 0}
    matched_drug_ids: set[str] = set()

    for score in scores:
        candidates = drugs_by_panel.get(score.signature_panel, [])
        if not candidates:
            continue
        modifier = modifier_cache.setdefault(
            score.modifier_id, session.get(Modifier, score.modifier_id)
        )
        if modifier is None:
            continue

        for drug, keyword in candidates:
            triple = (score.modifier_id, drug.drug_id, score.cell_line_id)
            if triple in existing:
                counts["skipped"] += 1
                continue

            annotation = f"{drug.target or ''} {drug.drug_class or ''}".strip()
            citations = []
            for c in (modifier.source_study, DEPMAP_RELEASE_CITATION):
                if c and c not in citations:
                    citations.append(c)

            note = HEURISTIC_NOTE_TEMPLATE.format(
                drug_name=drug.name,
                drug_annotation=annotation,
                keyword=keyword,
                panel=score.signature_panel.value,
                modifier_agent=modifier.agent,
                directionality=score.directionality.value,
                cell_line_name=score.cell_line_id,
            )

            session.add(InteractionEffect(
                modifier_id=score.modifier_id,
                drug_id=drug.drug_id,
                cell_line_id=score.cell_line_id,
                combined_effect_metric=None,
                interaction_type=InteractionType.unknown,
                evidence_tier=EvidenceTier.tier_4_heuristic_target_match,
                mechanism_link=score.id,
                resistance_mechanism_link=None,
                source_study=citations,
                curator_notes=note,
            ))
            existing.add(triple)
            matched_drug_ids.add(drug.drug_id)
            counts["generated"] += 1

    counts["drugs_matched"] = len(matched_drug_ids)
    return counts

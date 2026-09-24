"""
Mechanistic Bridging module (build spec v5).

Purpose (spec): surface non-pharmacological modifiers predicted to improve a
drug's effectiveness, specifically for combinations no study has tested
directly -- generating candidates, not just cataloguing known results.

**Scope-down from the full spec, documented explicitly, updated 2026-09-22**:
the spec's Step 5 calls for a "co-gene/GS" signature-overlap correlation scan
across the full drug library x full modifier library x full pathway universe
(MSigDB Hallmark/Reactome/KEGG), benchmarked against the DREAM consortium
synergy gold standard. `synlethality/signature_correlation.py` now
implements the real correlation math this needs (ccmap's XSum statistic, plus
a real gene-set enrichment score), and `ingest/msigdb.py` +
`ingest/geo_modifiers.py` pull real Hallmark/KEGG gene sets and compute real
per-gene log2FC from GSE153830's own published expression matrix -- but that
covers only the *modifier* side, for one GEO series. The *drug* side needs
LINCS L1000 per-compound induced signatures (`ingest/lincs_l1000.py`), which
remains a structured stub (clue.io registration + GB-scale files, neither
available this session), so a real full-drug-library x full-modifier-library
scan still isn't wired end-to-end here -- what runs below (`generate_candidates`)
is still the categorical signature_panel join, not the numeric correlation
engine. Benchmarking against the DREAM gold standard also remains out of
reach (external dataset access this session doesn't have). What's
implemented in `generate_candidates` below is Steps 2-4 and a simplified
6-7, for real, against the actually-curated data:

  Step 2 (match): join `stress_signature_score` to `drug_resistance_mechanism`
    on `signature_panel` -- both tables carry this field for exactly this
    join (see models.py docstrings for why it's an additive extension).
  Step 3 (directionality): death_promoting -> synergistic (candidate);
    protective_resistance -> antagonistic (logged, not surfaced as a primary
    candidate); ambiguous -> skipped (no clear directional signal to act on).
  Step 4 (subtype conditioning): implicit in using per-(modifier, cell_line)
    signature scores rather than a blanket per-tissue rule -- e.g. serine/
    glycine restriction only generates a death-promoting (candidate) match
    in the p53-null HCT116 derivative, not the p53-wild-type parental line,
    because that's what the underlying signature scores actually say.
  Step 6 (tumor-representativeness filter): candidates in a cell line
    flagged `poor_model_mesenchymal_shift` are skipped.
  Step 7 (convergent-evidence ranking): NOT implemented as a numeric score --
    every candidate here rests on exactly one signal (mechanism-panel
    overlap), so a fabricated-looking "confidence score" would overstate
    what's actually known. `/api/interactions/candidates` returns candidates
    unranked (stable name order) rather than inventing a ranking metric.

Every generated row is tagged unambiguously: `evidence_tier =
tier_3_mechanism_only`, both `mechanism_link` and `resistance_mechanism_link`
populated, and `curator_notes` states plainly that this is a model-generated
hypothesis, not a tested result. Never overwrites an existing
(modifier_id, drug_id, cell_line_id) row -- curated evidence always wins,
and re-running this function is idempotent.

**Known limitation, found and scoped around 2026-09-22**: matching purely on
`signature_panel` has no tumor-type/tissue awareness, and the real spec's
Step 4 (subtype conditioning) needs `oncotree_subtype`/`key_mutations` data
this build doesn't have populated yet (see models.py CellLine docstring).
This surfaced concretely as "temozolomide + colorectal cancer (RKO)" and
"temozolomide + mouse breast cancer (4T1)" candidates -- temozolomide/
lomustine's real-world relevance is CNS-restricted (BBB-penetrant chemistry,
glioma-specific clinical use), unlike a broadly-mechanistic compound like
metformin or erastin, where a cross-tissue candidate is a genuinely open
question rather than a known mismatch. Rather than add an unprincipled
tissue-overlap heuristic (which would also remove legitimately broad
candidates -- our own curated seed has no metformin-x-colon example, but
metformin-in-colorectal-cancer is real and well-studied, so "the drug must
already have curated evidence in this tissue" is too aggressive a filter
given how sparse this seed is), the fix applied was narrower and more
honest: `drug_resistance_mechanism.signature_panel` is left NULL for
temozolomide/lomustine specifically (see seed_data.py), so they're simply
not matchable by this join at all. Their two real, CNS-appropriate
interactions (TTFields, PEMF) are hand-curated instead. A real subtype-
conditioning gate (Step 4 as actually specified) is the durable fix once
oncotree_subtype is populated -- not implemented here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from synlethality.models import (
    CellLine,
    Directionality,
    Drug,
    DrugResistanceMechanism,
    EvidenceTier,
    InteractionEffect,
    InteractionType,
    Modifier,
    SignaturePanel,
    StressSignatureScore,
    TumorConcordanceFlag,
)

BRIDGING_NOTE_TEMPLATE = (
    "[Mechanistic Bridging -- model-generated hypothesis, not a tested result] "
    "{modifier_agent} induces a {panel} signature ({directionality}) in "
    "{cell_line_name}; {drug_name}'s reported resistance mechanism runs "
    "through the same pathway ({pathway_or_gene}). {directional_note} This "
    "combination has not been evaluated together in any cited study -- it is "
    "a candidate for testing, generated by matching independently-curated "
    "signature and resistance-mechanism evidence, not a direct or inferred "
    "empirical finding."
)

DIRECTIONAL_NOTE = {
    Directionality.death_promoting: (
        "Because the modifier's effect on this pathway is death-promoting "
        "(suppresses the pathway the drug's resistance depends on), this is "
        "surfaced as a synergy candidate."
    ),
    Directionality.protective_resistance: (
        "Because the modifier's effect on this pathway is protective/"
        "resistance-conferring (reinforces the same pathway the drug's "
        "resistance depends on), this predicts antagonism and is logged "
        "here rather than surfaced as a synergy candidate."
    ),
}


def _existing_pairs(session: Session) -> set[tuple[str, str, str]]:
    rows = session.execute(
        select(
            InteractionEffect.modifier_id,
            InteractionEffect.drug_id,
            InteractionEffect.cell_line_id,
        )
    ).all()
    return {(m, d, c) for m, d, c in rows}


def generate_candidates(session: Session) -> dict:
    """Run the bridging match and insert new interaction_effect rows.

    Idempotent: never inserts a (modifier_id, drug_id, cell_line_id) triple
    that already exists (curated or previously generated). Returns counts,
    not the rows themselves -- callers query interaction_effect directly.
    """
    scores = session.execute(
        select(StressSignatureScore).where(
            StressSignatureScore.signature_panel != SignaturePanel.other,
            StressSignatureScore.directionality != Directionality.ambiguous,
        )
    ).scalars().all()
    mechanisms = session.execute(
        select(DrugResistanceMechanism).where(
            DrugResistanceMechanism.signature_panel.isnot(None)
        )
    ).scalars().all()
    mechanisms_by_panel: dict[SignaturePanel, list[DrugResistanceMechanism]] = {}
    for m in mechanisms:
        mechanisms_by_panel.setdefault(m.signature_panel, []).append(m)

    existing = _existing_pairs(session)
    modifier_cache: dict[str, Modifier] = {}
    cell_line_cache: dict[str, CellLine] = {}
    drug_cache: dict[str, Drug | None] = {}

    counts = {"generated_synergistic": 0, "generated_antagonistic": 0, "skipped": 0}

    for score in scores:
        for mech in mechanisms_by_panel.get(score.signature_panel, []):
            triple = (score.modifier_id, mech.drug_id, score.cell_line_id)
            if triple in existing:
                counts["skipped"] += 1
                continue

            cell_line = cell_line_cache.setdefault(
                score.cell_line_id, session.get(CellLine, score.cell_line_id)
            )
            if cell_line is None:
                continue
            if cell_line.tumor_concordance_flag == TumorConcordanceFlag.poor_model_mesenchymal_shift:
                counts["skipped"] += 1
                continue  # Step 6: deprioritize/skip poor tumor models

            if score.directionality == Directionality.death_promoting:
                interaction_type = InteractionType.synergistic
            elif score.directionality == Directionality.protective_resistance:
                interaction_type = InteractionType.antagonistic
            else:
                continue  # unreachable given the query filter; defensive

            modifier = modifier_cache.setdefault(
                score.modifier_id, session.get(Modifier, score.modifier_id)
            )
            if modifier is None:
                continue
            drug = drug_cache.setdefault(mech.drug_id, session.get(Drug, mech.drug_id))
            drug_name = drug.name if drug else mech.drug_id

            citations = []
            for c in (modifier.source_study, mech.source):
                if c and c not in citations:
                    citations.append(c)

            note = BRIDGING_NOTE_TEMPLATE.format(
                modifier_agent=modifier.agent,
                panel=score.signature_panel.value,
                directionality=score.directionality.value,
                cell_line_name=cell_line.name,
                drug_name=drug_name,
                pathway_or_gene=mech.pathway_or_gene,
                directional_note=DIRECTIONAL_NOTE[score.directionality],
            )

            session.add(InteractionEffect(
                modifier_id=score.modifier_id,
                drug_id=mech.drug_id,
                cell_line_id=score.cell_line_id,
                combined_effect_metric=None,
                interaction_type=interaction_type,
                evidence_tier=EvidenceTier.tier_3_mechanism_only,
                mechanism_link=score.id,
                resistance_mechanism_link=mech.id,
                source_study=citations,
                curator_notes=note,
            ))
            existing.add(triple)
            if interaction_type == InteractionType.synergistic:
                counts["generated_synergistic"] += 1
            else:
                counts["generated_antagonistic"] += 1

    return counts

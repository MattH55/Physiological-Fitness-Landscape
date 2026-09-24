"""
Nearest-neighbor cell-line-similarity prediction (evidence_tier =
tier_2c_nearest_neighbor).

Reconciles the "NPxP Interaction Predictor & Opportunity Ranking" build spec
(2026-09-23, authored separately from this codebase) into the schema
already built here, rather than standing up its proposed parallel
`interventions`/`assays`/`predicted_interactions` tables. That spec's
Stage 1/E2 concept -- "no direct assay, but a molecularly similar cell
line has been tested with the same non-pharm mechanism and a drug of the
same MoA class" -- maps onto our EvidenceTier system as a new tier,
distinct from the two tiers it might otherwise be confused with:
  - tier_2_inferred: joins two *separately*-tested single-factor legs
    *in the same cell line*. No similarity computation, no borrowed
    combination result.
  - tier_2b_model_predicted: a fitted regression/ML model's output.
    tier_2c is not a model -- it's a direct, named, cited real result
    from a different cell line, re-weighted by similarity.

**Scope-down from the full spec, documented explicitly**: the spec's own
gate is "same mechanism_id or same intervention, and a drug of the same
MoA class." This implementation narrows that to the exact same
(modifier_id, drug_id) pair. The drug registry's ~7,000 bulk DepMap
compounds have free-text target/mechanism-of-action data but no
structured MoA-class taxonomy (building or licensing one is real,
separate work -- see README's reconciliation notes), and matching on a
loose keyword-derived "class" would repeat the same overclaiming risk
already documented and scoped around in heuristic_bridging.py. Matching
on the literal same drug_id is the honest, conservative version of the
same idea: it only ever borrows a result for the *identical* drug,
never a same-class stand-in.

**Cell-line similarity, real and computable today**: a blend of (a) Jaccard
similarity of the gene sets in each line's real, curated `key_mutations`,
(b) a real oncotree tissue/lineage match bonus (from DepMap's own
Model.csv annotation, see ingest/depmap_prism.py), and (c), where both
lines have one, real expression-based similarity -- Pearson correlation
over the ~212 real genes in the two gene sets already cached by
ingest/msigdb.py (Hallmark Reactive Oxygen Species Pathway, KEGG Hippo
signaling), pulled from DepMap 24Q4's own real expression matrix by
scripts/extract_depmap_expression.py into
data/depmap/curated_cell_line_expression.json (2026-09-23). This is
exactly the spec's own suggested `cell_line_features` composition --
"curated subset relevant to non-pharm mechanisms ... not the full omics
dump" -- built from real data, not the full ~19,000-gene profile. 13 of
the 14 curated cell lines have a real expression profile in this release;
MCF-10A does not (the one non-malignant line in the panel) -- left absent,
not imputed, and similarity for any pair involving it falls back to the
mutation+tissue blend alone rather than guessing an expression
contribution.

Every generated row is tagged unambiguously: `evidence_tier =
tier_2c_nearest_neighbor`, `curator_notes` names every borrowed neighbor
cell line, its similarity score, and its real citation -- never a hidden
score. Never overwrites an existing (modifier_id, drug_id, cell_line_id)
row -- curated or previously-generated evidence always wins, and
re-running this function is idempotent. Cell lines flagged
`poor_model_mesenchymal_shift` are excluded as *donor* neighbors (same
tumor-representativeness posture as bridging.py's Step 6) but can still
*receive* a prediction, since a poor-tumor-model line can still
legitimately want to know what's been found in a genuinely similar line.
"""

from __future__ import annotations

import json
import math
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from synlethality import config
from synlethality.models import (
    CellLine,
    EvidenceTier,
    InteractionEffect,
    InteractionType,
    TumorConcordanceFlag,
)

EXPRESSION_CACHE_PATH = os.path.join(
    config.DATA_DIR, "depmap", "curated_cell_line_expression.json"
)


def _load_expression_cache(cache_path: str = EXPRESSION_CACHE_PATH) -> dict[str, dict[str, float]]:
    """Real per-cell-line expression vectors (scripts/extract_depmap_expression.py's
    output), or {} if not yet extracted -- expression similarity is then
    skipped entirely (falls back to mutation+tissue only), never guessed."""
    if not os.path.isfile(cache_path):
        return {}
    with open(cache_path, encoding="utf-8") as fh:
        return json.load(fh)


def _pearson_correlation(a: dict[str, float], b: dict[str, float]) -> float | None:
    """Real Pearson correlation over the genes both vectors share. None if
    fewer than 3 shared genes (too few to mean anything) or if either
    vector is constant (zero variance -- correlation undefined)."""
    shared = sorted(set(a) & set(b))
    if len(shared) < 3:
        return None
    xs = [a[g] for g in shared]
    ys = [b[g] for g in shared]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / math.sqrt(var_x * var_y)

#: below this similarity, a candidate neighbor is not used at all -- 0.2 is
#: the score of a real tissue-family match with zero shared mutations (see
#: cell_line_similarity), i.e. "at least some real biological basis," not
#: an arbitrary cutoff.
MIN_SIMILARITY = 0.2

DEFAULT_K = 3


#: variant strings that mean "not actually mutated" -- must be excluded from
#: the gene set below, found and fixed 2026-09-23: RKO's curated
#: `{"gene": "TP53", "variant": "wild-type"}` (documenting that RKO is
#: TP53-wild-type, real and useful curated information) was otherwise
#: matched against MDA-MB-231's real `{"gene": "TP53", "variant": "R280K"}`
#: mutation purely by gene name, inflating similarity between a colorectal
#: line and a breast line that don't actually share a mutation at all.
_NON_MUTANT_VARIANTS = {"wild-type", "wildtype", "wt", "none", ""}


def cell_line_similarity(a: CellLine, b: CellLine,
                          expression_cache: dict[str, dict[str, float]] | None = None) -> float:
    """Real, computable similarity in [0, 1]. Tissue/lineage match is
    always a hard gate, not just an additive weight: a shared mutated gene
    (or a similar expression profile) with no tissue/lineage relationship
    at all returns 0.0 rather than a partial score. Same lesson
    bridging.py already learned and documented for signature-panel
    matching: gene-name overlap without tissue context produces
    nonsensical cross-tissue matches (found here 2026-09-23 as a real
    RKO-colorectal x MDA-MB-231-breast false positive, driven by the
    wild-type bug documented on _NON_MUTANT_VARIANTS plus BRAF appearing,
    with different variants, in both lines).

    With real expression data for both lines (see EXPRESSION_CACHE_PATH):
    0.4 x Jaccard(actually-mutated gene sets) + 0.3 x tissue/lineage match
    + 0.3 x expression similarity ((Pearson r + 1) / 2 over the real genes
    both share, from ingest/msigdb.py's cached gene sets). Without it for
    either line (2026-09-23: true only for MCF-10A in this release) or too
    few shared measured genes: falls back to 0.6 x Jaccard + 0.4 x tissue
    match -- never guesses a missing expression contribution.
    `expression_cache` defaults to a real load from EXPRESSION_CACHE_PATH;
    override only for tests.
    """
    genes_a = {
        m["gene"] for m in a.key_mutations
        if isinstance(m, dict) and "gene" in m
        and str(m.get("variant", "")).strip().lower() not in _NON_MUTANT_VARIANTS
    }
    genes_b = {
        m["gene"] for m in b.key_mutations
        if isinstance(m, dict) and "gene" in m
        and str(m.get("variant", "")).strip().lower() not in _NON_MUTANT_VARIANTS
    }
    union = genes_a | genes_b
    jaccard = len(genes_a & genes_b) / len(union) if union else 0.0

    if a.oncotree_primary_disease and a.oncotree_primary_disease == b.oncotree_primary_disease:
        tissue_match = 1.0
    elif a.tissue_origin == b.tissue_origin:
        tissue_match = 0.5
    else:
        return 0.0  # hard gate: no tissue/lineage relationship at all

    if expression_cache is None:
        expression_cache = _load_expression_cache()
    expr_a = expression_cache.get(a.cell_line_id)
    expr_b = expression_cache.get(b.cell_line_id)
    if expr_a and expr_b:
        r = _pearson_correlation(expr_a, expr_b)
        if r is not None:
            expression_similarity = (r + 1.0) / 2.0
            return 0.4 * jaccard + 0.3 * tissue_match + 0.3 * expression_similarity

    return 0.6 * jaccard + 0.4 * tissue_match


def _existing_triples(session: Session) -> set[tuple[str, str, str]]:
    rows = session.execute(
        select(
            InteractionEffect.modifier_id,
            InteractionEffect.drug_id,
            InteractionEffect.cell_line_id,
        )
    ).all()
    return {(m, d, c) for m, d, c in rows}


def generate_nearest_neighbor_candidates(session: Session, k: int = DEFAULT_K,
                                          min_similarity: float = MIN_SIMILARITY) -> dict:
    """For every (modifier_id, drug_id) pair with >=1 real tier_1_direct or
    tier_2_inferred row (i.e. actually tested somewhere), extrapolate to
    every other cell line that has no row at all for that exact pair,
    using similarity-weighted nearest neighbors among the cell lines that
    DO have a real row for it. Returns counts, never the rows themselves --
    callers query interaction_effect directly.
    """
    real_rows = session.execute(
        select(InteractionEffect).where(
            InteractionEffect.evidence_tier.in_(
                [EvidenceTier.tier_1_direct, EvidenceTier.tier_2_inferred]
            )
        )
    ).scalars().all()

    # group real rows by (modifier_id, drug_id) -> list of rows (one per
    # donor cell line; a pair can have >1 real row across different lines)
    by_pair: dict[tuple[str, str], list[InteractionEffect]] = {}
    for r in real_rows:
        by_pair.setdefault((r.modifier_id, r.drug_id), []).append(r)

    all_cell_lines = session.execute(select(CellLine)).scalars().all()
    cell_line_by_id = {cl.cell_line_id: cl for cl in all_cell_lines}
    expression_cache = _load_expression_cache()  # loaded once, not per comparison
    existing = _existing_triples(session)

    counts = {"generated": 0, "skipped_existing": 0, "skipped_no_neighbor": 0}

    for (modifier_id, drug_id), donor_rows in by_pair.items():
        donor_cell_line_ids = {r.cell_line_id for r in donor_rows}
        for target_cl in all_cell_lines:
            if target_cl.cell_line_id in donor_cell_line_ids:
                continue  # already has a real row for this exact pair
            triple = (modifier_id, drug_id, target_cl.cell_line_id)
            if triple in existing:
                counts["skipped_existing"] += 1
                continue

            scored = []
            for donor_row in donor_rows:
                donor_cl = cell_line_by_id.get(donor_row.cell_line_id)
                if donor_cl is None:
                    continue
                if donor_cl.tumor_concordance_flag == TumorConcordanceFlag.poor_model_mesenchymal_shift:
                    continue  # not used as a donor neighbor (Step 6 posture, see module docstring)
                sim = cell_line_similarity(target_cl, donor_cl, expression_cache)
                if sim >= min_similarity:
                    scored.append((sim, donor_cl, donor_row))

            if not scored:
                counts["skipped_no_neighbor"] += 1
                continue

            scored.sort(key=lambda t: t[0], reverse=True)
            neighbors = scored[:k]

            # Weighted-majority interaction_type.
            type_weights: dict[InteractionType, float] = {}
            for sim, _, row in neighbors:
                type_weights[row.interaction_type] = type_weights.get(row.interaction_type, 0.0) + sim
            predicted_type = max(type_weights, key=type_weights.get)

            # Weighted-average combined_effect_metric, only among neighbors
            # that actually have one -- never fabricated for a neighbor
            # that doesn't.
            metric_neighbors = [(sim, row.combined_effect_metric) for sim, _, row in neighbors
                                 if row.combined_effect_metric is not None]
            predicted_metric = None
            if metric_neighbors:
                mw = sum(sim for sim, _ in metric_neighbors)
                predicted_metric = sum(sim * val for sim, val in metric_neighbors) / mw

            citations: list[str] = []
            for _, _, row in neighbors:
                for c in row.source_study:
                    if c not in citations:
                        citations.append(c)

            neighbor_desc = "; ".join(
                f"{cl.name} (similarity={sim:.2f}, {row.interaction_type.value}"
                + (f", metric={row.combined_effect_metric}" if row.combined_effect_metric is not None else "")
                + ")"
                for sim, cl, row in neighbors
            )
            note = (
                f"[Nearest-neighbor prediction -- not a direct test in "
                f"{target_cl.name}] Borrowed from {len(neighbors)} real "
                f"tier_1/tier_2 result(s) for the same modifier x drug pair "
                f"in molecularly/tissue-similar cell line(s): {neighbor_desc}. "
                f"Similarity = Jaccard(key_mutations) + oncotree tissue match, "
                f"blended with real DepMap expression correlation where both "
                f"lines have one (see synlethality/nearest_neighbor.py's "
                f"cell_line_similarity for the exact weights). "
                f"This is an extrapolation from a real measured result in a "
                f"different cell line, not a tested result in {target_cl.name} "
                f"itself, and not a model prediction."
            )

            session.add(InteractionEffect(
                modifier_id=modifier_id,
                drug_id=drug_id,
                cell_line_id=target_cl.cell_line_id,
                combined_effect_metric=predicted_metric,
                interaction_type=predicted_type,
                evidence_tier=EvidenceTier.tier_2c_nearest_neighbor,
                source_study=citations,
                curator_notes=note,
            ))
            existing.add(triple)
            counts["generated"] += 1

    return counts

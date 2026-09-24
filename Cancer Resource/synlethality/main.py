"""
FastAPI application: Combinatorial Fitness Landscape API.

Endpoints
---------
GET  /api/health                 liveness
GET  /api/stats                  dataset summary (counts by tier/type)
GET  /api/evidence_tiers         evidence-tier definitions
GET  /api/cell_lines             filter: q, tissue, mutation
GET  /api/cell_lines/{id}        detail + signatures + responses + interactions
GET  /api/modifiers              filter: modifier_type, q
GET  /api/modifiers/{id}         detail + protocol + signatures + interactions
GET  /api/drugs                  registry with interaction counts
GET  /api/interactions           filter: cell_line_id, modifier_id, drug_id,
                                 evidence_tier, interaction_type, modifier_type
GET  /api/interactions/{id}      full interaction detail page payload
GET  /api/explorer/matrix        cell_line x modifier matrix for one drug
GET  /api/scoring/models         synergy reference models available
POST /api/scoring/synergy        Bliss/HSA/Loewe/ZIP scores for a
                                 modifier-level x drug-dose viability matrix
                                 (Prediction Layer, Step 1)
GET  /api/prediction/readiness   Step 2 gating: Tier 1 label critical mass

The curated seed is loaded automatically on first run (idempotent).
Static frontend is served from ../frontend at "/".
"""

import os

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from synlethality import config
from synlethality.coverage_gaps import compute_coverage_gap_matrix
from synlethality.opportunity_scoring import (
    compute_cancer_type_opportunity_scores,
    compute_cell_line_opportunity_scores,
)
from synlethality.database import get_engine, init_db, make_session_factory
from synlethality.models import (
    EVIDENCE_TIER_DEFINITIONS,
    CellLine,
    ClinicalEvidence,
    Drug,
    DrugResponse,
    EvidenceTier,
    IngestionRun,
    InteractionEffect,
    InteractionType,
    Modifier,
    ModifierType,
    StressSignatureScore,
)
from synlethality.predict import training_readiness
from synlethality.prioritization import (
    PRIORITY_COMPONENT_DESCRIPTIONS,
    PRIORITY_WEIGHTS,
    PriorityScorer,
)
from synlethality.scoring import MODEL_DESCRIPTIONS, MODELS, score_matrix
from synlethality.signature_correlation import correlate_modifier_drug
from synlethality.seed_data import seed as load_seed

engine = get_engine(config.DATABASE_URL)
init_db(engine)
SessionLocal = make_session_factory(engine)

# Auto-seed curated content on first run (idempotent).
with SessionLocal() as _s:
    _seed_result = load_seed(_s)

app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Serialization helpers (enrich joined names for list/table payloads).
# ---------------------------------------------------------------------------

def interaction_row(db: Session, it: InteractionEffect, scorer: "PriorityScorer | None" = None) -> dict:
    d = it.to_dict()
    mod = db.get(Modifier, it.modifier_id)
    cl = db.get(CellLine, it.cell_line_id)
    drug = db.get(Drug, it.drug_id)
    d["modifier_agent"] = mod.agent if mod else None
    d["modifier_type"] = mod.modifier_type.value if mod and mod.modifier_type else None
    d["modifier_infrastructure_requirement"] = (
        mod.infrastructure_requirement.value if mod and mod.infrastructure_requirement else None
    )
    d["cell_line_name"] = cl.name if cl else None
    d["tissue_origin"] = cl.tissue_origin if cl else None
    d["drug_name"] = drug.name if drug else it.drug_id
    d["drug_class"] = drug.drug_class if drug else ""
    d["drug_cost_accessibility_tier"] = (
        drug.cost_accessibility_tier.value if drug and drug.cost_accessibility_tier else None
    )
    # v2 schema (BUILD_SPEC (2).md): surface the LINCS L1000 pointer and
    # cross-refs alongside every interaction row, not just on /drugs/{id} —
    # this is what lets the explorer/interaction pages flag which drugs are
    # already represented in the induced-expression feature space Step 2
    # prediction needs, without a second round-trip to /api/drugs/{id}.
    d["drug_pubchem_cid"] = drug.pubchem_cid if drug else None
    d["drug_clinical_status"] = (
        drug.clinical_status.value if drug and drug.clinical_status else None
    )
    d["drug_lincs_signature_ref"] = drug.induced_expression_signature_ref if drug else None
    d["evidence_tier_label"] = EVIDENCE_TIER_DEFINITIONS.get(
        it.evidence_tier.value if it.evidence_tier else "", {}
    ).get("label")
    # Mechanistic Bridging module (build spec v5): present only on
    # generated hypothesis rows (resistance_mechanism_link set alongside
    # mechanism_link). Never present on curated rows.
    d["resistance_mechanism"] = it.resistance_mechanism.to_dict() if it.resistance_mechanism else None
    d["is_bridging_candidate"] = it.resistance_mechanism_link is not None
    # Build spec v6: computed, not stored (see InteractionEffect docstring).
    # A caller iterating many rows should build one PriorityScorer and pass
    # it in — building one per row would recompute the whole coverage-gap
    # matrix and trial-count query on every call.
    scorer = scorer or PriorityScorer(db)
    d.update(scorer.score(it, drug, mod, cl))
    return d


# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "app": config.APP_TITLE, "version": config.APP_VERSION}


@app.get("/api/evidence_tiers")
def evidence_tiers():
    return EVIDENCE_TIER_DEFINITIONS


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    def _count(model):
        return db.query(func.count()).select_from(model).scalar() or 0

    by_tier = dict(
        db.query(InteractionEffect.evidence_tier, func.count())
        .group_by(InteractionEffect.evidence_tier)
        .all()
    )
    by_type = dict(
        db.query(InteractionEffect.interaction_type, func.count())
        .group_by(InteractionEffect.interaction_type)
        .all()
    )
    by_mod_type = dict(
        db.query(Modifier.modifier_type, func.count())
        .group_by(Modifier.modifier_type)
        .all()
    )
    # Enums come back as enum members on some drivers; normalize to .value.
    def _norm(d):
        return {(k.value if hasattr(k, "value") else str(k)): v for k, v in d.items()}

    return {
        "cell_lines": _count(CellLine),
        "modifiers": _count(Modifier),
        "drugs": _count(Drug),
        "stress_signature_scores": _count(StressSignatureScore),
        "drug_responses": _count(DrugResponse),
        "interaction_effects": _count(InteractionEffect),
        "interactions_by_tier": _norm(by_tier),
        "interactions_by_type": _norm(by_type),
        "modifiers_by_type": _norm(by_mod_type),
        "ingestion_runs": _count(IngestionRun),
    }

# ---------------------------------------------------------------------------
# Cell lines
# ---------------------------------------------------------------------------

@app.get("/api/cell_lines")
def list_cell_lines(
    q: str | None = Query(None, description="name/tissue/subtype substring"),
    tissue: str | None = Query(None),
    mutation: str | None = Query(None, description="gene symbol substring, e.g. TP53"),
    db: Session = Depends(get_db),
):
    stmt = select(CellLine)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CellLine.name.ilike(like),
                CellLine.tissue_origin.ilike(like),
                CellLine.cancer_subtype.ilike(like),
            )
        )
    if tissue:
        stmt = stmt.where(CellLine.tissue_origin.ilike(f"%{tissue}%"))
    if mutation:
        stmt = stmt.where(cast(CellLine.key_mutations, String).ilike(f"%{mutation}%"))
    stmt = stmt.order_by(CellLine.name)
    rows = db.execute(stmt).scalars().all()

    sig_counts = dict(
        db.query(StressSignatureScore.cell_line_id, func.count())
        .group_by(StressSignatureScore.cell_line_id).all()
    )
    int_counts = dict(
        db.query(InteractionEffect.cell_line_id, func.count())
        .group_by(InteractionEffect.cell_line_id).all()
    )
    out = []
    for cl in rows:
        d = cl.to_dict()
        d["signature_count"] = sig_counts.get(cl.cell_line_id, 0)
        d["interaction_count"] = int_counts.get(cl.cell_line_id, 0)
        out.append(d)
    return out


@app.get("/api/cell_lines/{cell_line_id}")
def cell_line_detail(cell_line_id: str, db: Session = Depends(get_db)):
    cl = db.get(CellLine, cell_line_id)
    if cl is None:
        raise HTTPException(status_code=404, detail=f"Cell line '{cell_line_id}' not found")
    d = cl.to_dict()
    d["signature_scores"] = [s.to_dict() for s in cl.signature_scores]
    for s in d["signature_scores"]:
        mod = db.get(Modifier, s["modifier_id"])
        s["modifier_agent"] = mod.agent if mod else None
        s["modifier_type"] = mod.modifier_type.value if mod and mod.modifier_type else None
    d["drug_responses"] = [r.to_dict() for r in cl.drug_responses]
    scorer = PriorityScorer(db)
    d["interactions"] = [interaction_row(db, it, scorer) for it in cl.interactions]
    return d


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------

@app.get("/api/modifiers")
def list_modifiers(
    modifier_type: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(Modifier)
    if modifier_type:
        try:
            stmt = stmt.where(Modifier.modifier_type == ModifierType(modifier_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown modifier_type '{modifier_type}'")
    if q:
        stmt = stmt.where(Modifier.agent.ilike(f"%{q}%"))
    stmt = stmt.order_by(Modifier.modifier_type, Modifier.agent)
    rows = db.execute(stmt).scalars().all()

    sig_counts = dict(
        db.query(StressSignatureScore.modifier_id, func.count())
        .group_by(StressSignatureScore.modifier_id).all()
    )
    int_counts = dict(
        db.query(InteractionEffect.modifier_id, func.count())
        .group_by(InteractionEffect.modifier_id).all()
    )
    out = []
    for m in rows:
        d = m.to_dict()
        d["signature_count"] = sig_counts.get(m.modifier_id, 0)
        d["interaction_count"] = int_counts.get(m.modifier_id, 0)
        out.append(d)
    return out


@app.get("/api/modifiers/{modifier_id}")
def modifier_detail(modifier_id: str, db: Session = Depends(get_db)):
    m = db.get(Modifier, modifier_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"Modifier '{modifier_id}' not found")
    d = m.to_dict()
    d["signature_scores"] = [s.to_dict() for s in m.signature_scores]
    for s in d["signature_scores"]:
        cl = db.get(CellLine, s["cell_line_id"])
        s["cell_line_name"] = cl.name if cl else None
    scorer = PriorityScorer(db)
    d["interactions"] = [interaction_row(db, it, scorer) for it in m.interactions]
    d["cell_lines"] = sorted({it.cell_line.name for it in m.interactions})
    d["drugs"] = sorted({it.drug_id for it in m.interactions})
    return d

# ---------------------------------------------------------------------------
# Drugs
# ---------------------------------------------------------------------------

@app.get("/api/drugs")
def list_drugs(db: Session = Depends(get_db)):
    int_counts = dict(
        db.query(InteractionEffect.drug_id, func.count())
        .group_by(InteractionEffect.drug_id).all()
    )
    resp_counts = dict(
        db.query(DrugResponse.drug_id, func.count())
        .group_by(DrugResponse.drug_id).all()
    )
    known = {d.drug_id: d for d in db.execute(select(Drug)).scalars().all()}
    for drug_id in set(int_counts) | set(resp_counts):
        known.setdefault(
            drug_id,
            Drug(drug_id=drug_id, name=drug_id, drug_class="", target="", source="unregistered"),
        )
    out = []
    for drug_id, drug in sorted(known.items(), key=lambda kv: kv[1].name):
        d = drug.to_dict()
        d["interaction_count"] = int_counts.get(drug_id, 0)
        d["response_count"] = resp_counts.get(drug_id, 0)
        out.append(d)
    return out


@app.get("/api/drugs/{drug_id}")
def drug_detail(drug_id: str, db: Session = Depends(get_db)):
    """Drug detail: cross-referenced IDs plus every known cell-line response
    and interaction for this drug (spec: "GET /drugs/{id}")."""
    drug = db.get(Drug, drug_id)
    if drug is None:
        # Unregistered drug_id referenced only from responses/interactions
        # (same fallback as list_drugs) rather than a bare 404, unless it
        # truly has no rows anywhere.
        has_rows = (
            db.query(InteractionEffect.id).filter_by(drug_id=drug_id).first()
            or db.query(DrugResponse.id).filter_by(drug_id=drug_id).first()
        )
        if not has_rows:
            raise HTTPException(status_code=404, detail=f"Drug '{drug_id}' not found")
        drug = Drug(drug_id=drug_id, name=drug_id, drug_class="", target="", source="unregistered")
    d = drug.to_dict()
    responses = db.execute(
        select(DrugResponse).where(DrugResponse.drug_id == drug_id)
    ).scalars().all()
    d["drug_responses"] = [r.to_dict() for r in responses]
    interactions = db.execute(
        select(InteractionEffect).where(InteractionEffect.drug_id == drug_id)
    ).scalars().all()
    scorer = PriorityScorer(db)
    d["interactions"] = [interaction_row(db, it, scorer) for it in interactions]
    d["cell_lines"] = sorted({it.cell_line.name for it in interactions} |
                              {r.cell_line.name for r in responses})
    # Build spec v5: the drug-side counterpart to a modifier's
    # stress_signature_score, matched against by the Mechanistic Bridging
    # module (synlethality/bridging.py).
    d["resistance_mechanisms"] = [rm.to_dict() for rm in getattr(drug, "resistance_mechanisms", [])]
    return d


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

@app.get("/api/interactions")
def list_interactions(
    cell_line_id: str | None = Query(None),
    modifier_id: str | None = Query(None),
    drug_id: str | None = Query(None),
    evidence_tier: str | None = Query(None),
    interaction_type: str | None = Query(None),
    modifier_type: str | None = Query(None),
    low_resource_relevance: bool | None = Query(
        None, description="build spec v6: filter to drug+modifier pairs "
        "that are both low-cost and low-infrastructure"
    ),
    db: Session = Depends(get_db),
):
    stmt = select(InteractionEffect)
    if cell_line_id:
        stmt = stmt.where(InteractionEffect.cell_line_id == cell_line_id)
    if modifier_id:
        stmt = stmt.where(InteractionEffect.modifier_id == modifier_id)
    if drug_id:
        stmt = stmt.where(InteractionEffect.drug_id == drug_id)
    if evidence_tier:
        try:
            stmt = stmt.where(InteractionEffect.evidence_tier == EvidenceTier(evidence_tier))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown evidence_tier '{evidence_tier}'")
    if interaction_type:
        try:
            stmt = stmt.where(InteractionEffect.interaction_type == InteractionType(interaction_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown interaction_type '{interaction_type}'")
    if modifier_type:
        try:
            mt = ModifierType(modifier_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown modifier_type '{modifier_type}'")
        stmt = stmt.join(Modifier, InteractionEffect.modifier_id == Modifier.modifier_id).where(
            Modifier.modifier_type == mt
        )
    rows = db.execute(stmt).scalars().all()
    scorer = PriorityScorer(db)
    out = [interaction_row(db, it, scorer) for it in rows]
    if low_resource_relevance is not None:
        out = [d for d in out if d["low_resource_relevance"] == low_resource_relevance]
    return out


@app.get("/api/interactions/candidates")
def list_bridging_candidates(
    drug_id: str | None = Query(None),
    cell_line_id: str | None = Query(None),
    tissue_origin: str | None = Query(
        None, description="cell-line tissue_origin substring — a tumor-type "
        "proxy until oncotree_subtype is populated (build spec v5 asks for "
        "filtering 'by drug or tumor type')"
    ),
    low_resource_relevance: bool | None = Query(None),
    sort: str | None = Query(
        None, description="'priority_score' to rank by the build spec v6 "
        "Prioritization Schema (descending); omit for stable name order"
    ),
    db: Session = Depends(get_db),
):
    """Mechanistic Bridging module output (build spec v5): tier_3
    model-generated synergy hypotheses only — never the hand-curated
    mechanism-only rows, which lack resistance_mechanism_link entirely.

    Registered before /interactions/{interaction_id} so "candidates" is
    never parsed as a UUID path parameter.
    """
    stmt = select(InteractionEffect).where(
        InteractionEffect.evidence_tier == EvidenceTier.tier_3_mechanism_only,
        InteractionEffect.interaction_type == InteractionType.synergistic,
        InteractionEffect.resistance_mechanism_link.isnot(None),
    )
    if drug_id:
        stmt = stmt.where(InteractionEffect.drug_id == drug_id)
    if cell_line_id:
        stmt = stmt.where(InteractionEffect.cell_line_id == cell_line_id)
    if tissue_origin:
        stmt = stmt.join(CellLine, InteractionEffect.cell_line_id == CellLine.cell_line_id).where(
            CellLine.tissue_origin.ilike(f"%{tissue_origin}%")
        )
    rows = db.execute(stmt).scalars().all()
    scorer = PriorityScorer(db, tumor_type=tissue_origin)
    out = [interaction_row(db, it, scorer) for it in rows]
    if low_resource_relevance is not None:
        out = [d for d in out if d["low_resource_relevance"] == low_resource_relevance]
    if sort == "priority_score":
        out.sort(key=lambda d: d["priority_score"], reverse=True)
    elif sort and sort != "priority_score":
        raise HTTPException(status_code=400, detail=f"Unknown sort '{sort}'")
    else:
        # No explicit Step 5/7 correlation-based ranking exists (see
        # bridging.py) — stable name order when not sorting by priority_score.
        out.sort(key=lambda d: (d["drug_name"] or "", d["cell_line_name"] or "", d["modifier_agent"] or ""))
    return out


@app.get("/api/interactions/{interaction_id}")
def interaction_detail(interaction_id: str, db: Session = Depends(get_db)):
    import uuid as _uuid

    try:
        uid = _uuid.UUID(interaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="interaction_id must be a UUID")
    it = db.get(InteractionEffect, uid)
    if it is None:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")

    scorer = PriorityScorer(db)
    d = interaction_row(db, it, scorer)
    d["modifier"] = db.get(Modifier, it.modifier_id).to_dict()
    d["cell_line"] = db.get(CellLine, it.cell_line_id).to_dict()
    drug = db.get(Drug, it.drug_id)
    d["drug"] = drug.to_dict() if drug else {"drug_id": it.drug_id, "name": it.drug_id}
    d["mechanism"] = it.mechanism.to_dict() if it.mechanism else None
    d["evidence_tier_definition"] = EVIDENCE_TIER_DEFINITIONS.get(
        it.evidence_tier.value if it.evidence_tier else ""
    )
    # Aggregate clinical-trial evidence (build spec v3): has this specific
    # modifier x drug x cell-line finding been tested in humans yet? Never
    # patient-level data — just registry phase/status + a published summary.
    clinical = db.execute(
        select(ClinicalEvidence).where(ClinicalEvidence.linked_interaction_effect_id == it.id)
    ).scalars().all()
    d["clinical_evidence"] = [c.to_dict() for c in clinical]
    # Related interactions in the same cell line (context panel): a small,
    # curated-first sample, not every sibling row. Before Tier 4 existed a
    # cell line had at most ~10 interactions total, so embedding all of them
    # was harmless; a heuristically-matched line can now have 100+, and
    # embedding every one in every sibling's own detail JSON is quadratic --
    # it inflated a single cell line's static export to ~170MB before this
    # cap. Tier 4 rows are excluded entirely (they have their own filterable
    # view via /api/interactions?evidence_tier=tier_4_heuristic_target_match
    # and are not what "related" is for), and the remaining rows are capped.
    RELATED_LIMIT = 20
    related_stmt = (
        select(InteractionEffect)
        .where(
            InteractionEffect.cell_line_id == it.cell_line_id,
            InteractionEffect.id != it.id,
            InteractionEffect.evidence_tier != EvidenceTier.tier_4_heuristic_target_match,
        )
        .limit(RELATED_LIMIT)
    )
    related = db.execute(related_stmt).scalars().all()
    d["related"] = [interaction_row(db, r, scorer) for r in related]
    d["related_truncated"] = len(related) == RELATED_LIMIT
    return d


# ---------------------------------------------------------------------------
# Coverage Gap Analysis + Prioritization methodology (build spec v6)
# ---------------------------------------------------------------------------

@app.get("/api/coverage-gaps")
def coverage_gaps(
    tumor_type: str | None = Query(
        None, description="cell-line tissue_origin substring — restricts "
        "which existing interactions count toward coverage, not which "
        "drugs/mechanisms are considered"
    ),
    db: Session = Depends(get_db),
):
    """Drug x modifier_type coverage-gap matrix (build spec v6): the
    'what's missing, not just what's known' view. See coverage_gaps.py for
    the gap_score formula."""
    return compute_coverage_gap_matrix(db, tumor_type=tumor_type)


@app.get("/api/prioritization/methodology")
def prioritization_methodology():
    """Published weights/formula for priority_score (build spec v6:
    'publish the weights and formula on the methodology page, not just in
    code') — the frontend renders this rather than hardcoding a second
    copy of the numbers."""
    return {
        "weights": PRIORITY_WEIGHTS,
        "component_descriptions": PRIORITY_COMPONENT_DESCRIPTIONS,
        "formula": "priority_score = sum(weight[c] * component[c] for c in components)",
        "note": "disease_burden carries weight 0.0 pending a confirmed data "
        "source (GLOBOCAN vs. OSMF's Right to Try / Montana SB 535 "
        "therapeutic-adequacy work) — see build spec Open Questions.",
    }


@app.get("/api/opportunity/cell-lines")
def opportunity_cell_lines(db: Session = Depends(get_db)):
    """Cell-line opportunity ranking (reconciling the "NPxP Interaction
    Predictor" build spec's section 6): opportunity_score = predicted_uplift
    x gap_weight, a genuinely different question from /api/interactions/
    candidates?sort=priority_score's row-level ranking -- see
    synlethality/opportunity_scoring.py for exactly how and why."""
    return compute_cell_line_opportunity_scores(db)


@app.get("/api/opportunity/cancer-types")
def opportunity_cancer_types(db: Session = Depends(get_db)):
    """Roll-up of /api/opportunity/cell-lines by oncotree_primary_disease."""
    return compute_cancer_type_opportunity_scores(db)


# ---------------------------------------------------------------------------
# Explorer matrix: cell lines x modifiers for one drug (or drug class).
# ---------------------------------------------------------------------------

@app.get("/api/explorer/matrix")
def explorer_matrix(
    drug_id: str | None = Query(None),
    drug_class: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not drug_id and not drug_class:
        raise HTTPException(status_code=400, detail="Provide drug_id or drug_class")

    stmt = select(InteractionEffect)
    if drug_id:
        stmt = stmt.where(InteractionEffect.drug_id == drug_id)
    else:
        class_drug_ids = [
            d.drug_id
            for d in db.execute(select(Drug).where(Drug.drug_class == drug_class)).scalars().all()
        ]
        if not class_drug_ids:
            raise HTTPException(status_code=404, detail=f"No drugs in class '{drug_class}'")
        stmt = stmt.where(InteractionEffect.drug_id.in_(class_drug_ids))

    interactions = db.execute(stmt).scalars().all()
    cells = []
    cl_ids, mod_ids = set(), set()
    for it in interactions:
        cl_ids.add(it.cell_line_id)
        mod_ids.add(it.modifier_id)
        cells.append(
            {
                "interaction_id": str(it.id),
                "cell_line_id": it.cell_line_id,
                "modifier_id": it.modifier_id,
                "drug_id": it.drug_id,
                "interaction_type": it.interaction_type.value if it.interaction_type else None,
                "evidence_tier": it.evidence_tier.value if it.evidence_tier else None,
                "combined_effect_metric": it.combined_effect_metric,
            }
        )

    cell_lines = []
    for cid in cl_ids:
        cl = db.get(CellLine, cid)
        if cl is not None:
            cell_lines.append(cl.to_dict())
    cell_lines.sort(key=lambda c: c["name"])

    modifiers = []
    for mid in mod_ids:
        m = db.get(Modifier, mid)
        if m is not None:
            modifiers.append(m.to_dict())
    modifiers.sort(key=lambda m: (m["modifier_type"] or "", m["agent"] or ""))

    drug = db.get(Drug, drug_id) if drug_id else None
    return {
        "drug": drug.to_dict() if drug else None,
        "drug_class": drug_class,
        "cell_lines": cell_lines,
        "modifiers": modifiers,
        "cells": cells,
        "evidence_tier_definitions": EVIDENCE_TIER_DEFINITIONS,
    }


# ---------------------------------------------------------------------------
# Prediction Layer — Step 1 (synergy scoring) and Step 2 (gated stub)
# ---------------------------------------------------------------------------

@app.get("/api/scoring/models")
def scoring_models():
    """Reference models implemented by the synergy scoring engine."""
    return [
        {
            "name": name,
            "description": MODEL_DESCRIPTIONS[name],
            "requires_edge_fit": name in ("loewe", "zip"),
        }
        for name in MODELS
    ]


@app.post("/api/scoring/synergy")
def synergy_score(payload: dict = Body(...)):
    """Score a modifier-level x drug-dose viability matrix.

    Body: {"doses_a": [0, ...], "doses_b": [0, ...],
           "viability": [[...], ...],
           "models": optional subset of ["bliss", "hsa", "loewe", "zip"],
           "viability_scale": "fraction" (default) or "percent"}.
    Scores are effect-excess (positive = synergistic); edge cells are null.
    Results are returned to the caller only — never persisted, so curated
    claims remain traceable to cited sources.
    """
    try:
        return score_matrix(
            doses_a=payload.get("doses_a"),
            doses_b=payload.get("doses_b"),
            viability=payload.get("viability"),
            models=payload.get("models"),
            viability_scale=payload.get("viability_scale", "fraction"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:  # numpy/scipy unavailable
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/api/prediction/readiness")
def prediction_readiness(db: Session = Depends(get_db)):
    """Step 2 gating: whether enough Tier 1 labels exist to train a model."""
    return training_readiness(db)


@app.get("/api/signature-correlation")
def signature_correlation(modifier_key: str, drug_id: str):
    """Prediction Methodology Stage 1 at scale, real on-demand computation:
    ccmap-style XSum correlation between a modifier's real GEO-derived DEG
    signature and a drug's real LINCS-derived induced signature (see
    synlethality/signature_correlation.py's correlate_modifier_drug).
    Results are computed and returned only, never persisted to
    interaction_effect -- this is a real, tested capability, not yet wired
    into automatic candidate generation (see README for why: it would need
    a schema decision on how to distinguish this from bridging.py's
    resistance-mechanism-based Tier 3 output, not made yet).
    """
    try:
        return correlate_modifier_drug(modifier_key, drug_id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"No real signature data for that modifier/drug pair yet: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Static frontend (mounted last so /api routes take precedence).
# ---------------------------------------------------------------------------

if os.path.isdir(config.FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")

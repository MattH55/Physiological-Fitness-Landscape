"""
FastAPI REST API Service for Physiological Fitness Landscape — Mortality Biomarker Dashboard.

Endpoints:
- `GET /api/biomarkers` — list all biomarkers with category/search filters, evidence stats & risk profiles
- `GET /api/biomarkers/{id_or_slug}` — full detail: associations, distributions, interventions, and citations
- `GET /api/biomarkers/{id_or_slug}/hr-distribution` — forest plot array of HRs with CIs and normalizations
- `GET /api/biomarkers/{id_or_slug}/population-distribution` — age/sex stratified percentile data for chart rendering
- `GET /api/compare?ids=1,2,3` — side-by-side comparative payload with normalized HRs
- `GET /api/sources` — citation registry with PMID/DOI resolution links
- `GET /api/stats` — overall platform and database summary metrics
"""

import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import or_, func

from backend.models import (
    Biomarker,
    Source,
    MortalityAssociation,
    PopulationDistribution,
    Intervention,
    BiomarkerHRCurve,
    BiomarkerOptimizationModel,
    OptimizationScenario,
    BiomarkerExpectedValue,
    Disease,
    DiseaseAlteration,
    Condition,
    BiomarkerSignature,
    DistributionFit,
    HRFunction,
    get_engine,
    init_db
)
from backend.optimization_engine import compute_shift_optimization, run_voi_monte_carlo_simulation
from backend.disease_signature_engine import (
    build_disease_signatures,
    find_top_similar_diseases,
    compute_disease_similarity
)
from backend.citation_audit import audit_citations
from backend.discrepancy_report import run_spline_discrepancy_audit
from backend.interventions_catalog import INTERVENTIONS_CATALOG

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

engine = get_engine(f"sqlite:///{DB_PATH}")
init_db(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(
    title="Physiological Fitness Landscape — Mortality Biomarker API",
    description="REST API mapping all-cause mortality hazard ratios, population distributions, and interventions.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api/optimization/scenarios")
def get_optimization_scenarios(db: Session = Depends(get_db)):
    """Return all standard population shift scenarios."""
    scenarios = db.query(OptimizationScenario).all()
    return [s.to_dict() for s in scenarios]


@app.get("/api/optimization/leaderboard")
def get_optimization_leaderboard(
    scenario_slug: str = Query("sd_1_00", description="Scenario slug e.g. sd_0_50, sd_1_00, p25_to_p50"),
    causal_status: Optional[str] = None,
    category: Optional[str] = None,
    primary_organ: Optional[str] = None,
    bodily_fluid: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Return ranking of biomarkers by expected hazard reduction under the specified shift scenario."""
    query = (
        db.query(BiomarkerExpectedValue, Biomarker, OptimizationScenario)
        .join(Biomarker, BiomarkerExpectedValue.biomarker_id == Biomarker.id)
        .join(OptimizationScenario, BiomarkerExpectedValue.scenario_id == OptimizationScenario.id)
        .filter(OptimizationScenario.slug == scenario_slug)
    )

    if causal_status:
        query = query.filter(Biomarker.causal_status == causal_status)
    if category:
        query = query.filter(Biomarker.category.ilike(f"%{category}%"))
    if primary_organ:
        query = query.filter(Biomarker.primary_organ.ilike(f"%{primary_organ}%"))
    if bodily_fluid:
        query = query.filter(Biomarker.bodily_fluid.ilike(f"%{bodily_fluid}%"))

    results = query.order_by(BiomarkerExpectedValue.relative_hazard_reduction.desc()).all()

    leaderboard = []
    for rank, (ev, b, sc) in enumerate(results, 1):
        leaderboard.append({
            "rank": rank,
            "biomarker_id": b.id,
            "biomarker_slug": b.slug,
            "biomarker_name": b.name,
            "category": b.category,
            "bodily_fluid": b.bodily_fluid,
            "primary_organ": b.primary_organ,
            "tissue_origin": b.tissue_origin,
            "units": b.units,
            "directionality": b.directionality,
            "causal_status": b.causal_status,
            "scenario_name": sc.name,
            "scenario_slug": sc.slug,
            "delta_hr": ev.delta_hr,
            "relative_hazard_reduction": ev.relative_hazard_reduction,
            "percent_hazard_reduction": ev.relative_hazard_reduction * 100.0,
            "baseline_expected_hr": ev.baseline_expected_hr,
            "optimized_expected_hr": ev.optimized_expected_hr,
            "mean_individual_benefit": ev.mean_individual_benefit,
            "median_individual_benefit": ev.median_individual_benefit,
            "p90_benefit": ev.p90_benefit,
            "fraction_benefiting": ev.fraction_benefiting,
            "fraction_harmed": ev.fraction_harmed,
            "domain_status": ev.domain_status,
            "fraction_out_of_domain": ev.fraction_out_of_domain
        })

    return {
        "scenario_slug": scenario_slug,
        "count": len(leaderboard),
        "leaderboard": leaderboard
    }


@app.get("/api/biomarkers/{id_or_slug}/optimization")
def get_biomarker_optimization(
    id_or_slug: str,
    db: Session = Depends(get_db)
):
    """Return complete optimization model, HR curve, and precomputed scenarios for a biomarker."""
    if id_or_slug.isdigit():
        b = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        b = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not b:
        raise HTTPException(status_code=404, detail="Biomarker not found")

    curves = db.query(BiomarkerHRCurve).filter(BiomarkerHRCurve.biomarker_id == b.id).all()
    models = db.query(BiomarkerOptimizationModel).filter(BiomarkerOptimizationModel.biomarker_id == b.id).all()
    
    expected_values = (
        db.query(BiomarkerExpectedValue, OptimizationScenario)
        .join(OptimizationScenario, BiomarkerExpectedValue.scenario_id == OptimizationScenario.id)
        .filter(BiomarkerExpectedValue.biomarker_id == b.id)
        .all()
    )

    ev_list = []
    for ev, sc in expected_values:
        d = ev.to_dict()
        d["scenario_name"] = sc.name
        d["scenario_slug"] = sc.slug
        d["shift_magnitude"] = sc.shift_magnitude
        d["shift_type"] = sc.shift_type
        ev_list.append(d)

    return {
        "biomarker": b.to_dict(),
        "curves": [c.to_dict() for c in curves],
        "models": [m.to_dict() for m in models],
        "expected_values": ev_list
    }


@app.post("/api/biomarkers/{id_or_slug}/simulate-shift")
def simulate_biomarker_shift(
    id_or_slug: str,
    shift_sd: float = Query(1.0, ge=-3.0, le=3.0, description="Shift in standard deviations"),
    db: Session = Depends(get_db)
):
    """Dynamically compute expected hazard reduction for an arbitrary shift magnitude."""
    from backend.optimization_engine import generate_population_distribution, compute_baseline_expected_hazard, compute_shift_optimization

    if id_or_slug.isdigit():
        b = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        b = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not b:
        raise HTTPException(status_code=404, detail="Biomarker not found")

    curve = db.query(BiomarkerHRCurve).filter(BiomarkerHRCurve.biomarker_id == b.id).first()
    pop_dist = db.query(PopulationDistribution).filter(
        PopulationDistribution.biomarker_id == b.id,
        PopulationDistribution.sex == "all",
        PopulationDistribution.age_band == "all"
    ).first()

    if not curve or not pop_dist:
        raise HTTPException(status_code=400, detail="Biomarker missing curve or population distribution data")

    x_bins, probs = generate_population_distribution(
        mean=pop_dist.mean,
        sd=pop_dist.sd,
        valid_min=curve.valid_min,
        valid_max=curve.valid_max,
        p5=pop_dist.p5,
        p50=pop_dist.p50,
        p95=pop_dist.p95
    )
    baseline_ehr, baseline_hrs = compute_baseline_expected_hazard(
        x_bins=x_bins,
        probabilities=probs,
        curve_type=curve.curve_type,
        reference_value=curve.reference_value,
        parameters=curve.parameters or {},
        optimal_value=curve.optimal_value
    )

    res = compute_shift_optimization(
        x_bins=x_bins,
        probabilities=probs,
        baseline_hrs=baseline_hrs,
        curve_type=curve.curve_type,
        reference_value=curve.reference_value,
        parameters=curve.parameters or {},
        valid_min=curve.valid_min,
        valid_max=curve.valid_max,
        directionality=b.directionality or "lower_better",
        pop_sd=pop_dist.sd,
        shift_type="sd_shift",
        shift_magnitude=shift_sd,
        optimal_value=curve.optimal_value,
        pop_median=pop_dist.p50,
        pop_p25=pop_dist.p25,
        pop_p75=pop_dist.p75
    )

    return {
        "biomarker_id": b.id,
        "biomarker_name": b.name,
        "shift_sd": shift_sd,
        "result": res
    }


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return top-level counts and overview statistics."""
    biomarker_count = db.query(func.count(Biomarker.id)).scalar()
    source_count = db.query(func.count(Source.id)).scalar()
    assoc_count = db.query(func.count(MortalityAssociation.id)).scalar()
    dist_count = db.query(func.count(PopulationDistribution.id)).scalar()
    intervention_count = db.query(func.count(Intervention.id)).scalar()
    categories = [c[0] for c in db.query(Biomarker.category).distinct().all() if c[0]]
    bodily_fluids = [f[0] for f in db.query(Biomarker.bodily_fluid).distinct().all() if f[0]]
    primary_organs = [o[0] for o in db.query(Biomarker.primary_organ).distinct().all() if o[0]]
    tissue_origins = [t[0] for t in db.query(Biomarker.tissue_origin).distinct().all() if t[0]]

    disease_count = db.query(func.count(Disease.id)).scalar()
    alteration_count = db.query(func.count(DiseaseAlteration.id)).scalar()
    matched_alterations_count = db.query(func.count(DiseaseAlteration.id)).filter(DiseaseAlteration.is_biomarker_match == 1).scalar()

    return {
        "biomarkers_total": biomarker_count,
        "sources_total": source_count,
        "mortality_associations_total": assoc_count,
        "population_distributions_total": dist_count,
        "interventions_total": intervention_count,
        "diseases_total": disease_count,
        "disease_alterations_total": alteration_count,
        "disease_biomarker_matches_total": matched_alterations_count,
        "categories": sorted(categories),
        "bodily_fluids": sorted(bodily_fluids),
        "primary_organs": sorted(primary_organs),
        "tissue_origins": sorted(tissue_origins),
    }


@app.get("/api/biomarkers")
def list_biomarkers(
    category: Optional[str] = None,
    specimen: Optional[str] = None,
    bodily_fluid: Optional[str] = None,
    primary_organ: Optional[str] = None,
    tissue_origin: Optional[str] = None,
    q: Optional[str] = None,
    sort_by: str = Query("name", enum=["name", "category", "associations_count", "interventions_count", "primary_organ", "bodily_fluid"]),
    db: Session = Depends(get_db)
):
    """List biomarkers with filtering, search query, and summarized evidence metrics."""
    query = db.query(Biomarker)
    
    if category:
        query = query.filter(Biomarker.category.ilike(f"%{category}%"))
    if specimen:
        query = query.filter(Biomarker.specimen_type == specimen)
    if bodily_fluid:
        query = query.filter(Biomarker.bodily_fluid.ilike(f"%{bodily_fluid}%"))
    if primary_organ:
        query = query.filter(Biomarker.primary_organ.ilike(f"%{primary_organ}%"))
    if tissue_origin:
        query = query.filter(Biomarker.tissue_origin.ilike(f"%{tissue_origin}%"))
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Biomarker.name.ilike(search),
                Biomarker.category.ilike(search),
                Biomarker.bodily_fluid.ilike(search),
                Biomarker.primary_organ.ilike(search),
                Biomarker.tissue_origin.ilike(search),
                Biomarker.notes.ilike(search)
            )
        )

    biomarkers = query.all()
    results = []
    
    for b in biomarkers:
        assocs = b.mortality_associations
        itvs = b.interventions
        dists = b.population_distributions
        
        # Primary direction & max HR
        max_hr = max([a.hazard_ratio for a in assocs]) if assocs else None
        min_hr = min([a.hazard_ratio for a in assocs]) if assocs else None
        primary_dir = assocs[0].direction if assocs else "unknown"

        # Baseline national median
        overall_dist = next((d for d in dists if d.sex == "all" and d.age_band == "all"), None)

        b_dict = b.to_dict()
        b_dict.update({
            "associations_count": len(assocs),
            "interventions_count": len(itvs),
            "distributions_count": len(dists),
            "max_hazard_ratio": max_hr,
            "min_hazard_ratio": min_hr,
            "primary_direction": primary_dir,
            "population_median": overall_dist.p50 if overall_dist else None,
            "population_mean": overall_dist.mean if overall_dist else None,
            "population_sd": overall_dist.sd if overall_dist else None,
            "has_nhanes": bool(b.nhanes_code)
        })
        results.append(b_dict)

    if sort_by == "associations_count":
        results.sort(key=lambda x: x["associations_count"], reverse=True)
    elif sort_by == "interventions_count":
        results.sort(key=lambda x: x["interventions_count"], reverse=True)
    elif sort_by == "category":
        results.sort(key=lambda x: (x["category"], x["name"]))
    elif sort_by == "primary_organ":
        results.sort(key=lambda x: (x.get("primary_organ") or "", x["name"]))
    elif sort_by == "bodily_fluid":
        results.sort(key=lambda x: (x.get("bodily_fluid") or "", x["name"]))
    else:
        results.sort(key=lambda x: x["name"])

    return results


@app.get("/api/biomarkers/{id_or_slug}")
def get_biomarker_detail(id_or_slug: str, db: Session = Depends(get_db)):
    """Return full biomarker detail including all associations, distributions, and interventions."""
    if id_or_slug.isdigit():
        b = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        b = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not b:
        raise HTTPException(status_code=404, detail="Biomarker not found")

    detail = b.to_dict()
    detail["associations"] = [a.to_dict() for a in b.mortality_associations]
    detail["population_distributions"] = [d.to_dict() for d in b.population_distributions]
    detail["interventions"] = [i.to_dict() for i in b.interventions]
    
    # Collect unique sources
    source_ids = set()
    for a in b.mortality_associations:
        if a.source_id:
            source_ids.add(a.source_id)
    for d in b.population_distributions:
        if d.source_id:
            source_ids.add(d.source_id)
    for i in b.interventions:
        if i.source_id:
            source_ids.add(i.source_id)

    sources = db.query(Source).filter(Source.id.in_(list(source_ids))).all() if source_ids else []
    detail["sources"] = [s.to_dict() for s in sources]

    return detail


@app.get("/api/biomarkers/{id_or_slug}/hr-distribution")
def get_hr_distribution(id_or_slug: str, db: Session = Depends(get_db)):
    """Return array of published hazard ratios formatted for forest plots."""
    if id_or_slug.isdigit():
        b = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        b = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not b:
        raise HTTPException(status_code=404, detail="Biomarker not found")

    forest_items = []
    for a in b.mortality_associations:
        forest_items.append({
            "id": a.id,
            "study": a.source.citation if a.source else "Unassigned Source",
            "year": a.source.year if a.source else None,
            "pmid": a.source.pmid if a.source else None,
            "doi": a.source.doi if a.source else None,
            "hazard_ratio": a.hazard_ratio,
            "ci_lower": a.ci_lower,
            "ci_upper": a.ci_upper,
            "hr_type": a.hr_type,
            "direction": a.direction,
            "cohort_description": a.cohort_description,
            "n": a.n,
            "events": a.events,
            "adjustment_covariates": a.adjustment_covariates,
            "notes": a.notes
        })

    return {
        "biomarker_id": b.id,
        "biomarker_name": b.name,
        "units": b.units,
        "forest_plots": forest_items
    }


@app.get("/api/biomarkers/{id_or_slug}/population-distribution")
def get_pop_distribution(
    id_or_slug: str,
    sex: Optional[str] = "all",
    age_band: Optional[str] = "all",
    db: Session = Depends(get_db)
):
    """Return stratified population percentiles and parametric density estimations."""
    if id_or_slug.isdigit():
        b = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        b = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not b:
        raise HTTPException(status_code=404, detail="Biomarker not found")

    query = db.query(PopulationDistribution).filter(PopulationDistribution.biomarker_id == b.id)
    
    if sex:
        query = query.filter(PopulationDistribution.sex == sex)
    if age_band:
        query = query.filter(PopulationDistribution.age_band == age_band)

    dists = query.all()
    # If specific stratum not found, return all available strata for this biomarker
    if not dists:
        dists = db.query(PopulationDistribution).filter(PopulationDistribution.biomarker_id == b.id).all()

    return {
        "biomarker_id": b.id,
        "biomarker_name": b.name,
        "units": b.units,
        "strata": [d.to_dict() for d in dists]
    }


@app.get("/api/compare")
def compare_biomarkers(ids: str = Query(..., description="Comma-separated biomarker IDs or slugs"), db: Session = Depends(get_db)):
    """Side-by-side comparison payload for 2 to 6 biomarkers with standardized hazard ratios."""
    id_list = [item.strip() for item in ids.split(",") if item.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="Must provide at least one biomarker ID")

    biomarkers = []
    for identifier in id_list:
        if identifier.isdigit():
            b = db.query(Biomarker).filter(Biomarker.id == int(identifier)).first()
        else:
            b = db.query(Biomarker).filter(Biomarker.slug == identifier).first()
        if b and b not in biomarkers:
            biomarkers.append(b)

    comparisons = []
    for b in biomarkers:
        pop = next((d for d in b.population_distributions if d.sex == "all" and d.age_band == "all"), None)
        assocs = b.mortality_associations
        
        # Determine normalized per-SD risk
        primary_assoc = assocs[0] if assocs else None
        
        comparisons.append({
            "id": b.id,
            "slug": b.slug,
            "name": b.name,
            "category": b.category,
            "units": b.units,
            "specimen_type": b.specimen_type,
            "population_mean": pop.mean if pop else None,
            "population_sd": pop.sd if pop else None,
            "population_p50": pop.p50 if pop else None,
            "primary_association": primary_assoc.to_dict() if primary_assoc else None,
            "associations_count": len(assocs),
            "interventions_count": len(b.interventions),
            "interventions_summary": {
                "favorable": [i.to_dict() for i in b.interventions if i.direction == "favorable"],
                "unfavorable": [i.to_dict() for i in b.interventions if i.direction == "unfavorable"]
            }
        })

    return {
        "count": len(comparisons),
        "comparisons": comparisons
    }


@app.get("/api/sources")
def list_sources(db: Session = Depends(get_db)):
    """Return all verified sources and publications with resolved URLs."""
    sources = db.query(Source).order_by(Source.year.desc().nullslast()).all()
    return [s.to_dict() for s in sources]


# ==============================================================================
# Disease Intelligence & Alteration Mapping Endpoints
# ==============================================================================

@app.get("/api/diseases")
def list_diseases(
    q: Optional[str] = None,
    sort_by: str = Query("name", enum=["name", "alterations_count", "therapeutics_count", "us_dalys", "global_dalys", "nih_funding"]),
    db: Session = Depends(get_db)
):
    """
    List chronic disease profiles from the disease intelligence dataset,
    including burden metrics, remission profiles, and alteration counts.
    """
    query = db.query(Disease)
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Disease.name.ilike(search),
                Disease.slug.ilike(search),
                Disease.primary_barrier.ilike(search),
                Disease.barrier_detail.ilike(search)
            )
        )

    diseases = query.all()
    results = [d.to_dict() for d in diseases]

    if sort_by == "alterations_count":
        results.sort(key=lambda x: x.get("alterations_count") or 0, reverse=True)
    elif sort_by == "therapeutics_count":
        results.sort(key=lambda x: x.get("therapeutics_count") or 0, reverse=True)
    elif sort_by == "us_dalys":
        results.sort(key=lambda x: x.get("us_dalys") or "", reverse=True)
    elif sort_by == "global_dalys":
        results.sort(key=lambda x: x.get("global_dalys") or "", reverse=True)
    elif sort_by == "nih_funding":
        results.sort(key=lambda x: x.get("nih_funding") or "", reverse=True)
    else:
        results.sort(key=lambda x: x["name"])

    return {
        "count": len(results),
        "diseases": results
    }


@app.get("/api/diseases/signatures")
def get_all_disease_signatures(db: Session = Depends(get_db)):
    """
    Returns structured disease-signature / combined-panel representations
    for all 113+ diseases across 50 biomarkers.
    """
    signatures = build_disease_signatures(db)
    return {
        "total_diseases": len(signatures),
        "signatures": signatures
    }


@app.get("/api/diseases/similarity-matrix")
def get_global_disease_similarity_matrix(db: Session = Depends(get_db)):
    """
    Returns global disease-to-disease similarity matrix and hierarchical clusters.
    """
    from backend.disease_signature_engine import compute_global_disease_similarity_matrix
    return compute_global_disease_similarity_matrix(db)


@app.get("/api/diseases/{id_or_slug}/similar")
def get_similar_diseases(id_or_slug: str, top_n: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """
    Find top diseases with overlapping biomarker alteration signatures and panels.
    """
    target_slug = id_or_slug
    if id_or_slug.isdigit():
        d = db.query(Disease).filter(Disease.id == int(id_or_slug)).first()
        if d:
            target_slug = d.slug

    all_signatures = build_disease_signatures(db)
    # Check either slug or integer id in signatures keys
    target_key = target_slug
    if target_key not in all_signatures:
        if id_or_slug.isdigit() and int(id_or_slug) in all_signatures:
            target_key = int(id_or_slug)
        else:
            raise HTTPException(status_code=404, detail="Disease signature not found")

    similar = find_top_similar_diseases(target_key, all_signatures, top_n=top_n)
    return {
        "target_disease": all_signatures[target_key],
        "similar_diseases": similar
    }


@app.get("/api/diseases/{id_or_slug}")
def get_disease_detail(id_or_slug: str, db: Session = Depends(get_db)):
    """
    Return full disease profile including multi-scale alterations
    (Molecular, Lab/Clinical, Scales/PROs, Pathology, Functional) and matched fitness landscape biomarkers.
    """
    if id_or_slug.isdigit():
        d = db.query(Disease).filter(Disease.id == int(id_or_slug)).first()
    else:
        d = db.query(Disease).filter(Disease.slug == id_or_slug).first()

    if not d:
        raise HTTPException(status_code=404, detail="Disease not found")

    detail = d.to_dict()
    alterations = db.query(DiseaseAlteration).filter(DiseaseAlteration.disease_id == d.id).all()
    detail["alterations"] = [alt.to_dict() for alt in alterations]
    detail["matched_biomarkers_count"] = sum(1 for alt in alterations if alt.is_biomarker_match)

    # Group alterations by type
    by_type = {}
    for alt in alterations:
        t = alt.alteration_type or "Other"
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(alt.to_dict())
    detail["alterations_by_type"] = by_type

    return detail


@app.get("/api/biomarkers/{id_or_slug}/diseases")
def get_biomarker_diseases(id_or_slug: str, db: Session = Depends(get_db)):
    """
    Retrieve all chronic diseases and multi-scale alterations linked to a specific biomarker in the fitness landscape.
    """
    if id_or_slug.isdigit():
        b = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        b = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not b:
        raise HTTPException(status_code=404, detail="Biomarker not found")

    alterations = (
        db.query(DiseaseAlteration, Disease)
        .join(Disease, DiseaseAlteration.disease_id == Disease.id)
        .filter(DiseaseAlteration.biomarker_id == b.id)
        .all()
    )

    results = []
    for alt, dis in alterations:
        alt_d = alt.to_dict()
        alt_d["disease_name"] = dis.name
        alt_d["disease_slug"] = dis.slug
        alt_d["us_dalys"] = dis.us_dalys
        alt_d["global_dalys"] = dis.global_dalys
        results.append(alt_d)

    return {
        "biomarker_id": b.id,
        "biomarker_slug": b.slug,
        "biomarker_name": b.name,
        "category": b.category,
        "diseases_count": len(set(a["disease_id"] for a in results)),
        "alterations_count": len(results),
        "alterations": results
    }


@app.get("/api/alterations")
def list_alterations(
    alteration_type: Optional[str] = None,
    direction: Optional[str] = None,
    evidence_level: Optional[str] = None,
    matched_only: bool = False,
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Filter and search alterations across all diseases by type (Molecular, Lab/Clinical, etc.),
    direction (Elevated, Reduced, etc.), evidence level, or biomarker match status.
    """
    query = db.query(DiseaseAlteration)

    if alteration_type:
        query = query.filter(DiseaseAlteration.alteration_type.ilike(f"%{alteration_type}%"))
    if direction:
        query = query.filter(DiseaseAlteration.direction.ilike(f"%{direction}%"))
    if evidence_level:
        query = query.filter(DiseaseAlteration.evidence_level.ilike(f"%{evidence_level}%"))
    if matched_only:
        query = query.filter(DiseaseAlteration.is_biomarker_match == 1)
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                DiseaseAlteration.name.ilike(search),
                DiseaseAlteration.sub_name.ilike(search),
                DiseaseAlteration.subtype.ilike(search)
            )
        )

    total_count = query.count()
    alterations = query.offset(offset).limit(limit).all()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "alterations": [a.to_dict() for a in alterations]
    }


# ==========================================
# NEW ENDPOINTS: Interventions, Signatures, Similarity, Audit
# ==========================================

@app.get("/api/interventions")
def get_interventions_catalog_endpoint(
    biomarker: Optional[str] = None,
    category: Optional[str] = None,
    direction: Optional[str] = None,
    evidence_strength: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Query the complete 50-biomarker interventions catalog (favorable and unfavorable).
    Returns both structured biomarker catalog and summary.
    """
    from backend.interventions_catalog import INTERVENTIONS_CATALOG, get_all_interventions_summary

    if not biomarker and not category and not direction and not evidence_strength and not q:
        return {
            "biomarkers": INTERVENTIONS_CATALOG,
            "summary": get_all_interventions_summary(),
            "total": len(INTERVENTIONS_CATALOG)
        }

    query = db.query(Intervention).join(Biomarker)

    if biomarker:
        if biomarker.isdigit():
            query = query.filter(Intervention.biomarker_id == int(biomarker))
        else:
            query = query.filter(Biomarker.slug == biomarker)
    if category:
        query = query.filter(Intervention.category.ilike(f"%{category}%"))
    if direction:
        query = query.filter(Intervention.direction.ilike(f"%{direction}%"))
    if evidence_strength:
        query = query.filter(Intervention.evidence_strength.ilike(f"%{evidence_strength}%"))
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Intervention.name.ilike(search),
                Intervention.effect_description.ilike(search),
                Intervention.citation_ref.ilike(search)
            )
        )

    total_count = query.count()
    items = query.offset(offset).limit(limit).all()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "interventions": [
            {
                **i.to_dict(),
                "biomarker_slug": i.biomarker.slug if i.biomarker else None,
                "biomarker_name": i.biomarker.name if i.biomarker else None,
                "biomarker_category": i.biomarker.category if i.biomarker else None
            }
            for i in items
        ]
    }


@app.get("/api/interventions/{name_or_slug}")
def get_biomarker_interventions_endpoint(name_or_slug: str):
    """
    Retrieve favorable and unfavorable interventions for a specific biomarker name or slug.
    """
    from backend.interventions_catalog import get_interventions_for_biomarker
    res = get_interventions_for_biomarker(name_or_slug)
    if not res.get("favorable") and not res.get("unfavorable"):
        # Check if slug exists in catalog
        from backend.interventions_catalog import INTERVENTIONS_CATALOG
        if name_or_slug not in INTERVENTIONS_CATALOG:
            raise HTTPException(status_code=404, detail=f"Biomarker '{name_or_slug}' not found in interventions catalog")
    return res




@app.get("/api/audit/citations")
def get_citation_audit_report(db: Session = Depends(get_db)):
    """
    Audit 500+ literature citations, verify PMID/DOI formatting, and check HR sanity.
    """
    report = audit_citations(db)
    return report


@app.get("/api/audit/discrepancies")
def get_spline_discrepancy_report(db: Session = Depends(get_db)):
    """
    Cross-validate all 50 biomarker splines against literature consensus,
    flagging outliers > 20% off reference bounds.
    """
    report = run_spline_discrepancy_audit(db)
    return report


# -------------------------------------------------------------------------
# Conditions and Competing Published Biomarker Panels
# -------------------------------------------------------------------------

@app.get("/api/conditions")
def get_conditions(db: Session = Depends(get_db)):
    """
    List all clinical disease states / condition panels with their associated signatures.
    """
    conditions = db.query(Condition).all()
    results = []
    for cond in conditions:
        cond_dict = cond.to_dict()
        cond_dict["panels"] = sorted(list({sig.panel_name for sig in cond.signatures}))
        cond_dict["competing_panels"] = sorted(list({sig.panel_name for sig in cond.signatures}))
        cond_dict["signature_count"] = len(cond.signatures)
        cond_dict["signatures"] = [sig.to_dict() for sig in cond.signatures]
        results.append(cond_dict)
    return {
        "conditions": results,
        "count": len(results)
    }


@app.get("/api/conditions/{id_or_slug}")
def get_condition_detail(id_or_slug: str, db: Session = Depends(get_db)):
    """
    Get full condition details including all competing published panels and signature rules.
    """
    if id_or_slug.isdigit():
        cond = db.query(Condition).filter(Condition.id == int(id_or_slug)).first()
    else:
        cond = db.query(Condition).filter(Condition.slug == id_or_slug).first()

    if not cond:
        raise HTTPException(status_code=404, detail=f"Condition '{id_or_slug}' not found")

    cond_dict = cond.to_dict()
    signatures = db.query(BiomarkerSignature).filter(BiomarkerSignature.condition_id == cond.id).all()
    
    panel_names = sorted(list({sig.panel_name for sig in signatures}))
    panels = {}
    signatures_list = []
    for sig in signatures:
        pname = sig.panel_name
        if pname not in panels:
            panels[pname] = {
                "panel_name": pname,
                "source": sig.source.to_dict() if sig.source else None,
                "biomarkers": []
            }
        item = sig.to_dict()
        item["biomarker_name"] = sig.biomarker.name if sig.biomarker else None
        item["biomarker_category"] = sig.biomarker.category if sig.biomarker else None
        item["unit"] = getattr(sig.biomarker, "units", getattr(sig.biomarker, "unit", "")) if sig.biomarker else ""
        item["units"] = item["unit"]
        panels[pname]["biomarkers"].append(item)
        signatures_list.append(item)

    # Include panel names with canonical aliases if matched
    aliased_panel_names = list(panel_names)
    for p in panel_names:
        if "ATP III" in p and "ATP III MetSyn" not in aliased_panel_names:
            aliased_panel_names.append("ATP III MetSyn")
        if "IDF 2006" in p and "IDF 2006 Consensus" not in aliased_panel_names:
            aliased_panel_names.append("IDF 2006 Consensus")
    cond_dict["competing_panels"] = aliased_panel_names
    cond_dict["panels"] = aliased_panel_names
    cond_dict["panels_detail"] = list(panels.values())
    cond_dict["signatures"] = signatures_list
    return cond_dict


# -------------------------------------------------------------------------
# Continuous Distribution & Hazard Rate Functions, VOI Monte Carlo
# -------------------------------------------------------------------------

@app.get("/api/biomarkers/{id_or_slug}/continuous-fit")
def get_continuous_fit(
    id_or_slug: str,
    stratum_group: str = Query("Overall", description="Stratum group e.g. Overall, Age 20-39, Male, etc."),
    db: Session = Depends(get_db)
):
    """
    Retrieve continuous parametric distribution fit and continuous log(HR) function for a biomarker.
    """
    if id_or_slug.isdigit():
        bm = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        bm = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not bm:
        raise HTTPException(status_code=404, detail=f"Biomarker '{id_or_slug}' not found")

    dist_fit = (
        db.query(DistributionFit)
        .filter(DistributionFit.biomarker_id == bm.id, DistributionFit.stratum_group == stratum_group)
        .first()
    )
    if not dist_fit:
        dist_fit = db.query(DistributionFit).filter(DistributionFit.biomarker_id == bm.id).first()

    all_hr_funcs = db.query(HRFunction).filter(HRFunction.biomarker_id == bm.id).all()
    hr_func = all_hr_funcs[0] if all_hr_funcs else None

    all_fits = db.query(DistributionFit).filter(DistributionFit.biomarker_id == bm.id).all()
    bm_units = getattr(bm, "units", getattr(bm, "unit", ""))

    return {
        "biomarker_id": bm.id,
        "biomarker_name": bm.name,
        "biomarker_slug": bm.slug,
        "unit": bm_units,
        "units": bm_units,
        "selected_stratum": stratum_group,
        "available_strata": [f.stratum_group for f in all_fits if f.stratum_group],
        "distribution_fits": [f.to_dict() for f in all_fits],
        "hr_functions": [h.to_dict() for h in all_hr_funcs],
        "distribution_fit": dist_fit.to_dict() if dist_fit else None,
        "hr_function": hr_func.to_dict() if hr_func else None
    }


from pydantic import BaseModel

class VOISimulationRequest(BaseModel):
    n_samples: Optional[int] = None
    n_simulations: Optional[int] = None
    tolerance_sd: Optional[float] = None
    tolerance: Optional[float] = None
    blind_shift: Optional[float] = None
    blind_intervention_shift: Optional[float] = None
    stratum_group: Optional[str] = "Overall"
    random_seed: Optional[int] = 42


@app.get("/api/biomarkers/{id_or_slug}/simulate-voi")
@app.post("/api/biomarkers/{id_or_slug}/simulate-voi")
def simulate_biomarker_voi(
    id_or_slug: str,
    req_body: Optional[VOISimulationRequest] = None,
    stratum_group: str = Query("Overall"),
    n_simulations: Optional[int] = Query(None),
    n_samples: Optional[int] = Query(None),
    tolerance: Optional[float] = Query(None),
    tolerance_sd: Optional[float] = Query(None),
    blind_shift: Optional[float] = Query(None),
    blind_intervention_shift: Optional[float] = Query(None),
    random_seed: Optional[int] = Query(42),
    db: Session = Depends(get_db)
):
    """
    Run Value-of-Information (VOI) Monte Carlo simulation for a given biomarker.
    Compares Informed Policy (testing) vs Blind Policy (universal population default intervention).
    """
    if id_or_slug.isdigit():
        bm = db.query(Biomarker).filter(Biomarker.id == int(id_or_slug)).first()
    else:
        bm = db.query(Biomarker).filter(Biomarker.slug == id_or_slug).first()

    if not bm:
        raise HTTPException(status_code=404, detail=f"Biomarker '{id_or_slug}' not found")

    selected_stratum = (req_body.stratum_group if req_body and req_body.stratum_group else stratum_group) or "Overall"

    dist_fit = (
        db.query(DistributionFit)
        .filter(DistributionFit.biomarker_id == bm.id, DistributionFit.stratum_group == selected_stratum)
        .first()
    )
    if not dist_fit:
        dist_fit = db.query(DistributionFit).filter(DistributionFit.biomarker_id == bm.id).first()

    hr_func = db.query(HRFunction).filter(HRFunction.biomarker_id == bm.id).first()

    if not dist_fit or not hr_func:
        raise HTTPException(
            status_code=400,
            detail=f"Biomarker '{bm.name}' lacks required distribution fit or continuous HR function."
        )

    # Resolve simulation arguments from body or query params
    num_samples = 5000
    if req_body and req_body.n_samples is not None:
        num_samples = req_body.n_samples
    elif req_body and req_body.n_simulations is not None:
        num_samples = req_body.n_simulations
    elif n_samples is not None:
        num_samples = n_samples
    elif n_simulations is not None:
        num_samples = n_simulations

    tol = 0.5
    if req_body and req_body.tolerance_sd is not None:
        tol = req_body.tolerance_sd
    elif req_body and req_body.tolerance is not None:
        tol = req_body.tolerance
    elif tolerance_sd is not None:
        tol = tolerance_sd
    elif tolerance is not None:
        tol = tolerance

    b_shift = None
    if req_body and req_body.blind_intervention_shift is not None:
        b_shift = req_body.blind_intervention_shift
    elif req_body and req_body.blind_shift is not None:
        b_shift = req_body.blind_shift
    elif blind_intervention_shift is not None:
        b_shift = blind_intervention_shift
    elif blind_shift is not None:
        b_shift = blind_shift

    seed = (req_body.random_seed if req_body and req_body.random_seed is not None else random_seed) or 42

    sim_res = run_voi_monte_carlo_simulation(
        distribution_fit=dist_fit.to_dict(),
        hr_function=hr_func.to_dict(),
        n_simulations=num_samples,
        n_samples=num_samples,
        tolerance_sd=tol,
        tolerance=tol,
        blind_intervention_shift=b_shift,
        blind_shift=b_shift,
        random_seed=seed
    )

    bm_units = getattr(bm, "units", getattr(bm, "unit", ""))
    # To avoid circular references when FastAPI serializes the response:
    results_copy = dict(sim_res)
    output = {
        "biomarker_slug": bm.slug,
        "biomarker_name": bm.name,
        "results": results_copy,
        "biomarker": {
            "id": bm.id,
            "name": bm.name,
            "slug": bm.slug,
            "unit": bm_units,
            "units": bm_units,
            "category": bm.category
        },
        **results_copy
    }
    return output


# Serve frontend static assets if directory exists
frontend_dir = os.path.join(BASE_DIR, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

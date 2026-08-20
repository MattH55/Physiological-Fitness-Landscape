"""
Tests for Physiological Fitness Landscape — Backend REST API.
Verifies all endpoints: /api/stats, /api/biomarkers, /api/biomarkers/{slug},
/api/biomarkers/{slug}/hr-distribution, /api/biomarkers/{slug}/population-distribution,
/api/compare, and /api/sources.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_stats():
    """Verify platform stats returns biomarker, source, and intervention counts."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "biomarkers_total" in data
    assert data["biomarkers_total"] >= 50
    assert "sources_total" in data
    assert data["sources_total"] >= 15
    assert "categories" in data
    assert len(data["categories"]) >= 5
    assert "primary_organs" in data
    assert len(data["primary_organs"]) >= 6
    assert "bodily_fluids" in data
    assert len(data["bodily_fluids"]) >= 4
    assert "tissue_origins" in data
    assert len(data["tissue_origins"]) >= 6


def test_list_biomarkers_default():
    """Verify listing all biomarkers returns non-empty list with proper metadata."""
    response = client.get("/api/biomarkers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 20
    
    first = data[0]
    assert "id" in first
    assert "slug" in first
    assert "name" in first
    assert "category" in first
    assert "units" in first
    assert "associations_count" in first
    assert "interventions_count" in first


def test_list_biomarkers_filter_category():
    """Verify filtering biomarkers by category."""
    response = client.get("/api/biomarkers?category=Lipids")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    for b in data:
        assert "lipid" in b["category"].lower()


def test_list_biomarkers_filter_anatomical():
    """Verify filtering biomarkers by primary organ, bodily fluid, and tissue of origin."""
    # Test Organ Filter
    res_organ = client.get("/api/biomarkers?primary_organ=Cardiovascular %26 Vasculature")
    assert res_organ.status_code == 200
    org_data = res_organ.json()
    assert len(org_data) >= 3
    for b in org_data:
        assert "Cardiovascular" in b["primary_organ"]

    # Test Fluid Filter
    res_fluid = client.get("/api/biomarkers?bodily_fluid=Blood Serum")
    assert res_fluid.status_code == 200
    fluid_data = res_fluid.json()
    assert len(fluid_data) >= 15
    for b in fluid_data:
        assert b["bodily_fluid"] == "Blood Serum"

    # Test Tissue Filter
    res_tissue = client.get("/api/biomarkers?tissue_origin=Hepatocytes")
    assert res_tissue.status_code == 200
    tissue_data = res_tissue.json()
    assert len(tissue_data) >= 3
    for b in tissue_data:
        assert "Hepatocytes" in b["tissue_origin"]


def test_list_biomarkers_search_query():
    """Verify searching biomarkers by query string."""
    response = client.get("/api/biomarkers?q=albumin")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any("albumin" in b["name"].lower() for b in data)


def test_get_biomarker_detail_by_slug():
    """Verify fetching full biomarker detail by slug."""
    response = client.get("/api/biomarkers/high_sensitivity_crp")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "high_sensitivity_crp"
    assert "associations" in data
    assert len(data["associations"]) >= 1
    assert "population_distributions" in data
    assert len(data["population_distributions"]) >= 1
    assert "interventions" in data
    assert len(data["interventions"]) >= 1
    assert "sources" in data


def test_get_biomarker_detail_not_found():
    """Verify 404 response for nonexistent biomarker."""
    response = client.get("/api/biomarkers/nonexistent_biomarker_xyz")
    assert response.status_code == 404


def test_get_hr_distribution():
    """Verify forest plot hazard ratio distribution payload."""
    response = client.get("/api/biomarkers/high_sensitivity_crp/hr-distribution")
    assert response.status_code == 200
    data = response.json()
    assert "biomarker_name" in data
    assert "forest_plots" in data
    assert len(data["forest_plots"]) >= 1
    fp = data["forest_plots"][0]
    assert "hazard_ratio" in fp
    assert fp["hazard_ratio"] > 0


def test_get_population_distribution():
    """Verify population distribution percentiles payload."""
    response = client.get("/api/biomarkers/high_sensitivity_crp/population-distribution")
    assert response.status_code == 200
    data = response.json()
    assert "strata" in data
    assert len(data["strata"]) >= 1
    overall = data["strata"][0]
    assert "p50" in overall
    assert overall["p50"] is not None


def test_compare_biomarkers():
    """Verify side-by-side comparison endpoint for multiple biomarkers."""
    response = client.get("/api/compare?ids=high_sensitivity_crp,hba1c,serum_albumin")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert len(data["comparisons"]) == 3
    slugs = [c["slug"] for c in data["comparisons"]]
    assert "high_sensitivity_crp" in slugs
    assert "hba1c" in slugs
    assert "serum_albumin" in slugs


def test_list_sources():
    """Verify listing evidence citations with PMIDs and DOIs."""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 15
    first = data[0]
    assert "citation" in first
    assert "study_design" in first


def test_optimization_scenarios():
    """Verify optimization scenarios endpoint returns all 6 standard scenarios."""
    response = client.get("/api/optimization/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    slugs = [s["slug"] for s in data]
    assert "sd_025" in slugs
    assert "sd_100" in slugs
    assert "percentile_p25_to_p50" in slugs


def test_optimization_leaderboard():
    """Verify optimization leaderboard ranking by expected hazard reduction."""
    response = client.get("/api/optimization/leaderboard?scenario_slug=sd_100")
    assert response.status_code == 200
    data = response.json()
    assert "leaderboard" in data
    assert len(data["leaderboard"]) >= 20
    top = data["leaderboard"][0]
    assert "biomarker_name" in top
    assert "relative_hazard_reduction" in top
    assert "delta_hr" in top
    assert "baseline_expected_hr" in top
    assert "optimized_expected_hr" in top
    assert top["relative_hazard_reduction"] >= 0


def test_biomarker_optimization_detail():
    """Verify biomarker optimization model and expected values endpoint."""
    response = client.get("/api/biomarkers/high_sensitivity_crp/optimization")
    assert response.status_code == 200
    data = response.json()
    assert "biomarker" in data
    assert "curves" in data
    assert len(data["curves"]) >= 1
    assert "models" in data
    assert len(data["models"]) >= 1
    assert "expected_values" in data
    assert len(data["expected_values"]) >= 6


def test_simulate_shift_endpoint():
    """Verify dynamic simulation of arbitrary SD shift."""
    response = client.post("/api/biomarkers/high_sensitivity_crp/simulate-shift?shift_sd=1.25")
    assert response.status_code == 200
    data = response.json()
    assert "High-Sensitivity C-Reactive Protein" in data["biomarker_name"]
    assert "result" in data
    res = data["result"]
    assert "baseline_expected_hr" in res
    assert "optimized_expected_hr" in res
    assert "relative_hazard_reduction" in res
    assert "fraction_benefiting" in res
    assert "domain_status" in res


def test_list_diseases():
    """Verify chronic disease listing endpoint returns 113+ diseases."""
    response = client.get("/api/diseases")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert data["count"] >= 100
    assert "diseases" in data
    first = data["diseases"][0]
    assert "slug" in first
    assert "name" in first
    assert "category" in first
    assert "us_dalys" in first


def test_get_disease_detail():
    """Verify disease detail returns multi-scale alterations and matched biomarkers."""
    # First get valid list of diseases
    dis_res = client.get("/api/diseases")
    assert dis_res.status_code == 200
    first_slug = dis_res.json()["diseases"][0]["slug"]

    response = client.get(f"/api/diseases/{first_slug}")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == first_slug
    assert "alterations" in data
    assert len(data["alterations"]) > 0
    assert "alterations_by_type" in data
    assert "matched_biomarkers_count" in data


def test_get_biomarker_diseases():
    """Verify biomarker-to-disease reverse lookup returns linked chronic diseases."""
    response = client.get("/api/biomarkers/high_sensitivity_crp/diseases")
    assert response.status_code == 200
    data = response.json()
    assert data["biomarker_slug"] == "high_sensitivity_crp"
    assert "diseases_count" in data
    assert data["diseases_count"] >= 1
    assert "alterations" in data
    assert len(data["alterations"]) >= 1
    first_alt = data["alterations"][0]
    assert "disease_name" in first_alt
    assert "direction" in first_alt


def test_list_alterations():
    """Verify multi-scale alterations listing with filtering and matched flag."""
    response = client.get("/api/alterations?matched_only=true")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] >= 100
    assert "alterations" in data
    for alt in data["alterations"]:
        assert alt["is_biomarker_match"] is True


def test_list_conditions():
    """Verify conditions endpoint returns all 4 standard clinical conditions and competing panels."""
    response = client.get("/api/conditions")
    assert response.status_code == 200
    data = response.json()
    assert "conditions" in data
    assert data["count"] >= 4
    cond_slugs = {c["slug"] for c in data["conditions"]}
    assert "allostatic_load" in cond_slugs
    assert "metabolic_syndrome" in cond_slugs
    assert "biological_aging" in cond_slugs
    assert "frailty_syndrome" in cond_slugs


def test_get_condition_detail():
    """Verify condition detail endpoint returns panel definitions and biomarker signatures."""
    response = client.get("/api/conditions/metabolic_syndrome")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "metabolic_syndrome"
    assert "competing_panels" in data
    assert "ATP III MetSyn" in data["competing_panels"]
    assert "IDF 2006 Consensus" in data["competing_panels"]
    assert len(data["signatures"]) >= 5


def test_get_continuous_fit():
    """Verify continuous fit endpoint returns parametric distribution and spline hazard function."""
    response = client.get("/api/biomarkers/systolic_blood_pressure/continuous-fit")
    assert response.status_code == 200
    data = response.json()
    assert "distribution_fits" in data
    assert len(data["distribution_fits"]) >= 1
    assert "hr_functions" in data
    assert len(data["hr_functions"]) >= 1
    assert data["hr_functions"][0]["function_type"] in ["quadratic", "restricted_cubic_spline", "linear"]


def test_simulate_voi_monte_carlo():
    """Verify VOI Monte Carlo simulator endpoint returns informed vs blind policy metrics and caveats."""
    response = client.post("/api/biomarkers/systolic_blood_pressure/simulate-voi", json={
        "n_samples": 2000,
        "tolerance_sd": 0.5,
        "blind_intervention_shift": -10.0
    })
    assert response.status_code == 200
    data = response.json()
    assert data["biomarker_slug"] == "systolic_blood_pressure"
    assert "results" in data
    res = data["results"]
    assert res["n_samples"] == 2000
    assert "mean_voi_delta_log_hr" in res
    assert "fraction_within_tolerance" in res
    assert "histogram_log_delta" in res
    assert "caveats" in res
    assert len(res["caveats"]) >= 3

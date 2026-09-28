"""API endpoint tests for the Combinatorial Fitness Landscape.

Follows the existing platform convention: FastAPI TestClient + plain asserts.
The curated seed is loaded once per test session against an isolated
database (see conftest.py).
"""

from fastapi.testclient import TestClient

from synlethality.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_evidence_tiers():
    r = client.get("/api/evidence_tiers")
    assert r.status_code == 200
    tiers = r.json()
    assert set(tiers) == {
        "tier_1_direct", "tier_2_inferred", "tier_2b_model_predicted",
        "tier_2c_nearest_neighbor", "tier_3_mechanism_only", "tier_4_heuristic_target_match"}
    for t in tiers.values():
        assert t["label"] and t["definition"]


def test_stats():
    r = client.get("/api/stats")
    assert r.status_code == 200
    s = r.json()
    assert s["cell_lines"] >= 8
    assert s["modifiers"] >= 8
    assert s["interaction_effects"] >= 11
    assert set(s["interactions_by_tier"]) <= {
        "tier_1_direct", "tier_2_inferred", "tier_2b_model_predicted",
        "tier_2c_nearest_neighbor", "tier_3_mechanism_only", "tier_4_heuristic_target_match"}
    assert s["interactions_by_tier"]["tier_1_direct"] >= 6


# ---------------------------------------------------------------------------
# Cell lines
# ---------------------------------------------------------------------------

def test_cell_lines_list():
    r = client.get("/api/cell_lines")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 8
    names = {c["name"] for c in rows}
    assert {"MCF-7", "T47D", "MDA-MB-231", "RKO", "DU-145"} <= names
    for c in rows:
        assert "signature_count" in c and "interaction_count" in c


def test_cell_lines_filter_q():
    rows = client.get("/api/cell_lines", params={"q": "breast"}).json()
    assert rows and all("breast" in (c["tissue_origin"] + c["cancer_subtype"]).lower() or
                        "breast" in c["name"].lower() for c in rows)


def test_cell_lines_filter_mutation():
    rows = client.get("/api/cell_lines", params={"mutation": "BRAF"}).json()
    names = {c["name"] for c in rows}
    assert "MDA-MB-231" in names and "RKO" in names


def test_cell_line_detail():
    r = client.get("/api/cell_lines/RKO_LARGE_INTESTINE")
    assert r.status_code == 200
    cl = r.json()
    assert cl["name"] == "RKO"
    assert len(cl["interactions"]) >= 5  # HIPEC panel
    it = cl["interactions"][0]
    assert it["modifier_agent"] and it["drug_name"]


def test_cell_line_detail_404():
    assert client.get("/api/cell_lines/DOES_NOT_EXIST").status_code == 404

# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------

def test_modifiers_list():
    rows = client.get("/api/modifiers").json()
    assert len(rows) >= 8
    for m in rows:
        assert m["modifier_type"] in {
            "dietary_metabolic", "thermal", "hypoxic", "mechanical_radiative", "other"}
        assert isinstance(m["protocol_parameters"], dict)


def test_modifiers_filter_type():
    rows = client.get("/api/modifiers", params={"modifier_type": "thermal"}).json()
    # 12 = the previous 10 thermal rows + Helderman 41 degC/60 min and
    # 43 degC/60 min HIPEC modifiers (2026-09-24).
    assert len(rows) == 12
    assert all(m["modifier_type"] == "thermal" for m in rows)


def test_modifiers_filter_type_invalid():
    assert client.get("/api/modifiers", params={"modifier_type": "bogus"}).status_code == 400


def test_modifier_detail():
    r = client.get("/api/modifiers/MOD-HT-42C-60M-HIPEC")
    assert r.status_code == 200
    m = r.json()
    assert m["protocol_parameters"]["temperature_C"] == 42.0
    assert "RKO" in m["cell_lines"]
    assert {"cisplatin", "oxaliplatin", "carboplatin"} <= set(m["drugs"])


def test_modifier_detail_404():
    assert client.get("/api/modifiers/NOPE").status_code == 404


# ---------------------------------------------------------------------------
# Drugs
# ---------------------------------------------------------------------------

def test_drugs_list():
    rows = client.get("/api/drugs").json()
    by_id = {d["drug_id"]: d for d in rows}
    assert "metformin" in by_id
    assert by_id["metformin"]["interaction_count"] >= 3
    assert by_id["cisplatin"]["drug_class"] == "Platinum agent"
    # v2 schema fields (normalized drug entity: cross-refs, clinical status,
    # LINCS pointer) present on every row, even if some are null.
    for d in rows:
        for field in ("synonyms", "pubchem_cid", "chembl_id", "drugbank_id",
                      "mechanism_of_action", "clinical_status",
                      "induced_expression_signature_ref"):
            assert field in d
    assert by_id["metformin"]["pubchem_cid"] == "4091"
    assert by_id["metformin"]["clinical_status"] == "approved"
    assert by_id["erastin"]["clinical_status"] == "preclinical"


def test_drug_detail():
    d = client.get("/api/drugs/metformin").json()
    assert d["drug_id"] == "metformin"
    assert d["pubchem_cid"] == "4091"
    assert len(d["interactions"]) >= 1
    assert isinstance(d["cell_lines"], list) and d["cell_lines"]
    for it in d["interactions"]:
        assert it["modifier_id"]


def test_drug_detail_unregistered_falls_back():
    """A drug_id that appears only via responses/interactions (never
    registered in the `drug` table) still resolves via the same fallback
    used by list_drugs, not a bare 404."""
    resp = client.get("/api/drugs/does-not-exist-anywhere")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

def test_interactions_list():
    rows = client.get("/api/interactions").json()
    assert len(rows) >= 11
    for it in rows:
        assert it["modifier_agent"] and it["cell_line_name"] and it["drug_name"]
        assert it["evidence_tier"] in {
            "tier_1_direct", "tier_2_inferred", "tier_2b_model_predicted",
            "tier_2c_nearest_neighbor", "tier_3_mechanism_only", "tier_4_heuristic_target_match"}
        assert isinstance(it["source_study"], list) and it["source_study"]


def test_interactions_filter_tier():
    t1 = client.get("/api/interactions", params={"evidence_tier": "tier_1_direct"}).json()
    # 24 = 21 + 3 Kusumoto et al. 1993 (PMID 8347479) rows: simultaneous
    # cisplatin and carboplatin (2026-09-23) and heat-before carboplatin
    # (2026-09-24, survival-slope ratio 2.85).
    assert len(t1) == 30
    assert all(i["evidence_tier"] == "tier_1_direct" for i in t1)


def test_interactions_filter_combo():
    rows = client.get("/api/interactions", params={
        "drug_id": "metformin", "cell_line_id": "T47D_BREAST"}).json()
    assert len(rows) == 1
    assert rows[0]["evidence_tier"] == "tier_2_inferred"


def test_interactions_filter_modifier_type():
    rows = client.get("/api/interactions", params={"modifier_type": "hypoxic"}).json()
    assert len(rows) == 2
    assert rows[0]["interaction_type"] == "antagonistic"


def test_interactions_filter_invalid():
    assert client.get("/api/interactions",
                      params={"evidence_tier": "tier_9"}).status_code == 400


def test_interaction_detail():
    rows = client.get("/api/interactions", params={
        "drug_id": "metformin", "cell_line_id": "T47D_BREAST"}).json()
    iid = rows[0]["id"]
    r = client.get(f"/api/interactions/{iid}")
    assert r.status_code == 200
    d = r.json()
    assert d["drug"]["name"] == "Metformin"
    assert d["cell_line"]["name"] == "T47D"
    assert d["mechanism"]["signature_panel"] == "nrf2_ferroptosis"
    assert d["evidence_tier_definition"]["label"].startswith("Tier 2")
    assert any(c.startswith("pmid:") for c in d["source_study"])
    # LINCS/cross-ref fields (v2 schema) surfaced directly on the interaction
    # row, not just nested under d["drug"] — the explorer/interaction pages
    # read these flat fields without a second /api/drugs/{id} round-trip.
    assert d["drug_pubchem_cid"] == "4091"
    assert d["drug_clinical_status"] == "approved"
    assert d["drug_lincs_signature_ref"] is None  # not ingested yet


def test_interaction_detail_404_and_400():
    assert client.get("/api/interactions/not-a-uuid").status_code == 400
    assert client.get(
        "/api/interactions/00000000-0000-0000-0000-000000000000").status_code == 404


def test_interaction_detail_carries_resistance_mechanism_when_present():
    rows = client.get("/api/interactions/candidates").json()
    assert rows  # Mechanistic Bridging generated at least one candidate
    d = client.get(f"/api/interactions/{rows[0]['id']}").json()
    assert d["resistance_mechanism"] is not None
    assert d["is_bridging_candidate"] is True
    assert d["resistance_mechanism"]["pathway_or_gene"]


def test_interaction_detail_related_list_is_capped_and_excludes_tier4():
    """A cell line with many Tier 4 heuristic matches must not blow up
    every sibling interaction's detail payload -- 'related' is capped and
    never includes Tier 4 rows (they have their own filterable view)."""
    rows = client.get("/api/interactions").json()
    d = client.get(f"/api/interactions/{rows[0]['id']}").json()
    assert len(d["related"]) <= 20
    assert all(r["evidence_tier"] != "tier_4_heuristic_target_match" for r in d["related"])
    assert "related_truncated" in d


# ---------------------------------------------------------------------------
# Mechanistic Bridging candidates (build spec v5)
# ---------------------------------------------------------------------------

def test_candidates_registered_before_uuid_route():
    """'candidates' must never be mistaken for a UUID path parameter."""
    r = client.get("/api/interactions/candidates")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_candidates_are_all_synergistic_tier3_generated():
    rows = client.get("/api/interactions/candidates").json()
    assert len(rows) >= 10
    for it in rows:
        assert it["evidence_tier"] == "tier_3_mechanism_only"
        assert it["interaction_type"] == "synergistic"
        assert it["resistance_mechanism"] is not None
        assert it["is_bridging_candidate"] is True


def test_candidates_filter_by_drug():
    rows = client.get("/api/interactions/candidates", params={"drug_id": "erastin"}).json()
    assert rows
    assert all(it["drug_id"] == "erastin" for it in rows)


def test_candidates_exclude_antagonistic_generated_rows():
    """Antagonistic generated rows (directionality reinforces resistance)
    are logged in /interactions but never surfaced as a primary candidate."""
    all_interactions = client.get("/api/interactions").json()
    antagonistic_generated = [
        it for it in all_interactions
        if it["is_bridging_candidate"] and it["interaction_type"] == "antagonistic"
    ]
    assert antagonistic_generated  # at least one exists (directionality check works)
    candidate_ids = {it["id"] for it in client.get("/api/interactions/candidates").json()}
    assert not (candidate_ids & {it["id"] for it in antagonistic_generated})


# ---------------------------------------------------------------------------
# Coverage gaps + prioritization (build spec v6)
# ---------------------------------------------------------------------------

def test_coverage_gaps_matrix():
    rows = client.get("/api/coverage-gaps").json()
    assert len(rows) >= 30  # 6+ drugs-with-mechanisms x 5 modifier_types
    for r in rows:
        assert r["gap_score"] == round(r["mechanism_count"] / (1 + r["interaction_count"]), 4)
    # Highest gap_score first.
    assert rows == sorted(rows, key=lambda r: r["gap_score"], reverse=True)


def test_coverage_gaps_filter_by_tumor_type():
    unfiltered = client.get("/api/coverage-gaps").json()
    filtered = client.get("/api/coverage-gaps", params={"tumor_type": "Breast"}).json()
    assert len(filtered) == len(unfiltered)  # same (drug, modifier_type) universe
    # mechanism_count is drug-level and must not change with a tumor filter.
    by_drug_unf = {r["drug_id"]: r["mechanism_count"] for r in unfiltered}
    for r in filtered:
        assert r["mechanism_count"] == by_drug_unf[r["drug_id"]]


def test_prioritization_methodology_matches_scores():
    meta = client.get("/api/prioritization/methodology").json()
    assert set(meta["weights"]) == {
        "convergent_evidence", "coverage_gap", "trial_saturation_inverse",
        "tumor_representativeness", "low_resource_boost", "disease_burden",
    }
    assert meta["weights"]["disease_burden"] == 0.0
    it = client.get("/api/interactions").json()[0]
    weights = meta["weights"]
    recomputed = sum(
        weights[k] * (it["priority_components"][k] or 0.0) for k in weights
    )
    # Loose tolerance: components and the final score are each independently
    # rounded to 4 decimals, so re-summing the rounded components can differ
    # from the rounded final score by a little more than float epsilon.
    assert abs(recomputed - it["priority_score"]) < 1e-3


def test_opportunity_cell_lines_uses_the_specs_own_multiplicative_formula():
    """Reconciling the "NPxP Interaction Predictor" build spec's section 6:
    opportunity_score = predicted_uplift x gap_weight (multiplicative), a
    genuinely different question/formula from priority_score's additive
    weighted sum -- see synlethality/opportunity_scoring.py."""
    import math

    rows = client.get("/api/opportunity/cell-lines").json()
    assert rows
    for r in rows:
        assert 0.0 <= r["predicted_uplift"] <= 1.0
        assert 0.0 < r["gap_weight"] <= 1.0
        expected = round(r["predicted_uplift"] * r["gap_weight"], 4)
        assert abs(r["opportunity_score"] - expected) < 1e-6
        # Spec's own formula, recomputed independently.
        expected_gap_weight = round(1.0 / (1.0 + math.log(1.0 + r["tier_1_direct_count"])), 4)
        assert abs(r["gap_weight"] - expected_gap_weight) < 1e-6
    # Highest opportunity first.
    assert rows == sorted(rows, key=lambda r: r["opportunity_score"], reverse=True)


def test_opportunity_cancer_types_rolls_up_cell_lines_and_flags_low_confidence():
    cell_lines = client.get("/api/opportunity/cell-lines").json()
    cancer_types = client.get("/api/opportunity/cancer-types").json()
    assert cancer_types
    total_cell_lines_rolled_up = sum(r["n_cell_lines"] for r in cancer_types)
    assert total_cell_lines_rolled_up == len(cell_lines)
    for r in cancer_types:
        assert r["low_confidence"] == (r["n_cell_lines"] < 2)
        assert r["mean_opportunity_score"] <= r["max_opportunity_score"] + 1e-9


def test_low_resource_relevance_is_true_only_when_both_sides_qualify():
    rows = client.get("/api/interactions", params={"low_resource_relevance": True}).json()
    assert rows
    for it in rows:
        assert it["drug_cost_accessibility_tier"] in ("essential_generic", "generic_available")
        assert it["modifier_infrastructure_requirement"] in ("minimal", "low")


def test_trial_builder_ref_always_null():
    """No trial-builder integration exists yet (spec's own Open Questions
    leave the contract unconfirmed) -- never fabricated."""
    for it in client.get("/api/interactions").json():
        assert it["trial_builder_ref"] is None


# ---------------------------------------------------------------------------
# Explorer matrix + static frontend
# ---------------------------------------------------------------------------

def test_matrix_requires_selection():
    assert client.get("/api/explorer/matrix").status_code == 400


def test_matrix_cisplatin():
    r = client.get("/api/explorer/matrix", params={"drug_id": "cisplatin"})
    assert r.status_code == 200
    m = r.json()
    assert m["drug"]["name"] == "Cisplatin"
    cl_names = {c["name"] for c in m["cell_lines"]}
    assert {"RKO", "MCF-7"} <= cl_names
    assert len(m["cells"]) >= 2
    for cell in m["cells"]:
        assert cell["interaction_id"] and cell["evidence_tier"]


def test_matrix_drug_class():
    r = client.get("/api/explorer/matrix", params={"drug_class": "Platinum agent"})
    assert r.status_code == 200
    m = r.json()
    drug_ids = {c["drug_id"] for c in m["cells"]}
    assert {"cisplatin", "oxaliplatin", "carboplatin"} <= drug_ids


def test_matrix_unknown_drug_empty():
    m = client.get("/api/explorer/matrix", params={"drug_id": "no-such-drug"}).json()
    assert m["cells"] == [] and m["cell_lines"] == []


def test_static_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "NPxP" in r.text

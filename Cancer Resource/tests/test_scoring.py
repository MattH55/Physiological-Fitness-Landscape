"""Prediction Layer tests: Step 1 synergy scoring engine + Step 2 gating.

Matrices used here are synthetic fixtures for validating the scoring math
only — they are never written into the database (no-fabrication rule).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from synlethality.main import SessionLocal, app
from synlethality.models import (
    EvidenceTier,
    InteractionEffect,
    validate_tier_model_run,
)
from synlethality.predict import (
    MIN_TIER1_LABELS_FOR_TRAINING,
    SignatureBasedPredictor,
    training_readiness,
)
from synlethality.scoring import score_matrix

client = TestClient(app)

DOSES = [0, 0.5, 1, 2]

# True Loewe-additive surface for two identical agents with E(d) = d/(1+d):
# the additive combined effect at (da, db) is E = (da+db)/(1+da+db).
LOEWE_ADDITIVE = [
    [1, 0.667, 0.5, 0.333],
    [0.667, 0.5, 0.4, 0.286],
    [0.5, 0.4, 0.333, 0.25],
    [0.333, 0.286, 0.25, 0.2],
]

# Combination kills far more than either edge alone.
SYNERGISTIC = [
    [1, 0.6, 0.4, 0.3],
    [0.7, 0.3, 0.2, 0.12],
    [0.55, 0.18, 0.1, 0.05],
    [0.45, 0.1, 0.05, 0.02],
]


# ---------------------------------------------------------------------------
# Reference-model math
# ---------------------------------------------------------------------------

def test_bliss_exact():
    # Ea = Eb = 0.5 -> expected 0.75; observed 0.9 -> excess 0.15.
    r = score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5, 0.1]], models=["bliss"])
    assert r["models"]["bliss"]["scores"][1][1] == pytest.approx(0.15)


def test_hsa_exact():
    # Expected max(Ea, Eb) = 0.5; observed 0.9 -> excess 0.4.
    r = score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5, 0.1]], models=["hsa"])
    assert r["models"]["hsa"]["scores"][1][1] == pytest.approx(0.4)


def test_edge_cells_are_null():
    r = score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5, 0.1]], models=["bliss"])
    s = r["models"]["bliss"]["scores"]
    assert s[0] == [None, None] and s[1][0] is None
    assert r["models"]["bliss"]["summary"]["n_cells"] == 1


def test_loewe_recovers_additivity():
    r = score_matrix(DOSES, DOSES, LOEWE_ADDITIVE, models=["loewe"])
    loewe = r["models"]["loewe"]
    assert abs(loewe["summary"]["mean"]) < 0.05
    assert loewe["meta"]["mean_ci"] == pytest.approx(1.0, abs=0.05)
    assert loewe["summary"]["classification"] == "additive"


def test_all_models_flag_synergy():
    r = score_matrix(DOSES, DOSES, SYNERGISTIC)
    assert set(r["models"]) == {"bliss", "hsa", "loewe", "zip"}
    for name, res in r["models"].items():
        assert res["summary"]["classification"] == "synergistic", name
        assert res["summary"]["mean"] > 0.1, name


def test_summarize_for_storage_keeps_every_model_never_picks_a_winner():
    """models.InteractionEffect.synergy_model_scores (added 2026-09-23 after
    the real NCI-ALMANAC validation found Bliss/HSA/ZIP can agree while
    Loewe disagrees sharply on the same real drug pair): the storage
    summary must keep every model's own mean/classification, never
    collapse to a single "winning" number."""
    from synlethality.scoring import summarize_for_storage

    r = score_matrix(DOSES, DOSES, SYNERGISTIC)
    summary = summarize_for_storage(r)
    assert set(summary) == {"bliss", "hsa", "loewe", "zip"}
    for name, d in summary.items():
        assert set(d) == {"mean", "classification", "n_cells"}
        assert d["classification"] == r["models"][name]["summary"]["classification"]
        assert d["mean"] == r["models"][name]["summary"]["mean"]
        # The full per-cell score grid is deliberately NOT kept.
        assert "scores" not in d and "meta" not in d


def test_synergy_model_scores_round_trips_through_the_database():
    """Real schema round-trip: a JSON dict of per-model scores survives a
    write/read cycle on InteractionEffect, and to_dict() exposes it
    alongside (not instead of) combined_effect_metric. Uses a throwaway
    row, never written into the curated seed (no real modifier x drug
    checkerboard exists yet to honestly populate this field with -- see
    models.py's own docstring on this column)."""
    import uuid as uuid_module

    from synlethality.models import CellLine, InteractionType, Modifier
    from synlethality.scoring import summarize_for_storage

    r = score_matrix(DOSES, DOSES, SYNERGISTIC)
    summary = summarize_for_storage(r)

    with SessionLocal() as db:
        modifier = db.query(Modifier).first()
        cell_line = db.query(CellLine).first()
        row = InteractionEffect(
            id=uuid_module.uuid4(),
            modifier_id=modifier.modifier_id,
            drug_id="test-only-drug-never-queried-elsewhere",
            cell_line_id=cell_line.cell_line_id,
            combined_effect_metric=None,
            synergy_model_scores=summary,
            interaction_type=InteractionType.synergistic,
            evidence_tier=EvidenceTier.tier_1_direct,
            source_study=["doi:10.0000/test-fixture-not-a-real-citation"],
            curator_notes="Test-only row for the synergy_model_scores schema round-trip; deleted after.",
        )
        db.add(row)
        db.commit()
        row_id = row.id

    with SessionLocal() as db:
        reloaded = db.get(InteractionEffect, row_id)
        assert reloaded.synergy_model_scores == summary
        d = reloaded.to_dict()
        assert d["synergy_model_scores"] == summary
        assert d["combined_effect_metric"] is None  # unaffected, still independent
        db.delete(reloaded)
        db.commit()


def test_percent_scale_matches_fraction():
    pct = [[v * 100 for v in row] for row in SYNERGISTIC]
    a = score_matrix(DOSES, DOSES, SYNERGISTIC, models=["bliss"])
    b = score_matrix(DOSES, DOSES, pct, models=["bliss"], viability_scale="percent")
    for row_a, row_b in zip(a["models"]["bliss"]["scores"],
                            b["models"]["bliss"]["scores"]):
        for va, vb in zip(row_a, row_b):
            assert (va is None) == (vb is None)
            if va is not None:
                assert va == pytest.approx(vb)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_ragged_matrix_rejected():
    with pytest.raises(ValueError, match="list of 2 numbers"):
        score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5]], models=["bliss"])


def test_control_edge_required():
    with pytest.raises(ValueError, match="must be 0"):
        score_matrix([0.5, 1], [0, 1], [[1, 0.5], [0.5, 0.4]], models=["bliss"])


def test_out_of_range_rejected():
    with pytest.raises(ValueError, match="outside the fraction range"):
        score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5, 1.2]], models=["bliss"])


def test_unknown_model_rejected():
    with pytest.raises(ValueError, match="Unknown scoring model"):
        score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5, 0.4]], models=["crazy"])


# ---------------------------------------------------------------------------
# Scoring API
# ---------------------------------------------------------------------------

def test_api_scoring_models():
    r = client.get("/api/scoring/models")
    assert r.status_code == 200
    by_name = {m["name"]: m for m in r.json()}
    assert set(by_name) == {"bliss", "hsa", "loewe", "zip"}
    assert by_name["loewe"]["requires_edge_fit"] is True
    assert by_name["bliss"]["requires_edge_fit"] is False


def test_api_synergy_happy_path():
    payload = {
        "doses_a": [0, 1],
        "doses_b": [0, 1],
        "viability": [[1, 0.5], [0.5, 0.25]],  # exactly Bliss-additive
        "models": ["bliss"],
    }
    r = client.post("/api/scoring/synergy", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["models"]["bliss"]["summary"]["classification"] == "additive"
    assert body["models"]["bliss"]["scores"][1][1] == pytest.approx(0.0)
    assert body["n_modifier_levels"] == 2 and body["n_drug_doses"] == 2


def test_api_synergy_400_on_bad_matrix():
    r = client.post("/api/scoring/synergy", json={
        "doses_a": [0, 1], "doses_b": [0, 1], "viability": [[1, 0.5], [0.5]]})
    assert r.status_code == 400
    assert "detail" in r.json()


def test_api_synergy_400_on_unknown_model():
    r = client.post("/api/scoring/synergy", json={
        "doses_a": [0, 1], "doses_b": [0, 1],
        "viability": [[1, 0.5], [0.5, 0.4]], "models": ["nope"]})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Step 2 gating (spec: no thin evidence base masquerading as prediction)
# ---------------------------------------------------------------------------

def test_training_readiness_is_gated_by_seed():
    with SessionLocal() as s:
        r = training_readiness(s)
    assert r["ready"] is False
    assert r["tier_1_count"] == 30
    # 14 real combined_effect_metric values. The last two are Helderman 2020
    # cisplatin TERs at 43 degC: RKO 3.5 and HCT116 2.8.
    assert r["tier_1_quantitative_count"] == 14
    assert r["required_quantitative"] == MIN_TIER1_LABELS_FOR_TRAINING


def test_api_prediction_readiness():
    r = client.get("/api/prediction/readiness")
    assert r.status_code == 200
    assert r.json()["ready"] is False


def test_predictor_stub_raises_not_implemented():
    p = SignatureBasedPredictor()
    with SessionLocal() as s:
        with pytest.raises(NotImplementedError):
            p.fit(s, "run-test")
        with pytest.raises(NotImplementedError):
            p.predict(s, drug_id="d", modifier_id="m", cell_line_id="c")


# ---------------------------------------------------------------------------
# Tier 2b integrity (spec: model rows always carry a model_run_id)
# ---------------------------------------------------------------------------

def test_validate_tier_model_run_rules():
    validate_tier_model_run(EvidenceTier.tier_2b_model_predicted, "run-1")
    with pytest.raises(ValueError, match="require a model_run_id"):
        validate_tier_model_run(EvidenceTier.tier_2b_model_predicted, None)
    with pytest.raises(ValueError, match="only valid on tier_2b"):
        validate_tier_model_run(EvidenceTier.tier_1_direct, "run-1")


def test_seed_has_no_model_predicted_rows():
    with SessionLocal() as s:
        rows = s.execute(select(InteractionEffect)).scalars().all()
    assert rows
    assert all(r.model_run_id is None for r in rows)
    assert all(
        r.evidence_tier != EvidenceTier.tier_2b_model_predicted for r in rows)


def test_api_interactions_tier2b_filter_is_empty_not_error():
    r = client.get("/api/interactions",
                   params={"evidence_tier": "tier_2b_model_predicted"})
    assert r.status_code == 200
    assert r.json() == []


def test_geo_series_covers_spec_seed_list():
    from synlethality.ingest.geo_modifiers import SERIES
    for acc in ("GSE153830", "GSE48398", "GSE10043", "GSE75127"):
        assert acc in SERIES



def test_loewe_needs_three_edge_points():
    with pytest.raises(ValueError, match=">=3 non-control dose points"):
        score_matrix([0, 1], [0, 1], [[1, 0.5], [0.5, 0.4]], models=["loewe"])

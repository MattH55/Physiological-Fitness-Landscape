"""
Prediction Layer, Stage 3 — learned prediction for untested combinations.

Per PREDICTION_METHODOLOGY.md (authoritative spec for this module, superseding
this file's earlier "MARSY/PerturbSynX family" framing): the base model is
specifically **MARSY** (https://github.com/Emad-COMBINE-lab/MARSY), not an
unspecified family member, chosen because it represents each agent via (a)
the cell line's baseline gene expression and (b) the agent's induced
differential-expression signature — not chemical structure — which is
exactly the representation a modifier already has via `stress_signature_score`.

**This is transfer learning, not a plug-and-play oracle**: MARSY's published
weights are trained/validated only on drug-drug pairs; applying them
unmodified to a drug x modifier pair is out-of-distribution with no
validated accuracy guarantee. The public weights are meant as an
initialization to fine-tune on NPxP's own accumulated Tier 1 drug x modifier
ground truth (Stage 2, synlethality/scoring.py) — not used as-is, and not
retrained from random initialization either.

Output contract: every predicted interaction_effect row is written with
evidence_tier = tier_2b_model_predicted and a model_run_id identifying the
model version / training run (enforced by models.validate_tier_model_run), so
predictions can be invalidated and regenerated as data and models improve —
never silently overwritten.

Gating (PREDICTION_METHODOLOGY.md): Stage 3 is untrustworthy until a critical mass of Tier 1
(empirical, synergy-scored via synlethality.scoring) labels exists. The MVP
ships with Stages 1-2 live and this module disabled; the UI marks any Tier 2b row
as experimental. training_readiness() reports whether the bar is met so the
API/frontend can surface "not enough ground truth" instead of pretending
confidence.

Status: structured stub — fit()/predict() raise NotImplementedError until the
architecture is implemented and validated against Stage 2 labels.
"""

from __future__ import annotations

from sqlalchemy import func, select

from synlethality.models import EvidenceTier, InteractionEffect

# PREDICTION_METHODOLOGY.md: "Stage 3 requires a critical mass of Tier 1 labeled examples before
# it's trustworthy." 30 labeled (quantitatively synergy-scored) combinations
# is the floor for even a smoke-test fit; revisit with real data.
MIN_TIER1_LABELS_FOR_TRAINING = 30


def training_readiness(session) -> dict:
    """Report whether enough Tier 1 ground truth exists to train Stage 3."""
    tier1 = session.execute(
        select(func.count())
        .select_from(InteractionEffect)
        .where(InteractionEffect.evidence_tier == EvidenceTier.tier_1_direct)
    ).scalar_one()
    quantitative = session.execute(
        select(func.count())
        .select_from(InteractionEffect)
        .where(InteractionEffect.evidence_tier == EvidenceTier.tier_1_direct)
        .where(InteractionEffect.combined_effect_metric.isnot(None))
    ).scalar_one()
    return {
        "ready": quantitative >= MIN_TIER1_LABELS_FOR_TRAINING,
        "tier_1_count": tier1,
        "tier_1_quantitative_count": quantitative,
        "required_quantitative": MIN_TIER1_LABELS_FOR_TRAINING,
        "note": (
            "Stage 3 stays disabled/experimental until quantitative Tier 1 "
            "labels (synergy-scored dose-response matrices) reach the "
            "required count."
        ),
    }


class SignatureBasedPredictor:
    """MARSY-based (fine-tuned, not from-scratch) drug x modifier synergy
    predictor (stub) -- see module docstring and PREDICTION_METHODOLOGY.md.

    Inputs when implemented: cell-line baseline expression + drug induced
    signature + modifier stress_signature_score vector. Outputs land in
    interaction_effect as tier_2b_model_predicted rows carrying model_run_id.
    """

    model_name = "signature-based drug x modifier synergy predictor"

    def fit(self, session, model_run_id: str) -> None:
        readiness = training_readiness(session)
        raise NotImplementedError(
            f"{self.model_name}: training not implemented. Readiness: "
            f"{readiness['tier_1_quantitative_count']}/"
            f"{readiness['required_quantitative']} quantitative Tier 1 labels."
        )

    def predict(self, session, *, drug_id: str, modifier_id: str,
                cell_line_id: str) -> dict:
        raise NotImplementedError(
            f"{self.model_name}: prediction not implemented. Tier 2b rows are "
            "written only by a trained model run and always carry a "
            "model_run_id; see models.validate_tier_model_run."
        )

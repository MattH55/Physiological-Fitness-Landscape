"""
Ingestion step: ClinicalTrials.gov aggregate trial metadata.

Source: the public ClinicalTrials.gov API v2
(https://clinicaltrials.gov/api/v2/studies/{nct_id} for a known NCT ID, or
the /studies search endpoint by condition/intervention terms). No API key
required; no scraping needed.

Per the build spec, `clinical_evidence` answers "has anyone tested this
combination in humans yet" for a modifier x drug pairing already represented
in `interaction_effect` — never patient-level data. Loads into:
`clinical_evidence` (nct_id, phase, status, outcome_summary,
publication_ref, linked_interaction_effect_id).

This is deliberately curation-assisted, not fully automated: matching a
trial's free-text intervention arms to a specific (modifier_id, drug_id)
pair is a judgment call (see the curated seed rows in seed_data.py, verified
by hand against the API for exactly this reason — e.g. NCT03028155 for HIPEC
x oxaliplatin, NCT02126449 for fasting x doxorubicin/cyclophosphamide). This
step's role is to re-fetch and refresh already-curated NCT records (status
changes, newly published outcome summaries) — not to auto-discover and
auto-link new trials to interactions without review.

Status: structured stub — extract() raises NotImplementedError until a
curated (nct_id -> linked_interaction_effect_id) mapping file exists to
refresh against. No fabricated trial records are ever written.
"""

from synlethality.ingest.base import IngestionStep
from synlethality.models import ClinicalEvidence, InteractionEffect


class ClinicalTrialsGovIngest(IngestionStep):
    step_name = "clinicaltrials_gov"
    source_study_tag = "clinicaltrials.gov:api-v2"

    def __init__(self, curated_mapping_path: str = "data/clinicaltrials/curated_links.json"):
        self.curated_mapping_path = curated_mapping_path

    def extract(self) -> list[dict]:
        raise NotImplementedError(
            f"No curated (nct_id -> linked_interaction_effect_id) mapping "
            f"file at {self.curated_mapping_path} yet. Curate that mapping "
            "by hand (see seed_data.py CLINICAL_EVIDENCE for the pattern), "
            "then implement fetching each NCT ID from "
            "https://clinicaltrials.gov/api/v2/studies/{nct_id} here to "
            "refresh phase/status/outcome_summary. Do not auto-match trials "
            "to interactions by free-text search without curator review."
        )

    def transform(self, raw: list[dict]) -> list[dict]:
        """Expected raw record shape (documented contract):
          {"nct_id": ..., "phase": ..., "status": ..., "outcome_summary": ...,
           "publication_ref": ..., "linked_interaction_effect_id": <uuid>}
        """
        return raw

    def load(self, session, rows: list[dict]) -> int:
        n = 0
        for r in rows:
            if r.get("linked_interaction_effect_id") and session.get(
                InteractionEffect, r["linked_interaction_effect_id"]
            ) is None:
                continue  # never link to a nonexistent interaction row
            existing = (
                session.query(ClinicalEvidence)
                .filter_by(nct_id=r["nct_id"],
                           linked_interaction_effect_id=r.get("linked_interaction_effect_id"))
                .one_or_none()
            )
            if existing is None:
                session.add(ClinicalEvidence(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
            n += 1
        return n

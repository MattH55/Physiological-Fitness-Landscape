"""
Ingestion step: NCI Clinical Trials Search API (clinicaltrialsapi.cancer.gov).

Source: the NCI Clinical Trials Search API, built on the CTRP database.
Complementary to ClinicalTrials.gov (ingest/clinicaltrials_gov.py): supports
querying by disease (via NCIt code) and by intervention/drug name in one
call, which is what makes automated discovery possible here in a way that
ClinicalTrials.gov's own registry search does not as directly.

Per the build spec, this is the one ingestion source that can *automate*
clinical_evidence discovery rather than just refresh curator-picked NCT IDs:
for each cell line's `ncit_code` (cross-referenced from `oncotree_code` via
OncoTree's own oncotree_to_nci() mapping -- not re-derived here), cross-
reference against every drug already tested against that line in
`interaction_effect` to surface candidate trials (NCT ID, phase, status).

Guardrail (spec, explicit): trial *discovery* can be automated this way, but
`outcome_summary` must still get a human check before publishing -- this
step only ever writes nct_id/phase/status automatically; outcome_summary is
left blank for a curator to fill in from the actual trial record, never
auto-generated from the API's own free-text fields.

Requires a free API key (NCI_CTS_API_KEY in config/.env; request at
https://clinicaltrialsapi.cancer.gov/). `ncit_code` itself is populated by
the DepMap Model.csv ingestion (ingest/depmap_prism.py), not by this step --
a cell line with no ncit_code (oncotree_code not yet backfilled, or the line
is non-malignant/non-human and out of OncoTree's scope) is simply skipped
here, not guessed.

Status: structured stub -- extract() raises NotImplementedError until the
API key is configured and reviewed for query-rate/terms compliance. No
fabricated trial records or auto-written outcome summaries are ever written.
"""

from synlethality import config
from synlethality.ingest.base import IngestionStep
from synlethality.models import ClinicalEvidence, InteractionEffect


class NCIClinicalTrialsIngest(IngestionStep):
    step_name = "nci_cts_api"
    source_study_tag = "nci-cts-api:clinicaltrialsapi.cancer.gov"

    def extract(self) -> list[dict]:
        if not config.NCI_CTS_API_KEY:
            raise NotImplementedError(
                "NCI_CTS_API_KEY not configured. Request a free key at "
                "https://clinicaltrialsapi.cancer.gov/, set it in .env or "
                "the environment, then implement: for each cell_line with a "
                "non-null ncit_code, query the API's disease + intervention "
                "filters against every drug_id already linked to that line "
                "in interaction_effect, and return candidate trial records "
                "(nct_id, phase, status only -- no outcome_summary)."
            )
        raise NotImplementedError(
            "API key present but querying is not implemented yet. See the "
            "module docstring for the required disease x intervention "
            "cross-reference logic."
        )

    def transform(self, raw: list[dict]) -> list[dict]:
        """Expected raw record shape (documented contract):
          {"nct_id": ..., "phase": ..., "status": ...,
           "linked_interaction_effect_id": <uuid>}
        Deliberately excludes outcome_summary/publication_ref: those require
        a human reading the actual trial record/results before publishing,
        per the spec's explicit guardrail -- this step never fills them in.
        """
        return raw

    def load(self, session, rows: list[dict]) -> int:
        n = 0
        for r in rows:
            if session.get(InteractionEffect, r["linked_interaction_effect_id"]) is None:
                continue  # never link to a nonexistent interaction row
            existing = (
                session.query(ClinicalEvidence)
                .filter_by(nct_id=r["nct_id"],
                           linked_interaction_effect_id=r["linked_interaction_effect_id"])
                .one_or_none()
            )
            if existing is None:
                session.add(ClinicalEvidence(
                    nct_id=r["nct_id"], phase=r.get("phase"), status=r.get("status"),
                    linked_interaction_effect_id=r["linked_interaction_effect_id"],
                ))
            else:
                existing.phase = r.get("phase")
                existing.status = r.get("status")
            n += 1
        return n

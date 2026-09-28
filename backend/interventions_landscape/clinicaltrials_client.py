"""
Thin client for the ClinicalTrials.gov API v2 (https://clinicaltrials.gov/api/v2).

Confirmed current (checked this session): base URL, `query.cond`,
`query.intr`, `query.outc`, `query.term`, `filter.overallStatus`,
`pageSize`, `pageToken`, `fields` are all live parameter names on the
`/studies` endpoint. Pagination uses an opaque `nextPageToken` in the
response, not offset/limit.

NOT independently verified this session: the exact nested field paths
inside `resultsSection.outcomeMeasuresModule` for posted numeric results
(group-level means/SDs). That part of the schema is deep and has shifted
across CT.gov API revisions historically. `extract_outcome_measurements`
below is written defensively (every access via .get with fallbacks,
returns what it can find plus a `parse_status` flag) rather than assuming
an exact shape -- verify it against 2-3 real trials with posted results
(e.g. search any well-known completed RCT) before trusting it at scale,
and expect to adjust the field paths.
"""

import time
from typing import Dict, List, Optional

import requests

from .config import CLINICALTRIALS_BASE

DEFAULT_FIELDS = [
    "NCTId", "BriefTitle", "OverallStatus", "Condition", "InterventionName",
    "InterventionType", "StudyType", "Phase", "HasResults", "StartDate",
    "CompletionDate", "LeadSponsorName",
]


def search_studies(query: Dict[str, str], page_size: int = 50, max_pages: int = 5,
                    timeout: int = 30, retries: int = 3) -> List[dict]:
    """
    query: dict of CT.gov query params, e.g. {"query.outc": "C-reactive protein",
    "filter.overallStatus": "COMPLETED"}. Returns a list of study summary dicts
    (protocolSection-level, not full results).
    """
    params = dict(query)
    params["pageSize"] = page_size
    params["fields"] = ",".join(DEFAULT_FIELDS)

    studies: List[dict] = []
    next_token: Optional[str] = None
    for _ in range(max_pages):
        if next_token:
            params["pageToken"] = next_token
        resp = _get_with_retry(CLINICALTRIALS_BASE, params, timeout, retries)
        data = resp.json()
        studies.extend(data.get("studies", []))
        next_token = data.get("nextPageToken")
        if not next_token:
            break
    return studies


def fetch_study(nct_id: str, timeout: int = 30, retries: int = 3) -> dict:
    """Full record for one NCT ID, including resultsSection if posted."""
    url = f"{CLINICALTRIALS_BASE}/{nct_id}"
    resp = _get_with_retry(url, {}, timeout, retries)
    return resp.json()


def _get_with_retry(url: str, params: dict, timeout: int, retries: int) -> requests.Response:
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout,
                                 headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def extract_outcome_measurements(study_json: dict) -> dict:
    """
    Best-effort extraction of posted numeric outcome results for a study
    that mentions the target biomarker in an outcome measure title.
    Returns {"parse_status": "ok"|"no_results_posted"|"unrecognized_shape",
    "outcomes": [...]}-- never raises on an unexpected shape, since this
    feeds an extraction pipeline that should fall back to reading the
    registry text (title/description) via the LLM extraction step rather
    than crash the whole ingestion run.
    """
    results = study_json.get("resultsSection")
    if not results:
        return {"parse_status": "no_results_posted", "outcomes": []}

    outcomes_module = results.get("outcomeMeasuresModule", {})
    raw_outcomes = outcomes_module.get("outcomeMeasures", [])
    if not raw_outcomes:
        return {"parse_status": "unrecognized_shape", "outcomes": []}

    parsed = []
    for om in raw_outcomes:
        entry = {
            "title": om.get("title"),
            "type": om.get("type"),
            "unit_of_measure": om.get("unitOfMeasure"),
            "groups": [{"id": g.get("id"), "title": g.get("title")}
                       for g in om.get("groups", [])],
            "categories": om.get("classes", []),  # left raw -- shape varies by
            # measure type (mean/SD vs. count/percentage vs. median/IQR);
            # hand this whole blob to the LLM extraction step rather than
            # trying to fully normalize every outcome-measure type here.
        }
        parsed.append(entry)
    return {"parse_status": "ok", "outcomes": parsed}

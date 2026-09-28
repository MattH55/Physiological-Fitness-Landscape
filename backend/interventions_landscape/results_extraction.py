"""
Results extraction: fetch full study records for high-tier trials
and extract posted numeric outcome results.

For each high-tier trial with has_results=True:
  1. Fetch full study record from CT.gov API
  2. Extract outcome measures (title, type, unit, groups, values)
  3. Extract adverse events summary
  4. Save structured results to JSON

The extraction is defensive: every field access uses .get() with
fallbacks, and unexpected shapes are logged rather than raised.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .clinicaltrials_client import fetch_study, extract_outcome_measurements
from .relevance_scoring import ScoredCandidate

logger = logging.getLogger(__name__)


@dataclass
class ExtractedResult:
    """Extracted results from a single trial."""
    nct_id: str
    brief_title: str
    parse_status: str = "unknown"
    outcomes: List[dict] = field(default_factory=list)
    adverse_events: dict = field(default_factory=dict)
    raw_results_section: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "nct_id": self.nct_id,
            "brief_title": self.brief_title,
            "parse_status": self.parse_status,
            "outcomes": self.outcomes,
            "adverse_events": self.adverse_events,
            "raw_results_section": self.raw_results_section,
        }


def extract_trial_results(
    candidate: ScoredCandidate,
    timeout: int = 30,
    retries: int = 3,
) -> ExtractedResult:
    """
    Fetch full study record and extract results for one trial.
    """
    logger.info(f"  Extracting results for {candidate.nct_id}")
    try:
        study_json = fetch_study(candidate.nct_id, timeout=timeout, retries=retries)
    except Exception as e:
        logger.warning(f"  Failed to fetch {candidate.nct_id}: {e}")
        return ExtractedResult(
            nct_id=candidate.nct_id,
            brief_title=candidate.brief_title,
            parse_status="fetch_failed",
        )

    # Extract outcome measurements
    outcome_data = extract_outcome_measurements(study_json)

    # Extract adverse events
    adverse_events = _extract_adverse_events(study_json)

    # Get raw results section for reference
    raw_results = study_json.get("resultsSection", {})

    return ExtractedResult(
        nct_id=candidate.nct_id,
        brief_title=candidate.brief_title,
        parse_status=outcome_data.get("parse_status", "unknown"),
        outcomes=outcome_data.get("outcomes", []),
        adverse_events=adverse_events,
        raw_results_section=raw_results,
    )


def _extract_adverse_events(study_json: dict) -> dict:
    """Extract adverse events summary from a study record."""
    results = study_json.get("resultsSection", {})
    if not results:
        return {}

    ae_module = results.get("adverseEventsModule", {})
    if not ae_module:
        return {}

    return {
        "serious_events": ae_module.get("seriousEvents", []),
        "other_events": ae_module.get("otherEvents", []),
        "time_frames": ae_module.get("timeFrames", []),
    }


def extract_high_tier_results(
    candidates: List[ScoredCandidate],
    max_trials: int = 50,
    pause_seconds: float = 0.5,
) -> List[ExtractedResult]:
    """
    Extract results for all high-tier candidates with posted results.
    """
    # Filter to high tier with results
    high_with_results = [
        c for c in candidates
        if c.tier == "high" and c.has_results
    ]

    # Sort by score descending, take top N
    high_with_results.sort(key=lambda c: c.score, reverse=True)
    to_extract = high_with_results[:max_trials]

    logger.info(f"Extracting results for {len(to_extract)} high-tier trials")

    results = []
    for i, candidate in enumerate(to_extract):
        result = extract_trial_results(candidate)
        results.append(result)
        logger.info(
            f"  [{i+1}/{len(to_extract)}] {candidate.nct_id}: "
            f"{result.parse_status}, {len(result.outcomes)} outcomes"
        )
        time.sleep(pause_seconds)

    return results


def save_results(
    results: List[ExtractedResult],
    biomarker_id: str,
    output_dir: str,
) -> str:
    """Save extracted results to JSON. Returns the file path."""
    biomarker_dir = os.path.join(output_dir, biomarker_id)
    os.makedirs(biomarker_dir, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    path = os.path.join(biomarker_dir, f"results_{date_str}.json")

    data = {
        "biomarker_id": biomarker_id,
        "total_extracted": len(results),
        "parse_status_counts": _count_parse_statuses(results),
        "results": [r.to_dict() for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved results to {path}")
    return path


def _count_parse_statuses(results: List[ExtractedResult]) -> Dict[str, int]:
    """Count results by parse status."""
    counts = {}
    for r in results:
        counts[r.parse_status] = counts.get(r.parse_status, 0) + 1
    return counts
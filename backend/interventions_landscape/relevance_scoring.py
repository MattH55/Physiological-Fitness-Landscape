"""
Relevance scoring: score and tier trial candidates from the sweep.

Each TrialHit from the sweep is scored on multiple dimensions:
  - Biomarker specificity: how directly the trial mentions the biomarker
  - Interventional status: is it an interventional study?
  - Completion status: is it completed?
  - Results availability: does it have posted results?
  - Phase: later phases are more informative
  - Search source: which searches found it (more sources = more relevant)

Tiers:
  high:     score >= 70  (strong biomarker relevance, interventional, completed)
  review:   score >= 40  (moderate relevance, worth manual review)
  candidate: score >= 20 (weak relevance, possible tangential connection)
  low:      score < 20   (likely noise)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from .biomarker_ontology import get_ontology
from .ctgov_sweep import SweepResult, TrialHit

logger = logging.getLogger(__name__)


@dataclass
class ScoredCandidate:
    """A trial hit with a relevance score and tier assignment."""
    nct_id: str
    brief_title: str
    overall_status: str
    condition: str
    intervention_name: str
    intervention_type: str
    study_type: str
    phase: str
    has_results: bool
    start_date: str
    completion_date: str
    lead_sponsor: str
    search_source: str
    score: float = 0.0
    tier: str = "low"
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "nct_id": self.nct_id,
            "brief_title": self.brief_title,
            "overall_status": self.overall_status,
            "condition": self.condition,
            "intervention_name": self.intervention_name,
            "intervention_type": self.intervention_type,
            "study_type": self.study_type,
            "phase": self.phase,
            "has_results": self.has_results,
            "start_date": self.start_date,
            "completion_date": self.completion_date,
            "lead_sponsor": self.lead_sponsor,
            "search_source": self.search_source,
            "score": self.score,
            "tier": self.tier,
            "score_breakdown": self.score_breakdown,
        }


def _score_biomarker_specificity(hit: TrialHit, ontology) -> float:
    """
    Score how specifically the trial mentions the biomarker.
    Higher = more specific mention.
    """
    score = 0.0
    text = f"{hit.brief_title} {hit.condition}".lower()
    all_terms = [t.lower() for t in ontology.all_search_terms()]

    # Canonical name in title = strong signal
    if ontology.canonical_name.lower() in hit.brief_title.lower():
        score += 30
    elif ontology.canonical_name.lower() in text:
        score += 20

    # Alias in title
    for alias in ontology.aliases:
        if alias.lower() in hit.brief_title.lower():
            score += 15
            break

    # Assay term in title
    for at in ontology.assay_terms:
        if at.lower() in hit.brief_title.lower():
            score += 10
            break

    # Multiple terms present
    term_count = sum(1 for t in all_terms if t in text)
    score += min(term_count * 3, 15)

    return min(score, 50.0)


def _score_interventional(hit: TrialHit) -> float:
    """Score interventional status."""
    if hit.study_type or hit.phase:
        return 20.0
    if hit.intervention_name:
        return 15.0
    return 0.0


def _score_completion(hit: TrialHit) -> float:
    """Score completion status."""
    if hit.overall_status == "COMPLETED":
        return 15.0
    if hit.overall_status in ("ACTIVE_NOT_RECRUITING", "RECRUITING"):
        return 5.0
    return 0.0


def _score_results(hit: TrialHit) -> float:
    """Score results availability."""
    if hit.has_results:
        return 15.0
    return 0.0


def _score_phase(hit: TrialHit) -> float:
    """Score by phase (later = more informative)."""
    phase = hit.phase.upper()
    if "PHASE 4" in phase:
        return 10.0
    elif "PHASE 3" in phase:
        return 8.0
    elif "PHASE 2" in phase:
        return 5.0
    elif "PHASE 1" in phase:
        return 3.0
    elif "EARLY_PHASE" in phase:
        return 2.0
    return 0.0


def _score_search_sources(hit: TrialHit) -> float:
    """
    Score based on which searches found this trial.
    Found by multiple independent searches = more relevant.
    """
    sources = [s.strip() for s in hit.search_source.split(",") if s.strip()]
    unique_prefixes = set(s.split(":")[0] for s in sources)

    # Found by outcome search (A/B) = strong signal
    if "A" in unique_prefixes or "B" in unique_prefixes:
        return 10.0
    # Found by interventional search (C/D)
    if "C" in unique_prefixes or "D" in unique_prefixes:
        return 7.0
    # Found by general search (F)
    if "F" in unique_prefixes:
        return 5.0
    # Found by measurement/assay search (E/G)
    if "E" in unique_prefixes or "G" in unique_prefixes:
        return 3.0
    # Found by intervention expansion (H)
    if "H" in unique_prefixes:
        return 2.0
    return 0.0


def _assign_tier(score: float) -> str:
    """Assign tier based on score."""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "review"
    elif score >= 20:
        return "candidate"
    return "low"


def score_trial(hit: TrialHit, biomarker_id: str) -> ScoredCandidate:
    """Score a single trial hit."""
    ontology = get_ontology(biomarker_id)

    breakdown = {
        "biomarker_specificity": _score_biomarker_specificity(hit, ontology),
        "interventional": _score_interventional(hit),
        "completion": _score_completion(hit),
        "results": _score_results(hit),
        "phase": _score_phase(hit),
        "search_sources": _score_search_sources(hit),
    }

    total = sum(breakdown.values())
    tier = _assign_tier(total)

    return ScoredCandidate(
        nct_id=hit.nct_id,
        brief_title=hit.brief_title,
        overall_status=hit.overall_status,
        condition=hit.condition,
        intervention_name=hit.intervention_name,
        intervention_type=hit.intervention_type,
        study_type=hit.study_type,
        phase=hit.phase,
        has_results=hit.has_results,
        start_date=hit.start_date,
        completion_date=hit.completion_date,
        lead_sponsor=hit.lead_sponsor,
        search_source=hit.search_source,
        score=round(total, 1),
        tier=tier,
        score_breakdown={k: round(v, 1) for k, v in breakdown.items()},
    )


def score_sweep_result(sweep: SweepResult) -> List[ScoredCandidate]:
    """
    Score all hits in a sweep result.
    Returns list of ScoredCandidate sorted by score descending.
    """
    candidates = []
    for hit in sweep.hits:
        candidate = score_trial(hit, sweep.biomarker_id)
        candidates.append(candidate)

    # Sort by score descending
    candidates.sort(key=lambda c: c.score, reverse=True)

    logger.info(
        f"Scored {len(candidates)} candidates for {sweep.biomarker_id}"
    )
    return candidates


def tier_distribution(candidates: List[ScoredCandidate]) -> Dict[str, int]:
    """Count candidates by tier."""
    dist = {"high": 0, "review": 0, "candidate": 0, "low": 0}
    for c in candidates:
        dist[c.tier] = dist.get(c.tier, 0) + 1
    return dist
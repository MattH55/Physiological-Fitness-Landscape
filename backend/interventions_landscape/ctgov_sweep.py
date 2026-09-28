"""
High-recall CT.gov sweep: multi-search matrix per biomarker.

For each biomarker, runs a matrix of searches (A-G) to maximize recall:
  A: query.outc = canonical name
  B: query.outc = each alias
  C: query.term = canonical name AND interventional
  D: query.term = each alias AND interventional
  E: query.cond = related conditions (from ontology)
  F: query.term = measurement terms
  G: query.term = canonical name (no filter, all study types)

Then optionally runs intervention expansion (H):
  - Extract unique intervention names from hits
  - Search query.intr for each intervention
  - Merge new hits

All hits are deduplicated by NCT ID and stored in a SweepResult.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .biomarker_ontology import get_ontology
from .clinicaltrials_client import search_studies

logger = logging.getLogger(__name__)


@dataclass
class TrialHit:
    """A single trial hit from the sweep."""
    nct_id: str
    brief_title: str = ""
    overall_status: str = ""
    condition: str = ""
    intervention_name: str = ""
    intervention_type: str = ""
    study_type: str = ""
    phase: str = ""
    has_results: bool = False
    start_date: str = ""
    completion_date: str = ""
    lead_sponsor: str = ""
    search_source: str = ""  # which search (A-G, H) found this trial

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
        }


@dataclass
class SweepResult:
    """Aggregated results from all searches for one biomarker."""
    biomarker_id: str
    hits: List[TrialHit] = field(default_factory=list)
    unique_nct_ids: Set[str] = field(default_factory=set)
    search_log: List[dict] = field(default_factory=list)
    total_hits: int = 0

    def add_hit(self, study: dict, source: str) -> bool:
        """Add a study dict from CT.gov API. Returns True if new."""
        nct = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")
        if not nct or nct in self.unique_nct_ids:
            return False

        ident = study.get("protocolSection", {}).get("identificationModule", {})
        status = study.get("protocolSection", {}).get("statusModule", {})
        design = study.get("protocolSection", {}).get("designModule", {})
        arms = study.get("protocolSection", {}).get("armsInterventionsModule", {})
        eligibility = study.get("protocolSection", {}).get("eligibilityModule", {})
        contacts = study.get("protocolSection", {}).get("contactsLocationsModule", {})

        hit = TrialHit(
            nct_id=nct,
            brief_title=ident.get("briefTitle", ""),
            overall_status=status.get("overallStatus", ""),
            condition=", ".join(ident.get("condition", [])),
            intervention_name=", ".join(
                i.get("name", "") for i in arms.get("interventions", [])
            ),
            intervention_type=", ".join(
                i.get("type", "") for i in arms.get("interventions", [])
            ),
            study_type=design.get("phases", [""])[0] if design.get("phases") else "",
            phase=", ".join(design.get("phases", [])),
            has_results=study.get("hasResults", False),
            start_date=status.get("startDateStruct", {}).get("date", ""),
            completion_date=status.get("completionDateStruct", {}).get("date", ""),
            lead_sponsor=contacts.get("centralContacts", [{}])[0].get("name", "")
            if contacts.get("centralContacts") else "",
            search_source=source,
        )
        self.hits.append(hit)
        self.unique_nct_ids.add(nct)
        self.total_hits += 1
        return True

    def summary(self) -> dict:
        """Summary stats for the sweep."""
        completed = sum(1 for h in self.hits if h.overall_status == "COMPLETED")
        with_results = sum(1 for h in self.hits if h.has_results)
        interventional = sum(1 for h in self.hits if h.study_type or h.phase)
        return {
            "biomarker_id": self.biomarker_id,
            "total_hits": self.total_hits,
            "unique_trials": len(self.unique_nct_ids),
            "completed": completed,
            "completed_with_results": with_results,
            "interventional": interventional,
            "searches_run": len(self.search_log),
        }


def _run_single_search(
    query: dict,
    source: str,
    page_size: int,
    max_pages: int,
    pause_seconds: float,
) -> List[dict]:
    """Run a single CT.gov search and return raw study dicts."""
    try:
        studies = search_studies(
            query, page_size=page_size, max_pages=max_pages
        )
        time.sleep(pause_seconds)
        return studies
    except Exception as e:
        logger.warning(f"Search {source} failed: {e}")
        return []


def run_sweep(
    biomarker_id: str,
    page_size: int = 50,
    max_pages: int = 3,
    pause_seconds: float = 0.3,
) -> SweepResult:
    """
    Run the full search matrix (A-G) for one biomarker.
    """
    ontology = get_ontology(biomarker_id)
    result = SweepResult(biomarker_id=biomarker_id)

    # Build search matrix
    searches = []

    # A: query.outc = canonical name
    searches.append(("A", {"query.outc": ontology.canonical_name}))

    # B: query.outc = each alias (limit to first 5 to avoid too many calls)
    for alias in ontology.aliases[:5]:
        searches.append((f"B:{alias}", {"query.outc": alias}))

    # C: query.term = canonical name AND interventional
    searches.append((
        "C",
        {"query.term": f"{ontology.canonical_name} AND AREA[StudyType]INTERVENTIONAL"},
    ))

    # D: query.term = each alias AND interventional (limit to first 3)
    for alias in ontology.aliases[:3]:
        searches.append((
            f"D:{alias}",
            {"query.term": f"{alias} AND AREA[StudyType]INTERVENTIONAL"},
        ))

    # E: query.term = measurement terms (limit to first 3)
    for mt in ontology.measurement_search_terms()[:3]:
        searches.append((f"E:{mt}", {"query.term": mt}))

    # F: query.term = canonical name (no filter, all study types)
    searches.append(("F", {"query.term": ontology.canonical_name}))

    # G: query.term = assay terms (limit to first 3)
    for at in ontology.assay_terms[:3]:
        searches.append((f"G:{at}", {"query.term": at}))

    # Run all searches
    for source, query in searches:
        logger.info(f"  Search {source}: {query}")
        studies = _run_single_search(query, source, page_size, max_pages, pause_seconds)
        new_count = 0
        for study in studies:
            if result.add_hit(study, source):
                new_count += 1
        result.search_log.append({
            "source": source,
            "query": query,
            "hits": len(studies),
            "new_hits": new_count,
        })
        logger.info(f"  Search {source}: {len(studies)} hits, {new_count} new")

    logger.info(f"Sweep complete: {result.summary()}")
    return result


def run_intervention_expansion(
    sweep: SweepResult,
    page_size: int = 50,
    max_pages: int = 2,
    pause_seconds: float = 0.3,
    max_interventions: int = 20,
) -> SweepResult:
    """
    Intervention expansion loop (search H):
    Extract unique intervention names from existing hits,
    search query.intr for each, merge new hits.
    """
    # Extract unique intervention names
    interventions: Set[str] = set()
    for hit in sweep.hits:
        if hit.intervention_name:
            # Split on comma if multiple
            for name in hit.intervention_name.split(","):
                name = name.strip()
                if name and len(name) > 2:
                    interventions.add(name)

    # Sort by frequency (most common first) - approximate by just taking first N
    intervention_list = list(interventions)[:max_interventions]
    logger.info(f"Intervention expansion: {len(intervention_list)} unique interventions")

    for intr in intervention_list:
        source = f"H:{intr[:40]}"
        query = {"query.intr": intr}
        logger.info(f"  Search {source}")
        studies = _run_single_search(query, source, page_size, max_pages, pause_seconds)
        new_count = 0
        for study in studies:
            if sweep.add_hit(study, source):
                new_count += 1
        sweep.search_log.append({
            "source": source,
            "query": query,
            "hits": len(studies),
            "new_hits": new_count,
        })
        logger.info(f"  Search {source}: {len(studies)} hits, {new_count} new")

    logger.info(f"After expansion: {sweep.summary()}")
    return sweep


def run_results_sweep(
    biomarker_id: str,
    page_size: int = 50,
    max_pages: int = 3,
    pause_seconds: float = 0.3,
) -> SweepResult:
    """
    Results-focused sweep: search for completed trials with posted results
    that mention the biomarker.
    """
    ontology = get_ontology(biomarker_id)
    result = SweepResult(biomarker_id=biomarker_id)

    # Search for completed trials with results
    query = {
        "query.term": ontology.canonical_name,
        "filter.overallStatus": "COMPLETED",
        "filter.results": "true",
    }
    logger.info(f"Results sweep: {query}")
    studies = _run_single_search(query, "RESULTS", page_size, max_pages, pause_seconds)
    for study in studies:
        result.add_hit(study, "RESULTS")

    result.search_log.append({
        "source": "RESULTS",
        "query": query,
        "hits": len(studies),
        "new_hits": len(studies),
    })
    logger.info(f"Results sweep: {len(studies)} hits")
    return result


def save_sweep_result(sweep: SweepResult, output_dir: str) -> str:
    """Save sweep results to JSON. Returns the file path."""
    biomarker_dir = os.path.join(output_dir, sweep.biomarker_id)
    os.makedirs(biomarker_dir, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    path = os.path.join(biomarker_dir, f"sweep_{date_str}.json")

    data = {
        "summary": sweep.summary(),
        "search_log": sweep.search_log,
        "hits": [h.to_dict() for h in sweep.hits],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved sweep to {path}")
    return path
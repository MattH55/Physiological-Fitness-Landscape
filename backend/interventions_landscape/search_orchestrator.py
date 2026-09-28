"""
For each biomarker, run every query template (§config.py) against Europe
PMC + Cochrane-filtered Europe PMC + ClinicalTrials.gov, dedupe, and write
raw candidates to disk with full provenance -- this is the "thorough
search" step. It does NOT decide which candidates are actually relevant or
extract effect sizes; that's extraction.py's job, deliberately kept
separate so a re-run of extraction doesn't require re-searching.
"""

import json
import os
import time
from typing import Dict, List

from .clinicaltrials_client import search_studies
from .config import (
    BIOMARKER_SEARCH_SPECS, CLINICALTRIALS_QUERY_TEMPLATES,
    EUROPEPMC_QUERY_TEMPLATES,
)
from .literature_search import search_cochrane_reviews, search_europepmc

RAW_DIR = os.environ.get("INTERVENTIONS_RAW_DIR",
                          os.path.join(os.getcwd(), "data", "raw", "interventions"))


def search_biomarker(biomarker_id: str, page_size: int = 25) -> Dict[str, List[dict]]:
    """
    Runs the full query-template set for one biomarker. Returns
    {"literature": [...], "cochrane": [...], "trials": [...]}, each deduped
    by its natural id (pmid/doi/id for literature, nctId for trials).
    """
    spec = BIOMARKER_SEARCH_SPECS.get(biomarker_id)
    if spec is None:
        raise KeyError(f"No search spec for biomarker '{biomarker_id}' -- add one to "
                        f"BIOMARKER_SEARCH_SPECS in config.py first.")

    literature: Dict[str, dict] = {}
    cochrane: Dict[str, dict] = {}
    trials: Dict[str, dict] = {}

    for term in spec.all_terms():
        for template in EUROPEPMC_QUERY_TEMPLATES:
            query = template.format(term=term)
            for rec in search_europepmc(query, page_size=page_size):
                key = rec.get("doi") or f"{rec.get('source')}:{rec.get('id')}"
                if key and key not in literature:
                    rec["_matched_query"] = query
                    rec["_matched_term"] = term
                    literature[key] = rec

        for rec in search_cochrane_reviews(term, page_size=page_size):
            key = rec.get("doi") or f"{rec.get('source')}:{rec.get('id')}"
            if key and key not in cochrane:
                rec["_matched_term"] = term
                cochrane[key] = rec

        for template in CLINICALTRIALS_QUERY_TEMPLATES:
            query = {k: v.format(term=term) for k, v in template.items()}
            for study in search_studies(query, page_size=page_size):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}).get("nctId")
                if nct_id and nct_id not in trials:
                    study["_matched_query"] = query
                    study["_matched_term"] = term
                    trials[nct_id] = study

    return {
        "literature": list(literature.values()),
        "cochrane": list(cochrane.values()),
        "trials": list(trials.values()),
    }


def search_all_biomarkers(page_size: int = 25, pause_seconds: float = 0.5) -> None:
    """Runs search_biomarker for every configured biomarker and writes raw
    results to RAW_DIR/<biomarker_id>/<date>/candidates.json. `pause_seconds`
    is a courtesy delay between biomarkers -- these are free public APIs
    without a documented hard rate limit as of this writing, but hammering
    them across 15+ biomarkers x 5+ query templates each is a lot of
    requests; be a considerate caller."""
    date_str = time.strftime("%Y-%m-%d")
    for biomarker_id in BIOMARKER_SEARCH_SPECS:
        print(f"Searching {biomarker_id}...")
        results = search_biomarker(biomarker_id, page_size=page_size)
        out_dir = os.path.join(RAW_DIR, biomarker_id, date_str)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "candidates.json"), "w") as f:
            json.dump(results, f, indent=2, default=str)
        n = len(results["literature"]) + len(results["cochrane"]) + len(results["trials"])
        print(f"  {n} candidates "
              f"({len(results['literature'])} literature, "
              f"{len(results['cochrane'])} Cochrane, "
              f"{len(results['trials'])} trials)")
        time.sleep(pause_seconds)

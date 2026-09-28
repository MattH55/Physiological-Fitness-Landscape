"""
Publication linkage: link trials to publications via Europe PMC.

For each high/review tier trial:
  1. Search Europe PMC for the NCT ID
  2. Search Europe PMC for the trial title + biomarker
  3. Collect matching publications (PMID, DOI, title, journal, year)
  4. Save linkage data to JSON

Europe PMC REST API: https://www.ebi.ac.uk/europepmc/webservices/rest/search
  - query: search string
  - resultType: core (includes abstract, authors, etc.)
  - pageSize: max 1000
  - format: json
  - No API key required
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from .config import EUROPEPMC_BASE
from .relevance_scoring import ScoredCandidate

logger = logging.getLogger(__name__)


@dataclass
class PublicationLink:
    """A publication linked to a trial."""
    nct_id: str
    pmid: str = ""
    doi: str = ""
    title: str = ""
    journal: str = ""
    year: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    source: str = ""  # "nct_search" or "title_search"

    def to_dict(self) -> dict:
        return {
            "nct_id": self.nct_id,
            "pmid": self.pmid,
            "doi": self.doi,
            "title": self.title,
            "journal": self.journal,
            "year": self.year,
            "authors": self.authors,
            "abstract": self.abstract[:500] if self.abstract else "",
            "source": self.source,
        }


def _search_europepmc(
    query: str,
    page_size: int = 20,
    timeout: int = 30,
) -> List[dict]:
    """Search Europe PMC and return result items."""
    params = {
        "query": query,
        "resultType": "core",
        "pageSize": page_size,
        "format": "json",
    }
    try:
        resp = requests.get(EUROPEPMC_BASE, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("resultList", {}).get("result", [])
    except Exception as e:
        logger.warning(f"Europe PMC search failed: {e}")
        return []


def _parse_europepmc_result(item: dict) -> dict:
    """Parse a single Europe PMC result item."""
    return {
        "pmid": item.get("pmid", ""),
        "doi": item.get("doi", ""),
        "title": item.get("title", ""),
        "journal": item.get("journalInfo", {}).get("journal", {}).get("title", ""),
        "year": item.get("pubYear", ""),
        "authors": [
            a.get("fullName", "") for a in item.get("authorList", {}).get("author", [])
        ],
        "abstract": item.get("abstractText", ""),
    }


def link_trial_publications(
    candidate: ScoredCandidate,
    biomarker_term: str,
    pause_seconds: float = 0.3,
) -> List[PublicationLink]:
    """
    Find publications linked to a trial via Europe PMC.
    """
    links = []
    seen_pmids = set()

    # Search 1: NCT ID
    nct_query = f"EXT_ID:{candidate.nct_id}"
    logger.info(f"  Searching Europe PMC for NCT: {candidate.nct_id}")
    results = _search_europepmc(nct_query)
    time.sleep(pause_seconds)

    for item in results:
        parsed = _parse_europepmc_result(item)
        if parsed["pmid"] and parsed["pmid"] not in seen_pmids:
            seen_pmids.add(parsed["pmid"])
            links.append(PublicationLink(
                nct_id=candidate.nct_id,
                pmid=parsed["pmid"],
                doi=parsed["doi"],
                title=parsed["title"],
                journal=parsed["journal"],
                year=parsed["year"],
                authors=parsed["authors"],
                abstract=parsed["abstract"],
                source="nct_search",
            ))

    # Search 2: Trial title + biomarker (if title is long enough)
    if len(candidate.brief_title) > 10:
        title_query = f'TITLE:"{candidate.brief_title[:80]}" AND "{biomarker_term}"'
        logger.info(f"  Searching Europe PMC for title: {candidate.brief_title[:50]}...")
        results = _search_europepmc(title_query)
        time.sleep(pause_seconds)

        for item in results:
            parsed = _parse_europepmc_result(item)
            if parsed["pmid"] and parsed["pmid"] not in seen_pmids:
                seen_pmids.add(parsed["pmid"])
                links.append(PublicationLink(
                    nct_id=candidate.nct_id,
                    pmid=parsed["pmid"],
                    doi=parsed["doi"],
                    title=parsed["title"],
                    journal=parsed["journal"],
                    year=parsed["year"],
                    authors=parsed["authors"],
                    abstract=parsed["abstract"],
                    source="title_search",
                ))

    return links


def link_all_publications(
    candidates: List[ScoredCandidate],
    biomarker_term: str,
    max_trials: int = 30,
    pause_seconds: float = 0.3,
) -> List[PublicationLink]:
    """
    Link publications for all high/review tier candidates.
    """
    # Filter to high and review tiers
    to_link = [
        c for c in candidates
        if c.tier in ("high", "review")
    ]
    to_link.sort(key=lambda c: c.score, reverse=True)
    to_link = to_link[:max_trials]

    logger.info(f"Linking publications for {len(to_link)} trials")

    all_links = []
    for i, candidate in enumerate(to_link):
        links = link_trial_publications(candidate, biomarker_term, pause_seconds)
        all_links.extend(links)
        logger.info(
            f"  [{i+1}/{len(to_link)}] {candidate.nct_id}: {len(links)} publications"
        )

    return all_links


def save_publication_links(
    links: List[PublicationLink],
    biomarker_id: str,
    output_dir: str,
) -> str:
    """Save publication links to JSON. Returns the file path."""
    biomarker_dir = os.path.join(output_dir, biomarker_id)
    os.makedirs(biomarker_dir, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    path = os.path.join(biomarker_dir, f"publications_{date_str}.json")

    # Group by NCT ID
    by_nct: Dict[str, List[dict]] = {}
    for link in links:
        by_nct.setdefault(link.nct_id, []).append(link.to_dict())

    data = {
        "biomarker_id": biomarker_id,
        "total_links": len(links),
        "trials_linked": len(by_nct),
        "links_by_trial": by_nct,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved publication links to {path}")
    return path
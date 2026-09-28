"""
Literature search: Europe PMC as primary (covers PubMed + PMC full text +
Cochrane review abstracts + preprints in one free, no-key API), PubMed
E-utilities as a fallback.

Europe PMC base URL, params (query/resultType=core/pageSize/format=json),
and no-auth-required status confirmed this session against current docs
and example client code.
"""

import time
from typing import Dict, List, Optional

import requests

from .config import EUROPEPMC_BASE, PUBMED_ESEARCH_BASE, PUBMED_ESUMMARY_BASE


def search_europepmc(query: str, page_size: int = 25, timeout: int = 30,
                      retries: int = 3) -> List[dict]:
    """
    Returns a list of {title, abstract, journal, year, doi, pmid, pmcid,
    source, id, pub_types, url}. `resultType=core` includes abstractText
    and pubTypeList in the response.
    """
    params = {"query": query, "resultType": "core", "pageSize": page_size, "format": "json"}
    resp = _get_with_retry(EUROPEPMC_BASE, params, timeout, retries)
    results = resp.json().get("resultList", {}).get("result", [])
    out = []
    for r in results:
        out.append({
            "title": r.get("title"),
            "abstract": r.get("abstractText"),
            "journal": r.get("journalTitle"),
            "year": r.get("pubYear"),
            "doi": r.get("doi"),
            "pmid": r.get("pmid"),
            "pmcid": r.get("pmcid"),
            "source": r.get("source"),
            "id": r.get("id"),
            "pub_types": r.get("pubTypeList", {}).get("pubType", []),
            "url": f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}",
        })
    return out


def search_cochrane_reviews(term: str, page_size: int = 25) -> List[dict]:
    """Europe PMC, filtered to the Cochrane Database of Systematic Reviews
    journal -- the practical way to surface Cochrane content given there's
    no separate public Cochrane API. Returns abstracts only (Cochrane full
    text is paywalled via Wiley)."""
    query = f'JOURNAL:"Cochrane Database Syst Rev" AND "{term}"'
    return search_europepmc(query, page_size=page_size)


def search_pubmed_fallback(query: str, retmax: int = 25, timeout: int = 30,
                            retries: int = 3) -> List[dict]:
    """
    Fallback only -- use search_europepmc as the primary path, since Europe
    PMC already ingests all PubMed content plus more. This exists for cases
    where Europe PMC is down or rate-limited.
    """
    esearch_params = {"db": "pubmed", "term": query, "retmax": retmax, "retmode": "json"}
    resp = _get_with_retry(PUBMED_ESEARCH_BASE, esearch_params, timeout, retries)
    ids = resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    esummary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    resp2 = _get_with_retry(PUBMED_ESUMMARY_BASE, esummary_params, timeout, retries)
    summary = resp2.json().get("result", {})
    out = []
    for pmid in ids:
        rec = summary.get(pmid)
        if not rec:
            continue
        out.append({
            "title": rec.get("title"),
            "abstract": None,  # esummary doesn't include abstracts; would need efetch for that
            "journal": rec.get("fulljournalname"),
            "year": (rec.get("pubdate") or "")[:4],
            "doi": next((i.get("value") for i in rec.get("articleids", [])
                         if i.get("idtype") == "doi"), None),
            "pmid": pmid,
            "pmcid": None,
            "source": "MED",
            "id": pmid,
            "pub_types": rec.get("pubtype", []),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return out


def _get_with_retry(url: str, params: dict, timeout: int, retries: int) -> requests.Response:
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")

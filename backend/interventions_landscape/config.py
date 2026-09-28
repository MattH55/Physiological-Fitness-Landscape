"""
Config for the interventions layer: for each mortality biomarker, what
searches to run against ClinicalTrials.gov and the literature, and the
controlled vocabularies used downstream.

VERIFIED (checked against current docs/example responses this session):
  - ClinicalTrials.gov API v2: https://clinicaltrials.gov/api/v2/studies
    (query.cond, query.intr, query.outc, query.term, filter.overallStatus,
    pageSize, pageToken, fields -- all confirmed current parameter names)
  - Europe PMC REST API: https://www.ebi.ac.uk/europepmc/webservices/rest/search
    (query, resultType=core, pageSize, format=json -- confirmed current,
    no API key required)

NOT independently verified this session (long-standing, stable APIs, but
worth a spot-check before relying on them in production):
  - PubMed E-utilities (eutils.ncbi.nlm.nih.gov) -- used only as a fallback
    if Europe PMC is unavailable; Europe PMC already ingests all PubMed
    content so it's the primary path.

COCHRANE: there is no public Cochrane API. Cochrane Database of Systematic
Reviews abstracts (not full text -- full text is behind Wiley's paywall)
ARE indexed in Europe PMC, so Cochrane coverage here comes via Europe PMC
with a journal filter, not a separate integration. If you need full-text
Cochrane reviews, that's a manual/licensed step, not something this code
does.
"""

from dataclasses import dataclass, field
from typing import Dict, List

CLINICALTRIALS_BASE = "https://clinicaltrials.gov/api/v2/studies"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PUBMED_ESEARCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Effect measures we'll ask the extraction step to normalize into.
EFFECT_MEASURES = [
    "mean_difference",        # absolute change in biomarker units (treatment - control)
    "standardized_mean_difference",
    "percent_change",
    "relative_risk",          # rare for a continuous biomarker outcome, but some
    "odds_ratio",              # trials report "normalized" as a binary outcome
]

STUDY_DESIGNS = [
    "cochrane_review", "meta_analysis", "systematic_review",
    "rct", "randomized_controlled_trial_registry_entry",  # from ClinicalTrials.gov itself
    "observational", "other",
]

REVIEW_STATUSES = ["AUTO_EXTRACTED", "NEEDS_REVIEW", "MANUAL_VERIFIED", "REJECTED"]


@dataclass
class BiomarkerSearchSpec:
    """What to search for a given biomarker. `label` should match the
    NHANES-toolkit biomarker label so results tie back to the existing
    distribution/HR-curve work. `search_terms` are alternate names/synonyms
    to widen recall (trials and papers don't all use NHANES's variable
    label) -- e.g. CRP trials often say "C-reactive protein" or "hs-CRP",
    rarely "LBXCRP"."""
    biomarker_id: str
    label: str
    search_terms: List[str] = field(default_factory=list)

    def all_terms(self) -> List[str]:
        return [self.label] + self.search_terms


# Starter set matching nhanes_toolkit.config.BIOMARKERS. Extend both
# together -- an intervention search for a biomarker with no NHANES
# distribution can't be connected to the existing HR curve anyway.
BIOMARKER_SEARCH_SPECS: Dict[str, BiomarkerSearchSpec] = {
    "crp": BiomarkerSearchSpec("crp", "C-reactive protein", ["hs-CRP", "high-sensitivity CRP"]),
    "hdl": BiomarkerSearchSpec("hdl", "HDL cholesterol", ["high-density lipoprotein"]),
    "total_cholesterol": BiomarkerSearchSpec("total_cholesterol", "total cholesterol"),
    "glucose": BiomarkerSearchSpec("glucose", "fasting glucose", ["blood glucose"]),
    "albumin": BiomarkerSearchSpec("albumin", "serum albumin"),
    "creatinine": BiomarkerSearchSpec("creatinine", "serum creatinine", ["eGFR", "kidney function"]),
    "wbc": BiomarkerSearchSpec("wbc", "white blood cell count", ["leukocyte count"]),
    "hemoglobin": BiomarkerSearchSpec("hemoglobin", "hemoglobin"),
    "platelet": BiomarkerSearchSpec("platelet", "platelet count"),
}

# Query TEMPLATES applied per search term, in order of specificity. This is
# the "thorough search" strategy -- run all of these per biomarker, not
# just one broad query, since a single query systematically misses whole
# categories (a Cochrane-only query misses primary RCTs not yet reviewed;
# an RCT-only query misses the pooled/meta-analytic estimate you usually
# want as the headline number).
EUROPEPMC_QUERY_TEMPLATES = [
    '"{term}" AND "randomized controlled trial"',
    '"{term}" AND "meta-analysis"',
    '"{term}" AND "systematic review"',
    'JOURNAL:"Cochrane Database Syst Rev" AND "{term}"',
    '"{term}" AND (supplementation OR intervention OR treatment) AND "randomized"',
]

CLINICALTRIALS_QUERY_TEMPLATES = [
    # query.outc searches the outcome-measure text; combined with query.term
    # to require the biomarker also appear somewhere in the record.
    {"query.outc": "{term}"},
    {"query.term": "{term} AND AREA[StudyType]INTERVENTIONAL"},
]

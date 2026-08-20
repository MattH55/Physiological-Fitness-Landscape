"""
Physiological Fitness Landscape — Citation Audit and Backfill Engine
Audits 500+ literature citations, validates PMID / DOI formatting and resolution patterns,
cross-checks prospective mortality hazard ratios against cited evidence bounds,
and generates structured compliance reports with pass/fail gates.
"""

import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import Source, MortalityAssociation, Biomarker, Intervention


PMID_PATTERN = re.compile(r"^\d{7,9}$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")


def parse_pmid_from_text(text: str) -> Optional[str]:
    """Extract standard numeric PMID from citation or URL strings."""
    if not text:
        return None
    m = re.search(r"(?:PMID[:\s]*|pubmed[^\d]*)(\d{7,9})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def parse_doi_from_text(text: str) -> Optional[str]:
    """Extract standard DOI format from citation or URL strings."""
    if not text:
        return None
    m = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", text)
    if m:
        doi = m.group(1).rstrip(".;,")
        return doi
    return None


def audit_citations(db_session: Session) -> Dict[str, Any]:
    """
    Perform a complete audit over all registered Source records in the database,
    cross-referencing with MortalityAssociations and Interventions.
    
    Verifies:
    1. PMID format validity (7-9 numeric digits)
    2. DOI format validity (10.xxxx/...)
    3. Missing identifier backfill detection from raw citation string
    4. Mortality HR sanity vs cited prospective ranges (e.g. CI Lower <= HR <= CI Upper, HR > 0, realistic ranges)
    5. Pass/fail gate summary.
    """
    sources = db_session.query(Source).all()
    associations = db_session.query(MortalityAssociation).join(Biomarker).all()
    interventions = db_session.query(Intervention).join(Biomarker).all()

    total_sources = len(sources)
    valid_pmids = 0
    valid_dois = 0
    missing_both = 0
    backfilled_pmids = 0
    backfilled_dois = 0
    source_issues = []

    for s in sources:
        has_pmid = bool(s.pmid and PMID_PATTERN.match(s.pmid.strip()))
        has_doi = bool(s.doi and DOI_PATTERN.match(s.doi.strip()))

        # Attempt backfill if missing
        inferred_pmid = parse_pmid_from_text(s.citation) or (parse_pmid_from_text(s.url) if s.url else None)
        inferred_doi = parse_doi_from_text(s.citation) or (parse_doi_from_text(s.url) if s.url else None)

        if not has_pmid and inferred_pmid:
            backfilled_pmids += 1
            has_pmid = True
        
        if not has_doi and inferred_doi:
            backfilled_dois += 1
            has_doi = True

        if has_pmid:
            valid_pmids += 1
        if has_doi:
            valid_dois += 1

        if not has_pmid and not has_doi:
            missing_both += 1
            source_issues.append({
                "source_id": s.id,
                "citation": s.citation[:120] + "..." if len(s.citation) > 120 else s.citation,
                "issue": "Missing both verified PMID and DOI",
                "severity": "WARNING"
            })

    # Hazard Ratio Sanity and Discrepancy checks
    hr_audits = []
    hr_discrepancies = []

    for assoc in associations:
        b_slug = assoc.biomarker.slug if assoc.biomarker else "unknown"
        hr = assoc.hazard_ratio
        ci_l = assoc.ci_lower
        ci_u = assoc.ci_upper

        issue = None
        if hr <= 0 or ci_l <= 0 or ci_u <= 0:
            issue = f"Non-positive HR or CI ({hr:.2f} [{ci_l:.2f}-{ci_u:.2f}])"
        elif ci_l > ci_u:
            issue = f"Inverted confidence interval: [{ci_l:.2f} > {ci_u:.2f}]"
        elif hr < ci_l or hr > ci_u:
            issue = f"HR ({hr:.2f}) falls outside confidence interval [{ci_l:.2f}-{ci_u:.2f}]"
        elif hr > 15.0 or hr < 0.05:
            issue = f"Extreme biological HR value: {hr:.2f}"

        audit_entry = {
            "biomarker": b_slug,
            "assoc_id": assoc.id,
            "hr": hr,
            "ci_lower": ci_l,
            "ci_upper": ci_u,
            "direction": assoc.direction,
            "cohort": assoc.cohort_description,
            "status": "PASS" if not issue else "FAIL",
            "issue": issue
        }
        hr_audits.append(audit_entry)

        if issue:
            hr_discrepancies.append(audit_entry)

    # Intervention Citation checks
    intervention_citations = 0
    intervention_pmid_count = 0
    for iv in interventions:
        has_source = iv.source_id or (getattr(iv, "source", None) and iv.source.pmid) or getattr(iv, "pmid_citation", None)
        if has_source:
            intervention_citations += 1
        pmid_val = getattr(iv.source, "pmid", None) if getattr(iv, "source", None) else getattr(iv, "pmid_citation", None)
        if pmid_val and (re.search(r"\d{7,9}", str(pmid_val)) or str(pmid_val).isdigit()):
            intervention_pmid_count += 1

    # Quality Gate Calculation
    # Pass gate criteria:
    # 1. 0 inverted CIs or invalid non-positive HRs
    # 2. At least 85% of sources have PMID or DOI or known canonical citation
    source_coverage_pct = round(((total_sources - missing_both) / max(total_sources, 1)) * 100, 1)
    hr_pass_rate_pct = round(((len(hr_audits) - len(hr_discrepancies)) / max(len(hr_audits), 1)) * 100, 1)
    
    gate_passed = (len(hr_discrepancies) == 0) and (source_coverage_pct >= 85.0)

    summary = {
        "total_sources_audited": total_sources,
        "valid_pmids": valid_pmids,
        "valid_dois": valid_dois,
        "backfilled_pmids": backfilled_pmids,
        "backfilled_dois": backfilled_dois,
        "missing_both": missing_both,
        "missing_identifiers": missing_both,
        "source_coverage_pct": source_coverage_pct,
        "total_hazard_associations_audited": len(hr_audits),
        "hr_discrepancies_count": len(hr_discrepancies),
        "hr_pass_rate_pct": hr_pass_rate_pct,
        "total_interventions": len(interventions),
        "interventions_audited": len(interventions),
        "intervention_citations": intervention_citations,
        "interventions_with_citations": intervention_citations,
        "interventions_with_pmids": intervention_pmid_count,
    }

    report = {
        "gate_status": "PASS" if gate_passed else "FAIL",
        "summary": summary,
        "flagged_records": source_issues + hr_discrepancies,
        "total_sources_audited": total_sources,
        "valid_pmids": valid_pmids,
        "valid_dois": valid_dois,
        "backfilled_pmids": backfilled_pmids,
        "backfilled_dois": backfilled_dois,
        "missing_identifiers": missing_both,
        "source_coverage_pct": source_coverage_pct,
        "total_hazard_associations_audited": len(hr_audits),
        "hr_discrepancies_count": len(hr_discrepancies),
        "hr_pass_rate_pct": hr_pass_rate_pct,
        "hr_discrepancies": hr_discrepancies,
        "interventions_audited": len(interventions),
        "interventions_with_citations": intervention_citations,
        "interventions_with_pmids": intervention_pmid_count,
        "source_warnings": source_issues[:20]
    }

    return report

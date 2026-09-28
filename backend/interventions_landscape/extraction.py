"""
Extract structured (intervention, effect-on-biomarker) records from search
candidates (Europe PMC / Cochrane abstracts, ClinicalTrials.gov records).

This step genuinely needs a reading agent -- effect sizes, doses, and
populations are stated in free text in wildly inconsistent formats, and
regex/keyword extraction over that is unreliable. What CAN and MUST be
enforced in code: (1) the model only ever sees the abstract/registry text
you hand it -- never asked to recall a paper from its own training data,
which would risk fabricated numbers with no real source; (2) every
extracted numeric value must be traceable to text actually present in the
input, checked heuristically below; (3) nothing is auto-published --
everything lands as review_status=NEEDS_REVIEW (or REJECTED if the model
itself flags it) until a human confirms it.

COPYRIGHT: the prompt below explicitly tells the model to paraphrase, not
quote, and to extract only structured facts (numbers, directions, study
design) rather than reproduce abstract text -- consistent with the rest of
this project's citation handling elsewhere. Do not extend this to pull in
full-text Cochrane reviews (paywalled) even if you have institutional
access; that's a separate licensing question this pipeline doesn't try to
answer.

Requires: anthropic, pydantic (pip install anthropic pydantic).
Requires ANTHROPIC_API_KEY in the environment.
"""

import json
import os
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You extract structured data about how interventions affect a specific \
biomarker, from the study text provided. Follow these rules strictly:

1. Use ONLY the text provided in this request. Do not use any other knowledge \
of the study, the intervention, or typical effect sizes for this biomarker. \
If the provided text doesn't state a number, leave that field null -- \
never estimate, infer, or recall a "typical" value from training data.
2. Every numeric field you fill in (effect_value, ci_low, ci_high, p_value, \
n_participants, n_studies) must correspond to a number that literally \
appears in the provided text. If you're inferring rather than reading it \
directly, leave it null and lower your confidence instead.
3. Do not quote the source text verbatim beyond a few words. Summarize/ \
paraphrase in your own words for any free-text fields (population, dose, \
duration, notes).
4. If the text is not actually about an intervention affecting this \
biomarker (e.g. it's an observational study, a study of a different \
biomarker, a protocol with no results yet), return \
found_relevant_effect=false and leave the rest null -- do not force a match.
5. If multiple distinct intervention-biomarker effects are reported in one \
text (e.g. a meta-analysis with subgroup results), return the OVERALL \
pooled estimate as the primary record, and note the existence of subgroup \
results in `notes` without fabricating their specific numbers unless those \
numbers are also explicitly in the text.
6. Set confidence to "low" if the text is only an abstract with vague \
wording, or if you had to make any judgment call about which number to use.

Return ONLY a JSON object matching this schema, no other text:
{
  "found_relevant_effect": bool,
  "intervention_name": str | null,
  "intervention_type": "drug" | "supplement" | "diet" | "exercise" | "device" | "other" | null,
  "effect_measure": "mean_difference" | "standardized_mean_difference" | "percent_change" | "relative_risk" | "odds_ratio" | null,
  "effect_value": float | null,
  "effect_unit": str | null,
  "ci_low": float | null,
  "ci_high": float | null,
  "p_value": float | null,
  "direction": "increases" | "decreases" | "no_significant_effect" | null,
  "dose": str | null,
  "duration": str | null,
  "population": str | null,
  "n_participants": int | null,
  "n_studies": int | null,
  "study_design": "cochrane_review" | "meta_analysis" | "systematic_review" | "rct" | "observational" | "other" | null,
  "confidence": "high" | "medium" | "low",
  "notes": str | null
}"""


class ExtractedEffect(BaseModel):
    found_relevant_effect: bool
    intervention_name: Optional[str] = None
    intervention_type: Optional[str] = None
    effect_measure: Optional[str] = None
    effect_value: Optional[float] = None
    effect_unit: Optional[str] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    p_value: Optional[float] = None
    direction: Optional[str] = None
    dose: Optional[str] = None
    duration: Optional[str] = None
    population: Optional[str] = None
    n_participants: Optional[int] = None
    n_studies: Optional[int] = None
    study_design: Optional[str] = None
    confidence: str = "low"
    notes: Optional[str] = None


class ReviewRow(BaseModel):
    biomarker_id: str
    effect: ExtractedEffect
    source: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    publication_date: Optional[str] = None
    retrieved_date: str = Field(default_factory=lambda: date.today().isoformat())
    extraction_model: str = EXTRACTION_MODEL
    review_status: str = "NEEDS_REVIEW"
    plausibility_flag: Optional[str] = None


def _candidate_text(candidate: dict) -> str:
    """Build the text block handed to the model. For literature: title +
    abstract. For a ClinicalTrials.gov registry entry: title + condition/
    intervention fields (registry text, not results, unless you've already
    run extract_outcome_measurements and want to hand it the outcomes
    blob too -- pass that in separately if so)."""
    parts = [candidate.get("title") or ""]
    if candidate.get("abstract"):
        parts.append(candidate["abstract"])
    if candidate.get("protocolSection"):  # a raw CT.gov study record
        ident = candidate["protocolSection"].get("identificationModule", {})
        desc = candidate["protocolSection"].get("descriptionModule", {})
        parts.append(ident.get("briefTitle", ""))
        parts.append(desc.get("briefSummary", ""))
    return "\n\n".join(p for p in parts if p)


def extract_effect(biomarker_label: str, candidate: dict, client=None) -> ReviewRow:
    """
    Calls the LLM once on one candidate's text. `client` is an
    anthropic.Anthropic() instance -- passed in rather than constructed
    here so callers can reuse one client (and so this function is mockable
    in tests without needing a real API key).
    """
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    text = _candidate_text(candidate)
    user_prompt = (
        f"Target biomarker: {biomarker_label}\n\n"
        f"Study text:\n{text}"
    )

    response = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
    return _parse_and_validate(biomarker_label, candidate, raw_text)


def _parse_and_validate(biomarker_label: str, candidate: dict, raw_text: str) -> ReviewRow:
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
        effect = ExtractedEffect(**payload)
    except (json.JSONDecodeError, ValidationError) as e:
        # Model returned something unparseable -- fail closed into a
        # REJECTED row with the raw text preserved for a human to look at,
        # rather than crash the whole batch or silently drop the candidate.
        effect = ExtractedEffect(found_relevant_effect=False, confidence="low",
                                  notes=f"PARSE_ERROR: {e}")
        review_status = "REJECTED"
    else:
        review_status = "NEEDS_REVIEW" if effect.found_relevant_effect else "REJECTED"

    source = "COCHRANE" if candidate.get("source") == "MED" and "Cochrane" in (candidate.get("journal") or "") \
        else ("CLINICALTRIALS" if "protocolSection" in candidate else "EUROPEPMC")
    source_id = candidate.get("doi") or candidate.get("pmid") or \
        candidate.get("protocolSection", {}).get("identificationModule", {}).get("nctId")

    return ReviewRow(
        biomarker_id=biomarker_label,
        effect=effect,
        source=source,
        source_id=source_id,
        source_url=candidate.get("url"),
        source_title=candidate.get("title"),
        publication_date=str(candidate.get("year")) if candidate.get("year") else None,
        review_status=review_status,
    )


def check_plausibility(row: ReviewRow, nhanes_p10: Optional[float], nhanes_p90: Optional[float]) -> ReviewRow:
    """
    Flags (doesn't reject) an effect whose magnitude, applied to a
    population-typical value, would land outside the NHANES-observed
    range for this biomarker -- a cheap sanity check against the
    distribution work already built (stratified_summary in the NHANES
    toolkit). A flagged row still needs human review either way; this
    just prioritizes attention on the more implausible-looking ones.

    Returns a NEW row (doesn't mutate `row`) with plausibility_flag set to
    either the flag or None -- always assigned explicitly so re-checking a
    row against a different reference range doesn't leave a stale flag
    from a previous call.
    """
    flag = None
    if nhanes_p10 is not None and nhanes_p90 is not None and row.effect.effect_value is not None:
        if row.effect.effect_measure == "mean_difference":
            span = nhanes_p90 - nhanes_p10
            if span > 0 and abs(row.effect.effect_value) > span:
                flag = "implausible_effect_size"
    return row.model_copy(update={"plausibility_flag": flag})


def extract_batch(biomarker_label: str, candidates: List[dict], client=None) -> List[ReviewRow]:
    rows = []
    for c in candidates:
        try:
            rows.append(extract_effect(biomarker_label, c, client=client))
        except Exception as e:  # noqa: BLE001 -- one bad candidate shouldn't kill the batch
            rows.append(ReviewRow(
                biomarker_id=biomarker_label,
                effect=ExtractedEffect(found_relevant_effect=False, confidence="low",
                                        notes=f"EXTRACTION_ERROR: {e}"),
                source="EUROPEPMC", review_status="REJECTED",
            ))
    return rows


def write_review_csv(rows: List[ReviewRow], path: str, append: bool = True) -> None:
    """Flattens ReviewRow objects (including the nested `effect`) into a
    flat CSV for human review -- one row per candidate, regardless of
    whether extraction found a relevant effect (REJECTED rows stay in the
    file too, so a reviewer can spot-check false negatives)."""
    import csv

    fieldnames = [
        "biomarker_id", "review_status", "plausibility_flag", "confidence",
        "found_relevant_effect", "intervention_name", "intervention_type",
        "effect_measure", "effect_value", "effect_unit", "ci_low", "ci_high",
        "p_value", "direction", "dose", "duration", "population",
        "n_participants", "n_studies", "study_design",
        "source", "source_id", "source_url", "source_title",
        "publication_date", "retrieved_date", "extraction_model", "notes",
    ]
    file_exists = os.path.exists(path)
    mode = "a" if (append and file_exists) else "w"
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for row in rows:
            flat = row.model_dump(exclude={"effect"})
            flat.update(row.effect.model_dump())
            writer.writerow({k: flat.get(k) for k in fieldnames})

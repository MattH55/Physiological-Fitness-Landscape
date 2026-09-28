"""
Ingest the INTERVENTIONS_CATALOG (backend/interventions_catalog.py) into the
Intervention → Biomarker Effects database schema.

For each biomarker in the catalog, this script:
  1. Creates/updates an InterventionEntity for each unique intervention name
  2. Creates an InterventionRegimen (generic, since the catalog has no dose details)
  3. Creates an InterventionBiomarkerEffect with the magnitude parsed from the catalog
  4. Creates an InterventionEvidence with the citation/PMID
  5. Creates an EvidencePopulation (generic adult population)
  6. Creates an InterventionComparator (standard care / no intervention)
  7. Creates an EffectMeasurement (if numeric values can be parsed)

The script is idempotent: it checks for existing records by intervention_id,
evidence_id, and effect_id before inserting.

Usage:
    python backend/ingest_intervention_effects.py
    python backend/ingest_intervention_effects.py --dry-run
"""

import os
import re
import sys
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import (
    Biomarker,
    InterventionEntity,
    InterventionRegimen,
    InterventionBiomarkerEffect,
    InterventionEvidence,
    EvidencePopulation,
    InterventionComparator,
    EffectMeasurement,
    get_engine,
    init_db,
)
from backend.interventions_catalog import INTERVENTIONS_CATALOG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert a human-readable name to a URL/slug-friendly identifier."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    text = re.sub(r"^_+|_+$", "", text)
    return text[:100]


def make_intervention_id(name: str) -> str:
    """Generate a stable intervention_id from the intervention name."""
    return slugify(name)


def make_evidence_id(pmid: Optional[str], citation: str) -> str:
    """Generate a stable evidence_id from PMID or citation hash."""
    if pmid:
        return f"PMID-{pmid}"
    # Hash the citation for a stable ID
    h = hashlib.md5(citation.encode("utf-8")).hexdigest()[:12]
    return f"CIT-{h}"


def make_effect_id(intervention_id: str, biomarker_slug: str, direction: str) -> str:
    """Generate a stable effect_id."""
    return f"{intervention_id}_{biomarker_slug}_{direction}"


def make_regimen_id(intervention_id: str) -> str:
    """Generate a stable regimen_id (generic since catalog has no dose details)."""
    return f"{intervention_id}_standard"


def make_comparator_id(intervention_id: str) -> str:
    """Generate a stable comparator_id."""
    return f"{intervention_id}_standard_care"


def make_population_id(evidence_id: str) -> str:
    """Generate a stable population_id."""
    return f"{evidence_id}_adults"


def make_measurement_id(effect_id: str) -> str:
    """Generate a stable measurement_id."""
    return f"{effect_id}_meas"


def parse_magnitude(magnitude_str: str) -> Dict[str, Any]:
    """
    Parse a magnitude string like '-20% to -35% reduction' or
    '+5 to +10 mg/dL (+8% to +18%) increase' into structured values.

    Returns a dict with:
      - effect_value: float (midpoint) or None
      - effect_lower: float or None
      - effect_upper: float or None
      - effect_unit: str or None
      - effect_scale: 'percent' or 'absolute' or None
      - direction: 'decrease' or 'increase' or 'mixed'
    """
    result = {
        "effect_value": None,
        "effect_lower": None,
        "effect_upper": None,
        "effect_unit": None,
        "effect_scale": None,
        "direction": "mixed",
    }

    if not magnitude_str:
        return result

    s = magnitude_str.strip()

    # Determine direction
    has_decrease = bool(re.search(r"reduction|decrease|drop|lower|decline|suppression|mitigation|preservation", s, re.I))
    has_increase = bool(re.search(r"increase|elevation|rise|gain|boost|improvement", s, re.I))

    if has_decrease and not has_increase:
        result["direction"] = "decrease"
    elif has_increase and not has_decrease:
        result["direction"] = "increase"
    else:
        result["direction"] = "mixed"

    # Try to extract percentage values
    pct_matches = re.findall(r"[-+]?\d+(?:\.\d+)?\s*%", s)
    # Try to extract absolute values with units
    abs_matches = re.findall(r"[-+]?\d+(?:\.\d+)?\s*(?:mg/dL|mg/L|mm/hr|mL/min|ng/mL|g/kg|units|mmHg|mg|g|L|hr|weeks|months|years)", s, re.I)

    if pct_matches:
        result["effect_scale"] = "percent"
        result["effect_unit"] = "%"
        values = [float(m.replace("%", "").replace("+", "")) for m in pct_matches]
        if len(values) >= 2:
            result["effect_lower"] = min(values)
            result["effect_upper"] = max(values)
            result["effect_value"] = round((result["effect_lower"] + result["effect_upper"]) / 2, 2)
        elif len(values) == 1:
            result["effect_value"] = values[0]
            result["effect_lower"] = values[0]
            result["effect_upper"] = values[0]

    elif abs_matches:
        result["effect_scale"] = "absolute"
        # Extract the unit from the first match
        first_match = abs_matches[0]
        unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(.+)$", first_match)
        if unit_match:
            result["effect_unit"] = unit_match.group(2).strip()
        values = []
        for m in abs_matches:
            num_match = re.match(r"[-+]?\d+(?:\.\d+)?", m)
            if num_match:
                values.append(float(num_match.group()))
        if len(values) >= 2:
            result["effect_lower"] = min(values)
            result["effect_upper"] = max(values)
            result["effect_value"] = round((result["effect_lower"] + result["effect_upper"]) / 2, 2)
        elif len(values) == 1:
            result["effect_value"] = values[0]
            result["effect_lower"] = values[0]
            result["effect_upper"] = values[0]

    return result


def map_evidence_strength(evidence_strength: str) -> Tuple[str, str]:
    """
    Map the catalog's evidence_strength string to the schema's
    study_design and evidence_tier.

    Returns (study_design, evidence_tier).
    """
    es = evidence_strength.lower()

    if "rct" in es or "randomized" in es:
        return "rct", "RCT"
    elif "meta" in es:
        return "meta_analysis", "META_ANALYSIS"
    elif "systematic" in es:
        return "systematic_review", "SYSTEMATIC_REVIEW"
    elif "cohort" in es:
        return "prospective_cohort", "OBSERVATIONAL"
    elif "guideline" in es:
        return "clinical_guideline", "CLINICAL_GUIDELINE"
    elif "mechanistic" in es:
        return "mechanistic_study", "MECHANISTIC"
    elif "cross" in es:
        return "cross_sectional_survey", "OBSERVATIONAL"
    else:
        return "observational", "OBSERVATIONAL"


def map_category_to_intervention_type(category: str) -> str:
    """Map the catalog's category to the schema's intervention_type."""
    cat = category.lower()
    if "pharmacologic" in cat or "pharmaceutical" in cat or "drug" in cat:
        return "PHARMACOLOGIC"
    elif "diet" in cat or "nutrition" in cat:
        return "DIET"
    elif "exercise" in cat or "physical" in cat:
        return "EXERCISE"
    elif "behavioral" in cat or "behavior" in cat:
        return "BEHAVIORAL"
    elif "lifestyle" in cat:
        return "LIFESTYLE"
    elif "nutraceutical" in cat or "supplement" in cat:
        return "NUTRACEUTICAL"
    elif "clinical" in cat:
        return "CLINICAL_PROCEDURE"
    elif "sleep" in cat:
        return "SLEEP"
    elif "environmental" in cat:
        return "ENVIRONMENTAL"
    elif "physiological" in cat:
        return "PHYSIOLOGICAL"
    else:
        return "LIFESTYLE"


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest_catalog(
    db: Session,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Ingest the INTERVENTIONS_CATALOG into the database.

    Returns a summary dict with counts.
    """
    stats = {
        "biomarkers_processed": 0,
        "biomarkers_skipped": 0,
        "interventions_created": 0,
        "interventions_existing": 0,
        "regimens_created": 0,
        "effects_created": 0,
        "effects_existing": 0,
        "evidence_created": 0,
        "evidence_existing": 0,
        "populations_created": 0,
        "comparators_created": 0,
        "measurements_created": 0,
        "errors": [],
    }

    # Load all biomarkers into a dict by slug
    biomarkers = db.query(Biomarker).all()
    biomarker_map = {bm.slug: bm for bm in biomarkers}

    for bm_slug, bm_data in INTERVENTIONS_CATALOG.items():
        # Check if biomarker exists in DB
        if bm_slug not in biomarker_map:
            stats["biomarkers_skipped"] += 1
            continue

        biomarker = biomarker_map[bm_slug]
        stats["biomarkers_processed"] += 1

        # Process favorable and unfavorable interventions
        for direction in ["favorable", "unfavorable"]:
            interventions = bm_data.get(direction, [])
            for intv in interventions:
                try:
                    _ingest_single_intervention(
                        db=db,
                        biomarker=biomarker,
                        intervention_data=intv,
                        direction=direction,
                        dry_run=dry_run,
                        stats=stats,
                    )
                except Exception as e:
                    stats["errors"].append(
                        f"{bm_slug}/{intv.get('name', '?')}: {str(e)}"
                    )

    if not dry_run:
        db.commit()

    return stats


def _ingest_single_intervention(
    db: Session,
    biomarker: Biomarker,
    intervention_data: Dict[str, Any],
    direction: str,
    dry_run: bool,
    stats: Dict[str, Any],
):
    """Ingest a single intervention entry from the catalog."""

    name = intervention_data.get("name", "")
    category = intervention_data.get("category", "Lifestyle")
    magnitude = intervention_data.get("magnitude", "")
    evidence_strength = intervention_data.get("evidence_strength", "RCT")
    citation = intervention_data.get("citation", "")
    pmid = intervention_data.get("pmid")

    if not name:
        return

    # --- InterventionEntity ---
    intervention_id = make_intervention_id(name)
    intervention_type = map_category_to_intervention_type(category)

    existing_intv = (
        db.query(InterventionEntity)
        .filter(InterventionEntity.intervention_id == intervention_id)
        .first()
    )

    if existing_intv:
        stats["interventions_existing"] += 1
        intv_entity = existing_intv
    else:
        if dry_run:
            stats["interventions_created"] += 1
            intv_entity = None
        else:
            intv_entity = InterventionEntity(
                intervention_id=intervention_id,
                canonical_name=name,
                intervention_type=intervention_type,
                description=f"{name} ({category}) — {direction} effect on {biomarker.name}",
                mechanism=None,
                synonyms=[],
            )
            db.add(intv_entity)
            db.flush()
            stats["interventions_created"] += 1

    # --- InterventionRegimen (generic) ---
    regimen_id = make_regimen_id(intervention_id)
    existing_regimen = (
        db.query(InterventionRegimen)
        .filter(InterventionRegimen.regimen_id == regimen_id)
        .first()
    )

    if existing_regimen:
        regimen = existing_regimen
    else:
        if dry_run:
            regimen = None
        else:
            regimen = InterventionRegimen(
                regimen_id=regimen_id,
                intervention_id=intervention_id,
                regimen_description=f"Standard protocol for {name}",
            )
            db.add(regimen)
            db.flush()
            stats["regimens_created"] += 1

    # --- InterventionEvidence ---
    evidence_id = make_evidence_id(pmid, citation)
    study_design, evidence_tier = map_evidence_strength(evidence_strength)

    existing_evidence = (
        db.query(InterventionEvidence)
        .filter(InterventionEvidence.evidence_id == evidence_id)
        .first()
    )

    if existing_evidence:
        stats["evidence_existing"] += 1
        evidence = existing_evidence
    else:
        if dry_run:
            evidence = None
        else:
            # Extract year from citation if possible
            year = None
            year_match = re.search(r"\b(19|20)\d{2}\b", citation)
            if year_match:
                year = int(year_match.group())

            evidence = InterventionEvidence(
                evidence_id=evidence_id,
                source_type=evidence_tier,
                title=citation,
                pmid=pmid,
                study_design=study_design,
                publication_year=year,
            )
            db.add(evidence)
            db.flush()
            stats["evidence_created"] += 1

    # --- EvidencePopulation (generic adult) ---
    population_id = make_population_id(evidence_id)
    existing_pop = (
        db.query(EvidencePopulation)
        .filter(EvidencePopulation.population_id == population_id)
        .first()
    )

    if not existing_pop:
        if not dry_run:
            pop = EvidencePopulation(
                population_id=population_id,
                evidence_id=evidence_id,
                age_min=18,
                age_max=80,
                sex_distribution={"male": 0.5, "female": 0.5},
                baseline_condition="general_population",
            )
            db.add(pop)
            db.flush()
            stats["populations_created"] += 1

    # --- InterventionComparator (standard care) ---
    comparator_id = make_comparator_id(intervention_id)
    existing_comp = (
        db.query(InterventionComparator)
        .filter(InterventionComparator.comparator_id == comparator_id)
        .first()
    )

    if not existing_comp:
        if not dry_run:
            comp = InterventionComparator(
                comparator_id=comparator_id,
                comparator_type="USUAL_CARE",
                comparator_name="Standard care / no intervention",
                description="Standard care / no intervention (control group)",
            )
            db.add(comp)
            db.flush()
            stats["comparators_created"] += 1

    # --- InterventionBiomarkerEffect ---
    effect_id = make_effect_id(intervention_id, biomarker.slug, direction)
    existing_effect = (
        db.query(InterventionBiomarkerEffect)
        .filter(InterventionBiomarkerEffect.effect_id == effect_id)
        .first()
    )

    if existing_effect:
        stats["effects_existing"] += 1
        return

    # Parse magnitude
    parsed = parse_magnitude(magnitude)

    if dry_run:
        stats["effects_created"] += 1
        return

    effect = InterventionBiomarkerEffect(
        effect_id=effect_id,
        intervention_id=intervention_id,
        regimen_id=regimen_id,
        biomarker_id=biomarker.id,
        effect_type="biomarker_change",
        effect_value=parsed["effect_value"],
        effect_lower=parsed["effect_lower"],
        effect_upper=parsed["effect_upper"],
        effect_unit=parsed["effect_unit"],
        effect_scale=parsed["effect_scale"],
        standard_error=None,
        p_value=None,
        baseline_biomarker=None,
        baseline_biomarker_sd=None,
        post_biomarker=None,
        post_biomarker_sd=None,
        sample_size=None,
        intervention_sample_size=None,
        comparator_sample_size=None,
        timepoint_value=None,
        timepoint_unit=None,
        evidence_id=evidence_id,
        comparator_id=comparator_id,
    )
    db.add(effect)
    db.flush()
    stats["effects_created"] += 1

    # --- EffectMeasurement (if we have numeric values) ---
    if parsed["effect_value"] is not None:
        existing_meas = (
            db.query(EffectMeasurement)
            .filter(EffectMeasurement.effect_id == effect_id)
            .first()
        )
        if not existing_meas:
            meas = EffectMeasurement(
                effect_id=effect_id,
                original_value=parsed["effect_value"],
                original_lower=parsed["effect_lower"],
                original_upper=parsed["effect_upper"],
                original_unit=parsed["effect_unit"],
                canonical_value=parsed["effect_value"],
                canonical_lower=parsed["effect_lower"],
                canonical_upper=parsed["effect_upper"],
                canonical_unit=parsed["effect_unit"],
            )
            db.add(meas)
            db.flush()
            stats["measurements_created"] += 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "mortality_biomarkers.db")

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    print(f"{'DRY RUN — ' if dry_run else ''}Ingesting intervention catalog into database...")
    print(f"Database: {db_path}")
    print(f"Catalog biomarkers: {len(INTERVENTIONS_CATALOG)}")
    print()

    stats = ingest_catalog(db, dry_run=dry_run)

    db.close()

    print(f"{'[DRY RUN] ' if dry_run else ''}Ingestion complete.")
    print(f"  Biomarkers processed:  {stats['biomarkers_processed']}")
    print(f"  Biomarkers skipped:    {stats['biomarkers_skipped']} (not in DB)")
    print(f"  Interventions created: {stats['interventions_created']}")
    print(f"  Interventions existing:{stats['interventions_existing']}")
    print(f"  Regimens created:      {stats['regimens_created']}")
    print(f"  Effects created:       {stats['effects_created']}")
    print(f"  Effects existing:      {stats['effects_existing']}")
    print(f"  Evidence created:      {stats['evidence_created']}")
    print(f"  Evidence existing:     {stats['evidence_existing']}")
    print(f"  Populations created:   {stats['populations_created']}")
    print(f"  Comparators created:   {stats['comparators_created']}")
    print(f"  Measurements created:  {stats['measurements_created']}")

    if stats["errors"]:
        print(f"\n  Errors ({len(stats['errors'])}):")
        for err in stats["errors"][:20]:
            print(f"    - {err}")
        if len(stats["errors"]) > 20:
            print(f"    ... and {len(stats['errors']) - 20} more")


if __name__ == "__main__":
    main()
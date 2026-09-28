"""
Generate data/intervention_effects/{biomarker_id}.json files from the
Intervention → Biomarker Effects database.

Structure per biomarker:
{
  "biomarker_id": "crp",
  "biomarker_name": "High-Sensitivity C-Reactive Protein",
  "interventions": [
    {
      "intervention_id": "aerobic_exercise",
      "canonical_name": "Aerobic exercise",
      "intervention_type": "EXERCISE",
      "regimens": [
        {
          "regimen_id": "exercise_150min_16wk",
          "regimen": { ... },
          "effects": [
            {
              "effect_id": "...",
              "effect": { ... },
              "population": { ... },
              "evidence": { ... },
              "comparator": { ... }
            }
          ]
        }
      ]
    }
  ]
}
"""

import os
import json
import sys
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, joinedload

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


def build_biomarker_effects_payload(
    db: Session,
    biomarker: Biomarker,
) -> Dict[str, Any]:
    """Build the full JSON payload for a single biomarker."""
    effects = (
        db.query(InterventionBiomarkerEffect)
        .options(
            joinedload(InterventionBiomarkerEffect.intervention),
            joinedload(InterventionBiomarkerEffect.regimen),
            joinedload(InterventionBiomarkerEffect.evidence),
            joinedload(InterventionBiomarkerEffect.comparator),
            joinedload(InterventionBiomarkerEffect.measurement),
        )
        .filter(InterventionBiomarkerEffect.biomarker_id == biomarker.id)
        .all()
    )

    # Group by intervention
    interventions_map: Dict[str, Dict[str, Any]] = {}
    for eff in effects:
        intv = eff.intervention
        if not intv:
            continue
        intv_id = intv.intervention_id
        if intv_id not in interventions_map:
            interventions_map[intv_id] = {
                "intervention_id": intv_id,
                "canonical_name": intv.canonical_name,
                "intervention_type": intv.intervention_type,
                "description": intv.description,
                "mechanism": intv.mechanism,
                "synonyms": intv.synonyms or [],
                "regimens": {},
            }

        reg_id = eff.regimen_id or "unspecified"
        if reg_id not in interventions_map[intv_id]["regimens"]:
            reg = eff.regimen
            interventions_map[intv_id]["regimens"][reg_id] = {
                "regimen_id": reg_id,
                "regimen": reg.to_dict() if reg else None,
                "effects": [],
            }

        # Build effect entry
        evidence = eff.evidence
        population = None
        if evidence:
            pop = (
                db.query(EvidencePopulation)
                .filter(EvidencePopulation.evidence_id == evidence.evidence_id)
                .first()
            )
            if pop:
                population = pop.to_dict()

        effect_entry = {
            "effect_id": eff.effect_id,
            "effect": {
                "type": eff.effect_type,
                "value": eff.effect_value,
                "lower": eff.effect_lower,
                "upper": eff.effect_upper,
                "standard_error": eff.standard_error,
                "p_value": eff.p_value,
                "unit": eff.effect_unit,
                "scale": eff.effect_scale,
                "timepoint_value": eff.timepoint_value,
                "timepoint_unit": eff.timepoint_unit,
            },
            "measurement": eff.measurement.to_dict() if eff.measurement else None,
            "baseline": {
                "value": eff.baseline_biomarker,
                "sd": eff.baseline_biomarker_sd,
            },
            "post": {
                "value": eff.post_biomarker,
                "sd": eff.post_biomarker_sd,
            },
            "sample_size": eff.sample_size,
            "intervention_sample_size": eff.intervention_sample_size,
            "comparator_sample_size": eff.comparator_sample_size,
            "population": population,
            "evidence": evidence.to_dict() if evidence else None,
            "comparator": eff.comparator.to_dict() if eff.comparator else None,
        }

        interventions_map[intv_id]["regimens"][reg_id]["effects"].append(effect_entry)

    # Convert regimens dict to list
    interventions_list = []
    for intv_data in interventions_map.values():
        regimens_list = list(intv_data["regimens"].values())
        interventions_list.append({
            "intervention_id": intv_data["intervention_id"],
            "canonical_name": intv_data["canonical_name"],
            "intervention_type": intv_data["intervention_type"],
            "description": intv_data["description"],
            "mechanism": intv_data["mechanism"],
            "synonyms": intv_data["synonyms"],
            "regimens": regimens_list,
        })

    return {
        "biomarker_id": biomarker.slug,
        "biomarker_name": biomarker.name,
        "biomarker_units": biomarker.units,
        "interventions": interventions_list,
    }


def generate_all_biomarker_effects(
    db_path: str = "sqlite:///data/mortality_biomarkers.db",
    output_dir: Optional[str] = None,
) -> List[str]:
    """
    Generate JSON files for all biomarkers that have intervention effects.
    Returns list of generated file paths.
    """
    if output_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, "data", "intervention_effects")

    os.makedirs(output_dir, exist_ok=True)

    engine = get_engine(db_path)
    init_db(engine)
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    biomarkers = db.query(Biomarker).order_by(Biomarker.id).all()
    generated = []

    for bm in biomarkers:
        payload = build_biomarker_effects_payload(db, bm)
        if not payload["interventions"]:
            continue

        out_path = os.path.join(output_dir, f"{bm.slug}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        generated.append(out_path)

    db.close()
    return generated


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "mortality_biomarkers.db")
    files = generate_all_biomarker_effects(f"sqlite:///{db_path}")
    print(f"Generated {len(files)} biomarker effect files:")
    for f in files:
        print(f"  {f}")
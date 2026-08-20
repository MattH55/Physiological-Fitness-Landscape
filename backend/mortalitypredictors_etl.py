"""
MortalityPredictors.org Raw Export and Ingestion Pipeline.

Parses timestamped raw export files from data/raw/mortalitypredictors/
and normalizes records into the relational database schema (Source and MortalityAssociation).
"""

import os
import json
import csv
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from backend.models import Biomarker, Source, MortalityAssociation, get_engine, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mortalitypredictors_etl")

DEFAULT_RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "mortalitypredictors")
DEFAULT_EXPORT_JSON = os.path.join(DEFAULT_RAW_DIR, "mortalitypredictors_export_2024.json")
DEFAULT_EXPORT_CSV = os.path.join(DEFAULT_RAW_DIR, "mortalitypredictors_export_2024.csv")


def load_raw_export(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load raw export records from JSON or CSV file.
    """
    if file_path is None:
        file_path = DEFAULT_EXPORT_JSON
        if not os.path.exists(file_path):
            file_path = DEFAULT_EXPORT_CSV

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"MortalityPredictors export file not found at: {file_path}")

    logger.info(f"Loading MortalityPredictors export from: {file_path}")
    if file_path.endswith(".json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "records" in data:
                return data["records"]
            elif isinstance(data, list):
                return data
            else:
                raise ValueError("Unrecognized JSON export structure")
    elif file_path.endswith(".csv"):
        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numerical fields
                converted = dict(row)
                for num_key in ["hazard_ratio", "ci_lower", "ci_upper", "p_value", "hr_unit_scale", "follow_up_years"]:
                    if row.get(num_key) not in (None, "", "null", "None"):
                        try:
                            converted[num_key] = float(row[num_key])
                        except (ValueError, TypeError):
                            converted[num_key] = None
                    else:
                        converted[num_key] = None
                for int_key in ["year", "n", "events"]:
                    if row.get(int_key) not in (None, "", "null", "None"):
                        try:
                            converted[int_key] = int(float(row[int_key]))
                        except (ValueError, TypeError):
                            converted[int_key] = None
                    else:
                        converted[int_key] = None
                records.append(converted)
        return records
    else:
        raise ValueError(f"Unsupported file format for export: {file_path}")


def get_or_create_source(db_session: Session, record: Dict[str, Any]) -> Source:
    """
    Look up existing Source by PMID or DOI or citation, or create new.
    """
    pmid = record.get("pmid")
    doi = record.get("doi")
    citation = record.get("citation", "Unknown Citation")
    year = record.get("year")
    url = record.get("url")
    study_design = record.get("study_design", "prospective_cohort")

    source = None
    if pmid:
        source = db_session.query(Source).filter(Source.pmid == str(pmid)).first()
    if not source and doi:
        source = db_session.query(Source).filter(Source.doi == str(doi)).first()
    if not source and citation:
        source = db_session.query(Source).filter(Source.citation == citation).first()

    if not source:
        source = Source(
            citation=citation,
            pmid=str(pmid) if pmid else None,
            doi=str(doi) if doi else None,
            url=url or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None),
            year=year,
            study_design=study_design
        )
        db_session.add(source)
        db_session.flush()
    elif source.year is None and year is not None:
        source.year = int(year)
        db_session.flush()
    return source


def ingest_mortalitypredictors_data(db_session: Session, file_path: Optional[str] = None) -> Dict[str, int]:
    """
    Normalize and ingest MortalityPredictors export records into SQLite database.
    Returns summary metrics of ingested entities.
    """
    records = load_raw_export(file_path)
    logger.info(f"Loaded {len(records)} raw mortality association records")

    # Build lookup map of biomarker slug -> Biomarker object
    biomarkers = db_session.query(Biomarker).all()
    slug_map = {b.slug: b for b in biomarkers}

    inserted_associations = 0
    sources_created = 0
    skipped_records = 0

    for r in records:
        slug = r.get("biomarker_slug")
        if not slug or slug not in slug_map:
            logger.warning(f"Skipping record with unknown or missing biomarker_slug: '{slug}'")
            skipped_records += 1
            continue

        biomarker = slug_map[slug]
        source = get_or_create_source(db_session, r)

        # Check if identical association already exists to prevent duplication
        existing = db_session.query(MortalityAssociation).filter(
            MortalityAssociation.biomarker_id == biomarker.id,
            MortalityAssociation.source_id == source.id,
            MortalityAssociation.hr_type == r.get("hr_type", "per_sd")
        ).first()

        if existing:
            # Update fields if needed
            existing.hazard_ratio = float(r.get("hazard_ratio", 1.0))
            existing.ci_lower = float(r.get("ci_lower", 1.0))
            existing.ci_upper = float(r.get("ci_upper", 1.0))
            existing.p_value = float(r["p_value"]) if r.get("p_value") is not None else None
            existing.direction = r.get("direction", "higher_worse")
            existing.hr_unit_scale = float(r.get("hr_unit_scale", 1.0))
            existing.cohort_description = r.get("cohort_description")
            existing.n = int(r["n"]) if r.get("n") is not None else None
            existing.events = int(r["events"]) if r.get("events") is not None else None
            existing.follow_up_years = float(r["follow_up_years"]) if r.get("follow_up_years") is not None else None
            existing.population_type = r.get("population_type", "general")
            existing.adjustment_covariates = r.get("adjustment_covariates")
            existing.notes = r.get("notes")
        else:
            assoc = MortalityAssociation(
                biomarker_id=biomarker.id,
                source_id=source.id,
                hazard_ratio=float(r.get("hazard_ratio", 1.0)),
                hr_type=r.get("hr_type", "per_sd"),
                hr_unit_scale=float(r.get("hr_unit_scale", 1.0)),
                ci_lower=float(r.get("ci_lower", 1.0)),
                ci_upper=float(r.get("ci_upper", 1.0)),
                p_value=float(r["p_value"]) if r.get("p_value") is not None else None,
                direction=r.get("direction", "higher_worse"),
                cohort_description=r.get("cohort_description"),
                n=int(r["n"]) if r.get("n") is not None else None,
                events=int(r["events"]) if r.get("events") is not None else None,
                follow_up_years=float(r["follow_up_years"]) if r.get("follow_up_years") is not None else None,
                population_type=r.get("population_type", "general"),
                adjustment_covariates=r.get("adjustment_covariates"),
                notes=r.get("notes")
            )
            db_session.add(assoc)
            inserted_associations += 1

    db_session.commit()
    logger.info(f"MortalityPredictors Ingestion Complete: {inserted_associations} associations added, {skipped_records} skipped.")
    return {
        "total_records": len(records),
        "inserted_associations": inserted_associations,
        "skipped_records": skipped_records
    }


if __name__ == "__main__":
    engine = get_engine()
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        summary = ingest_mortalitypredictors_data(session)
        print("Ingestion Summary:", summary)
    finally:
        session.close()

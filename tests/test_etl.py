"""
Tests for NHANES ETL Data Pipeline and Calibrated Fallbacks.
Verifies variable mapping, distribution statistics calculations, benchmark retrievals, and database population routines.
"""

import os
import pytest
pd = pytest.importorskip("pandas")
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Base, Biomarker, Source, MortalityAssociation, PopulationDistribution, init_db
from backend.nhanes_etl import (
    NHANES_VARIABLE_MAP,
    compute_distribution_stats,
    get_nhanes_calibrated_benchmarks,
    compute_nhanes_distributions
)
from backend.mortalitypredictors_etl import (
    load_raw_export,
    get_or_create_source,
    ingest_mortalitypredictors_data,
    DEFAULT_EXPORT_JSON,
    DEFAULT_EXPORT_CSV
)


def test_nhanes_variable_map():
    """Verify CDC variable map contains key biomarkers with URLs, files, and variable names."""
    expected_slugs = [
        "total_cholesterol", "hdl_cholesterol", "triglycerides", "ldl_cholesterol",
        "fasting_glucose", "hba1c", "high_sensitivity_crp", "serum_creatinine",
        "serum_albumin", "hemoglobin", "systolic_blood_pressure"
    ]
    for slug in expected_slugs:
        assert slug in NHANES_VARIABLE_MAP, f"Missing map for {slug}"
        entry = NHANES_VARIABLE_MAP[slug]
        assert "file" in entry
        assert "url" in entry
        assert "var" in entry
        assert "units" in entry
        assert "cycle" in entry


def test_compute_distribution_stats():
    """Verify percentiles and summary statistics calculation."""
    data = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
    stats = compute_distribution_stats(data)
    assert stats is not None
    assert stats["sample_n"] == 10
    assert stats["mean"] == 55.0
    assert stats["p50"] == 55.0
    assert stats["p5"] < stats["p25"] < stats["p50"] < stats["p75"] < stats["p95"]

    # Test empty or invalid series
    empty_stats = compute_distribution_stats(pd.Series([]))
    assert empty_stats is None


def test_get_nhanes_calibrated_benchmarks():
    """Verify benchmark lookup returns stratified distributions for calibrated markers."""
    crp_benchmarks = get_nhanes_calibrated_benchmarks("high_sensitivity_crp", "mg/L")
    assert len(crp_benchmarks) >= 6
    
    # Check overall stratum
    overall = next((item for item in crp_benchmarks if item[0] == "all" and item[1] == "all"), None)
    assert overall is not None
    sex, age_band, stats = overall
    assert stats["mean"] > 0
    assert stats["p50"] > 0
    assert stats["sample_n"] > 500


def test_compute_nhanes_distributions_db_population():
    """Verify ETL populates population_distribution records in SQLite DB."""
    test_engine = create_engine("sqlite:///:memory:")
    init_db(test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()

    # Create dummy source and biomarker
    source = Source(
        citation="CDC NHANES 2017-2018. National Center for Health Statistics.",
        pmid="CDC-NHANES-2017-2018",
        year=2018,
        study_design="Nationally Representative Survey"
    )
    db.add(source)
    db.commit()

    crp = Biomarker(
        slug="high_sensitivity_crp",
        name="High-Sensitivity C-Reactive Protein (hs-CRP)",
        category="Inflammation",
        units="mg/L",
        specimen_type="Serum"
    )
    db.add(crp)
    db.commit()

    # Run ETL distribution routine
    compute_nhanes_distributions(db, source.id)

    # Verify distributions inserted
    distributions = db.query(PopulationDistribution).filter(PopulationDistribution.biomarker_id == crp.id).all()
    assert len(distributions) >= 1
    
    overall = next((d for d in distributions if d.sex == "all" and d.age_band == "all"), None)
    assert overall is not None
    assert overall.p50 is not None
    assert overall.p50 > 0
    assert overall.sample_n > 0
    assert overall.is_low_confidence in (0, 1)

    db.close()


def test_load_mortalitypredictors_raw_export():
    """Verify loading raw export files in both JSON and CSV formats."""
    assert os.path.exists(DEFAULT_EXPORT_JSON), f"Missing JSON export file at {DEFAULT_EXPORT_JSON}"
    assert os.path.exists(DEFAULT_EXPORT_CSV), f"Missing CSV export file at {DEFAULT_EXPORT_CSV}"

    records_json = load_raw_export(DEFAULT_EXPORT_JSON)
    assert isinstance(records_json, list)
    assert len(records_json) >= 25

    records_csv = load_raw_export(DEFAULT_EXPORT_CSV)
    assert isinstance(records_csv, list)
    assert len(records_csv) >= 25

    # Check key fields in record
    first_record = records_json[0]
    assert "biomarker_slug" in first_record
    assert "hazard_ratio" in first_record
    assert "cohort_description" in first_record
    assert "pmid" in first_record


def test_mortalitypredictors_ingestion_pipeline():
    """Verify ingestion pipeline populates Source and MortalityAssociation entities in DB."""
    test_engine = create_engine("sqlite:///:memory:")
    init_db(test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()

    # Add sample biomarker
    crp = Biomarker(
        slug="high_sensitivity_crp",
        name="High-Sensitivity C-Reactive Protein (hsCRP)",
        category="Inflammation",
        units="mg/L",
        specimen_type="serum"
    )
    db.add(crp)
    db.commit()

    # Run ingestion from JSON export
    summary = ingest_mortalitypredictors_data(db, DEFAULT_EXPORT_JSON)
    assert summary["total_records"] >= 25
    assert summary["inserted_associations"] >= 1

    # Verify association created and properly linked
    assoc = db.query(MortalityAssociation).filter(MortalityAssociation.biomarker_id == crp.id).first()
    assert assoc is not None
    assert assoc.hazard_ratio > 0
    assert assoc.source_id is not None
    assert assoc.source.citation is not None

    db.close()

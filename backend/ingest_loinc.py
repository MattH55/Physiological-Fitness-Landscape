"""
LOINC Reference Ingestion.

Parses the Regenstrief LOINC bulk table (Loinc_2.83.zip -> LoincTable/Loinc.csv)
and populates the `loinc_reference` table with the structured axes
(component, property, time, system, scale, method) for each LOINC code.

This reference table is the lookup used by the §6 matching hierarchy in
TEST_COST_BUILD_SPEC.md to resolve a lab_tests row to a LOINC code via
verified component/specimen/method match against LOINC's structured axes.

Usage:
    python -m backend.ingest_loinc [--zip PATH] [--all-statuses]

By default only ACTIVE codes are ingested (the vast majority of the table).
Pass --all-statuses to include RETIRED / INACTIVE codes as well.
"""

import os
import sys
import csv
import io
import zipfile
import logging
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import sessionmaker
from backend.models import get_engine, init_db
from backend.test_cost_models import LoincReference, init_test_cost_tables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DEFAULT_ZIP = os.path.join(BASE_DIR, "backend", "Loinc_2.83.zip")
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")

# Column index map for Loinc.csv (0-based, from the header row)
COL = {
    "LOINC_NUM": 0,
    "COMPONENT": 1,
    "PROPERTY": 2,
    "TIME_ASPCT": 3,
    "SYSTEM": 4,
    "SCALE_TYP": 5,
    "METHOD_TYP": 6,
    "CLASS": 7,
    "VersionLastChanged": 8,
    "STATUS": 11,
    "SHORTNAME": 20,
    "EXAMPLE_UNITS": 24,
    "LONG_COMMON_NAME": 25,
    "EXAMPLE_UCUM_UNITS": 26,
    "RELATEDNAMES2": 19,
    "VersionFirstReleased": 37,
    "DisplayName": 39,
}


def _find_loinc_csv(zf: zipfile.ZipFile):
    """Locate the main LoincTable/Loinc.csv entry inside the zip.

    Prefers the canonical LoincTable folder; avoids the PanelsAndForms
    accessory CSV which has a different (narrower) schema.
    """
    names = zf.namelist()
    # 1) Exact canonical path
    for name in names:
        if name.lower() == "loinctable/loinc.csv":
            return name
    # 2) Any LoincTable/*.csv
    for name in names:
        low = name.lower()
        if "loinctable" in low and low.endswith(".csv"):
            return name
    # 3) Fallback: any Loinc.csv that is NOT in PanelsAndForms
    for name in names:
        low = name.lower()
        if low.endswith("loinc.csv") and "panelsandforms" not in low:
            return name
    return None


def _clean(value):
    """Normalize a CSV cell: strip whitespace, treat empty as None."""
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def ingest_loinc(zip_path: str, all_statuses: bool = False):
    """Parse the LOINC zip and upsert rows into loinc_reference."""
    if not os.path.exists(zip_path):
        logger.error(f"LOINC zip not found: {zip_path}")
        return 0

    engine = get_engine(f"sqlite:///{DB_PATH}")
    init_db(engine)
    init_test_cost_tables(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    logger.info(f"Opening LOINC zip: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_name = _find_loinc_csv(zf)
        if csv_name is None:
            logger.error("Could not find Loinc.csv inside the zip.")
            db.close()
            return 0
        logger.info(f"Found LOINC CSV entry: {csv_name}")

        # Determine LOINC version from the zip filename (e.g. Loinc_2.83.zip -> 2.83)
        loinc_version = os.path.basename(zip_path).replace("Loinc_", "").replace(".zip", "")

        inserted = 0
        skipped = 0
        batch = []
        # SQLite limits ~999 variables per statement; 19 cols x 500 = 9500 is too high.
        # Use 500 rows x 19 cols = 9500... still too high. Use 50 rows = 950 vars.
        BATCH_SIZE = 50

        with zf.open(csv_name) as f:
            # The file is UTF-8; wrap the binary stream for text iteration
            text_stream = io.TextIOWrapper(f, encoding="utf-8", newline="")
            reader = csv.reader(text_stream)
            header = next(reader, None)
            logger.info(f"CSV header has {len(header)} columns")
            # Validate the header looks like the main LOINC table
            if header and "LOINC_NUM" not in header[0].upper():
                logger.warning(f"Unexpected header in {csv_name}: {header[:5]}")

            for row in reader:
                if not row or len(row) < 12:
                    skipped += 1
                    continue

                loinc_code = _clean(row[COL["LOINC_NUM"]])
                if not loinc_code:
                    skipped += 1
                    continue

                status = _clean(row[COL["STATUS"]]) or ""
                if not all_statuses and status.upper() != "ACTIVE":
                    skipped += 1
                    continue

                rec = LoincReference(
                    loinc_code=loinc_code,
                    component=_clean(row[COL["COMPONENT"]]),
                    property_=_clean(row[COL["PROPERTY"]]),
                    time_aspect=_clean(row[COL["TIME_ASPCT"]]),
                    system=_clean(row[COL["SYSTEM"]]),
                    scale_type=_clean(row[COL["SCALE_TYP"]]),
                    method_type=_clean(row[COL["METHOD_TYP"]]),
                    loinc_class=_clean(row[COL["CLASS"]]),
                    short_name=_clean(row[COL["SHORTNAME"]]),
                    long_common_name=_clean(row[COL["LONG_COMMON_NAME"]]),
                    display_name=_clean(row[COL["DisplayName"]]),
                    status=status,
                    example_units=_clean(row[COL["EXAMPLE_UNITS"]]),
                    example_ucum_units=_clean(row[COL["EXAMPLE_UCUM_UNITS"]]),
                    related_names=_clean(row[COL["RELATEDNAMES2"]]),
                    loinc_version=loinc_version,
                    version_first_released=_clean(row[COL["VersionFirstReleased"]]),
                    version_last_changed=_clean(row[COL["VersionLastChanged"]]),
                    ingested_at=datetime.utcnow(),
                )
                batch.append(rec)

                if len(batch) >= BATCH_SIZE:
                    _upsert_batch(db, batch)
                    inserted += len(batch)
                    batch = []
                    logger.info(f"  ...{inserted} ingested so far")

        if batch:
            _upsert_batch(db, batch)
            inserted += len(batch)

    db.commit()

    total = db.query(LoincReference).count()
    logger.info(f"LOINC ingestion complete: {inserted} upserted, {skipped} skipped. "
                f"Total rows in loinc_reference: {total}")
    db.close()
    return inserted


def _upsert_batch(db, batch):
    """Bulk upsert a batch of LoincReference rows (SQLite INSERT OR IGNORE)."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    values = []
    for r in batch:
        values.append({
            "loinc_code": r.loinc_code,
            "component": r.component,
            "property_": r.property_,
            "time_aspect": r.time_aspect,
            "system": r.system,
            "scale_type": r.scale_type,
            "method_type": r.method_type,
            "loinc_class": r.loinc_class,
            "short_name": r.short_name,
            "long_common_name": r.long_common_name,
            "display_name": r.display_name,
            "status": r.status,
            "example_units": r.example_units,
            "example_ucum_units": r.example_ucum_units,
            "related_names": r.related_names,
            "loinc_version": r.loinc_version,
            "version_first_released": r.version_first_released,
            "version_last_changed": r.version_last_changed,
            "ingested_at": r.ingested_at,
        })
    stmt = sqlite_insert(LoincReference).values(values)
    stmt = stmt.on_conflict_do_nothing(index_elements=["loinc_code"])
    db.execute(stmt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest LOINC reference table")
    parser.add_argument("--zip", default=DEFAULT_ZIP, help="Path to Loinc_*.zip")
    parser.add_argument("--all-statuses", action="store_true",
                        help="Include RETIRED/INACTIVE codes (default: ACTIVE only)")
    args = parser.parse_args()
    ingest_loinc(args.zip, all_statuses=args.all_statuses)
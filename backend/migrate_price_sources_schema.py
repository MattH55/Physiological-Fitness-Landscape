"""
Lightweight migration: adds the price-data-sources-build-spec.md columns to
the existing test_prices / test_cost_summary tables (SQLAlchemy's
create_all only creates missing tables, not missing columns on existing
ones). Safe to run repeatedly — each ALTER is guarded by a column-existence
check.

Run with: python -m backend.migrate_price_sources_schema
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")

TEST_PRICES_NEW_COLUMNS = [
    ("source_tier", "VARCHAR(30)"),
    ("payer", "VARCHAR(200)"),
    ("raw_payload_ref", "VARCHAR(500)"),
    # The exact product this price buys, as named by the provider. Lets a
    # standalone analyte price be told apart from a multi-analyte panel
    # price at the same store.
    ("product_name", "VARCHAR(300)"),
]

TEST_COST_SUMMARY_NEW_COLUMNS = [
    ("reference_price", "FLOAT"),
    ("reference_price_source", "VARCHAR(50)"),
    ("reference_price_region", "VARCHAR(100)"),
    ("reference_price_date", "DATE"),
    ("reference_price_is_carrier_specific", "INTEGER DEFAULT 0"),
    ("negotiated_rate_median", "FLOAT"),
    ("negotiated_rate_iqr_low", "FLOAT"),
    ("negotiated_rate_iqr_high", "FLOAT"),
    ("negotiated_rate_payer_count", "INTEGER"),
    ("negotiated_rate_date", "DATE"),
    ("cash_pay_min", "FLOAT"),
    ("cash_pay_median", "FLOAT"),
    ("cash_pay_max", "FLOAT"),
    ("cash_pay_source_count", "INTEGER"),
    ("cash_pay_date", "DATE"),
    ("cash_pay_standalone_min", "FLOAT"),
    ("cash_pay_standalone_median", "FLOAT"),
    ("cash_pay_standalone_max", "FLOAT"),
    ("cash_pay_standalone_count", "INTEGER"),
]

# Biomarker-level (backend/models.py) — keeps the comparable standalone figure
# and the blended all-products median side by side for the VOI pane.
BIOMARKER_NEW_COLUMNS = [
    ("cash_pay_blended_median", "FLOAT"),
]


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: list):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    added = []
    for name, coltype in columns:
        if name in existing:
            continue
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
        added.append(name)
    return added


def migrate(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        added_prices = _add_missing_columns(conn, "test_prices", TEST_PRICES_NEW_COLUMNS)
        added_summary = _add_missing_columns(conn, "test_cost_summary", TEST_COST_SUMMARY_NEW_COLUMNS)
        added_bm = _add_missing_columns(conn, "biomarker", BIOMARKER_NEW_COLUMNS)
        conn.commit()
        print(f"test_prices: added {added_prices or '(none — already up to date)'}")
        print(f"test_cost_summary: added {added_summary or '(none — already up to date)'}")
        print(f"biomarker: added {added_bm or '(none — already up to date)'}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()

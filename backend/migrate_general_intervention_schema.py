"""
Migration: Apply the general intervention schema (CT.gov-compatible) to the
existing mortality_biomarkers.db. Creates 8 new tables and seeds
intervention_categories.

Run: python backend/migrate_general_intervention_schema.py
"""
import sys
import os
from datetime import datetime

# Ensure we can import from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text, inspect
from backend.models import (
    Base,
    get_engine,
    INTERVENTION_CATEGORIES_SEED,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mortality_biomarkers.db")

def main():
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    
    # Check existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    print(f"Existing tables ({len(existing_tables)}): {existing_tables}")
    
    # New tables to create
    new_tables = [
        "intervention_categories",
        "general_intervention",
        "general_intervention_synonyms",
        "general_intervention_attributes",
        "trial_intervention_arms",
        "intervention_arm_mappings",
        "biomarker_intervention_effects",
        "intervention_hazard_impact",
    ]
    
    tables_to_create = [t for t in new_tables if t not in existing_tables]
    tables_existing = [t for t in new_tables if t in existing_tables]
    
    if tables_existing:
        print(f"\nAlready exist (skipping): {tables_existing}")
    if tables_to_create:
        print(f"\nCreating: {tables_to_create}")
    
    # Create only the new tables
    if tables_to_create:
        # Filter metadata to only include the tables we need
        tables_to_create_set = set(tables_to_create)
        Base.metadata.create_all(engine, tables=[
            Base.metadata.tables[t] for t in tables_to_create
        ])
        print("Tables created successfully.")
    
    # Verify all 8 tables now exist
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    missing = [t for t in new_tables if t not in all_tables]
    if missing:
        print(f"\nERROR: Missing tables after migration: {missing}")
        sys.exit(1)
    print(f"\nAll 8 tables verified present.")
    
    # Seed intervention_categories if empty
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM intervention_categories")).scalar()
        if count == 0:
            print(f"\nSeeding {len(INTERVENTION_CATEGORIES_SEED)} intervention categories...")
            for cat_id, label, ct_type in INTERVENTION_CATEGORIES_SEED:
                conn.execute(
                    text("""
                        INSERT INTO intervention_categories 
                        (category_id, label, ct_gov_intervention_type, created_at)
                        VALUES (:cid, :label, :ct, :now)
                    """),
                    {"cid": cat_id, "label": label, "ct": ct_type, "now": datetime.utcnow()},
                )
            conn.commit()
            print(f"Seeded {len(INTERVENTION_CATEGORIES_SEED)} categories.")
        else:
            print(f"\nintervention_categories already has {count} rows, skipping seed.")
    
    # Verify seed
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT category_id, label, ct_gov_intervention_type FROM intervention_categories ORDER BY category_id")).fetchall()
        print(f"\nintervention_categories ({len(rows)} rows):")
        for r in rows:
            print(f"  {r[0]:30s} {r[1]:50s} -> {r[2]}")
    
    # Test full chain: canonical exercise intervention -> category rollup -> EAV attributes -> raw trial arm -> mapping -> effect estimate
    print("\n" + "=" * 60)
    print("TEST: Full chain verification")
    print("=" * 60)
    
    with engine.connect() as conn:
        # 1. Create a test canonical exercise intervention
        conn.execute(text("""
            INSERT OR IGNORE INTO general_intervention 
            (intervention_id, canonical_name, category_id, description, created_at, updated_at)
            VALUES ('test_exercise_001', 'moderate-intensity aerobic exercise', 'exercise',
                    'Brisk walking, cycling, or swimming at moderate intensity', :now, :now)
        """), {"now": datetime.utcnow()})
        
        # 2. Verify category rollup to CT.gov BEHAVIORAL
        row = conn.execute(text("""
            SELECT gi.canonical_name, ic.label, ic.ct_gov_intervention_type
            FROM general_intervention gi
            JOIN intervention_categories ic ON gi.category_id = ic.category_id
            WHERE gi.intervention_id = 'test_exercise_001'
        """)).fetchone()
        print(f"\n1. Canonical intervention: {row[0]}")
        print(f"   Category: {row[1]}")
        print(f"   CT.gov type: {row[2]}")
        assert row[2] == "BEHAVIORAL", f"Expected BEHAVIORAL, got {row[2]}"
        print("   [OK] Rolls up to CT.gov BEHAVIORAL")
        
        # 3. Add EAV attributes (modality, intensity, frequency -- no schema change needed)
        attrs = [
            ("test_attr_001", "modality", "aerobic", None),
            ("test_attr_002", "intensity", "moderate", None),
            ("test_attr_003", "frequency_per_week", "5", "sessions"),
            ("test_attr_004", "session_duration_min", "30", "minutes"),
        ]
        for attr_id, key, value, unit in attrs:
            conn.execute(text("""
                INSERT OR IGNORE INTO general_intervention_attributes
                (attribute_id, intervention_id, attribute_key, attribute_value, attribute_unit, created_at)
                VALUES (:aid, 'test_exercise_001', :key, :val, :unit, :now)
            """), {"aid": attr_id, "key": key, "val": value, "unit": unit, "now": datetime.utcnow()})
        
        attr_rows = conn.execute(text("""
            SELECT attribute_key, attribute_value, attribute_unit
            FROM general_intervention_attributes
            WHERE intervention_id = 'test_exercise_001'
            ORDER BY attribute_key
        """)).fetchall()
        print(f"\n2. EAV attributes ({len(attr_rows)}):")
        for a in attr_rows:
            unit_str = f" ({a[2]})" if a[2] else ""
            print(f"   {a[0]} = {a[1]}{unit_str}")
        assert len(attr_rows) == 4, f"Expected 4 attributes, got {len(attr_rows)}"
        print("   [OK] 4 exercise-specific attributes, no schema change needed")
        
        # 4. Create a raw trial arm
        conn.execute(text("""
            INSERT OR IGNORE INTO trial_intervention_arms
            (arm_id, source, source_study_id, raw_intervention_type, raw_name, raw_description, arm_group_label, retrieved_date, created_at)
            VALUES ('test_arm_001', 'CLINICALTRIALS', 'NCT01234567', 'Behavioral',
                    'Aerobic Exercise Training Program', '30 min moderate-intensity aerobic exercise 5x/week for 12 weeks',
                    'Intervention', :now, :now)
        """), {"now": datetime.utcnow()})
        
        arm = conn.execute(text("""
            SELECT raw_name, raw_intervention_type, source_study_id
            FROM trial_intervention_arms WHERE arm_id = 'test_arm_001'
        """)).fetchone()
        print(f"\n3. Raw trial arm: {arm[0]}")
        print(f"   Type: {arm[1]}, Study: {arm[2]}")
        print("   [OK] Raw arm created")
        
        # 5. Create a reviewed mapping
        conn.execute(text("""
            INSERT OR IGNORE INTO intervention_arm_mappings
            (mapping_id, arm_id, candidate_intervention_id, match_method, confidence, review_status, review_notes, created_at)
            VALUES ('test_map_001', 'test_arm_001', 'test_exercise_001', 'llm_extracted', 'high',
                    'MANUAL_VERIFIED', 'Verified: aerobic exercise program matches canonical entity', :now)
        """), {"now": datetime.utcnow()})
        
        mapping = conn.execute(text("""
            SELECT m.match_method, m.confidence, m.review_status, gi.canonical_name
            FROM intervention_arm_mappings m
            JOIN general_intervention gi ON m.candidate_intervention_id = gi.intervention_id
            WHERE m.mapping_id = 'test_map_001'
        """)).fetchone()
        print(f"\n4. Mapping: {mapping[3]}")
        print(f"   Method: {mapping[0]}, Confidence: {mapping[1]}, Status: {mapping[2]}")
        assert mapping[2] == "MANUAL_VERIFIED"
        print("   [OK] Reviewed mapping (MANUAL_VERIFIED)")
        
        # 6. Create an effect estimate (need a biomarker_id -- use first one)
        biomarker = conn.execute(text("SELECT id, name FROM biomarker LIMIT 1")).fetchone()
        if biomarker:
            conn.execute(text("""
                INSERT OR IGNORE INTO biomarker_intervention_effects
                (effect_id, biomarker_id, intervention_id, effect_measure, effect_value, effect_unit,
                 ci_low, ci_high, p_value, direction, dose, duration, population,
                 n_participants, n_studies, study_design, source, source_id, source_title,
                 publication_date, retrieved_date, extraction_method, review_status, created_at)
                VALUES ('test_effect_001', :bid, 'test_exercise_001', 'mean_difference', -0.5, 'mg/dL',
                        -0.8, -0.2, 0.001, 'decreases', '30 min 5x/week', '12 weeks', 'adults with elevated biomarkers',
                        500, 3, 'rct', 'PUBMED', 'PMID12345', 'Test Study: Exercise and Biomarker Reduction',
                        '2024-01-15', :now, 'manual', 'MANUAL_VERIFIED', :now)
            """), {"bid": biomarker[0], "now": datetime.utcnow()})
            
            effect = conn.execute(text("""
                SELECT e.effect_measure, e.effect_value, e.direction, b.name, gi.canonical_name
                FROM biomarker_intervention_effects e
                JOIN biomarker b ON e.biomarker_id = b.id
                JOIN general_intervention gi ON e.intervention_id = gi.intervention_id
                WHERE e.effect_id = 'test_effect_001'
            """)).fetchone()
            print(f"\n5. Effect estimate: {effect[3]} + {effect[4]}")
            print(f"   Measure: {effect[0]}, Value: {effect[1]}, Direction: {effect[2]}")
            print("   [OK] Effect estimate linked to canonical intervention + biomarker")
        else:
            print("\n5. No biomarkers in DB, skipping effect test")
        
        # 7. Verify the full join chain
        chain = conn.execute(text("""
            SELECT 
                gi.canonical_name,
                ic.ct_gov_intervention_type,
                COUNT(DISTINCT ga.attribute_id) as n_attrs,
                tia.raw_name,
                m.review_status,
                bie.effect_value
            FROM general_intervention gi
            JOIN intervention_categories ic ON gi.category_id = ic.category_id
            LEFT JOIN general_intervention_attributes ga ON gi.intervention_id = ga.intervention_id
            LEFT JOIN intervention_arm_mappings m ON gi.intervention_id = m.candidate_intervention_id
            LEFT JOIN trial_intervention_arms tia ON m.arm_id = tia.arm_id
            LEFT JOIN biomarker_intervention_effects bie ON gi.intervention_id = bie.intervention_id
            WHERE gi.intervention_id = 'test_exercise_001'
            GROUP BY gi.intervention_id
        """)).fetchone()
        print(f"\n6. Full chain join:")
        print(f"   Intervention: {chain[0]}")
        print(f"   CT.gov type: {chain[1]}")
        print(f"   Attributes: {chain[2]}")
        print(f"   Raw arm: {chain[3]}")
        print(f"   Mapping status: {chain[4]}")
        print(f"   Effect value: {chain[5]}")
        print("   [OK] Full chain verified end-to-end")
        
        conn.commit()
    
    # Cleanup test data
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM biomarker_intervention_effects WHERE effect_id = 'test_effect_001'"))
        conn.execute(text("DELETE FROM intervention_arm_mappings WHERE mapping_id = 'test_map_001'"))
        conn.execute(text("DELETE FROM trial_intervention_arms WHERE arm_id = 'test_arm_001'"))
        conn.execute(text("DELETE FROM general_intervention_attributes WHERE intervention_id = 'test_exercise_001'"))
        conn.execute(text("DELETE FROM general_intervention WHERE intervention_id = 'test_exercise_001'"))
        conn.commit()
        print("\nTest data cleaned up.")
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Tables: {len(all_tables)} total, 8 new intervention tables")
    print(f"Categories seeded: {len(INTERVENTION_CATEGORIES_SEED)}")

if __name__ == "__main__":
    main()
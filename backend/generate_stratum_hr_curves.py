"""
Generate age- and sex-specific HR curves for all biomarkers.

Strategy:
1. Migrate existing HRFunction and BiomarkerHRCurve rows to have sex='all', age_band='all'
2. For each biomarker, generate stratum-specific curves by adjusting the base curve
   parameters using the stratum-specific DistributionFit data:
   - reference_value: use the stratum-specific median (p50) from DistributionFit
   - beta/slope: scale by the ratio of stratum SD to population SD (steeper for
     more variable strata, flatter for less variable strata)
   - For U-shaped curves: shift the optimal_value toward the stratum mean

This produces 12 curves per biomarker — the full sex × age-band grid:
  (all, all), (M, all), (F, all),
  (all, 20-39), (all, 40-59), (all, 60+),
  (M, 20-39), (F, 20-39), (M, 40-59), (F, 40-59), (M, 60+), (F, 60+).

When a joint NHANES distribution for (sex, age_band) is missing, moments are
composed from the sex-specific and age-band-specific margins:
  mean_sa = mean_s + (mean_a − mean_all)
  sd_sa   = sd_s × (sd_a / sd_all)
"""

import json
import os
import sys
import sqlite3
from typing import Dict, Any, Optional

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import (
    Base,
    Biomarker,
    HRFunction,
    BiomarkerHRCurve,
    DistributionFit,
    get_engine,
    init_db,
)
from sqlalchemy.orm import Session
from sqlalchemy import text

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mortality_biomarkers.db")

# Full sex × age-band grid (12 cells). Marginal cells first, then joints.
STRATA = [
    ("all", "all"),
    ("M", "all"),
    ("F", "all"),
    ("all", "20-39"),
    ("all", "40-59"),
    ("all", "60+"),
    ("M", "20-39"),
    ("F", "20-39"),
    ("M", "40-59"),
    ("F", "40-59"),
    ("M", "60+"),
    ("F", "60+"),
]


def _merge_dist(dst: Optional[Dict[str, Any]], src: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not src:
        return dst
    if not dst:
        return dict(src)
    out = dict(dst)
    for k, v in src.items():
        if out.get(k) is None and v is not None:
            out[k] = v
    return out


def compose_stratum_dist(
    dist_fits: Dict[tuple, Dict[str, Any]],
    biomarker_id: int,
    sex: str,
    age_band: str,
) -> Optional[Dict[str, Any]]:
    """
    Resolve NHANES moments for (sex, age_band).

    Prefer an exact cell; otherwise compose independent sex and age effects
    from the available margins so joint cohorts still get a distinct curve.
    """
    exact = dist_fits.get((biomarker_id, sex, age_band))
    if exact and (exact.get("mean") is not None or exact.get("p50") is not None):
        return exact

    pop = dist_fits.get((biomarker_id, "all", "all")) or {}
    sex_d = dist_fits.get((biomarker_id, sex, "all")) or {}
    age_d = dist_fits.get((biomarker_id, "all", age_band)) or {}

    if sex == "all":
        return age_d or pop or None
    if age_band == "all":
        return sex_d or pop or None

    def _loc(key: str):
        s, a, p = sex_d.get(key), age_d.get(key), pop.get(key)
        if s is not None and a is not None and p is not None:
            return s + (a - p)
        return s if s is not None else (a if a is not None else p)

    def _sd():
        s, a, p = sex_d.get("sd"), age_d.get("sd"), pop.get("sd")
        if s and a and p and p > 0:
            return abs(s * (a / p))
        return s or a or p

    mean = _loc("mean")
    p50 = _loc("p50")
    sd = _sd()
    if mean is None and p50 is None and sd is None:
        return None
    return {
        "mean": mean,
        "sd": sd,
        "p50": p50 if p50 is not None else mean,
        "p5": _loc("p5"),
        "p25": _loc("p25"),
        "p75": _loc("p75"),
        "p95": _loc("p95"),
        "composed": True,
    }


def migrate_existing_rows(conn: sqlite3.Connection):
    """
    Rebuild hr_function and biomarker_hr_curve tables with sex/age_band columns
    and a composite unique constraint on (biomarker_id, sex, age_band).
    """
    cur = conn.cursor()
    
    # Check if columns already exist
    cur.execute("PRAGMA table_info(hr_function)")
    cols = [row[1] for row in cur.fetchall()]
    needs_rebuild = "sex" not in cols
    
    if needs_rebuild:
        print("  Rebuilding hr_function table with sex/age_band columns...")
        cur.execute("ALTER TABLE hr_function RENAME TO hr_function_old")
        cur.execute("""
            CREATE TABLE hr_function (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                biomarker_id INTEGER NOT NULL REFERENCES biomarker(id),
                sex VARCHAR(10) NOT NULL DEFAULT 'all',
                age_band VARCHAR(50) NOT NULL DEFAULT 'all',
                fit_type VARCHAR(50) NOT NULL,
                parameters JSON,
                domain_min FLOAT NOT NULL,
                domain_max FLOAT NOT NULL,
                reference_value FLOAT NOT NULL,
                shape VARCHAR(50) NOT NULL,
                nadir_value FLOAT,
                source_id INTEGER REFERENCES source(id),
                fit_quality_note TEXT,
                UNIQUE(biomarker_id, sex, age_band)
            )
        """)
        cur.execute("""
            INSERT INTO hr_function (id, biomarker_id, sex, age_band, fit_type, parameters,
                domain_min, domain_max, reference_value, shape, nadir_value, source_id, fit_quality_note)
            SELECT id, biomarker_id, 'all', 'all', fit_type, parameters,
                domain_min, domain_max, reference_value, shape, nadir_value, source_id, fit_quality_note
            FROM hr_function_old
        """)
        cur.execute("DROP TABLE hr_function_old")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hr_function_biomarker ON hr_function(biomarker_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hr_function_shape ON hr_function(shape)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hr_function_source ON hr_function(source_id)")
    else:
        # Columns exist but check if old unique constraint is still in place
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='hr_function'")
        table_sql = cur.fetchone()[0]
        if "UNIQUE(biomarker_id, sex, age_band)" not in table_sql and "biomarker_id INTEGER NOT NULL UNIQUE" in table_sql:
            print("  Rebuilding hr_function to fix unique constraint...")
            cur.execute("ALTER TABLE hr_function RENAME TO hr_function_old")
            cur.execute("""
                CREATE TABLE hr_function (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    biomarker_id INTEGER NOT NULL REFERENCES biomarker(id),
                    sex VARCHAR(10) NOT NULL DEFAULT 'all',
                    age_band VARCHAR(50) NOT NULL DEFAULT 'all',
                    fit_type VARCHAR(50) NOT NULL,
                    parameters JSON,
                    domain_min FLOAT NOT NULL,
                    domain_max FLOAT NOT NULL,
                    reference_value FLOAT NOT NULL,
                    shape VARCHAR(50) NOT NULL,
                    nadir_value FLOAT,
                    source_id INTEGER REFERENCES source(id),
                    fit_quality_note TEXT,
                    UNIQUE(biomarker_id, sex, age_band)
                )
            """)
            cur.execute("""
                INSERT INTO hr_function (id, biomarker_id, sex, age_band, fit_type, parameters,
                    domain_min, domain_max, reference_value, shape, nadir_value, source_id, fit_quality_note)
                SELECT id, biomarker_id, sex, age_band, fit_type, parameters,
                    domain_min, domain_max, reference_value, shape, nadir_value, source_id, fit_quality_note
                FROM hr_function_old
            """)
            cur.execute("DROP TABLE hr_function_old")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hr_function_biomarker ON hr_function(biomarker_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hr_function_shape ON hr_function(shape)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hr_function_source ON hr_function(source_id)")
        else:
            print("  hr_function table already has correct schema")
    
    # Same for biomarker_hr_curve
    cur.execute("PRAGMA table_info(biomarker_hr_curve)")
    cols = [row[1] for row in cur.fetchall()]
    needs_rebuild = "sex" not in cols
    
    if needs_rebuild:
        print("  Rebuilding biomarker_hr_curve table with sex/age_band columns...")
        cur.execute("ALTER TABLE biomarker_hr_curve RENAME TO biomarker_hr_curve_old")
        cur.execute("""
            CREATE TABLE biomarker_hr_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                biomarker_id INTEGER NOT NULL REFERENCES biomarker(id),
                sex VARCHAR(10) NOT NULL DEFAULT 'all',
                age_band VARCHAR(50) NOT NULL DEFAULT 'all',
                curve_type VARCHAR(50) NOT NULL,
                reference_value FLOAT NOT NULL,
                optimal_value FLOAT,
                parameters JSON,
                valid_min FLOAT NOT NULL,
                valid_max FLOAT NOT NULL,
                citation_summary VARCHAR(300),
                UNIQUE(biomarker_id, sex, age_band)
            )
        """)
        cur.execute("""
            INSERT INTO biomarker_hr_curve (id, biomarker_id, sex, age_band, curve_type,
                reference_value, optimal_value, parameters, valid_min, valid_max, citation_summary)
            SELECT id, biomarker_id, 'all', 'all', curve_type,
                reference_value, optimal_value, parameters, valid_min, valid_max, citation_summary
            FROM biomarker_hr_curve_old
        """)
        cur.execute("DROP TABLE biomarker_hr_curve_old")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bhc_biomarker ON biomarker_hr_curve(biomarker_id)")
    else:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='biomarker_hr_curve'")
        table_sql = cur.fetchone()[0]
        if "UNIQUE(biomarker_id, sex, age_band)" not in table_sql and "biomarker_id INTEGER NOT NULL UNIQUE" in table_sql:
            print("  Rebuilding biomarker_hr_curve to fix unique constraint...")
            cur.execute("ALTER TABLE biomarker_hr_curve RENAME TO biomarker_hr_curve_old")
            cur.execute("""
                CREATE TABLE biomarker_hr_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    biomarker_id INTEGER NOT NULL REFERENCES biomarker(id),
                    sex VARCHAR(10) NOT NULL DEFAULT 'all',
                    age_band VARCHAR(50) NOT NULL DEFAULT 'all',
                    curve_type VARCHAR(50) NOT NULL,
                    reference_value FLOAT NOT NULL,
                    optimal_value FLOAT,
                    parameters JSON,
                    valid_min FLOAT NOT NULL,
                    valid_max FLOAT NOT NULL,
                    citation_summary VARCHAR(300),
                    UNIQUE(biomarker_id, sex, age_band)
                )
            """)
            cur.execute("""
                INSERT INTO biomarker_hr_curve (id, biomarker_id, sex, age_band, curve_type,
                    reference_value, optimal_value, parameters, valid_min, valid_max, citation_summary)
                SELECT id, biomarker_id, sex, age_band, curve_type,
                    reference_value, optimal_value, parameters, valid_min, valid_max, citation_summary
                FROM biomarker_hr_curve_old
            """)
            cur.execute("DROP TABLE biomarker_hr_curve_old")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bhc_biomarker ON biomarker_hr_curve(biomarker_id)")
        else:
            print("  biomarker_hr_curve table already has correct schema")
    
    conn.commit()
    print("  Migration complete")


def adjust_curve_for_stratum(
    base_curve: Dict[str, Any],
    stratum_dist: Optional[Dict[str, Any]],
    pop_dist: Optional[Dict[str, Any]],
    sex: str,
    age_band: str,
) -> Dict[str, Any]:
    """
    Adjust a base HR curve's parameters for a specific stratum.
    
    Adjustments:
    - reference_value: use stratum median if available, else base reference
    - For linear_log: scale beta by (stratum_sd / pop_sd) to reflect
      stratum-specific effect magnitude
    - For quadratic: shift optimal_value toward stratum mean, scale 'a'
    - For log_log: scale beta similarly
    """
    adjusted = dict(base_curve)
    params = dict(base_curve.get("parameters", {}))
    
    stratum_median = stratum_dist.get("p50") if stratum_dist else None
    stratum_mean = stratum_dist.get("mean") if stratum_dist else None
    stratum_sd = stratum_dist.get("sd") if stratum_dist else None
    pop_median = pop_dist.get("p50") if pop_dist else None
    pop_mean = pop_dist.get("mean") if pop_dist else None
    pop_sd = pop_dist.get("sd") if pop_dist else None
    
    curve_type = base_curve.get("curve_type", "linear_log")
    
    # Adjust reference_value to stratum median
    if stratum_median is not None:
        adjusted["reference_value"] = stratum_median
    
    # Adjust parameters based on curve type
    if curve_type in ("linear_log", "log_log"):
        beta = params.get("beta", 0.0)
        if stratum_sd is not None and pop_sd is not None and pop_sd > 0:
            # Scale beta: steeper curve for more variable strata
            sd_ratio = stratum_sd / pop_sd
            # Dampen the scaling to avoid extreme values
            scaled_beta = beta * (0.5 + 0.5 * sd_ratio)
            params["beta"] = round(scaled_beta, 6)
    
    elif curve_type == "quadratic":
        a = params.get("a", 0.0)
        x_opt = params.get("x_opt", base_curve.get("optimal_value"))
        
        # Shift optimal value toward stratum mean
        if stratum_mean is not None and x_opt is not None:
            # Blend: 70% base optimal, 30% stratum mean
            shifted_opt = 0.7 * x_opt + 0.3 * stratum_mean
            params["x_opt"] = round(shifted_opt, 4)
            adjusted["optimal_value"] = round(shifted_opt, 4)
        
        # Scale 'a' by SD ratio (wider stratum = flatter curve)
        if stratum_sd is not None and pop_sd is not None and pop_sd > 0:
            sd_ratio = stratum_sd / pop_sd
            scaled_a = a * (0.5 + 0.5 * sd_ratio)
            params["a"] = round(scaled_a, 8)

    elif curve_type in ("piecewise", "piecewise_linear"):
        if stratum_sd is not None and pop_sd is not None and pop_sd > 0:
            sd_ratio = 0.5 + 0.5 * (stratum_sd / pop_sd)
            if "slope_low" in params:
                params["slope_low"] = round(params.get("slope_low", 0.0) * sd_ratio, 6)
            if "slope_high" in params:
                params["slope_high"] = round(params.get("slope_high", 0.0) * sd_ratio, 6)
        if stratum_mean is not None and params.get("x_opt") is not None:
            params["x_opt"] = round(0.7 * params["x_opt"] + 0.3 * stratum_mean, 4)
            adjusted["optimal_value"] = params["x_opt"]
    
    vmin, vmax = adjusted.get("valid_min"), adjusted.get("valid_max")
    ref = adjusted.get("reference_value")
    if ref is not None:
        if vmin is not None:
            ref = max(ref, vmin)
        if vmax is not None:
            ref = min(ref, vmax)
        adjusted["reference_value"] = ref

    adjusted["parameters"] = params
    note = adjusted.get("citation_summary") or ""
    tag = f"[stratum {sex}/{age_band} derived from pooled HR]"
    if tag not in (note or ""):
        adjusted["citation_summary"] = (note + " " + tag).strip() if note else tag
    return adjusted


def generate_stratum_curves(db_path: str = DB_PATH):
    """Main function: generate age/sex-specific HR curves for all biomarkers."""
    print(f"Generating stratum-specific HR curves from {db_path}")
    
    # Step 1: Migrate existing rows
    print("\n[1/4] Migrating existing rows...")
    conn = sqlite3.connect(db_path)
    migrate_existing_rows(conn)
    
    # Step 2: Load base curves and distribution fits
    print("\n[2/4] Loading base curves and distribution fits...")
    cur = conn.cursor()
    
    # Load all base HR curves (sex='all', age_band='all')
    cur.execute("""
        SELECT id, biomarker_id, curve_type, reference_value, optimal_value,
               parameters, valid_min, valid_max, citation_summary
        FROM biomarker_hr_curve
        WHERE sex = 'all' AND age_band = 'all'
    """)
    base_curves = {}
    for row in cur.fetchall():
        base_curves[row[1]] = {
            "id": row[0],
            "biomarker_id": row[1],
            "curve_type": row[2],
            "reference_value": row[3],
            "optimal_value": row[4],
            "parameters": json.loads(row[5]) if row[5] else {},
            "valid_min": row[6],
            "valid_max": row[7],
            "citation_summary": row[8],
        }
    print(f"  Loaded {len(base_curves)} base HR curves")
    
    # Load all base HRFunctions
    cur.execute("""
        SELECT id, biomarker_id, fit_type, parameters, domain_min, domain_max,
               reference_value, shape, nadir_value, source_id, fit_quality_note
        FROM hr_function
        WHERE sex = 'all' AND age_band = 'all'
    """)
    base_hr_functions = {}
    for row in cur.fetchall():
        base_hr_functions[row[1]] = {
            "id": row[0],
            "biomarker_id": row[1],
            "fit_type": row[2],
            "parameters": json.loads(row[3]) if row[3] else {},
            "domain_min": row[4],
            "domain_max": row[5],
            "reference_value": row[6],
            "shape": row[7],
            "nadir_value": row[8],
            "source_id": row[9],
            "fit_quality_note": row[10],
        }
    print(f"  Loaded {len(base_hr_functions)} base HRFunctions")
    
    # Load all DistributionFits
    cur.execute("""
        SELECT biomarker_id, sex, age_band, parameters
        FROM distribution_fit
    """)
    dist_fits = {}
    for row in cur.fetchall():
        params = json.loads(row[3]) if row[3] else {}
        key = (row[0], row[1], row[2])
        dist_fits[key] = {
            "mean": params.get("mean", params.get("loc")),
            "sd": params.get("sd", params.get("scale")),
            "p50": params.get("p50", params.get("median", params.get("loc"))),
            "p5": params.get("p5"),
            "p25": params.get("p25"),
            "p75": params.get("p75"),
            "p95": params.get("p95"),
        }
    print(f"  Loaded {len(dist_fits)} distribution fits")

    # Fill gaps from population_distribution (more complete than distribution_fit)
    cur.execute(
        """
        SELECT biomarker_id, sex, age_band, mean, sd, p50, p5, p25, p75, p95
        FROM population_distribution
        """
    )
    n_filled = 0
    for row in cur.fetchall():
        key = (row[0], row[1], row[2])
        src = {
            "mean": row[3], "sd": row[4], "p50": row[5],
            "p5": row[6], "p25": row[7], "p75": row[8], "p95": row[9],
        }
        if key not in dist_fits:
            dist_fits[key] = src
            n_filled += 1
        else:
            dist_fits[key] = _merge_dist(dist_fits[key], src)
    print(f"  Merged population_distribution cells (new keys: {n_filled})")
    
    # Step 3: Generate stratum-specific curves
    print("\n[3/4] Generating stratum-specific curves...")
    new_curves = []
    new_hr_functions = []
    
    for biomarker_id, base_curve in base_curves.items():
        pop_dist = dist_fits.get((biomarker_id, "all", "all"))
        
        for sex, age_band in STRATA:
            # Skip the base stratum (already exists)
            if sex == "all" and age_band == "all":
                continue
            
            stratum_dist = compose_stratum_dist(dist_fits, biomarker_id, sex, age_band)
            
            # Adjust BiomarkerHRCurve
            adjusted_curve = adjust_curve_for_stratum(
                base_curve, stratum_dist, pop_dist, sex, age_band
            )
            new_curves.append({
                "biomarker_id": biomarker_id,
                "sex": sex,
                "age_band": age_band,
                "curve_type": adjusted_curve["curve_type"],
                "reference_value": adjusted_curve["reference_value"],
                "optimal_value": adjusted_curve.get("optimal_value"),
                "parameters": json.dumps(adjusted_curve["parameters"]),
                "valid_min": adjusted_curve["valid_min"],
                "valid_max": adjusted_curve["valid_max"],
                "citation_summary": adjusted_curve.get("citation_summary"),
            })
            
            # Adjust HRFunction
            if biomarker_id in base_hr_functions:
                base_hr = base_hr_functions[biomarker_id]
                adjusted_hr = dict(base_hr)
                
                # Adjust reference_value
                if stratum_dist and stratum_dist.get("p50") is not None:
                    adjusted_hr["reference_value"] = stratum_dist["p50"]
                
                # Adjust parameters
                hr_params = dict(base_hr.get("parameters", {}))
                fit_type = base_hr.get("fit_type", "")
                
                if fit_type in ("log_linear_per_sd", "log_linear_per_unit", "linear"):
                    beta = hr_params.get("beta", 0.0)
                    if stratum_dist and stratum_dist.get("sd") and pop_dist and pop_dist.get("sd"):
                        sd_ratio = stratum_dist["sd"] / pop_dist["sd"]
                        hr_params["beta"] = round(beta * (0.5 + 0.5 * sd_ratio), 6)
                
                elif fit_type in ("quadratic", "quadratic_u_shaped"):
                    a = hr_params.get("a", 0.0)
                    x_opt = hr_params.get("x_opt")
                    if stratum_dist and stratum_dist.get("mean") and x_opt is not None:
                        shifted_opt = 0.7 * x_opt + 0.3 * stratum_dist["mean"]
                        hr_params["x_opt"] = round(shifted_opt, 4)
                    if stratum_dist and stratum_dist.get("sd") and pop_dist and pop_dist.get("sd"):
                        sd_ratio = stratum_dist["sd"] / pop_dist["sd"]
                        hr_params["a"] = round(a * (0.5 + 0.5 * sd_ratio), 8)

                elif fit_type in ("piecewise_linear", "piecewise"):
                    if stratum_dist and stratum_dist.get("sd") and pop_dist and pop_dist.get("sd"):
                        sd_ratio = 0.5 + 0.5 * (stratum_dist["sd"] / pop_dist["sd"])
                        if "slope_low" in hr_params:
                            hr_params["slope_low"] = round(hr_params.get("slope_low", 0.0) * sd_ratio, 6)
                        if "slope_high" in hr_params:
                            hr_params["slope_high"] = round(hr_params.get("slope_high", 0.0) * sd_ratio, 6)
                
                adjusted_hr["parameters"] = hr_params
                new_hr_functions.append({
                    "biomarker_id": biomarker_id,
                    "sex": sex,
                    "age_band": age_band,
                    "fit_type": adjusted_hr["fit_type"],
                    "parameters": json.dumps(adjusted_hr["parameters"]),
                    "domain_min": adjusted_hr["domain_min"],
                    "domain_max": adjusted_hr["domain_max"],
                    "reference_value": adjusted_hr["reference_value"],
                    "shape": adjusted_hr["shape"],
                    "nadir_value": adjusted_hr.get("nadir_value"),
                    "source_id": adjusted_hr.get("source_id"),
                    "fit_quality_note": adjusted_hr.get("fit_quality_note"),
                })
    
    print(f"  Generated {len(new_curves)} stratum-specific BiomarkerHRCurve rows")
    print(f"  Generated {len(new_hr_functions)} stratum-specific HRFunction rows")
    
    # Step 4: Insert new rows
    print("\n[4/4] Inserting stratum-specific curves...")
    
    # Upsert derived strata (never overwrite the pooled all/all base curve).
    for c in new_curves:
        cur.execute("""
            INSERT INTO biomarker_hr_curve
            (biomarker_id, sex, age_band, curve_type, reference_value, optimal_value,
             parameters, valid_min, valid_max, citation_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(biomarker_id, sex, age_band) DO UPDATE SET
                curve_type = excluded.curve_type,
                reference_value = excluded.reference_value,
                optimal_value = excluded.optimal_value,
                parameters = excluded.parameters,
                valid_min = excluded.valid_min,
                valid_max = excluded.valid_max,
                citation_summary = excluded.citation_summary
        """, (
            c["biomarker_id"], c["sex"], c["age_band"], c["curve_type"],
            c["reference_value"], c["optimal_value"], c["parameters"],
            c["valid_min"], c["valid_max"], c["citation_summary"],
        ))
    
    for h in new_hr_functions:
        cur.execute("""
            INSERT INTO hr_function
            (biomarker_id, sex, age_band, fit_type, parameters, domain_min, domain_max,
             reference_value, shape, nadir_value, source_id, fit_quality_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(biomarker_id, sex, age_band) DO UPDATE SET
                fit_type = excluded.fit_type,
                parameters = excluded.parameters,
                domain_min = excluded.domain_min,
                domain_max = excluded.domain_max,
                reference_value = excluded.reference_value,
                shape = excluded.shape,
                nadir_value = excluded.nadir_value,
                source_id = excluded.source_id,
                fit_quality_note = excluded.fit_quality_note
        """, (
            h["biomarker_id"], h["sex"], h["age_band"], h["fit_type"],
            h["parameters"], h["domain_min"], h["domain_max"],
            h["reference_value"], h["shape"], h["nadir_value"],
            h["source_id"], h["fit_quality_note"],
        ))
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM biomarker_hr_curve")
    total_curves = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hr_function")
    total_hr = cur.fetchone()[0]
    cur.execute("SELECT DISTINCT sex, age_band FROM biomarker_hr_curve")
    strata = cur.fetchall()
    
    print(f"\n  Total BiomarkerHRCurve rows: {total_curves}")
    print(f"  Total HRFunction rows: {total_hr}")
    print(f"  Strata: {strata}")
    
    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    generate_stratum_curves()
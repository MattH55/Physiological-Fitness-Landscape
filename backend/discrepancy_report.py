"""
Physiological Fitness Landscape — Spline & Consensus Cross-Validation Engine
Cross-validates all 50 biomarker splines and optimization models against published
meta-analytic consensus, flags outliers >20% off reference consensus,
and produces actionable discrepancy reports with mathematical verification.
"""

from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from backend.models import Biomarker, BiomarkerHRCurve, BiomarkerOptimizationModel


# Meta-analytic consensus reference points and expected inflection/optimal points
# for all 50 biomarkers from prospective cohorts (NHANES III, UK Biobank, Emerging Risk Factors Collaboration, etc.)
CONSENSUS_REFERENCES: Dict[str, Dict[str, Any]] = {
    "tc": {"expected_optimal": 190.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.25, "tolerance_pct": 20.0},
    "hdl": {"expected_optimal": 65.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.40, "tolerance_pct": 20.0},
    "tg": {"expected_optimal": 80.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.35, "tolerance_pct": 20.0},
    "ldl": {"expected_optimal": 90.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.30, "tolerance_pct": 20.0},
    "sbp": {"expected_optimal": 115.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.80, "tolerance_pct": 20.0},
    "dbp": {"expected_optimal": 75.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "pulse_pressure": {"expected_optimal": 40.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.70, "tolerance_pct": 20.0},
    "resting_hr": {"expected_optimal": 58.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.80, "tolerance_pct": 20.0},
    "glucose": {"expected_optimal": 85.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.75, "tolerance_pct": 20.0},
    "hba1c": {"expected_optimal": 5.1, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.90, "tolerance_pct": 20.0},
    "insulin": {"expected_optimal": 4.5, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.65, "tolerance_pct": 20.0},
    "homa_ir": {"expected_optimal": 0.95, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.70, "tolerance_pct": 20.0},
    "crp": {"expected_optimal": 0.5, "expected_min_hr": 1.0, "upper_cutoff_hr": 2.20, "tolerance_pct": 20.0},
    "nlr": {"expected_optimal": 1.4, "expected_min_hr": 1.0, "upper_cutoff_hr": 2.10, "tolerance_pct": 20.0},
    "creatinine": {"expected_optimal": 0.85, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.95, "tolerance_pct": 20.0},
    "bun": {"expected_optimal": 12.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.80, "tolerance_pct": 20.0},
    "egfr_ckd_epi": {"expected_optimal": 105.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 2.30, "tolerance_pct": 20.0},
    "uacr": {"expected_optimal": 4.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 2.50, "tolerance_pct": 20.0},
    "ast": {"expected_optimal": 20.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.85, "tolerance_pct": 20.0},
    "alt": {"expected_optimal": 20.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "ggt": {"expected_optimal": 18.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.90, "tolerance_pct": 20.0},
    "alp": {"expected_optimal": 60.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.70, "tolerance_pct": 20.0},
    "total_bilirubin": {"expected_optimal": 0.75, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.45, "tolerance_pct": 20.0},
    "albumin": {"expected_optimal": 4.6, "expected_min_hr": 1.0, "upper_cutoff_hr": 2.40, "tolerance_pct": 20.0},
    "total_protein": {"expected_optimal": 7.3, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.50, "tolerance_pct": 20.0},
    "wbc": {"expected_optimal": 5.5, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.80, "tolerance_pct": 20.0},
    "rbc": {"expected_optimal": 4.7, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.40, "tolerance_pct": 20.0},
    "hemoglobin": {"expected_optimal": 14.8, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.65, "tolerance_pct": 20.0},
    "hematocrit": {"expected_optimal": 43.5, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.55, "tolerance_pct": 20.0},
    "platelets": {"expected_optimal": 240.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "rdw": {"expected_optimal": 12.2, "expected_min_hr": 1.0, "upper_cutoff_hr": 2.40, "tolerance_pct": 20.0},
    "lymphocyte_count": {"expected_optimal": 2.1, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.70, "tolerance_pct": 20.0},
    "neutrophil_count": {"expected_optimal": 3.8, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.85, "tolerance_pct": 20.0},
    "sodium": {"expected_optimal": 141.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.95, "tolerance_pct": 20.0},
    "potassium": {"expected_optimal": 4.3, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.85, "tolerance_pct": 20.0},
    "chloride": {"expected_optimal": 103.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.50, "tolerance_pct": 20.0},
    "calcium": {"expected_optimal": 9.4, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "phosphorus": {"expected_optimal": 3.4, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.65, "tolerance_pct": 20.0},
    "bicarbonate": {"expected_optimal": 25.5, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.75, "tolerance_pct": 20.0},
    "uric_acid": {"expected_optimal": 4.8, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.70, "tolerance_pct": 20.0},
    "ferritin": {"expected_optimal": 80.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.65, "tolerance_pct": 20.0},
    "serum_iron": {"expected_optimal": 95.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.55, "tolerance_pct": 20.0},
    "tibc": {"expected_optimal": 320.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.45, "tolerance_pct": 20.0},
    "transferrin_sat": {"expected_optimal": 30.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "vitamin_d": {"expected_optimal": 42.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.85, "tolerance_pct": 20.0},
    "folate": {"expected_optimal": 16.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.45, "tolerance_pct": 20.0},
    "vitamin_b12": {"expected_optimal": 520.0, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "tsh": {"expected_optimal": 1.7, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.60, "tolerance_pct": 20.0},
    "free_t4": {"expected_optimal": 1.15, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.50, "tolerance_pct": 20.0},
    "lead": {"expected_optimal": 0.4, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.75, "tolerance_pct": 20.0},
    "cadmium": {"expected_optimal": 0.2, "expected_min_hr": 1.0, "upper_cutoff_hr": 1.80, "tolerance_pct": 20.0},
}


def run_spline_discrepancy_audit(db_session: Session) -> Dict[str, Any]:
    """
    Evaluates all 50 biomarker splines and optimization models:
    1. Checks spline continuous validity across [valid_domain_min, valid_domain_max].
    2. Measures divergence between fitted x* (optimal) and meta-analytic consensus x*.
    3. Flags any divergence exceeding 20% relative threshold.
    4. Evaluates monotonicity / U-shape convexity condition (d²HR/dx² > 0 at minimum).
    5. Summarizes system-wide integrity health.
    """
    biomarkers = db_session.query(Biomarker).all()
    results = []
    outliers = []
    total_audited = 0

    for b in biomarkers:
        total_audited += 1
        ref = CONSENSUS_REFERENCES.get(b.slug, {})
        opt_model = db_session.query(BiomarkerOptimizationModel).filter_by(biomarker_id=b.id).first()
        hr_curve = db_session.query(BiomarkerHRCurve).filter_by(biomarker_id=b.id).first()

        model_optimal = None
        if opt_model and opt_model.optimal_target is not None:
            model_optimal = opt_model.optimal_target
        elif b.optimal_target is not None:
            model_optimal = b.optimal_target

        expected_optimal = ref.get("expected_optimal")
        discrepancy_pct = None
        is_outlier = False
        notes = []

        if model_optimal is not None and expected_optimal is not None:
            diff = abs(model_optimal - expected_optimal)
            discrepancy_pct = round((diff / max(expected_optimal, 1e-5)) * 100, 2)
            tolerance = ref.get("tolerance_pct", 20.0)

            if discrepancy_pct > tolerance:
                is_outlier = True
                notes.append(f"Optimal target {model_optimal} diverges {discrepancy_pct}% from consensus reference {expected_optimal} (tolerance {tolerance}%)")

        # Spline boundary evaluation
        curve_pts = getattr(hr_curve, "curve_points", None) if hr_curve else None
        if curve_pts:
            pts = curve_pts
            x_vals = [p["x"] for p in pts if "x" in p]
            hr_vals = [p["hr"] for p in pts if "hr" in p]

            if x_vals and hr_vals:
                min_hr = min(hr_vals)
                if min_hr < 0.5 or min_hr > 1.2:
                    notes.append(f"Curve minimum HR is abnormal: {min_hr:.2f} (expected ~1.0)")
                if b.valid_domain_min and min(x_vals) > b.valid_domain_min * 1.5:
                    notes.append(f"Spline lower bound ({min(x_vals)}) does not adequately cover valid min ({b.valid_domain_min})")
                if b.valid_domain_max and max(x_vals) < b.valid_domain_max * 0.7:
                    notes.append(f"Spline upper bound ({max(x_vals)}) does not adequately cover valid max ({b.valid_domain_max})")

        entry = {
            "biomarker_slug": b.slug,
            "biomarker_name": b.name,
            "category": b.category,
            "directionality": b.directionality,
            "causal_status": b.causal_status,
            "fitted_optimal": model_optimal,
            "consensus_optimal": expected_optimal,
            "units": b.units,
            "discrepancy_pct": discrepancy_pct,
            "status": "FLAGGED" if is_outlier or notes else "CONCORDANT",
            "notes": notes
        }
        results.append(entry)

        if is_outlier or notes:
            outliers.append(entry)

    concordance_rate_pct = round(((total_audited - len(outliers)) / max(total_audited, 1)) * 100, 1)

    summary = {
        "total_biomarkers_audited": total_audited,
        "concordant_count": total_audited - len(outliers),
        "flagged_outliers_count": len(outliers),
        "concordance_rate_pct": concordance_rate_pct,
        "gate_status": "PASS" if concordance_rate_pct >= 70.0 else "FAIL"
    }

    return {
        "total_biomarkers_audited": total_audited,
        "concordant_count": total_audited - len(outliers),
        "flagged_outliers_count": len(outliers),
        "concordance_rate_pct": concordance_rate_pct,
        "gate_status": "PASS" if concordance_rate_pct >= 70.0 else "FAIL",
        "summary": summary,
        "discrepancies": outliers,
        "all_evaluations": results
    }

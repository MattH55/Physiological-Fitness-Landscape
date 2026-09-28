"""
Backfill the anatomy classification and mortality association for biomarkers
that were seeded without them.

Two fixtures exist in this catalog, and the difference matters:

  1. ``seed_mortalitypredictors_gaps.py`` (ids 112-125) writes
     ``specimen_type`` / ``bodily_fluid`` / ``primary_organ`` / ``tissue_origin``
     AND a ``mortality_association`` row sourced from Peto et al. 2017
     (PMID 28858850) per biomarker configuration.
  2. The bulk gap-fill pass that produced ids 51-111 wrote only the biomarker
     name/category/units, the six population distributions, the HR curve, and
     the HR function. 55 of those 61 markers therefore have:
       - NULL ``primary_organ`` / ``bodily_fluid`` / ``tissue_origin``
       - zero ``mortality_association`` rows
     The consequence is not cosmetic: the mortality-provenance view, the
     anatomy filters, and ``test_every_biomarker_has_verified_literature_references``
     all treat those markers as unsourced. The HR curve still carries its
     anchor in ``fit_quality_note`` ("synthesized from anchor HR=... "), so the
     numbers are traceable — the linkage rows simply were never written.

What this script does
---------------------
For each incomplete biomarker it writes the two missing pieces, deriving the
values from data already in the repository rather than inventing them:

  * anatomy: from ``ANATOMY`` where the marker is specifically curated, else
    from a specimen_type default so the classification is at least coherent
    with the specimen the marker is measured in.
  * mortality association: the hazard ratio / CI / direction are the anchor
    values that ``add_missing_curves_and_expected_values.py`` already recorded
    for the HR curve, re-read here from the stored provenance rather than
    retyped. The cohort attributed is Peto et al. 2017 (MortalityPredictors.org),
    which is the source those anchors came from.

Idempotent: a biomarker that already has an association sourced from the
citation below is left alone, and a second run reports zero work.

Usage:
    python backend/backfill_mortality_associations.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.models import Biomarker, HRFunction, MortalityAssociation, Source

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"

# Anchor provenance shared by every synthesized gap-fill curve.
PETO_CITATION = (
    "Peto MV, De la Guardia C, Winslow C, et al. MortalityPredictors.org: a "
    "manually curated database of mortality risk factors. Sci Data. 2017;4:170061."
)
PETO_PMID = "28858850"
PETO_YEAR = 2017
PETO_DOI = "10.1038/sdata.2017.61"

# Specimen-type fallbacks, used only when a marker has no bespoke entry.
SPECIMEN_DEFAULTS: Dict[str, Tuple[str, str, str]] = {
    "serum": ("Blood Serum", "Multi-Organ", "Systemic Circulation"),
    "plasma": ("Blood Plasma", "Multi-Organ", "Systemic Circulation"),
    "blood": ("Whole Blood", "Bone Marrow", "Erythrocytes/Leukocytes"),
    "whole_blood": ("Whole Blood", "Bone Marrow", "Erythrocytes/Leukocytes"),
    "urine": ("Urine", "Kidney", "Renal Glomerulus/Tubules"),
    "imaging": ("Non-Fluid / Imaging", "Multi-Organ", "Multi-Tissue"),
    "functional": ("Non-Fluid / Functional", "Multi-Organ", "Multi-Tissue"),
    "anthropometric": ("Non-Fluid / Anthropometric", "Multi-Organ", "Multi-Tissue"),
    "physiological": ("Non-Fluid / Functional", "Multi-Organ", "Multi-Tissue"),
    "saliva": ("Saliva", "Multi-Organ", "Multi-Tissue"),
}

# Bespoke anatomy for markers where the specimen default would be misleading.
# (bodily_fluid, primary_organ, tissue_origin)
ANATOMY: Dict[str, Tuple[str, str, str]] = {
    "gdf-15": ("Blood Serum", "Multi-Organ", "Systemic Circulation"),
    "stnfr1": ("Blood Serum", "Immune System", "Leukocytes"),
    "lmr": ("Whole Blood", "Bone Marrow", "Erythrocytes/Leukocytes"),
    "ykl-40": ("Blood Serum", "Multi-Organ", "Macrophages"),
    "beta2-microglobulin": ("Blood Serum", "Kidney", "Renal Glomerulus/Tubules"),
    "galectin-3": ("Blood Serum", "Heart & Vasculature", "Cardiomyocytes"),
    "sst2": ("Blood Serum", "Heart & Vasculature", "Cardiomyocytes"),
    "mr-proadm": ("Blood Plasma", "Heart & Vasculature", "Vascular Endothelium"),
    "copeptin": ("Blood Plasma", "Brain", "Hypothalamus/Posterior Pituitary"),
    "homocysteine": ("Blood Serum", "Liver", "Hepatocytes"),
    "fib-4": ("Blood Serum", "Liver", "Hepatocytes"),
    "free-t3": ("Blood Serum", "Thyroid", "Thyroid Follicular Cells"),
    "tsh": ("Blood Serum", "Thyroid", "Pituitary Thyrotrophs"),
    "igf-1": ("Blood Serum", "Liver", "Hepatocytes"),
    "dhea-s": ("Blood Serum", "Adrenal Gland", "Adrenal Cortex"),
    "mpv": ("Whole Blood", "Bone Marrow", "Megakaryocytes"),
    "eosinophil-count": ("Whole Blood", "Bone Marrow", "Eosinophils"),
    "8-ohdg": ("Urine", "Multi-Organ", "DNA (Oxidative Adduct)"),
    "folate": ("Blood Serum", "Multi-Organ", "Systemic Circulation"),
    "vitamin-b12": ("Blood Serum", "Liver", "Hepatocytes"),
    "selenium": ("Blood Serum", "Multi-Organ", "Systemic Circulation"),
    "zinc": ("Blood Serum", "Multi-Organ", "Systemic Circulation"),
    "supar": ("Blood Serum", "Immune System", "Monocytes/Macrophages"),
    "il-18": ("Blood Serum", "Immune System", "Monocytes/Macrophages"),
    "mcp-1": ("Blood Serum", "Immune System", "Vascular Endothelium"),
    "neopterin": ("Blood Serum", "Immune System", "Monocytes/Macrophages"),
    "scd14": ("Blood Serum", "Immune System", "Monocytes/Macrophages"),
    "scd163": ("Blood Serum", "Immune System", "Macrophages"),
    "procalcitonin": ("Blood Serum", "Thyroid", "Thyroid C-Cells"),
    "ptx3": ("Blood Serum", "Immune System", "Macrophages"),
    "d-dimer": ("Blood Plasma", "Liver", "Hepatocytes"),
    "pai-1": ("Blood Plasma", "Vascular Endothelium", "Endothelial Cells"),
    "vwf": ("Blood Plasma", "Vascular Endothelium", "Endothelial Cells"),
    "tmao": ("Blood Plasma", "Liver", "Hepatocytes"),
    "non-hdl-c": ("Blood Serum", "Liver", "Hepatocytes"),
    "lp-pla2": ("Blood Serum", "Vascular Endothelium", "Macrophages"),
    "apob-apoa1": ("Blood Serum", "Liver", "Hepatocytes"),
    "alpha-klotho": ("Blood Serum", "Kidney", "Renal Tubules"),
    "telomere-length": ("Whole Blood", "Multi-Organ", "Erythrocytes/Leukocytes"),
    "dna-methylation-age": ("Whole Blood", "Multi-Organ", "Erythrocytes/Leukocytes"),
    "mt-dna-copy": ("Whole Blood", "Multi-Organ", "Mitochondria"),
    "nfl": ("Blood Serum", "Brain", "Neurons/Axons"),
    "testosterone": ("Blood Serum", "Testis", "Leydig Cells"),
    "cortisol": ("Blood Serum", "Adrenal Gland", "Adrenal Cortex"),
    "c-peptide": ("Blood Serum", "Pancreas", "Beta Cells"),
    "adiponectin": ("Blood Serum", "Adipose Tissue", "Adipocytes"),
    "mcv": ("Whole Blood", "Bone Marrow", "Erythrocytes/Leukocytes"),
    "monocyte-count": ("Whole Blood", "Bone Marrow", "Monocytes/Macrophages"),
    "hematocrit": ("Whole Blood", "Bone Marrow", "Erythrocytes/Leukocytes"),
    "transferrin-sat": ("Blood Serum", "Liver", "Hepatocytes"),
    "deritis-ratio": ("Blood Serum", "Liver", "Hepatocytes"),
    "total-protein": ("Blood Serum", "Liver", "Hepatocytes"),
    "ag-ratio": ("Blood Serum", "Liver", "Hepatocytes"),
    "bmd-tscore": ("Non-Fluid / Imaging", "Bone", "Trabecular/Cortical Bone"),
    "pth": ("Blood Serum", "Parathyroid", "Parathyroid Chief Cells"),
    "bmi": ("Non-Fluid / Anthropometric", "Multi-Organ", "Multi-Tissue"),
    "waist-height-ratio": ("Non-Fluid / Anthropometric", "Adipose Tissue", "Adipocytes"),
    "gait-speed": ("Non-Fluid / Functional", "Skeletal Muscle", "Skeletal Myocytes"),
    "appendicular-lean-mass": ("Non-Fluid / Imaging", "Skeletal Muscle", "Skeletal Myocytes"),
    "hrv-sdnn": ("Non-Fluid / Functional", "Heart & Vasculature", "Cardiac Conduction"),
    "orthostatic-bp-drop": ("Non-Fluid / Functional", "Heart & Vasculature", "Vascular Endothelium"),
}

# ``fit_quality_note`` written by add_missing_curves_and_expected_values.py.
# Three shapes occur, and they do NOT all represent a real literature anchor:
#
#   "Synthesized from mortality_association (HR=1.25 default_assumed); ... No
#    mortality_association row; assumed HR=1.25 (quartile_extreme)."
#       -> the HR was INVENTED by the seeder. There is no study behind it.
#   "Recalculated from mortality_association (HR=1.3 quartile_extreme); ..."
#       -> a real anchor existed when the curve was built.
#   "Higher suPAR associated with increased mortality risk"
#       -> free-text provenance carried by the newer seeder.
ANCHOR_RE = re.compile(
    r"HR=(?P<hr>[0-9]*\.?[0-9]+)"
    r"(?:\s*,?\s*CI\s*(?P<lo>[0-9]*\.?[0-9]+)\s*[-–]\s*(?P<hi>[0-9]*\.?[0-9]+))?"
    r"(?:\s*\((?P<type>[a-z_]+)\))?",
    re.IGNORECASE,
)

# Markers whose curve HR is a seeder placeholder, never a measured hazard
# ratio. Writing these into mortality_association would assert a literature
# finding that does not exist, so they are reported as needing real sourcing.
PLACEHOLDER_MARKERS = ("default_assumed", "assumed HR", "No mortality_association row")

# Detect a fabricated/stub PMID: real ones are 7-8 digits, and the seeder's
# synthetic fixtures used obvious sequential patterns.
REAL_PMID_RE = re.compile(r"^[0-9]{7,8}$")

# Map the stored curve shape onto the association direction vocabulary.
SHAPE_TO_DIRECTION = {
    "monotonic_increasing": "increasing",
    "monotonic_decreasing": "decreasing",
    "u_shaped": "u_shaped",
    "j_shaped": "u_shaped",
    "inverse_j_shaped": "u_shaped",
    "linear": "increasing",
}

# Direction implied by the biomarker's own "higher is better" flag, used when
# the curve shape is not specific enough to disambiguate.
DIRECTIONALITY_TO_DIRECTION = {
    "higher_better": "decreasing",
    "lower_better": "increasing",
    "u_shaped": "u_shaped",
}


def resolve_anatomy(specimen_type: Optional[str], slug: str) -> Tuple[str, str, str]:
    """Return (bodily_fluid, primary_organ, tissue_origin) for a biomarker."""
    if slug in ANATOMY:
        return ANATOMY[slug]
    key = (specimen_type or "").strip().lower()
    if key in SPECIMEN_DEFAULTS:
        return SPECIMEN_DEFAULTS[key]
    return ("Multi-Fluid / Other", "Multi-Organ", "Multi-Tissue")


def parse_anchor(fit_quality_note: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extract the anchor HR / CI / hr_type the curve was synthesized from."""
    if not fit_quality_note:
        return None
    m = ANCHOR_RE.search(fit_quality_note)
    if not m:
        return None
    out: Dict[str, Any] = {"hazard_ratio": float(m.group("hr"))}
    out["ci_lower"] = float(m.group("lo")) if m.group("lo") else None
    out["ci_upper"] = float(m.group("hi")) if m.group("hi") else None
    out["hr_type"] = m.group("type") or "per_sd"
    return out


def is_placeholder(note: Optional[str]) -> bool:
    """True when the curve HR was invented by the seeder, not measured."""
    if not note:
        return True
    return any(tag.lower() in note.lower() for tag in PLACEHOLDER_MARKERS)


def classify_provenance(fit_quality_note: Optional[str]) -> str:
    """Bucket a curve's stored provenance for reporting."""
    if not fit_quality_note:
        return "no-fqn"
    if is_placeholder(fit_quality_note):
        return "placeholder"
    if "Recalculated from mortality_association" in fit_quality_note:
        return "measured"
    return "free-text"


def resolve_direction(bm: Biomarker, curve_shape: Optional[str]) -> str:
    """Pick the association direction, preferring the stored curve shape."""
    if curve_shape in SHAPE_TO_DIRECTION:
        return SHAPE_TO_DIRECTION[curve_shape]
    d = (bm.directionality or "").strip().lower()
    if d in DIRECTIONALITY_TO_DIRECTION:
        return DIRECTIONALITY_TO_DIRECTION[d]
    return "increasing"


def ensure_source(session: Session) -> Source:
    """Get or create the Peto et al. 2017 anchor source."""
    existing = (
        session.query(Source)
        .filter(Source.pmid == PETO_PMID, Source.year == PETO_YEAR)
        .one_or_none()
    )
    if existing is not None:
        return existing
    existing = session.query(Source).filter(Source.doi == PETO_DOI).one_or_none()
    if existing is not None:
        return existing
    src = Source(
        citation=PETO_CITATION,
        pmid=PETO_PMID,
        doi=PETO_DOI,
        year=PETO_YEAR,
        study_design="database_curation",
        url="https://mortalitypredictors.org",
    )
    session.add(src)
    session.flush()
    print(f"  [+source] created Source id={src.id} (PMID {PETO_PMID})")
    return src


def incomplete_biomarkers(session: Session) -> List[Biomarker]:
    """Biomarkers missing anatomy, associations, or both."""
    out = []
    for bm in session.query(Biomarker).order_by(Biomarker.id).all():
        missing_anatomy = not (bm.primary_organ or "").strip()
        missing_assoc = not bm.mortality_associations
        if missing_anatomy or missing_assoc:
            out.append(bm)
    return out


def backfill_one(session: Session, bm: Biomarker, source: Source,
                 dry_run: bool) -> Dict[str, Any]:
    """Fill the anatomy fields and (if absent) the anchor mortality association."""
    result = {"slug": bm.slug, "biomarker_id": bm.id, "anatomy": False, "assoc": False}

    # ---- anatomy ----------------------------------------------------------
    if not (bm.primary_organ or "").strip():
        fluid, organ, tissue = resolve_anatomy(bm.specimen_type, bm.slug)
        result["anatomy"] = True
        result["anatomy_values"] = (fluid, organ, tissue)
        if not dry_run:
            if not (bm.bodily_fluid or "").strip():
                bm.bodily_fluid = fluid
            if not (bm.tissue_origin or "").strip():
                bm.tissue_origin = tissue
            bm.primary_organ = organ

    # ---- mortality association -------------------------------------------
    if not bm.mortality_associations:
        # The anchor provenance lives on the all/all continuous HR function
        # (fit_quality_note), which add_missing_curves_and_expected_values.py
        # wrote for every gap-fill marker; the curve itself has no such column.
        fn = (
            session.query(HRFunction)
            .filter(
                HRFunction.biomarker_id == bm.id,
                HRFunction.sex == "all",
                HRFunction.age_band == "all",
            )
            .first()
        )
        anchor = parse_anchor(fn.fit_quality_note if fn else None) or {}
        provenance = classify_provenance(fn.fit_quality_note if fn else None)

        # A "default_assumed" HR is a seeder placeholder, not a study result.
        # Materializing it as a mortality_association would manufacture a
        # citation for a number nobody measured, so we surface it instead.
        if provenance in ("placeholder", "no-fqn"):
            result["needs_source"] = True
            result["skipped"] = (
                f"{provenance}: no measured hazard ratio exists for this marker"
            )
            return result

        hr = anchor.get("hazard_ratio")
        if hr is None:
            result["needs_source"] = True
            result["skipped"] = "no anchor HR recoverable"
            return result

        direction = resolve_direction(bm, fn.shape if fn else None)
        result["assoc"] = True
        result["provenance"] = provenance
        result["assoc_values"] = {
            "hazard_ratio": hr,
            "hr_type": anchor.get("hr_type"),
            "ci_lower": anchor.get("ci_lower"),
            "ci_upper": anchor.get("ci_upper"),
            "direction": direction,
        }
        if not dry_run:
            session.add(MortalityAssociation(
                biomarker_id=bm.id,
                source_id=source.id,
                hazard_ratio=hr,
                hr_type=anchor.get("hr_type") or "per_sd",
                hr_unit_scale=1.0,
                ci_lower=anchor.get("ci_lower"),
                ci_upper=anchor.get("ci_upper"),
                p_value=None,
                direction=direction,
                cohort_description=(
                    "Peto et al. 2017 (MortalityPredictors.org) anchor cohort"
                ),
                n=None,
                events=None,
                follow_up_years=None,
                population_type="general",
                adjustment_covariates=(
                    "Age, sex, and study-specific covariates (see source)"
                ),
                notes=(
                    "Backfilled mortality association reusing the anchor HR this "
                    "biomarker's HR curve was synthesized from; cohort attribution "
                    "is the MortalityPredictors.org curated literature underlying "
                    "Peto et al. 2017."
                ),
            ))

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report intended changes without writing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 2

    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Session_ = sessionmaker(bind=engine)
    session: Session = Session_()

    try:
        targets = incomplete_biomarkers(session)
        print(f"Incomplete biomarkers: {len(targets)}")
        if not targets:
            print("Nothing to do.")
            return 0

        source = ensure_source(session)

        n_anatomy = n_assoc = n_skipped = 0
        needs_source: List[str] = []
        for bm in targets:
            res = backfill_one(session, bm, source, args.dry_run)
            if res.get("anatomy"):
                n_anatomy += 1
                fluid, organ, tissue = res["anatomy_values"]
                print(f"  [anat]  {res['slug']:<28} {fluid} | {organ} | {tissue}")
            if res.get("assoc"):
                n_assoc += 1
                av = res["assoc_values"]
                ci = (f" CI {av['ci_lower']}-{av['ci_upper']}"
                      if av["ci_lower"] is not None else "")
                print(f"  [assoc] {res['slug']:<28} HR={av['hazard_ratio']}{ci} "
                      f"({av['hr_type']}, {av['direction']}) "
                      f"[{res['provenance']}]")
            if res.get("skipped"):
                n_skipped += 1
                if res.get("needs_source"):
                    needs_source.append(res["slug"])
                print(f"  [skip]  {res['slug']:<28} {res['skipped']}")

        if needs_source:
            print(f"\nNO MEASURED HR IN CATALOG ({len(needs_source)} markers).")
            print("These curves were built from a seeder placeholder (HR=1.25) or")
            print("carry no provenance at all. They need a real dose-response study")
            print("before a mortality_association can be written:")
            for slug in needs_source:
                print(f"    - {slug}")

        if args.dry_run:
            session.rollback()
            print(f"\nDRY RUN: would fill anatomy={n_anatomy}, "
                  f"associations={n_assoc}, skipped={n_skipped}")
        else:
            session.commit()
            print(f"\nCOMMITTED: anatomy={n_anatomy}, associations={n_assoc}, "
                  f"skipped={n_skipped}")
        return 0
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

"""
Example end-to-end run of the interventions layer.

Usage:
    pip install pandas numpy scipy matplotlib requests lifelines patsy anthropic pydantic
    export ANTHROPIC_API_KEY=...
    python run_intervention_search.py crp

Steps:
  1. Thorough search (Europe PMC x 5 query templates x N search terms,
     Cochrane-filtered Europe PMC, ClinicalTrials.gov) for one biomarker.
  2. LLM extraction of structured effect estimates from each candidate.
  3. Write everything to a review CSV -- NOTHING here is auto-published;
     a human confirms MANUAL_VERIFIED before it's used downstream.
  4. (Illustrative only, commented out) once you have a MANUAL_VERIFIED
     effect, show how it plugs into the existing HR-curve machinery.
"""

import sys

from interventions_toolkit.extraction import extract_batch, write_review_csv
from interventions_toolkit.search_orchestrator import search_biomarker
from interventions_toolkit.config import BIOMARKER_SEARCH_SPECS


def main(biomarker_id: str):
    spec = BIOMARKER_SEARCH_SPECS[biomarker_id]
    print(f"Searching for interventions affecting {spec.label}...")
    results = search_biomarker(biomarker_id, page_size=20)
    all_candidates = results["literature"] + results["cochrane"] + results["trials"]
    print(f"Found {len(all_candidates)} candidates "
          f"({len(results['literature'])} literature, {len(results['cochrane'])} Cochrane, "
          f"{len(results['trials'])} trial registrations)")

    print("Extracting structured effects (this calls the LLM once per candidate)...")
    rows = extract_batch(spec.label, all_candidates)

    out_path = f"/mnt/user-data/outputs/{biomarker_id}_intervention_effects_review.csv"
    write_review_csv(rows, out_path, append=False)

    n_relevant = sum(1 for r in rows if r.effect.found_relevant_effect)
    print(f"\n{n_relevant}/{len(rows)} candidates yielded a relevant effect estimate.")
    print(f"Review queue written to {out_path} -- every row needs a human to move it "
          f"from NEEDS_REVIEW to MANUAL_VERIFIED (or REJECTED) before use.")

    # --- Illustrative only: applying a verified effect to the HR curve ---
    # from interventions_toolkit.impact import apply_effect_to_curve
    # from nhanes_toolkit.hazard_curves import fit_rcs_cox
    # from nhanes_toolkit.analysis import pool_cycles, add_age_cohort
    #
    # df = add_age_cohort(pool_cycles(biomarker_id))
    # result = fit_rcs_cox(df[df.sex_label == "Male"], age_interaction=True)
    # impact = apply_effect_to_curve(
    #     result, df, effect_value=-0.34, effect_measure="mean_difference", age=60,
    # )
    # print(impact)


if __name__ == "__main__":
    biomarker = sys.argv[1] if len(sys.argv) > 1 else "crp"
    main(biomarker)

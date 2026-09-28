"""
Example: rank cohorts by testing priority using distribution shape alone
(no mortality model, no intervention data needed).

Usage:
    python run_testing_priority.py crp
"""

import sys

from nhanes_toolkit.analysis import add_age_cohort, pool_cycles
from nhanes_toolkit.testing_priority import testing_priority_report


def main(biomarker_id: str):
    df = pool_cycles(biomarker_id, with_mortality=False)  # no mortality data needed for this
    df = add_age_cohort(df)
    df = df[df["age_years"] >= 18]

    report = testing_priority_report(df, biomarker_id)
    print(f"\n=== Testing priority for {biomarker_id}, by cohort ===\n")
    print(report.to_string(index=False))

    print(
        "\ndispersion_rank: cohorts where an individual result carries the most\n"
        "  information (high spread relative to the cohort's typical value).\n"
        "borderline_rank (if shown): cohorts where the most people sit near a\n"
        "  recognized clinical decision point -- where testing would most often\n"
        "  change risk classification. Only defined for biomarkers with a\n"
        "  reference band in clinical_bands.py."
    )


if __name__ == "__main__":
    biomarker = sys.argv[1] if len(sys.argv) > 1 else "crp"
    main(biomarker)

"""
Example: pull albumin across all cycles, build distributions stratified by
sex/age/race, test for racial differences, plot, and (optionally) fit an
HR-vs-value curve.

Usage:
    pip install pandas numpy scipy matplotlib requests lifelines patsy
    python run_example.py
"""

from nhanes_toolkit.analysis import (
    pool_cycles, add_age_cohort, stratified_summary, racial_difference_tests,
    plot_distributions_by_race,
)
from nhanes_toolkit.config import BIOMARKERS

BIOMARKER = "albumin"  # try "wbc", "creatinine", "glucose", "hdl", "crp", ...


def main():
    print(f"Pulling {BIOMARKER} across cycles (first run downloads + caches XPT files)...")
    df = pool_cycles(BIOMARKER, with_mortality=True)
    df = add_age_cohort(df)
    df = df[df["age_years"] >= 18]  # adults only, adjust as needed

    label = BIOMARKERS[BIOMARKER].label
    print(f"\n{len(df):,} respondents with valid {label} values.\n")

    summary = stratified_summary(df)
    print("=== Weighted distribution by sex / age cohort / race ===")
    print(summary.to_string(index=False))

    tests = racial_difference_tests(df)
    print("\n=== Kruskal-Wallis test for racial differences, within sex x age strata ===")
    print(tests.to_string(index=False))

    outpath = f"/mnt/user-data/outputs/{BIOMARKER}_distribution_by_race.png"
    plot_distributions_by_race(df, label, outpath)
    print(f"\nSaved plot to {outpath}")

    summary.to_csv(f"/mnt/user-data/outputs/{BIOMARKER}_stratified_summary.csv", index=False)
    tests.to_csv(f"/mnt/user-data/outputs/{BIOMARKER}_racial_difference_tests.csv", index=False)


if __name__ == "__main__":
    main()

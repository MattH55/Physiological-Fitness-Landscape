# NHANES biomarker distribution + racial-difference toolkit

Pulls NHANES lab biomarkers across survey cycles (1999-2018), merges with
demographics and NCHS mortality linkage, and builds:

1. Weighted value distributions stratified by **sex x age cohort x race/
   ethnicity** (`analysis.stratified_summary`, `analysis.plot_distributions_by_race`)
2. A screening test for racial differences within each sex/age stratum
   (`analysis.racial_difference_tests`, Kruskal-Wallis)
3. (Optional) HR(biomarker value) curves via Cox PH + restricted cubic
   spline, with race as a covariate or interaction (`hazard_curves.py`)

## Quick start

```bash
pip install pandas numpy scipy matplotlib requests lifelines patsy
python run_example.py   # pulls "albumin" by default; edit BIOMARKER at the top
```

First run downloads and caches raw NHANES `.XPT` files and NCHS mortality
`.dat` files into `./nhanes_cache/` (a few hundred MB for all 10 cycles x a
couple of components). Subsequent runs reuse the cache.

To add a biomarker, add an entry to `BIOMARKERS` in `nhanes_toolkit/config.py`
— you need the NHANES component file stem (e.g. `"CBC"`) and the SAS
variable name (e.g. `"LBXWBCSI"`), findable on the NHANES variable search
page (wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx). If the variable
name or component changes across cycles (CRP is the example already handled
in the config), use `component_overrides` / `variable_overrides`.

## What's been tested vs. not

This was built and smoke-tested in a sandbox **without internet access to
cdc.gov**, so:

- **Tested against synthetic data**: the merge/weighting/stratification/
  plotting/Cox-spline logic in `analysis.py` and `hazard_curves.py` all run
  correctly end-to-end (verified with simulated respondents, a simulated
  race effect, and a simulated mortality outcome).
- **Not tested against live NHANES**: `download.py`'s URL pattern and
  `mortality.py`'s fixed-width column layout match NCHS's published loader
  programs as of this writing, but haven't been run against the live
  servers. Run `run_example.py` yourself first with a small `CYCLES` slice
  (e.g. just 2017-2018) to confirm the URLs/column positions still match
  before doing a full 10-cycle pull. If something's off, the error will be
  at the exact failed request/parse -- most likely causes are a renamed
  component file or a shifted mortality-file column (CDC has occasionally
  revised these).

Three real bugs were caught and fixed during synthetic testing (worth
knowing about since they'd resurface if you extend this code):
- A Cox model can't include an intercept column (it's absorbed into the
  baseline hazard) -- the spline basis had one by default, causing a
  singular matrix.
- Fitting a spline x race-dummy Cox model on a rare outcome (mortality) is
  prone to quasi-separation when a race category has few deaths -- fixed
  with a small ridge penalty and pooling sparse race categories.
- Predicting the HR curve on a small grid re-derived spline *knots* from
  that grid instead of reusing the training knots, which either crashes
  (too few points) or silently shifts the curve. Fixed by carrying the
  fitted design_info forward via `patsy.build_design_matrices`.

## Interpreting racial differences (read this before presenting results)

- `RIDRETH1` (1999-2010) and `RIDRETH3` (2011-2018) are NHANES's own
  self-reported race/Hispanic-origin categories -- coarse census-style
  groupings, not biological/genetic categories, and the category set
  changes at 2011 (Asian only breaks out separately from 2011 on).
- A statistically significant between-group difference can reflect
  measurement factors, socioeconomic status, health-care access, diet, or
  comorbidity prevalence, in addition to (for a few markers) real
  population-level physiological variation. This code flags differences;
  it doesn't and can't adjudicate why they exist.
- The distribution/plotting code uses NHANES exam weights (rescaled for
  pooled cycles), which is right for point estimates. The Kruskal-Wallis
  test is **unweighted** -- a reasonable first screen, but for a number
  you'd publish, redo it with proper survey-design standard errors (e.g.
  Python's `statsmodels` complex-samples tools, or R's `survey`/`srvyr`,
  using `SDMVPSU`/`SDMVSTRA`).

## Files

- `nhanes_toolkit/config.py` — cycles, biomarker variable map, race/sex labels
- `nhanes_toolkit/download.py` — fetch + cache NHANES `.XPT` lab/demo files
- `nhanes_toolkit/mortality.py` — fetch + parse NCHS mortality linkage files
- `nhanes_toolkit/analysis.py` — merge, weighted distributions, racial-difference tests, plotting
- `nhanes_toolkit/hazard_curves.py` — optional Cox PH + restricted cubic spline HR curves
- `run_example.py` — end-to-end example for one biomarker

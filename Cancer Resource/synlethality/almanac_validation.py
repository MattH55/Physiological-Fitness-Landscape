"""
Real-data validation of synlethality/scoring.py against NCI-ALMANAC.

`scoring.py`'s Bliss/Loewe/HSA/ZIP engine had only ever been run against
synthetic test fixtures before this (2026-09-23) -- this module runs it
against a real, published, full dose-response checkerboard for the first
time, as a genuine correctness/robustness demonstration.

**This does NOT fill the modifier x drug data gap.** NCI-ALMANAC
(Holbeck et al. 2017) is a drug x drug combination screen -- 50 FDA-approved
anticancer drugs tested pairwise across the NCI-60 cell line panel, 3M+
real data points, mirrored ungated on Zenodo (record 3782304, the comboFM
dataset) since NCI's own wiki host blocks automated access the same way
MDPI does. This project's `interaction_effect` schema is structurally
modifier_id x drug_id, not drug_id x drug_id -- there is no non-
pharmacological modifier anywhere in ALMANAC, so this cannot become a
curated interaction_effect row no matter how it's reshaped. Two of our
curated drugs (oxaliplatin, lomustine) happen to be in ALMANAC's 50-drug
panel, which is what makes a real oxaliplatin x lomustine checkerboard
usable here as a validation case -- coincidence, not a schema fit.

**The %Growth -> viability conversion, and its real caveat**: NCI's own
readout is "%Growth" (Monks et al. 1991 NCI-60 assay convention), not a
raw viability fraction -- it accounts for the T0 (time-zero) cell count,
so 100 = growth matching the untreated control, 0 = net-static (no growth,
not death), -100 = complete cell kill. The standard approximation used in
several published NCI-ALMANAC re-analyses (and adopted here, not invented)
maps this onto scoring.py's expected [0, 1] viability fraction via
`viability = clip((growth_percent + 100) / 100, 0, 1) / 2 + 0.5`... written
out plainly as `(growth_percent + 100) / 200`. This is a real, standard,
documented approximation -- not a literal measurement of fraction-alive --
since %Growth's T0-relative definition doesn't correspond exactly to an
endpoint viable fraction. ALMANAC's own per-pair grids omit the (0, 0)
untreated-control point (it's definitionally 100% by the assay's own
normalization, not separately measured/stored) -- assumed as growth=100.0
here, not fabricated.

**Real finding from running this** (see tests/test_almanac_validation.py):
across several real oxaliplatin x lomustine checkerboards (different
NCI-60 cell lines), Bliss/HSA/ZIP consistently agree, classifying the
combination as additive with small, stable mean scores. Loewe swings
wildly by comparison -- antagonistic in one cell line, synergistic in
another, sometimes producing no computable value at all -- for the *same*
real drug pair. This is a real, reproducible finding about Loewe's
numerical stability on coarse (3-4 point) real dose-response grids, not a
bug in this implementation: Loewe/ZIP require fitting a Hill curve to each
monotherapy edge from only 3 non-control points (the Hill slope isn't
identifiable at that count -- see scoring.py's own `_fit_hill` docstring),
and real, noisy biological dose-response curves can defeat that fit
badly when the tested dose range doesn't span the curve's inflection well.
"""

from __future__ import annotations

import csv
import os


def growth_percent_to_viability(growth_percent: float) -> float:
    """NCI %Growth -> viability fraction, clipped to [0, 1]. See module
    docstring for the real definition and its documented approximation."""
    return max(0.0, min(1.0, (growth_percent + 100.0) / 200.0))


def load_almanac_checkerboard(csv_path: str, drug1: str, drug2: str, cell_line: str):
    """Real checkerboard for (drug1, drug2, cell_line) from a real
    NCI-ALMANAC export (Conc1,Conc2,Drug1,Drug2,CellLine,PercentageGrowth
    columns -- the comboFM/Zenodo mirror's CombALMANAC_*.csv format).

    Returns (doses_a, doses_b, viability_matrix) or None if no rows match.
    The (0, 0) untreated-control cell is assumed growth=100.0 (see module
    docstring) since ALMANAC's own grids don't store it explicitly.
    """
    rows = []
    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["Drug1"] == drug1 and row["Drug2"] == drug2 and row["CellLine"] == cell_line:
                rows.append(row)
    if not rows:
        return None

    doses_a = sorted({float(r["Conc1"]) for r in rows})
    doses_b = sorted({float(r["Conc2"]) for r in rows})
    grid = {(float(r["Conc1"]), float(r["Conc2"])): float(r["PercentageGrowth"]) for r in rows}

    matrix = []
    for c1 in doses_a:
        row_vals = []
        for c2 in doses_b:
            if c1 == 0.0 and c2 == 0.0:
                growth = 100.0  # assumed control edge; see module docstring
            else:
                growth = grid.get((c1, c2))
                if growth is None:
                    return None  # incomplete grid; don't guess a missing cell
            row_vals.append(growth_percent_to_viability(growth))
        matrix.append(row_vals)
    return doses_a, doses_b, matrix

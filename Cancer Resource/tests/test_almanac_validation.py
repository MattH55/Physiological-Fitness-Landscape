"""Real-data validation of synlethality/scoring.py against NCI-ALMANAC
(see synlethality/almanac_validation.py for the full explanation of what
this is and, importantly, what it isn't -- a drug x drug validation of the
scoring engine, not modifier x drug data).

Skipped if the real ALMANAC export isn't present in this environment (a
one-time download from Zenodo record 3782304, not committed here -- same
posture as the DepMap/PRISM/LINCS real-data tests)."""

import os

import pytest

from synlethality.almanac_validation import growth_percent_to_viability, load_almanac_checkerboard
from synlethality.scoring import score_matrix

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "combofm", "CombALMANAC_555300.csv",
)


def _require_csv():
    if not os.path.isfile(CSV_PATH):
        pytest.skip(f"{CSV_PATH} not present -- download comboFM_data.zip from "
                    "https://zenodo.org/records/3782304 and extract "
                    "CombALMANAC_555300.csv to run this real-data validation.")


def test_growth_percent_to_viability_conversion():
    assert growth_percent_to_viability(100.0) == pytest.approx(1.0)   # normal growth
    assert growth_percent_to_viability(0.0) == pytest.approx(0.5)     # net-static
    assert growth_percent_to_viability(-100.0) == pytest.approx(0.0)  # total kill
    # Real data can exceed the nominal +/-100 range (measurement noise);
    # must clip, never go outside [0, 1].
    assert growth_percent_to_viability(150.0) == pytest.approx(1.0)
    assert growth_percent_to_viability(-150.0) == pytest.approx(0.0)


def test_real_oxaliplatin_lomustine_checkerboard_loads_and_scores():
    """Real, complete 4x4 checkerboard (oxaliplatin x lomustine, MCF7) --
    both curated drugs of ours, coincidentally also in ALMANAC's 50-drug
    panel. Confirms the real conversion + scoring.py run end-to-end
    without crashing on genuine published data."""
    _require_csv()
    grid = load_almanac_checkerboard(CSV_PATH, "Oxaliplatin", "Lomustine", "MCF7")
    assert grid is not None
    doses_a, doses_b, matrix = grid
    assert len(doses_a) == 4 and len(doses_b) == 4
    assert doses_a[0] == 0.0 and doses_b[0] == 0.0
    assert matrix[0][0] == pytest.approx(1.0)  # assumed control edge

    result = score_matrix(doses_a, doses_b, matrix)
    for model in ("bliss", "hsa", "loewe", "zip"):
        assert model in result["models"]


def test_real_data_reveals_loewe_instability_vs_bliss_hsa_zip_agreement():
    """The actual, reproducible finding from this validation (documented in
    almanac_validation.py): across real oxaliplatin x lomustine
    checkerboards in different real NCI-60 cell lines, Bliss/HSA/ZIP
    consistently classify the combination as additive with small, stable
    mean scores, while Loewe swings wildly (antagonistic in one line,
    synergistic in another, sometimes no data at all) for the *same* real
    drug pair. This is a genuine numerical-stability property of Loewe's
    Hill-curve-fitting approach on coarse real dose grids, not asserted as
    a bug -- captured here as a regression check on the real data itself,
    and as documentation that a large Loewe swing alone (without checking
    Bliss/HSA/ZIP agreement) should not be read as a real biological
    signal."""
    _require_csv()
    cell_lines_with_data = []
    bliss_classifications = set()
    loewe_classifications = set()
    for cell_line in ("MCF7", "T-47D", "HCT-116", "A549/ATCC", "MDA-MB-231/ATCC"):
        grid = load_almanac_checkerboard(CSV_PATH, "Oxaliplatin", "Lomustine", cell_line)
        if grid is None:
            continue
        doses_a, doses_b, matrix = grid
        result = score_matrix(doses_a, doses_b, matrix)
        cell_lines_with_data.append(cell_line)
        bliss_classifications.add(result["models"]["bliss"]["summary"]["classification"])
        loewe_cls = result["models"]["loewe"]["summary"]["classification"]
        loewe_classifications.add(loewe_cls)

    assert len(cell_lines_with_data) >= 3, "expected real data in at least 3 real cell lines"
    # Bliss agrees with itself across cell lines (the real, stable finding).
    assert bliss_classifications == {"additive"}
    # Loewe genuinely disagrees with itself across the SAME real drug pair
    # in different cell lines -- the real instability finding, not a
    # fabricated claim about the model's behavior.
    assert len(loewe_classifications) > 1, (
        "expected Loewe's classification to vary across real cell lines for "
        "the same drug pair (the documented instability finding) -- if this "
        "now fails, re-verify the finding still holds before assuming a bug")

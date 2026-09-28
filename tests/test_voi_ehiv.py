"""
Unit tests for the VOI / EHIV DALY-dollar layer (eq. 5–13).

Acceptance:
  (a) EHIV = 0 when c_test = λ · VOI
  (b) VOI is monotonically non-negative
  (c) EYLL = 0 when x = x_ref
  (d) population total equals the sum of exclusive per-stratum parts
      (overlapping strata are excluded, not double-counted)
  plus a hand-computed spreadsheet-style check on three published HR curves.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.voi import (
    LifeTableView,
    delta_daly,
    ehiv,
    expected_voi,
    eyll,
    make_hr_fn,
    population_voi,
    select_nonoverlapping_strata,
    shifted_value,
    voi_per_individual,
)


def _const_hr(hr):
    return lambda x: float(hr)


def _linear_hr(x_ref=1.0, beta=0.2):
    def hr(x):
        return math.exp(beta * (x - x_ref))
    return hr


class TestEYLL:
    def test_zero_when_x_equals_xref(self):
        table = LifeTableView(age=50, sex="M", s0_cond=[1.0, 0.9, 0.8, 0.5, 0.0])
        hr_fn = _linear_hr()
        assert eyll(1.5, 1.5, 50, "M", hr_fn, baseline_table=table) == 0.0
        assert eyll(3.0, 3.0, 50, "M", hr_fn, baseline_table=table) == 0.0

    def test_hand_computed_two_year_table(self):
        # S = [1.0, 0.9, 0.8, 0.0]; HR(x)=x; x=2, x_ref=1
        # EYLL = Σ (S^1 − S^2) = 0 + (0.9-0.81) + (0.8-0.64) + 0 = 0.25
        table = LifeTableView(age=50, sex="M", s0_cond=[1.0, 0.9, 0.8, 0.0])
        got = eyll(2.0, 1.0, 50, "M", lambda x: x, baseline_table=table)
        assert got == pytest.approx(0.25, abs=1e-12)

    def test_higher_hr_means_more_yll(self):
        table = LifeTableView(age=50, sex="M", s0_cond=[1.0, 0.95, 0.9, 0.8, 0.6, 0.0])
        low = eyll(1.2, 1.0, 50, "M", lambda x: x, baseline_table=table)
        high = eyll(2.0, 1.0, 50, "M", lambda x: x, baseline_table=table)
        assert high > low >= 0


class TestDeltaDALY:
    def test_equals_eyll_when_yld_zero(self):
        table = LifeTableView(age=40, sex="F", s0_cond=[1.0, 0.92, 0.7, 0.0])
        hr_fn = _linear_hr()
        assert delta_daly(1.4, 1.0, 40, "F", hr_fn, baseline_table=table, yld=0.0) == pytest.approx(
            eyll(1.4, 1.0, 40, "F", hr_fn, baseline_table=table)
        )

    def test_yld_extension_point(self):
        table = LifeTableView(age=40, sex="F", s0_cond=[1.0, 0.92, 0.0])
        hr_fn = _const_hr(1.0)
        # HR(x)=HR(x_ref)=1 → EYLL=0, so ΔDALY = yld
        assert delta_daly(1.0, 1.0, 40, "F", hr_fn, baseline_table=table, yld=0.3) == pytest.approx(0.3)


class TestVOINonNegative:
    def test_voi_never_negative(self):
        table = LifeTableView(age=50, sex="M", s0_cond=[1.0, 0.9, 0.7, 0.4, 0.0])
        hr_fn = _linear_hr(x_ref=2.0, beta=0.3)
        for x in [0.5, 1.0, 2.0, 3.0, 4.5]:
            r = voi_per_individual(
                x, 50, "M", sigma_x=1.0, epsilon=1.0, c_int_daly=0.0,
                hr_fn=hr_fn, x_ref=2.0, directionality="lower_better",
                baseline_table=table,
            )
            assert r.voi >= 0.0

    def test_zero_shift_gives_zero_voi_when_c_int_zero(self):
        table = LifeTableView(age=50, sex="M", s0_cond=[1.0, 0.9, 0.7, 0.0])
        r = voi_per_individual(
            3.0, 50, "M", sigma_x=1.0, epsilon=0.0, c_int_daly=0.0,
            hr_fn=_linear_hr(), x_ref=1.0, directionality="lower_better",
            baseline_table=table,
        )
        assert r.voi == pytest.approx(0.0, abs=1e-12)
        assert r.x_shifted == pytest.approx(r.x)

    def test_expected_voi_non_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ps = [0.1, 0.4, 0.4, 0.1]
        ev = expected_voi(
            xs, ps, age=50, sex="M", sigma_x=1.0, epsilon=1.0, c_int_daly=0.0,
            hr_fn=_linear_hr(), x_ref=2.0, directionality="lower_better",
        )
        assert ev.expected_voi >= 0.0


class TestEHIVBoundary:
    def test_zero_when_ctest_equals_lambda_voi(self):
        e_voi = 0.012345
        lam = 150_000.0
        result = ehiv(e_voi, lam, c_test=lam * e_voi)
        assert result.ehiv == pytest.approx(0.0, abs=1e-9)
        assert result.lambda_voi == pytest.approx(lam * e_voi)
        assert result.favorable is False

    def test_favorable_when_lambda_voi_exceeds_price(self):
        result = ehiv(0.02, 150_000.0, c_test=50.0)
        assert result.ehiv == pytest.approx(150_000.0 * 0.02 - 50.0)
        assert result.favorable is True


class TestPopulationAggregation:
    def _stratum(self, sex, age_band, n, voi_force=None):
        # Constant HR so EYLL=0 and VOI=0 unless we inject bins with a slope.
        xs = [1.0, 2.0, 3.0]
        ps = [0.2, 0.6, 0.2]
        return {
            "sex": sex,
            "age_band": age_band,
            "x_bins": xs,
            "p_bins": ps,
            "sigma_x": 1.0,
            "n": n,
            "sample_n": 500,
            "age": 50,
        }

    def test_total_equals_sum_of_strata(self):
        strata = [
            self._stratum("M", "20-39", 1000),
            self._stratum("F", "20-39", 2000),
            self._stratum("M", "40-59", 3000),
            self._stratum("F", "40-59", 4000),
            self._stratum("M", "60+", 5000),
            self._stratum("F", "60+", 6000),
        ]
        hr_fn = _linear_hr(x_ref=2.0, beta=0.25)
        result = population_voi(
            strata, lam=100_000.0, c_test=10.0, epsilon=1.0, c_int_daly=0.0,
            hr_fn=hr_fn, x_ref=2.0, directionality="lower_better",
        )
        assert result.total_voi == pytest.approx(sum(s.total_voi for s in result.by_stratum), rel=1e-12)
        assert result.total_ehiv == pytest.approx(sum(s.total_ehiv for s in result.by_stratum), rel=1e-12)
        assert result.total_n == pytest.approx(21000)
        assert len(result.by_stratum) == 6

    def test_overlapping_all_all_is_excluded(self):
        strata = [
            self._stratum("M", "20-39", 100),
            self._stratum("F", "20-39", 100),
            self._stratum("all", "all", 999999),  # must not be added in
            self._stratum("all", "20-39", 888888),
        ]
        included, excluded = select_nonoverlapping_strata(strata)
        keys = {(s["sex"], s["age_band"]) for s in included}
        assert ("M", "20-39") in keys
        assert ("F", "20-39") in keys
        assert ("all", "all") not in keys
        assert ("all", "20-39") not in keys
        assert any(e.get("sex") == "all" for e in excluded)

        hr_fn = _linear_hr()
        result = population_voi(
            strata, lam=1.0, c_test=0.0, epsilon=1.0, c_int_daly=0.0,
            hr_fn=hr_fn, x_ref=2.0, directionality="lower_better",
        )
        assert result.total_n == pytest.approx(200)
        assert not any(s.sex == "all" and s.age_band == "all" for s in result.by_stratum)


class TestShiftDirection:
    def test_lower_better_decreases_x(self):
        assert shifted_value(5.0, 1.0, 1.0, "lower_better", None) == pytest.approx(4.0)

    def test_higher_better_increases_x(self):
        assert shifted_value(5.0, 1.0, 1.0, "higher_better", None) == pytest.approx(6.0)

    def test_u_shaped_moves_toward_opt_without_overshoot(self):
        assert shifted_value(5.0, 10.0, 1.0, "u_shaped", 4.5) == pytest.approx(4.5)
        assert shifted_value(3.0, 0.2, 1.0, "u_shaped", 4.5) == pytest.approx(3.2)


def _load_biomarker_curve(slug):
    import sqlite3
    from pathlib import Path

    db = Path(__file__).resolve().parent.parent / "data" / "mortality_biomarkers.db"
    if not db.exists():
        pytest.skip("mortality_biomarkers.db not present")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    bm = c.execute("SELECT * FROM biomarker WHERE slug = ?", (slug,)).fetchone()
    if not bm:
        conn.close()
        pytest.skip(f"biomarker {slug} not in db")
    curve = c.execute(
        "SELECT * FROM biomarker_hr_curve WHERE biomarker_id = ? AND sex = 'all' AND age_band = 'all'",
        (bm["id"],),
    ).fetchone()
    if curve is None:
        curve = c.execute(
            "SELECT * FROM biomarker_hr_curve WHERE biomarker_id = ? LIMIT 1",
            (bm["id"],),
        ).fetchone()
    dist = c.execute(
        "SELECT * FROM population_distribution WHERE biomarker_id = ? AND sex = 'all' AND age_band = 'all'",
        (bm["id"],),
    ).fetchone()
    conn.close()
    if curve is None or dist is None:
        pytest.skip(f"missing curve/dist for {slug}")
    return dict(bm), dict(curve), dict(dist)


def _independent_eyll(x, x_ref, hr_fn, s0_cond):
    """Second implementation used as the 'spreadsheet' check — do not call eyll()."""
    hr_x = hr_fn(x)
    hr_ref = hr_fn(x_ref)
    return sum((s ** hr_ref) - (s ** hr_x) for s in s0_cond)


class TestThreeBiomarkerHandCheck:
    """Hand-computed check against an independent summation for 3 published curves."""

    SLUGS = ("high_sensitivity_crp", "hba1c", "ldl_cholesterol")

    @pytest.mark.parametrize("slug", SLUGS)
    def test_eyll_matches_independent_sum(self, slug):
        from backend.life_tables import conditional_survival_from_age
        from backend.optimization_engine import generate_population_distribution

        bm, curve, dist = _load_biomarker_curve(slug)
        hr_fn = make_hr_fn(curve)
        x_ref = float(curve["reference_value"] or dist["p50"] or dist["mean"])
        s0 = conditional_survival_from_age(50, "M")
        x = float(dist["mean"])
        engine_val = eyll(x, x_ref, 50, "M", hr_fn, baseline_table=LifeTableView(50, "M", s0))
        sheet_val = _independent_eyll(x, x_ref, hr_fn, s0)
        assert engine_val == pytest.approx(sheet_val, rel=1e-12, abs=1e-12)

        xs, ps = generate_population_distribution(
            mean=float(dist["mean"]),
            sd=float(dist["sd"] or 1.0),
            valid_min=float(bm["valid_domain_min"] if bm["valid_domain_min"] is not None else dist["mean"] - 4 * dist["sd"]),
            valid_max=float(bm["valid_domain_max"] if bm["valid_domain_max"] is not None else dist["mean"] + 4 * dist["sd"]),
            n_bins=40,
        )
        ev = expected_voi(
            xs, ps, age=50, sex="M",
            sigma_x=float(dist["sd"] or 1.0),
            epsilon=1.0, c_int_daly=0.0,
            hr_fn=hr_fn, x_ref=x_ref,
            directionality=bm["directionality"],
            optimal=bm.get("optimal_target"),
            valid_min=bm.get("valid_domain_min"),
            valid_max=bm.get("valid_domain_max"),
        )
        assert ev.expected_voi >= 0.0
        boundary = ehiv(ev.expected_voi, 150_000.0, c_test=150_000.0 * ev.expected_voi)
        assert boundary.ehiv == pytest.approx(0.0, abs=1e-6)

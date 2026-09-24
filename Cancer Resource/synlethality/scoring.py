"""
Classical synergy quantification -- Prediction Methodology Stage 2 (see PREDICTION_METHODOLOGY.md).

Applies the standard drug-combination reference models (Bliss independence,
HSA, Loewe additivity, ZIP-style delta) to a two-factor dose-response matrix.
The math does not require both factors to be drugs; it applies unchanged to
modifier-level x drug-dose surfaces (e.g. BHB concentration x drug dose, or
temperature x drug dose) once the modifier axis is expressed on a monotone
level scale (concentration, temperature, O2 depth, duration).

Matrix layout convention (matches SynergyFinder/DrugComb exports):
  doses_a          modifier levels, ascending, doses_a[0] == 0  (modifier control)
  doses_b          drug doses, ascending,      doses_b[0] == 0  (drug control)
  viability[i][j]  viability fraction at (doses_a[i], doses_b[j])
  row 0            drug monotherapy edge; col 0 modifier monotherapy edge;
  [0][0]           untreated control.

Scores are reported as effect excess: observed combined effect E = 1 - viability
minus the model's expected effect. Positive = synergistic (more death than the
reference model predicts), negative = antagonistic. Loewe additionally reports
the combination index (CI < 1 = synergy) as score = 1 - CI. Monotherapy edge
cells are null — scoring them would be circular.

Loewe and ZIP require fitting single-agent Hill curves to the two monotherapy
edges and use numpy/scipy (lazy import). ZIP is implemented as the delta score
over Hill-fitted single-agent surfaces (the ZIP core); it does not reproduce
SynergyFinder's exact curve-shift correction.

This engine produces the ground-truth synergy labels for Tier 1 combinations
once curated dose-response matrices are ingested; it never fabricates values
into the database — results are returned to the caller, not persisted.
"""

from __future__ import annotations

MODELS = ("bliss", "hsa", "loewe", "zip")

MODEL_DESCRIPTIONS = {
    "bliss": (
        "Bliss independence: expected E = Ea + Eb - Ea*Eb "
        "(probabilistic independent action)."
    ),
    "hsa": "Highest single agent: expected E = max(Ea, Eb).",
    "loewe": (
        "Loewe additivity: CI = da/Da + db/Db from Hill fits to the two "
        "monotherapy edges; reported score = 1 - CI (CI < 1 = synergy)."
    ),
    "zip": (
        "ZIP-style delta: observed effect minus Bliss expectation over "
        "Hill-fitted single-agent surfaces (zero interaction potency)."
    ),
}

SYNERGY_THRESHOLD = 0.1  # |mean excess| above this -> synergistic/antagonistic


def _as_effects(doses_a, doses_b, viability, viability_scale):
    """Validate inputs and return the effect matrix (E = 1 - viability)."""
    if not isinstance(doses_a, (list, tuple)) or not isinstance(doses_b, (list, tuple)):
        raise ValueError("doses_a and doses_b must be lists of numbers.")
    if not isinstance(viability, (list, tuple)) or not viability:
        raise ValueError("viability must be a non-empty 2-D list.")
    if viability_scale not in ("fraction", "percent"):
        raise ValueError("viability_scale must be 'fraction' or 'percent'.")

    def _check_doses(d, name):
        if len(d) < 2:
            raise ValueError(f"{name} must contain a control (0) plus >=1 dose.")
        vals = []
        for x in d:
            if not isinstance(x, (int, float)) or isinstance(x, bool):
                raise ValueError(f"{name} entries must be numeric, got {x!r}.")
            vals.append(float(x))
        if vals[0] != 0.0:
            raise ValueError(f"{name}[0] must be 0 (control edge of the matrix).")
        if any(v2 <= v1 for v1, v2 in zip(vals, vals[1:])):
            raise ValueError(f"{name} must be strictly ascending.")
        return vals

    da = _check_doses(doses_a, "doses_a")
    db = _check_doses(doses_b, "doses_b")
    scale = 100.0 if viability_scale == "percent" else 1.0

    if len(viability) != len(da):
        raise ValueError(
            f"viability has {len(viability)} rows but doses_a has {len(da)} levels."
        )
    effects = []
    for i, row in enumerate(viability):
        if not isinstance(row, (list, tuple)) or len(row) != len(db):
            raise ValueError(
                f"viability row {i} must be a list of {len(db)} numbers "
                f"(one per doses_b entry)."
            )
        erow = []
        for v in row:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError(f"viability entries must be numeric, got {v!r}.")
            fv = float(v) / scale
            if fv < -1e-9 or fv > 1.0 + 1e-9:
                raise ValueError(
                    f"viability value {v!r} outside the {viability_scale} range."
                )
            erow.append(min(1.0, max(0.0, 1.0 - fv)))
        effects.append(erow)
    return da, db, effects


def _edge_scores(effects, expected_fn):
    """Cell scores for rows/cols beyond the monotherapy edges (else None)."""
    n_a, n_b = len(effects), len(effects[0])
    out = []
    for i in range(n_a):
        row = []
        for j in range(n_b):
            if i == 0 or j == 0:
                row.append(None)
            else:
                row.append(effects[i][j] - expected_fn(effects[i][0], effects[0][j]))
        out.append(row)
    return out


def bliss_scores(effects):
    """Bliss independence: expected E = Ea + Eb - Ea*Eb."""
    return _edge_scores(effects, lambda ea, eb: ea + eb - ea * eb)

# ---------------------------------------------------------------------------
# Hill-curve fitting (Loewe / ZIP)
# ---------------------------------------------------------------------------

def _fit_hill(doses, edge_effects):
    """Fit E(d) = Emax * d^n / (EC50^n + d^n) (Emin fixed at 0).

    Returns (emax, ec50, n). The control point (dose 0, E = 0) is excluded
    from the fit but implied by Emin = 0. With only 3 non-control points the
    Hill slope is not identifiable, so n is fixed at 1 (Emax/EC50 fit only);
    >=4 points fit the full 3-parameter curve.
    """
    try:
        import warnings

        import numpy as np
        from scipy.optimize import OptimizeWarning, curve_fit
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Loewe/ZIP scoring requires numpy and scipy (pip install numpy scipy)."
        ) from exc

    pts = [(float(d), float(e)) for d, e in zip(doses, edge_effects) if d > 0]
    if len(pts) < 3:
        raise ValueError(
            "Loewe/ZIP need >=3 non-control dose points on each monotherapy "
            f"edge; got {len(pts)}."
        )
    d = np.asarray([p[0] for p in pts])
    e = np.asarray([p[1] for p in pts])
    emax0 = min(1.0, max(float(e.max()), 0.05))

    if len(pts) >= 4:
        def hill(x, emax, ec50, n):
            return emax * np.power(x, n) / (np.power(ec50, n) + np.power(x, n))

        p0 = [emax0, float(np.median(d)), 1.0]
        bounds = ([1e-4, d.min() * 1e-2, 0.1], [1.0, d.max() * 1e2, 10.0])
    else:
        def hill(x, emax, ec50):
            return emax * x / (ec50 + x)

        p0 = [emax0, float(np.median(d))]
        bounds = ([1e-4, d.min() * 1e-2], [1.0, d.max() * 1e2])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", OptimizeWarning)
        popt, _ = curve_fit(hill, d, e, p0=p0, bounds=bounds, maxfev=20000)
    emax, ec50 = float(popt[0]), float(popt[1])
    n = float(popt[2]) if len(popt) > 2 else 1.0
    return (emax, ec50, n)


def _hill_effect(d, emax, ec50, n):
    if d <= 0:
        return 0.0
    return emax * d**n / (ec50**n + d**n)


def _hill_inverse(e, emax, ec50, n):
    """Dose producing effect e; None when outside the fitted range."""
    if e <= 0.0 or e >= emax:
        return None
    return ec50 * (e / (emax - e)) ** (1.0 / n)


def loewe_scores(doses_a, doses_b, effects):
    """Loewe additivity: CI = da/Da + db/Db; score = 1 - CI.

    Returns (scores, meta) where meta carries the fitted Hill parameters and
    the mean combination index over scored cells.
    """
    hill_a = _fit_hill(doses_a, [effects[i][0] for i in range(len(effects))])
    hill_b = _fit_hill(doses_b, effects[0])
    cis = []
    out = []
    for i in range(len(effects)):
        row = []
        for j in range(len(effects[0])):
            if i == 0 or j == 0:
                row.append(None)
                continue
            e = effects[i][j]
            d_a = _hill_inverse(e, *hill_a)
            d_b = _hill_inverse(e, *hill_b)
            if d_a is None or d_b is None:
                row.append(None)  # effect outside what either agent can explain
                continue
            ci = doses_a[i] / d_a + doses_b[j] / d_b
            cis.append(ci)
            row.append(1.0 - ci)
        out.append(row)
    meta = {
        "hill_a": hill_a,
        "hill_b": hill_b,
        "mean_ci": (sum(cis) / len(cis)) if cis else None,
    }
    return out, meta


def zip_scores(doses_a, doses_b, effects):
    """ZIP-style delta: observed E minus Bliss expectation over fitted curves."""
    hill_a = _fit_hill(doses_a, [effects[i][0] for i in range(len(effects))])
    hill_b = _fit_hill(doses_b, effects[0])
    out = []
    for i in range(len(effects)):
        row = []
        for j in range(len(effects[0])):
            if i == 0 or j == 0:
                row.append(None)
                continue
            fa = _hill_effect(doses_a[i], *hill_a)
            fb = _hill_effect(doses_b[j], *hill_b)
            row.append(effects[i][j] - (fa + fb - fa * fb))
        out.append(row)
    return out, {"hill_a": hill_a, "hill_b": hill_b}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _summarize(scores):
    vals = [v for row in scores for v in row if v is not None]
    if not vals:
        return {"n_cells": 0, "mean": None, "max": None, "min": None,
                "classification": "no_data"}
    mean = sum(vals) / len(vals)
    if mean > SYNERGY_THRESHOLD:
        cls = "synergistic"
    elif mean < -SYNERGY_THRESHOLD:
        cls = "antagonistic"
    else:
        cls = "additive"
    return {"n_cells": len(vals), "mean": mean, "max": max(vals),
            "min": min(vals), "classification": cls}


def score_matrix(doses_a, doses_b, viability, models=None,
                 viability_scale="fraction"):
    """Score a modifier-level x drug-dose viability matrix.

    Returns {"models": {name: {"scores": [[float|None]], "summary": {...},
    "meta": {...}|None}}, "n_modifier_levels", "n_drug_doses",
    "synergy_threshold"}.
    """
    wanted = list(models) if models else list(MODELS)
    unknown = [m for m in wanted if m not in MODELS]
    if unknown:
        raise ValueError(f"Unknown scoring model(s) {unknown}; choose from {list(MODELS)}.")

    da, db, effects = _as_effects(doses_a, doses_b, viability, viability_scale)

    results = {}
    for name in wanted:
        meta = None
        if name == "bliss":
            scores = bliss_scores(effects)
        elif name == "hsa":
            scores = hsa_scores(effects)
        elif name == "loewe":
            scores, meta = loewe_scores(da, db, effects)
        else:
            scores, meta = zip_scores(da, db, effects)
        results[name] = {"scores": scores, "summary": _summarize(scores), "meta": meta}

    return {
        "models": results,
        "n_modifier_levels": len(da),
        "n_drug_doses": len(db),
        "synergy_threshold": SYNERGY_THRESHOLD,
    }


def summarize_for_storage(score_matrix_result: dict) -> dict:
    """Reduce a score_matrix() result to what's worth persisting on an
    InteractionEffect row (models.InteractionEffect.synergy_model_scores):
    per-model mean/classification/cell-count, not the full per-cell score
    grid (recomputable on demand from the same real matrix; storing it
    permanently would bloat the row for no real benefit).

    Deliberately keeps every model's result, even when they disagree --
    the real motivation for this field (see models.py) is that collapsing
    to one number hides exactly that disagreement (Loewe's real
    instability vs Bliss/HSA/ZIP's real agreement, found validating this
    engine against NCI-ALMANAC; see almanac_validation.py). Never picks a
    "winning" model here.
    """
    return {
        name: {
            "mean": d["summary"]["mean"],
            "classification": d["summary"]["classification"],
            "n_cells": d["summary"]["n_cells"],
        }
        for name, d in score_matrix_result["models"].items()
    }


def hsa_scores(effects):
    """Highest single agent: expected E = max(Ea, Eb)."""
    return _edge_scores(effects, max)

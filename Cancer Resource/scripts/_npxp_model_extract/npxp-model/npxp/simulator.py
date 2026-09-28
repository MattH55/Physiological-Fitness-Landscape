"""
Mechanistic cell-viability simulator -- the label generator.

WHY THIS EXISTS. Training a synergy model needs tens of thousands of
labelled (cell, A, B) triples. For drug-drug pairs those exist
(NCI-ALMANAC ~ 300k, DrugComb ~ 700k). For modifier-drug pairs the
published quantitative record is a few dozen thermal enhancement ratios
and IC50 fold-shifts, scattered across papers, much of it only in
figures. So the model is trained on drug-drug labels and transferred.

To develop and validate that transfer offline, this module generates
labels from an explicit mechanistic model of cell survival that the
predictor never sees. It is NOT a claim about real biology, and it is deliberately NOT
calibrated against published combination pharmacology: fitting it to a
list of "known" synergies and then training the predictor on its output
would make the validation circular -- the predictor would be recovering
the curator's priors, not learning anything.

What it is instead is a STRUCTURAL testbed. It encodes four sources of
non-additivity with known ground truth, so that "can a predictor built
only from signature-level features recover interaction structure, and
does that recovery survive holding out entire perturbagens and entire
cell lines?" becomes an answerable question offline. A predictor that
fails here cannot work on real labels either. A predictor that succeeds
here has cleared a necessary, not sufficient, bar -- quantitative
validation requires real DrugComb/NCI-ALMANAC labels (see data.py).

The four mechanisms:

  (i)   per-pathway saturation -- two agents hitting one pathway show
        diminishing returns;
  (ii)  module-level AND logic -- survival is a product over functional
        modules, so hitting two SEPARATE essential modules is
        multiplicatively worse for the cell than hitting one twice
        (this is the mechanism behind complementary exposure);
  (iii) inducible protection -- stress-response programs (heat shock,
        NRF2, autophagy, efflux) blunt the partner's insult, so blocking
        a partner-induced protective program is synergistic;
  (iv)  uptake modulation -- membrane permeability and efflux change the
        effective dose of a co-administered drug.

Ground truth runs on `func_vec` (true functional direction). The
predictor sees transcriptional `vec` plus target-derived corrections, so
it must cope with compensatory sign inversions the way a real
LINCS-trained model must.
"""
import numpy as np

from .pathways import PATHWAYS, PW_INDEX, MODULES, MODULE_NAMES, SURVIVAL_VEC

SURV = np.asarray(SURVIVAL_VEC, dtype=float)
ESSENTIAL_MODULES = ["proliferation", "damage_death", "proteostasis",
                     "metabolism", "growth_signalling", "nutrient_sensing",
                     "transcription", "redox"]
MODULE_IDX = {m: np.asarray([PW_INDEX[p] for p in MODULES[m]]) for m in MODULES}

PROTECTIVE_PROGRAMS = {
    "HEAT_SHOCK_RESPONSE": 0.55,
    "NRF2_ANTIOXIDANT": 0.45,
    "GLUTATHIONE_METABOLISM": 0.35,
    "AUTOPHAGY": 0.40,
    "ABC_EFFLUX": 0.30,
    "PROTEASOME": 0.30,
    "UNFOLDED_PROTEIN_RESPONSE": 0.20,
}
_PROT_I = np.asarray([PW_INDEX[k] for k in PROTECTIVE_PROGRAMS])
_PROT_W = np.asarray(list(PROTECTIVE_PROGRAMS.values()))
_MEMB = PW_INDEX["MEMBRANE_FLUIDITY_TRANSPORT"]
_EFFL = PW_INDEX["ABC_EFFLUX"]


def _baseline_activity(cell):
    """Pathway activity of the untreated line, on a (0, inf) scale."""
    return np.exp(0.30 * np.asarray(cell["expr_vec"], dtype=float))


def _effective_dose(pert, dose, partner_func, partner_dose):
    """Uptake modulation: a partner that fluidises the membrane raises the
    effective dose of a small molecule; efflux induction lowers it.
    Only pharmacological agents are dose-modulated this way."""
    if pert["kind"] != "drug":
        return dose
    memb = partner_func[_MEMB] * partner_dose / 8.0
    effl = partner_func[_EFFL] * partner_dose / 8.0
    return dose * float(np.exp(0.50 * memb - 0.40 * effl))


def _insult(cell, perts, doses):
    """Combined functional perturbation, with saturation and protection."""
    base = _baseline_activity(cell)
    dep = np.asarray(cell["dep_vec"], dtype=float)

    fs = [np.asarray(p["func_vec"], dtype=float) for p in perts]
    ds = list(doses)
    if len(perts) == 2:
        e0 = _effective_dose(perts[0], ds[0], fs[1], ds[1])
        e1 = _effective_dose(perts[1], ds[1], fs[0], ds[0])
        ds = [e0, e1]

    # (iii) inducible protection: each agent's induced protective program
    # blunts the other's insult.
    shields = []
    for i, (f, d) in enumerate(zip(fs, ds)):
        others = [j for j in range(len(fs)) if j != i]
        prot = 0.0
        for j in others:
            induced = np.maximum(fs[j][_PROT_I] * ds[j] / 8.0, 0.0)
            prot += float(np.sum(_PROT_W * induced))
        shields.append(1.0 / (1.0 + 0.22 * min(prot, 3.0)))

    # (i) per-pathway redundancy: two agents pushing the SAME pathway in
    # the same direction compete for the same rate-limiting step, so their
    # contributions combine sub-additively. Aggregating same-signed
    # contributions with an L^q norm (q > 1) gives this at every dose --
    # unlike a saturating tanh, which is linear in the sub-IC50 regime
    # where synergy is actually measured. Opposite-signed contributions
    # cancel linearly (one agent restoring what the other removes).
    Q = 1.20
    contrib = np.stack([f * d * s / 8.0 for f, d, s in zip(fs, ds, shields)])
    pos = np.maximum(contrib, 0.0)
    neg = np.maximum(-contrib, 0.0)
    agg_pos = np.sum(pos ** Q, axis=0) ** (1.0 / Q)
    agg_neg = np.sum(neg ** Q, axis=0) ** (1.0 / Q)
    raw = agg_pos - agg_neg
    delta = 3.0 * np.tanh(raw / 3.0)   # far-field cap only

    activity = base * np.exp(delta)
    return activity, dep


def viability(cell, perts, doses):
    """Fraction of control growth. (ii) module-level AND logic."""
    activity, dep = _insult(cell, perts, doses)
    v = 1.0
    for m in ESSENTIAL_MODULES:
        idx = MODULE_IDX[m]
        w = np.abs(SURV[idx]) * (1.0 + np.abs(dep[idx]))
        if w.sum() < 1e-9:
            continue
        signed = np.where(SURV[idx] >= 0, activity[idx], 1.0 / np.maximum(activity[idx], 1e-3))
        signed = np.clip(signed, 1e-3, 20.0)
        # Soft-min (power mean, p = -3) rather than an average: an
        # essential module is rate-limited by its weakest component, so
        # knocking out one pathway hard impairs the module. An average
        # would let a 6-pathway module shrug off a single-target drug.
        cap = float((np.sum(w * signed ** -2.5) / np.sum(w)) ** (-1.0 / 2.5))
        # Hill: capacity must stay near 1 for the module to support growth
        f = cap ** 1.35 / (cap ** 1.35 + 0.42 ** 1.35) / (1.0 / (1.0 + 0.42 ** 1.35))
        v *= min(f, 1.0)   # no module may raise growth above control
    return float(np.clip(v, 1e-4, 1.2))


def ic50_dose(cell, pert, lo=1e-3, hi=64.0, target=0.5):
    """Dose giving `target` viability; returns hi if never reached."""
    if viability(cell, [pert], [hi]) > target:
        return hi
    for _ in range(40):
        mid = np.sqrt(lo * hi)
        if viability(cell, [pert], [mid]) > target:
            lo = mid
        else:
            hi = mid
    return float(np.sqrt(lo * hi))


DOSE_GRID = (0.1, 0.2, 0.35, 0.5)   # sub-IC50: the regime where Bliss/Loewe
                                    # excess is informative rather than
                                    # saturation-dominated


def synergy(cell, pert_a, pert_b, grid=DOSE_GRID, return_matrix=False):
    """Mean Bliss excess inhibition (x100) over a 4x4 dose matrix anchored
    on each agent's single-agent IC50 -- the same summarisation DrugComb
    applies to screening matrices. Positive = synergy.
    """
    da = ic50_dose(cell, pert_a)
    db = ic50_dose(cell, pert_b)
    rows = []
    for ma in grid:
        row = []
        for mb in grid:
            a, b = da * ma, db * mb
            va = viability(cell, [pert_a], [a])
            vb = viability(cell, [pert_b], [b])
            vab = viability(cell, [pert_a, pert_b], [a, b])
            row.append((va * vb - vab) * 100.0)   # Bliss excess inhibition
        rows.append(row)
    mat = np.asarray(rows)
    score = float(mat.mean())
    if return_matrix:
        return score, mat, (da, db)
    return score

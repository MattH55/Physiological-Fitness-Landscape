"""
Feature construction for a (cell line, perturbagen A, perturbagen B) triple.

Design constraint: every feature must be computable for a
non-pharmacological modifier, i.e. from a signature + a target/mechanism
annotation + the cell context. Nothing may depend on a chemical
structure (SMILES, Morgan fingerprint), because a modifier has none.
This is what makes zero-shot transfer from drug-drug training data to
modifier-drug prediction possible at all, and it is the one place this
design departs from DeepSynergy / MatchMaker / DeepDDS, all of which are
structure-conditioned and therefore cannot represent hyperthermia.

Feature blocks
  1  cell context            baseline pathway activity + dependency
  2  pooled perturbation     order-invariant summaries of the two signatures
  3  geometry                signature similarity / orthogonality scalars
  4  dependency capture      single-agent efficacy proxies from cell dependency
  5  complementary exposure  per-module joint-hit-but-separate-neighbourhood
  6  escape-route blockade   one agent suppresses the other's protective program
  7  redundancy / buffering   overlapping hits, and mutual protection
  8  cell x mechanism cross   interaction of the pair's programs with context

Order invariance: blocks 2-8 are built from symmetric functions of A and
B, so f(A,B) == f(B,A) by construction rather than by train-time
augmentation.
"""
import numpy as np

from .pathways import (PATHWAYS, N_PW, PW_INDEX, SURVIVAL_VEC, MODULES,
                       MODULE_NAMES)

SURV = np.asarray(SURVIVAL_VEC, dtype=float)
PROTECTIVE = SURV > 0          # pathways whose activity supports survival
MODULE_MASKS = {m: np.asarray([p in set(g) for p in PATHWAYS], dtype=float)
                for m, g in MODULES.items()}
STRONG = 2.5                   # |z| threshold for "strongly perturbed"


def _relu(x):
    return np.maximum(x, 0.0)


def _cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na < 1e-9 or nb < 1e-9 else float(a @ b / (na * nb))


def _dependency_capture(f, dep, expr):
    """How much this agent removes what the line actually leans on.

    Positive contribution when the agent suppresses a survival-supporting
    pathway the line depends on, or induces a death program.
    """
    w = 1.0 + np.abs(dep)
    suppress = np.sum(w * _relu(SURV) * _relu(-f))       # blocks what helps
    induce = np.sum(w * _relu(-SURV) * _relu(f))          # turns on what kills
    rescue = np.sum(w * _relu(SURV) * _relu(f))           # boosts what helps
    ctx = np.sum(_relu(expr) * _relu(SURV) * _relu(-f))   # hits an active program
    return suppress, induce, rescue, ctx


def pair_features(cell, pert_a, pert_b, return_names=False):
    """Build the feature vector for one triple.

    cell    : dict with 'expr_vec', 'dep_vec'
    pert_a/b: dict with 'sig' (transcriptional), 'func_vec' (target-corrected)
    """
    expr = np.asarray(cell["expr_vec"], dtype=float)
    dep = np.asarray(cell["dep_vec"], dtype=float)

    # Transcriptional signatures -- what LINCS gives you.
    za = np.asarray(pert_a["vec"], dtype=float)
    zb = np.asarray(pert_b["vec"], dtype=float)
    # Target-corrected functional directions -- what drug-target
    # annotation gives you. Available for modifiers too (mechanism is
    # known even when no L1000 profile exists).
    fa = np.asarray(pert_a["func_vec"], dtype=float)
    fb = np.asarray(pert_b["func_vec"], dtype=float)

    feats, names = [], []

    def add(vals, labels):
        feats.extend(np.atleast_1d(vals).astype(float).tolist())
        names.extend(np.atleast_1d(labels).tolist())

    # -- block 1: cell context ------------------------------------------
    add(expr, [f"expr::{p}" for p in PATHWAYS])
    add(dep, [f"dep::{p}" for p in PATHWAYS])

    # -- block 2: pooled perturbation (symmetric) -----------------------
    add((fa + fb) / 2.0, [f"fmean::{p}" for p in PATHWAYS])
    add(np.abs(fa - fb) / 2.0, [f"fdiff::{p}" for p in PATHWAYS])
    add(np.sign(fa * fb) * np.sqrt(np.abs(fa * fb)),
        [f"fprod::{p}" for p in PATHWAYS])
    add((za + zb) / 2.0, [f"zmean::{p}" for p in PATHWAYS])

    # -- block 3: geometry ----------------------------------------------
    sa, sb = set(np.where(np.abs(fa) > STRONG)[0]), set(np.where(np.abs(fb) > STRONG)[0])
    inter, union = len(sa & sb), len(sa | sb)
    add([_cos(fa, fb), _cos(za, zb), _cos(np.abs(fa), np.abs(fb)),
         float(np.linalg.norm(fa)), float(np.linalg.norm(fb)),
         float(min(np.linalg.norm(fa), np.linalg.norm(fb))),
         float(np.linalg.norm(fa + fb)), float(np.linalg.norm(fa - fb)),
         len(sa), len(sb), inter, inter / union if union else 0.0,
         float(np.sum(np.sign(fa) * np.sign(fb) * (np.abs(fa) > STRONG) * (np.abs(fb) > STRONG)))],
        ["cos_func", "cos_expr", "cos_absfunc", "norm_a", "norm_b",
         "norm_min", "norm_sum", "norm_absdiff", "n_strong_a", "n_strong_b",
         "n_strong_both", "jaccard_strong", "sign_concordance"])

    # -- block 4: dependency capture (single-agent efficacy proxies) -----
    ca = _dependency_capture(fa, dep, expr)
    cb = _dependency_capture(fb, dep, expr)
    add([min(ca[0], cb[0]), max(ca[0], cb[0]), ca[0] + cb[0],
         min(ca[1], cb[1]), max(ca[1], cb[1]), ca[1] + cb[1],
         ca[2] + cb[2], min(ca[2], cb[2]),
         min(ca[3], cb[3]), max(ca[3], cb[3]), ca[3] + cb[3]],
        ["cap_suppress_min", "cap_suppress_max", "cap_suppress_sum",
         "cap_induce_min", "cap_induce_max", "cap_induce_sum",
         "cap_rescue_sum", "cap_rescue_min",
         "cap_ctx_min", "cap_ctx_max", "cap_ctx_sum"])

    # -- block 5: complementary exposure (Cheng et al. 2019) ------------
    # Both agents hit the same functional module, but through different
    # pathways within it: joint exposure high, within-module overlap low.
    comp_scores = []
    for m in MODULE_NAMES:
        mask = MODULE_MASKS[m]
        ea, eb = np.abs(fa) * mask, np.abs(fb) * mask
        ja = np.linalg.norm(ea) * np.linalg.norm(eb)          # joint exposure
        overlap = _cos(ea, eb)                                  # same neighbourhood?
        comp = ja * (1.0 - overlap)                             # separate -> high
        comp_scores.append(comp)
        add([ja, overlap, comp],
            [f"mod_joint::{m}", f"mod_overlap::{m}", f"mod_compl::{m}"])
    cs = np.asarray(comp_scores)
    add([cs.max(), cs.sum(), float(np.count_nonzero(cs > 5)), cs.argmax()],
        ["compl_max", "compl_sum", "compl_n_modules", "compl_argmax"])

    # -- block 6: escape-route blockade --------------------------------
    # A induces a protective program; B functionally suppresses it. This
    # is the dominant published mechanism for modifier-drug synergy
    # (hyperthermia + HSP90/proteasome inhibition; fasting + PI3K/IGF1R).
    prot = PROTECTIVE.astype(float)
    w = 1.0 + np.abs(dep)
    blk_ab = float(np.sum(w * prot * _relu(za) * _relu(-fb)))
    blk_ba = float(np.sum(w * prot * _relu(zb) * _relu(-fa)))
    # per-pathway detail for the strongest few programs of interest
    add([blk_ab + blk_ba, max(blk_ab, blk_ba), min(blk_ab, blk_ba)],
        ["blockade_sum", "blockade_max", "blockade_min"])
    for p in ["HEAT_SHOCK_RESPONSE", "PROTEASOME", "AUTOPHAGY",
              "NRF2_ANTIOXIDANT", "GLUTATHIONE_METABOLISM", "ABC_EFFLUX",
              "MTORC1_SIGNALING", "PI3K_AKT", "GLYCOLYSIS",
              "DNA_REPAIR_CAPACITY", "HYPOXIA_HIF1A", "MEMBRANE_FLUIDITY_TRANSPORT"]:
        i = PW_INDEX[p]
        add([_relu(za[i]) * _relu(-fb[i]) + _relu(zb[i]) * _relu(-fa[i]),
             _relu(-fa[i]) * _relu(-fb[i])],
            [f"blockade::{p}", f"codown::{p}"])

    # -- block 7: redundancy and mutual buffering -----------------------
    # Both suppress the same essential pathway -> diminishing returns.
    redundant = float(np.sum(_relu(SURV) * w * np.minimum(_relu(-fa), _relu(-fb))))
    # One agent restores what the other removes -> antagonism.
    buffer_ab = float(np.sum(_relu(SURV) * w * _relu(-fa) * _relu(fb)))
    buffer_ba = float(np.sum(_relu(SURV) * w * _relu(-fb) * _relu(fa)))
    # Opposing directions on the same pathway, regardless of sign of use.
    opposition = float(np.sum(_relu(-fa * fb) * (np.abs(fa) > STRONG) * (np.abs(fb) > STRONG)))
    add([redundant, buffer_ab + buffer_ba, max(buffer_ab, buffer_ba), opposition],
        ["redundancy", "buffering_sum", "buffering_max", "opposition"])

    # -- block 8: cell x mechanism cross-terms --------------------------
    # Does the pair's combined perturbation land on programs this line is
    # actually running, and does the context pre-empt either agent?
    combo = (fa + fb) / 2.0
    add([float(np.sum(expr * combo)), float(np.sum(dep * np.abs(combo))),
         float(np.sum(_relu(expr) * _relu(-combo) * _relu(SURV))),
         float(np.sum(_relu(-expr) * _relu(-combo) * _relu(SURV))),
         float(np.sum(_relu(expr) * _relu(SURV) * (_relu(-fa) + _relu(-fb)))),
         # pre-existing resistance the pair fails to address
         float(np.sum(_relu(expr) * prot * (np.abs(fa) < 1.0) * (np.abs(fb) < 1.0)))],
        ["ctx_align", "dep_align", "ctx_hit_active", "ctx_hit_inactive",
         "ctx_suppress_active", "unaddressed_resistance"])

    x = np.asarray(feats, dtype=float)
    return (x, names) if return_names else x


def feature_names():
    from .celllines import CELL_LINES
    from .signatures import ALL_PERTS
    c = next(iter(CELL_LINES.values()))
    a, b = list(ALL_PERTS.values())[:2]
    return pair_features(c, a, b, return_names=True)[1]

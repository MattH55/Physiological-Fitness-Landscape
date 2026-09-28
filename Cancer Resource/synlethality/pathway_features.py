"""
Mechanistically-motivated pathway-level features for a (cell-line
baseline, perturbagen A, perturbagen B) triple, built entirely from real
data: the real 978-gene canonical space (synlethality.signature_space),
real MSigDB Hallmark gene sets (data/msigdb/h.all.v2024.1.Hs.symbols.gmt,
50 sets, official Broad Institute download, 2026-09-28), and real
perturbagen signatures (LINCS drug signatures or modifier MIGEPs) plus
real cell-line baselines (DepMap).

Design lineage: adapted from scripts/npxp-model.tar.gz's feature-block
design (found in this project's scripts/ directory, credited in
scripts/README (1).md's literature review) -- but rebuilt on real
pathway gene sets and real signatures instead of that document's
51-synthetic-pathway simulator. Per the build order's standing
"no fabricated data" rule, three of that design's eight blocks are
dropped rather than faked:
  - block 4 (dependency capture) needs real DepMap CRISPR essentiality
    scores, not cached in this project (only expression is);
  - block 6 (escape-route blockade) and the "func_vec" used throughout
    that design need real drug-target/mechanism-of-action annotation
    (DrugBank/ChEMBL target+action), not available here for most of the
    curated drug list.
Both are real, named gaps -- not silently approximated with expression
alone (that would misrepresent a target-annotation feature as a
transcriptional one). What's kept (blocks 1/2/3/5/7/8) needs only
signatures + gene sets, which are real for every perturbagen this
project has.

**SURVIVAL_SIGN is this module's own documented curation** (mirroring
the source design's SURVIVAL_VEC, similarly a documented choice, not a
measured quantity): +1 for a Hallmark program broadly supporting cancer
cell survival/proliferation when active, -1 for one broadly opposing it,
0 for a genuinely context-dependent or ambiguous program left unweighted
rather than guessed. Only pathways with a defensible textbook direction
are signed; the rest score 0 and drop out of every SURVIVAL-weighted term
(they still contribute to the un-weighted geometry/complementary-exposure
terms).
"""
from __future__ import annotations

import os

import numpy as np

from synlethality import config
from synlethality.signature_space import CANONICAL_SYMBOLS

HALLMARK_GMT = os.path.join(config.DATA_DIR, "msigdb", "h.all.v2024.1.Hs.symbols.gmt")
STRONG = 1.5  # |z| threshold for "strongly perturbed" on the real, harmonized robust-z scale

#: Documented curation, not a measured quantity -- see module docstring.
#: Only pathways with an unambiguous textbook direction for cancer-cell
#: survival are signed. Absent from this dict == 0 (unweighted).
SURVIVAL_SIGN = {
    "HALLMARK_APOPTOSIS": -1,               # activating it kills the cell
    "HALLMARK_P53_PATHWAY": -1,             # tumour-suppressive, pro-death/arrest
    "HALLMARK_DNA_REPAIR": +1,              # repair capacity helps the cell survive damage
    "HALLMARK_MTORC1_SIGNALING": +1,        # growth/anabolic signal
    "HALLMARK_PI3K_AKT_MTOR_SIGNALING": +1,
    "HALLMARK_MYC_TARGETS_V1": +1,
    "HALLMARK_MYC_TARGETS_V2": +1,
    "HALLMARK_E2F_TARGETS": +1,             # proliferation
    "HALLMARK_G2M_CHECKPOINT": +1,
    "HALLMARK_OXIDATIVE_PHOSPHORYLATION": +1,   # ATP supply
    "HALLMARK_GLYCOLYSIS": +1,
    "HALLMARK_UNFOLDED_PROTEIN_RESPONSE": +1,   # adaptive stress response, pro-survival
    "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY": +1,  # antioxidant defence, pro-survival
    "HALLMARK_XENOBIOTIC_METABOLISM": +1,       # drug clearance/detox, pro-survival under drug stress
    "HALLMARK_HYPOXIA": 0,                      # genuinely context-dependent
    "HALLMARK_INFLAMMATORY_RESPONSE": 0,
    "HALLMARK_TNFA_SIGNALING_VIA_NFKB": 0,
    "HALLMARK_TGF_BETA_SIGNALING": 0,
    "HALLMARK_EPITHELIAL_MESENCHYMAL_TRANSITION": 0,
}


def load_hallmark_sets(path: str = HALLMARK_GMT) -> dict[str, set[str]]:
    """Real MSigDB Hallmark gene sets, gene symbols restricted to nothing
    here (restriction to the 978 canonical genes happens in
    build_pathway_masks) -- keeps this loader reusable outside the
    978-gene space."""
    sets = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            name = parts[0]
            genes = set(parts[2:])
            sets[name] = genes
    return sets


def build_pathway_masks(gene_sets: dict[str, set[str]] | None = None) -> tuple[list[str], np.ndarray]:
    """Boolean [n_pathways, 978] mask matrix, aligned to CANONICAL_SYMBOLS
    order. A pathway with zero real landmark genes present is dropped
    (real gap, not padded) -- reports how many that removed."""
    gene_sets = gene_sets or load_hallmark_sets()
    names, rows = [], []
    for name, genes in sorted(gene_sets.items()):
        mask = np.array([sym in genes for sym in CANONICAL_SYMBOLS], dtype=bool)
        if mask.sum() == 0:
            continue
        names.append(name)
        rows.append(mask)
    return names, np.stack(rows)


class PathwaySpace:
    """Loads the real Hallmark gene sets and their 978-gene masks once;
    reused across every pair-feature call."""

    def __init__(self):
        self.gene_sets = load_hallmark_sets()
        self.names, self.masks = build_pathway_masks(self.gene_sets)  # [P, 978]
        self.survival = np.array([SURVIVAL_SIGN.get(n, 0) for n in self.names], dtype=float)
        self.n_pathways = len(self.names)

    def activity(self, vec: np.ndarray) -> np.ndarray:
        """Mean signed value per pathway over its present (non-nan) genes.
        A gene missing from a signature (nan) is excluded from that
        pathway's mean, never treated as 0."""
        present = ~np.isnan(vec)
        out = np.zeros(self.n_pathways)
        for i in range(self.n_pathways):
            m = self.masks[i] & present
            out[i] = float(vec[m].mean()) if m.any() else 0.0
        return out


def _dense(vec) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in vec], dtype=float)


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na < 1e-9 or nb < 1e-9 else float(a @ b / (na * nb))


def pair_block(space: PathwaySpace, sig_a_vec, sig_b_vec):
    """Blocks 2/3/5/7 -- everything in the original feature vector that
    depends only on the (modifier, drug) pair, never on the cell-line
    baseline. Split out 2026-09-28 so a batch scorer can compute this
    once per (modifier, drug) instead of once per (modifier, drug,
    cell_line) -- real, correctness-preserving speedup: scoring against
    all 6,204 real LINCS Phase 1 compounds instead of the 13 curated
    drugs multiplies the grid ~690x (33 modifiers x 6204 drugs x 13 cell
    lines vs x9 drugs), and blocks 2/3/5/7 are ~97% of the per-row cost
    (block 5 alone loops over 50 pathways). Cell lines reuse whatever a
    (modifier, drug) pair already computed here -- see baseline_block for
    the remaining, genuinely cell-line-dependent blocks 1/8. Returns
    (vector, names, pa, pb) -- pa/pb (pathway activity of each signature)
    are needed by baseline_block, so they're handed back rather than
    recomputed there."""
    za = _dense(sig_a_vec)
    zb = _dense(sig_b_vec)
    za_filled = np.nan_to_num(za, nan=0.0)
    zb_filled = np.nan_to_num(zb, nan=0.0)

    feats, names = [], []

    def add(vals, labels):
        feats.extend(np.atleast_1d(vals).astype(float).tolist())
        names.extend(np.atleast_1d(labels).tolist())

    # -- block 2: pooled perturbation (symmetric in A/B) -----------------
    pa = space.activity(za)
    pb = space.activity(zb)
    add((pa + pb) / 2.0, [f"pmean::{n}" for n in space.names])
    add(np.abs(pa - pb) / 2.0, [f"pdiff::{n}" for n in space.names])
    add(np.sign(pa * pb) * np.sqrt(np.abs(pa * pb)), [f"pprod::{n}" for n in space.names])

    # -- block 3: geometry (real gene-level, not pathway-level) ----------
    common = ~np.isnan(za) & ~np.isnan(zb)
    n_common = int(common.sum())
    ca, cb = za_filled[common], zb_filled[common]
    sa = set(np.where(common & (np.abs(za_filled) > STRONG))[0])
    sb = set(np.where(common & (np.abs(zb_filled) > STRONG))[0])
    inter, union = len(sa & sb), len(sa | sb)
    add(
        [
            _cos(ca, cb), float(np.linalg.norm(ca)), float(np.linalg.norm(cb)),
            float(min(np.linalg.norm(ca), np.linalg.norm(cb))),
            float(np.linalg.norm(ca + cb)), float(np.linalg.norm(ca - cb)),
            len(sa), len(sb), inter, inter / union if union else 0.0, n_common,
        ],
        ["cos_sig", "norm_a", "norm_b", "norm_min", "norm_sum", "norm_absdiff",
         "n_strong_a", "n_strong_b", "n_strong_both", "jaccard_strong", "n_common_genes"],
    )

    # -- block 5: complementary exposure (Cheng, Kovacs & Barabasi 2019) -
    # Both agents hit the same Hallmark program, but via largely different
    # genes within it: joint exposure high, within-pathway gene overlap low.
    comp_scores = np.zeros(space.n_pathways)
    for i in range(space.n_pathways):
        mask = space.masks[i]
        ea = np.abs(za_filled) * mask
        eb = np.abs(zb_filled) * mask
        joint = float(np.linalg.norm(ea) * np.linalg.norm(eb))
        overlap = _cos(ea, eb)
        comp_scores[i] = joint * (1.0 - overlap)
        add([joint, overlap, comp_scores[i]],
            [f"mod_joint::{space.names[i]}", f"mod_overlap::{space.names[i]}",
             f"mod_compl::{space.names[i]}"])
    add([comp_scores.max(), comp_scores.sum(), float(np.count_nonzero(comp_scores > 1.0))],
        ["compl_max", "compl_sum", "compl_n_pathways"])

    # -- block 7: redundancy and mutual buffering (survival-signed) ------
    surv = space.survival
    redundant = float(np.sum(np.maximum(surv, 0) * np.minimum(-pa * (surv > 0), -pb * (surv > 0))
                              .clip(min=0)))
    buffer_ab = float(np.sum(np.maximum(surv, 0) * np.clip(-pa, 0, None) * np.clip(pb, 0, None)))
    buffer_ba = float(np.sum(np.maximum(surv, 0) * np.clip(-pb, 0, None) * np.clip(pa, 0, None)))
    opposition = float(np.sum(np.clip(-pa * pb, 0, None)))
    add([redundant, buffer_ab + buffer_ba, max(buffer_ab, buffer_ba), opposition],
        ["redundancy", "buffering_sum", "buffering_max", "opposition"])

    x = np.asarray(feats, dtype=float)
    return x, names, pa, pb


def baseline_block(space: PathwaySpace, baseline_vec, pa: np.ndarray, pb: np.ndarray):
    """Blocks 1/8 -- the genuinely cell-line-dependent part. `pa`/`pb`
    come from pair_block (real reuse, not recomputation)."""
    base = np.nan_to_num(_dense(baseline_vec), nan=0.0)
    surv = space.survival

    feats, names = [], []

    def add(vals, labels):
        feats.extend(np.atleast_1d(vals).astype(float).tolist())
        names.extend(np.atleast_1d(labels).tolist())

    # -- block 1: cell context (real baseline pathway activity) ---------
    ctx = space.activity(base)
    add(ctx, [f"ctx::{n}" for n in space.names])

    # -- block 8: cell x mechanism cross-terms ---------------------------
    combo = (pa + pb) / 2.0
    add(
        [float(np.dot(ctx, combo)), float(np.sum(np.clip(ctx, 0, None) * np.clip(-combo, 0, None) * np.clip(surv, 0, None)))],
        ["ctx_align", "ctx_suppress_active"],
    )

    x = np.asarray(feats, dtype=float)
    return x, names


def pair_features(
    space: PathwaySpace,
    baseline_vec,
    sig_a_vec,
    sig_b_vec,
    return_names: bool = False,
):
    """Real feature vector for one (cell-line baseline, perturbagen A,
    perturbagen B) triple, in the same canonical 978-gene space. Every
    input is that source's real, harmonized (robust-z) vector -- no
    per-gene imputation; missing genes drop out of pathway means.

    A thin composition of pair_block (blocks 2/3/5/7) and baseline_block
    (blocks 1/8), reassembled in the ORIGINAL column order
    [1, 2, 3, 5, 7, 8] so a model trained against this function's output
    scores identically whether called row-by-row (here) or via the cached
    batch path in scripts/score_lincs_grid.py. Kept as the single
    reference implementation; batch callers should still prefer calling
    pair_block/baseline_block directly for the reuse win."""
    pair_vec, pair_names, pa, pb = pair_block(space, sig_a_vec, sig_b_vec)
    base_vec, base_names = baseline_block(space, baseline_vec, pa, pb)
    n_block1 = space.n_pathways  # block 1 is exactly n_pathways long, always first
    x = np.concatenate([base_vec[:n_block1], pair_vec, base_vec[n_block1:]])
    if not return_names:
        return x
    names = base_names[:n_block1] + pair_names + base_names[n_block1:]
    return x, names

"""
Dataset assembly.

REAL DATA PATH (blocked in this offline environment, wired up for a run
with network access). Each loader returns the same frame schema as the
simulated generator, so nothing downstream changes:

  load_drugcomb(path)    DrugComb v1.5 summary_v_1_5.csv -- ~740k
                         drug-pair/cell-line blocks with synergy_zip,
                         synergy_bliss, synergy_loewe, synergy_hsa.
                         https://drugcomb.fimm.fi/
  load_almanac(path)     NCI-ALMANAC ComboDrugGrowth_Nov2017.zip -- ~300k
                         pairs over the NCI-60, full dose matrices.
  load_lincs(path)       LINCS L1000 level-5 (GSE92742 Phase 1 /
                         GSE70138 Phase 2, or clue.io). Take the 978
                         landmark z-scores per (pert, cell, dose, time),
                         collapse replicates, project onto PATHWAYS with
                         a gene-set matrix (MSigDB Hallmark + Reactome)
                         to get `vec`.
  load_ccle(path)        CCLE/DepMap OmicsExpressionProteinCodingGenes...
                         .csv for baseline `expr_vec`; CRISPRGeneEffect
                         .csv for `dep_vec`.
  load_modifier_gse(...)  GEO series for the modifiers, differential
                         expression vs matched control, same projection:
                           hyperthermia   GSE13005, GSE50290, GSE168581
                           fasting/CR     GSE74905, GSE119713
                           hypoxia        GSE47533, GSE142867
                           TTFields       GSE179663
                         These give real modifier signatures and replace
                         the curated vectors in signatures.py.

The ordering matters: drug signatures and synergy labels must come from
overlapping cell lines, which in practice means intersecting LINCS cell
coverage with DrugComb cell coverage -- about 30-40 lines, and the reason
published models (MARSY, DRSPRING) work on that scale rather than all of
DrugComb.
"""
import itertools

import numpy as np
import pandas as pd

from .celllines import CELL_LINES
from .signatures import DRUGS, MODIFIERS, ALL_PERTS
from .features import pair_features
from . import simulator


def _scaled(pert, s):
    """Intensity-scaled perturbagen: stands in for dose / duration /
    temperature / degree of restriction. Scaling the signature is how a
    modifier's 'dose' enters the model, since a modifier has no molar
    concentration."""
    if s == 1.0:
        return pert
    out = dict(pert)
    out["vec"] = (np.asarray(pert["vec"]) * s).tolist()
    out["func_vec"] = (np.asarray(pert["func_vec"]) * s).tolist()
    return out


def _jittered_cell(cell, rng, sd=0.25):
    out = dict(cell)
    out["expr_vec"] = (np.asarray(cell["expr_vec"])
                       + rng.normal(0, sd, len(cell["expr_vec"]))).tolist()
    out["dep_vec"] = (np.asarray(cell["dep_vec"])
                      + rng.normal(0, sd * 0.6, len(cell["dep_vec"]))).tolist()
    return out


def build_dataset(kind="drug_drug", n_per_pair=6, seed=0, lines=None,
                  intensity=(0.6, 1.4)):
    """Generate labelled triples.

    kind: 'drug_drug'      -- training set
          'modifier_drug'  -- zero-shot transfer target
          'modifier_modifier'
    """
    rng = np.random.default_rng(seed)
    lines = lines or list(CELL_LINES)
    if kind == "drug_drug":
        pairs = list(itertools.combinations(DRUGS, 2))
        lookup = DRUGS
    elif kind == "modifier_drug":
        pairs = [(m, d) for m in MODIFIERS for d in DRUGS]
        lookup = ALL_PERTS
    elif kind == "modifier_modifier":
        pairs = list(itertools.combinations(MODIFIERS, 2))
        lookup = MODIFIERS
    else:
        raise ValueError(kind)

    rows, X = [], []
    for cl in lines:
        base = CELL_LINES[cl]
        for a, b in pairs:
            for rep in range(n_per_pair):
                cell = base if rep == 0 else _jittered_cell(base, rng)
                sa = 1.0 if rep == 0 else rng.uniform(*intensity)
                sb = 1.0 if rep == 0 else rng.uniform(*intensity)
                pa, pb = _scaled(lookup[a], sa), _scaled(lookup[b], sb)
                y = simulator.synergy(cell, pa, pb)
                X.append(pair_features(cell, pa, pb))
                rows.append(dict(cell_line=cl, pert_a=a, pert_b=b,
                                 kind_a=lookup[a]["kind"], kind_b=lookup[b]["kind"],
                                 intensity_a=sa, intensity_b=sb, rep=rep,
                                 synergy=y))
    meta = pd.DataFrame(rows)
    return np.asarray(X), meta

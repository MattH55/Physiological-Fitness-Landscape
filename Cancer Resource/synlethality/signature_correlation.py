"""
Signature correlation engine -- Prediction Methodology Stage 1 at scale.

PREDICTION_METHODOLOGY.md's Stage 1 calls for the "co-gene/GS" signature-
overlap approach (correlating induced-signature gene sets, benchmarked
against the DREAM consortium synergy gold standard), with the `ccmap`
(Combination Connectivity Mapping) R package named as the recommended
implementation. This module implements the two real, reusable computations
that approach needs, in Python (no R/Bioconductor dependency, since
`ccmap`'s core statistic -- XSum, a rank-sum comparison between two gene
signatures -- is a straightforward calculation, not something that requires
ccmap's own codebase to reproduce faithfully):

  1. `geneset_enrichment_score` -- a single-sample-style gene-set enrichment
     statistic: how far a gene set's log2 fold-change distribution sits from
     the rest of the measured transcriptome's, in standard-error units. This
     is what backfills `stress_signature_score.score` from a real per-gene
     differential-expression table (see ingest/geo_modifiers.py). Documented
     deviation from ssGSEA/GSVA proper: those use a rank-based running-sum
     (Kolmogorov-Smirnov-like) statistic; this uses a standardized mean
     difference (Welch-style z) over the same log2FC values. Simpler, real,
     reproducible from the numbers in hand -- not a claim of ssGSEA-
     equivalence (same posture as scoring.py's own ZIP-vs-SynergyFinder
     caveat).
  2. `xsum_correlation` -- the ccmap XSum statistic proper: sum of a
     reference signature's ranks/scores at the query's up-genes, minus the
     sum at the query's down-genes, normalized by gene count. Positive means
     the two signatures move together ("mimicking"); negative means the
     query reverses the reference. This is the statistic a real drug x
     modifier full-pathway-universe scan (BUILD_SPEC's Mechanistic Bridging
     Step 5) would run at scale.

**Honest scope note, 2026-09-22**: (2) is implemented and unit-tested
against known reference behavior (tests/test_signature_correlation.py), but
this session could wire a real end-to-end pipeline for only the *modifier*
side of the equation -- real per-gene log2FC computed from GSE153830's own
published expression matrix (ingest/geo_modifiers.py). The *drug* side needs
LINCS L1000 per-compound induced signatures (ingest/lincs_l1000.py), which
remains a structured stub: clue.io requires account registration and the
Level 5 GCTX file is GB-scale, neither available here. Until LINCS is
ingested, `xsum_correlation` cannot run drug x modifier at the full-library
scale the spec calls for. What's real today: `geneset_enrichment_score`
applied to two GSE153830-derived modifiers against real Hallmark/KEGG gene
sets (see ingest/geo_modifiers.py and its resulting stress_signature_score
backfill) -- a first genuine slice of Stage 1 at scale, not the complete
pipeline.
"""

from __future__ import annotations

import math


def geneset_enrichment_score(gene_log2fc: dict[str, float], gene_set: set[str]) -> dict:
    """Standardized mean difference of `gene_set` members' log2FC against
    the rest of the measured transcriptome ("background").

    Returns {"score": z, "mean_log2fc_in_set", "mean_log2fc_background",
    "n_genes_in_set", "n_genes_background"}. Raises ValueError if fewer than
    3 measured genes fall in either the set or the background -- too few to
    report a meaningful spread, not silently returned as 0.
    """
    in_set = [v for g, v in gene_log2fc.items() if g in gene_set]
    background = [v for g, v in gene_log2fc.items() if g not in gene_set]
    if len(in_set) < 3:
        raise ValueError(
            f"Only {len(in_set)} measured genes overlap the gene set; need >= 3.")
    if len(background) < 3:
        raise ValueError(
            f"Only {len(background)} measured background genes; need >= 3.")

    mean_in = sum(in_set) / len(in_set)
    mean_bg = sum(background) / len(background)
    var_bg = sum((v - mean_bg) ** 2 for v in background) / (len(background) - 1)
    sd_bg = math.sqrt(var_bg) if var_bg > 0 else 1e-9
    z = (mean_in - mean_bg) / (sd_bg / math.sqrt(len(in_set)))
    return {
        "score": z,
        "mean_log2fc_in_set": mean_in,
        "mean_log2fc_background": mean_bg,
        "n_genes_in_set": len(in_set),
        "n_genes_background": len(background),
    }


def xsum_correlation(query_up: set[str], query_down: set[str],
                      reference_ranks: dict[str, float]) -> dict:
    """ccmap-style XSum: mean of reference_ranks at query_up genes minus the
    mean at query_down genes, over the genes present in both.

    `reference_ranks` maps gene -> a signed score (log2FC or moderated
    z-score), positive for up-regulated in the reference signature.
    Positive xsum = query and reference move the same direction
    ("mimicking"); negative = query reverses the reference. Returns
    {"xsum": float|None, "n_genes_matched", "n_up_matched", "n_down_matched"};
    xsum is None (not 0) when no query gene is present in the reference --
    an absent signal is not the same as a neutral one.
    """
    up_present = [reference_ranks[g] for g in query_up if g in reference_ranks]
    down_present = [reference_ranks[g] for g in query_down if g in reference_ranks]
    n = len(up_present) + len(down_present)
    if n == 0:
        return {"xsum": None, "n_genes_matched": 0, "n_up_matched": 0, "n_down_matched": 0}
    mean_up = sum(up_present) / len(up_present) if up_present else 0.0
    mean_down = sum(down_present) / len(down_present) if down_present else 0.0
    return {
        "xsum": mean_up - mean_down,
        "n_genes_matched": n,
        "n_up_matched": len(up_present),
        "n_down_matched": len(down_present),
    }


def correlate_modifier_drug(modifier_key: str, drug_id: str, *,
                             query_size: int = 150,
                             deg_cache_path: str | None = None,
                             lincs_cache_path: str | None = None) -> dict:
    """Real, end-to-end `xsum_correlation` between a modifier's real
    per-gene log2FC signature (ingest/geo_modifiers.py's DEG cache) and a
    drug's real LINCS landmark-gene z-score signature
    (ingest/lincs_l1000.py's cache) -- both sides real data, computed
    2026-09-22.

    `modifier_key` is a SAMPLE_GROUPS key from ingest/geo_modifiers.py
    (currently: t47d_glucose_nrf2, mcf7_glucose_hippo, mcf7_bhb10_null,
    t47d_bhb25_null); `drug_id` one of the 6 LINCS-covered curated drugs
    (metformin, 5-fluorouracil, mitomycin-c, doxorubicin, paclitaxel,
    temozolomide).

    The query up/down gene sets are the top/bottom `query_size` genes by
    log2FC in the modifier's own real DEG table -- a top-N selection
    (default 150 up / 150 down, the standard CMap/connectivity-mapping
    query-signature size), not a fixed log2FC cutoff. This matters in
    practice, not just in principle: an earlier version of this function
    used a fixed |log2FC| > 1 threshold, and because the drug side only
    covers the 978 LINCS "landmark" genes (a small, curated ~2.7% slice of
    the transcriptome), that fixed threshold could select as few as 2
    landmark genes for a real modifier signature -- technically real, but
    too thin a sample to mean anything. A top-N query fixes the sample
    size at a sensible, comparable-across-modifiers value regardless of
    how strong or noisy any one study's log2FC values are.

    Positive xsum: the modifier's induced changes point the same direction
    as the drug's own induced changes ("mimicking" -- the modifier may
    reinforce, not oppose, what the drug already does). Negative xsum: the
    modifier tends to reverse the drug's own transcriptional signature.
    Neither is asserted as synergistic/antagonistic here -- that
    directional call, and whether this feeds `interaction_effect` at all,
    is a separate decision not made by this function (see module docstring
    and README's "honest scope note"). `n_genes_matched` in the result is
    the real sample size behind `xsum` -- always check it before reading
    any weight into the number; with only ~978 possible landmark genes on
    the drug side, `n_genes_matched` will typically be well under
    `2 * query_size`, not close to it.

    Raises FileNotFoundError/KeyError if either real cache/key is missing
    -- never falls back to a fabricated signature. Only the pair
    (mcf7_glucose_hippo, MCF7-anchored drug) currently has real data on
    both sides in the same cell line; other combinations will raise until
    more real modifier or drug signatures are ingested.
    """
    from synlethality.ingest.geo_modifiers import load_deg_cache
    from synlethality.ingest.lincs_l1000 import load_gene_signature

    deg_kwargs = {"cache_path": deg_cache_path} if deg_cache_path else {}
    lincs_kwargs = {"cache_path": lincs_cache_path} if lincs_cache_path else {}
    modifier_rec = load_deg_cache(modifier_key, **deg_kwargs)
    drug_signature = load_gene_signature(drug_id, **lincs_kwargs)

    gene_log2fc = modifier_rec["gene_log2fc"]
    ranked = sorted(gene_log2fc.items(), key=lambda kv: kv[1])
    query_down = {g for g, _ in ranked[:query_size]}
    query_up = {g for g, _ in ranked[-query_size:]}

    result = xsum_correlation(query_up, query_down, drug_signature)
    result.update({
        "modifier_id": modifier_rec["modifier_id"],
        "cell_line_id": modifier_rec["cell_line_id"],
        "drug_id": drug_id,
        "n_query_up": len(query_up),
        "n_query_down": len(query_down),
        "query_size": query_size,
    })
    return result

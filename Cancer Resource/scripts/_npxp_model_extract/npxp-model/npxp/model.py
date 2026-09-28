"""
Predictor and evaluation protocol.

Model: gradient-boosted trees on the mechanistic feature blocks. Chosen
over a deep net deliberately -- with the label counts available for
modifier work (tens of real quantitative labels, or a few thousand
simulated), a 401-feature GBM is the honest capacity choice, and
TreeCombo (Janizek et al.) showed boosted trees match DeepSynergy on the
same features anyway. Swap in an MLP once real DrugComb labels are
loaded and the training set is ~10^5.

Evaluation splits, in increasing difficulty -- the field's CV1/CV2/CV3
convention:
  random        rows shuffled. Optimistic: the same pair appears in train
                and test at a different intensity. Reported for
                comparability, not believed.
  unseen_pair   whole (A,B) pairs held out.
  unseen_pert   every row containing a held-out perturbagen is removed
                from training. This is the split that predicts zero-shot
                modifier performance.
  unseen_cell   whole cell lines held out.
And the one that matters here:
  transfer      train on drug x drug ONLY, test on modifier x drug.
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold, KFold


def make_model(seed=0):
    return HistGradientBoostingRegressor(
        loss="absolute_error",        # labels are heavy-tailed
        max_iter=500, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=20, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.15,
        random_state=seed)


def _metrics(y, yhat):
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    out = {"n": len(y),
           "pearson": float(pearsonr(y, yhat)[0]) if len(y) > 2 else np.nan,
           "spearman": float(spearmanr(y, yhat)[0]) if len(y) > 2 else np.nan,
           "mae": float(np.mean(np.abs(y - yhat))),
           "rmse": float(np.sqrt(np.mean((y - yhat) ** 2)))}
    # sign agreement on rows where the truth is not near-additive
    m = np.abs(y) > 1.0
    out["sign_acc"] = float(np.mean(np.sign(y[m]) == np.sign(yhat[m]))) if m.sum() else np.nan
    # top-decile enrichment: of the rows the model ranks highest, what
    # fraction are truly in the top decile of synergy?
    k = max(1, len(y) // 10)
    top_true = set(np.argsort(-y)[:k])
    top_pred = np.argsort(-yhat)[:k]
    out["precision_at_10pct"] = float(np.mean([i in top_true for i in top_pred]))
    return out


def cross_validate(X, meta, split="random", n_splits=5, seed=0):
    y = meta["synergy"].to_numpy()
    if split == "random":
        splitter, groups = KFold(n_splits, shuffle=True, random_state=seed), None
    else:
        if split == "unseen_pair":
            groups = meta.apply(
                lambda r: "|".join(sorted([r.pert_a, r.pert_b])), axis=1).to_numpy()
        elif split == "unseen_pert":
            # group by the alphabetically-first member so that holding a
            # group out removes that perturbagen from training entirely
            groups = meta[["pert_a", "pert_b"]].min(axis=1).to_numpy()
        elif split == "unseen_cell":
            groups = meta["cell_line"].to_numpy()
        else:
            raise ValueError(split)
        n_splits = min(n_splits, len(np.unique(groups)))
        splitter = GroupKFold(n_splits)

    preds = np.full(len(y), np.nan)
    for tr, te in splitter.split(X, y, groups):
        m = make_model(seed)
        m.fit(X[tr], y[tr])
        preds[te] = m.predict(X[te])
    res = _metrics(y, preds)
    res["split"] = split
    return res, preds


def fit_full(X, meta, seed=0):
    m = make_model(seed)
    m.fit(X, meta["synergy"].to_numpy())
    return m


def permutation_importance_blocks(model, X, y, names, n_repeat=3, seed=0):
    """Block-level permutation importance: shuffle a whole feature block
    at once. Individual features are collinear by construction, so
    per-feature importance is misleading."""
    rng = np.random.default_rng(seed)
    def block_of(n):
        if "::" in n:
            return n.split("::")[0]
        return {"cos_func": "geometry", "cos_expr": "geometry",
                "cos_absfunc": "geometry"}.get(n, "scalar_" + n.split("_")[0])
    blocks = {}
    for i, n in enumerate(names):
        blocks.setdefault(block_of(n), []).append(i)
    base = np.mean(np.abs(y - model.predict(X)))
    rows = []
    for b, idx in blocks.items():
        drops = []
        for _ in range(n_repeat):
            Xp = X.copy()
            for j in idx:
                Xp[:, j] = rng.permutation(Xp[:, j])
            drops.append(np.mean(np.abs(y - model.predict(Xp))) - base)
        rows.append({"block": b, "n_features": len(idx),
                     "mae_increase": float(np.mean(drops))})
    return pd.DataFrame(rows).sort_values("mae_increase", ascending=False)

"""Generate data, evaluate the predictor, test zero-shot transfer."""
import json, pickle, time
import numpy as np, pandas as pd
from npxp.data import build_dataset
from npxp.features import feature_names
from npxp import model as M

t0 = time.time()
out = {}

print("building drug x drug training set ...", flush=True)
Xd, md = build_dataset("drug_drug", n_per_pair=6, seed=1)
print(f"  {Xd.shape[0]} labels, {Xd.shape[1]} features  [{time.time()-t0:.0f}s]", flush=True)

print("building modifier x drug transfer set ...", flush=True)
Xm, mm = build_dataset("modifier_drug", n_per_pair=3, seed=2)
print(f"  {Xm.shape[0]} labels  [{time.time()-t0:.0f}s]", flush=True)

np.save("cache_Xd.npy", Xd); md.to_csv("cache_md.csv", index=False)
np.save("cache_Xm.npy", Xm); mm.to_csv("cache_mm.csv", index=False)

print("\n=== within-domain cross-validation (drug x drug) ===", flush=True)
cv = []
for split in ["random", "unseen_pair", "unseen_pert", "unseen_cell"]:
    res, _ = M.cross_validate(Xd, md, split=split)
    cv.append(res)
    print(f"  {split:13s} n={res['n']:5d} r={res['pearson']:.3f} "
          f"rho={res['spearman']:.3f} MAE={res['mae']:6.2f} "
          f"sign={res['sign_acc']:.3f} P@10%={res['precision_at_10pct']:.3f}", flush=True)
out["cv"] = cv

print("\n=== zero-shot transfer: train drug x drug -> test modifier x drug ===", flush=True)
mdl = M.fit_full(Xd, md)
pred = mdl.predict(Xm)
tr = M._metrics(mm["synergy"].to_numpy(), pred)
tr["split"] = "transfer_drugdrug_to_modifierdrug"
print(f"  n={tr['n']} r={tr['pearson']:.3f} rho={tr['spearman']:.3f} "
      f"MAE={tr['mae']:.2f} sign={tr['sign_acc']:.3f} P@10%={tr['precision_at_10pct']:.3f}", flush=True)
out["transfer"] = tr

# per-modifier breakdown: does transfer hold for every modifier class?
mm = mm.assign(pred=pred)
per = (mm.groupby("pert_a")
         .apply(lambda g: pd.Series(M._metrics(g.synergy, g.pred)), include_groups=False)
         .reset_index())
print("\n  per-modifier transfer:")
print(per[["pert_a","n","pearson","spearman","mae","sign_acc"]].to_string(index=False))
out["per_modifier"] = per.to_dict("records")

# baseline: how much better than predicting the training mean, or than
# using only the two agents' single-agent potency?
mu = md.synergy.mean()
base = M._metrics(mm.synergy, np.full(len(mm), mu))
print(f"\n  constant-baseline MAE={base['mae']:.2f}  (model {tr['mae']:.2f})")
out["baseline_constant"] = base

print("\n=== feature block importance (transfer set) ===", flush=True)
names = feature_names()
imp = M.permutation_importance_blocks(mdl, Xm, mm.synergy.to_numpy(), names)
print(imp.head(14).to_string(index=False))
out["block_importance"] = imp.to_dict("records")

with open("model.pkl","wb") as f: pickle.dump(mdl, f)
mm.to_csv("transfer_predictions.csv", index=False)
imp.to_csv("block_importance.csv", index=False)
with open("results.json","w") as f: json.dump(out, f, indent=2, default=float)
print(f"\ndone [{time.time()-t0:.0f}s]")

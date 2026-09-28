"""Fast end-to-end check: 2 cell lines, 1 replicate. Confirms the
pipeline runs and that zero-shot transfer is wired correctly. Numbers are
NOT meaningful at this size -- use run_experiments.py for real runs."""
import numpy as np
from npxp.data import build_dataset
from npxp.features import feature_names
from npxp import model as M

LINES = ["U87MG", "HCT116"]
Xd, md = build_dataset("drug_drug", n_per_pair=1, seed=1, lines=LINES)
Xm, mm = build_dataset("modifier_drug", n_per_pair=1, seed=2, lines=LINES)
print(f"train {Xd.shape}  transfer {Xm.shape}  features {len(feature_names())}")

res, _ = M.cross_validate(Xd, md, split="unseen_pert", n_splits=4)
print("unseen-perturbagen CV:",
      {k: round(v, 3) for k, v in res.items() if isinstance(v, float)})

mdl = M.fit_full(Xd, md)
pred = mdl.predict(Xm)
tr = M._metrics(mm.synergy.to_numpy(), pred)
print("zero-shot drug->modifier:",
      {k: round(v, 3) for k, v in tr.items() if isinstance(v, float)})

mm = mm.assign(pred=pred)
top = mm.sort_values("pred", ascending=False).head(10)
print("\ntop predicted modifier x drug:")
print(top[["cell_line", "pert_a", "pert_b", "pred", "synergy"]].to_string(index=False))

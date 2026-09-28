# Phase 6 report — zero-shot transfer (GCN)

Built 2026-09-28T02:19:36.536773+00:00.

Trained on the same real 2924-pair Phase 4 corpus (ALMANAC + DrugComb, mimetic-anchored) Phase 5 used, with the same leave-one-cell-line-out and leave-one-drug-out validation and the same Bliss-independence baseline. The architecture is different: a DRUGSYNC-style GCN on the real STRING PPI graph (node features = [signature_A, signature_B], real cell-line baseline concatenated before the FC head), not the flat GBT/dual-arm-MLP models Phase 5 tried.

**Gate 6: FAILED.** Bliss-independence RMSE: 0.1105. GCN RMSE, cell-line-out: 0.1130. GCN RMSE, drug-out: 0.1098. Beats Bliss on both splits: False.

The GCN did not beat Bliss independence under both cross-validation schemes. That is the result, not a rerun condition. Per the build order's own rule, no `tier_2b_model_predicted` rows are written while Gate 6 fails. Real modifier x drug x cell-line predictions were still generated from a model trained on the full corpus and saved to `data/lincs/phase6_predictions.json`, explicitly marked `validated: false` -- extrapolations for inspection, not curated evidence.

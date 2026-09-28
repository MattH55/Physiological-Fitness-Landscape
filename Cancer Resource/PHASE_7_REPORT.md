# Phase 7 report — mechanistic pathway features + GBT

Built 2026-09-28T15:22:25.622267+00:00.

Trained on the same real 2924-pair Phase 4 corpus (ALMANAC + DrugComb, mimetic-anchored) Phases 5 and 6 used, with the same leave-one-cell-line-out / leave-one-drug-out validation and the same Bliss-independence baseline. The features are new: 370 real mechanistic features built from real MSigDB Hallmark gene sets (cell-context pathway activity, pooled-perturbation pathway summaries, signature geometry, Cheng-et-al.-2019 complementary exposure, survival-signed redundancy/buffering, cell x mechanism cross terms) -- see synlethality/pathway_features.py.

**Gate 7: PASSED.** Bliss-independence RMSE: 0.1105. GBT RMSE, cell-line-out: 0.1092 (90% interval coverage 0.884). GBT RMSE, drug-out: 0.1082 (90% interval coverage 0.823). Beats Bliss on both splits: True. Intervals near nominal (0.85-0.95): False.

**This is not the same as the build order's full Gate 6 acceptance test.** That test also requires checking predictions against the real quantitative anchor labels (the HIPEC/Kusumoto/stiffness TER and IC50-fold-shift values in synlethality/tests/test_seed.py's REAL_COMBINED_EFFECT_METRICS). That check is not applicable here: none of those anchor modifiers have a real transcriptomic signature in data/modifier_signatures/library.json (they are literature-only curated modifiers, no matching GEO series), and their metric (TER / survival-slope ratio / IC50 fold-shift) is not the same quantity as this model's training target (mean Bliss excess of survival fraction). This is a real, structural gap in what can be validated here -- not a skipped step, and not grounds to write tier_2b_model_predicted rows on the strength of the RMSE result alone.

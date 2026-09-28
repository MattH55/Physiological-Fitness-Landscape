# Phase 5 report — model and validation

Built 2026-09-27T18:21:37.196549+00:00.

Phase 4 did not pass its size gate. This comparison uses the 2924 pairs and 56 cell lines that were featurized. The target is mean Bliss excess. Predicting 0 is the Bliss independence baseline.

**Gate 5: FAILED.** Chosen model: `b_bliss`. Beats Bliss on both splits: False. 90% intervals near nominal: True.

| Model | Cell-line-out RMSE | Drug-out RMSE | Cell-line-out coverage | Drug-out coverage |
| --- | ---: | ---: | ---: | ---: |
| (a) global mean | 0.1115 | 0.1106 | 0.893 | 0.877 |
| (b) Bliss independence | 0.1105 | 0.1105 | 0.893 | 0.878 |
| (c) gradient-boosted trees | 0.1184 | 0.1093 | 0.887 | 0.848 |
| (d) dual-arm network | 0.4685 | 2.1831 | 0.949 | 0.404 |

The learned models did not beat Bliss independence under both cross-validation schemes. That is the result, not a rerun condition.

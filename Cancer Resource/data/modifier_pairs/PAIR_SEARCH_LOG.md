# Modifier-pair label search log

2026-09-27. `modifier_pairs.csv` is still empty. This is not an oversight
-- it is the honest result of a real search, logged here per this
project's standing rule against fabricating labels (see the DRUGSYNC-NP
build spec's "Training labels" section: "Do NOT fabricate interaction
labels... If no pairwise experimental labels exist yet, implement the
complete inference/data pipeline but do not claim that the model has
learned interaction prediction.")

## What "usable" means here

A row needs: two modifiers that were **applied together** in a real
experiment (not two independent single-modifier studies compared after
the fact), with a **measured combined outcome**, where **both modifiers
already have a real MIGEP** in `data/modifier_signatures/library.json`
(so the pair can actually be featurized against the real PPI graph) --
or, failing that, a same-species/same-tissue combined study that could
justify adding a new MIGEP alongside the label.

## Candidates found, and why each was not added

1. **Cold acclimation vs. exercise training, human vastus lateralis**
   (PMID 32887608, PMC7487556, *BMC Med Genomics* 2020, real, PMC full
   text pulled). Real, relevant-sounding title -- but on reading it: cold
   acclimation was studied in 8 T2D patients and exercise training in a
   *different* cohort of 20 healthy subjects. The two modifiers were
   never applied together; the paper computes cross-study transcriptomic
   *overlap* (Venn/RRHO) between two independent single-modifier
   datasets. That is real and useful, but it is **transcriptomic
   similarity, not a measured interaction outcome** -- the build spec
   explicitly warns against this exact conflation ("Do not treat
   gene-expression similarity as proof of synergy... Clearly
   distinguish: experimental interaction, predicted interaction,
   transcriptomic similarity"). Not added as a pair label. (Real finding
   worth keeping on record: significant overlap in *upregulated* genes,
   concentrated in extracellular-matrix-remodeling pathways, not in
   insulin-signaling/glucose-metabolism pathways; no significant overlap
   in downregulated genes.)

2. **Fasting + exercise, rat gastrocnemius/plantaris** (PMID 10827011,
   *Am J Physiol Endocrinol Metab* 2000, not in PMC -- real abstract
   pulled via PubMed's own E-utilities). This *is* a real combined-
   exposure experiment: rats were fasted, and a subset also ran on a
   treadmill (two 2-h bouts) during the first 8h of the fast. Real,
   measured, qualitatively antagonistic interaction: exercise attenuated
   the 24h fasting-induced transcriptional activation of UCP3, LPL, CPT
   I, and LCAD in red gastrocnemius and plantaris muscle (nuclear run-on,
   not microarray/RNA-seq). Not added, for two real reasons: (a) rat, not
   human -- none of this project's 33 real MIGEPs are rat-derived; (b)
   nuclear run-on transcription-rate data for 4 named genes is not
   commensurable with a 978-gene microarray/RNA-seq MIGEP -- there is no
   real MIGEP for either arm of this study to featurize against the PPI
   graph. Recorded here as a real, directionally-informative finding
   (fasting x exercise -> antagonistic on lipid-metabolism genes), not as
   a training row.

## Conclusion

No real, usable modifier-pair label was found this session. This appears
to be a genuine, structural data gap -- non-pharmacological interventions
are overwhelmingly studied one at a time (the same finding this
project's other, parallel effort reached independently for the
drug-modifier TER literature: see `data/thermal_ter/ter_corpus.json`'s
own search log). The complete inference pipeline (MIGEP -> PPI graph ->
GCN -> scalar) is real and runs end to end on real data
(`scripts/demo_drugsync_np.py`); it has not been trained on any real
interaction label, and no claim is made that it predicts real modifier
interactions.

## Where to look next (not yet done)

- Multi-arm human intervention trials that explicitly cross two of this
  library's 33 real modifiers in the same subjects (e.g. a fasting x
  cold-exposure or exercise x heat-exposure factorial design) with
  transcriptomic readout.
- GEO/ArrayExpress series search restricted to factorial/combined designs
  (search terms like "combined intervention", "interaction effect",
  "factorial design" alongside each modifier keyword) rather than
  single-modifier keyword search, which mostly surfaces single-modifier
  studies or post-hoc cross-study comparisons like candidate 1 above.

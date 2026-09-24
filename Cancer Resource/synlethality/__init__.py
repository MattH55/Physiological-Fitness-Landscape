"""
Combinatorial Fitness Landscape — Drug × Non-Pharmacological Modifier Interactions.

A browsable, queryable, evidence-graded interaction database cataloguing how
non-pharmacological interventions (dietary/metabolic, thermal, hypoxic, and
similar stressors) modify the fitness/death response of cancer cell lines to
pharmacological agents.

Every claim traces back to a cited source and an explicit evidence tier:
  - Tier 1 (direct): combination tested empirically in the same study.
  - Tier 2 (inferred): drug response and modifier response measured separately,
    joined via shared cell line and biologically plausible shared mechanism.
  - Tier 3 (mechanism-only): signature overlap only; no death/viability readout
    for either factor in combination.
"""

__version__ = "0.1.0"

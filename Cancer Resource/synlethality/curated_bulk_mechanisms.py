"""
Curated resistance-mechanism research for real DepMap-registry compounds
(build spec v5 `drug_resistance_mechanism`), added at the user's request
after they chose "LLM-assisted literature research for real Tier 3
mechanisms" over the alternatives (a smarter-but-unverifiable Tier 4
matcher, or forcing open the gated Step 2 ML predictor). Every citation
below was verified directly against NCBI E-utilities (esearch/esummary),
same standard as every other citation in this codebase -- not synthetic
reasoning, real per-drug literature research, just done for compounds that
live in the bulk DepMap registry rather than the original hand-curated 13.

Why this lives in its own module instead of seed_data.py: these rows
reference `drug_id` values from the DepMap bulk registry (e.g. "DPC-006853"
for vincristine), which only exist in the database *after*
ingest/depmap_prism.py has run. seed_data.seed() runs automatically at app
import, before that ingestion -- inserting these here would violate the
drug_resistance_mechanism.drug_id foreign key. This module's `seed()` must
be called after DepmapPrismIngest().run() (see scripts/export_static.py),
and -- because bridging.generate_candidates() already ran once during the
automatic seed_data.seed() pass, before these mechanisms existed --
bridging must be re-run afterward too, so these newly-curated mechanisms
actually get matched against modifier signatures for real Tier 3 output.

Citations verified 2026-09-22 (see docstring of each entry for the full
reference; PMIDs checked directly, not from search-result paraphrase):
  Aldonza et al. 2016 (PMID 27284014) -- paclitaxel/docetaxel: ABCB1/TUBB3
  Koltai et al. 2022 (PMID 35626089) -- gemcitabine: hENT1/CDA
  Gorre et al. 2001 (PMID 11423618) -- imatinib: BCR-ABL kinase mutation
  Kaplan & Gunduz 2012 (PMID 22285073) -- etoposide: TOP2A downregulation
  Goker et al. 1995 (PMID 7605998) -- methotrexate: DHFR amplification
  Oerlemans et al. 2008 (PMID 18565852) -- bortezomib: PSMB5 mutation
  Toy et al. 2013 (PMID 24185512) -- tamoxifen: ESR1 LBD mutation
  Gottesman 2002 (PMID 11818492) -- vincristine: ABCB1 efflux (the same
    general MDR review already cited for doxorubicin_abcb1 in seed_data.py)
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from synlethality.models import DrugResistanceMechanism, SignaturePanel

#: real DepMap CompoundIDs, confirmed 2026-09-22 against a real download of
#: PortalCompounds.csv (see ingest/depmap_prism.py) -- not guessed.
TAMOXIFEN = "DPC-003334"      # listed as "ICI-46474" in DepMap, TAMOXIFEN a synonym
VINCRISTINE = "DPC-006853"
GEMCITABINE = "DPC-002977"
IMATINIB = "DPC-003373"
ETOPOSIDE = "DPC-002651"
METHOTREXATE = "DPC-000234"
BORTEZOMIB = "DPC-001195"
DOCETAXEL = "DPC-002313"

CURATED_BULK_RESISTANCE_MECHANISMS = [
    dict(
        drug_id=TAMOXIFEN,
        pathway_or_gene="ESR1 ligand-binding-domain mutations (e.g. Y537S, D538G)",
        mechanism_description="Activating ESR1 LBD mutations drive ligand-"
        "independent ER transcriptional activity and reduce tamoxifen/"
        "fulvestrant efficacy in ER+ breast cancer (Toy et al. 2013).",
        source="pmid:24185512",
        signature_panel=None,
    ),
    dict(
        drug_id=VINCRISTINE,
        pathway_or_gene="ABCB1/P-glycoprotein drug efflux",
        mechanism_description="Vinca alkaloids are classic ABCB1/P-gp "
        "substrates; P-gp overexpression is one of the best-characterized "
        "multidrug-resistance mechanisms in oncology (Gottesman 2002) -- "
        "the same review already cited for doxorubicin's ABCB1 mechanism.",
        source="pmid:11818492",
        signature_panel=None,
    ),
    dict(
        drug_id=GEMCITABINE,
        pathway_or_gene="hENT1 (SLC29A1) transporter loss / cytidine deaminase (CDA) overexpression",
        mechanism_description="Gemcitabine uptake depends on the hENT1 "
        "nucleoside transporter; hENT1 loss reduces intracellular drug "
        "accumulation, and CDA overexpression inactivates the drug "
        "directly (Koltai et al. 2022 review).",
        source="pmid:35626089",
        signature_panel=None,
    ),
    dict(
        drug_id=IMATINIB,
        pathway_or_gene="BCR-ABL kinase-domain mutation (e.g. T315I)",
        mechanism_description="Point mutations in the BCR-ABL kinase domain "
        "(the 'gatekeeper' T315I being the best known) sterically block "
        "imatinib binding in the ATP pocket -- the landmark mechanism "
        "described in CML (Gorre et al. 2001).",
        source="pmid:11423618",
        signature_panel=None,
    ),
    dict(
        drug_id=ETOPOSIDE,
        pathway_or_gene="TOP2A (topoisomerase II alpha) downregulation",
        mechanism_description="Reduced TOP2A expression lowers the number "
        "of etoposide-DNA-topoisomerase cleavable complexes that can form, "
        "one of several mechanisms identified in etoposide-resistant MCF-7 "
        "cells (Kaplan & Gunduz 2012).",
        source="pmid:22285073",
        # Topoisomerase-mediated DNA damage is the same thematic mechanism
        # already tracked for the platinum drugs and TTFields -- a
        # legitimate panel match, unlike most other rows in this module.
        signature_panel=SignaturePanel.dna_damage,
    ),
    dict(
        drug_id=METHOTREXATE,
        pathway_or_gene="DHFR (dihydrofolate reductase) gene amplification",
        mechanism_description="Amplification of the drug's own target gene, "
        "DHFR, restores enzyme activity above what methotrexate can "
        "inhibit; originally described in relapsed acute lymphoblastic "
        "leukemia, correlated with p53 mutation (Goker et al. 1995).",
        source="pmid:7605998",
        signature_panel=None,
    ),
    dict(
        drug_id=BORTEZOMIB,
        pathway_or_gene="PSMB5 (proteasome subunit beta5) mutation/overexpression",
        mechanism_description="Mutation of the drug's own binding pocket in "
        "PSMB5, combined with dramatic PSMB5 overexpression, is the "
        "molecular basis of acquired bortezomib resistance (Oerlemans et "
        "al. 2008).",
        source="pmid:18565852",
        signature_panel=None,
    ),
    dict(
        drug_id=DOCETAXEL,
        pathway_or_gene="ABCB1/P-glycoprotein efflux; TUBB3 (class III beta-tubulin) alteration",
        mechanism_description="Same taxane-class mechanism as paclitaxel "
        "(Aldonza et al. 2016) -- not a docetaxel-specific study, but the "
        "underlying ABCB1/TUBB3 biology is a documented class effect "
        "across taxanes.",
        source="pmid:27284014",
        signature_panel=None,
    ),
]


def seed(session: Session) -> dict:
    """Insert the curated bulk-registry resistance mechanisms. Idempotent:
    skips any (drug_id, pathway_or_gene) pair already present. Must be
    called after ingest.depmap_prism.DepmapPrismIngest().run() (these
    drug_ids only exist in the DB afterward) and should be followed by a
    fresh synlethality.bridging.generate_candidates() call so the new
    mechanisms actually get matched against modifier signatures.
    """
    existing = {
        (row.drug_id, row.pathway_or_gene)
        for row in session.query(DrugResistanceMechanism.drug_id, DrugResistanceMechanism.pathway_or_gene)
    }
    n = 0
    for row in CURATED_BULK_RESISTANCE_MECHANISMS:
        key = (row["drug_id"], row["pathway_or_gene"])
        if key in existing:
            continue
        session.add(DrugResistanceMechanism(**row))
        n += 1
    return {"inserted": n, "skipped": len(CURATED_BULK_RESISTANCE_MECHANISMS) - n}

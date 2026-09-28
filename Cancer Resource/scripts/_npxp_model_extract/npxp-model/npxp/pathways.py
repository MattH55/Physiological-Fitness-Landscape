"""
Pathway-space representation used as a compact stand-in for the L1000
landmark space (978 genes). Real runs should swap PATHWAYS for the
landmark gene index and load signatures from LINCS level-5 z-scores;
every downstream function is agnostic to the dimension.

Rationale for a reduced space: the non-pharmacological modifiers
(hyperthermia, fasting, hypoxia, TTFields) have no L1000 profiles, so
their signatures must be curated from published differential-expression
studies. Curation is only tractable at pathway/program resolution, and
pathway-space projection of L1000 signatures is standard practice
(e.g. SynPathy, TranSynergy's pathway deconvolution).
"""

PATHWAYS = [
    # proliferation / cell cycle
    "CELL_CYCLE_G1S", "CELL_CYCLE_G2M", "MITOTIC_SPINDLE", "DNA_REPLICATION",
    # damage & death
    "DNA_DAMAGE_RESPONSE", "DNA_REPAIR_CAPACITY", "P53_SIGNALING",
    "APOPTOSIS", "SENESCENCE",
    # stress / proteostasis
    "HEAT_SHOCK_RESPONSE", "UNFOLDED_PROTEIN_RESPONSE", "PROTEASOME",
    "AUTOPHAGY", "OXIDATIVE_STRESS",
    # metabolism
    "GLYCOLYSIS", "OXPHOS", "FATTY_ACID_OXIDATION", "LIPOGENESIS",
    "ONE_CARBON_NUCLEOTIDE", "PENTOSE_PHOSPHATE", "GLUTAMINOLYSIS",
    # nutrient / energy sensing
    "MTORC1_SIGNALING", "AMPK_SIGNALING", "INSULIN_IGF1_SIGNALING", "FOXO_SIGNALING",
    # growth signalling
    "PI3K_AKT", "MAPK_ERK", "WNT", "NOTCH", "TGF_BETA", "JAK_STAT",
    # hypoxia / angiogenesis
    "HYPOXIA_HIF1A", "ANGIOGENESIS",
    # membrane / transport / efflux
    "MEMBRANE_FLUIDITY_TRANSPORT", "ABC_EFFLUX", "ION_HOMEOSTASIS",
    # immune / inflammation
    "INFLAMMATORY_NFKB", "INTERFERON", "ANTIGEN_PRESENTATION",
    # differentiation / structure
    "EMT", "ECM_ADHESION", "CYTOSKELETON", "CILIUM_CENTROSOME",
    # redox & detox
    "NRF2_ANTIOXIDANT", "GLUTATHIONE_METABOLISM", "XENOBIOTIC_METABOLISM",
    # chromatin / transcription
    "CHROMATIN_HDAC", "RIBOSOME_BIOGENESIS", "TRANSLATION_INITIATION",
    "RNA_SPLICING", "MYC_TARGETS",
]

PW_INDEX = {p: i for i, p in enumerate(PATHWAYS)}
N_PW = len(PATHWAYS)

# Pathways whose residual activity supports proliferation/survival.
# Used by the mechanistic simulator and by the "essentiality-weighted"
# feature block. Weights are directional: positive = supports survival.
SURVIVAL_WEIGHTS = {
    "CELL_CYCLE_G1S": 1.0, "CELL_CYCLE_G2M": 1.0, "DNA_REPLICATION": 0.9,
    "MITOTIC_SPINDLE": 0.9, "MTORC1_SIGNALING": 0.8, "PI3K_AKT": 0.8,
    "MAPK_ERK": 0.7, "MYC_TARGETS": 0.7, "TRANSLATION_INITIATION": 0.6,
    "RIBOSOME_BIOGENESIS": 0.5, "OXPHOS": 0.4, "GLYCOLYSIS": 0.4,
    "ONE_CARBON_NUCLEOTIDE": 0.5, "NRF2_ANTIOXIDANT": 0.4,
    "GLUTATHIONE_METABOLISM": 0.35, "PROTEASOME": 0.45,
    "HEAT_SHOCK_RESPONSE": 0.5, "AUTOPHAGY": 0.3, "ABC_EFFLUX": 0.3,
    "DNA_REPAIR_CAPACITY": 0.75,
    "ANGIOGENESIS": 0.2, "EMT": 0.15,
    "APOPTOSIS": -1.0, "P53_SIGNALING": -0.6, "SENESCENCE": -0.5,
    "DNA_DAMAGE_RESPONSE": -0.45, "OXIDATIVE_STRESS": -0.5,
    "UNFOLDED_PROTEIN_RESPONSE": -0.4,
}
SURVIVAL_VEC = [SURVIVAL_WEIGHTS.get(p, 0.0) for p in PATHWAYS]

# Functional modules, used for the "complementary exposure" feature
# (Cheng, Kovacs & Barabasi, Nat Commun 2019): synergy is enriched when
# two agents hit the same disease module through separate neighbourhoods.
MODULES = {
    "proliferation": ["CELL_CYCLE_G1S", "CELL_CYCLE_G2M", "DNA_REPLICATION",
                      "MITOTIC_SPINDLE", "MYC_TARGETS", "CILIUM_CENTROSOME"],
    "damage_death": ["DNA_DAMAGE_RESPONSE", "DNA_REPAIR_CAPACITY",
                     "P53_SIGNALING", "APOPTOSIS", "SENESCENCE"],
    "proteostasis": ["HEAT_SHOCK_RESPONSE", "UNFOLDED_PROTEIN_RESPONSE",
                     "PROTEASOME", "AUTOPHAGY"],
    "metabolism": ["GLYCOLYSIS", "OXPHOS", "FATTY_ACID_OXIDATION",
                   "LIPOGENESIS", "ONE_CARBON_NUCLEOTIDE",
                   "PENTOSE_PHOSPHATE", "GLUTAMINOLYSIS"],
    "nutrient_sensing": ["MTORC1_SIGNALING", "AMPK_SIGNALING",
                         "INSULIN_IGF1_SIGNALING", "FOXO_SIGNALING"],
    "growth_signalling": ["PI3K_AKT", "MAPK_ERK", "WNT", "NOTCH", "TGF_BETA",
                          "JAK_STAT"],
    "redox": ["OXIDATIVE_STRESS", "NRF2_ANTIOXIDANT",
              "GLUTATHIONE_METABOLISM", "XENOBIOTIC_METABOLISM"],
    "transport": ["MEMBRANE_FLUIDITY_TRANSPORT", "ABC_EFFLUX",
                  "ION_HOMEOSTASIS"],
    "immune": ["INFLAMMATORY_NFKB", "INTERFERON", "ANTIGEN_PRESENTATION"],
    "structure": ["EMT", "ECM_ADHESION", "CYTOSKELETON"],
    "transcription": ["CHROMATIN_HDAC", "RIBOSOME_BIOGENESIS",
                      "TRANSLATION_INITIATION", "RNA_SPLICING"],
    "hypoxia": ["HYPOXIA_HIF1A", "ANGIOGENESIS"],
}
MODULE_NAMES = list(MODULES)

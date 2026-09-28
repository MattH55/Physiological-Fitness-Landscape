"""
Cell-line context. In production this is the CCLE/DepMap RNA-seq profile
(log2 TPM, z-scored across lines) projected onto PATHWAYS, optionally
concatenated with DepMap CRISPR gene-effect scores -- the latter is what
TranSynergy showed adds signal over expression alone.

Offline stand-in: baseline pathway activity z-scores encoding each line's
documented biology, plus a dependency vector marking which pathways that
line leans on. Values are z-scores relative to a pan-cancer average line.
"""
from .pathways import N_PW, PW_INDEX


def _vec(d):
    v = [0.0] * N_PW
    for k, val in d.items():
        v[PW_INDEX[k]] = float(val)
    return v


_LINES = {
    "U87MG": dict(
        tissue="glioblastoma",
        notes="PTEN-null (PI3K/AKT high), CDKN2A-deleted, p53 wild-type, "
              "MGMT-low, highly glycolytic; standard TTFields model line",
        expr={"PI3K_AKT": 2.2, "MTORC1_SIGNALING": 1.8, "GLYCOLYSIS": 1.6,
              "HYPOXIA_HIF1A": 1.2, "CELL_CYCLE_G1S": 1.4, "EMT": 1.0,
              "ANGIOGENESIS": 1.2, "P53_SIGNALING": 0.4, "OXPHOS": -0.8,
              "FATTY_ACID_OXIDATION": -1.0, "HEAT_SHOCK_RESPONSE": 0.6,
              "XENOBIOTIC_METABOLISM": -1.2, "INTERFERON": -0.8},
        dep={"PI3K_AKT": 1.8, "MTORC1_SIGNALING": 1.6, "GLYCOLYSIS": 1.5,
             "CELL_CYCLE_G1S": 1.2, "MITOTIC_SPINDLE": 1.0,
             "TRANSLATION_INITIATION": 0.9, "OXPHOS": 0.3}),
    "MDAMB231": dict(
        tissue="triple-negative breast",
        notes="KRAS/BRAF-mutant, p53-mutant, mesenchymal, glutamine-avid, "
              "high ABC efflux",
        expr={"MAPK_ERK": 2.0, "EMT": 2.2, "GLUTAMINOLYSIS": 1.8,
              "ABC_EFFLUX": 1.5, "GLYCOLYSIS": 1.2, "P53_SIGNALING": -1.8,
              "INFLAMMATORY_NFKB": 1.4, "ECM_ADHESION": 1.5,
              "OXPHOS": -0.5, "NOTCH": 0.8, "CELL_CYCLE_G2M": 1.0},
        dep={"MAPK_ERK": 1.9, "GLUTAMINOLYSIS": 1.5, "MITOTIC_SPINDLE": 1.2,
             "CELL_CYCLE_G2M": 1.1, "MYC_TARGETS": 1.0, "EMT": 0.7}),
    "HCT116": dict(
        tissue="colorectal",
        notes="KRAS-mutant, p53 wild-type, MMR-deficient, high nucleotide "
              "flux; the workhorse line of the NCI-ALMANAC matrix",
        expr={"MAPK_ERK": 1.8, "ONE_CARBON_NUCLEOTIDE": 1.6,
              "DNA_REPLICATION": 1.5, "MYC_TARGETS": 1.7,
              "CELL_CYCLE_G1S": 1.3, "P53_SIGNALING": 0.6,
              "DNA_DAMAGE_RESPONSE": -0.8, "WNT": 1.8, "GLYCOLYSIS": 1.0},
        dep={"MAPK_ERK": 1.6, "ONE_CARBON_NUCLEOTIDE": 1.7, "WNT": 1.5,
             "DNA_REPLICATION": 1.4, "MYC_TARGETS": 1.2}),
    "A549": dict(
        tissue="lung adenocarcinoma",
        notes="KEAP1-mutant so NRF2 constitutively active (chemo-resistant, "
              "high glutathione), LKB1-null, KRAS-mutant",
        expr={"NRF2_ANTIOXIDANT": 2.6, "GLUTATHIONE_METABOLISM": 2.4,
              "XENOBIOTIC_METABOLISM": 2.0, "MAPK_ERK": 1.5,
              "AMPK_SIGNALING": -1.8, "OXPHOS": 0.8, "PENTOSE_PHOSPHATE": 1.5,
              "P53_SIGNALING": 0.5, "GLYCOLYSIS": 0.6},
        dep={"NRF2_ANTIOXIDANT": 1.4, "MAPK_ERK": 1.6, "OXPHOS": 1.0,
             "PENTOSE_PHOSPHATE": 1.1, "CELL_CYCLE_G1S": 1.0}),
    "PANC1": dict(
        tissue="pancreatic ductal adenocarcinoma",
        notes="KRAS/p53/CDKN2A/SMAD4 altered, autophagy-dependent, hypoxic, "
              "desmoplastic; poor drug penetration in vivo",
        expr={"AUTOPHAGY": 2.2, "HYPOXIA_HIF1A": 1.8, "MAPK_ERK": 1.7,
              "EMT": 1.6, "ECM_ADHESION": 2.0, "P53_SIGNALING": -1.8,
              "TGF_BETA": -1.2, "GLYCOLYSIS": 1.4, "OXPHOS": -0.6,
              "ONE_CARBON_NUCLEOTIDE": 0.8},
        dep={"AUTOPHAGY": 1.8, "MAPK_ERK": 1.7, "GLYCOLYSIS": 1.3,
             "GLUTAMINOLYSIS": 1.2, "MITOTIC_SPINDLE": 0.9}),
    "OVCAR3": dict(
        tissue="high-grade serous ovarian",
        notes="p53-mutant, HR-proficient but BRCA-wildtype, platinum-treated "
              "clinical context; standard HIPEC/hyperthermia model",
        expr={"DNA_DAMAGE_RESPONSE": 1.6, "P53_SIGNALING": -2.0,
              "CELL_CYCLE_G2M": 1.4, "LIPOGENESIS": 1.5,
              "HEAT_SHOCK_RESPONSE": 1.2, "ABC_EFFLUX": 1.2,
              "GLUTATHIONE_METABOLISM": 1.4, "JAK_STAT": 1.0},
        dep={"DNA_DAMAGE_RESPONSE": 1.5, "CELL_CYCLE_G2M": 1.3,
             "LIPOGENESIS": 1.2, "HEAT_SHOCK_RESPONSE": 1.1,
             "MITOTIC_SPINDLE": 1.0}),
    "HEPG2": dict(
        tissue="hepatocellular",
        notes="high oxidative and xenobiotic metabolism, CTNNB1-mutant, "
              "insulin/IGF1-responsive",
        expr={"XENOBIOTIC_METABOLISM": 2.4, "OXPHOS": 1.8,
              "FATTY_ACID_OXIDATION": 1.6, "WNT": 2.0,
              "INSULIN_IGF1_SIGNALING": 1.8, "LIPOGENESIS": 1.4,
              "GLYCOLYSIS": -0.6, "P53_SIGNALING": 0.8},
        dep={"OXPHOS": 1.6, "WNT": 1.7, "INSULIN_IGF1_SIGNALING": 1.3,
             "FATTY_ACID_OXIDATION": 1.1, "CELL_CYCLE_G1S": 0.9}),
    "MCF7": dict(
        tissue="ER+ breast",
        notes="p53 wild-type, PIK3CA-mutant, luminal, low efflux; the most "
              "densely profiled line in LINCS L1000",
        expr={"PI3K_AKT": 1.6, "INSULIN_IGF1_SIGNALING": 1.4,
              "CELL_CYCLE_G1S": 1.2, "LIPOGENESIS": 1.3, "P53_SIGNALING": 0.9,
              "ABC_EFFLUX": -1.2, "EMT": -1.5, "OXPHOS": 0.6,
              "CHROMATIN_HDAC": 0.8},
        dep={"PI3K_AKT": 1.5, "CELL_CYCLE_G1S": 1.4,
             "INSULIN_IGF1_SIGNALING": 1.2, "LIPOGENESIS": 1.1,
             "TRANSLATION_INITIATION": 0.9}),
}

CELL_LINES = {k: {**v, "expr_vec": _vec(v["expr"]), "dep_vec": _vec(v["dep"])}
              for k, v in _LINES.items()}

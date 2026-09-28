"""
Perturbation signature library.

Two classes of perturbagen:

  PHARMACOLOGICAL (drugs) -- in a production run these come from LINCS
  L1000 level-5 z-scores, projected onto PATHWAYS. Here they are
  literature-consensus pathway signatures so the pipeline is runnable
  offline and auditable.

  NON-PHARMACOLOGICAL (modifiers) -- hyperthermia, fasting/caloric
  restriction, hypoxia, TTFields, radiotherapy. These have NO L1000
  profiles; they are curated from published transcriptomic studies.
  Each carries `refs` naming the evidence class it was drawn from.

Values are on an L1000-like z-scale: |z| ~ 2 is a solid change,
|z| ~ 5-8 is a dominant program.  Only nonzero entries are listed.
"""
from .pathways import N_PW, PW_INDEX


def _vec(d):
    v = [0.0] * N_PW
    for k, val in d.items():
        v[PW_INDEX[k]] = float(val)
    return v


# ---------------------------------------------------------------- drugs
_DRUGS = {
    "doxorubicin": dict(
        moa="topoisomerase II inhibitor / DNA intercalator",
        sig={"DNA_DAMAGE_RESPONSE": 6.5, "P53_SIGNALING": 5.0, "APOPTOSIS": 4.0,
             "SENESCENCE": 3.0, "DNA_REPLICATION": -5.0, "CELL_CYCLE_G2M": -4.0,
             "CELL_CYCLE_G1S": -3.0, "OXIDATIVE_STRESS": 3.5,
             "NRF2_ANTIOXIDANT": 2.0, "MYC_TARGETS": -2.5, "ABC_EFFLUX": 2.5, "DNA_REPAIR_CAPACITY": 1.5}),
    "cisplatin": dict(
        moa="DNA crosslinker",
        sig={"DNA_DAMAGE_RESPONSE": 7.0, "P53_SIGNALING": 5.5, "APOPTOSIS": 4.2,
             "DNA_REPLICATION": -5.5, "CELL_CYCLE_G2M": -4.5,
             "GLUTATHIONE_METABOLISM": 3.5, "NRF2_ANTIOXIDANT": 3.0,
             "OXIDATIVE_STRESS": 3.0, "XENOBIOTIC_METABOLISM": 2.0, "DNA_REPAIR_CAPACITY": 2.0}),
    "paclitaxel": dict(
        moa="microtubule stabiliser",
        sig={"MITOTIC_SPINDLE": -7.0, "CELL_CYCLE_G2M": 4.0, "APOPTOSIS": 3.8,
             "CYTOSKELETON": -4.5, "CILIUM_CENTROSOME": -3.0,
             "INFLAMMATORY_NFKB": 2.0, "ABC_EFFLUX": 3.0,
             "DNA_REPLICATION": -1.5}),
    "gemcitabine": dict(
        moa="nucleoside analogue / ribonucleotide reductase inhibitor",
        sig={"DNA_REPLICATION": -7.0, "ONE_CARBON_NUCLEOTIDE": -5.5,
             "DNA_DAMAGE_RESPONSE": 4.5, "CELL_CYCLE_G1S": -4.5,
             "P53_SIGNALING": 3.0, "APOPTOSIS": 3.0, "PENTOSE_PHOSPHATE": -2.0,
             "DNA_REPAIR_CAPACITY": 1.0}),
    "fluorouracil": dict(
        moa="thymidylate synthase inhibitor",
        sig={"ONE_CARBON_NUCLEOTIDE": -7.0, "DNA_REPLICATION": -6.0,
             "RNA_SPLICING": -3.0, "RIBOSOME_BIOGENESIS": -3.5,
             "DNA_DAMAGE_RESPONSE": 4.0, "P53_SIGNALING": 3.5,
             "CELL_CYCLE_G1S": -4.0, "APOPTOSIS": 2.8}),
    "temozolomide": dict(
        moa="DNA methylating agent",
        sig={"DNA_DAMAGE_RESPONSE": 5.5, "P53_SIGNALING": 4.0,
             "APOPTOSIS": 2.5, "SENESCENCE": 2.5, "DNA_REPLICATION": -3.5,
             "CELL_CYCLE_G2M": -3.0, "AUTOPHAGY": 2.5,
             "DNA_REPAIR_CAPACITY": 1.5}),
    "bortezomib": dict(
        moa="26S proteasome inhibitor",
        sig={"PROTEASOME": -7.5, "UNFOLDED_PROTEIN_RESPONSE": 6.5,
             "HEAT_SHOCK_RESPONSE": 5.5, "APOPTOSIS": 4.5,
             "OXIDATIVE_STRESS": 3.5, "AUTOPHAGY": 3.0,
             "INFLAMMATORY_NFKB": -4.0, "TRANSLATION_INITIATION": -3.0,
             "CELL_CYCLE_G1S": -2.5}),
    "tanespimycin_17AAG": dict(
        moa="HSP90 inhibitor",
        sig={"HEAT_SHOCK_RESPONSE": 7.0, "UNFOLDED_PROTEIN_RESPONSE": 4.0,
             "PI3K_AKT": -4.5, "MAPK_ERK": -3.5, "MYC_TARGETS": -3.5,
             "CELL_CYCLE_G1S": -3.0, "APOPTOSIS": 3.0, "PROTEASOME": 2.0}),
    "rapamycin": dict(
        moa="mTORC1 inhibitor",
        sig={"MTORC1_SIGNALING": -7.5, "TRANSLATION_INITIATION": -5.5,
             "RIBOSOME_BIOGENESIS": -5.0, "AUTOPHAGY": 5.5,
             "FOXO_SIGNALING": 3.0, "LIPOGENESIS": -3.5, "MYC_TARGETS": -3.0,
             "CELL_CYCLE_G1S": -3.5, "GLYCOLYSIS": -2.5,
             "INSULIN_IGF1_SIGNALING": -2.0}),
    "metformin": dict(
        moa="complex I inhibitor / AMPK activator",
        sig={"AMPK_SIGNALING": 5.5, "OXPHOS": -5.0, "MTORC1_SIGNALING": -4.0,
             "GLYCOLYSIS": 3.5, "FATTY_ACID_OXIDATION": 2.5, "AUTOPHAGY": 2.5,
             "LIPOGENESIS": -3.0, "FOXO_SIGNALING": 2.0, "MYC_TARGETS": -1.5}),
    "2_deoxyglucose": dict(
        moa="hexokinase / glycolysis inhibitor",
        sig={"GLYCOLYSIS": -7.0, "PENTOSE_PHOSPHATE": -3.5,
             "AMPK_SIGNALING": 4.5, "UNFOLDED_PROTEIN_RESPONSE": 4.0,
             "MTORC1_SIGNALING": -3.5, "AUTOPHAGY": 3.5, "OXPHOS": 2.0,
             "ONE_CARBON_NUCLEOTIDE": -2.0}),
    "sorafenib": dict(
        moa="multikinase (RAF/VEGFR/PDGFR) inhibitor",
        sig={"MAPK_ERK": -6.0, "ANGIOGENESIS": -5.0, "PI3K_AKT": -2.5,
             "APOPTOSIS": 3.0, "OXPHOS": -3.0, "AMPK_SIGNALING": 2.5,
             "CELL_CYCLE_G1S": -3.0, "HYPOXIA_HIF1A": -2.5}),
    "vorinostat": dict(
        moa="HDAC inhibitor",
        sig={"CHROMATIN_HDAC": -7.0, "P53_SIGNALING": 3.5, "APOPTOSIS": 4.0,
             "CELL_CYCLE_G1S": -4.5, "OXIDATIVE_STRESS": 3.0,
             "HEAT_SHOCK_RESPONSE": 3.5, "DNA_DAMAGE_RESPONSE": 3.0,
             "MYC_TARGETS": -3.5, "ANTIGEN_PRESENTATION": 3.0,
             "INTERFERON": 2.5, "DNA_REPAIR_CAPACITY": -3.5}),
    "olaparib": dict(
        moa="PARP inhibitor",
        sig={"DNA_DAMAGE_RESPONSE": 6.0, "DNA_REPLICATION": -4.0,
             "P53_SIGNALING": 3.0, "APOPTOSIS": 2.5, "CELL_CYCLE_G2M": -3.0,
             "SENESCENCE": 2.0, "DNA_REPAIR_CAPACITY": -6.5}),
    "erlotinib": dict(
        moa="EGFR tyrosine kinase inhibitor",
        sig={"MAPK_ERK": -5.5, "PI3K_AKT": -4.0, "CELL_CYCLE_G1S": -4.0,
             "MYC_TARGETS": -3.0, "TRANSLATION_INITIATION": -2.5,
             "APOPTOSIS": 2.5, "EMT": -2.0}),
    "verapamil": dict(
        moa="L-type calcium channel blocker / P-gp inhibitor",
        sig={"ION_HOMEOSTASIS": -5.0, "ABC_EFFLUX": -5.5,
             "MEMBRANE_FLUIDITY_TRANSPORT": 2.5, "AUTOPHAGY": 2.0}),
}

# ------------------------------------------------- non-pharm modifiers
_MODIFIERS = {
    "hyperthermia_42C_1h": dict(
        moa="mild hyperthermia, 42 C / 1 h",
        refs="HSF1-driven heat-shock transcriptome; impaired homologous "
             "recombination and NHEJ; membrane fluidisation increasing "
             "platinum/anthracycline uptake (thermal radiobiology & HIPEC "
             "literature)",
        sig={"HEAT_SHOCK_RESPONSE": 8.0, "UNFOLDED_PROTEIN_RESPONSE": 5.0,
             "PROTEASOME": 3.0, "AUTOPHAGY": 3.0, "OXIDATIVE_STRESS": 3.5,
             "DNA_REPAIR_CAPACITY": -5.5,   # HR and NHEJ impairment
             "MEMBRANE_FLUIDITY_TRANSPORT": 5.0,
             "CELL_CYCLE_G1S": -3.0, "CELL_CYCLE_G2M": -2.5,
             "DNA_REPLICATION": -3.0, "TRANSLATION_INITIATION": -4.0,
             "RIBOSOME_BIOGENESIS": -3.0, "CYTOSKELETON": -3.0,
             "APOPTOSIS": 2.5, "INFLAMMATORY_NFKB": 2.5,
             "ANTIGEN_PRESENTATION": 2.5, "ION_HOMEOSTASIS": -2.5,
             "GLYCOLYSIS": 2.0}),
    "fasting_caloric_restriction": dict(
        moa="short-term fasting / fasting-mimicking, low glucose + low IGF1",
        refs="AMPK/SIRT1 activation with mTORC1 suppression; IGF1-axis "
             "withdrawal (differential stress resistance); CMap-based "
             "CR-mimetic studies (Calvert 2016; de Magalhaes 2020)",
        sig={"AMPK_SIGNALING": 6.5, "MTORC1_SIGNALING": -6.5,
             "INSULIN_IGF1_SIGNALING": -6.0, "FOXO_SIGNALING": 5.0,
             "AUTOPHAGY": 5.5, "FATTY_ACID_OXIDATION": 5.0,
             "OXPHOS": 3.0, "GLYCOLYSIS": -4.5, "LIPOGENESIS": -5.0,
             "PENTOSE_PHOSPHATE": -3.0, "ONE_CARBON_NUCLEOTIDE": -3.5,
             "GLUTAMINOLYSIS": -2.0, "TRANSLATION_INITIATION": -4.5,
             "RIBOSOME_BIOGENESIS": -4.0, "MYC_TARGETS": -3.5,
             "CELL_CYCLE_G1S": -4.0, "PI3K_AKT": -4.0,
             "NRF2_ANTIOXIDANT": 2.5, "GLUTATHIONE_METABOLISM": -2.5,
             "SENESCENCE": -1.5, "ABC_EFFLUX": -2.0}),
    "ketogenic_low_glucose": dict(
        moa="ketogenic / low-glucose high-fat medium",
        refs="glucose withdrawal with ketone body oxidation; overlaps CR "
             "signature but retains substrate supply",
        sig={"GLYCOLYSIS": -6.0, "FATTY_ACID_OXIDATION": 6.0, "OXPHOS": 4.0,
             "AMPK_SIGNALING": 4.5, "MTORC1_SIGNALING": -4.0,
             "INSULIN_IGF1_SIGNALING": -4.0, "PENTOSE_PHOSPHATE": -4.0,
             "GLUTATHIONE_METABOLISM": -3.5, "OXIDATIVE_STRESS": 3.0,
             "NRF2_ANTIOXIDANT": 2.0, "LIPOGENESIS": -3.0,
             "AUTOPHAGY": 3.0, "MYC_TARGETS": -2.5, "CELL_CYCLE_G1S": -2.5,
             "INFLAMMATORY_NFKB": -2.5}),
    "hypoxia_1pct_O2": dict(
        moa="hypoxia, 1% O2",
        refs="HIF1A-target induction; glycolytic switch; replication stress "
             "and repair downregulation under chronic hypoxia",
        sig={"HYPOXIA_HIF1A": 8.0, "GLYCOLYSIS": 6.0, "OXPHOS": -5.5,
             "ANGIOGENESIS": 5.0, "AUTOPHAGY": 4.0, "EMT": 3.5,
             "DNA_REPLICATION": -3.5, "DNA_DAMAGE_RESPONSE": 2.0,
             "DNA_REPAIR_CAPACITY": -3.5,
             "CELL_CYCLE_G1S": -3.0, "MTORC1_SIGNALING": -3.0,
             "AMPK_SIGNALING": 3.5, "ABC_EFFLUX": 3.0,
             "OXIDATIVE_STRESS": 2.5, "TRANSLATION_INITIATION": -3.5,
             "UNFOLDED_PROTEIN_RESPONSE": 3.0, "P53_SIGNALING": -2.0,
             "ONE_CARBON_NUCLEOTIDE": -2.5}),
    "ttfields_200kHz": dict(
        moa="tumour-treating fields, 200 kHz",
        refs="mitotic spindle and septin disruption, aberrant mitosis; "
             "downregulated DNA replication/repair signatures; ER stress and "
             "immunogenic cell death; increased membrane permeability",
        sig={"MITOTIC_SPINDLE": -6.5, "CYTOSKELETON": -5.0,
             "CILIUM_CENTROSOME": -4.5, "CELL_CYCLE_G2M": -4.0,
             "DNA_REPLICATION": -4.0, "DNA_DAMAGE_RESPONSE": 2.0,
             "DNA_REPAIR_CAPACITY": -3.0,
             "MEMBRANE_FLUIDITY_TRANSPORT": 4.5,
             "UNFOLDED_PROTEIN_RESPONSE": 4.0, "AUTOPHAGY": 3.5,
             "APOPTOSIS": 3.0, "SENESCENCE": 2.5,
             "ANTIGEN_PRESENTATION": 3.0, "INTERFERON": 2.5,
             "INFLAMMATORY_NFKB": 2.0, "EMT": -2.5}),
    "radiotherapy_2Gy": dict(
        moa="ionising radiation, 2 Gy fraction",
        refs="included as a positive control: the modifier class with the "
             "densest published drug-interaction data (radiosensitisation)",
        sig={"DNA_DAMAGE_RESPONSE": 7.5, "P53_SIGNALING": 6.0,
             "APOPTOSIS": 3.5, "SENESCENCE": 4.0, "CELL_CYCLE_G2M": -5.0,
             "DNA_REPLICATION": -4.5, "OXIDATIVE_STRESS": 4.5,
             "NRF2_ANTIOXIDANT": 3.0, "INFLAMMATORY_NFKB": 3.0,
             "DNA_REPAIR_CAPACITY": 2.5,
             "INTERFERON": 2.5, "CELL_CYCLE_G1S": -3.0}),
    "exercise_mimetic_shear_stress": dict(
        moa="mechanical shear / exercise-mimetic conditioning",
        refs="speculative for in vitro cancer models; retained to test the "
             "model's behaviour on a weakly cytotoxic modifier",
        sig={"AMPK_SIGNALING": 4.0, "OXPHOS": 3.5,
             "FATTY_ACID_OXIDATION": 3.0, "NRF2_ANTIOXIDANT": 3.0,
             "INFLAMMATORY_NFKB": -3.0, "ECM_ADHESION": 3.0,
             "MTORC1_SIGNALING": -1.5, "GLYCOLYSIS": -1.5}),
}

DRUGS = {k: {**v, "vec": _vec(v["sig"]), "kind": "drug"} for k, v in _DRUGS.items()}
MODIFIERS = {k: {**v, "vec": _vec(v["sig"]), "kind": "modifier"}
             for k, v in _MODIFIERS.items()}
ALL_PERTS = {**DRUGS, **MODIFIERS}


# ---------------------------------------------------------------------
# Functional direction vs transcriptional direction.
#
# A recurring failure mode of signature-only models: inhibiting a target
# often UPREGULATES its own transcriptional program by compensation.
# HSP90 inhibitors raise the heat-shock transcriptome while lowering
# chaperone capacity; proteasome inhibitors raise proteasome subunit
# transcripts while lowering degradative flux. A model given only
# expression signatures sees these as agonists.
#
# FUNC_OVERRIDES records the functional direction where it diverges from
# the transcriptional one. In production this block is derived from
# drug-target annotations (DrugBank / ChEMBL / DGIdb target + action)
# rather than curated by hand -- i.e. the drug-target feature block that
# TranSynergy and DRSPRING add on top of expression.
# ---------------------------------------------------------------------
FUNC_OVERRIDES = {
    # damage-induced repair-gene transcription overstates repair capacity
    # while the lesion burden is what matters functionally
    "doxorubicin": {"DNA_REPAIR_CAPACITY": -0.5},
    "cisplatin": {"DNA_REPAIR_CAPACITY": 0.0},
    "radiotherapy_2Gy": {"DNA_REPAIR_CAPACITY": 0.5},
    "tanespimycin_17AAG": {"HEAT_SHOCK_RESPONSE": -7.0, "PROTEASOME": -1.0},
    "bortezomib": {"UNFOLDED_PROTEIN_RESPONSE": -2.0, "HEAT_SHOCK_RESPONSE": -1.5},
    "vorinostat": {"HEAT_SHOCK_RESPONSE": -1.0},
    "paclitaxel": {"CELL_CYCLE_G2M": -5.0},      # mitotic arrest, not progression
    "hyperthermia_42C_1h": {"PROTEASOME": -2.5},  # aggregate load exceeds capacity
    "hypoxia_1pct_O2": {"UNFOLDED_PROTEIN_RESPONSE": -1.0},
    "ttfields_200kHz": {"UNFOLDED_PROTEIN_RESPONSE": -1.0},
}


def func_vec(name):
    """Functional perturbation vector: transcriptional signature with
    target-informed sign corrections applied."""
    base = dict(ALL_PERTS[name]["sig"])
    base.update(FUNC_OVERRIDES.get(name, {}))
    return _vec(base)


for _n, _d in ALL_PERTS.items():
    _d["func_vec"] = func_vec(_n)
    _d["has_target_correction"] = _n in FUNC_OVERRIDES

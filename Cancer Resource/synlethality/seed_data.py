"""
Curated seed content for the Combinatorial Fitness Landscape.

Every claim below was verified against the primary record (GEO series pages and
PubMed abstracts via NCBI E-utilities) before inclusion. Citations use
self-describing strings: "pmid:<id>", "doi:<doi>", "geo:<accession>".

Curated sources (all verified 2026-09-21):
  [S1] Zhang Z et al., Oncol Lett 2021 (PMID 33281976; doi:10.3892/ol.2020.12326)
       Transcriptomic (RNA-seq) effects of glucose deprivation (5% of standard
       glucose, 96 h) and beta-hydroxybutyrate (10 and 25 mM, 96 h) on MCF-7
       and T47D breast cancer cells. GEO: GSE153830. Series summary: glucose
       deprivation DEGs implicated the NRF2-ferroptosis axis in T47D and the
       Hippo pathway in MCF-7; BHB had limited impact (no pathway enrichment).
  [S2] GEO GSE48398 (submitter publication PMID 27245201): hyperthermic shock
       (42-45 degC) transcriptional response of breast cancer cell lines
       (MCF-7, MDA-MB-231, MDA-MB-468) vs non-malignant MCF-10A.
  [S3] Tabuchi Y et al., Int J Hyperthermia 2008 (PMID 18608577;
       doi:10.1080/02656730802140777). Mild hyperthermia 41 degC/30 min in
       human lymphoma U937 cells: HSF1 activation with Hsp40/Hsp70 induction,
       no apoptosis observed -> thermotolerance program. GEO: GSE10043.
  [S4] Helderman RFCPA et al., Cells 2020 (PMID 32722384;
       doi:10.3390/cells9081775). HIPEC-mimetic hyperthermia (38-43 degC,
       60 min) x oxaliplatin/cisplatin/carboplatin/mitomycin C/5-FU in CRC
       cell lines (incl. RKO): platinum drugs show temperature-dependent
       synergy at >=41 degC; 5-FU and MMC additive at best.
  [S5] Raffaele M et al., Int J Mol Sci 2019 (PMID 31137785;
       doi:10.3390/ijms20102593). Metformin anti-proliferative effect on
       DU-145 prostate cancer cells is glucose-concentration-dependent;
       HO-1 inhibition further sensitizes.
  [S6] Rohwer N & Cramer T, Drug Resist Updat 2011 (PMID 21466972;
       doi:10.1016/j.drup.2011.03.001). Review: HIF-1-mediated hypoxia
       responses attenuate drug-induced apoptosis (resistance).
  [S7] Hadad SM et al., Clin Transl Oncol 2014;16:746-52 (PMID 24338509;
       doi:10.1007/s12094-013-1144-8). Metformin (and direct AMPK activator
       A-769662) cause concentration-dependent proliferation suppression with
       G1 arrest in MCF-7 and MDA-MB-231 (effect stronger in MCF-7); AMPK and
       ACC are phosphorylated; no p53/p70S6K/Raptor change. NOTE: an earlier
       draft of this header cited "Mol Med Rep 2014 (doi:10.3892/mmr.2014.1803)"
       - both journal label and DOI were wrong (DOI resolves to no PubMed
       record); corrected 2026-09-21 against the PMID 24338509 record.
  [S8] Yang J et al., Int J Biol Sci 2021 (PMID 34162423;
       doi:10.7150/ijbs.41907). Metformin induces ferroptosis in breast
       cancer cells by inhibiting UFMylation of SLC7A11.
  [S9] Swanda RV et al., Mol Cell 2023 (PMID 37647899;
       doi:10.1016/j.molcel.2023.08.004). "Lysosomal cystine governs
       ferroptosis sensitivity in cancer via cysteine stress response."
       GEO: GSE237928. Cystine withdrawal combined with System Xc- inhibitors
       (erastin, sulfasalazine) and AhR modulators, viability measured, across
       a panel including A549, MDA-MB-231, UMRC6, 786-O; ferrostatin-1 rescue
       (not Z-VAD/necrostatin) confirms ferroptotic death mode.
  [S10] Chen Y et al., ACS Biomater Sci Eng 2025 (PMID 40013911;
        doi:10.1021/acsbiomaterials.4c01636). "Biofabrication of Tunable 3D
        Hydrogel for Investigating the Matrix Stiffness Impact on Breast
        Cancer Chemotherapy Resistance." MCF-7 and MDA-MB-231 cultured in
        3D hydrogels at 7.02/15.83/52.99 kPa (5G1P/5G3P/5G5P) vs 2D control;
        paclitaxel and doxorubicin IC50 assessed at 48 h per condition.
        Transcriptomic data not deposited to a public accession (available
        from corresponding author on request per the paper's data statement).
  [S11] Lee C et al., Sci Transl Med 2012;4(127):124ra27 (PMID 22323820;
       doi:10.1126/scitranslmed.3003293). "Fasting cycles retard growth of
       tumors and sensitize a range of cancer cell types to chemotherapy."
       Serum from 48-h-fasted mice sensitizes 4T1 cells to doxorubicin (DXR)
       and cyclophosphamide (CP); IGF-1 addback reverses sensitization; two
       fasting cycles with drugs retard 4T1/B16/GL26 allografts (fasting+
       chemo -> long-term cancer-free survival in neuroblastoma models);
       short-term starvation in 4T1: Akt/S6K phosphorylation up, oxidative
       stress up, caspase-3 cleavage, DNA damage, apoptosis.
  [S12] Maddocks OD et al., Nature 2012;493:542-6 (PMID 23242140;
       doi:10.1038/nature11743). Serine/glycine starvation (-SG medium; 10%
       dialysed FBS): p53-p21 (CDKN1A) arrest channels serine to glutathione
       in p53+/+ cells (HCT116 primary; RKO/MEF support), while p53-/- cells
       fail the response (oxidative stress, reduced viability, impaired
       proliferation); dietary serine/glycine depletion shrinks p53-/-
       xenografts in vivo.
  [S13] Kunos CA et al., Radiat Res 2009;172(6):666-76 (PMID 19929413;
       doi:10.1667/RR1858.1). Triapine (3-AP, NSC #663249; inhibits RNR M2
       and p53R2) significantly enhances radiation cytotoxicity in cervical
       (CaSki, HeLa, C33-a) and colon (RKO, RKO-E6) cells; prolonged
       radiation-induced DNA damage; extended G1/S arrest; similar in RKO vs
       RKO-E6 -> p53-independent radiosensitization.
  [S14] Pandey N et al., Cell Physiol Biochem 2020;54(4):748-766 (PMID
       32809300; doi:10.33594/000000253). Allicin suppresses HIF-1alpha/
       HIF-2alpha in hypoxic A549 (ROS/JNK-MAPK death pathway; apoptosis +
       autophagy; S/G2-M arrest) and synergistically enhances low-dose
       cisplatin to overcome hypoxia-induced cisplatin resistance (also
       efficacious in normoxia); long-term passive demethylation observed.
  [S15] Newell M et al., J Nutr 2019;149(1):46-56 (PMID 30601995;
       doi:10.1093/jn/nxy224). DHA (60 uM + OALA in vitro; 2.8 g/100 g diet
       in nu/nu mice) potentiates doxorubicin in MDA-MB-231: apoptosis genes
       up (Caspase-10/9, RIPK1), cell-cycle genes down (Cyclin B1, WEE1,
       CDC25C); DHA+DOX mice had 50% smaller tumors than DOX controls
       (P < 0.05).

Clinical evidence (build spec v3 `clinical_evidence`; verified 2026-09-21
directly against the ClinicalTrials.gov v2 API, not search-result text):
  [C1] NCT03028155, "Concentration-based Versus Body Surface Area-based
       Peroperative Intraperitoneal Chemotherapy (HIPEC) After Optimal
       Cytoreductive Surgery in Colorectal Peritoneal Carcinomatosis'
       Treatment." Phase III; last known status Recruiting (registry marks
       overall status Unknown as of last update). Oxaliplatin 460 mg/m2,
       30 min, hyperthermic IP delivery post-cytoreductive surgery -- links
       to the RKO HIPEC x oxaliplatin interaction (same procedure class as
       the Helderman et al. in-vitro model, not an identical protocol).
  [C2] NCT02126449 (the "DIRECT" trial), "DIetary REstriction as an Adjunct
       to Neoadjuvant ChemoTherapy for HER2 Negative Breast Cancer." Phase
       2/3; Completed. AC>T regimen (doxorubicin + cyclophosphamide, then
       paclitaxel) with a fasting-mimicking diet vs regular diet; published
       in de Groot et al. 2020, Nat Commun (doi:10.1038/s41467-020-16138-3;
       PMID 32576828). Links to the 4T1 fasting x doxorubicin and fasting x
       cyclophosphamide interactions -- human trial evidence for the same
       modifier x drug pairing the mouse/cell model (Lee et al. 2012)
       predicted, not a claim that this trial validated the 4T1 findings.
  [C3] Durando X, Farges MC, Buc E et al., Oncology 2010;78(3-4):205-9
       (PMID 20424491), "Dietary methionine restriction with FOLFOX regimen
       as first line therapy of metastatic colorectal cancer: a
       feasibility study." No NCT registration identified (predates/outside
       routine trial registration). Feasibility: dietary methionine
       restriction + FOLFOX (5-FU + oxaliplatin) as first-line therapy in
       metastatic colorectal cancer -- acceptable toxicity and tumor
       response, though patients found the low-methionine diet unpalatable
       long-term. Links to the HCT116 methionine-restriction x
       5-fluorouracil and x oxaliplatin interactions (human trial evidence
       for the same modifier-class x drug-class pairing the cell/epigenomic
       studies below predicted).

More curated modifiers, verified 2026-09-22 directly against NCBI
E-utilities (esearch/esummary) and the PubChem PUG REST API, added in
response to a request to cover more of the modifiers already named in the
build spec's "Modifier Scope (MVP)" table but never actually seeded
(glutamine restriction, methionine restriction, HBOT, TTFields, PEMF):
  [S16] Kung HN, Marks JR, Chi JT, PLoS Genet 2011;7(8):e1002229 (PMID
        21852960; doi:10.1371/journal.pgen.1002229). Basal-type breast
        cancer cells (e.g. MDA-MB-231) are glutamine-dependent; luminal-type
        cells (e.g. MCF-7) are glutamine-independent via glutamine
        synthetase expression, which also represses glutaminase. GEO:
        GSE26370 (glutamine deprivation, MCF7 + MDA-MB-231).
  [S17] Timmerman LA et al., Cancer Cell 2013;24(4):450-65 (PMID 24094812).
        Functional glutamine-sensitivity screen of 46 breast cancer lines
        identifies the SLC7A11/xCT cystine-glutamate antiporter as the
        determinant of glutamine addiction, concentrated in triple-negative
        lines. GEO: GSE48984. Direct mechanistic tie to the SLC7A11
        resistance-mechanism entries already tracked for metformin/erastin.
  [S18] Mentch SJ, Mehrmohamadi M, Huang L et al., Cell Metab 2015;22(5):
        861-73 (PMID 26411344), "Histone Methylation Dynamics and Gene
        Regulation Occur through the Sensing of One-Carbon Metabolism";
        Dai Z, Mentch SJ, Gao X et al., Nat Commun 2018;9(1):1955 (PMID
        29769529), "Methionine metabolism influences genomic architecture
        and gene expression through H3K4me3 peak width." Methionine
        restriction remodels H3K4me3 (via SAM/one-carbon-metabolism
        depletion) and gene expression in HCT116 (GSE72131) and human
        cancer cells/mouse liver (GSE103602). Clinical precedent for
        pairing with antimetabolite chemotherapy: see [C3].
  [S19] Zhang L, Ke J, Min S et al., Front Oncol 2021;11:691762 (PMID
        34367973; doi:10.3389/fonc.2021.691762). Hyperbaric oxygen (HBO)
        represses the HIF-1alpha/PFKP axis in hypoxic A549 and H1299 NSCLC cells,
        suppressing the Warburg effect, hyperproliferation and EMT;
        HBO inhibited murine Lewis lung carcinoma growth in a
        Pfkp-dependent manner in vivo. Mechanism-only in this build: no
        HBO x drug combination readout in the source study.
  [S20] Fishman H, Monin R, Dor-On E et al., J Neurooncol 2023;163(1):83-94
        (PMID 37131108; doi:10.1007/s11060-023-04308-4). Tumor Treating
        Fields (200 kHz,
        0.83 V/cm, 72 h) downregulate the FA-BRCA DNA-damage-response
        pathway in glioblastoma lines (U-87 MG, LN-229, U-118 MG, LN-18)
        and increase temozolomide (TMZ)- and lomustine (CCNU)-induced DNA
        damage; additive with TMZ irrespective of MGMT status, additive
        with CCNU in MGMT-expressing and synergistic in MGMT-non-expressing
        lines. PARP-inhibitor combination is discussed as a hypothesis
        from the induced BRCAness state, not experimentally tested in this
        paper.
  [S21] Gullà L, Ferraro A, Gervino G et al., Sci Rep 2026;16 (PMID
        41957483; doi:10.1038/s41598-026-47481-y). A defined pulsed
        electromagnetic field (PEMF)
        protocol (XR-BK11 sequence: 11 base frequencies 40 Hz-10 kHz,
        5 min each, 55 min/day x4 days, 10-400 uT) suppresses stemness
        (OCT4/NANOG, PI3K/AKT) in U-87 MG and T98 glioblastoma cells and
        potentiates temozolomide-induced apoptosis (caspase-3) and
        viability loss in U-87 MG.

Drug-resistance-mechanism completion pass (build spec v5 `drug_resistance_
mechanism`; verified 2026-09-22 directly against NCBI E-utilities), added
at the user's request to do real literature research -- not synthetic
reasoning -- for more drugs than the original 9:
  [S22] Aldonza MB, Hong JY, Alinsug MV et al., Oncotarget 2016;7(21):
        31461-78 (PMID 27284014). Paclitaxel resistance: ABCB1/P-gp efflux
        and TUBB3 (class III beta-tubulin) alteration, linked by FOXO3a-
        mediated feedback. Also cited for docetaxel (same taxane-class
        mechanism, not a docetaxel-specific study).
  [S23] Gustafson DL, Siegel D, Rastatter JC et al., J Pharmacol Exp Ther
        2003;305(3):1079-86 (PMID 12649308). NQO1 kinetics in mitomycin C
        bioreductive activation in vitro and in vivo.
  [S24] Magni M, Shammah S, Schiro R et al., Blood 1996;87(3):1097-103
        (PMID 8562935). ALDH1A1 gene transfer confers cyclophosphamide
        resistance in hematopoietic cell lines.
  [S25] Zuo Z, Zhou Z, Chang Y et al., Genes Dis 2024;11(5) (PMID 37588202;
        doi:10.1016/j.gendis.2022.11.022). RRM2 regulation/function/
        targeting review, cited for RRM2 overexpression as a general
        resistance mechanism against RNR-dependent chemotherapy including
        triapine, which directly targets RRM2.
  [S26] Toy W, Shen Y, Won H et al., Nat Genet 2013;45(12):1439-45 (PMID
        24185512; doi:10.1038/ng.2822). ESR1 ligand-binding-domain
        mutations (e.g. Y537S, D538G) confer tamoxifen/fulvestrant
        resistance in ER+ breast cancer.
  [S27] Koltai T, Reshkin SJ, Carvalho TMA et al., Cancers 2022;14(10):2486
        (PMID 35626089; doi:10.3390/cancers14102486). Gemcitabine
        resistance review: hENT1 (SLC29A1) nucleoside-transporter loss and
        cytidine deaminase (CDA) overexpression.
  [S28] Gorre ME, Mohammed M, Ellwood K et al., Science 2001;293(5531):
        876-80 (PMID 11423618). BCR-ABL kinase-domain mutations (e.g.
        T315I) confer imatinib (STI-571) resistance in CML.
  [S29] Goker E, Waltham M, Kheradpour A et al., Blood 1995;86(2):677-84
        (PMID 7605998). DHFR gene amplification confers methotrexate
        resistance in ALL, correlated with p53 mutation.
  [S30] Oerlemans R, Franke NE, Assaraf YG et al., Blood 2008;112(6):
        2489-99 (PMID 18565852). PSMB5 (proteasome beta5 subunit) mutation
        and overexpression confer bortezomib resistance.
  [S31] Kaplan E, Gunduz U, Biomed Pharmacother 2012;66(1):29-35 (PMID
        22285073). TOP2A downregulation is one of several mechanisms in
        etoposide-resistant MCF-7 cells.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from synlethality import bridging
from synlethality.models import (
    CellLine,
    ClinicalEvidence,
    ClinicalStatus,
    CostAccessibilityTier,
    Directionality,
    Drug,
    DrugResistanceMechanism,
    EvidenceTier,
    InfrastructureRequirement,
    InteractionEffect,
    InteractionType,
    Modifier,
    ModifierType,
    SignaturePanel,
    StressSignatureScore,
    TumorConcordanceFlag,
)

# ---------------------------------------------------------------------------
# Cell lines (panel anchored to the curated studies; CCLE as lineage source).
# ---------------------------------------------------------------------------

CELL_LINES = [
    dict(
        cell_line_id="MCF7_BREAST",
        name="MCF-7",
        tissue_origin="Breast",
        cancer_subtype="Breast adenocarcinoma, ER+/HER2- (luminal A)",
        key_mutations=[
            {"gene": "PIK3CA", "variant": "E545K"},
            {"gene": "GATA3", "variant": "frameshift"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="T47D_BREAST",
        name="T47D",
        tissue_origin="Breast",
        cancer_subtype="Breast ductal carcinoma, ER+/HER2- (luminal A)",
        key_mutations=[
            {"gene": "PIK3CA", "variant": "H1047R"},
            {"gene": "TP53", "variant": "L194F"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="MDAMB231_BREAST",
        name="MDA-MB-231",
        tissue_origin="Breast",
        cancer_subtype="Triple-negative breast cancer (basal-like)",
        key_mutations=[
            {"gene": "KRAS", "variant": "G13D"},
            {"gene": "BRAF", "variant": "G464V"},
            {"gene": "TP53", "variant": "R280K"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="MDAMB468_BREAST",
        name="MDA-MB-468",
        tissue_origin="Breast",
        cancer_subtype="Triple-negative breast cancer (basal-like)",
        key_mutations=[
            {"gene": "PTEN", "variant": "homozygous deletion"},
            {"gene": "TP53", "variant": "R273H"},
            {"gene": "EGFR", "variant": "amplification"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="MCF10A_BREAST",
        name="MCF-10A",
        tissue_origin="Breast",
        cancer_subtype="Non-malignant mammary epithelial (basal)",
        key_mutations=[{"gene": "CDKN2A", "variant": "homozygous deletion"}],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE",
        name="U-937",
        tissue_origin="Haematopoietic and lymphoid tissue",
        cancer_subtype="Histiocytic lymphoma",
        key_mutations=[{"gene": "TP53", "variant": "deficient"}],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="RKO_LARGE_INTESTINE",
        name="RKO",
        tissue_origin="Large intestine",
        cancer_subtype="Colorectal adenocarcinoma (MSI-H)",
        key_mutations=[
            {"gene": "BRAF", "variant": "V600E"},
            {"gene": "TP53", "variant": "wild-type"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="DU145_PROSTATE",
        name="DU-145",
        tissue_origin="Prostate",
        cancer_subtype="Prostate adenocarcinoma (androgen-independent)",
        key_mutations=[
            {"gene": "TP53", "variant": "P223L/V274F"},
            {"gene": "RB1", "variant": "mutant"},
        ],
        source="CCLE/DepMap",
    ),
    # --- New 2026-09-21 curation pass (literature-verified; see [S11]-[S15]) ---
    dict(
        cell_line_id="A549_LUNG",
        name="A549",
        tissue_origin="Lung",
        cancer_subtype="Lung adenocarcinoma (NSCLC)",
        key_mutations=[
            {"gene": "KRAS", "variant": "G12S"},
            {"gene": "STK11", "variant": "loss-of-function"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="HELA_CERVIX",
        name="HeLa",
        tissue_origin="Cervix",
        cancer_subtype="Cervical adenocarcinoma (HPV18-positive)",
        key_mutations=[
            {"gene": "HPV18", "variant": "E6/E7 oncoprotein expression; E6 targets TP53 "
            "and E7 targets RB1 for degradation (virally silenced p53 per Kunos et al. 2009)"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="CASKI_CERVIX",
        name="Ca Ski",
        tissue_origin="Cervix",
        cancer_subtype="Cervical squamous cell carcinoma (HPV16-positive)",
        key_mutations=[
            {"gene": "HPV16", "variant": "E6/E7 oncoprotein expression; TP53/RB1 "
            "pathway silenced (virally silenced p53 per Kunos et al. 2009)"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="HCT116_LARGE_INTESTINE",
        name="HCT116",
        tissue_origin="Large intestine",
        cancer_subtype="Colorectal adenocarcinoma (KRAS-mutant; mismatch-repair deficient)",
        key_mutations=[
            {"gene": "KRAS", "variant": "G13D"},
            {"gene": "TP53", "variant": "wild-type (parental line; p53+/+)"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="HCT116P53NULL_LARGE_INTESTINE",
        name="HCT116 p53-/-",
        tissue_origin="Large intestine",
        cancer_subtype="Colorectal adenocarcinoma, isogenic TP53 knockout derivative of HCT116",
        key_mutations=[
            {"gene": "KRAS", "variant": "G13D"},
            {"gene": "TP53", "variant": "homozygous knockout (isogenic p53-/- derivative)"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="4T1_BREAST",
        name="4T1",
        tissue_origin="Breast (mouse)",
        cancer_subtype="Murine mammary carcinoma (BALB/c; highly metastatic; triple-negative)",
        key_mutations=[
            {"gene": "AKT", "variant": "short-term starvation increases AKT/S6K "
            "phosphorylation - sensitizing stress response (Lee et al. 2012)"},
            {"gene": "ESR1/ERBB2", "variant": "triple-negative phenotype"},
        ],
        source="Primary literature (Lee et al. 2012, PMID 22323820); murine line, not CCLE/DepMap-registered",
    ),
    # --- New 2026-09-22 curation pass: modifiers named in the build spec's
    # "Modifier Scope (MVP)" table but never seeded (TTFields, PEMF) ---
    dict(
        cell_line_id="U87MG_CENTRAL_NERVOUS_SYSTEM",
        name="U-87 MG",
        tissue_origin="Central nervous system",
        cancer_subtype="Glioblastoma multiforme",
        key_mutations=[
            {"gene": "PTEN", "variant": "homozygous deletion"},
            {"gene": "CDKN2A", "variant": "homozygous deletion"},
        ],
        source="CCLE/DepMap",
    ),
    dict(
        cell_line_id="T98G_CENTRAL_NERVOUS_SYSTEM",
        name="T98G",
        tissue_origin="Central nervous system",
        cancer_subtype="Glioblastoma multiforme",
        key_mutations=[
            {"gene": "TP53", "variant": "M237I (missense)"},
            {"gene": "PTEN", "variant": "mutant"},
        ],
        source="CCLE/DepMap",
    ),
]

# ---------------------------------------------------------------------------
# Modifiers (protocol parameters preserved per spec; never normalized away).
#
# infrastructure_requirement / estimated_relative_cost_note (build spec v6):
# curator judgment calls, not independently-verified facts (see models.py
# Modifier docstring) -- no automated source exists, per the spec's own
# Open Questions. MOD-STIFFNESS-53KPA-5G5P is left unassessed on purpose:
# it's an in-vitro-only biomaterial system with no patient-deliverable
# form, so no infrastructure tier applies to it at all.
# ---------------------------------------------------------------------------

MODIFIERS = [
    dict(
        modifier_id="MOD-GLUCOSE-RESTRICT-5PCT-96H",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Glucose restriction (5% of standard medium glucose)",
        protocol_parameters={
            "glucose_percent_of_standard": 5.0,
            "duration_hr": 96,
            "readout": "RNA-seq",
        },
        source_study="doi:10.3892/ol.2020.12326",
        source_dataset_accession="GSE153830",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Dietary/fasting-style protocol; no equipment.",
    ),
    dict(
        modifier_id="MOD-BHB-10MM-96H",
        modifier_type=ModifierType.dietary_metabolic,
        agent="beta-Hydroxybutyrate (sodium salt)",
        protocol_parameters={"concentration_mM": 10.0, "duration_hr": 96, "readout": "RNA-seq"},
        source_study="doi:10.3892/ol.2020.12326",
        source_dataset_accession="GSE153830",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Oral ketone-body supplement (BHB salts); low unit cost.",
    ),
    dict(
        modifier_id="MOD-BHB-25MM-96H",
        modifier_type=ModifierType.dietary_metabolic,
        agent="beta-Hydroxybutyrate (sodium salt)",
        protocol_parameters={"concentration_mM": 25.0, "duration_hr": 96, "readout": "RNA-seq"},
        source_study="doi:10.3892/ol.2020.12326",
        source_dataset_accession="GSE153830",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Oral ketone-body supplement (BHB salts); low unit cost.",
    ),
    dict(
        modifier_id="MOD-GLUCOSE-LOW-DU145",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Low-glucose medium (metformin co-treatment context)",
        protocol_parameters={
            "glucose_concentration": "low vs standard; exact concentration and duration "
            "per Raffaele et al. 2019 Methods (PMID 31137785)",
        },
        source_study="doi:10.3390/ijms20102593",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Dietary/glycemic-control protocol; no equipment.",
    ),
    dict(
        modifier_id="MOD-HT-45C-GSE48398",
        modifier_type=ModifierType.thermal,
        agent="Hyperthermic shock (45 degC)",
        protocol_parameters={
            "temperature_C": 45.0,
            "note": "Exposure time/timepoints per GEO series page GSE48398; "
            "series compares malignant vs non-malignant breast lines under heat shock",
        },
        source_study="geo:GSE48398",
        source_dataset_accession="GSE48398",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Basic heating/water-bath equipment; no specialized device.",
    ),
    dict(
        modifier_id="MOD-HT-41C-30M",
        modifier_type=ModifierType.thermal,
        agent="Mild hyperthermia (41 degC, 30 min)",
        protocol_parameters={
            "temperature_C": 41.0,
            "duration_min": 30,
            "post_treatment_timepoint_hr": 3,
        },
        source_study="doi:10.1080/02656730802140777",
        source_dataset_accession="GSE10043",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Basic heating equipment (e.g. heating pads/blankets).",
    ),
    dict(
        modifier_id="MOD-HT-42C-60M-HIPEC",
        modifier_type=ModifierType.thermal,
        agent="Fever-range hyperthermia (HIPEC-mimetic)",
        protocol_parameters={
            "temperature_C": 42.0,
            "duration_min": 60,
            "note": "Representative of the studied range 38-43 degC for 60 min "
            "(Helderman et al. 2020)",
        },
        source_study="doi:10.3390/cells9081775",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.high,
        estimated_relative_cost_note="HIPEC is an intraoperative procedure requiring "
        "cytoreductive surgery plus dedicated heated-perfusion equipment and an OR "
        "team -- dedicated clinical infrastructure, not a bedside intervention.",
    ),
    dict(
        modifier_id="MOD-HT-41C-60M-HIPEC",
        modifier_type=ModifierType.thermal,
        agent="HIPEC-mimetic hyperthermia (41 degC, 60 min)",
        protocol_parameters={
            "temperature_C": 41.0,
            "duration_min": 60,
            "cem43_min": 3.75,
            "cem43_note": "Derived here, not reported by the paper: "
            "60 min * 0.25**(43-41).",
            "note": "Helderman et al. 2020 water-bath HIPEC model, 60 min.",
        },
        source_study="doi:10.3390/cells9081775",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.high,
        estimated_relative_cost_note="Same HIPEC infrastructure as the 42 degC row.",
    ),
    dict(
        modifier_id="MOD-HT-43C-60M-HIPEC",
        modifier_type=ModifierType.thermal,
        agent="HIPEC-mimetic hyperthermia (43 degC, 60 min)",
        protocol_parameters={
            "temperature_C": 43.0,
            "duration_min": 60,
            "cem43_min": 60.0,
            "cem43_note": "At 43 degC, CEM43 minutes equal the exposure time. "
            "Derived here, not reported by the paper.",
            "note": "Helderman et al. 2020 water-bath HIPEC model, 60 min.",
        },
        source_study="doi:10.3390/cells9081775",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.high,
        estimated_relative_cost_note="Same HIPEC infrastructure as the 42 degC row.",
    ),
    dict(
        # Track C (Signature-transfer modifier x drug predictor build order),
        # C1/C2, 2026-09-23: Kusumoto et al. 1993 (PMID 8347479), a real,
        # freely accessible (PMC1968573, CC-BY) schedule-dependence study --
        # exactly the class of source the build order calls out as "the
        # only realistic source for the schedule coefficient." This modifier
        # is the *simultaneous* heat/drug schedule. Heat-before carboplatin
        # is a separate modifier (MOD-HT-42.8C-30M-BEFORE): the discussion
        # states its survival-slope ratio as 2.85. Other schedules remain
        # figure-only.
        modifier_id="MOD-HT-42.8C-30M-SIMUL",
        modifier_type=ModifierType.thermal,
        agent="Hyperthermia (42.8 degC, 30 min), simultaneous with drug",
        protocol_parameters={
            "temperature_C": 42.8,
            "duration_min": 30,
            "schedule": "simultaneous (heat and drug started together)",
            "note": "Water-bath heating of cell suspension, maintained to +/-0.1 degC "
            "(Kusumoto et al. 1993); real value, not this project's rounding.",
        },
        source_study="pmid:8347479",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Basic heating/water-bath equipment; no specialized device.",
    ),
    dict(
        # Same paper, heat-before schedule. Discussion: "the increased effects
        # seen for heat prior to carboplatin were almost identical (2.85 vs
        # 2.75)" -- 2.85 is the survival effect, 2.75 is the Table I platinum
        # accumulation ratio. Interval is the 30 min spacing used for Table I
        # and for the Figure 3 "heat followed by carboplatin at 30 min
        # intervals" arm.
        modifier_id="MOD-HT-42.8C-30M-BEFORE",
        modifier_type=ModifierType.thermal,
        agent="Hyperthermia (42.8 degC, 30 min), 30 min before drug",
        protocol_parameters={
            "temperature_C": 42.8,
            "duration_min": 30,
            "schedule": "heat-before-drug",
            "interval_min": 30,
            "cem43_min": 22.74,
            "cem43_note": "Derived here, not reported by the paper: "
            "30 min * 0.25**(43-42.8), R=0.25 for T<=43 degC.",
            "note": "Water-bath, +/-0.1 degC (Kusumoto et al. 1993).",
        },
        source_study="pmid:8347479",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Basic heating/water-bath equipment; no specialized device.",
    ),
    dict(
        modifier_id="MOD-HYP-1O2-24H",
        modifier_type=ModifierType.hypoxic,
        agent="Hypoxia (1% O2)",
        protocol_parameters={
            "o2_percent": 1.0,
            "duration_hr": 24,
            "note": "Representative protocol parameters; this row is anchored to "
            "review-level evidence (Rohwer & Cramer 2011), not a single experiment",
        },
        source_study="doi:10.1016/j.drup.2011.03.001",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Tumor-microenvironment condition, not a "
        "directly patient-applied intervention; basic hypoxia-chamber/gas-mixing "
        "equipment would be needed for any lab replication.",
    ),
    dict(
        modifier_id="MOD-CYS-WITHDRAWAL",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Cystine withdrawal (cysteine/cystine-free medium)",
        protocol_parameters={
            "cystine_concentration": "0 (withdrawal)",
            "readout": "RNA-seq + viability",
            "note": "Exact duration/timepoints per GSE237928 Methods "
            "(Swanda et al. 2023); combined with System Xc- inhibitors "
            "(erastin, sulfasalazine) and AhR modulators in the source study.",
        },
        source_study="doi:10.1016/j.molcel.2023.08.004",
        source_dataset_accession="GSE237928",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Dietary/nutrient-restriction protocol (no cystine "
        "supplementation); no equipment. Clinical translation would likely be a "
        "specialized diet, not a device.",
    ),
    dict(
        modifier_id="MOD-STIFFNESS-53KPA-5G5P",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Substrate stiffness (52.99 kPa, 3D hydrogel, formulation 5G5P)",
        protocol_parameters={
            "stiffness_kPa": 52.99,
            "hydrogel_formulation": "5G5P (tunable 3D hydrogel)",
            "comparator_conditions_kPa": [7.02, 15.83],
            "comparator_format": "2D culture control",
            "readout": "IC50 (48 h drug exposure)",
        },
        source_study="doi:10.1021/acsbiomaterials.4c01636",
        source_dataset_accession=None,
        infrastructure_requirement=None,
        estimated_relative_cost_note="Not a patient-deliverable intervention -- an "
        "in-vitro biomaterial culture system only, so no infrastructure_requirement "
        "tier applies (left unassessed rather than forced into a category).",
    ),
    # --- New 2026-09-21 curation pass (literature-verified; see [S11]-[S15]) ---
    dict(
        modifier_id="MOD-FAST-CYCLES-48-60H",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Short-term fasting cycles (48-60 h, water ad libitum)",
        protocol_parameters={
            "fasting_window_hr": "48-60 (complete food withdrawal; water ad libitum)",
            "in_vitro_leg": "serum from 48-h fasted mice vs ad-lib serum, "
            "with/without doxorubicin (DXR) or cyclophosphamide (CP)",
            "in_vivo_leg": "two full fasting cycles in the 4T1 subcutaneous "
            "allograft arm (breast cancer); allografts also tested: GL26 "
            "glioma, B16 melanoma, neuroblastoma (NXS2, Neuro-2a); human "
            "xenografts: OVCAR3, MDA-MB-231",
            "refeeding": "mice returned to near pre-fast weight after each cycle",
            "readout": "viability/cell death (in vitro); tumour growth "
            "retardation and chemotherapy effectiveness (in vivo)",
        },
        source_study="pmid:22323820",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Fasting protocol; food withdrawal only, no equipment.",
    ),
    dict(
        modifier_id="MOD-SERINE-GLYCINE-FREE",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Serine/glycine starvation (-SG medium; dietary serine/glycine depletion in vivo)",
        protocol_parameters={
            "medium": "MEM (21090) + 1x MEM vitamins (11120) + 10% dialysed FBS "
            "+ 2 mM L-glutamine + 25 mM D-glucose; complete media additionally "
            "contains serine 0.4 mM and glycine 0.4 mM; starvation media omit "
            "both (-SG)",
            "in_vivo_leg": "serine/glycine-depleted diet (LC-MS-confirmed drop "
            "in serum serine/glycine) in HCT116 xenografts",
            "line_context": "HCT116 p53+/+ vs isogenic p53-/-; RKO (Supp. Fig. 2); primary MEFs",
            "readout": "proliferation/viability; LC-MS metabolic flux; p53/p21 immunoblot",
        },
        source_study="pmid:23242140",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Specialized diet formulation; no equipment, though "
        "compliance monitoring (dietary counseling) adds some real-world overhead.",
    ),
    dict(
        modifier_id="MOD-IRRAD-SINGLE-DOSE",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Ionizing radiation (single-dose radiosensitization context)",
        protocol_parameters={
            "dose_and_fractionation": "single-dose study design; exact Gy per "
            "gamma/cell-cycle figure tables pending curation (Kunos et al. 2009)",
            "sequencing": "3-AP treatment (RNR inhibition) combined with "
            "ionizing radiation; effects read as radiation cytotoxicity, RNR "
            "activity, persistence of DNA damage, cell-cycle arrest",
            "readout": "radiation-related cytotoxicity rescue-block readout; "
            "radiation-induced DNA damage duration; G1/S arrest",
        },
        source_study="pmid:19929413",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.high,
        estimated_relative_cost_note="Requires radiotherapy delivery equipment and a "
        "trained clinical team -- dedicated clinical infrastructure, comparable in "
        "tier to TTFields/HBOT, not a bedside or outpatient device.",
    ),
    dict(
        modifier_id="MOD-ALICIN-NSCLC",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Allicin (garlic organosulfur thiosulfinate)",
        protocol_parameters={
            "oxygenation": "parallel normoxic and hypoxic arms (hypoxia confers "
            "cisplatin resistance in A549; exact O2% per source Methods pending curation)",
            "dose": "per Pandey et al. Methods (dose/timepoints pending curation "
            "from source tables; not stated in abstract)",
            "readout": "MTT viability; flow cytometry (cell cycle, apoptosis, ROS); "
            "scratch and transwell migration; genome-wide methylation dot blot; "
            "HIF-1alpha/HIF-2alpha immunoblot",
        },
        source_study="pmid:32809300",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Garlic-derived compound / dietary organosulfur; "
        "low-cost, widely available.",
    ),
    dict(
        modifier_id="MOD-DHA-60UM",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Docosahexaenoic acid (DHA, omega-3 PUFA)",
        protocol_parameters={
            "in_vitro_leg": "DHA 60 uM on a control fatty-acid background (OALA: "
            "40 uM linoleic + 40 uM oleic) vs OALA alone",
            "in_vivo_leg": "nutritionally complete diet with 2.8 g/100 g DHA "
            "(P:S ratio 0.5) vs matched control diet in nu/nu mice bearing "
            "MDA-MB-231 xenografts",
            "drug_leg": "doxorubicin 0.41 uM (in vitro); 5 mg/kg DOX 2x/week for 4 weeks (in vivo)",
            "readout": "viability; microarray/protein apoptosis and cell-cycle "
            "markers; tumour volume",
        },
        source_study="pmid:30601995",
        source_dataset_accession=None,
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Omega-3 (DHA) dietary supplement; low-cost, "
        "widely available over the counter.",
    ),
    # ---------------------------------------------------------------------
    # New 2026-09-22 curation pass: modifiers already named in the build
    # spec's "Modifier Scope (MVP)" table but never actually seeded
    # (glutamine restriction, methionine restriction, HBOT, TTFields, PEMF).
    # See [S16]-[S21] above; every entry follows the same protocol_parameters
    # key-naming convention as the rest of this list (e.g. "<name>_<unit>"
    # for numeric fields, "readout"/"note" for free text).
    # ---------------------------------------------------------------------
    dict(
        modifier_id="MOD-GLUTAMINE-RESTRICT",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Glutamine restriction (glutamine-free/deprived medium)",
        protocol_parameters={
            "glutamine_concentration": "0 (deprivation)",
            "line_context": "MDA-MB-231 (basal/TNBC) glutamine-dependent; "
            "MCF-7 (luminal) glutamine-independent via glutamine synthetase "
            "expression (Kung et al. 2011)",
            "readout": "viability/proliferation; RNA-seq (GSE26370)",
        },
        source_study="doi:10.1371/journal.pgen.1002229",
        source_dataset_accession="GSE26370",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Dietary/nutrient-restriction protocol; no equipment.",
    ),
    dict(
        modifier_id="MOD-METHIONINE-RESTRICT",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Methionine restriction (-Met medium; dietary methionine restriction in vivo)",
        protocol_parameters={
            "medium": "methionine-restricted vs standard",
            "line_context": "HCT116 (GSE72131); human cancer cell lines + mouse "
            "liver (GSE103602)",
            "readout": "H3K4me3 ChIP-seq + RNA-seq (one-carbon-metabolism/SAM sensing)",
            "clinical_precedent": "Phase I/II feasibility: dietary methionine "
            "restriction + FOLFOX (5-FU + oxaliplatin) in metastatic colorectal "
            "cancer (Durando et al. 2010, PMID 20424491) -- see [C3]",
        },
        source_study="pmid:26411344",
        source_dataset_accession="GSE72131",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Specialized low-methionine diet; no equipment, "
        "though the Durando et al. feasibility trial noted poor long-term "
        "palatability as a real adherence barrier.",
    ),
    dict(
        modifier_id="MOD-HBOT",
        modifier_type=ModifierType.hypoxic,
        agent="Hyperbaric oxygen therapy (HBOT)",
        protocol_parameters={
            "line_context": "A549, H1299 NSCLC (hypoxic culture reversed by HBO)",
            "note": "Exact pressure (ATA)/exposure duration per Zhang et al. 2021 "
            "Methods, pending curation from source tables; acts via HIF-1alpha/"
            "PFKP axis suppression of the Warburg effect and EMT",
            "readout": "Warburg-effect/EMT markers; in vivo Lewis lung carcinoma "
            "growth (Pfkp-dependent)",
        },
        source_study="doi:10.3389/fonc.2021.691762",
        source_dataset_accession=None,
        # Spec's own worked example of the "high" tier is an HBOT chamber.
        infrastructure_requirement=InfrastructureRequirement.high,
        estimated_relative_cost_note="Requires a dedicated hyperbaric chamber "
        "facility and clinical staff -- dedicated clinical infrastructure, not "
        "a bedside or outpatient intervention.",
    ),
    dict(
        modifier_id="MOD-TTFIELDS-200KHZ",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Tumor Treating Fields (TTFields, 200 kHz)",
        protocol_parameters={
            "frequency_kHz": 200,
            "field_strength_V_cm": 0.83,
            "duration_hr": 72,
            "device": "inovitro (research); clinical delivery via Optune "
            "transducer arrays",
            "line_context": "U-87 MG, LN-229, U-118 MG, LN-18 glioblastoma "
            "(+ TMZ-resistant U-87 MG/U-118 MG derivatives)",
            "readout": "viability, apoptosis, clonogenic assay",
        },
        source_study="doi:10.1007/s11060-023-04308-4",
        source_dataset_accession=None,
        # Spec's own worked example of the "high" tier is TTFields arrays.
        infrastructure_requirement=InfrastructureRequirement.high,
        estimated_relative_cost_note="FDA-approved Optune device: portable "
        "field generator plus adhesive transducer arrays replaced every few "
        "days -- high recurring cost, though it is a wearable/outpatient "
        "device rather than an inpatient procedure.",
    ),
    dict(
        modifier_id="MOD-PEMF-XRBK11",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Pulsed electromagnetic field (PEMF), XR-BK11 sequence",
        protocol_parameters={
            "sequence": "XR-BK11: 11 base frequencies (40, 150, 230, 490, 720, "
            "780, 1830, 5100, 7500, 8000, 10000 Hz), 5 min each",
            "duration_min": 55,
            "days": 4,
            "magnetic_flux_uT_range": "10-400",
            "line_context": "U-87 MG, T98 glioblastoma",
            "readout": "viability, apoptosis (caspase-3), stemness markers "
            "(OCT4/NANOG); see also Sandberg et al. 2025 (PMID 40278322) "
            "genomic-profiling in bladder cancer HT-1197 (monotherapy, no "
            "drug combination tested)",
        },
        source_study="doi:10.1038/s41598-026-47481-y",
        source_dataset_accession=None,
        # Spec's own worked example of the "moderate" tier is a PEMF unit.
        infrastructure_requirement=InfrastructureRequirement.moderate,
        estimated_relative_cost_note="Portable PEMF device; moderate cost "
        "range relative to dietary/fasting protocols, well below TTFields/HBOT.",
    ),
    # Human physiological-response series, added 2026-09-24. Each accession
    # was checked against the GEO series record the same day (title, design,
    # organism, PMID when GEO lists one). These are healthy-human or
    # keratinocyte transcriptomes, not cancer-cell drug-combination studies:
    # no interaction_effect rows and no stress_signature_score rows are
    # invented for them. infrastructure_requirement is a curator judgment,
    # same as the rows above. Where a paper and its GEO summary disagree,
    # both figures are kept in protocol_parameters.
    dict(
        modifier_id="MOD-FAST-24H-GSE55924",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Short-term fasting (24 h), skeletal muscle",
        protocol_parameters={
            "cohort": "12 young healthy men",
            "tissue": "skeletal muscle",
            "duration_hr": 24,
            "biopsy_timepoints_h_post_meal": [1.5, 4, 10, 24],
            "readout": "expression microarray",
            "note": "GEO overall design: biopsies at 1.5, 4, 10 and 24 h "
            "post-meal during a 24 h fast (PMID 25249505).",
        },
        source_study="pmid:25249505",
        source_dataset_accession="GSE55924",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Supervised short fast; no device.",
    ),
    dict(
        modifier_id="MOD-FAST-40H-GSE28016",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Prolonged fasting (40 h) vs fed, vastus lateralis",
        protocol_parameters={
            "cohort": "7 healthy adults",
            "tissue": "vastus lateralis",
            "fast_duration_hr": 40,
            "fed_biopsy": "6 h after a mixed meal, contralateral vastus lateralis",
            "readout": "expression microarray",
        },
        source_study="pmid:21641545",
        source_dataset_accession="GSE28016",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Supervised 40 h fast; no device.",
    ),
    dict(
        modifier_id="MOD-TRF-8H-5D-GSE129843",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Time-restricted feeding (8 h window, 5 days), skeletal muscle",
        protocol_parameters={
            "cohort": "11 overweight/obese men",
            "tissue": "vastus lateralis (serum metabolomics in the same study, not this array)",
            "duration_days": 5,
            "trf_window": "08:00 span, 10:00-18:00",
            "control_window": "15 h unrestricted, 07:00-22:00",
            "diet": "~32% carbohydrate, ~49% fat, ~19% protein of energy; meals provided",
            "sampling": "six vastus lateralis biopsies, every 4 h over 24 h on day 5",
            "readout": "RNA-seq",
        },
        source_study="pmid:32938935",
        source_dataset_accession="GSE129843",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Meal-timing protocol; food provided in the study, no device.",
    ),
    dict(
        modifier_id="MOD-TRE-10H-8WK-GSE168705",
        modifier_type=ModifierType.dietary_metabolic,
        agent="Time-restricted eating (10 h window, 8 weeks), adipose",
        protocol_parameters={
            "cohort": "15 men, mean age 63 y, waist 113 cm, no diabetes history",
            "tissue": "adipose",
            "eating_window_hr": 10,
            "duration_weeks": 8,
            "design": "single-arm, within-subject; 2-week baseline then 8 weeks",
            "readout": "RNA-seq",
        },
        source_study="pmid:35912794",
        source_dataset_accession="GSE168705",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Self-timed eating window; no device.",
    ),
    dict(
        modifier_id="MOD-ENDURANCE-18WK-RUN",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Endurance running (18 weeks), muscle and PBMC",
        protocol_parameters={
            "cohort": "two groups of untrained policemen recruits (n=20 and n=21)",
            "protocol": "running 3 times/week, 60 min, for 18 weeks",
            "tissues": "skeletal muscle (GSE111551); PBMC (GSE111552)",
            "related_accessions": ["GSE111552"],
            "readout": "expression microarray, before and after training",
            "note": "The study summary also describes whole-blood leukocytes. "
            "These two accessions are the muscle and PBMC sets; no separate "
            "whole-blood accession was verified.",
        },
        source_study="geo:GSE111551",
        source_dataset_accession="GSE111551",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Supervised running; no specialized device.",
    ),
    dict(
        modifier_id="MOD-RESIST-ACUTE-GSE252357",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Acute resistance exercise, vastus lateralis time course",
        protocol_parameters={
            "cohort": "8 recreationally active adults in the exercise arm; 5 controls",
            "tissue": "vastus lateralis",
            "biopsy_timepoints": "baseline, 30 min, 3 h, 8 h, 24 h after resistance exercise",
            "readout": "RNA-seq",
            "also_pubmed": "39482487",
        },
        source_study="pmid:38586026",
        source_dataset_accession="GSE252357",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="A single supervised resistance session.",
    ),
    dict(
        modifier_id="MOD-EXERCISE-ACUTE-TREADMILL",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Acute treadmill exercise, moderate vs exhaustive, white blood cells",
        protocol_parameters={
            "cohort": "5 healthy men",
            "tissue": "white blood cells",
            "exhaustive": "treadmill at 80% VO2max to exhaustion",
            "moderate": "treadmill at 60% VO2max for the same duration, 1-2 weeks later",
            "sampling": "before and 1 h after each test",
            "readout": "Affymetrix U133A",
        },
        source_study="pmid:16990507",
        source_dataset_accession="GSE3606",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Treadmill plus VO2 measurement.",
    ),
    dict(
        modifier_id="MOD-COLD-ACCLIM-10D",
        modifier_type=ModifierType.thermal,
        agent="Cold acclimation (10 days), vastus lateralis, type 2 diabetes",
        protocol_parameters={
            "cohort": "8 overweight men with type 2 diabetes",
            "tissue": "vastus lateralis",
            "temperature_C": "14-15",
            "temperature_kind": "environmental air, not core temperature",
            "schedule": "10 consecutive days: 2 h day 1, 4 h day 2, 6 h days 3-10; "
            "shorts and T-shirt, sedentary",
            "readout": "expression microarray",
        },
        source_study="pmid:32887608",
        source_dataset_accession="GSE156248",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Needs a temperature-controlled cold room.",
    ),
    dict(
        modifier_id="MOD-COLD-VS-EXERCISE-GSE156249",
        modifier_type=ModifierType.other,
        agent="Cold acclimation vs 12-week exercise (comparative muscle transcriptomes)",
        protocol_parameters={
            "super_series": "GSE156249",
            "cold_arm": "GSE156248, 10-day cold acclimation, 8 men with type 2 diabetes",
            "exercise_arm": "GSE156247, 12-week combined exercise, 20 overweight "
            "middle-aged men (a different cohort, not a within-subject crossover)",
            "tissue": "vastus lateralis",
            "temperature_C": "14-15",
            "temperature_kind": "environmental air of the cold arm only",
            "readout": "expression microarray",
            "note": "Registered as other rather than thermal: the series is a "
            "cross-modifier comparison, and only the cold arm has a temperature.",
        },
        source_study="pmid:32887608",
        source_dataset_accession="GSE156249",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Cold room for one arm; supervised exercise for the other.",
    ),
    dict(
        modifier_id="MOD-CWI-10WK-STRENGTH",
        modifier_type=ModifierType.thermal,
        agent="Post-exercise cold-water immersion during 10 weeks of strength training",
        protocol_parameters={
            "cohort": "trained road cyclists (age 30±8 y); CWI vs sham recovery drink",
            "tissue": "vastus lateralis",
            "training": "lower-limb strength, 2 sessions/week for 10 weeks "
            "(20 sessions), biopsies before and after",
            "temperature_unreported": True,
            "note": "GEO sample protocol describes CWI immediately after each "
            "strength visit but does not state water temperature or immersion "
            "duration. No temperature_C is stored.",
            "readout": "Affymetrix HG-U133 Plus 2.0",
        },
        source_study="geo:GSE85620",
        source_dataset_accession="GSE85620",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Strength training plus a cold-water bath. "
        "Water temperature was not in the GEO record.",
    ),
    dict(
        modifier_id="MOD-HEAT-CHAMBER-30M-GSE82323",
        modifier_type=ModifierType.thermal,
        agent="Acute whole-body heat, skeletal muscle",
        protocol_parameters={
            "cohort": "6 able-bodied adults (the heat arm; the same series also "
            "has vibration and electrical-contraction arms in people with spinal cord injury)",
            "tissue": "vastus lateralis, biopsied 3 h after the stress",
            "temperature_C": 73.0,
            "temperature_kind": "environmental chamber; paper states ~73 degC, 20% humidity",
            "duration_min": 30,
            "related_accessions": ["same series as MOD-VIBRATION-LIMB-GSE82323 "
            "and MOD-NMES-GSE82323"],
            "readout": "Affymetrix Human Exon 1.0 ST",
        },
        source_study="pmid:27486743",
        source_dataset_accession="GSE82323",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Heat chamber; not a clinical hyperthermia device.",
    ),
    dict(
        modifier_id="MOD-HEAT-SHEET-10WK",
        modifier_type=ModifierType.thermal,
        agent="Local heat-and-steam sheet (10 weeks), quadriceps",
        protocol_parameters={
            "tissue": "vastus lateralis",
            "schedule": "8 h/day, 4 days/week, 10 weeks, sheet on the lateral thigh, no exercise",
            "temperature_unreported": True,
            "cohort_note": "GEO overall design says five subjects. The paper "
            "abstract (PMID 20803152) says eight healthy men. Both are recorded; "
            "the expression series is the GEO set.",
            "readout": "expression microarray",
        },
        source_study="pmid:20803152",
        source_dataset_accession="GSE12474",
        infrastructure_requirement=InfrastructureRequirement.minimal,
        estimated_relative_cost_note="Heat-and-steam sheet. The abstract and the "
        "GEO summary do not state a temperature, so none is stored.",
    ),
    dict(
        modifier_id="MOD-HEAT-SAUNA-PBMC",
        modifier_type=ModifierType.thermal,
        agent="Sauna heat stress, PBMC",
        protocol_parameters={
            "cohort": "15 men and women",
            "tissue": "peripheral blood mononuclear cells",
            "temperature_C": 75.7,
            "temperature_sd_or_sem_C": 0.86,
            "geo_summary_temperature_C": "78 ± 6",
            "temperature_kind": "sauna air. Abstract reports 75.7±0.86 degC; "
            "the GEO series summary says 78±6 degC. Core temperature did not "
            "rise significantly (abstract).",
            "sampling": "before, at the end of exposure, and 1 h after",
            "readout": "expression microarray",
        },
        source_study="pmid:28842615",
        source_dataset_accession="GSE90763",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Sauna session.",
    ),
    dict(
        modifier_id="MOD-PBM-BLUE-HACAT",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Blue-light photobiomodulation, HaCaT keratinocytes",
        protocol_parameters={
            "system": "immortalized human keratinocytes (HaCaT), not a tumor line in the curated cell-line table",
            "wavelength_nm": 452,
            "doses": [
                {"accession": "GSE82093", "duration_min": 30, "fluence_J_cm2": 41.4, "timepoint_hr": 24},
                {"accession": "GSE89083", "duration_min": 7.5, "fluence_J_cm2": 10.35},
            ],
            "related_accessions": ["GSE89083"],
            "readout": "expression microarray",
        },
        source_study="pmid:27669902",
        source_dataset_accession="GSE82093",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Blue-light source in a culture plate. "
        "GSE89083 has no PMID on its GEO record.",
    ),
    dict(
        modifier_id="MOD-BBL-SKIN-GSE39170",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Broadband light treatment, human skin",
        protocol_parameters={
            "cohort": "5 women aged 50 or older, treated vs untreated skin; "
            "compared with skin from 5 women aged 30 or younger",
            "tissue": "skin",
            "readout": "RNA 3'-end sequencing (3-seq)",
        },
        source_study="pmid:22931923",
        source_dataset_accession="GSE39170",
        infrastructure_requirement=InfrastructureRequirement.moderate,
        estimated_relative_cost_note="Clinic broadband-light device.",
    ),
    dict(
        modifier_id="MOD-VIBRATION-LIMB-GSE82323",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Acute passive limb-segment vibration, soleus",
        protocol_parameters={
            "cohort": "participants with chronic spinal cord injury (five received "
            "vibration or electrically induced contractions in this series)",
            "tissue": "soleus, biopsied 3 h after the stress",
            "stimulus": "passive limb-segment vibration",
            "related_modifier_ids": ["MOD-HEAT-CHAMBER-30M-GSE82323", "MOD-NMES-GSE82323"],
            "readout": "Affymetrix Human Exon 1.0 ST",
        },
        source_study="pmid:27486743",
        source_dataset_accession="GSE82323",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Limb-segment vibration device.",
    ),
    dict(
        modifier_id="MOD-NMES-GSE82323",
        modifier_type=ModifierType.mechanical_radiative,
        agent="Neuromuscular electrical stimulation (acute contractions), soleus",
        protocol_parameters={
            "cohort": "participants with chronic spinal cord injury (same series as the vibration arm)",
            "tissue": "soleus, biopsied 3 h after the stress",
            "stimulus": "repetitive electrically induced muscle contractions",
            "related_modifier_ids": ["MOD-HEAT-CHAMBER-30M-GSE82323", "MOD-VIBRATION-LIMB-GSE82323"],
            "readout": "Affymetrix Human Exon 1.0 ST",
        },
        source_study="pmid:27486743",
        source_dataset_accession="GSE82323",
        infrastructure_requirement=InfrastructureRequirement.low,
        estimated_relative_cost_note="Neuromuscular stimulator.",
    ),
]

# ---------------------------------------------------------------------------
# Drug registry (minimal; additive extension to the spec).
# ---------------------------------------------------------------------------

#: PubChem CIDs verified 2026-09-21 against the PubChem PUG REST API
#: (https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/<name>/cids/JSON)
#: directly, not from search-result text. ChEMBL/DrugBank ids are left NULL
#: below: not yet cross-checked against their own authoritative APIs, and a
#: missing cross-reference is preferred over a guessed one.
#:
#: cost_accessibility_tier (build spec v6): `essential_generic` is set only
#: where the drug's presence on the WHO Model List of Essential Medicines
#: was checked (2026-09-21, via web search cross-referencing WHO EML
#: documentation/secondary sources -- not the authoritative-API-direct
#: standard used for PubChem CIDs above, since the EML PDF itself couldn't
#: be fetched in this session; treat as verified-but-lower-confidence than
#: the PubChem cross-refs). `generic_available`/`unknown` are curator
#: judgment calls per the spec's own Open Questions, not checked facts.
DRUGS = [
    dict(drug_id="metformin", name="Metformin",
         drug_class="Biguanide (mitochondrial complex I inhibitor)",
         target="Mitochondrial ETC complex I; AMPK activation", source="curated seed",
         synonyms=["Glucophage", "Dimethylbiguanide"], pubchem_cid="4091",
         mechanism_of_action="Complex I inhibition -> AMPK activation -> reduced hepatic "
         "gluconeogenesis and cellular energetic stress",
         clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="cisplatin", name="Cisplatin", drug_class="Platinum agent",
         target="DNA crosslinking (intrastrand adducts)", source="curated seed",
         synonyms=["cis-Diamminedichloroplatinum(II)", "CDDP"], pubchem_cid="5702198",
         mechanism_of_action="Platinum-DNA intrastrand crosslinks trigger DNA-damage "
         "response and apoptosis", clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="oxaliplatin", name="Oxaliplatin", drug_class="Platinum agent",
         target="DNA crosslinking (intrastrand adducts)", source="curated seed",
         synonyms=["Eloxatin"], pubchem_cid="9887053",
         mechanism_of_action="Platinum-DNA intrastrand crosslinks (oxalate leaving group; "
         "third-generation platinum agent)", clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="carboplatin", name="Carboplatin", drug_class="Platinum agent",
         target="DNA crosslinking (intrastrand adducts)", source="curated seed",
         synonyms=["Paraplatin"], pubchem_cid="426756",
         mechanism_of_action="Platinum-DNA intrastrand crosslinks (cyclobutanedicarboxylate "
         "leaving group; lower nephrotoxicity than cisplatin)",
         clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="5-fluorouracil", name="5-Fluorouracil", drug_class="Antimetabolite (fluoropyrimidine)",
         target="Thymidylate synthase; RNA/DNA incorporation", source="curated seed",
         synonyms=["5-FU", "Adrucil"], pubchem_cid="3385",
         mechanism_of_action="Thymidylate synthase inhibition and misincorporation into "
         "RNA/DNA", clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="mitomycin-c", name="Mitomycin C", drug_class="Antibiotic alkylating agent",
         target="DNA crosslinking (bioreductive activation)", source="curated seed",
         synonyms=["Mitomycin", "Mutamycin"], pubchem_cid="5746",
         mechanism_of_action="Bioreductive activation to a DNA-crosslinking alkylating "
         "agent", clinical_status=ClinicalStatus.approved,
         # Long off-patent generic, but WHO EML listing not confirmed in this
         # session -- generic_available rather than essential_generic.
         cost_accessibility_tier=CostAccessibilityTier.generic_available),
    dict(drug_id="doxorubicin", name="Doxorubicin", drug_class="Anthracycline (topoisomerase II inhibitor)",
         target="Topoisomerase II; redox cycling", source="curated seed",
         synonyms=["Adriamycin"], pubchem_cid="31703",
         mechanism_of_action="Topoisomerase II poisoning and intercalation; redox cycling "
         "generates ROS", clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="paclitaxel", name="Paclitaxel", drug_class="Taxane (microtubule stabilizer)",
         target="beta-Tubulin", source="curated seed",
         synonyms=["Taxol"], pubchem_cid="36314",
         mechanism_of_action="Microtubule stabilization blocks mitotic spindle "
         "disassembly, arresting cells in mitosis", clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="erastin", name="Erastin", drug_class="System Xc- inhibitor (ferroptosis inducer)",
         target="SLC7A11/system Xc- cystine-glutamate antiporter", source="curated seed",
         synonyms=[], pubchem_cid="11214940",
         mechanism_of_action="System Xc- inhibition depletes intracellular cystine, "
         "collapsing glutathione synthesis and inducing ferroptosis",
         clinical_status=ClinicalStatus.preclinical,
         # Research tool compound, never marketed -- no accessibility framework applies.
         cost_accessibility_tier=CostAccessibilityTier.unknown),
    # --- Added with the 2026-09-21 curation pass (MOD-FAST-CYCLES-48-60H,
    # MOD-IRRAD-SINGLE-DOSE interactions below reference these) ---
    dict(drug_id="cyclophosphamide", name="Cyclophosphamide",
         drug_class="Nitrogen mustard alkylating agent (oxazaphosphorine prodrug)",
         target="DNA crosslinking (via hepatic CYP450 activation to phosphoramide mustard)",
         source="curated seed", synonyms=["Cytoxan", "Endoxan"], pubchem_cid="2907",
         mechanism_of_action="Prodrug bioactivated by hepatic CYP450 to phosphoramide "
         "mustard, which crosslinks DNA", clinical_status=ClinicalStatus.approved,
         cost_accessibility_tier=CostAccessibilityTier.essential_generic),
    dict(drug_id="triapine", name="Triapine (3-AP)",
         drug_class="Ribonucleotide reductase (RNR) inhibitor",
         target="Ribonucleotide reductase M2 subunit (iron chelation of the tyrosyl "
         "radical site)", source="curated seed", synonyms=["3-AP", "3-aminopyridine-2-"
         "carboxaldehyde thiosemicarbazone"], pubchem_cid="9571836",
         mechanism_of_action="Iron chelation inactivates the RNR tyrosyl radical, "
         "depleting dNTP pools and impairing DNA-damage repair",
         clinical_status=ClinicalStatus.investigational,
         # Investigational, never commercially marketed/priced.
         cost_accessibility_tier=CostAccessibilityTier.unknown),
    # --- Added with the 2026-09-22 curation pass (TTFields, PEMF interactions
    # below reference these) ---
    dict(drug_id="temozolomide", name="Temozolomide",
         drug_class="Alkylating agent (imidazotetrazine prodrug)",
         target="DNA O6-guanine methylation; MGMT-repairable lesion",
         source="curated seed", synonyms=["Temodar", "TMZ"], pubchem_cid="5394",
         mechanism_of_action="Spontaneous hydrolysis to MTIC methylates DNA at O6-guanine, "
         "triggering mismatch-repair-mediated cytotoxicity unless reversed by MGMT",
         clinical_status=ClinicalStatus.approved,
         # Generic versions exist (patent expired); a 2025 WHO EML expert-
         # committee document proposes adding it to the EMLc, but that is a
         # proposal, not a confirmed listing -- generic_available, not
         # essential_generic, until an actual listing is confirmed.
         cost_accessibility_tier=CostAccessibilityTier.generic_available),
    dict(drug_id="lomustine", name="Lomustine (CCNU)",
         drug_class="Nitrosourea alkylating agent",
         target="DNA/RNA alkylation and interstrand crosslinking; lysine carbamoylation",
         source="curated seed", synonyms=["CCNU", "CeeNU"], pubchem_cid="3950",
         mechanism_of_action="Lipophilic nitrosourea crosses the blood-brain barrier and "
         "alkylates DNA, forming interstrand crosslinks",
         clinical_status=ClinicalStatus.approved,
         # Long off-patent generic; WHO EML status not checked this session.
         cost_accessibility_tier=CostAccessibilityTier.generic_available),
]

# ---------------------------------------------------------------------------
# Stress signature scores. `score` is NULL where the source publication
# reports directionality but no numeric enrichment score (documented
# deviation; numeric ssGSEA/GSVA scores are backfilled by the ingestion
# pipeline from raw expression data).
# ---------------------------------------------------------------------------

SIGNATURE_SCORES = [
    # key used by INTERACTIONS for mechanism_link resolution
    dict(
        key="t47d_glucose_nrf2",
        modifier_id="MOD-GLUCOSE-RESTRICT-5PCT-96H",
        cell_line_id="T47D_BREAST",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
        score=None,
        raw_deg_evidence_ref="GSE153830 DEG table; Zhang et al. 2021 (PMID 33281976)",
        directionality=Directionality.death_promoting,
        notes="Glucose-deprivation DEGs implicated the NRF2-ferroptosis axis in T47D "
        "(GSE153830 series summary).",
    ),
    dict(
        key="mcf7_glucose_hippo",
        modifier_id="MOD-GLUCOSE-RESTRICT-5PCT-96H",
        cell_line_id="MCF7_BREAST",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="GSE153830 DEG table; Zhang et al. 2021 (PMID 33281976)",
        directionality=Directionality.ambiguous,
        notes="Glucose-deprivation DEGs indicated Hippo pathway involvement in MCF-7 "
        "(GSE153830 series summary). Panel=other (no Hippo panel defined in spec).",
    ),
    dict(
        key="mcf7_bhb10_null",
        modifier_id="MOD-BHB-10MM-96H",
        cell_line_id="MCF7_BREAST",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="GSE153830; Zhang et al. 2021 (PMID 33281976)",
        directionality=Directionality.ambiguous,
        notes="No significant pathway enrichment detected for 10 mM BHB in MCF-7 "
        "(series summary: limited transcriptional impact).",
    ),
    dict(
        key="t47d_bhb25_null",
        modifier_id="MOD-BHB-25MM-96H",
        cell_line_id="T47D_BREAST",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="GSE153830; Zhang et al. 2021 (PMID 33281976)",
        directionality=Directionality.ambiguous,
        notes="No significant pathway enrichment detected for 25 mM BHB in T47D "
        "(series summary: limited transcriptional impact).",
    ),
    dict(
        key="mcf7_ht45_hsf1",
        modifier_id="MOD-HT-45C-GSE48398",
        cell_line_id="MCF7_BREAST",
        signature_panel=SignaturePanel.hsf1_hsp,
        score=None,
        raw_deg_evidence_ref="GSE48398 series (submitter publication PMID 27245201)",
        directionality=Directionality.death_promoting,
        notes="Malignant breast lines mount a distinct heat-shock transcriptional "
        "response vs MCF-10A; series premise is enhanced malignant susceptibility "
        "to 42-45 degC hyperthermia.",
    ),
    dict(
        key="mdamb231_ht45_hsf1",
        modifier_id="MOD-HT-45C-GSE48398",
        cell_line_id="MDAMB231_BREAST",
        signature_panel=SignaturePanel.hsf1_hsp,
        score=None,
        raw_deg_evidence_ref="GSE48398 series (submitter publication PMID 27245201)",
        directionality=Directionality.death_promoting,
        notes="As for MCF-7: distinct malignant heat-shock response (GSE48398).",
    ),
    dict(
        key="mdamb468_ht45_hsf1",
        modifier_id="MOD-HT-45C-GSE48398",
        cell_line_id="MDAMB468_BREAST",
        signature_panel=SignaturePanel.hsf1_hsp,
        score=None,
        raw_deg_evidence_ref="GSE48398 series (submitter publication PMID 27245201)",
        directionality=Directionality.death_promoting,
        notes="As for MCF-7: distinct malignant heat-shock response (GSE48398).",
    ),
    dict(
        key="mcf10a_ht45_hsf1",
        modifier_id="MOD-HT-45C-GSE48398",
        cell_line_id="MCF10A_BREAST",
        signature_panel=SignaturePanel.hsf1_hsp,
        score=None,
        raw_deg_evidence_ref="GSE48398 series (submitter publication PMID 27245201)",
        directionality=Directionality.ambiguous,
        notes="Non-malignant comparator; relative thermoresistance is the series "
        "premise. Directionality ambiguous at signature level.",
    ),
    dict(
        key="u937_ht41_hsf1_protective",
        modifier_id="MOD-HT-41C-30M",
        cell_line_id="U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE",
        signature_panel=SignaturePanel.hsf1_hsp,
        score=None,
        raw_deg_evidence_ref="GSE10043; Tabuchi et al. 2008 (PMID 18608577)",
        directionality=Directionality.protective_resistance,
        notes="41 degC/30 min induced HSF1 with Hsp40/Hsp70 up-regulation and no "
        "apoptosis, consistent with a protective heat-shock program "
        "(thermotolerance) rather than death.",
    ),
    dict(
        key="du145_hypoxia_hif1",
        modifier_id="MOD-HYP-1O2-24H",
        cell_line_id="DU145_PROSTATE",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="Review-level: Rohwer & Cramer 2011 (PMID 21466972)",
        directionality=Directionality.protective_resistance,
        notes="HIF-1-driven hypoxia response attenuates drug-induced apoptosis "
        "(review-level evidence; no single experiment anchors this row).",
    ),
    dict(
        key="mdamb231_cys_withdrawal_ferroptosis",
        modifier_id="MOD-CYS-WITHDRAWAL",
        cell_line_id="MDAMB231_BREAST",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
        score=None,
        raw_deg_evidence_ref="GSE237928; Swanda et al. 2023 (PMID 37647899)",
        directionality=Directionality.death_promoting,
        notes="Cystine withdrawal engages the cysteine-stress/ferroptosis response "
        "(GSE237928 series); ferrostatin-1 (not Z-VAD/necrostatin) rescues "
        "viability, confirming a ferroptotic (NRF2-ferroptosis axis) death mode. "
        "Quantitative ssGSEA score pending pipeline re-computation from raw counts.",
    ),
    # --- New 2026-09-21 curation pass (literature-verified; see [S11]-[S15]) ---
    dict(
        key="fast4t1_akt_oxid",
        modifier_id="MOD-FAST-CYCLES-48-60H",
        cell_line_id="4T1_BREAST",
        signature_panel=SignaturePanel.dna_damage,
        score=None,
        raw_deg_evidence_ref="Lee C et al. 2012 (PMID 22323820), Sci Transl Med "
        "4(127):124ra27 (published figures; no transcriptomic accession)",
        directionality=Directionality.death_promoting,
        notes="In 4T1 breast cancer cells, short-term starvation increased "
        "phosphorylation of the stress-sensitizing Akt and S6 kinases, with "
        "increased oxidative stress, caspase-3 cleavage, DNA damage and "
        "apoptosis (abstract-verified). Adding IGF-1 reversed the starvation-"
        "driven sensitization of 4T1 and B16 cells to doxorubicin, implicating "
        "the IGF-1/growth-factor axis in differential stress sensitization.",
    ),
    dict(
        key="hct116_serine_p53p21",
        modifier_id="MOD-SERINE-GLYCINE-FREE",
        cell_line_id="HCT116_LARGE_INTESTINE",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
        score=None,
        raw_deg_evidence_ref="Maddocks et al. 2012 (PMID 23242140), Nature 493:542-6",
        directionality=Directionality.protective_resistance,
        notes="In p53+/+ HCT116 cells, serine/glycine withdrawal triggers "
        "transient p53-p21 (CDKN1A) cell-cycle arrest that promotes survival "
        "by channelling depleted serine stores into glutathione synthesis, "
        "preserving antioxidant capacity (Nature 2012). Directionality is "
        "protective for the p53-WT state under this modifier.",
    ),
    dict(
        key="hct116p53null_serine_oxid",
        modifier_id="MOD-SERINE-GLYCINE-FREE",
        cell_line_id="HCT116P53NULL_LARGE_INTESTINE",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
        score=None,
        raw_deg_evidence_ref="Maddocks et al. 2012 (PMID 23242140); p53-/- "
        "response per Figs. 1a-c and 3 (PMC6485472 full text)",
        directionality=Directionality.death_promoting,
        notes="p53-/- HCT116 cells fail the serine-starvation metabolic "
        "remodelling response: no protective p53-p21 arrest, oxidative stress, "
        "reduced viability and severely impaired proliferation; serine/glycine-"
        "depleted diet also significantly reduced p53-/- xenograft volume in "
        "vivo (translates to p53-deficient tumour vulnerability).",
    ),
    dict(
        key="rko_irrad_3ap_dna",
        modifier_id="MOD-IRRAD-SINGLE-DOSE",
        cell_line_id="RKO_LARGE_INTESTINE",
        signature_panel=SignaturePanel.dna_damage,
        score=None,
        raw_deg_evidence_ref="Kunos CA et al. 2009 (PMID 19929413), Radiat Res "
        "172(6):666-76 (published figures; no transcriptomic accession)",
        directionality=Directionality.death_promoting,
        notes="3-AP (triapine) treatment significantly decreased RNR activity "
        "and caused prolonged radiation-induced DNA damage with extended G1/S "
        "arrest in all tested lines; effects were similar in RKO (p53 WT) and "
        "RKO-E6 (E6-silenced p53), demonstrating a p53-independent "
        "radiosensitization mechanism (impaired repair relying on dNTP supply).",
    ),
    dict(
        key="a549_allicin_hif_ros",
        modifier_id="MOD-ALICIN-NSCLC",
        cell_line_id="A549_LUNG",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="Pandey N et al. 2020 (PMID 32809300), Cell Physiol "
        "Biochem 54(4):748-766 (published figures; no transcriptomic accession)",
        directionality=Directionality.death_promoting,
        notes="Allicin decreases A549 viability/proliferation/migration in "
        "normoxia and hypoxia via ROS accumulation (ROS/MAPK and ROS/JNK), "
        "elicits apoptosis + autophagy with S/G2-M arrest, and suppresses "
        "HIF-1alpha/HIF-2alpha expression in hypoxic cells - overcoming "
        "hypoxia-mediated resistance. Panel=other (no HIF panel in spec).",
    ),
    dict(
        key="mdamb231_dha_dox_apop",
        modifier_id="MOD-DHA-60UM",
        cell_line_id="MDAMB231_BREAST",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="Newell M et al. 2019 (PMID 30601995), J Nutr "
        "149(1):46-56 (microarray/protein readouts; no public accession)",
        directionality=Directionality.death_promoting,
        notes="DHA + doxorubicin (vs OALA + DOX) upregulated apoptosis genes "
        "(Caspase-10 1.3x, Caspase-9 1.4x, RIPK1 1.2x) and downregulated "
        "cell-cycle genes (Cyclin B1 -2.1x, WEE1 -1.6x, CDC25C -1.8x); in "
        "tumours: increased Caspase-10/Bid, decreased BCL2. Panel=other "
        "(apoptosis/cell-cycle gene signature).",
    ),
    # --- New 2026-09-22 curation pass (glutamine/methionine restriction, HBOT, TTFields, PEMF) ---
    dict(
        key="mdamb231_glutamine_xct",
        modifier_id="MOD-GLUTAMINE-RESTRICT",
        cell_line_id="MDAMB231_BREAST",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
        score=None,
        raw_deg_evidence_ref="GSE26370 (Kung et al. 2011, PMID 21852960); "
        "GSE48984 (Timmerman et al. 2013, PMID 24094812)",
        directionality=Directionality.death_promoting,
        notes="MDA-MB-231 (basal/TNBC) is glutamine-dependent (Kung et al. 2011); "
        "a functional screen of 46 breast lines identified the SLC7A11/xCT "
        "cystine-glutamate antiporter as the determinant of glutamine addiction, "
        "concentrated in TNBC lines (Timmerman et al. 2013) -- the same node "
        "already tracked as a resistance mechanism for metformin/erastin.",
    ),
    dict(
        key="mcf7_glutamine_gs_protective",
        modifier_id="MOD-GLUTAMINE-RESTRICT",
        cell_line_id="MCF7_BREAST",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="GSE26370 (Kung et al. 2011, PMID 21852960)",
        directionality=Directionality.protective_resistance,
        notes="MCF-7 (luminal) is glutamine-independent via glutamine synthetase "
        "expression, which bypasses the deprivation and represses glutaminase "
        "(Kung et al. 2011). Panel=other: this bypass is biosynthetic, not the "
        "xCT/ferroptosis axis the MDA-MB-231 leg above runs through.",
    ),
    dict(
        key="hct116_methionine_onecarbon",
        modifier_id="MOD-METHIONINE-RESTRICT",
        cell_line_id="HCT116_LARGE_INTESTINE",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="GSE72131 (Mentch et al. 2015, PMID 26411344); "
        "GSE103602 (Dai et al. 2018, PMID 29769529)",
        directionality=Directionality.death_promoting,
        notes="Methionine restriction depletes SAM/one-carbon metabolism, "
        "remodeling H3K4me3 and gene expression in HCT116 (Mentch et al. 2015; "
        "Dai et al. 2018) -- the source studies measure epigenomic/expression "
        "change, not a direct death readout; the death-promoting call reflects "
        "the field's clinical/mechanistic framing of methionine restriction as "
        "an antimetabolite-chemotherapy sensitizer (see [C3], Durando et al. "
        "2010), not a result reported in GSE72131/GSE103602 themselves. "
        "Panel=other (epigenomic remodeling, not one of the five curated panels).",
    ),
    dict(
        key="a549_hbot_hif_pfkp",
        modifier_id="MOD-HBOT",
        cell_line_id="A549_LUNG",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="Zhang et al. 2021 (PMID 34367973), Front Oncol "
        "11:691762 (published figures; no transcriptomic accession)",
        directionality=Directionality.death_promoting,
        notes="HBO represses the HIF-1alpha/PFKP axis in hypoxic A549 (and "
        "H1299), suppressing the Warburg effect, hyperproliferation and EMT -- "
        "i.e. reversing a hypoxia-driven resistance/aggressiveness program, "
        "the opposite direction from the existing hypoxia signature "
        "(MOD-HYP-1O2-24H, protective_resistance). Panel=other (no HIF/"
        "glycolysis panel in spec).",
    ),
    dict(
        key="u87mg_ttfields_brca",
        modifier_id="MOD-TTFIELDS-200KHZ",
        cell_line_id="U87MG_CENTRAL_NERVOUS_SYSTEM",
        signature_panel=SignaturePanel.dna_damage,
        score=None,
        raw_deg_evidence_ref="Fishman et al. 2023 (PMID 37131108), J Neurooncol "
        "163(1):83-94 (published figures; no public transcriptomic accession)",
        directionality=Directionality.death_promoting,
        notes="TTFields downregulate the FA-BRCA DNA-damage-response pathway "
        "(BRCAness), increasing TMZ- and CCNU-induced DNA damage across the "
        "tested glioblastoma lines including U-87 MG.",
    ),
    dict(
        key="u87mg_pemf_stemness",
        modifier_id="MOD-PEMF-XRBK11",
        cell_line_id="U87MG_CENTRAL_NERVOUS_SYSTEM",
        signature_panel=SignaturePanel.other,
        score=None,
        raw_deg_evidence_ref="Gulla et al. 2026 (PMID 41957483), Sci Rep "
        "(published figures; no public transcriptomic accession)",
        directionality=Directionality.death_promoting,
        notes="The XR-BK11 PEMF sequence suppresses stemness markers (OCT4/"
        "NANOG) and PI3K/AKT signaling in U-87 MG, and potentiates "
        "temozolomide-induced apoptosis (caspase-3) and viability loss. "
        "Panel=other (stemness/PI3K-AKT signature, not one of the five "
        "curated panels).",
    ),
]

# ---------------------------------------------------------------------------
# Interaction effects — the core output table (all three evidence tiers).
# mechanism_key references SIGNATURE_SCORES keys above (resolved in seed()).
# ---------------------------------------------------------------------------

INTERACTIONS = [
    # --- Tier 1 (direct): Helderman et al. 2020, HIPEC-mimetic hyperthermia ---
    dict(
        modifier_id="MOD-HT-42C-60M-HIPEC", drug_id="cisplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Platinum drugs showed temperature-dependent synergy with "
        "heat at >=41 degC (increased platinum uptake ~2x, increased DNA damage "
        "and apoptosis; thermosensitization ratio > 1). Real TER=3.5 found "
        "(2026-09-23) but only at 43 degC, not this modifier's exact 42 degC "
        "protocol -- left as combined_effect_metric=None rather than assign a "
        "value from a different condition (see carboplatin's entry, which does "
        "have a real 42 degC-matched TER, for the metric definition).",
    ),
    dict(
        key="hipec_oxaliplatin_rko",
        modifier_id="MOD-HT-42C-60M-HIPEC", drug_id="oxaliplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Temperature-dependent synergy at >=41 degC "
        "(Helderman et al. 2020). The text states the RKO oxaliplatin TER "
        "of 3.3 at 43 degC, which is stored on MOD-HT-43C-60M-HIPEC. This "
        "42 degC row stays without a number.",
    ),
    dict(
        modifier_id="MOD-HT-42C-60M-HIPEC", drug_id="carboplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=3.8,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Real, protocol-matched quantitative metric (2026-09-23): "
        "Thermal Enhancement Ratio (TER) = 3.8 at 42 degC in RKO, as directly "
        "reported by Helderman et al. 2020 (main text: 'TER ratios of 2.5, 3.8, "
        "and 7.2 at 41, 42, and 43 degC, respectively'). TER = IC50(37 degC) / "
        "IC50(hyperthermia) -- a real literature-reported synergy metric, NOT a "
        "Bliss/Loewe/HSA/ZIP score from synlethality/scoring.py. The heat maps "
        "do not print per-cell numbers. The 41 degC (2.5) and 43 degC (7.2) RKO "
        "carboplatin TERs from the same sentence are on their own modifiers.",
    ),
    dict(
        modifier_id="MOD-HT-41C-60M-HIPEC", drug_id="carboplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=2.5,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Helderman et al. 2020, main text: carboplatin TER in RKO "
        "is 2.5, 3.8, and 7.2 at 41, 42, and 43 degC. TER = IC50(37 degC) / "
        "IC50(heated), 60 min water bath, viability at 48 h.",
    ),
    dict(
        modifier_id="MOD-HT-43C-60M-HIPEC", drug_id="carboplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=7.2,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Same sentence as the 2.5 and 3.8 RKO carboplatin rows. "
        "TER 7.2 at 43 degC for 60 min.",
    ),
    dict(
        modifier_id="MOD-HT-43C-60M-HIPEC", drug_id="oxaliplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=3.3,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Helderman et al. 2020: oxaliplatin TER values of RKO and "
        "HCT116 are the highest, 3.3 and 3.1, respectively, at 43 degC "
        "(Figure S4). TER = IC50(37) / IC50(43), 60 min.",
    ),
    dict(
        modifier_id="MOD-HT-43C-60M-HIPEC", drug_id="oxaliplatin",
        cell_line_id="HCT116_LARGE_INTESTINE",
        combined_effect_metric=3.1,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Same sentence as the RKO oxaliplatin 3.3 row. HCT116, "
        "43 degC, 60 min, viability TER.",
    ),
    dict(
        modifier_id="MOD-HT-43C-60M-HIPEC", drug_id="cisplatin",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=3.5,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Helderman et al. 2020: TER values increased at higher "
        "temperatures, starting at 41 degC, to 3.5, 2.8, and 3.9 in RKO, "
        "HCT116, and COLO320 (Figure S4). Stored at 43 degC, the top of that "
        "range, matching the oxaliplatin sentence in the same section which "
        "names 43 degC for its peak values. TER = IC50(37)/IC50(heated), 60 min. "
        "COLO320 is not in the curated cell-line table.",
    ),
    dict(
        modifier_id="MOD-HT-43C-60M-HIPEC", drug_id="cisplatin",
        cell_line_id="HCT116_LARGE_INTESTINE",
        combined_effect_metric=2.8,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Same Helderman sentence as the RKO cisplatin 3.5 row. "
        "HCT116, 43 degC, 60 min.",
    ),
    dict(
        modifier_id="MOD-HT-42C-60M-HIPEC", drug_id="5-fluorouracil",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.additive,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="Apoptosis increased after 5-FU but without temperature-"
        "dependent synergy with heat (Helderman et al. 2020).",
    ),
    dict(
        modifier_id="MOD-HT-42C-60M-HIPEC", drug_id="mitomycin-c",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.additive,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/cells9081775", "pmid:32722384"],
        curator_notes="MMC induced apoptosis but no temperature-dependent synergy "
        "with heat (Helderman et al. 2020).",
    ),
    # --- Tier 1 (direct): Kusumoto et al. 1993 (PMID 8347479), schedule-dependence
    # of heat + platinum drugs, HeLa -- real values found in running text (Results),
    # not digitized from a figure. Track C, 2026-09-23. Metric here is a
    # *survival-curve-slope enhancement ratio* (heat+drug slope / drug-alone slope,
    # from colony-formation survival assays), explicitly NOT the classic TER
    # definition (IC-something ratio) used by the Helderman entries above --
    # per the build order's "do not homogenize across metric types" rule, this
    # is spelled out in full below rather than folded into a shared "TER" label.
    # Simultaneous cisplatin (3.10) and carboplatin (2.96), plus heat-before
    # carboplatin (2.85, discussion). Heat-after and the intermediate
    # intervals are still Figure 2/3/5 only (see ter_corpus.json).
    # Intracellular platinum ratios in Table I are a different metric and
    # are not stored in combined_effect_metric.
    dict(
        modifier_id="MOD-HT-42.8C-30M-SIMUL", drug_id="cisplatin",
        cell_line_id="HELA_CERVIX",
        combined_effect_metric=3.10,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["pmid:8347479", "doi:10.1038/bjc.1993.324"],
        curator_notes="Real, protocol-matched quantitative metric (2026-09-23): "
        "survival-curve-slope enhancement ratio = 3.10 (colony-formation assay "
        "regression slopes: -0.0430 min^-1 cisplatin alone [33.2 uM, 30 min] vs "
        "-0.1331 min^-1 for cisplatin + simultaneous heat [42.8 degC], P<0.01 vs "
        "other schedules) -- Kusumoto et al. 1993 main text. Not a classic TER "
        "(no IC-something ratio reported); recorded as this paper's own headline "
        "enhancement number, metric type spelled out here per the build order's "
        "metric-homogeneity rule. Simultaneous schedule was the most cytotoxic of "
        "the schedules tested for cisplatin (heat-before/after less effective).",
    ),
    dict(
        modifier_id="MOD-HT-42.8C-30M-SIMUL", drug_id="carboplatin",
        cell_line_id="HELA_CERVIX",
        combined_effect_metric=2.96,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["pmid:8347479", "doi:10.1038/bjc.1993.324"],
        curator_notes="Real, protocol-matched quantitative metric (2026-09-23): "
        "survival-curve-slope enhancement ratio = 2.96 (colony-formation assay "
        "regression slopes: -0.0154 min^-1 carboplatin alone [265 uM, 30 min] vs "
        "-0.0456 min^-1 for carboplatin + simultaneous heat [42.8 degC], P<0.01 "
        "vs other schedules) -- Kusumoto et al. 1993 main text. Same metric-type "
        "caveat as the cisplatin entry above. Note this paper found carboplatin's "
        "*greatest* effect with heat-before-or-during (not strictly simultaneous, "
        "unlike cisplatin) -- the simultaneous value is reported here because it's "
        "the one schedule with an explicit plain-text number in the Results. "
        "The discussion separately states the heat-before carboplatin "
        "survival effect as 2.85; that schedule is its own row.",
    ),
    dict(
        modifier_id="MOD-HT-42.8C-30M-BEFORE", drug_id="carboplatin",
        cell_line_id="HELA_CERVIX",
        combined_effect_metric=2.85,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["pmid:8347479", "doi:10.1038/bjc.1993.324"],
        curator_notes="Real quantitative metric (2026-09-24), discussion of "
        "Kusumoto et al. 1993: 'the increased effects seen for heat prior to "
        "carboplatin were almost identical (2.85 vs 2.75).' 2.85 is the "
        "survival-curve-slope enhancement (same metric as the simultaneous "
        "2.96 row, not a classic TER). 2.75 is Table I's intracellular "
        "platinum accumulation ratio for heat-before carboplatin and is not "
        "this field. Protocol: 42.8 degC for 30 min, then 265 uM carboplatin, "
        "30 min interval (Table I / Figure 3). HeLa colony formation.",
    ),
    # --- Tier 1 (direct): Raffaele et al. 2019, metformin x low glucose, DU-145 ---
    dict(
        modifier_id="MOD-GLUCOSE-LOW-DU145", drug_id="metformin",
        cell_line_id="DU145_PROSTATE",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.3390/ijms20102593", "pmid:31137785"],
        curator_notes="Metformin anti-proliferative effect was glucose-concentration-"
        "dependent: low glucose potentiated metformin-mediated DU-145 cell death "
        "(MTT/xCELLigence); HO-1 inhibition further sensitized cells.",
    ),

    # --- Tier 2 (inferred): two verified legs, shared mechanism, no combo readout ---
    dict(
        modifier_id="MOD-GLUCOSE-RESTRICT-5PCT-96H", drug_id="metformin",
        cell_line_id="T47D_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_2_inferred,
        mechanism_key="t47d_glucose_nrf2",
        source_study=["pmid:33281976", "pmid:34162423"],
        curator_notes="Modifier leg: glucose deprivation engaged the NRF2-ferroptosis "
        "axis in T47D (GSE153830; Zhang et al. 2021). Drug leg: metformin induces "
        "ferroptosis in breast cancer cells via SLC7A11 UFMylation inhibition "
        "(Yang et al. 2021). No combination viability readout exists in either "
        "study — inferred via shared ferroptosis mechanism.",
    ),
    dict(
        modifier_id="MOD-GLUCOSE-RESTRICT-5PCT-96H", drug_id="metformin",
        cell_line_id="MCF7_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_2_inferred,
        mechanism_key="mcf7_glucose_hippo",
        source_study=["pmid:33281976", "pmid:24338509"],
        curator_notes="Modifier leg: glucose deprivation engaged Hippo-pathway DEGs "
        "in MCF-7 (GSE153830). Drug leg: metformin impairs MCF-7 growth via "
        "AMPK-dependent and -independent mechanisms (Hadad et al. 2014). Hypothesized "
        "energetic-stress synergy; no combination viability readout exists.",
    ),
    # --- Tier 3 (mechanism-only): signature overlap only ---
    dict(
        modifier_id="MOD-HT-41C-30M", drug_id="doxorubicin",
        cell_line_id="U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE",
        combined_effect_metric=None,
        interaction_type=InteractionType.unknown,
        evidence_tier=EvidenceTier.tier_3_mechanism_only,
        mechanism_key="u937_ht41_hsf1_protective",
        source_study=["doi:10.1080/02656730802140777", "pmid:18608577"],
        curator_notes="Series reports no drug readout; the paper's introduction "
        "notes literature observations of mild-hyperthermia synergism with "
        "anti-cancer drugs. Mechanism-only entry pending a combination study. "
        "Note protective HSF1 program at this temperature argues against naive "
        "synergy assumptions.",
    ),
    dict(
        modifier_id="MOD-HYP-1O2-24H", drug_id="doxorubicin",
        cell_line_id="DU145_PROSTATE",
        combined_effect_metric=None,
        interaction_type=InteractionType.antagonistic,
        evidence_tier=EvidenceTier.tier_3_mechanism_only,
        mechanism_key="du145_hypoxia_hif1",
        source_study=["doi:10.1016/j.drup.2011.03.001", "pmid:21466972"],
        curator_notes="Review-level evidence that HIF-1 activity attenuates "
        "drug-induced apoptosis (hypoxia-mediated drug resistance); no "
        "line-specific combination readout. Representative hypoxia protocol "
        "parameters.",
    ),
    dict(
        modifier_id="MOD-HT-45C-GSE48398", drug_id="cisplatin",
        cell_line_id="MCF7_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.unknown,
        evidence_tier=EvidenceTier.tier_3_mechanism_only,
        mechanism_key="mcf7_ht45_hsf1",
        source_study=["geo:GSE48398", "pmid:32722384"],
        curator_notes="Heat-shock response measured in MCF-7 (expression only, "
        "GSE48398); platinum-heat synergy measured in CRC lines, not MCF-7 "
        "(Helderman et al. 2020). Mechanism-only.",
    ),
    # --- Tier 1 (direct): Swanda et al. 2023, cystine withdrawal x erastin ---
    dict(
        modifier_id="MOD-CYS-WITHDRAWAL", drug_id="erastin",
        cell_line_id="MDAMB231_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="mdamb231_cys_withdrawal_ferroptosis",
        source_study=["doi:10.1016/j.molcel.2023.08.004", "geo:GSE237928"],
        curator_notes="Cystine withdrawal combined with the system Xc- inhibitor "
        "erastin in the source study's cell-line panel; combined ferroptotic "
        "death was ferrostatin-1-rescuable (Swanda et al. 2023). Quantitative "
        "per-line viability/dose data pending curation from source figures; "
        "note erastin also blocks cystine uptake, so the two legs act on an "
        "overlapping node (system Xc-) rather than fully independent pathways.",
    ),
    # --- Tier 1 (direct): Chen et al. 2025, substrate stiffness x chemotherapy ---
    dict(
        modifier_id="MOD-STIFFNESS-53KPA-5G5P", drug_id="doxorubicin",
        cell_line_id="MDAMB231_BREAST",
        combined_effect_metric=4.71,
        interaction_type=InteractionType.antagonistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1021/acsbiomaterials.4c01636", "pmid:40013911"],
        curator_notes="Real, exact quantitative metric (2026-09-23): IC50 fold-shift "
        "= 2311 nM (5G5P, ~53 kPa) / 490.7 nM (2D control) = 4.71, from Chen et al. "
        "2025's own directly-reported IC50 values (mean +/- SD: 2311 +/- 356.7 nM "
        "vs 490.7 +/- 34.36 nM) at 48h in MDA-MB-231. This is an IC50 fold-shift "
        "(how much less potent the drug becomes on stiff matrix vs 2D), NOT a "
        "Bliss/Loewe/HSA/ZIP score from synlethality/scoring.py -- that engine "
        "needs a combined viability matrix at shared doses, which the paper "
        "reports as two separately-fit dose-response curves instead. Fold-shift "
        "> 1 = drug less effective on stiff matrix, consistent with the "
        "antagonistic call.",
    ),
    dict(
        modifier_id="MOD-STIFFNESS-53KPA-5G5P", drug_id="paclitaxel",
        cell_line_id="MDAMB231_BREAST",
        combined_effect_metric=6.65,
        interaction_type=InteractionType.antagonistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1021/acsbiomaterials.4c01636", "pmid:40013911"],
        curator_notes="Real, exact quantitative metric (2026-09-23): IC50 fold-shift "
        "= 51.64 nM (5G5P) / 7.765 nM (2D control) = 6.65, from Chen et al. 2025's "
        "own directly-reported IC50 values (51.64 +/- 2.402 nM vs 7.765 +/- "
        "0.2823 nM) at 48h in MDA-MB-231. Same metric definition as the "
        "doxorubicin entry above (fold-shift, not a Bliss/Loewe/HSA/ZIP score).",
    ),
    dict(
        modifier_id="MOD-STIFFNESS-53KPA-5G5P", drug_id="doxorubicin",
        cell_line_id="MCF7_BREAST",
        combined_effect_metric=4.3,
        interaction_type=InteractionType.antagonistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1021/acsbiomaterials.4c01636", "pmid:40013911"],
        curator_notes="Real, exact quantitative metric (2026-09-23): IC50 fold-shift "
        "= 566.7 nM (5G5P) / 131.8 nM (2D control) = 4.30, from Chen et al. 2025's "
        "own directly-reported IC50 values (566.7 +/- 40.41 nM vs 131.8 +/- 12.45 "
        "nM) at 48h in MCF-7. Same metric definition as the MDA-MB-231 doxorubicin "
        "entry above (fold-shift, not a Bliss/Loewe/HSA/ZIP score). Notably a "
        "smaller fold-shift than MDA-MB-231's (4.71) -- a real, cross-line "
        "difference this data captures, not asserted.",
    ),
    dict(
        modifier_id="MOD-STIFFNESS-53KPA-5G5P", drug_id="paclitaxel",
        cell_line_id="MCF7_BREAST",
        combined_effect_metric=3.77,
        interaction_type=InteractionType.antagonistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1021/acsbiomaterials.4c01636", "pmid:40013911"],
        curator_notes="Real, exact quantitative metric (2026-09-23): IC50 fold-shift "
        "= 308.3 nM (5G5P) / 81.87 nM (2D control) = 3.77, from Chen et al. 2025's "
        "own directly-reported IC50 values (308.3 +/- 25.07 nM vs 81.87 +/- 15.80 "
        "nM) at 48h in MCF-7. Same metric definition as the other three entries "
        "above (fold-shift, not a Bliss/Loewe/HSA/ZIP score).",
    ),
    # ---------------------------------------------------------------------------
    # New 2026-09-21 curation pass (literature-verified abstracts/full text;
    # sources [S11]-[S15]). No fabricated quantitative metrics.
    # ---------------------------------------------------------------------------
    # --- Tier 1 (direct): Lee et al. 2012, fasting cycles x chemo (4T1) ---
    dict(
        key="fasting_doxorubicin_4t1",
        modifier_id="MOD-FAST-CYCLES-48-60H", drug_id="doxorubicin",
        cell_line_id="4T1_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="fast4t1_akt_oxid",
        source_study=["doi:10.1126/scitranslmed.3003293", "pmid:22323820"],
        curator_notes="Serum from 48-h-fasted mice sensitized 4T1 cells to "
        "doxorubicin (DXR) vs serum from ad-lib-fed mice (Lee et al. 2012); "
        "starvation raised Akt/S6K phosphorylation, oxidative stress, caspase-3 "
        "cleavage, DNA damage and apoptosis in 4T1, and IGF-1 addback reversed "
        "the sensitization (IGF-1/growth-factor axis). In vivo, fasting cycles "
        "retarded 4T1/B16/GL26 allograft growth and fasting+chemotherapy gave "
        "long-term cancer-free survival in neuroblastoma models. Quantitative "
        "doses/percentages pending curation from source figures.",
    ),
    dict(
        key="fasting_cyclophosphamide_4t1",
        modifier_id="MOD-FAST-CYCLES-48-60H", drug_id="cyclophosphamide",
        cell_line_id="4T1_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1126/scitranslmed.3003293", "pmid:22323820"],
        curator_notes="Serum from 48-h-fasted mice also sensitized 4T1 cells to "
        "cyclophosphamide (CP) in the in-vitro serum-transfer assay (Lee et al. "
        "2012). The paper's in-vivo arms are reported against DXR and other "
        "agents; per-figure CP dosing pending curation.",
    ),
    # --- Tier 1 (direct): Kunos et al. 2009, triapine x radiation ---
    dict(
        modifier_id="MOD-IRRAD-SINGLE-DOSE", drug_id="triapine",
        cell_line_id="RKO_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="rko_irrad_3ap_dna",
        source_study=["doi:10.1667/RR1858.1", "pmid:19929413"],
        curator_notes="3-AP significantly enhanced radiation-related "
        "cytotoxicity in RKO (and p53-silenced RKO-E6): decreased RNR activity, "
        "prolonged radiation-induced DNA damage, extended G1/S arrest "
        "(Kunos et al. 2009). Similar effects in RKO vs RKO-E6 indicate a "
        "p53-independent radiosensitization mechanism.",
    ),
    dict(
        modifier_id="MOD-IRRAD-SINGLE-DOSE", drug_id="triapine",
        cell_line_id="HELA_CERVIX",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1667/RR1858.1", "pmid:19929413"],
        curator_notes="3-AP radiosensitization verified in HeLa (HPV18 E6/E7 "
        "virally silenced p53): enhanced radiation-related cytotoxicity, "
        "prolonged DNA damage, extended G1/S arrest (Kunos et al. 2009). "
        "Per-line effect sizes pending curation from source figures.",
    ),
    dict(
        modifier_id="MOD-IRRAD-SINGLE-DOSE", drug_id="triapine",
        cell_line_id="CASKI_CERVIX",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key=None,
        source_study=["doi:10.1667/RR1858.1", "pmid:19929413"],
        curator_notes="3-AP radiosensitization verified in CaSki (HPV16 E6/E7 "
        "virally silenced p53): enhanced radiation-related cytotoxicity "
        "(Kunos et al. 2009). Per-line effect sizes pending curation from "
        "source figures.",
    ),
    # --- Tier 1 (direct): Pandey et al. 2020, allicin x cisplatin (hypoxic A549) ---
    dict(
        modifier_id="MOD-ALICIN-NSCLC", drug_id="cisplatin",
        cell_line_id="A549_LUNG",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="a549_allicin_hif_ros",
        source_study=["doi:10.33594/000000253", "pmid:32809300"],
        curator_notes="Allicin synergistically enhanced the growth-inhibitory "
        "activity of low-dose cisplatin in A549 cells under hypoxia, "
        "overcoming hypoxia-induced cisplatin resistance via ROS accumulation, "
        "HIF-1alpha/HIF-2alpha suppression and ROS/JNK-MAPK signalling "
        "(Pandey et al. 2020); allicin alone was also efficacious in normoxia. "
        "Quantitative IC50/CI values pending curation from source figures.",
    ),
    # --- Tier 1 (direct): Newell et al. 2019, DHA x doxorubicin (MDA-MB-231) ---
    dict(
        modifier_id="MOD-DHA-60UM", drug_id="doxorubicin",
        cell_line_id="MDAMB231_BREAST",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="mdamb231_dha_dox_apop",
        source_study=["doi:10.1093/jn/nxy224", "pmid:30601995"],
        curator_notes="DHA pretreatment (60 uM + OALA) amplified the doxorubicin "
        "(0.41 uM) response in MDA-MB-231: Caspase-10/9 and RIPK1 upregulated, "
        "Cyclin B1/WEE1/CDC25C downregulated; in nu/nu mice, dietary DHA "
        "(2.8 g/100 g) + DOX yielded 50% smaller tumours than DOX alone "
        "(P < 0.05), with increased Caspase-10/Bid and decreased BCL2 (Newell "
        "et al. 2019). Framed by the source as DHA facilitating DOX action.",
    ),
    # --- Tier 3 (mechanism-only): serine starvation x oxidative drug stress ---
    dict(
        modifier_id="MOD-SERINE-GLYCINE-FREE", drug_id="doxorubicin",
        cell_line_id="HCT116P53NULL_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.unknown,
        evidence_tier=EvidenceTier.tier_3_mechanism_only,
        mechanism_key="hct116p53null_serine_oxid",
        source_study=["doi:10.1038/nature11743", "pmid:23242140"],
        curator_notes="Mechanism-only entry: p53-/- HCT116 cells fail the "
        "serine-starvation p53-p21/glutathione response and accumulate "
        "oxidative stress with reduced viability (Maddocks et al. 2012); "
        "doxorubicin imposes redox/nuclear stress, but the combination was not "
        "empirically tested in the source study. Awaiting a combination "
        "viability readout before any higher tier.",
    ),
    # --- New 2026-09-22 curation pass (glutamine/methionine restriction, HBOT, TTFields, PEMF) ---
    # Tier 2 (inferred): methionine restriction x FOLFOX components, HCT116
    dict(
        key="methionine_5fu_hct116",
        modifier_id="MOD-METHIONINE-RESTRICT", drug_id="5-fluorouracil",
        cell_line_id="HCT116_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_2_inferred,
        mechanism_key="hct116_methionine_onecarbon",
        source_study=["pmid:26411344", "pmid:20424491"],
        curator_notes="Modifier leg: methionine restriction remodels one-carbon "
        "metabolism/H3K4me3 in HCT116 (Mentch et al. 2015). Drug leg: 5-FU is "
        "the antimetabolite component of the FOLFOX regimen shown feasible "
        "with dietary methionine restriction in a Phase I/II colorectal-cancer "
        "trial (Durando et al. 2010, PMID 20424491; see [C3]). No cell-line-"
        "level combination viability readout exists in either source -- "
        "inferred via the shared one-carbon-metabolism/antimetabolite-"
        "sensitization mechanism and human trial precedent.",
    ),
    dict(
        key="methionine_oxaliplatin_hct116",
        modifier_id="MOD-METHIONINE-RESTRICT", drug_id="oxaliplatin",
        cell_line_id="HCT116_LARGE_INTESTINE",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_2_inferred,
        mechanism_key="hct116_methionine_onecarbon",
        source_study=["pmid:26411344", "pmid:20424491"],
        curator_notes="As for 5-fluorouracil: oxaliplatin is the platinum "
        "component of the same FOLFOX regimen tested with dietary methionine "
        "restriction in Durando et al. 2010 (PMID 20424491; see [C3]). No "
        "cell-line-level combination readout exists -- inferred via the "
        "shared mechanism and human trial precedent.",
    ),
    # --- Tier 3 (mechanism-only): HBOT reverses hypoxia-driven platinum resistance, A549 ---
    dict(
        modifier_id="MOD-HBOT", drug_id="cisplatin",
        cell_line_id="A549_LUNG",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_3_mechanism_only,
        mechanism_key="a549_hbot_hif_pfkp",
        source_study=["doi:10.3389/fonc.2021.691762", "pmid:34367973"],
        curator_notes="Mechanism-only entry, paralleling the curated allicin x "
        "cisplatin (hypoxic A549) entry above: HBO suppresses the HIF-1alpha/"
        "PFKP axis that otherwise drives hypoxia-mediated chemoresistance "
        "(Zhang et al. 2021), but no HBO x cisplatin combination was tested in "
        "the source study. Awaiting a combination viability readout.",
    ),
    # --- Tier 1 (direct): Fishman et al. 2023, TTFields x TMZ/CCNU, U-87 MG ---
    dict(
        modifier_id="MOD-TTFIELDS-200KHZ", drug_id="temozolomide",
        cell_line_id="U87MG_CENTRAL_NERVOUS_SYSTEM",
        combined_effect_metric=None,
        interaction_type=InteractionType.additive,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="u87mg_ttfields_brca",
        source_study=["doi:10.1007/s11060-023-04308-4", "pmid:37131108"],
        curator_notes="TTFields concomitant with TMZ displayed an additive "
        "effect irrespective of MGMT expression level across the tested "
        "glioblastoma lines, including U-87 MG (Fishman et al. 2023). "
        "Quantitative per-line viability values pending curation from source "
        "figures.",
    ),
    dict(
        modifier_id="MOD-TTFIELDS-200KHZ", drug_id="lomustine",
        cell_line_id="U87MG_CENTRAL_NERVOUS_SYSTEM",
        combined_effect_metric=None,
        interaction_type=InteractionType.additive,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="u87mg_ttfields_brca",
        source_study=["doi:10.1007/s11060-023-04308-4", "pmid:37131108"],
        curator_notes="TTFields concomitant with CCNU (lomustine) was additive "
        "in MGMT-expressing cells and synergistic in MGMT-non-expressing "
        "cells (Fishman et al. 2023); recorded conservatively as additive here "
        "since this build does not curate U-87 MG's specific MGMT-promoter-"
        "methylation status against the source figures. The paper also "
        "discusses a PARP-inhibitor combination as a hypothesis from the "
        "induced BRCAness state -- not experimentally tested in this study.",
    ),
    # --- Tier 1 (direct): Gulla et al. 2026, PEMF x temozolomide, U-87 MG ---
    dict(
        modifier_id="MOD-PEMF-XRBK11", drug_id="temozolomide",
        cell_line_id="U87MG_CENTRAL_NERVOUS_SYSTEM",
        combined_effect_metric=None,
        interaction_type=InteractionType.synergistic,
        evidence_tier=EvidenceTier.tier_1_direct,
        mechanism_key="u87mg_pemf_stemness",
        source_study=["doi:10.1038/s41598-026-47481-y", "pmid:41957483"],
        curator_notes="Combined PEMF (XR-BK11 sequence) + TMZ significantly "
        "reduced U-87 MG cell viability and enhanced apoptotic cell death "
        "(increased pro-apoptotic gene expression, caspase-3 activation) "
        "beyond either treatment alone (Gulla et al. 2026). Quantitative "
        "per-condition values pending curation from source figures.",
    ),
]

# ---------------------------------------------------------------------------
# Clinical evidence (build spec v3 `clinical_evidence`): aggregate, publicly
# published trial metadata only, answering "has anyone tested this
# combination in humans yet" -- never patient-level data. Verified directly
# against the ClinicalTrials.gov v2 API (see [C1]/[C2] above).
# linked_interaction_key resolves to linked_interaction_effect_id in seed(),
# same pattern as SIGNATURE_SCORES' mechanism_key.
# ---------------------------------------------------------------------------

CLINICAL_EVIDENCE = [
    dict(
        nct_id="NCT03028155",
        phase="Phase 3",
        status="Recruiting (last known; registry overall status: Unknown)",
        outcome_summary="Randomized comparison of concentration-based vs body-"
        "surface-area-based dosing for HIPEC (oxaliplatin, 460 mg/m^2, "
        "hyperthermic, ~30 min) after cytoreductive surgery in colorectal "
        "peritoneal carcinomatosis. Same procedure class as the RKO HIPEC x "
        "oxaliplatin interaction below (Helderman et al. 2020 in-vitro model), "
        "not an identical protocol -- dosing-approach comparison, not a "
        "hyperthermia-vs-no-hyperthermia arm.",
        publication_ref=None,
        linked_interaction_key="hipec_oxaliplatin_rko",
    ),
    dict(
        nct_id="NCT02126449",
        phase="Phase 2/3",
        status="Completed",
        outcome_summary="The DIRECT trial: fasting-mimicking diet (FMD) vs "
        "regular diet alongside AC>T neoadjuvant chemotherapy (doxorubicin + "
        "cyclophosphamide, then paclitaxel) in HER2-negative breast cancer "
        "(n=131). Radiological/pathological response occurred more often with "
        "FMD (de Groot et al. 2020, Nat Commun). Human trial evidence for the "
        "fasting x doxorubicin and fasting x cyclophosphamide pairing the "
        "mouse/cell model below (Lee et al. 2012) predicted -- not a claim "
        "that this trial validated the 4T1 findings specifically.",
        publication_ref="doi:10.1038/s41467-020-16138-3",
        linked_interaction_key="fasting_doxorubicin_4t1",
    ),
    dict(
        nct_id="NCT02126449",
        phase="Phase 2/3",
        status="Completed",
        outcome_summary="Same DIRECT trial as above (AC>T regimen includes "
        "cyclophosphamide); recorded as a second row since it links to a "
        "different interaction_effect (the cyclophosphamide leg) rather than "
        "duplicating the trial record.",
        publication_ref="doi:10.1038/s41467-020-16138-3",
        linked_interaction_key="fasting_cyclophosphamide_4t1",
    ),
    dict(
        nct_id=None,  # no NCT registration identified for this 2010 feasibility study
        phase="Phase 1/2 (feasibility)",
        status="Completed",
        outcome_summary="Dietary methionine restriction combined with first-line "
        "FOLFOX (5-FU + oxaliplatin + leucovorin) in metastatic colorectal "
        "cancer: acceptable toxicity and tumor response, though patients found "
        "the low-methionine diet unpalatable for long-term adherence (Durando "
        "et al. 2010). Human trial evidence for the same modifier-class x "
        "drug-class pairing the HCT116 methionine-restriction interactions "
        "below infer from cell/epigenomic studies -- not a claim that this "
        "trial validated the HCT116 findings specifically.",
        publication_ref="pmid:20424491",
        linked_interaction_key="methionine_5fu_hct116",
    ),
    dict(
        nct_id=None,
        phase="Phase 1/2 (feasibility)",
        status="Completed",
        outcome_summary="Same Durando et al. 2010 feasibility study as above "
        "(FOLFOX includes oxaliplatin); recorded as a second row since it "
        "links to a different interaction_effect (the oxaliplatin leg) rather "
        "than duplicating the trial record.",
        publication_ref="pmid:20424491",
        linked_interaction_key="methionine_oxaliplatin_hct116",
    ),
]

# ---------------------------------------------------------------------------
# Drug resistance mechanisms (build spec v5 `drug_resistance_mechanism`) --
# the drug-side counterpart to SIGNATURE_SCORES, matched against by
# synlethality/bridging.py to generate candidate synergy hypotheses. Citations
# verified 2026-09-21 directly against NCBI E-utilities esummary (not
# search-result text): PMID 9861196 (Reed E., Cancer Treat Rev 1998,
# "Platinum-DNA adduct, nucleotide excision repair and platinum based
# anti-cancer chemotherapy"), PMID 11818492 (Gottesman MM, Annu Rev Med 2002,
# "Mechanisms of cancer drug resistance"), PMID 12724731 (Longley DB et al.,
# Nat Rev Cancer 2003, "5-fluorouracil: mechanisms of action and clinical
# strategies"), PMID 24439385 (Yang WS et al., Cell 2014, "Regulation of
# ferroptotic cancer cell death by GPX4"), PMID 22632970 (Dixon SJ et al.,
# Cell 2012, "Ferroptosis: an iron-dependent form of nonapoptotic cell
# death" -- the original erastin/system Xc- paper). Metformin's row reuses
# [S8] (Yang J et al. 2021, PMID 34162423) already cited above.
#
# signature_panel is left NULL for doxorubicin/5-FU: efflux-transporter and
# enzyme-overexpression resistance don't map onto any of the five curated
# stress-signature panels, so the bridging module correctly cannot match
# against them yet -- populated here for completeness of "one row per drug
# in the library" per the spec, not because every row is matchable today.
# ---------------------------------------------------------------------------

DRUG_RESISTANCE_MECHANISMS = [
    dict(
        key="cisplatin_ner",
        drug_id="cisplatin",
        pathway_or_gene="ERCC1/XPF nucleotide excision repair (NER)",
        mechanism_description="NER removes platinum-DNA intrastrand adducts before "
        "they trigger apoptosis; elevated ERCC1/XPF activity is a well-established "
        "platinum-resistance mechanism across tumor types (Reed 1998).",
        source="pmid:9861196",
        signature_panel=SignaturePanel.dna_damage,
    ),
    dict(
        key="oxaliplatin_ner",
        drug_id="oxaliplatin",
        pathway_or_gene="ERCC1/XPF nucleotide excision repair (NER)",
        mechanism_description="As for cisplatin: NER-mediated adduct removal is the "
        "principal resistance mechanism for platinum agents generally (Reed 1998).",
        source="pmid:9861196",
        signature_panel=SignaturePanel.dna_damage,
    ),
    dict(
        key="carboplatin_ner",
        drug_id="carboplatin",
        pathway_or_gene="ERCC1/XPF nucleotide excision repair (NER)",
        mechanism_description="As for cisplatin: NER-mediated adduct removal is the "
        "principal resistance mechanism for platinum agents generally (Reed 1998).",
        source="pmid:9861196",
        signature_panel=SignaturePanel.dna_damage,
    ),
    dict(
        key="doxorubicin_abcb1",
        drug_id="doxorubicin",
        pathway_or_gene="ABCB1/P-glycoprotein drug efflux",
        mechanism_description="ABCB1 (P-gp) actively effluxes doxorubicin, one of "
        "the best-characterized multidrug-resistance mechanisms in oncology "
        "(Gottesman 2002).",
        source="pmid:11818492",
        signature_panel=None,
    ),
    dict(
        key="5fu_tyms",
        drug_id="5-fluorouracil",
        pathway_or_gene="TYMS (thymidylate synthase) overexpression",
        mechanism_description="Elevated thymidylate synthase overcomes 5-FU's "
        "TYMS-inhibitory mechanism, restoring dTMP synthesis (Longley et al. 2003).",
        source="pmid:12724731",
        signature_panel=None,
    ),
    dict(
        key="metformin_slc7a11",
        drug_id="metformin",
        pathway_or_gene="SLC7A11/xCT cystine-glutamate antiporter",
        mechanism_description="High SLC7A11/xCT expression sustains cystine import "
        "and glutathione synthesis, protecting against metformin-induced ferroptosis; "
        "metformin acts in part by destabilizing SLC7A11 via UFMylation inhibition "
        "(Yang et al. 2021, [S8] above).",
        source="pmid:34162423",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
    ),
    dict(
        key="erastin_gpx4",
        drug_id="erastin",
        pathway_or_gene="GPX4-dependent lipid-peroxide detoxification",
        mechanism_description="GPX4 detoxifies lipid peroxides downstream of "
        "cystine/glutathione depletion; sufficient GPX4 activity (or an intact "
        "glutathione pool feeding it) can rescue cells from erastin's system "
        "Xc- blockade despite cystine starvation (Dixon et al. 2012; Yang et al. "
        "2014).",
        source="pmid:24439385",
        signature_panel=SignaturePanel.nrf2_ferroptosis,
    ),
    # --- Added with the 2026-09-22 curation pass (TTFields/PEMF vs. MGMT) ---
    dict(
        key="temozolomide_mgmt",
        drug_id="temozolomide",
        pathway_or_gene="MGMT (O6-methylguanine-DNA methyltransferase)",
        mechanism_description="MGMT directly repairs the O6-methylguanine "
        "lesion TMZ induces, irreversibly inactivating the drug's cytotoxic "
        "mechanism; MGMT promoter methylation (low MGMT expression) predicts "
        "TMZ benefit, the landmark clinical correlation in glioblastoma "
        "(Hegi et al. 2005).",
        source="pmid:15758010",
        # Deliberately NOT tagged with a signature_panel (unlike every other
        # resistance-mechanism row): temozolomide's real-world relevance is
        # CNS-restricted (BBB-penetrant chemistry, glioma-specific clinical
        # use), unlike metformin/erastin's genuinely broad mechanisms.
        # Matching it via the generic dna_damage panel against any dna_damage
        # signature regardless of tumor type produced clinically nonsensical
        # bridging candidates (e.g. "temozolomide + colorectal cancer") when
        # this was tried -- see bridging.py docstring. The two real,
        # CNS-appropriate temozolomide interactions (TTFields, PEMF) are
        # already hand-curated above; this row exists for completeness of
        # "one row per drug in the library" and for future curator-reviewed
        # matching, not for automated cross-tissue bridging.
        signature_panel=None,
    ),
    dict(
        key="lomustine_mgmt",
        drug_id="lomustine",
        pathway_or_gene="MGMT (O6-methylguanine-DNA methyltransferase)",
        mechanism_description="Like temozolomide, lomustine (CCNU) alkylates "
        "DNA at O6-guanine; MGMT-mediated repair of this lesion is a shared "
        "resistance mechanism across O6-alkylating agents (Hegi et al. 2005 "
        "established the correlation for TMZ specifically; extended here to "
        "CCNU by shared lesion chemistry, not a CCNU-specific clinical study).",
        source="pmid:15758010",
        # Same CNS-restriction rationale as temozolomide_mgmt above.
        signature_panel=None,
    ),
    # --- Added 2026-09-22: completes resistance-mechanism coverage for the
    # 4 curated drugs that didn't have one yet (paclitaxel, mitomycin-c,
    # cyclophosphamide, triapine) -- real, PMID-verified per drug (see
    # [S22]-[S25] in the module docstring). Not a new tier or method; same
    # standard as the original 9 rows above. ---
    dict(
        key="paclitaxel_abcb1_tubb3",
        drug_id="paclitaxel",
        pathway_or_gene="ABCB1/P-glycoprotein efflux; TUBB3 (class III beta-tubulin) alteration",
        mechanism_description="ABCB1/P-gp-mediated efflux reduces intracellular "
        "paclitaxel accumulation; TUBB3 overexpression alters microtubule "
        "dynamics away from paclitaxel's stabilizing mechanism. FOXO3a-mediated "
        "feedback links the two: TUBB3 upregulation drives ABCB1 expression, "
        "compounding resistance (Aldonza et al. 2016).",
        source="pmid:27284014",
        signature_panel=None,
    ),
    dict(
        key="mitomycin_nqo1",
        drug_id="mitomycin-c",
        pathway_or_gene="NQO1 (NAD(P)H:quinone oxidoreductase 1) bioreductive activation",
        mechanism_description="Mitomycin C requires bioreductive activation "
        "(quinone to hydroquinone/semiquinone) to form the DNA-crosslinking "
        "species; NQO1 is a major activating enzyme in vivo (Gustafson et al. "
        "2003), so its loss/inhibition reduces effective drug activation -- "
        "the reverse of the more commonly cited overexpression-confers-"
        "resistance pattern seen for detox/efflux mechanisms elsewhere in "
        "this table.",
        source="pmid:12649308",
        signature_panel=None,
    ),
    dict(
        key="cyclophosphamide_aldh1a1",
        drug_id="cyclophosphamide",
        pathway_or_gene="ALDH1A1 (aldehyde dehydrogenase 1A1) detoxification",
        mechanism_description="Cytosolic ALDH1A1 oxidizes the active "
        "cyclophosphamide metabolite (aldophosphamide) to the inactive "
        "carboxyphosphamide; ALDH1A1 overexpression (originally shown via "
        "retroviral gene transfer into hematopoietic cell lines) confers "
        "cyclophosphamide resistance (Magni et al. 1996).",
        source="pmid:8562935",
        signature_panel=None,
    ),
    dict(
        key="triapine_rrm2",
        drug_id="triapine",
        pathway_or_gene="RRM2 (ribonucleotide reductase M2 subunit) overexpression",
        mechanism_description="Triapine directly inhibits RRM2 (iron chelation "
        "of the tyrosyl radical); RRM2 overexpression -- the same target the "
        "drug itself acts on -- is a documented general resistance mechanism "
        "across multiple RNR-dependent chemotherapies (Zuo et al. 2024 "
        "review), consistent with a titration-out-the-inhibitor pattern.",
        source="pmid:37588202",
        signature_panel=SignaturePanel.dna_damage,
    ),
]


def seed(session: Session) -> dict:
    """Load curated seed content. Idempotent: skips if cell_line is populated."""
    existing = session.query(func.count(CellLine.cell_line_id)).scalar()
    if existing and existing > 0:
        return {"seeded": False, "reason": "cell_line table already populated"}

    for cl in CELL_LINES:
        # Celligner tumor-concordance fields default to explicitly
        # "unassessed" (not silently NULL) until ingest/celligner.py runs.
        cl.setdefault("tumor_concordance_flag", TumorConcordanceFlag.unassessed)
        session.add(CellLine(**cl))
    for mod in MODIFIERS:
        session.add(Modifier(**mod))
    for drug in DRUGS:
        session.add(Drug(**drug))
    session.flush()

    score_ids: dict[str, object] = {}
    for s in SIGNATURE_SCORES:
        payload = {k: v for k, v in s.items() if k != "key"}
        row = StressSignatureScore(**payload)
        session.add(row)
        session.flush()
        score_ids[s["key"]] = row.id

    interaction_ids: dict[str, object] = {}
    for it in INTERACTIONS:
        payload = {k: v for k, v in it.items() if k not in ("key", "mechanism_key")}
        if it.get("mechanism_key"):
            payload["mechanism_link"] = score_ids[it["mechanism_key"]]
        row = InteractionEffect(**payload)
        session.add(row)
        if it.get("key"):
            session.flush()
            interaction_ids[it["key"]] = row.id

    for ce in CLINICAL_EVIDENCE:
        payload = {k: v for k, v in ce.items() if k != "linked_interaction_key"}
        if ce.get("linked_interaction_key"):
            payload["linked_interaction_effect_id"] = interaction_ids[ce["linked_interaction_key"]]
        session.add(ClinicalEvidence(**payload))

    for drm in DRUG_RESISTANCE_MECHANISMS:
        payload = {k: v for k, v in drm.items() if k != "key"}
        session.add(DrugResistanceMechanism(**payload))
    session.flush()

    # Mechanistic Bridging (build spec v5): generate candidate synergy/
    # antagonism hypotheses from the curated signature x resistance-mechanism
    # data just inserted above. Never touches the curated rows themselves.
    bridging_counts = bridging.generate_candidates(session)

    session.commit()
    return {
        "seeded": True,
        "cell_lines": len(CELL_LINES),
        "modifiers": len(MODIFIERS),
        "drugs": len(DRUGS),
        "signature_scores": len(SIGNATURE_SCORES),
        "interactions": len(INTERACTIONS),
        "clinical_evidence": len(CLINICAL_EVIDENCE),
        "drug_resistance_mechanisms": len(DRUG_RESISTANCE_MECHANISMS),
        "bridging_candidates": bridging_counts,
    }

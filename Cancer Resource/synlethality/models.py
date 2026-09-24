"""
SQLAlchemy data model for the Combinatorial Fitness Landscape.

Faithful to synlethality-fitness-landscape-build-spec.md. Two deliberate,
documented extensions/deviations:

1. `drug` registry table (additive): the spec keeps `drug_id` as a bare string
   on drug_response/interaction_effect and ingests PRISM responses without
   duplicating the source dataset. A minimal registry (id, name, class,
   target) is required for the explorer's "select a drug (or drug class)" UI
   without pulling full PRISM compound metadata into this schema.
2. `stress_signature_score.score` is nullable: ssGSEA/GSVA scores must be
   recomputed from raw expression data by the ingestion pipeline; curated
   entries whose directionality is documented in the source publication but
   whose numeric enrichment score is not published are admitted with
   score=NULL and an explanatory note, rather than fabricating numbers.

Also `interaction_effect.source_study` is stored as a JSON array of citation
strings ("pmid:...", "doi:...", "geo:...") since Tier-2 entries cite one study
per leg ("one or more" per the spec).
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    DateTime,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# JSONB on Postgres, generic JSON (TEXT-backed) elsewhere.
JSONBVariant = JSON().with_variant(postgresql.JSONB(), "postgresql")


def _enum(py_enum):
    # native_enum=False -> portable VARCHAR + CHECK constraint (SQLite & PG parity).
    return SAEnum(py_enum, native_enum=False, length=64, validate_strings=True)


class ModifierType(str, enum.Enum):
    dietary_metabolic = "dietary_metabolic"
    thermal = "thermal"
    hypoxic = "hypoxic"
    mechanical_radiative = "mechanical_radiative"
    other = "other"


class SignaturePanel(str, enum.Enum):
    isr_upr = "isr_upr"
    nrf2_ferroptosis = "nrf2_ferroptosis"
    hsf1_hsp = "hsf1_hsp"
    dna_damage = "dna_damage"
    senescence = "senescence"
    other = "other"


class Directionality(str, enum.Enum):
    death_promoting = "death_promoting"
    protective_resistance = "protective_resistance"
    ambiguous = "ambiguous"


class MetricType(str, enum.Enum):
    ic50 = "ic50"
    auc = "auc"
    viability_percent = "viability_percent"
    # PRISM Repurposing single-dose primary screen (ingest/prism_repurposing.py):
    # log2 fold-change vs. the plate's DMSO negative control, at 2.5 uM /
    # 5-day treatment, QC-filtered and replicate-median-collapsed. Distinct
    # from viability_percent (a direct 0-100 scale) and from ic50/auc (which
    # need a dose series this single-dose screen doesn't have) -- stored
    # under its own real name rather than force-converted into one of those
    # and mislabeled. Negative = growth inhibition relative to control;
    # near 0 = no effect; positive = growth stimulation (rare).
    lfc_2_5um_5d = "lfc_2_5um_5d"


class ClinicalStatus(str, enum.Enum):
    approved = "approved"
    investigational = "investigational"
    withdrawn = "withdrawn"
    preclinical = "preclinical"


class TumorConcordanceFlag(str, enum.Enum):
    good_model = "good_model"
    poor_model_mesenchymal_shift = "poor_model_mesenchymal_shift"
    unassessed = "unassessed"


class InfrastructureRequirement(str, enum.Enum):
    minimal = "minimal"
    low = "low"
    moderate = "moderate"
    high = "high"


class CostAccessibilityTier(str, enum.Enum):
    essential_generic = "essential_generic"
    generic_available = "generic_available"
    brand_moderate_cost = "brand_moderate_cost"
    specialty_high_cost = "specialty_high_cost"
    unknown = "unknown"


class InteractionType(str, enum.Enum):
    synergistic = "synergistic"
    antagonistic = "antagonistic"
    additive = "additive"
    unknown = "unknown"


class EvidenceTier(str, enum.Enum):
    tier_1_direct = "tier_1_direct"
    tier_2_inferred = "tier_2_inferred"
    tier_2b_model_predicted = "tier_2b_model_predicted"
    # "NPxP Interaction Predictor & Opportunity Ranking" build spec
    # (2026-09-23, reconciled into this schema rather than a parallel one --
    # see synlethality/nearest_neighbor.py): that spec's own E2 ("no direct
    # assay, but a molecularly similar cell line has been tested with the
    # same modifier and the same drug"). Distinct from tier_2_inferred
    # (which joins two *separately*-tested single-factor legs *in the same
    # cell line*, no similarity computation involved) and from
    # tier_2b_model_predicted (a fitted regression/ML model's output, not a
    # nearest-neighbor lookup). Always carries the real, cited source
    # interaction(s) it's borrowed from, named explicitly in curator_notes
    # -- never a hidden score.
    tier_2c_nearest_neighbor = "tier_2c_nearest_neighbor"
    tier_3_mechanism_only = "tier_3_mechanism_only"
    # Distinct from tier_3: tier_3 rows always carry a real, per-row cited
    # drug_resistance_mechanism (either hand-curated or matched against one
    # by synlethality/bridging.py). tier_4 rows (synlethality/
    # heuristic_bridging.py) instead come from a mechanical keyword match
    # between a DepMap-supplied compound's own target/mechanism-of-action
    # text and a modifier's induced-signature panel -- real source data,
    # but no per-drug resistance-mechanism citation exists or was checked.
    # Never conflate the two: tier_4 rows always have interaction_type =
    # unknown (a keyword match implies nothing about direction) and
    # resistance_mechanism_link = NULL.
    tier_4_heuristic_target_match = "tier_4_heuristic_target_match"


EVIDENCE_TIER_DEFINITIONS = {
    EvidenceTier.tier_1_direct.value: {
        "label": "Tier 1 — Direct",
        "short_label": "T1",
        "definition": (
            "The combination was tested empirically in the same study: drug and "
            "modifier were applied together and death/viability was measured."
        ),
    },
    EvidenceTier.tier_2_inferred.value: {
        "label": "Tier 2 — Inferred",
        "short_label": "T2",
        "definition": (
            "Drug response and modifier response were measured separately, then "
            "joined via a shared cell line and a biologically plausible shared "
            "mechanism. No combined-treatment readout exists."
        ),
    },
    EvidenceTier.tier_2b_model_predicted.value: {
        "label": "Tier 2b — Model-predicted",
        "short_label": "T2b",
        "definition": (
            "Generated by the learned prediction layer (Step 2) for an untested "
            "drug x modifier x cell-line combination — distinct from Tier 2, "
            "which is a manual join of separate single-factor studies. Every "
            "Tier 2b row stores the model version / training-run ID it came "
            "from so predictions can be invalidated and regenerated as data "
            "and models improve. Experimental: low-confidence until validated "
            "against a critical mass of Tier 1 labels."
        ),
    },
    EvidenceTier.tier_2c_nearest_neighbor.value: {
        "label": "Tier 2c — Nearest-neighbor",
        "short_label": "T2c",
        "definition": (
            "No direct test exists for this exact drug x modifier x cell-line "
            "combination, but the same drug x modifier pair was tested "
            "directly in a molecularly similar cell line (matched on shared "
            "mutations and tissue/lineage). Extrapolated from that real "
            "result, weighted by similarity -- the borrowed source "
            "interaction(s) are always named and cited, never a hidden "
            "score. Weaker than a direct test in this exact line; stronger "
            "than a pure mechanism-overlap guess since it rests on a real "
            "measured combination, just in a different (similar) cell line."
        ),
    },
    EvidenceTier.tier_3_mechanism_only.value: {
        "label": "Tier 3 — Mechanism-only",
        "short_label": "T3",
        "definition": (
            "Signature overlap suggests a plausible interaction, but no "
            "death/viability readout exists for either factor in combination."
        ),
    },
    EvidenceTier.tier_4_heuristic_target_match.value: {
        "label": "Tier 4 — Heuristic (unverified target match)",
        "short_label": "T4",
        "definition": (
            "The lowest-confidence tier in this database. A mechanical "
            "keyword match between a compound's own DepMap-supplied target/"
            "mechanism-of-action text and a modifier's induced-signature "
            "panel category -- not a cited, per-drug resistance-mechanism "
            "claim (see Tier 3), not reviewed by a curator, and not a "
            "prediction of direction (interaction_type is always 'unknown' "
            "here). Treat as 'worth someone checking,' not evidence."
        ),
    },
}


def validate_tier_model_run(evidence_tier, model_run_id) -> None:
    """Enforce the spec rule for model-predicted interaction rows.

    Tier 2b rows are model outputs and MUST carry the model version /
    training-run ID that produced them, so predictions can be invalidated and
    regenerated as data and models improve — never silently overwritten.
    Curated tiers (1/2/3) must NOT carry a model_run_id.

    Raises ValueError on violation; call before writing an InteractionEffect.
    """
    tier_value = (
        evidence_tier.value if isinstance(evidence_tier, EvidenceTier) else str(evidence_tier)
    )
    if tier_value == EvidenceTier.tier_2b_model_predicted.value:
        if not model_run_id:
            raise ValueError(
                "tier_2b_model_predicted rows require a model_run_id identifying "
                "the model version / training run that produced the prediction."
            )
    elif model_run_id:
        raise ValueError(
            f"model_run_id is only valid on tier_2b_model_predicted rows, "
            f"not on {tier_value!r}."
        )


class CellLine(Base):
    __tablename__ = "cell_line"

    # Canonical ID: DepMap/CCLE identifier (CCLE name form used in seed;
    # DepMap ACH IDs backfilled by the DepMap ingestion pipeline).
    cell_line_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    tissue_origin: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    cancer_subtype: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    key_mutations: Mapped[list] = mapped_column(JSONBVariant, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    # OncoTree annotation (build spec v4), sourced from DepMap's own
    # Model.csv (already OncoTree-annotated) -- not re-derived locally.
    # ncit_code cross-references via OncoTree's oncotree_to_nci() and is the
    # code used to query the NCI Clinical Trials Search API. All four NULL
    # until ingest/depmap_prism.py backfills Model.csv (or a line has no
    # corresponding code, e.g. non-malignant MCF-10A or the murine 4T1 line,
    # which is outside DepMap/OncoTree's human-tumor scope entirely).
    oncotree_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    oncotree_primary_disease: Mapped[str | None] = mapped_column(String(256), nullable=True)
    oncotree_subtype: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ncit_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Celligner (Broad/DepMap): how closely this line's transcriptional
    # profile matches real patient tumors of its assigned type/subtype.
    # Both NULL/unassessed until the Celligner ingestion pipeline
    # (ingest/celligner.py) has run — a meaningful subset of commonly-used
    # lines don't actually resemble any real tumor type (mesenchymal-shift
    # artifact of long-term culture), so this flag exists to stop users
    # unknowingly building on a poor model without silently guessing which
    # of our 14 curated lines fall into that subset.
    tumor_concordance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tumor_concordance_flag: Mapped["TumorConcordanceFlag | None"] = mapped_column(
        _enum(TumorConcordanceFlag), nullable=True
    )

    signature_scores: Mapped[list["StressSignatureScore"]] = relationship(
        back_populates="cell_line", cascade="all, delete-orphan"
    )
    drug_responses: Mapped[list["DrugResponse"]] = relationship(
        back_populates="cell_line", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["InteractionEffect"]] = relationship(
        back_populates="cell_line", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "cell_line_id": self.cell_line_id,
            "name": self.name,
            "tissue_origin": self.tissue_origin,
            "cancer_subtype": self.cancer_subtype,
            "key_mutations": self.key_mutations or [],
            "source": self.source,
            "oncotree_code": self.oncotree_code,
            "oncotree_primary_disease": self.oncotree_primary_disease,
            "oncotree_subtype": self.oncotree_subtype,
            "ncit_code": self.ncit_code,
            "tumor_concordance_score": self.tumor_concordance_score,
            "tumor_concordance_flag": (
                self.tumor_concordance_flag.value if self.tumor_concordance_flag else None
            ),
        }


class Modifier(Base):
    __tablename__ = "modifier"

    modifier_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    modifier_type: Mapped[ModifierType] = mapped_column(_enum(ModifierType), nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    # Type-specific protocol parameters, e.g. {concentration_mM, duration_hr}
    # for dietary/metabolic; {temperature_C, duration_min, timepoint_hr} for
    # thermal; {o2_percent, duration_hr} for hypoxic. DO NOT normalize away:
    # cross-study pooling without protocol metadata is the single biggest
    # known failure mode for thermal-stress data (per spec).
    protocol_parameters: Mapped[dict] = mapped_column(JSONBVariant, nullable=False, default=dict)
    source_study: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    source_dataset_accession: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Build spec v6: the core input to low-resource-setting relevance scoring.
    # Unlike pubchem_cid etc., there is no authoritative API to verify these
    # against -- the spec's own Open Questions ask Matt to confirm these are
    # curator-assigned at launch. Values below are curator judgment calls
    # (documented per-row in seed_data.py where the call isn't obvious),
    # not independently-verified facts, and should be reviewed before any
    # low-resource-relevance output is treated as authoritative.
    infrastructure_requirement: Mapped["InfrastructureRequirement | None"] = mapped_column(
        _enum(InfrastructureRequirement), nullable=True
    )
    estimated_relative_cost_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    signature_scores: Mapped[list["StressSignatureScore"]] = relationship(
        back_populates="modifier", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["InteractionEffect"]] = relationship(
        back_populates="modifier", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "modifier_id": self.modifier_id,
            "modifier_type": self.modifier_type.value if self.modifier_type else None,
            "agent": self.agent,
            "protocol_parameters": self.protocol_parameters or {},
            "source_study": self.source_study,
            "source_dataset_accession": self.source_dataset_accession,
            "infrastructure_requirement": (
                self.infrastructure_requirement.value if self.infrastructure_requirement else None
            ),
            "estimated_relative_cost_note": self.estimated_relative_cost_note,
        }

class StressSignatureScore(Base):
    __tablename__ = "stress_signature_score"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    modifier_id: Mapped[str] = mapped_column(
        ForeignKey("modifier.modifier_id", ondelete="CASCADE"), nullable=False, index=True
    )
    cell_line_id: Mapped[str] = mapped_column(
        ForeignKey("cell_line.cell_line_id", ondelete="CASCADE"), nullable=False, index=True
    )
    signature_panel: Mapped[SignaturePanel] = mapped_column(_enum(SignaturePanel), nullable=False, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # ssGSEA/GSVA or equivalent
    raw_deg_evidence_ref: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    directionality: Mapped[Directionality] = mapped_column(_enum(Directionality), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    modifier: Mapped["Modifier"] = relationship(back_populates="signature_scores")
    cell_line: Mapped["CellLine"] = relationship(back_populates="signature_scores")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "modifier_id": self.modifier_id,
            "cell_line_id": self.cell_line_id,
            "signature_panel": self.signature_panel.value if self.signature_panel else None,
            "score": self.score,
            "raw_deg_evidence_ref": self.raw_deg_evidence_ref,
            "directionality": self.directionality.value if self.directionality else None,
            "notes": self.notes,
        }


class DrugResponse(Base):
    """Ingested (not curated) drug sensitivity data from DepMap/PRISM.

    Only what is needed to join is stored; the full source dataset is not
    duplicated.
    """

    __tablename__ = "drug_response"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    drug_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cell_line_id: Mapped[str] = mapped_column(
        ForeignKey("cell_line.cell_line_id", ondelete="CASCADE"), nullable=False, index=True
    )
    viability_metric: Mapped[float] = mapped_column(Float, nullable=False)
    metric_type: Mapped[MetricType] = mapped_column(_enum(MetricType), nullable=False)
    source: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    cell_line: Mapped["CellLine"] = relationship(back_populates="drug_responses")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "drug_id": self.drug_id,
            "cell_line_id": self.cell_line_id,
            "viability_metric": self.viability_metric,
            "metric_type": self.metric_type.value if self.metric_type else None,
            "source": self.source,
        }


class Drug(Base):
    """Drug registry, normalized per the build spec's v2 `drug` entity.

    `drug_id` stays a short string slug rather than the spec's bare uuid
    (documented, additive deviation, consistent with the rest of this table's
    existing extensions): the curated seed and every FK reference
    (`drug_response.drug_id`, `interaction_effect.drug_id`) already key off a
    human-readable id (e.g. "metformin"), and switching the PK type would be
    a disruptive migration for no functional gain at this scale. `synonyms`
    plays the normalization role the spec wants instead — alternate names
    seen across source libraries resolve to this one row.

    `pubchem_cid`/`chembl_id`/`drugbank_id`/`mechanism_of_action` are cross-
    references from Broad Repurposing Hub-style curation; `chembl_id` and
    `drugbank_id` are left NULL in the curated seed until verified against
    their authoritative sources (only `pubchem_cid` has been checked so far,
    against PubChem's PUG REST API) — per the evidence-integrity rule against
    fabricated values, a missing identifier is preferred over a guessed one.

    `induced_expression_signature_ref` is a pointer to a LINCS L1000
    signature ID, when available: this is what lets a drug be represented in
    the same induced-differential-expression feature space as a modifier's
    `stress_signature_score`, which Step 2 (MARSY/PerturbSynX-family
    prediction) needs as input. NULL until the LINCS ingestion pipeline
    (`ingest/lincs_l1000.py`) is enabled.
    """

    __tablename__ = "drug"

    drug_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    drug_class: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    target: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    synonyms: Mapped[list] = mapped_column(JSONBVariant, nullable=False, default=list)
    pubchem_cid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chembl_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    drugbank_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mechanism_of_action: Mapped[str | None] = mapped_column(String(512), nullable=True)
    clinical_status: Mapped["ClinicalStatus | None"] = mapped_column(
        _enum(ClinicalStatus), nullable=True
    )
    induced_expression_signature_ref: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    # Build spec v6: drives low-resource-setting relevance alongside
    # modifier.infrastructure_requirement. Where a drug is on the WHO Model
    # List of Essential Medicines, `essential_generic` is a checkable fact
    # (verified per-drug in seed_data.py against WHO EML documentation);
    # otherwise this is a curator judgment call, same caveat as
    # modifier.infrastructure_requirement above.
    cost_accessibility_tier: Mapped["CostAccessibilityTier | None"] = mapped_column(
        _enum(CostAccessibilityTier), nullable=True
    )

    resistance_mechanisms: Mapped[list["DrugResistanceMechanism"]] = relationship(
        back_populates="drug", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "drug_id": self.drug_id,
            "name": self.name,
            "drug_class": self.drug_class,
            "target": self.target,
            "source": self.source,
            "synonyms": self.synonyms or [],
            "pubchem_cid": self.pubchem_cid,
            "chembl_id": self.chembl_id,
            "drugbank_id": self.drugbank_id,
            "mechanism_of_action": self.mechanism_of_action,
            "clinical_status": self.clinical_status.value if self.clinical_status else None,
            "induced_expression_signature_ref": self.induced_expression_signature_ref,
            "cost_accessibility_tier": (
                self.cost_accessibility_tier.value if self.cost_accessibility_tier else None
            ),
        }


class DrugResistanceMechanism(Base):
    """Structured "what defends this drug's target cell against it"
    annotation (build spec v5) -- the drug-side counterpart to
    `stress_signature_score` on the modifier side. This is what
    synlethality/bridging.py matches against to generate candidate
    modifier x drug synergy hypotheses (Mechanistic Bridging module).

    `signature_panel` is an additive, documented extension beyond the
    spec's literal columns: the spec's Step 2 ("check whether the
    modifier's induced signature overlaps the pathway/gene recorded in
    that drug's drug_resistance_mechanism entry") requires a normalized
    join key to do a real match rather than fuzzy text-matching
    `pathway_or_gene` against `stress_signature_score.signature_panel`.
    NULL is a valid value (a resistance mechanism outside the five
    curated panels, e.g. drug-efflux transporters) and such rows are
    simply not matchable by the bridging module yet, not incorrectly
    matched.
    """

    __tablename__ = "drug_resistance_mechanism"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    drug_id: Mapped[str] = mapped_column(
        ForeignKey("drug.drug_id", ondelete="CASCADE"), nullable=False, index=True
    )
    pathway_or_gene: Mapped[str] = mapped_column(String(256), nullable=False)
    mechanism_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    signature_panel: Mapped["SignaturePanel | None"] = mapped_column(
        _enum(SignaturePanel), nullable=True, index=True
    )

    drug: Mapped["Drug"] = relationship(back_populates="resistance_mechanisms")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "drug_id": self.drug_id,
            "pathway_or_gene": self.pathway_or_gene,
            "mechanism_description": self.mechanism_description,
            "source": self.source,
            "signature_panel": self.signature_panel.value if self.signature_panel else None,
        }


class InteractionEffect(Base):
    """The core output table: one drug x modifier x cell-line interaction claim."""

    __tablename__ = "interaction_effect"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    modifier_id: Mapped[str] = mapped_column(
        ForeignKey("modifier.modifier_id", ondelete="CASCADE"), nullable=False, index=True
    )
    drug_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cell_line_id: Mapped[str] = mapped_column(
        ForeignKey("cell_line.cell_line_id", ondelete="CASCADE"), nullable=False, index=True
    )
    combined_effect_metric: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Real per-model synergy scores (Bliss/HSA/Loewe/ZIP), added 2026-09-23
    # after validating synlethality/scoring.py against real NCI-ALMANAC
    # checkerboards (synlethality/almanac_validation.py) surfaced a real
    # finding worth not hiding: Bliss/HSA/ZIP can agree closely while Loewe
    # disagrees sharply for the identical real drug pair, because Loewe's
    # Hill-curve fit is numerically unstable on coarse real dose grids.
    # combined_effect_metric stays the single "headline" number for sources
    # that report one directly (e.g. a paper's own Thermal Enhancement
    # Ratio or IC50 fold-shift -- see seed_data.py's REAL_COMBINED_EFFECT_
    # METRICS) -- those aren't Bliss/Loewe/HSA/ZIP scores and don't belong
    # in this field. This field is specifically for when scoring.py's own
    # engine has been run against a real dose-response matrix for THIS
    # interaction_effect row: {"bliss": {"mean":.., "classification":..},
    # "hsa": {...}, "loewe": {...}, "zip": {...}}, via
    # scoring.summarize_for_storage(). NULL until a real modifier x drug
    # checkerboard exists for at least one curated row -- none does yet
    # (this build's only real checkerboard validation, NCI-ALMANAC, is
    # drug x drug and structurally can't populate this schema; see
    # almanac_validation.py) -- this is ready infrastructure ahead of that
    # data, not backfilled with anything, same posture as every other
    # "empty until a real study exists" field in this schema.
    synergy_model_scores: Mapped[dict | None] = mapped_column(JSONBVariant, nullable=True)
    interaction_type: Mapped[InteractionType] = mapped_column(_enum(InteractionType), nullable=False, index=True)
    evidence_tier: Mapped[EvidenceTier] = mapped_column(_enum(EvidenceTier), nullable=False, index=True)
    mechanism_link: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stress_signature_score.id", ondelete="SET NULL"), nullable=True
    )
    # Build spec v5 (Mechanistic Bridging module): which drug-defense
    # mechanism the modifier is hypothesized to suppress. Set together with
    # mechanism_link for any row produced by synlethality/bridging.py; NULL
    # on every hand-curated row. This is the field the /interactions/
    # candidates endpoint filters on to distinguish generated hypotheses
    # from curated evidence.
    resistance_mechanism_link: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("drug_resistance_mechanism.id", ondelete="SET NULL"), nullable=True
    )
    # JSON array of citations, e.g. ["pmid:33281976", "doi:10.3892/ol.2020.12326"].
    source_study: Mapped[list] = mapped_column(JSONBVariant, nullable=False, default=list)
    curator_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Model version / training-run ID for tier_2b_model_predicted rows only
    # (spec: predictions are invalidated and regenerated, never silently
    # overwritten). NULL on all curated tiers. Enforced by
    # validate_tier_model_run(); not a DB constraint so SQLite/Postgres agree.
    model_run_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    # Build spec v6: outbound reference to the existing clinical trial
    # builder tool, populated once that tool's integration interface is
    # confirmed (spec's own Open Questions leave this unresolved). Always
    # NULL in this build -- no integration exists yet, and this field is
    # never guessed at or stubbed with a fake reference. The frontend's
    # "Send to Trial Builder" action is disabled with an explanatory
    # tooltip rather than pretending to call a contract that doesn't exist.
    trial_builder_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # low_resource_relevance and priority_score are deliberately NOT stored
    # columns, despite the spec listing them as such: the spec's own
    # instruction is "recompute on either input changing, don't hand-
    # maintain," and a stored column with no DB trigger mechanism here is
    # exactly the kind of thing that goes silently stale. Both are computed
    # on read in synlethality/prioritization.py and attached to the API
    # payload the same way evidence_tier_label already is.

    modifier: Mapped["Modifier"] = relationship(back_populates="interactions")
    cell_line: Mapped["CellLine"] = relationship(back_populates="interactions")
    mechanism: Mapped["StressSignatureScore | None"] = relationship(
        foreign_keys=[mechanism_link]
    )
    resistance_mechanism: Mapped["DrugResistanceMechanism | None"] = relationship(
        foreign_keys=[resistance_mechanism_link]
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "modifier_id": self.modifier_id,
            "drug_id": self.drug_id,
            "cell_line_id": self.cell_line_id,
            "combined_effect_metric": self.combined_effect_metric,
            "synergy_model_scores": self.synergy_model_scores,
            "interaction_type": self.interaction_type.value if self.interaction_type else None,
            "evidence_tier": self.evidence_tier.value if self.evidence_tier else None,
            "mechanism_link": str(self.mechanism_link) if self.mechanism_link else None,
            "resistance_mechanism_link": (
                str(self.resistance_mechanism_link) if self.resistance_mechanism_link else None
            ),
            "source_study": self.source_study or [],
            "curator_notes": self.curator_notes,
            "model_run_id": self.model_run_id,
            "trial_builder_ref": self.trial_builder_ref,
        }


class ClinicalEvidence(Base):
    """Aggregate, publicly published clinical-trial evidence (build spec v3).

    Exists to answer "has anyone tested this combination in humans yet" —
    never to store trial data itself. Only aggregate, already-published
    metadata (registry phase/status, a brief outcome summary sourced from the
    published record, a resulting publication) is stored; no individual or
    patient-level records. `linked_interaction_effect_id` is nullable: a
    trial can exist (and be curated) before/without a matching cell-line
    finding yet in `interaction_effect`.
    """

    __tablename__ = "clinical_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nct_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    linked_interaction_effect_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("interaction_effect.id", ondelete="SET NULL"), nullable=True, index=True
    )

    linked_interaction: Mapped["InteractionEffect | None"] = relationship(
        foreign_keys=[linked_interaction_effect_id]
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "nct_id": self.nct_id,
            "phase": self.phase,
            "status": self.status,
            "outcome_summary": self.outcome_summary,
            "publication_ref": self.publication_ref,
            "linked_interaction_effect_id": (
                str(self.linked_interaction_effect_id)
                if self.linked_interaction_effect_id else None
            ),
        }


class IngestionRun(Base):
    """Bookkeeping for ingestion pipeline steps.

    Each job is tagged with the source(s) it loaded, so a bad/retracted source
    can be pulled without touching the rest of the table.
    """

    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_study_tag: Mapped[str] = mapped_column(String(512), nullable=False, default="", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "step_name": self.step_name,
            "source_study_tag": self.source_study_tag,
            "status": self.status,
            "row_count": self.row_count,
            "message": self.message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


"""
Physiological Fitness Landscape — Mortality Biomarker Database Schema & Models
Relational schema (SQLite/PostgreSQL compatible via SQLAlchemy 2.0).
Includes Derived Analytics Optimization Layer (population shifts, numerical expected hazard integration,
causal tiering, individual benefit distributions, and physiological domain boundaries).
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Text,
    DateTime,
    JSON,
    create_engine,
    Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Biomarker(Base):
    __tablename__ = "biomarker"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    aliases = Column(JSON, default=list)  # List[str]
    category = Column(String(100), nullable=False, index=True)  # e.g. 'Lipids', 'Inflammation', 'Metabolic', 'Kidney', 'Liver', 'Cardiovascular', 'Hematology', 'Electrolytes'
    units = Column(String(50), nullable=False)
    measurement_method = Column(String(200), nullable=True)
    specimen_type = Column(String(100), nullable=False)  # 'serum', 'plasma', 'whole_blood', 'urine', 'physiological', 'functional'
    bodily_fluid = Column(String(100), nullable=True)   # 'Blood Serum', 'Blood Plasma', 'Whole Blood', 'Urine', 'Non-Fluid / Functional', 'Non-Fluid / Hemodynamic'
    primary_organ = Column(String(100), nullable=True)  # 'Liver', 'Kidney', 'Heart & Vasculature', 'Pancreas', 'Bone Marrow', 'Immune System', 'Skeletal Muscle', 'Multi-Organ'
    tissue_origin = Column(String(150), nullable=True)  # 'Hepatocytes', 'Cardiomyocytes', 'Renal Glomerulus/Tubules', 'Erythrocytes/Leukocytes', etc.
    nhanes_code = Column(String(50), nullable=True)  # e.g. 'LBXTC', 'LBXCRP', 'URXUCR'
    notes = Column(Text, nullable=True)

    # Directionality & Causal Evidence Tier
    # directionality: 'lower_better', 'higher_better', 'u_shaped', 'j_shaped', 'inverted_u'
    directionality = Column(String(50), default="lower_better", nullable=False)
    # causal_status: 'RCT_SUPPORTED', 'MENDELIAN_RANDOMIZATION', 'QUASI_EXPERIMENTAL', 'STRONG_OBSERVATIONAL', 'OBSERVATIONAL'
    causal_status = Column(String(50), default="STRONG_OBSERVATIONAL", nullable=False)
    
    # Boundary Guardrails
    valid_domain_min = Column(Float, nullable=True)
    valid_domain_max = Column(Float, nullable=True)
    optimal_target = Column(Float, nullable=True)  # x* for U/J shaped or target value

    # VOI / EHIV layer (c_test in eq. 12). Nullable until a priced test is mapped.
    # test_price_usd is the standalone-analyte cash-pay median when one exists
    # (falling back to the blended median for panel-only analytes — see
    # backend.sync_biomarker_prices_from_test_cost); cash_pay_blended_median
    # keeps the all-products median so the pane can show both.
    test_price_usd = Column(Float, nullable=True)
    cash_pay_blended_median = Column(Float, nullable=True)
    cms_reimbursement_usd = Column(Float, nullable=True)
    loinc_to_test_id = Column(JSON, nullable=True)  # {loinc_code: test_id, ...}

    # Relationships
    mortality_associations = relationship("MortalityAssociation", back_populates="biomarker", cascade="all, delete-orphan")
    population_distributions = relationship("PopulationDistribution", back_populates="biomarker", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="biomarker", cascade="all, delete-orphan")
    hr_curves = relationship(
        "BiomarkerHRCurve",
        back_populates="biomarker",
        cascade="all, delete-orphan",
    )
    hr_curve = relationship(
        "BiomarkerHRCurve",
        uselist=False,
        viewonly=True,
        primaryjoin="and_(Biomarker.id==BiomarkerHRCurve.biomarker_id, BiomarkerHRCurve.sex=='all', BiomarkerHRCurve.age_band=='all')",
    )
    optimization_model = relationship("BiomarkerOptimizationModel", back_populates="biomarker", uselist=False, cascade="all, delete-orphan")
    expected_values = relationship("BiomarkerExpectedValue", back_populates="biomarker", cascade="all, delete-orphan")
    disease_alterations = relationship("DiseaseAlteration", back_populates="biomarker", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "aliases": self.aliases or [],
            "category": self.category,
            "units": self.units,
            "measurement_method": self.measurement_method,
            "specimen_type": self.specimen_type,
            "bodily_fluid": self.bodily_fluid,
            "primary_organ": self.primary_organ,
            "tissue_origin": self.tissue_origin,
            "nhanes_code": self.nhanes_code,
            "notes": self.notes,
            "directionality": self.directionality,
            "causal_status": self.causal_status,
            "valid_domain_min": self.valid_domain_min,
            "valid_domain_max": self.valid_domain_max,
            "optimal_target": self.optimal_target,
            "testPriceUSD": self.test_price_usd,
            "cmsReimbursementUSD": self.cms_reimbursement_usd,
            "loincToTestId": self.loinc_to_test_id or {},
        }


class Source(Base):
    __tablename__ = "source"

    id = Column(Integer, primary_key=True, autoincrement=True)
    citation = Column(Text, nullable=False)
    pmid = Column(String(30), nullable=True, index=True)
    doi = Column(String(100), nullable=True, index=True)
    url = Column(String(500), nullable=True)
    year = Column(Integer, nullable=True)
    study_design = Column(String(100), nullable=True)  # 'prospective_cohort', 'meta_analysis', 'rct', 'retrospective_cohort', 'cross_sectional_survey'
    # For grey-literature / institutional sources that have neither a PMID nor
    # a DOI (CDC NHANES data files, CDC nutrition and exposure reports,
    # laboratory reference-interval pages), the identifier is recorded here so
    # provenance stays machine-checkable without inventing a fake citation id.
    identifier_type = Column(String(50), nullable=True)  # 'NHANES_DATA_FILE', 'INSTITUTIONAL_REPORT', 'WEB_REFERENCE', 'LABORATORY_REFERENCE', 'REFERENCE_DATA_FOR'
    identifier = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    associations = relationship("MortalityAssociation", back_populates="source")
    distributions = relationship("PopulationDistribution", back_populates="source")
    interventions = relationship("Intervention", back_populates="source")

    def to_dict(self):
        return {
            "id": self.id,
            "citation": self.citation,
            "pmid": self.pmid,
            "doi": self.doi,
            "url": self.url,
            "year": self.year,
            "study_design": self.study_design,
            "identifier_type": self.identifier_type,
            "identifier": self.identifier,
        }


class MortalityAssociation(Base):
    __tablename__ = "mortality_association"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("source.id"), nullable=False, index=True)
    
    hazard_ratio = Column(Float, nullable=False)
    # hr_type: 'per_unit', 'per_sd', 'quartile_extreme', 'tertile_extreme', 'per_log_unit', 'per_10_units'
    hr_type = Column(String(50), nullable=False)
    hr_unit_scale = Column(Float, default=1.0)  # scale if per unit (e.g. 1.0 or 10.0 or 1 SD)
    ci_lower = Column(Float, nullable=False)
    ci_upper = Column(Float, nullable=False)
    p_value = Column(Float, nullable=True)
    # direction: 'higher_worse', 'lower_worse', 'u_shaped', 'j_shaped', 'null'
    direction = Column(String(50), nullable=False, index=True)
    
    cohort_description = Column(String(300), nullable=True)  # e.g., 'NHANES III Follow-up (1988-2015)', 'UK Biobank'
    n = Column(Integer, nullable=True)
    events = Column(Integer, nullable=True)  # number of deaths
    follow_up_years = Column(Float, nullable=True)
    # population_type: 'general', 'patient_subgroup', 'older_adults'
    population_type = Column(String(50), default="general")
    adjustment_covariates = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    biomarker = relationship("Biomarker", back_populates="mortality_associations")
    source = relationship("Source", back_populates="associations")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "source_id": self.source_id,
            "hazard_ratio": self.hazard_ratio,
            "hr_type": self.hr_type,
            "hr_unit_scale": self.hr_unit_scale,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "p_value": self.p_value,
            "direction": self.direction,
            "cohort_description": self.cohort_description,
            "n": self.n,
            "events": self.events,
            "follow_up_years": self.follow_up_years,
            "population_type": self.population_type,
            "adjustment_covariates": self.adjustment_covariates,
            "notes": self.notes,
            "source": self.source.to_dict() if self.source else None,
        }


class PopulationDistribution(Base):
    __tablename__ = "population_distribution"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("source.id"), nullable=False, index=True)
    
    sex = Column(String(10), nullable=False)  # 'M', 'F', 'all'
    age_band = Column(String(50), nullable=False)  # 'all', '20-39', '40-59', '60+'
    
    mean = Column(Float, nullable=False)
    sd = Column(Float, nullable=False)
    p5 = Column(Float, nullable=True)
    p25 = Column(Float, nullable=True)
    p50 = Column(Float, nullable=False)  # Median
    p75 = Column(Float, nullable=True)
    p95 = Column(Float, nullable=True)
    unit = Column(String(50), nullable=False)
    sample_n = Column(Integer, nullable=False)
    
    survey_cycle = Column(String(100), nullable=True)  # e.g., 'NHANES 2017-2018 + 2015-2016'
    is_low_confidence = Column(Integer, default=0)  # 1 if sample_n < 500

    # Relationships
    biomarker = relationship("Biomarker", back_populates="population_distributions")
    source = relationship("Source", back_populates="distributions")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "source_id": self.source_id,
            "sex": self.sex,
            "age_band": self.age_band,
            "mean": round(self.mean, 2) if self.mean is not None else None,
            "sd": round(self.sd, 2) if self.sd is not None else None,
            "p5": round(self.p5, 2) if self.p5 is not None else None,
            "p25": round(self.p25, 2) if self.p25 is not None else None,
            "p50": round(self.p50, 2) if self.p50 is not None else None,
            "p75": round(self.p75, 2) if self.p75 is not None else None,
            "p95": round(self.p95, 2) if self.p95 is not None else None,
            "unit": self.unit,
            "sample_n": self.sample_n,
            "survey_cycle": self.survey_cycle,
            "is_low_confidence": bool(self.is_low_confidence),
            "source": self.source.to_dict() if self.source else None,
        }


class Intervention(Base):
    __tablename__ = "intervention"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("source.id"), nullable=False, index=True)
    
    # direction: 'favorable' (improves biomarker toward lower mortality risk), 'unfavorable' (worsens biomarker)
    direction = Column(String(50), nullable=False, index=True)
    # category: 'diet', 'exercise', 'pharmacologic', 'sleep', 'supplement', 'environmental', 'behavioral'
    category = Column(String(50), nullable=False, index=True)
    
    description = Column(Text, nullable=False)
    quantified_effect = Column(String(200), nullable=True)  # e.g., 'Reduces hsCRP by 25-35%', 'Increases HDL-C by 5-10%'
    # evidence_strength: 'RCT', 'meta-analysis', 'cohort', 'mechanistic'
    evidence_strength = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    biomarker = relationship("Biomarker", back_populates="interventions")
    source = relationship("Source", back_populates="interventions")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "source_id": self.source_id,
            "direction": self.direction,
            "category": self.category,
            "description": self.description,
            "quantified_effect": self.quantified_effect,
            "evidence_strength": self.evidence_strength,
            "notes": self.notes,
            "source": self.source.to_dict() if self.source else None,
        }


# =======================================================================
# Derived Analytics Optimization Layer Models
# =======================================================================

class BiomarkerHRCurve(Base):
    """
    Mathematical functional form of the Hazard Ratio curve HR(x) for a biomarker.
    Supports:
    - 'linear_log': ln(HR(x)) = beta * (x - x_ref)
    - 'quadratic': ln(HR(x)) = a * (x - x_opt)^2
    - 'spline' / 'piecewise': piecewise linear or polynomial
    - 'log_log': ln(HR(x)) = beta * (ln(x) - ln(x_ref))
    """
    __tablename__ = "biomarker_hr_curve"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    sex = Column(String(10), nullable=False, default="all", index=True)  # 'M', 'F', 'all'
    age_band = Column(String(50), nullable=False, default="all", index=True)  # 'all', '20-39', '40-59', '60+'
    
    curve_type = Column(String(50), nullable=False)  # 'linear_log', 'quadratic', 'log_log', 'piecewise'
    reference_value = Column(Float, nullable=False)  # x_ref where HR=1.0
    optimal_value = Column(Float, nullable=True)     # x* (nadir of risk)
    
    # Mathematical parameters stored in JSON (e.g. {'beta': 0.15} or {'a': 0.005, 'x_opt': 75.0})
    parameters = Column(JSON, default=dict)
    
    # Boundaries
    valid_min = Column(Float, nullable=False)
    valid_max = Column(Float, nullable=False)
    
    # Metadata
    citation_summary = Column(String(300), nullable=True)

    # Relationships
    biomarker = relationship("Biomarker", back_populates="hr_curves")
    
    __table_args__ = (
        Index("uq_biomarker_hr_curve_stratum", "biomarker_id", "sex", "age_band", unique=True),
    )

    @property
    def stratum_name(self):
        return f"{self.sex}_{self.age_band}"

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "sex": self.sex,
            "age_band": self.age_band,
            "stratum_name": self.stratum_name,
            "curve_type": self.curve_type,
            "reference_value": self.reference_value,
            "optimal_value": self.optimal_value,
            "parameters": self.parameters,
            "valid_min": self.valid_min,
            "valid_max": self.valid_max,
            "citation_summary": self.citation_summary
        }


class BiomarkerOptimizationModel(Base):
    """
    Precomputed baseline population distribution density and hazard expectations.
    """
    __tablename__ = "biomarker_optimization_model"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), unique=True, nullable=False, index=True)
    
    relationship_type = Column(String(50), nullable=False)  # 'MONOTONIC_INCREASING', 'MONOTONIC_DECREASING', 'U_SHAPED', 'J_SHAPED'
    causal_status = Column(String(50), nullable=False)
    
    # Baseline expected hazard E[HR_0] = \int HR(x) f(x) dx
    baseline_expected_hr = Column(Float, nullable=False)
    
    # Population summary
    pop_mean = Column(Float, nullable=False)
    pop_sd = Column(Float, nullable=False)
    pop_median = Column(Float, nullable=False)
    pop_p25 = Column(Float, nullable=False)
    pop_p75 = Column(Float, nullable=False)
    
    # Optimal target x*
    optimal_target = Column(Float, nullable=False)
    
    # Relationships
    biomarker = relationship("Biomarker", back_populates="optimization_model")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "relationship_type": self.relationship_type,
            "causal_status": self.causal_status,
            "baseline_expected_hr": round(self.baseline_expected_hr, 4) if self.baseline_expected_hr else None,
            "pop_mean": round(self.pop_mean, 2) if self.pop_mean else None,
            "pop_sd": round(self.pop_sd, 2) if self.pop_sd else None,
            "pop_median": round(self.pop_median, 2) if self.pop_median else None,
            "pop_p25": round(self.pop_p25, 2) if self.pop_p25 else None,
            "pop_p75": round(self.pop_p75, 2) if self.pop_p75 else None,
            "optimal_target": round(self.optimal_target, 2) if self.optimal_target else None,
        }


class OptimizationScenario(Base):
    """
    Standardized shift scenarios (e.g. 0.25 SD, 0.5 SD, 1.0 SD, 1.5 SD, 2.0 SD, or percentile truncation).
    """
    __tablename__ = "optimization_scenario"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    shift_type = Column(String(50), nullable=False)  # 'sd_shift', 'percentile_shift', 'target_nadir'
    shift_magnitude = Column(Float, nullable=False)  # e.g., 0.25, 0.50, 1.00, 1.50, 2.00
    description = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "shift_type": self.shift_type,
            "shift_magnitude": self.shift_magnitude,
            "description": self.description
        }


class BiomarkerExpectedValue(Base):
    """
    Precomputed optimization outcome for a biomarker under a specific scenario.
    Includes absolute HR difference, relative hazard reduction, domain boundary status,
    and individual benefit distribution metrics.
    """
    __tablename__ = "biomarker_expected_value"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    scenario_id = Column(Integer, ForeignKey("optimization_scenario.id"), nullable=False, index=True)
    
    # Hazard outcomes
    baseline_expected_hr = Column(Float, nullable=False)   # E[HR_0]
    optimized_expected_hr = Column(Float, nullable=False)  # E[HR_delta]
    delta_hr = Column(Float, nullable=False)               # E[HR_0] - E[HR_delta]
    relative_hazard_reduction = Column(Float, nullable=False) # 1 - (E[HR_delta] / E[HR_0])
    
    # Boundary status
    # domain_status: 'IN_DOMAIN', 'BOUNDARY_REACHED', 'OUT_OF_DOMAIN'
    domain_status = Column(String(50), nullable=False)
    fraction_out_of_domain = Column(Float, default=0.0)
    
    # Individual benefit distribution metrics
    mean_individual_benefit = Column(Float, nullable=False)
    median_individual_benefit = Column(Float, nullable=False)
    p10_benefit = Column(Float, nullable=False)
    p25_benefit = Column(Float, nullable=False)
    p75_benefit = Column(Float, nullable=False)
    p90_benefit = Column(Float, nullable=False)
    max_individual_benefit = Column(Float, nullable=False)
    fraction_benefiting = Column(Float, nullable=False)  # fraction experiencing HR reduction
    fraction_harmed = Column(Float, nullable=False)      # fraction experiencing HR increase

    # Relationships
    biomarker = relationship("Biomarker", back_populates="expected_values")
    scenario = relationship("OptimizationScenario")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "scenario_id": self.scenario_id,
            "baseline_expected_hr": round(self.baseline_expected_hr, 4),
            "optimized_expected_hr": round(self.optimized_expected_hr, 4),
            "delta_hr": round(self.delta_hr, 4),
            "relative_hazard_reduction": round(self.relative_hazard_reduction, 4),
            "domain_status": self.domain_status,
            "fraction_out_of_domain": round(self.fraction_out_of_domain, 4),
            "mean_individual_benefit": round(self.mean_individual_benefit, 4),
            "median_individual_benefit": round(self.median_individual_benefit, 4),
            "p10_benefit": round(self.p10_benefit, 4),
            "p25_benefit": round(self.p25_benefit, 4),
            "p75_benefit": round(self.p75_benefit, 4),
            "p90_benefit": round(self.p90_benefit, 4),
            "max_individual_benefit": round(self.max_individual_benefit, 4),
            "fraction_benefiting": round(self.fraction_benefiting, 4),
            "fraction_harmed": round(self.fraction_harmed, 4),
            "scenario": self.scenario.to_dict() if self.scenario else None
        }


class Condition(Base):
    """
    Disease / physiological composite state entity (e.g. Allostatic Load, Metabolic Syndrome,
    PhenoAge, Frailty Index) characterized by combinations of biomarker alterations.
    Supports multiple competing published scoring panels per condition.
    """
    __tablename__ = "condition"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    icd10_code = Column(String(50), nullable=True)
    # category: 'metabolic', 'cardiovascular', 'frailty', 'infectious', 'neuroendocrine', 'composite_aging_score'
    category = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    signatures = relationship("BiomarkerSignature", back_populates="condition", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "icd10_code": self.icd10_code,
            "category": self.category,
            "description": self.description,
            "signatures_count": len(self.signatures) if self.signatures else 0,
        }


class BiomarkerSignature(Base):
    """
    Biomarker alteration component within a specific published condition panel.
    Keyed to panel_name + source_id to support multiple competing published panels per condition.
    """
    __tablename__ = "biomarker_signature"

    id = Column(Integer, primary_key=True, autoincrement=True)
    condition_id = Column(Integer, ForeignKey("condition.id"), nullable=False, index=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("source.id"), nullable=True, index=True)

    panel_name = Column(String(200), nullable=False, index=True)  # e.g. 'MacArthur AL-10', 'ATP III Metabolic Syndrome', 'Levine PhenoAge'
    direction = Column(String(50), nullable=False)  # 'elevated', 'reduced'
    cutoff_value = Column(Float, nullable=True)
    cutoff_type = Column(String(50), nullable=False)  # 'percentile', 'absolute', 'sd'
    cutoff_description = Column(String(100), nullable=True)  # e.g. '> 75th percentile', '>= 130 mmHg'
    weight = Column(Float, default=1.0)
    scoring_method = Column(String(50), nullable=False)  # 'count_based', 'weighted_composite', 'regression'
    notes = Column(Text, nullable=True)

    # Relationships
    condition = relationship("Condition", back_populates="signatures")
    biomarker = relationship("Biomarker")
    source = relationship("Source")

    def to_dict(self):
        return {
            "id": self.id,
            "condition_id": self.condition_id,
            "condition_name": self.condition.name if self.condition else None,
            "condition_slug": self.condition.slug if self.condition else None,
            "biomarker_id": self.biomarker_id,
            "biomarker_name": self.biomarker.name if self.biomarker else None,
            "biomarker_slug": self.biomarker.slug if self.biomarker else None,
            "biomarker_units": self.biomarker.units if self.biomarker else None,
            "source_id": self.source_id,
            "source_citation": self.source.citation if self.source else None,
            "panel_name": self.panel_name,
            "direction": self.direction,
            "cutoff_value": self.cutoff_value,
            "cutoff_type": self.cutoff_type,
            "cutoff_description": self.cutoff_description,
            "weight": self.weight,
            "scoring_method": self.scoring_method,
            "notes": self.notes,
        }


class DistributionFit(Base):
    """
    Continuous, sampleable population distribution functions derived from NHANES or literature percentiles.
    Supports empirical ECDF, KDE, Log-normal, Normal, Gamma, Weibull, and Johnson SU parametric families.
    """
    __tablename__ = "distribution_fit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    sex = Column(String(10), nullable=False, default="all")  # 'M', 'F', 'all'
    age_band = Column(String(50), nullable=False, default="all")  # 'all', '20-39', '40-59', '60+'
    
    # fit_type: 'empirical_ecdf', 'kde', 'lognormal', 'normal', 'gamma', 'weibull', 'johnson_su'
    fit_type = Column(String(50), nullable=False)
    parameters = Column(JSON, default=dict)  # Stores mean, sd, shape/loc/scale or KDE knots
    domain_min = Column(Float, nullable=False)
    domain_max = Column(Float, nullable=False)
    
    source_id = Column(Integer, ForeignKey("source.id"), nullable=True, index=True)
    fit_quality_note = Column(Text, nullable=True)

    # Relationships
    biomarker = relationship("Biomarker")
    source = relationship("Source")

    @property
    def family(self):
        params = self.parameters or {}
        return params.get("family", self.fit_type)

    @property
    def distribution_type(self):
        return self.fit_type

    @property
    def stratum_name(self):
        return f"{self.sex}_{self.age_band}"

    @property
    def stratum_group(self):
        return f"{self.sex}_{self.age_band}"

    @property
    def valid_min(self):
        return self.domain_min

    @property
    def valid_max(self):
        return self.domain_max

    @property
    def param_shape(self):
        params = self.parameters or {}
        return params.get("shape", params.get("s", params.get("a", params.get("k", None))))

    @property
    def param_loc(self):
        params = self.parameters or {}
        return params.get("loc", params.get("mean", 0.0))

    @property
    def param_scale(self):
        params = self.parameters or {}
        return params.get("scale", params.get("sd", 1.0))

    @property
    def ks_stat(self):
        params = self.parameters or {}
        return params.get("ks_stat", None)

    @property
    def ks_pvalue(self):
        params = self.parameters or {}
        return params.get("ks_pvalue", None)

    @property
    def aic(self):
        params = self.parameters or {}
        return params.get("aic", None)

    @property
    def bic(self):
        params = self.parameters or {}
        return params.get("bic", None)

    def to_dict(self):
        params = self.parameters or {}
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "biomarker_slug": self.biomarker.slug if self.biomarker else None,
            "sex": self.sex,
            "age_band": self.age_band,
            "fit_type": self.fit_type,
            "distribution_type": self.distribution_type,
            "family": self.family,
            "stratum_name": self.stratum_name,
            "stratum_group": self.stratum_group,
            "parameters": params,
            "param_shape": self.param_shape,
            "param_loc": self.param_loc,
            "param_scale": self.param_scale,
            "domain_min": self.domain_min,
            "domain_max": self.domain_max,
            "valid_min": self.valid_min,
            "valid_max": self.valid_max,
            "ks_stat": self.ks_stat,
            "ks_pvalue": self.ks_pvalue,
            "aic": self.aic,
            "bic": self.bic,
            "source_id": self.source_id,
            "fit_quality_note": self.fit_quality_note,
        }


class HRFunction(Base):
    """
    Continuous mathematical Hazard Ratio function HR(x) derived from dose-response meta-analyses or splines.
    Operates strictly in log(HR) space with hard domain extrapolation guardrails.
    """
    __tablename__ = "hr_function"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    sex = Column(String(10), nullable=False, default="all", index=True)  # 'M', 'F', 'all'
    age_band = Column(String(50), nullable=False, default="all", index=True)  # 'all', '20-39', '40-59', '60+'
    
    # fit_type: 'log_linear_per_sd', 'log_linear_per_unit', 'quadratic', 'restricted_cubic_spline', 'linear', 'piecewise_linear'
    fit_type = Column(String(50), nullable=False)
    parameters = Column(JSON, default=dict)  # {'beta': 0.4} or spline coefficients
    domain_min = Column(Float, nullable=False)
    domain_max = Column(Float, nullable=False)
    reference_value = Column(Float, nullable=False)  # x_ref where HR(x_ref) = 1.0
    
    # shape: 'monotonic_increasing', 'monotonic_decreasing', 'u_shaped'
    shape = Column(String(50), nullable=False, index=True)
    nadir_value = Column(Float, nullable=True)  # Queryable argmin of HR(x) within domain for U-shaped curves
    
    source_id = Column(Integer, ForeignKey("source.id"), nullable=True, index=True)
    fit_quality_note = Column(Text, nullable=True)

    # Relationships
    biomarker = relationship("Biomarker")
    source = relationship("Source")
    
    __table_args__ = (
        Index("uq_hr_function_stratum", "biomarker_id", "sex", "age_band", unique=True),
    )

    @property
    def function_type(self):
        params = self.parameters or {}
        f_type = params.get("function_type", params.get("curve_type", self.fit_type))
        if f_type in ["log_linear_per_sd", "log_linear_per_unit", "linear_log"]:
            return "linear"
        return f_type

    @property
    def curve_type(self):
        return self.function_type

    @property
    def model_type(self):
        return self.function_type

    @property
    def valid_min(self):
        return self.domain_min

    @property
    def valid_max(self):
        return self.domain_max

    @property
    def knot_locations(self):
        params = self.parameters or {}
        return params.get("knot_locations", params.get("knots", []))

    @property
    def stratum_name(self):
        return f"{self.sex}_{self.age_band}"

    def to_dict(self):
        params = self.parameters or {}
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "biomarker_slug": self.biomarker.slug if self.biomarker else None,
            "sex": self.sex,
            "age_band": self.age_band,
            "stratum_name": self.stratum_name,
            "fit_type": self.fit_type,
            "function_type": self.function_type,
            "curve_type": self.curve_type,
            "model_type": self.model_type,
            "parameters": params,
            "domain_min": self.domain_min,
            "domain_max": self.domain_max,
            "valid_min": self.valid_min,
            "valid_max": self.valid_max,
            "knot_locations": self.knot_locations,
            "reference_value": self.reference_value,
            "shape": self.shape,
            "nadir_value": self.nadir_value,
            "source_id": self.source_id,
            "fit_quality_note": self.fit_quality_note,
        }


class Disease(Base):
    """
    Disease entity capturing clinical burden, remission rates, standard of care,
    and associated multi-scale alterations across physiological domains.
    """
    __tablename__ = "disease"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(120), unique=True, nullable=False, index=True)
    name = Column(String(250), nullable=False, index=True)
    category = Column(String(100), nullable=True, index=True)
    
    # Epidemiological & Economic Burden
    us_dalys = Column(String(50), nullable=True)
    global_dalys = Column(String(50), nullable=True)
    us_mortality = Column(String(50), nullable=True)
    global_mortality = Column(String(50), nullable=True)
    nih_funding = Column(String(50), nullable=True)
    funding_level = Column(String(50), nullable=True)
    
    # Remission & Chronicity Dynamics
    spontaneous_remission = Column(Text, nullable=True)
    best_intervention_remission = Column(Text, nullable=True)
    gap_size = Column(String(50), nullable=True)
    primary_barrier = Column(String(100), nullable=True)
    barrier_detail = Column(Text, nullable=True)
    soc_change = Column(Text, nullable=True)
    
    # Cross-ontology Identifiers (MONDO, EFO, OMIM, MESH, UMLS, etc.)
    identifiers = Column(JSON, default=dict)
    
    # Metadata
    alterations_count = Column(Integer, default=0)
    therapeutics_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    alterations = relationship("DiseaseAlteration", back_populates="disease", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "category": self.category,
            "us_dalys": self.us_dalys,
            "global_dalys": self.global_dalys,
            "us_mortality": self.us_mortality,
            "global_mortality": self.global_mortality,
            "nih_funding": self.nih_funding,
            "funding_level": self.funding_level,
            "spontaneous_remission": self.spontaneous_remission,
            "best_intervention_remission": self.best_intervention_remission,
            "gap_size": self.gap_size,
            "primary_barrier": self.primary_barrier,
            "barrier_detail": self.barrier_detail,
            "soc_change": self.soc_change,
            "identifiers": self.identifiers or {},
            "alterations_count": self.alterations_count,
            "therapeutics_count": self.therapeutics_count,
        }


class DiseaseAlteration(Base):
    """
    Multi-scale pathological or clinical alteration characterizing a disease state.
    Spans Type A (Molecular / Gene / Protein), Type B (Lab / Clinical Biomarker),
    Type C (Scales & PROs), Type D (Pathology / Structural), and Type E (Functional / Organ-level).
    Directly maps to Biomarkers in the Physiological Fitness Landscape where applicable.
    """
    __tablename__ = "disease_alteration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disease_id = Column(Integer, ForeignKey("disease.id"), nullable=False, index=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=True, index=True)

    name = Column(String(250), nullable=False, index=True)
    sub_name = Column(String(250), nullable=True)
    alteration_type = Column(String(50), nullable=False, index=True)  # 'Molecular', 'Lab / Clinical', 'Scales & PROs', 'Pathology', 'Functional'
    alteration_type_code = Column(String(10), nullable=True, index=True)  # 'A', 'B', 'C', 'D', 'E'
    subtype = Column(String(100), nullable=True)  # 'Gene', 'Lab value', 'Pathological finding', 'Clinical scale', etc.
    direction = Column(String(50), nullable=True)  # 'Elevated', 'Reduced', 'Upregulated', 'Downregulated', 'Abnormal', '—'
    frequency = Column(String(100), nullable=True)  # e.g. 'Common (75%)', 'Frequent', '—'
    evidence_level = Column(String(50), nullable=True)  # 'High', 'Moderate', 'Emerging', 'Low'
    sources = Column(String(300), nullable=True)  # e.g. 'Open Targets, HPO, ClinicalTrials.gov'
    links = Column(JSON, default=list)  # List[Dict[str, str]] with URLs to UniProt, Ensembl, HPO, LOINC, etc.
    is_biomarker_match = Column(Integer, default=0, index=True)  # 1 if linked to a Physiological Fitness Biomarker

    # Relationships
    disease = relationship("Disease", back_populates="alterations")
    biomarker = relationship("Biomarker", back_populates="disease_alterations")

    def to_dict(self):
        return {
            "id": self.id,
            "disease_id": self.disease_id,
            "disease_name": self.disease.name if self.disease else None,
            "disease_slug": self.disease.slug if self.disease else None,
            "biomarker_id": self.biomarker_id,
            "biomarker_name": self.biomarker.name if self.biomarker else None,
            "biomarker_slug": self.biomarker.slug if self.biomarker else None,
            "name": self.name,
            "sub_name": self.sub_name,
            "alteration_type": self.alteration_type,
            "alteration_type_code": self.alteration_type_code,
            "subtype": self.subtype,
            "direction": self.direction,
            "frequency": self.frequency,
            "evidence_level": self.evidence_level,
            "sources": self.sources,
            "links": self.links or [],
            "is_biomarker_match": bool(self.is_biomarker_match),
        }


# =======================================================================
# Intervention → Biomarker Effects Database
# =======================================================================

class InterventionEntity(Base):
    """
    Canonical intervention entity (drug, supplement, diet, exercise, etc.).
    Distinct from the legacy Intervention model which links a single
    intervention description to a biomarker + source.
    """
    __tablename__ = "intervention_entity"

    intervention_id = Column(String(100), primary_key=True)
    canonical_name = Column(String(300), nullable=False, index=True)
    # intervention_type: DRUG, SUPPLEMENT, DIET, EXERCISE, WEIGHT_LOSS,
    #   BEHAVIORAL, SMOKING_CESSATION, ALCOHOL_REDUCTION, SLEEP, SURGERY,
    #   PROCEDURE, DEVICE, OTHER
    intervention_type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    mechanism = Column(Text, nullable=True)
    synonyms = Column(JSON, default=list)  # List[str]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    regimens = relationship("InterventionRegimen", back_populates="intervention", cascade="all, delete-orphan")
    effects = relationship("InterventionBiomarkerEffect", back_populates="intervention")

    def to_dict(self):
        return {
            "intervention_id": self.intervention_id,
            "canonical_name": self.canonical_name,
            "intervention_type": self.intervention_type,
            "description": self.description,
            "mechanism": self.mechanism,
            "synonyms": self.synonyms or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InterventionRegimen(Base):
    """
    Specific dosing / delivery regimen for an intervention.
    The same intervention can have radically different effects depending on
    dose, frequency, route, formulation, intensity, duration, etc.
    """
    __tablename__ = "intervention_regimen"

    regimen_id = Column(String(100), primary_key=True)
    intervention_id = Column(String(100), ForeignKey("intervention_entity.intervention_id"), nullable=False, index=True)

    # General
    formulation = Column(String(200), nullable=True)
    route = Column(String(100), nullable=True)
    dose_value = Column(Float, nullable=True)
    dose_unit = Column(String(50), nullable=True)
    dose_frequency = Column(String(100), nullable=True)
    dose_frequency_value = Column(Float, nullable=True)
    dose_frequency_unit = Column(String(50), nullable=True)
    timing = Column(String(200), nullable=True)
    intensity = Column(String(100), nullable=True)
    duration_value = Column(Float, nullable=True)
    duration_unit = Column(String(50), nullable=True)
    cycles = Column(String(100), nullable=True)
    titration = Column(Text, nullable=True)
    adherence_target = Column(String(200), nullable=True)
    regimen_description = Column(Text, nullable=True)
    source_evidence_id = Column(String(100), nullable=True)

    # Session-level fields (exercise / behavioral)
    session_duration_value = Column(Float, nullable=True)
    session_duration_unit = Column(String(50), nullable=True)
    sessions_per_week = Column(Float, nullable=True)
    intensity_value = Column(Float, nullable=True)
    intensity_unit = Column(String(50), nullable=True)

    # Diet-specific fields
    diet_pattern = Column(String(200), nullable=True)
    energy_target = Column(Float, nullable=True)
    energy_target_unit = Column(String(50), nullable=True)
    macronutrient_targets = Column(JSON, default=dict)
    adherence_measure = Column(String(200), nullable=True)

    # Drug-specific fields
    active_ingredient = Column(String(200), nullable=True)
    dose_per_administration = Column(Float, nullable=True)
    dose_per_administration_unit = Column(String(50), nullable=True)

    # Relationships
    intervention = relationship("InterventionEntity", back_populates="regimens")
    effects = relationship("InterventionBiomarkerEffect", back_populates="regimen")

    def to_dict(self):
        return {
            "regimen_id": self.regimen_id,
            "intervention_id": self.intervention_id,
            "formulation": self.formulation,
            "route": self.route,
            "dose_value": self.dose_value,
            "dose_unit": self.dose_unit,
            "dose_frequency": self.dose_frequency,
            "dose_frequency_value": self.dose_frequency_value,
            "dose_frequency_unit": self.dose_frequency_unit,
            "timing": self.timing,
            "intensity": self.intensity,
            "duration_value": self.duration_value,
            "duration_unit": self.duration_unit,
            "cycles": self.cycles,
            "titration": self.titration,
            "adherence_target": self.adherence_target,
            "regimen_description": self.regimen_description,
            "source_evidence_id": self.source_evidence_id,
            "session_duration_value": self.session_duration_value,
            "session_duration_unit": self.session_duration_unit,
            "sessions_per_week": self.sessions_per_week,
            "intensity_value": self.intensity_value,
            "intensity_unit": self.intensity_unit,
            "diet_pattern": self.diet_pattern,
            "energy_target": self.energy_target,
            "energy_target_unit": self.energy_target_unit,
            "macronutrient_targets": self.macronutrient_targets or {},
            "adherence_measure": self.adherence_measure,
            "active_ingredient": self.active_ingredient,
            "dose_per_administration": self.dose_per_administration,
            "dose_per_administration_unit": self.dose_per_administration_unit,
        }


class InterventionBiomarkerEffect(Base):
    """
    Core table: a specific intervention + regimen + biomarker effect observation.
    The fundamental unit of the intervention → biomarker effects database.
    """
    __tablename__ = "intervention_biomarker_effect"

    effect_id = Column(String(100), primary_key=True)
    intervention_id = Column(String(100), ForeignKey("intervention_entity.intervention_id"), nullable=False, index=True)
    regimen_id = Column(String(100), ForeignKey("intervention_regimen.regimen_id"), nullable=True, index=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    evidence_id = Column(String(100), ForeignKey("intervention_evidence.evidence_id"), nullable=False, index=True)
    comparator_id = Column(String(100), ForeignKey("intervention_comparator.comparator_id"), nullable=True, index=True)

    # effect_type: MEAN_DIFFERENCE, PERCENT_CHANGE, STANDARDIZED_MEAN_DIFFERENCE,
    #   RATIO_OF_MEANS, LOG_RATIO_OF_MEANS, CHANGE_FROM_BASELINE, BETWEEN_GROUP_CHANGE
    effect_type = Column(String(50), nullable=False, index=True)
    effect_value = Column(Float, nullable=True)
    effect_lower = Column(Float, nullable=True)
    effect_upper = Column(Float, nullable=True)
    standard_error = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    effect_unit = Column(String(50), nullable=True)
    # effect_scale: ABSOLUTE, PERCENT, LOG, STANDARDIZED
    effect_scale = Column(String(50), nullable=True)

    # Timepoint
    timepoint_value = Column(Float, nullable=True)
    timepoint_unit = Column(String(50), nullable=True)

    # Baseline / post values
    baseline_biomarker = Column(Float, nullable=True)
    baseline_biomarker_sd = Column(Float, nullable=True)
    post_biomarker = Column(Float, nullable=True)
    post_biomarker_sd = Column(Float, nullable=True)

    # Sample sizes
    sample_size = Column(Integer, nullable=True)
    intervention_sample_size = Column(Integer, nullable=True)
    comparator_sample_size = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    intervention = relationship("InterventionEntity", back_populates="effects")
    regimen = relationship("InterventionRegimen", back_populates="effects")
    biomarker = relationship("Biomarker")
    evidence = relationship("InterventionEvidence")
    comparator = relationship("InterventionComparator")
    measurement = relationship("EffectMeasurement", back_populates="effect", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "effect_id": self.effect_id,
            "intervention_id": self.intervention_id,
            "regimen_id": self.regimen_id,
            "biomarker_id": self.biomarker_id,
            "evidence_id": self.evidence_id,
            "comparator_id": self.comparator_id,
            "effect_type": self.effect_type,
            "effect_value": self.effect_value,
            "effect_lower": self.effect_lower,
            "effect_upper": self.effect_upper,
            "standard_error": self.standard_error,
            "p_value": self.p_value,
            "effect_unit": self.effect_unit,
            "effect_scale": self.effect_scale,
            "timepoint_value": self.timepoint_value,
            "timepoint_unit": self.timepoint_unit,
            "baseline_biomarker": self.baseline_biomarker,
            "baseline_biomarker_sd": self.baseline_biomarker_sd,
            "post_biomarker": self.post_biomarker,
            "post_biomarker_sd": self.post_biomarker_sd,
            "sample_size": self.sample_size,
            "intervention_sample_size": self.intervention_sample_size,
            "comparator_sample_size": self.comparator_sample_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EffectMeasurement(Base):
    """
    Preserves original reported measurement and canonical unit conversion.
    Never overwrites the original value.
    """
    __tablename__ = "effect_measurement"

    effect_id = Column(String(100), ForeignKey("intervention_biomarker_effect.effect_id"), primary_key=True)

    original_value = Column(Float, nullable=True)
    original_lower = Column(Float, nullable=True)
    original_upper = Column(Float, nullable=True)
    original_unit = Column(String(50), nullable=True)

    canonical_value = Column(Float, nullable=True)
    canonical_lower = Column(Float, nullable=True)
    canonical_upper = Column(Float, nullable=True)
    canonical_unit = Column(String(50), nullable=True)

    conversion_factor = Column(Float, nullable=True)
    conversion_method = Column(String(200), nullable=True)

    # Relationships
    effect = relationship("InterventionBiomarkerEffect", back_populates="measurement")

    def to_dict(self):
        return {
            "effect_id": self.effect_id,
            "original_value": self.original_value,
            "original_lower": self.original_lower,
            "original_upper": self.original_upper,
            "original_unit": self.original_unit,
            "canonical_value": self.canonical_value,
            "canonical_lower": self.canonical_lower,
            "canonical_upper": self.canonical_upper,
            "canonical_unit": self.canonical_unit,
            "conversion_factor": self.conversion_factor,
            "conversion_method": self.conversion_method,
        }


class InterventionEvidence(Base):
    """
    Evidence record: a specific study, review, or trial that supports
    an intervention → biomarker effect.
    """
    __tablename__ = "intervention_evidence"

    evidence_id = Column(String(100), primary_key=True)
    # source_type: COCHRANE_REVIEW, SYSTEMATIC_REVIEW, META_ANALYSIS,
    #   RANDOMIZED_CONTROLLED_TRIAL, CONTROLLED_CLINICAL_TRIAL,
    #   PROSPECTIVE_INTERVENTION, OTHER_CLINICAL_STUDY
    source_type = Column(String(50), nullable=False, index=True)
    title = Column(Text, nullable=True)
    authors = Column(Text, nullable=True)
    journal = Column(String(300), nullable=True)
    publication_year = Column(Integer, nullable=True)
    doi = Column(String(100), nullable=True, index=True)
    pmid = Column(String(30), nullable=True, index=True)
    nct_id = Column(String(30), nullable=True, index=True)
    url = Column(String(500), nullable=True)
    study_design = Column(String(100), nullable=True)
    # evidence_level: HIGH, MODERATE, LOW, VERY_LOW, UNKNOWN
    evidence_level = Column(String(50), nullable=True)
    population_description = Column(Text, nullable=True)
    sample_size = Column(Integer, nullable=True)
    comparator_description = Column(Text, nullable=True)
    followup_value = Column(Float, nullable=True)
    followup_unit = Column(String(50), nullable=True)
    risk_of_bias = Column(String(100), nullable=True)
    # certainty: HIGH, MODERATE, LOW, VERY_LOW, UNKNOWN
    certainty = Column(String(50), nullable=True)
    extraction_status = Column(String(50), nullable=True)
    source_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Heterogeneity (for meta-analyses)
    heterogeneity_i2 = Column(Float, nullable=True)
    heterogeneity_tau2 = Column(Float, nullable=True)
    number_of_studies = Column(Integer, nullable=True)

    # Relationships
    effects = relationship("InterventionBiomarkerEffect", back_populates="evidence")
    populations = relationship("EvidencePopulation", back_populates="evidence", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "title": self.title,
            "authors": self.authors,
            "journal": self.journal,
            "publication_year": self.publication_year,
            "doi": self.doi,
            "pmid": self.pmid,
            "nct_id": self.nct_id,
            "url": self.url,
            "study_design": self.study_design,
            "evidence_level": self.evidence_level,
            "population_description": self.population_description,
            "sample_size": self.sample_size,
            "comparator_description": self.comparator_description,
            "followup_value": self.followup_value,
            "followup_unit": self.followup_unit,
            "risk_of_bias": self.risk_of_bias,
            "certainty": self.certainty,
            "extraction_status": self.extraction_status,
            "source_date": self.source_date.isoformat() if self.source_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "heterogeneity_i2": self.heterogeneity_i2,
            "heterogeneity_tau2": self.heterogeneity_tau2,
            "number_of_studies": self.number_of_studies,
        }


class EvidencePopulation(Base):
    """
    Study population characteristics for an evidence record.
    Allows later determination of whether an intervention effect applies
    to a particular user/population.
    """
    __tablename__ = "evidence_population"

    population_id = Column(String(100), primary_key=True)
    evidence_id = Column(String(100), ForeignKey("intervention_evidence.evidence_id"), nullable=False, index=True)

    age_mean = Column(Float, nullable=True)
    age_sd = Column(Float, nullable=True)
    age_min = Column(Float, nullable=True)
    age_max = Column(Float, nullable=True)
    sex_distribution = Column(JSON, default=dict)  # e.g. {"male": 0.55, "female": 0.45}
    race_ethnicity_distribution = Column(JSON, default=dict)
    bmi_mean = Column(Float, nullable=True)
    bmi_sd = Column(Float, nullable=True)
    baseline_condition = Column(String(300), nullable=True)
    disease_status = Column(String(300), nullable=True)
    baseline_biomarker_mean = Column(Float, nullable=True)
    baseline_biomarker_sd = Column(Float, nullable=True)
    inclusion_criteria = Column(Text, nullable=True)
    exclusion_criteria = Column(Text, nullable=True)

    # Relationships
    evidence = relationship("InterventionEvidence", back_populates="populations")

    def to_dict(self):
        return {
            "population_id": self.population_id,
            "evidence_id": self.evidence_id,
            "age_mean": self.age_mean,
            "age_sd": self.age_sd,
            "age_min": self.age_min,
            "age_max": self.age_max,
            "sex_distribution": self.sex_distribution or {},
            "race_ethnicity_distribution": self.race_ethnicity_distribution or {},
            "bmi_mean": self.bmi_mean,
            "bmi_sd": self.bmi_sd,
            "baseline_condition": self.baseline_condition,
            "disease_status": self.disease_status,
            "baseline_biomarker_mean": self.baseline_biomarker_mean,
            "baseline_biomarker_sd": self.baseline_biomarker_sd,
            "inclusion_criteria": self.inclusion_criteria,
            "exclusion_criteria": self.exclusion_criteria,
        }


class InterventionComparator(Base):
    """
    Comparator arm in a study.
    """
    __tablename__ = "intervention_comparator"

    comparator_id = Column(String(100), primary_key=True)
    # comparator_type: PLACEBO, NO_TREATMENT, USUAL_CARE, ACTIVE_COMPARATOR,
    #   WAITLIST, BASELINE, OTHER
    comparator_type = Column(String(50), nullable=False, index=True)
    comparator_name = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    effects = relationship("InterventionBiomarkerEffect", back_populates="comparator")

    def to_dict(self):
        return {
            "comparator_id": self.comparator_id,
            "comparator_type": self.comparator_type,
            "comparator_name": self.comparator_name,
            "description": self.description,
        }


class EvidenceRelationship(Base):
    """
    Links between evidence records (e.g. meta-analysis contains trial,
    publication reports trial, duplicate publication, etc.).
    """
    __tablename__ = "evidence_relationship"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_evidence_id = Column(String(100), ForeignKey("intervention_evidence.evidence_id"), nullable=False, index=True)
    child_evidence_id = Column(String(100), ForeignKey("intervention_evidence.evidence_id"), nullable=False, index=True)
    # relationship: META_ANALYSIS_CONTAINS_TRIAL, SYSTEMATIC_REVIEW_CONTAINS_TRIAL,
    #   PUBLICATION_REPORTS_TRIAL, FOLLOWUP_OF_TRIAL, DUPLICATE_PUBLICATION
    relationship = Column(String(50), nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "parent_evidence_id": self.parent_evidence_id,
            "child_evidence_id": self.child_evidence_id,
            "relationship": self.relationship,
        }


# =======================================================================
# General Intervention Schema (CT.gov-compatible)
# =======================================================================
# Design: top-level type = ClinicalTrials.gov controlled vocabulary,
# subcategory = data-driven lookup table, type-specific detail = EAV.
# Mirrors the canonical-entity-vs-raw-source pattern used for lab tests.

class InterventionCategory(Base):
    """
    Extensible subcategory lookup. Adding a new category is an INSERT,
    not a migration. Each row rolls up to a CT.gov top-level type.
    """
    __tablename__ = "intervention_categories"

    category_id = Column(String(100), primary_key=True)
    label = Column(String(200), nullable=False)
    # CT.gov top-level bucket: DRUG | DEVICE | BIOLOGICAL | PROCEDURE |
    # RADIATION | BEHAVIORAL | DIETARY_SUPPLEMENT | GENETIC |
    # COMBINATION_PRODUCT | DIAGNOSTIC_TEST | OTHER
    ct_gov_intervention_type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    interventions = relationship("GeneralIntervention", back_populates="category")

    def to_dict(self):
        return {
            "category_id": self.category_id,
            "label": self.label,
            "ct_gov_intervention_type": self.ct_gov_intervention_type,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Starter seed rows -- INSERT statements, not part of the DDL itself.
INTERVENTION_CATEGORIES_SEED = [
    ("pharmaceutical", "Pharmaceutical drug", "DRUG"),
    ("biologic_vaccine", "Biologic / vaccine", "BIOLOGICAL"),
    ("medical_device", "Medical device", "DEVICE"),
    ("procedure_surgery", "Procedure / surgery", "PROCEDURE"),
    ("radiation", "Radiation therapy", "RADIATION"),
    ("dietary_supplement", "Dietary supplement / nutraceutical", "DIETARY_SUPPLEMENT"),
    ("genetic_therapy", "Genetic / gene therapy", "GENETIC"),
    ("combination_product", "Combination product", "COMBINATION_PRODUCT"),
    ("diagnostic_test", "Diagnostic test (as intervention)", "DIAGNOSTIC_TEST"),
    # CT.gov files all of these under the single "Behavioral" bucket --
    # split out because the platform explicitly wants to distinguish them.
    ("exercise", "Exercise / physical activity", "BEHAVIORAL"),
    ("dietary_pattern", "Dietary pattern (e.g. Mediterranean, DASH)", "BEHAVIORAL"),
    ("sleep_intervention", "Sleep intervention", "BEHAVIORAL"),
    ("smoking_cessation", "Smoking cessation", "BEHAVIORAL"),
    ("mindfulness_stress", "Mindfulness / stress reduction", "BEHAVIORAL"),
    ("other_behavioral", "Other behavioral intervention", "BEHAVIORAL"),
    ("other", "Other / uncategorized", "OTHER"),
]


class GeneralIntervention(Base):
    """
    Canonical intervention entity. Distinct from the legacy Intervention
    model (which links a single description to a biomarker + source) and
    from the InterventionEntity model (which is regimen-centric).
    This is the CT.gov-compatible canonical entity.
    """
    __tablename__ = "general_intervention"

    intervention_id = Column(String(100), primary_key=True)
    canonical_name = Column(String(300), nullable=False, index=True)
    category_id = Column(String(100), ForeignKey("intervention_categories.category_id"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = relationship("InterventionCategory", back_populates="interventions")
    synonyms = relationship("GeneralInterventionSynonym", back_populates="intervention", cascade="all, delete-orphan")
    attributes = relationship("GeneralInterventionAttribute", back_populates="intervention", cascade="all, delete-orphan")
    arm_mappings = relationship("InterventionArmMapping", back_populates="candidate_intervention")
    effects = relationship("BiomarkerInterventionEffect", back_populates="intervention")

    def to_dict(self):
        return {
            "intervention_id": self.intervention_id,
            "canonical_name": self.canonical_name,
            "category_id": self.category_id,
            "category_label": self.category.label if self.category else None,
            "ct_gov_type": self.category.ct_gov_intervention_type if self.category else None,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GeneralInterventionSynonym(Base):
    """
    Synonyms / alternative names for a canonical intervention.
    CT.gov itself collects "Other Intervention Names" per this pattern.
    """
    __tablename__ = "general_intervention_synonyms"

    intervention_id = Column(String(100), ForeignKey("general_intervention.intervention_id"), primary_key=True)
    synonym = Column(String(300), nullable=False, primary_key=True)
    # 'brand_name' | 'generic_name' | 'code_name' | 'other'
    synonym_type = Column(String(50), nullable=True)
    source = Column(String(200), nullable=True)

    # Relationships
    intervention = relationship("GeneralIntervention", back_populates="synonyms")

    def to_dict(self):
        return {
            "intervention_id": self.intervention_id,
            "synonym": self.synonym,
            "synonym_type": self.synonym_type,
            "source": self.source,
        }


class GeneralInterventionAttribute(Base):
    """
    Type-agnostic structured attributes (EAV -- the generality mechanism).
    A drug's dose/route, a device's model/manufacturer, an exercise
    intervention's modality/intensity/frequency, and a dietary pattern's
    macronutrient targets all fit the same (key, value, unit) shape.
    """
    __tablename__ = "general_intervention_attributes"

    attribute_id = Column(String(100), primary_key=True)
    intervention_id = Column(String(100), ForeignKey("general_intervention.intervention_id"), nullable=False, index=True)
    # Free but conventionally namespaced, e.g.:
    #   drug:  route, typical_dose, mechanism_class
    #   device: manufacturer, model, fda_classification
    #   exercise: modality, intensity, frequency_per_week, session_duration_min
    #   dietary_pattern: macronutrient_profile, key_foods_emphasized, key_foods_restricted
    attribute_key = Column(String(100), nullable=False, index=True)
    attribute_value = Column(Text, nullable=True)
    attribute_unit = Column(String(50), nullable=True)
    source = Column(String(200), nullable=True)
    retrieved_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    intervention = relationship("GeneralIntervention", back_populates="attributes")

    def to_dict(self):
        return {
            "attribute_id": self.attribute_id,
            "intervention_id": self.intervention_id,
            "attribute_key": self.attribute_key,
            "attribute_value": self.attribute_value,
            "attribute_unit": self.attribute_unit,
            "source": self.source,
            "retrieved_date": self.retrieved_date.isoformat() if self.retrieved_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TrialInterventionArm(Base):
    """
    Raw per-trial intervention arms, as ingested from ClinicalTrials.gov
    (or, later, other registries -- source column keeps this open).
    """
    __tablename__ = "trial_intervention_arms"

    arm_id = Column(String(100), primary_key=True)
    source = Column(String(50), nullable=False, index=True)  # 'CLINICALTRIALS' | (future: other registries)
    source_study_id = Column(String(50), nullable=False, index=True)  # NCT number
    raw_intervention_type = Column(String(100), nullable=True)  # verbatim CT.gov type as ingested
    raw_name = Column(String(500), nullable=False)  # verbatim intervention name/title
    raw_description = Column(Text, nullable=True)
    raw_other_names = Column(JSON, default=list)  # JSON array -- CT.gov's "Other Intervention Names"
    arm_group_label = Column(String(200), nullable=True)
    retrieved_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    mappings = relationship("InterventionArmMapping", back_populates="arm", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "arm_id": self.arm_id,
            "source": self.source,
            "source_study_id": self.source_study_id,
            "raw_intervention_type": self.raw_intervention_type,
            "raw_name": self.raw_name,
            "raw_description": self.raw_description,
            "raw_other_names": self.raw_other_names or [],
            "arm_group_label": self.arm_group_label,
            "retrieved_date": self.retrieved_date.isoformat() if self.retrieved_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InterventionArmMapping(Base):
    """
    Review queue: raw arm -> canonical intervention.
    Same pattern as LOINC mapping: NEEDS_REVIEW / MANUAL_VERIFIED discipline.
    """
    __tablename__ = "intervention_arm_mappings"

    mapping_id = Column(String(100), primary_key=True)
    arm_id = Column(String(100), ForeignKey("trial_intervention_arms.arm_id"), nullable=False, index=True)
    candidate_intervention_id = Column(String(100), ForeignKey("general_intervention.intervention_id"), nullable=True, index=True)
    # 'exact_name' | 'synonym_match' | 'llm_extracted' | 'manual'
    match_method = Column(String(50), nullable=True)
    # 'high' | 'medium' | 'low'
    confidence = Column(String(20), nullable=True)
    # AUTO_VERIFIED | MANUAL_VERIFIED | NEEDS_REVIEW | REJECTED
    review_status = Column(String(50), nullable=False, index=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    arm = relationship("TrialInterventionArm", back_populates="mappings")
    candidate_intervention = relationship("GeneralIntervention", back_populates="arm_mappings")

    def to_dict(self):
        return {
            "mapping_id": self.mapping_id,
            "arm_id": self.arm_id,
            "candidate_intervention_id": self.candidate_intervention_id,
            "candidate_name": self.candidate_intervention.canonical_name if self.candidate_intervention else None,
            "match_method": self.match_method,
            "confidence": self.confidence,
            "review_status": self.review_status,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BiomarkerInterventionEffect(Base):
    """
    Effect estimates referencing the general (CT.gov-compatible) intervention_id.
    Same shape as the legacy InterventionBiomarkerEffect but keyed to
    GeneralIntervention instead of InterventionEntity.
    """
    __tablename__ = "biomarker_intervention_effects"

    effect_id = Column(String(100), primary_key=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    intervention_id = Column(String(100), ForeignKey("general_intervention.intervention_id"), nullable=False, index=True)

    # mean_difference | standardized_mean_difference | percent_change
    # | relative_risk | odds_ratio
    effect_measure = Column(String(50), nullable=False, index=True)
    effect_value = Column(Float, nullable=True)
    effect_unit = Column(String(50), nullable=True)
    ci_low = Column(Float, nullable=True)
    ci_high = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)

    # 'increases' | 'decreases' | 'no_significant_effect'
    direction = Column(String(50), nullable=True)

    dose = Column(String(200), nullable=True)
    duration = Column(String(100), nullable=True)
    population = Column(String(300), nullable=True)

    n_participants = Column(Integer, nullable=True)
    n_studies = Column(Integer, nullable=True)

    study_design = Column(String(100), nullable=True)

    source = Column(String(50), nullable=False, index=True)  # 'EUROPEPMC' | 'COCHRANE' | 'CLINICALTRIALS' | 'PUBMED'
    source_id = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True)
    source_title = Column(Text, nullable=True)
    publication_date = Column(String(50), nullable=True)
    retrieved_date = Column(DateTime, nullable=True)

    extraction_method = Column(String(50), nullable=True)  # 'llm_extracted' | 'manual'
    extraction_model = Column(String(100), nullable=True)
    # AUTO_EXTRACTED | NEEDS_REVIEW | MANUAL_VERIFIED | REJECTED
    review_status = Column(String(50), nullable=False, index=True)
    review_notes = Column(Text, nullable=True)
    plausibility_flag = Column(String(50), nullable=True)  # null | 'outside_nhanes_range' | 'implausible_effect_size'

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    biomarker = relationship("Biomarker")
    intervention = relationship("GeneralIntervention", back_populates="effects")

    def to_dict(self):
        return {
            "effect_id": self.effect_id,
            "biomarker_id": self.biomarker_id,
            "biomarker_name": self.biomarker.name if self.biomarker else None,
            "intervention_id": self.intervention_id,
            "intervention_name": self.intervention.canonical_name if self.intervention else None,
            "effect_measure": self.effect_measure,
            "effect_value": self.effect_value,
            "effect_unit": self.effect_unit,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "p_value": self.p_value,
            "direction": self.direction,
            "dose": self.dose,
            "duration": self.duration,
            "population": self.population,
            "n_participants": self.n_participants,
            "n_studies": self.n_studies,
            "study_design": self.study_design,
            "source": self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "publication_date": self.publication_date,
            "retrieved_date": self.retrieved_date.isoformat() if self.retrieved_date else None,
            "extraction_method": self.extraction_method,
            "extraction_model": self.extraction_model,
            "review_status": self.review_status,
            "review_notes": self.review_notes,
            "plausibility_flag": self.plausibility_flag,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InterventionHazardImpact(Base):
    """
    One row per (biomarker, age-cohort, sex) showing the resulting shifted
    distribution/HR after applying a MANUAL_VERIFIED effect.
    Built by combining biomarker_intervention_effects with the existing
    NHANES distribution + hazard_curves.predict_hr_curve.
    """
    __tablename__ = "intervention_hazard_impact"

    impact_id = Column(String(100), primary_key=True)
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), nullable=False, index=True)
    intervention_id = Column(String(100), ForeignKey("general_intervention.intervention_id"), nullable=False, index=True)
    effect_id = Column(String(100), ForeignKey("biomarker_intervention_effects.effect_id"), nullable=False, index=True)

    age = Column(Integer, nullable=True)
    sex = Column(String(10), nullable=True)
    race_ethnicity = Column(String(100), nullable=True)

    baseline_value = Column(Float, nullable=True)
    shifted_value = Column(Float, nullable=True)

    hr_baseline = Column(Float, nullable=True)
    hr_shifted = Column(Float, nullable=True)
    hr_ratio = Column(Float, nullable=True)  # hr_shifted / hr_baseline -- the headline number

    mortality_model_id = Column(String(100), nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    biomarker = relationship("Biomarker")
    intervention = relationship("GeneralIntervention")
    effect = relationship("BiomarkerInterventionEffect")

    def to_dict(self):
        return {
            "impact_id": self.impact_id,
            "biomarker_id": self.biomarker_id,
            "biomarker_name": self.biomarker.name if self.biomarker else None,
            "intervention_id": self.intervention_id,
            "intervention_name": self.intervention.canonical_name if self.intervention else None,
            "effect_id": self.effect_id,
            "age": self.age,
            "sex": self.sex,
            "race_ethnicity": self.race_ethnicity,
            "baseline_value": self.baseline_value,
            "shifted_value": self.shifted_value,
            "hr_baseline": self.hr_baseline,
            "hr_shifted": self.hr_shifted,
            "hr_ratio": self.hr_ratio,
            "mortality_model_id": self.mortality_model_id,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }


class VoiPolicyConfig(Base):
    """User-adjustable policy parameters for the VOI/EHIV layer (not biomarker data)."""
    __tablename__ = "voi_policy_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lambda_default = Column(Float, nullable=False, default=150000.0)
    epsilon_default = Column(Float, nullable=False, default=1.0)
    c_int_daly_default = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "lambdaDefault": self.lambda_default,
            "epsilonDefault": self.epsilon_default,
            "cIntDalyDefault": self.c_int_daly_default,
            "notes": self.notes,
        }


def get_engine(db_path: str = "sqlite:///data/mortality_biomarkers.db"):
    return create_engine(db_path, echo=False)


def _ensure_voi_schema(engine):
    """Add VOI columns/tables on existing SQLite databases (create_all will not ALTER)."""
    from sqlalchemy import text, inspect

    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("biomarker")} if insp.has_table("biomarker") else set()
    with engine.begin() as conn:
        if "test_price_usd" not in cols:
            conn.execute(text("ALTER TABLE biomarker ADD COLUMN test_price_usd FLOAT"))
        if "cms_reimbursement_usd" not in cols:
            conn.execute(text("ALTER TABLE biomarker ADD COLUMN cms_reimbursement_usd FLOAT"))
        if "loinc_to_test_id" not in cols:
            conn.execute(text("ALTER TABLE biomarker ADD COLUMN loinc_to_test_id JSON"))

        # Copy priced tests onto biomarker rows when still null.
        if insp.has_table("lab_tests") and insp.has_table("test_cost_summary"):
            try:
                conn.execute(text("""
                    UPDATE biomarker
                    SET
                        test_price_usd = (
                            SELECT s.reference_consumer_price
                            FROM lab_tests t
                            JOIN test_cost_summary s ON s.test_id = t.test_id
                            WHERE t.canonical_biomarker_id = biomarker.id
                              AND s.reference_consumer_price IS NOT NULL
                            LIMIT 1
                        ),
                        cms_reimbursement_usd = (
                            SELECT s.cms_clfs
                            FROM lab_tests t
                            JOIN test_cost_summary s ON s.test_id = t.test_id
                            WHERE t.canonical_biomarker_id = biomarker.id
                              AND s.cms_clfs IS NOT NULL
                            LIMIT 1
                        )
                    WHERE test_price_usd IS NULL
                """))
            except Exception:
                pass


def init_db(engine):
    Base.metadata.create_all(engine)
    _ensure_voi_schema(engine)
    # Seed intervention categories if table is empty
    with engine.connect() as conn:
        from sqlalchemy import text
        count = conn.execute(text("SELECT COUNT(*) FROM intervention_categories")).scalar()
        if count == 0:
            for cat_id, label, ct_type in INTERVENTION_CATEGORIES_SEED:
                conn.execute(
                    text("INSERT INTO intervention_categories (category_id, label, ct_gov_intervention_type, created_at) VALUES (:cid, :label, :ct, :now)"),
                    {"cid": cat_id, "label": label, "ct": ct_type, "now": datetime.utcnow()},
                )
            conn.commit()
            print(f"Seeded {len(INTERVENTION_CATEGORIES_SEED)} intervention categories")
        voi_count = conn.execute(text("SELECT COUNT(*) FROM voi_policy_config")).scalar()
        if voi_count == 0:
            conn.execute(
                text(
                    "INSERT INTO voi_policy_config (lambda_default, epsilon_default, c_int_daly_default, notes, updated_at) "
                    "VALUES (:lam, :eps, :cint, :notes, :now)"
                ),
                {
                    "lam": 150000.0,
                    "eps": 1.0,
                    "cint": 0.0,
                    "notes": "lambda is a normative willingness-to-pay per DALY, not an empirical estimate.",
                    "now": datetime.utcnow(),
                },
            )
            conn.commit()

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

    # Relationships
    mortality_associations = relationship("MortalityAssociation", back_populates="biomarker", cascade="all, delete-orphan")
    population_distributions = relationship("PopulationDistribution", back_populates="biomarker", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="biomarker", cascade="all, delete-orphan")
    hr_curve = relationship("BiomarkerHRCurve", back_populates="biomarker", uselist=False, cascade="all, delete-orphan")
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
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), unique=True, nullable=False, index=True)
    
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
    biomarker = relationship("Biomarker", back_populates="hr_curve")

    def to_dict(self):
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
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
    biomarker_id = Column(Integer, ForeignKey("biomarker.id"), unique=True, nullable=False, index=True)
    
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

    def to_dict(self):
        params = self.parameters or {}
        return {
            "id": self.id,
            "biomarker_id": self.biomarker_id,
            "biomarker_slug": self.biomarker.slug if self.biomarker else None,
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


def get_engine(db_path: str = "sqlite:///data/mortality_biomarkers.db"):
    return create_engine(db_path, echo=False)


def init_db(engine):
    Base.metadata.create_all(engine)

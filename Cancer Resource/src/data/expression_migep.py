"""
MIGEP computation, normalization, canonical-space mapping, and I/O.
Complements src/data/expression.py.
"""
from __future__ import annotations
import statistics
import numpy as np
from src.data.expression import ExpressionProfile


class MIGEP(ExpressionProfile):
    """Modifier-Induced Gene Expression Profile."""

    def __init__(self, *, treated_values, control_values, gene_symbols,
                 modifier_id="", protocol="", biological_context="", tissue="",
                 study_id="", species="human", dose=None, duration_hr=None,
                 timepoint_hr=None, platform="", n_replicates=1,
                 quality_score=None, diff_method="subtraction"):
        diff_vector = [t-c if t is not None and c is not None else None
                       for t, c in zip(treated_values, control_values)]
        super().__init__(vector=diff_vector, gene_symbols=gene_symbols,
            source_dataset=study_id or "", tissue=tissue,
            context=biological_context, modifier_id=modifier_id,
            protocol=protocol, timepoint_hr=timepoint_hr,
            n_replicates=n_replicates, quality_score=quality_score,
            replicate_info={"n_replicates": n_replicates})
        self.study_id = study_id
        self.species = species
        self.dose = dose or {}
        self.duration_hr = duration_hr
        self.platform = platform
        self.diff_method = diff_method
        self.biological_context = biological_context

    def to_dict(self):
        return {"modifier_id": self.modifier_id, "protocol": self.protocol,
                "biological_context": self.biological_context, "tissue": self.tissue,
                "study_id": self.study_id, "species": self.species, "dose": self.dose,
                "duration_hr": self.duration_hr, "timepoint_hr": self.timepoint_hr,
                "n_genes": self.n_genes}


def robust_z_normalize(vector):
    """Robust z-score (median / MAD * 1.4826). None entries stay None."""
    present = [v for v in vector if v is not None]
    if len(present) < 2:
        raise ValueError(f"Need >= 2 present values, got {len(present)}")
    med = statistics.median(present)
    mad = statistics.median(abs(v - med) for v in present)
    scale = 1.4826 * mad if mad > 0 else 1e-9
    return [None if v is None else (v - med) / scale for v in vector]


def map_to_978(signature, gene_symbols, min_coverage=0.7):
    """Map gene_symbol -> value dict to 978-gene space."""
    vector = [signature.get(sym) for sym in gene_symbols]
    n_present = sum(1 for v in vector if v is not None)
    coverage = n_present / len(gene_symbols) if gene_symbols else 0.0
    if coverage < min_coverage:
        raise ValueError(
            "Gene coverage {:.3f} ({}/{}) below minimum {}".format(
                coverage, n_present, len(gene_symbols), min_coverage))
    return vector, coverage, n_present


def calculate_migep(treated, control, gene_symbols, modifier_id="",
                    protocol="", biological_context="", study_id="",
                    min_coverage=0.7, normalize=True):
    """Calculate MIGEP = treated - control in 978-gene space."""
    t_vec, t_cov, _ = map_to_978(treated, gene_symbols, min_coverage)
    c_vec, c_cov, _ = map_to_978(control, gene_symbols, min_coverage)
    diff = [t-c if t is not None and c is not None else None
            for t, c in zip(t_vec, c_vec)]
    if normalize:
        diff = robust_z_normalize(diff)
    return MIGEP(treated_values=t_vec, control_values=c_vec,
                 gene_symbols=gene_symbols, modifier_id=modifier_id,
                 protocol=protocol, biological_context=biological_context,
                 study_id=study_id, quality_score=min(t_cov, c_cov))


def load_expression_profile(path):
    """Load gene expression from TSV/CSV: gene_symbol, expression_value."""
    gene_expr = {}
    with open(path, encoding="utf-8") as f:
        first_line = f.readline().strip()
        delimiter = "\t" if "\t" in first_line else ","
        is_header = (first_line.lower().startswith("gene")
                     or first_line.lower().startswith("symbol"))
        if not is_header:
            parts = first_line.split(delimiter)
            if len(parts) >= 2:
                try:
                    gene_expr[parts[0].strip()] = float(parts[1].strip())
                except (ValueError, IndexError):
                    pass
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(delimiter)
            if len(parts) < 2:
                continue
            try:
                gene_expr[parts[0].strip()] = float(parts[1].strip())
            except (ValueError, IndexError):
                continue
    if not gene_expr:
        raise ValueError(f"No expression values parsed from {path}")
    return gene_expr
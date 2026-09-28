"""
Expression profile loading, normalization, and canonical-space mapping.

Faithful reproduction of the DRUGSYNC data preprocessing pipeline,
adapted for non-pharmaceutical modifier-induced gene expression profiles (MIGEPs).
"""
from __future__ import annotations

import csv
import os
import statistics
from typing import Any

import numpy as np


# ---------------------------------------------------------------
# Canonical gene space
# ---------------------------------------------------------------
def load_genes_978(path: str) -> list[str]:
    """Load the canonical 978 gene symbols in deterministic order."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Canonical gene list not found at {path}. "
            "Create data/reference/genes_978.txt first."
        )
    with open(path, encoding="utf-8") as f:
        genes = [line.strip() for line in f if line.strip()]
    if len(genes) != 978:
        raise ValueError(
            f"Expected 978 canonical genes, got {len(genes)} from {path}"
        )
    return genes


def load_gene_index(path: str) -> dict[str, int]:
    """Load gene symbol -> index mapping from gene_index.csv."""
    mapping = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["gene_symbol"]] = int(row["index"])
    if len(mapping) != 978:
        raise ValueError(f"Expected 978 gene index entries, got {len(mapping)}")
    return mapping


# ---------------------------------------------------------------
# Expression profile representation
# ---------------------------------------------------------------
class ExpressionProfile:
    """A gene expression profile with full provenance metadata.
    Stores values in the canonical 978-gene space. Missing genes
    are represented as None -- never imputed.
    """

    def __init__(
        self,
        vector: list[float | None],
        gene_symbols: list[str],
        source_dataset: str = "",
        tissue: str = "",
        context: str = "",
        modifier_id: str = "",
        protocol: str = "",
        timepoint_hr: float | None = None,
        replicate_info: dict | None = None,
        n_replicates: int = 1,
        quality_score: float | None = None,
        metadata: dict | None = None,
    ):
        self.vector = list(vector)
        self.gene_symbols = list(gene_symbols)
        self.n_genes = len(vector)
        self.source_dataset = source_dataset
        self.tissue = tissue
        self.context = context
        self.modifier_id = modifier_id
        self.protocol = protocol
        self.timepoint_hr = timepoint_hr
        self.replicate_info = replicate_info or {}
        self.n_replicates = n_replicates
        self.quality_score = quality_score
        self.metadata = metadata or {}

        self.n_present = sum(1 for v in vector if v is not None)
        self.coverage = self.n_present / self.n_genes if self.n_genes > 0 else 0.0

    def to_vector(self) -> np.ndarray:
        """Return dense vector with NaN for missing values."""
        return np.array([float("nan") if v is None else v for v in self.vector])

    def present_mask(self) -> np.ndarray:
        """Return boolean mask of present (non-None) entries."""
        return np.array([v is not None for v in self.vector])

    def summary(self) -> dict[str, Any]:
        return {
            "modifier_id": self.modifier_id,
            "protocol": self.protocol,
            "source_dataset": self.source_dataset,
            "tissue": self.tissue,
            "context": self.context,
            "n_genes": self.n_genes,
            "n_present": self.n_present,
            "coverage": self.coverage,
            "n_replicates": self.n_replicates,
            "quality_score": self.quality_score,
        }

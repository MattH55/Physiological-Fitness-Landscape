"""Modifier data models."""
from __future__ import annotations
import csv
import os
from dataclasses import dataclass, field


@dataclass
class ModifierProfile:
    modifier_id: str
    protocol: str = ""
    biological_context: str = ""
    tissue: str = ""
    study_id: str = ""
    species: str = "human"
    dose: dict = field(default_factory=dict)
    duration_hr: float | None = None
    timepoint_hr: float | None = None
    platform: str = ""
    n_replicates: int = 1
    quality_score: float = 0.0
    migep_vector: list[float | None] = field(default_factory=list)
    gene_symbols: list[str] = field(default_factory=list)
    migep_source: str = "experimental"
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {"modifier_id": self.modifier_id, "protocol": self.protocol,
                "biological_context": self.biological_context, "tissue": self.tissue,
                "study_id": self.study_id, "species": self.species, "dose": self.dose,
                "duration_hr": self.duration_hr, "timepoint_hr": self.timepoint_hr,
                "platform": self.platform, "n_replicates": self.n_replicates,
                "quality_score": self.quality_score,
                "n_genes": len(self.gene_symbols),
                "n_present": sum(1 for v in self.migep_vector if v is not None),
                "migep_source": self.migep_source}


@dataclass
class ModifierPair:
    pair_id: str
    modifier_a: str
    modifier_b: str
    biological_context: str = ""
    study_id: str = ""
    outcome: float = 0.0
    outcome_type: str = "binary"
    metric_name: str = ""
    metric_definition: str = ""
    label: int | None = None
    metadata: dict = field(default_factory=dict)


def load_modifier_pairs(path: str) -> list[ModifierPair]:
    pairs = []
    if not os.path.isfile(path):
        return pairs
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            outcome_type = row.get("outcome_type", "binary")
            outcome = float(row["outcome"]) if row.get("outcome") else 0.0
            label = None
            if outcome_type == "binary":
                label = 1 if outcome > 0.5 else 0
            pairs.append(ModifierPair(
                pair_id=row.get("pair_id", ""), modifier_a=row.get("modifier_a", ""),
                modifier_b=row.get("modifier_b", ""),
                biological_context=row.get("biological_context", ""),
                study_id=row.get("study_id", ""), outcome=outcome,
                outcome_type=outcome_type, metric_name=row.get("metric_name", ""),
                metric_definition=row.get("metric_definition", ""), label=label))
    return pairs
"""
The modifier x drug interaction predictor, per the Signature-transfer
modifier x drug predictor build order's Phase 6: predicts an interaction
score between a non-pharmaceutical intervention's real gene-expression
signature (MIGEP) and a real drug-induced gene-expression signature, in a
given cell line, using the DRUGSYNC-style GCN on the real STRING PPI
graph.

**This model failed Gate 6** (PHASE_6_REPORT.md, data/lincs/phase6_summary.json):
it does not beat Bliss independence under both leave-one-cell-line-out and
leave-one-drug-out cross-validation on the real training corpus (2924
pairs, ALMANAC + DrugComb). Every prediction this module returns carries
`validated: False` and the same warning, and this is not decorative --
callers must treat the number as an unvalidated extrapolation, not a
forecast. Nothing in this module writes to synlethality/seed_data.py;
promoting a prediction to curated evidence is a separate, human decision
this module does not make, and per the build order's own rule it cannot
happen at all while Gate 6 fails.

Real data sources, all loaded lazily and cached:
  - Modifier MIGEPs: data/modifier_signatures/library.json (33 real
    signatures, this project's own Phase 1 modifier library), via
    src.data.loader.signatures_to_migeps (normalized_vector, not the raw
    per-source-scale vector -- see that function's docstring).
  - Drug signatures: data/lincs/curated_drug_signatures.json (LINCS
    Phase 2, preferred when available) and
    data/lincs_phase1_raw/phase1_mcf7_10uM_24h.json (LINCS Phase 1,
    6204 compounds) as fallback.
  - Cell-line baselines: data/depmap/curated_cell_line_expression_l1000landmark.json
    (real DepMap 24Q4 expression, 13 curated lines).
  - Model weights + architecture: models/interaction/phase6_gcn.pt +
    phase6_gcn_manifest.json (scripts/phase6_save_model.py).

CLI:
    python -m src.inference.predict_modifier_drug \\
        --modifier gse48398_mcf7_heat45c30min --drug cisplatin --cell-line MCF7_BREAST
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from src.data.expression import load_genes_978
from src.data.loader import signatures_to_migeps
from src.models.gcn import DrugsyncGCN
from src.ppi.graph import PPIGraph, load_ppi_edges

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENES_PATH = os.path.join(ROOT, "data", "reference", "genes_978.txt")
PPI_PATH = os.path.join(ROOT, "data", "reference", "ppi_edges.csv")
LIBRARY_PATH = os.path.join(ROOT, "data", "modifier_signatures", "library.json")
PHASE1_REF = os.path.join(ROOT, "data", "lincs_phase1_raw", "phase1_mcf7_10uM_24h.json")
PHASE2_REF = os.path.join(ROOT, "data", "lincs", "curated_drug_signatures.json")
BASELINE_PATH = os.path.join(ROOT, "data", "depmap", "curated_cell_line_expression_l1000landmark.json")
MODEL_PATH = os.path.join(ROOT, "models", "interaction", "phase6_gcn.pt")
MANIFEST_PATH = os.path.join(ROOT, "models", "interaction", "phase6_gcn_manifest.json")


def _dense(vec) -> list[float]:
    return [0.0 if v is None else v for v in vec]


class ModifierDrugPredictor:
    """Loads once, predicts many times. Every real source is loaded from
    disk exactly once (lazily, on first use) and cached on the instance."""

    def __init__(self):
        self._gene_symbols = None
        self._adj = None
        self._model = None
        self._manifest = None
        self._migeps_by_id = None
        self._drug_vectors = None
        self._baseline_vectors = None

    # -- lazy real-data loading -------------------------------------
    @property
    def gene_symbols(self):
        if self._gene_symbols is None:
            self._gene_symbols = load_genes_978(GENES_PATH)
        return self._gene_symbols

    @property
    def manifest(self) -> dict:
        if self._manifest is None:
            if not os.path.isfile(MANIFEST_PATH):
                raise FileNotFoundError(
                    f"{MANIFEST_PATH} not found. Run scripts/phase6_save_model.py first."
                )
            with open(MANIFEST_PATH, encoding="utf-8") as fh:
                self._manifest = json.load(fh)
        return self._manifest

    @property
    def model(self) -> DrugsyncGCN:
        if self._model is None:
            if not os.path.isfile(MODEL_PATH):
                raise FileNotFoundError(
                    f"{MODEL_PATH} not found. Run scripts/phase6_save_model.py first."
                )
            arch = self.manifest["architecture"]
            edges = load_ppi_edges(PPI_PATH)
            graph = PPIGraph(gene_symbols=self.gene_symbols, edges=edges,
                              n_genes=978, virtual_node_id=978)
            adj = torch.tensor(graph.adjacency_matrix(), dtype=torch.float32)
            model = DrugsyncGCN(
                n_nodes=arch["n_nodes"], gcn_input_dim=arch["gcn_input_dim"],
                gcn_hidden_dim=arch["gcn_hidden_dim"], gcn_n_layers=arch["gcn_n_layers"],
                fc_hidden_dims=arch["fc_hidden_dims"], readout=arch["readout"],
                baseline_dim=arch["baseline_dim"],
            )
            model.set_adjacency(adj)
            model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
            model.eval()
            self._model = model
        return self._model

    @property
    def migeps_by_id(self) -> dict:
        if self._migeps_by_id is None:
            migeps = signatures_to_migeps(LIBRARY_PATH, GENES_PATH, None)
            self._migeps_by_id = {m.modifier_id: m for m in migeps}
        return self._migeps_by_id

    @property
    def drug_vectors(self) -> dict:
        if self._drug_vectors is None:
            from scripts.build_phase4_corpus import norm_name
            from synlethality.signature_space import normalize_z, to_canonical

            phase1 = json.load(open(PHASE1_REF, encoding="utf-8")) if os.path.isfile(PHASE1_REF) else {}
            phase2 = json.load(open(PHASE2_REF, encoding="utf-8")) if os.path.isfile(PHASE2_REF) else {}
            out = {}
            for source in (phase1, phase2):  # phase2 second so it overwrites phase1 (better QC)
                for name, entry in source.items():
                    projected = to_canonical(entry["gene_zscore"])
                    if projected["coverage"] < 0.7:
                        continue
                    out[norm_name(name)] = {"name": name, "vector": normalize_z(projected["vector"])}
            self._drug_vectors = out
        return self._drug_vectors

    @property
    def baseline_vectors(self) -> dict:
        if self._baseline_vectors is None:
            from synlethality.signature_space import normalize_z, to_canonical

            raw = json.load(open(BASELINE_PATH, encoding="utf-8"))
            out = {}
            for cell_id, gene_dict in raw.items():
                projected = to_canonical(gene_dict)
                if projected["coverage"] < 0.7:
                    continue
                out[cell_id] = normalize_z(projected["vector"])
            self._baseline_vectors = out
        return self._baseline_vectors

    # -- lookup helpers -----------------------------------------------
    def resolve_drug(self, drug_id: str) -> list[float] | None:
        from scripts.build_phase4_corpus import norm_name
        entry = self.drug_vectors.get(norm_name(drug_id))
        return entry["vector"] if entry else None

    def list_modifiers(self) -> list[str]:
        return sorted(self.migeps_by_id)

    def list_drugs(self) -> list[str]:
        return sorted(v["name"] for v in self.drug_vectors.values())

    def list_cell_lines(self) -> list[str]:
        return sorted(self.baseline_vectors)

    # -- prediction -----------------------------------------------------
    def predict(self, modifier_id: str, drug_id: str, cell_line_id: str) -> dict:
        """Real modifier MIGEP x real drug signature x real cell-line
        baseline -> a predicted Bliss-excess score from the Phase 6 GCN.
        Always carries validated=False; see this module's docstring."""
        migep = self.migeps_by_id.get(modifier_id)
        if migep is None:
            raise KeyError(
                f"Unknown modifier_id {modifier_id!r}. Known: {self.list_modifiers()}"
            )
        drug_vec = self.resolve_drug(drug_id)
        if drug_vec is None:
            raise KeyError(
                f"No real signature for drug_id {drug_id!r}. Available: {self.list_drugs()}"
            )
        baseline_vec = self.baseline_vectors.get(cell_line_id)
        if baseline_vec is None:
            raise KeyError(
                f"No real baseline for cell_line_id {cell_line_id!r}. "
                f"Available: {self.list_cell_lines()}"
            )

        mvec = torch.tensor(_dense(migep.vector), dtype=torch.float32)
        dvec = torch.tensor(_dense(drug_vec), dtype=torch.float32)
        base_t = torch.tensor(_dense(baseline_vec), dtype=torch.float32)
        score = self.model.predict_pair(mvec, dvec, baseline=base_t)

        return {
            "modifier_id": modifier_id,
            "drug_id": drug_id,
            "cell_line_id": cell_line_id,
            "predicted_bliss_excess": float(score.item()),
            "validated": self.manifest["validation"]["gate_6_passed"],
            "gate_6": self.manifest["validation"],
            "warning": self.manifest["warning"],
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modifier", required=True, help="A modifier_id from data/modifier_signatures/library.json")
    parser.add_argument("--drug", required=True, help="A drug_id/name with a real LINCS signature")
    parser.add_argument("--cell-line", required=True, dest="cell_line", help="A curated cell_line_id")
    parser.add_argument("--list", action="store_true", help="List available modifiers/drugs/cell lines and exit")
    args = parser.parse_args(argv)

    predictor = ModifierDrugPredictor()
    if args.list:
        print("Modifiers:", predictor.list_modifiers())
        print("Drugs:", predictor.list_drugs())
        print("Cell lines:", predictor.list_cell_lines())
        return 0

    result = predictor.predict(args.modifier, args.drug, args.cell_line)
    print(json.dumps(result, indent=2))
    if not result["validated"]:
        print("\n*** UNVALIDATED: Gate 6 failed. This is an extrapolation, not a forecast. ***",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

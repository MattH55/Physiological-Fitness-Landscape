"""
Inference API for DRUGSYNC-NPxP.
"""
from __future__ import annotations
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.expression import load_genes_978
from src.data.expression_migep import load_expression_profile, map_to_978, robust_z_normalize
from src.data.context import resolve_context
from src.data.loader import load_modifier_profiles
from src.ppi.graph import PPIGraph, load_ppi_edges, build_ppi_graph
from src.models.gcn import DrugsyncGCN, DrugSyncMLP
from src.baselines.baselines import cosine_similarity, correlation


class InteractionPredictor:
    """Predict modifier-modifier interactions."""

    def __init__(self, model=None, graph=None, genes_path=None,
                 profiles_dir=None, device="cpu"):
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.device = device
        self.genes_path = genes_path or os.path.join(self.root, "data", "reference", "genes_978.txt")
        self.gene_symbols = load_genes_978(self.genes_path)
        self.graph = graph
        self.model = model
        self.profiles = {}
        self._loaded_profiles = False

        if profiles_dir:
            self.profiles = load_modifier_profiles(profiles_dir, self.genes_path)
            self._loaded_profiles = True

    def load_model(self, model_path, model_class=DrugsyncGCN, **kwargs):
        state = __import__("torch").load(model_path, map_location=self.device)
        if self.graph is None:
            raise ValueError("Graph must be set before loading a GCN model")
        if model_class == DrugsyncGCN:
            self.model = DrugsyncGCN(
                n_nodes=self.graph.n_nodes, gcn_input_dim=2,
                gcn_hidden_dim=kwargs.get("gcn_hidden_dim", 256),
                gcn_n_layers=kwargs.get("gcn_n_layers", 3),
                fc_hidden_dims=kwargs.get("fc_hidden_dims", [128, 64]),
                readout=kwargs.get("readout", "mean"))
            adj = self.graph.adjacency_matrix()
            self.model.set_adjacency(__import__("torch").tensor(adj, dtype=__import__("torch").float))
        else:
            self.model = model_class(**kwargs)
        self.model.load_state_dict(state)
        self.model.eval()
        self.model.to(self.device)
        return self

    def load_graph(self, ppi_path=None):
        if ppi_path and os.path.isfile(ppi_path):
            edges = load_ppi_edges(ppi_path)
            self.graph = PPIGraph(gene_symbols=self.gene_symbols, edges=edges,
                                  n_genes=978, virtual_node_id=978)
        else:
            self.graph = build_ppi_graph(self.gene_symbols)
        return self

    def predict_from_profiles(self, modifier_a, modifier_b):
        if modifier_a not in self.profiles or modifier_b not in self.profiles:
            raise ValueError(f"Profiles not found for {modifier_a}, {modifier_b}")
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")
        pa = self.profiles[modifier_a]
        pb = self.profiles[modifier_b]
        import torch
        ma = torch.tensor(_dense(pa.migep_vector), dtype=torch.float, device=self.device)
        mb = torch.tensor(_dense(pb.migep_vector), dtype=torch.float, device=self.device)
        with torch.no_grad():
            score = self.model.forward_pair(ma, mb).squeeze(-1)
        return {"modifier_a": modifier_a, "modifier_b": modifier_b,
                "prediction": float(score.cpu().numpy())}

    def predict_raw_migeps(self, migep_a, migep_b):
        """Predict from two raw MIGEP vectors (978-length)."""
        import torch
        ma = torch.tensor(_dense(migep_a), dtype=torch.float, device=self.device)
        mb = torch.tensor(_dense(migep_b), dtype=torch.float, device=self.device)
        with torch.no_grad():
            score = self.model.forward_pair(ma, mb).squeeze(-1)
        return float(score.cpu().numpy())

    def baseline_cosine(self, modifier_a, modifier_b):
        pa = self.profiles.get(modifier_a)
        pb = self.profiles.get(modifier_b)
        if pa is None or pb is None:
            raise ValueError(f"Profiles not found")
        return cosine_similarity(_dense(pa.migep_vector), _dense(pb.migep_vector))

    def baseline_correlation(self, modifier_a, modifier_b):
        pa = self.profiles.get(modifier_a)
        pb = self.profiles.get(modifier_b)
        if pa is None or pb is None:
            raise ValueError(f"Profiles not found")
        return correlation(_dense(pa.migep_vector), _dense(pb.migep_vector))


def _dense(vec):
    arr = np.array([float("nan") if v is None else v for v in vec])
    return np.nan_to_num(arr, nan=0.0)


def load_predictor(model_path=None, ppi_path=None, profiles_dir=None, device="cpu"):
    pred = InteractionPredictor(profiles_dir=profiles_dir, device=device)
    pred.load_graph(ppi_path)
    if model_path:
        pred.load_model(model_path)
    return pred
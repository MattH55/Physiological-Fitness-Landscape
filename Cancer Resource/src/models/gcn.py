"""
DRUGSYNC GCN interaction model.
"""
from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F


class SymmetricGCNConv(nn.Module):
    """GCN layer with symmetric message passing."""

    def __init__(self, in_dim: int, out_dim: int, add_self: bool = True):
        super().__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.add_self = add_self
        self.weight = nn.Parameter(torch.empty(in_dim, out_dim))
        self.bias = nn.Parameter(torch.zeros(out_dim))
        nn.init.xavier_uniform_(self.weight)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """Accepts a single graph's features `x` as [n_nodes, in_dim], or a
        batch [batch, n_nodes, in_dim] -- `adj` (the graph structure) is
        shared across the batch, so a batched call is one einsum instead
        of a Python loop over batch items. Added 2026-09-27: DrugsyncGCN
        originally looped over the batch in Python, calling this once per
        item -- correct, but made real training (thousands of real pairs,
        many cross-validation folds each retraining from scratch)
        impractically slow. Single-graph behaviour is unchanged."""
        n = adj.size(0)
        if self.add_self:
            adj = adj + torch.eye(n, device=adj.device)
        deg = adj.sum(dim=1).clamp(min=1.0)
        deg_inv_sqrt = deg.pow(-0.5)
        norm_adj = deg_inv_sqrt.unsqueeze(1) * adj * deg_inv_sqrt.unsqueeze(0)
        if x.dim() == 2:
            h = torch.mm(norm_adj, x)
            return torch.mm(h, self.weight) + self.bias
        if x.dim() == 3:
            h = torch.einsum("nm,bmc->bnc", norm_adj, x)
            return torch.einsum("bnc,cd->bnd", h, self.weight) + self.bias
        raise ValueError(f"Expected x with 2 or 3 dims, got {x.dim()}")


class DrugsyncGCN(nn.Module):
    """Full DRUGSYNC-style GCN interaction model."""

    def __init__(self, n_nodes, gcn_input_dim=2, gcn_hidden_dim=256,
                 gcn_n_layers=3, gcn_dropout=0.2, fc_input_dim=None,
                 fc_hidden_dims=None, fc_dropout=0.3, output_dim=1,
                 readout="mean", adj=None, baseline_dim=None):
        """`baseline_dim`, if given, is the real cell-line baseline
        expression vector's length (978, same canonical space as the
        node features). It is NOT placed on graph nodes -- doing that
        would need a third node channel the spec's DRUGSYNC-without-DTI
        node feature [MIGEP_A, MIGEP_B] deliberately doesn't have, and
        the spec explicitly forbids manufacturing dimensions to fit.
        Instead it is linearly projected and concatenated to the pooled
        graph representation, before the FC head -- real cell-line
        context, added without touching the graph's channel semantics.
        Added 2026-09-27 for the drug/modifier x cell-line interaction
        task, where cell-line identity is known to matter and dropping it
        entirely would be a real, avoidable information loss."""
        super().__init__()
        self.n_nodes = n_nodes
        self.gcn_input_dim = gcn_input_dim
        self.gcn_hidden_dim = gcn_hidden_dim
        self.gcn_n_layers = gcn_n_layers
        self.gcn_dropout = gcn_dropout
        self.readout = readout
        self.baseline_dim = baseline_dim
        if fc_input_dim is None:
            fc_input_dim = gcn_hidden_dim
        if fc_hidden_dims is None:
            fc_hidden_dims = [128, 64]

        self.gcn_layers = nn.ModuleList()
        prev = gcn_input_dim
        for _ in range(gcn_n_layers):
            self.gcn_layers.append(SymmetricGCNConv(prev, gcn_hidden_dim))
            prev = gcn_hidden_dim

        self.baseline_proj = None
        if baseline_dim:
            self.baseline_proj = nn.Linear(baseline_dim, 32)
            fc_input_dim = fc_input_dim + 32

        self.fc_layers = nn.ModuleList()
        prev_dim = fc_input_dim
        for hd in fc_hidden_dims:
            self.fc_layers.append(nn.Linear(prev_dim, hd))
            prev_dim = hd
        self.output_layer = nn.Linear(prev_dim, output_dim)
        self.dropout_gcn = nn.Dropout(gcn_dropout)
        self.dropout_fc = nn.Dropout(fc_dropout)
        self.register_buffer("adj", None)
        if adj is not None:
            self.adj = adj

    def set_adjacency(self, adj):
        if adj.ndim != 2 or adj.size(0) != adj.size(1):
            raise ValueError(f"Adjacency must be square; got {tuple(adj.shape)}")
        self.register_buffer("adj", adj)

    def forward(self, x, baseline=None):
        if self.adj is None:
            raise RuntimeError("Adjacency matrix not set")
        h = x
        for i, layer in enumerate(self.gcn_layers):
            h = layer(h, self.adj)
            if i < self.gcn_n_layers - 1:
                h = F.relu(h)
                h = self.dropout_gcn(h)
        if self.readout == "mean":
            pooled = h.mean(dim=1)
        elif self.readout == "max":
            pooled = h.max(dim=1).values
        elif self.readout == "sum":
            pooled = h.sum(dim=1)
        elif self.readout == "virtual":
            pooled = h[:, self.n_nodes - 1, :]
        else:
            raise ValueError(f"Unknown readout: {self.readout}")
        if self.baseline_proj is not None:
            if baseline is None:
                raise ValueError("Model configured with baseline_dim but no baseline given")
            pooled = torch.cat([pooled, F.relu(self.baseline_proj(baseline))], dim=-1)
        elif baseline is not None:
            raise ValueError("baseline given but model has no baseline_dim configured")
        for fc in self.fc_layers:
            pooled = F.relu(fc(pooled))
            pooled = self.dropout_fc(pooled)
        return self.output_layer(pooled)

    def forward_pair(self, migep_a, migep_b, baseline=None):
        if migep_a.ndim == 1:
            features = torch.stack([migep_a, migep_b], dim=-1)
            virtual = torch.zeros(1, 2, device=migep_a.device)
            features = torch.cat([features, virtual], dim=0).unsqueeze(0)
            if baseline is not None and baseline.ndim == 1:
                baseline = baseline.unsqueeze(0)
        else:
            features = torch.stack([migep_a, migep_b], dim=-1)
            batch_size = features.size(0)
            virtual = torch.zeros(batch_size, 1, 2, device=migep_a.device)
            features = torch.cat([features, virtual], dim=1)
        return self.forward(features, baseline=baseline)

    def predict_pair(self, migep_a, migep_b, baseline=None):
        if not isinstance(migep_a, torch.Tensor):
            migep_a = torch.tensor(migep_a, dtype=torch.float)
        if not isinstance(migep_b, torch.Tensor):
            migep_b = torch.tensor(migep_b, dtype=torch.float)
        if baseline is not None and not isinstance(baseline, torch.Tensor):
            baseline = torch.tensor(baseline, dtype=torch.float)
        self.eval()
        with torch.no_grad():
            return self.forward_pair(migep_a, migep_b, baseline=baseline).squeeze(-1)


class DrugSyncMLP(nn.Module):
    """Baseline MLP (no PPI graph)."""

    def __init__(self, n_genes, hidden_dims=None, output_dim=1, dropout=0.3):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [256, 128]
        dims = [2 * n_genes] + hidden_dims
        self.fc_layers = nn.ModuleList()
        for i in range(len(dims) - 1):
            self.fc_layers.append(nn.Linear(dims[i], dims[i + 1]))
        self.output = nn.Linear(dims[-1], output_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, migep_a, migep_b):
        if not isinstance(migep_a, torch.Tensor):
            migep_a = torch.tensor(migep_a, dtype=torch.float)
        if not isinstance(migep_b, torch.Tensor):
            migep_b = torch.tensor(migep_b, dtype=torch.float)
        if migep_a.ndim == 1:
            x = torch.cat([migep_a, migep_b], dim=0).unsqueeze(0)
        else:
            x = torch.cat([migep_a, migep_b], dim=-1)
        for fc in self.fc_layers:
            x = F.relu(fc(x))
            x = self.dropout(x)
        return self.output(x)
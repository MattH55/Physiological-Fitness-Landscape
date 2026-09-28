"""
Tests for DRUGSYNC-NPxP core modules.
"""
from __future__ import annotations
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import numpy as np

from src.data.expression import load_genes_978, ExpressionProfile
from src.data.expression_migep import MIGEP, robust_z_normalize, load_expression_profile
from src.data.context import resolve_context
from src.data.modifier import ModifierProfile, ModifierPair, load_modifier_pairs
from src.ppi.graph import PPIGraph, build_ppi_graph, load_ppi_edges, save_ppi_edges
from src.qc.quality import calculate_replicate_pcc, qc_replicates, aggregate_replicates
from src.evaluation.metrics import roc_auc, balanced_accuracy, pearson_correlation, rmse, r_squared
from src.evaluation.validation import leave_pairs_out_split, leave_modifiers_out_split
from src.baselines.baselines import cosine_similarity, correlation
from src.models.gcn import SymmetricGCNConv, DrugsyncGCN, DrugSyncMLP

import torch


class TestExpression:
    def test_load_genes_978(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "reference", "genes_978.txt")
        if os.path.isfile(path):
            genes = load_genes_978(path)
            assert len(genes) == 978
            assert isinstance(genes[0], str)
            assert len(set(genes)) == 978
        else:
            pytest.skip("Reference file not available")

    def test_expression_profile(self):
        vec = [1.0, None, 3.0]
        ep = ExpressionProfile(vector=vec, gene_symbols=["A", "B", "C"])
        assert ep.n_genes == 3
        assert ep.n_present == 2
        assert ep.coverage == 2 / 3
        np.testing.assert_array_equal(ep.present_mask(), [True, False, True])
        assert np.isnan(ep.to_vector()[1])

    def test_migep_creation(self):
        treated = [10.0, 20.0, None]
        control = [5.0, None, 10.0]
        migep = MIGEP(treated_values=treated, control_values=control,
                      gene_symbols=["A", "B", "C"], modifier_id="test")
        assert migep.modifier_id == "test"
        assert migep.vector[0] == 5.0
        assert migep.vector[1] is None
        assert migep.vector[2] is None


class TestNormalization:
    def test_robust_z_normalize(self):
        vec = [10.0, 12.0, 9.0, 11.0, None, 13.0]
        result = robust_z_normalize(vec)
        assert len(result) == 6
        assert result[4] is None
        assert abs(np.median([r for r in result if r is not None])) < 1e-6

    def test_robust_z_normalize_too_few(self):
        with pytest.raises(ValueError):
            robust_z_normalize([1.0])


class TestContext:
    def test_resolve_context(self):
        assert resolve_context("skeletal muscle") == "skeletal_muscle"
        assert resolve_context("MCF-7") == "mcf7"
        assert resolve_context("UnknownTissue") == "UnknownTissue"

class TestModifier:
    def test_modifier_profile_to_dict(self):
        mp = ModifierProfile(modifier_id="test", protocol="exercise")
        d = mp.to_dict()
        assert d["modifier_id"] == "test"
        assert d["protocol"] == "exercise"

    def test_load_modifier_pairs_nonexistent(self):
        pairs = load_modifier_pairs("nonexistent.csv")
        assert pairs == []


class TestLoader:
    """src.data.loader against this project's real Phase 1 modifier
    signature library (33 real signatures, synlethality/). Skips if that
    real data file isn't present rather than fabricating a fixture for it."""

    LIBRARY = os.path.join(os.path.dirname(__file__), "..", "data",
                            "modifier_signatures", "library.json")
    GENES = os.path.join(os.path.dirname(__file__), "..", "data", "reference", "genes_978.txt")

    def test_signatures_to_migeps_real_library(self):
        if not (os.path.isfile(self.LIBRARY) and os.path.isfile(self.GENES)):
            pytest.skip("Real Phase 1 signature library or gene list not available")
        from src.data.loader import signatures_to_migeps

        migeps = signatures_to_migeps(self.LIBRARY, self.GENES, None)
        assert len(migeps) == 33
        for m in migeps:
            assert len(m.vector) == 978
            assert m.biological_context  # never empty/unresolved

    def test_signatures_to_migeps_uses_normalized_not_raw_vector(self):
        """2026-09-27 fix, real regression case: an earlier version used
        the library's raw `vector` (heterogeneous native scale per source)
        instead of `normalized_vector` (Phase 0's harmonized robust
        z-score) -- silently reintroducing the scale mismatch across
        microarray/LINCS/DepMap sources that Phase 0 exists to remove."""
        if not (os.path.isfile(self.LIBRARY) and os.path.isfile(self.GENES)):
            pytest.skip("Real Phase 1 signature library or gene list not available")
        import json

        from src.data.loader import signatures_to_migeps

        with open(self.LIBRARY, encoding="utf-8") as f:
            library = json.load(f)
        first = next(s for s in library["signatures"] if s["vector"] != s["normalized_vector"])
        migeps = signatures_to_migeps(self.LIBRARY, self.GENES, None)
        migep = next(m for m in migeps if m.modifier_id == first["signature_id"])
        present_idx = next(i for i, v in enumerate(first["normalized_vector"]) if v is not None)
        assert migep.vector[present_idx] == pytest.approx(first["normalized_vector"][present_idx])


class TestPPI:
    def test_ppi_graph_creation(self):
        genes = [f"GENE{i}" for i in range(978)]
        edges = [(0, 1, 0.8), (1, 2, 0.9)]
        graph = PPIGraph(gene_symbols=genes, edges=edges, n_genes=978, virtual_node_id=978)
        assert graph.n_nodes == 979
        A = graph.adjacency_matrix()
        assert A.shape == (979, 979)
        assert A[0, 1] == 0.8

    def test_build_demo_graph(self):
        genes = [f"G{i}" for i in range(978)]
        graph = build_ppi_graph(genes)
        assert len(graph.edges) >= 7800
        assert graph.n_nodes == 979

    def test_ppi_edge_io(self):
        edges = [(0, 1, 0.8), (2, 3, 0.9)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            path = f.name
        try:
            save_ppi_edges(edges, path)
            loaded = load_ppi_edges(path)
            assert loaded == edges
        finally:
            os.unlink(path)

    def test_build_ppi_graph_requires_protein_info_with_string_data(self):
        """2026-09-27 fix: passing a real STRING protein.links file without
        its companion protein.info file must raise, not silently produce a
        zero-edge graph (protein.links uses Ensembl protein IDs, which
        never match gene symbols on their own)."""
        genes = [f"GENE{i}" for i in range(978)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("protein1 protein2 combined_score\n")
            links_path = f.name
        try:
            with pytest.raises(FileNotFoundError):
                build_ppi_graph(genes, string_data_path=links_path, protein_info_path=None)
        finally:
            os.unlink(links_path)

    def test_build_ppi_graph_resolves_ensp_ids_to_caller_gene_order(self):
        """2026-09-27 fix, real regression case: a real STRING links line
        (Ensembl protein IDs) must resolve through protein.info to the
        right gene symbols, and the resulting edge indices must match the
        *caller's* gene_symbols order -- not an internally re-sorted one.
        Uses a gene order that is deliberately NOT alphabetical (mirrors
        this project's real Entrez-sorted canonical order) to catch the
        original re-sort bug."""
        genes = ["ZZZ_GENE", "AAA_GENE", "MMM_GENE"] + [f"GENE{i}" for i in range(975)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("protein1 protein2 combined_score\n")
            f.write("9606.ENSP_A 9606.ENSP_B 900\n")  # AAA_GENE -- MMM_GENE
            links_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("#string_protein_id\tpreferred_name\n")
            f.write("9606.ENSP_A\tAAA_GENE\n")
            f.write("9606.ENSP_B\tMMM_GENE\n")
            info_path = f.name
        try:
            graph = build_ppi_graph(
                genes, string_data_path=links_path, protein_info_path=info_path,
                threshold=700.0, add_virtual_node=False,
            )
            assert len(graph.edges) == 1
            src, tgt, weight = graph.edges[0]
            # AAA_GENE is index 1, MMM_GENE is index 2 in the caller's real order.
            assert {src, tgt} == {1, 2}
            assert weight == pytest.approx(0.9)
        finally:
            os.unlink(links_path)
            os.unlink(info_path)


class TestMetrics:
    def test_roc_auc_perfect(self):
        y_true = [0, 0, 1, 1]
        y_score = [0.1, 0.2, 0.9, 0.8]
        assert roc_auc(y_true, y_score) >= 0.5

    def test_pearson_perfect(self):
        assert pearson_correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0, abs=1e-6)

    def test_rmse(self):
        assert rmse([0, 0], [1, 1]) == pytest.approx(1.0)


class TestValidationSplits:
    def test_leave_pairs_out(self):
        samples = [{"modifier_a": "a", "modifier_b": "b"}] * 10
        folds = leave_pairs_out_split(samples, n_folds=5)
        assert len(folds) == 5
        all_test = set()
        for _, test in folds:
            all_test.update(test)
        assert len(all_test) == 10

    def test_leave_modifiers_out(self):
        samples = [
            {"modifier_a": "A", "modifier_b": "B"},
            {"modifier_a": "C", "modifier_b": "D"},
            {"modifier_a": "E", "modifier_b": "F"},
            {"modifier_a": "G", "modifier_b": "H"},
            {"modifier_a": "I", "modifier_b": "J"},
            {"modifier_a": "K", "modifier_b": "L"},
        ]
        folds = leave_modifiers_out_split(samples, n_folds=2, random_seed=42)
        for train, test in folds:
            train_mods = set()
            for j in train:
                train_mods.add(samples[j]["modifier_a"])
                train_mods.add(samples[j]["modifier_b"])
            test_mods = set()
            for j in test:
                test_mods.add(samples[j]["modifier_a"])
                test_mods.add(samples[j]["modifier_b"])
            assert not (train_mods & test_mods)


class TestBaselines:
    def test_cosine_similarity_identical(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_correlation_identical(self):
        v = [1.0, 2.0, 3.0]
        assert correlation(v, v) == pytest.approx(1.0, abs=1e-6)


class TestModels:
    def test_symmetric_gcn_conv(self):
        conv = SymmetricGCNConv(4, 8)
        x = torch.randn(3, 4)
        adj = torch.eye(3)
        out = conv(x, adj)
        assert out.shape == (3, 8)

    def test_drugsync_gcn_init(self):
        model = DrugsyncGCN(n_nodes=979, gcn_input_dim=2, gcn_hidden_dim=16,
                            gcn_n_layers=2, fc_hidden_dims=[8, 4])
        assert model.n_nodes == 979

    def test_drugsync_mlp_init(self):
        model = DrugSyncMLP(n_genes=978, hidden_dims=[16, 8])
        x1 = torch.randn(978)
        x2 = torch.randn(978)
        out = model(x1, x2)
        assert out.shape == (1, 1)


class TestIO:
    def test_load_expression_profile(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
            f.write("gene\texpression\nBRCA1\t10.5\nTP53\t8.2\n")
            path = f.name
        try:
            expr = load_expression_profile(path)
            assert expr == {"BRCA1": 10.5, "TP53": 8.2}
        finally:
            os.unlink(path)

class TestQC:
    def test_replicate_pcc_identical(self):
        v1 = [1.0, 2.0, 3.0, 4.0]
        v2 = [1.0, 2.0, 3.0, 4.0]
        assert calculate_replicate_pcc([v1, v2]) == pytest.approx(1.0, abs=1e-6)

    def test_qc_replicates_insufficient(self):
        result = qc_replicates([[1.0]], min_replicates=2)
        assert not result["pass"]
        assert "insufficient_replicates" in result["flags"]

    def test_aggregate_replicates(self):
        v1 = [1.0, 2.0]
        v2 = [3.0, 4.0]
        avg = aggregate_replicates([v1, v2])
        assert avg == [2.0, 3.0]
"""
Test suite for Physiological Fitness Landscape:
1. Interventions catalog (50 biomarkers, favorable/unfavorable, evidence tiers, citations)
2. Disease signature engine (Type A-E alterations, Jaccard/Cosine similarity, top similar diseases)
3. Literature/citation audit (PMID validation, HR sanity checks, source coverage, pass/fail gate)
4. Continuous spline & target discrepancy report (validation against meta-analyses, outlier detection)
5. REST API endpoints for interventions, disease signatures, and audit reports
"""

import unittest
import sqlite3
import os
from backend.interventions_catalog import INTERVENTIONS_CATALOG, get_interventions_for_biomarker, get_all_interventions_summary
from backend.disease_signature_engine import build_disease_signatures, compute_disease_similarity, find_top_similar_diseases, compute_global_disease_similarity_matrix
from backend.citation_audit import audit_citations, parse_pmid_from_text, parse_doi_from_text
from backend.discrepancy_report import run_spline_discrepancy_audit, CONSENSUS_REFERENCES
from backend.models import get_engine, init_db
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from backend.main import app

class TestInterventionsCatalog(unittest.TestCase):
    """Test suite for biomarker interventions catalog."""

    def test_catalog_has_all_50_biomarkers(self):
        """Interventions catalog must contain entries for all 50 primary biomarkers."""
        self.assertGreaterEqual(len(INTERVENTIONS_CATALOG), 50, f"Expected >= 50 biomarkers, found {len(INTERVENTIONS_CATALOG)}")

    def test_interventions_have_favorable_and_unfavorable(self):
        """Each biomarker must have both favorable and unfavorable lists."""
        for name, data in INTERVENTIONS_CATALOG.items():
            self.assertIn("favorable", data, f"Missing 'favorable' in {name}")
            self.assertIn("unfavorable", data, f"Missing 'unfavorable' in {name}")
            self.assertIn("optimal_range", data, f"Missing 'optimal_range' in {name}")
            self.assertIn("clinical_context", data, f"Missing 'clinical_context' in {name}")
            self.assertGreater(len(data["favorable"]), 0, f"No favorable interventions for {name}")
            self.assertGreater(len(data["unfavorable"]), 0, f"No unfavorable interventions for {name}")

    def test_intervention_item_schema(self):
        """Verify each intervention has required fields: name, category, magnitude, evidence_strength, citation, pmid."""
        required_fields = ["name", "category", "magnitude", "evidence_strength", "citation"]
        valid_categories = {"Lifestyle", "Pharmacologic", "Nutraceutical", "Diet", "Exercise", "Sleep", "Behavioral", "Environmental", "Clinical", "Physiological"}
        valid_evidence = {"RCT", "Meta-analysis", "Prospective Cohort", "Systematic Review", "Mechanistic", "Clinical Guideline"}

        total_interventions = 0
        pmid_count = 0

        for name, data in INTERVENTIONS_CATALOG.items():
            for polarity in ["favorable", "unfavorable"]:
                for item in data[polarity]:
                    total_interventions += 1
                    for field in required_fields:
                        self.assertIn(field, item, f"Missing field '{field}' in {name} -> {polarity} -> {item.get('name')}")
                    self.assertIn(item["category"], valid_categories, f"Invalid category '{item['category']}' in {name}")
                    self.assertIn(item["evidence_strength"], valid_evidence, f"Invalid evidence_strength '{item['evidence_strength']}' in {name}")
                    if item.get("pmid"):
                        pmid_count += 1
                        self.assertTrue(item["pmid"].isdigit() or item["pmid"].startswith("PMC"), f"Invalid PMID format '{item['pmid']}' in {name}")

        self.assertGreater(total_interventions, 200, f"Expected >200 total interventions, got {total_interventions}")
        self.assertGreater(pmid_count, 150, f"Expected >150 interventions with verified PMIDs, got {pmid_count}")

    def test_interventions_summary_helper(self):
        """Test summary helper function."""
        summary = get_all_interventions_summary()
        self.assertGreaterEqual(summary["total_biomarkers"], 50)
        self.assertGreaterEqual(summary["total_interventions"], 200)
        self.assertIn("Lifestyle", summary["by_category"])
        self.assertIn("Pharmacologic", summary["by_category"])


class TestDiseaseSignatureEngine(unittest.TestCase):
    """Test suite for disease signatures and multi-panel similarity."""

    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine("sqlite:///data/mortality_biomarkers.db")
        init_db(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.session = cls.Session()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def test_build_disease_signatures(self):
        """Build signatures from DB and verify structure."""
        signatures = build_disease_signatures(self.session)
        self.assertIsInstance(signatures, dict)
        self.assertGreater(len(signatures), 0, "Expected at least 1 disease signature")

        for disease_id, sig in signatures.items():
            self.assertIn("disease_name", sig)
            self.assertIn("category", sig)
            self.assertIn("biomarker_panel", sig)
            self.assertIn("alterations_count", sig)
            self.assertIn("type_counts", sig)

    def test_disease_similarity_computation(self):
        """Test similarity score computation between two signatures."""
        sig_a = {
            "disease_id": 1,
            "disease_name": "Type 2 Diabetes",
            "biomarker_panel": {
                "fasting_glucose": {"direction": "elevated", "evidence": "High"},
                "hba1c": {"direction": "elevated", "evidence": "High"},
                "triglycerides": {"direction": "elevated", "evidence": "Moderate"},
                "hdl_cholesterol": {"direction": "reduced", "evidence": "Moderate"}
            },
            "type_a_molecular": ["IRS-1 phosphorylation", "GLUT4 downregulation"],
            "type_b_clinical": ["HbA1c > 6.5%", "Fasting glucose > 126 mg/dL"],
            "type_c_scales": ["FINDRISC > 15"],
            "type_d_pathology": ["Islet amyloid polypeptide deposition"],
            "type_e_functional": ["Impaired oral glucose tolerance"]
        }

        sig_b = {
            "disease_id": 2,
            "disease_name": "Metabolic Syndrome",
            "biomarker_panel": {
                "fasting_glucose": {"direction": "elevated", "evidence": "High"},
                "triglycerides": {"direction": "elevated", "evidence": "High"},
                "hdl_cholesterol": {"direction": "reduced", "evidence": "High"},
                "systolic_bp": {"direction": "elevated", "evidence": "High"}
            },
            "type_a_molecular": ["GLUT4 downregulation", "Adiponectin reduction"],
            "type_b_clinical": ["Triglycerides >= 150 mg/dL", "HDL < 40 mg/dL"],
            "type_c_scales": [],
            "type_d_pathology": ["Hepatic steatosis"],
            "type_e_functional": ["Insulin resistance (HOMA-IR > 2.5)"]
        }

        sim = compute_disease_similarity(sig_a, sig_b)
        self.assertIn("composite_similarity", sim)
        self.assertIn("biomarker_jaccard", sim)
        self.assertIn("directional_cosine", sim)
        self.assertIn("shared_biomarkers", sim)
        self.assertGreater(sim["composite_similarity"], 0.3, "Metabolic Syndrome and T2D should have substantial composite similarity")
        self.assertIn("fasting_glucose", sim["shared_biomarkers"])

    def test_find_top_similar_diseases(self):
        """Test finding top similar diseases across global DB."""
        results = find_top_similar_diseases(1, self.session, top_n=5)
        self.assertIsInstance(results, list)

    def test_global_similarity_matrix(self):
        """Test matrix generation."""
        matrix_data = compute_global_disease_similarity_matrix(self.session)
        self.assertIn("diseases", matrix_data)
        self.assertIn("similarity_matrix", matrix_data)
        self.assertIn("top_disease_clusters", matrix_data)


class TestCitationAudit(unittest.TestCase):
    """Test suite for literature citation auditing and backfill validation."""

    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine("sqlite:///data/mortality_biomarkers.db")
        cls.Session = sessionmaker(bind=cls.engine)
        cls.session = cls.Session()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def test_pmid_and_doi_regex_parser(self):
        """Test extraction of PMIDs and DOIs from free text citations."""
        text1 = "Lancet 2018; 392: 1015-1035. PMID: 30139563. doi: 10.1016/S0140-6736(18)31310-2"
        self.assertEqual(parse_pmid_from_text(text1), "30139563")
        self.assertEqual(parse_doi_from_text(text1), "10.1016/S0140-6736(18)31310-2")

        text2 = "Arch Gerontol Geriatr Plus. 2024; PMID: 38456123."
        self.assertEqual(parse_pmid_from_text(text2), "38456123")

        text3 = "No pmid here"
        self.assertIsNone(parse_pmid_from_text(text3))

    def test_run_citation_audit(self):
        """Audit citations in DB and verify summary metrics and pass/fail gate."""
        report = audit_citations(self.session)
        self.assertIn("summary", report)
        self.assertIn("flagged_records", report)
        self.assertIn("gate_status", report)

        summary = report["summary"]
        self.assertGreaterEqual(summary["total_sources_audited"], 10)
        self.assertIn(report["gate_status"], ["PASS", "FAIL"])


class TestDiscrepancyReport(unittest.TestCase):
    """Test continuous biomarker spline validation against meta-analyses & consensus."""

    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine("sqlite:///data/mortality_biomarkers.db")
        cls.Session = sessionmaker(bind=cls.engine)
        cls.session = cls.Session()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def test_consensus_references_structure(self):
        """Verify consensus targets dictionary covers essential biomarkers."""
        self.assertGreaterEqual(len(CONSENSUS_REFERENCES), 30)
        for name, meta in CONSENSUS_REFERENCES.items():
            self.assertIn("expected_optimal", meta)
            self.assertIn("tolerance_pct", meta)

    def test_run_spline_discrepancy_audit(self):
        """Run discrepancy audit against DB models."""
        audit_res = run_spline_discrepancy_audit(self.session)
        self.assertIn("total_biomarkers_audited", audit_res)
        self.assertIn("concordance_rate_pct", audit_res)
        self.assertIn("gate_status", audit_res)
        self.assertGreaterEqual(audit_res["concordance_rate_pct"], 70.0, "At least 70% of biomarkers should be concordant")


class TestAPIEndpoints(unittest.TestCase):
    """Test FastAPI REST endpoints for new features."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_api_interventions_catalog(self):
        """Test /api/interventions endpoint."""
        res = self.client.get("/api/interventions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("biomarkers", data)
        self.assertIn("summary", data)
        self.assertGreaterEqual(len(data["biomarkers"]), 50)

    def test_api_biomarker_interventions(self):
        """Test /api/interventions/{name} endpoint."""
        res = self.client.get("/api/interventions/fasting_glucose")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["biomarker_name"], "fasting_glucose")
        self.assertIn("favorable", data)
        self.assertIn("unfavorable", data)

    def test_api_disease_signatures(self):
        """Test /api/diseases/signatures endpoint."""
        res = self.client.get("/api/diseases/signatures")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_diseases", data)
        self.assertIn("signatures", data)

    def test_api_disease_similarity(self):
        """Test /api/diseases/{id_or_slug}/similar endpoint."""
        res = self.client.get("/api/diseases/1/similar")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("target_disease", data)
        self.assertIn("similar_diseases", data)

    def test_api_citation_audit(self):
        """Test /api/audit/citations endpoint."""
        res = self.client.get("/api/audit/citations")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("gate_status", data)

    def test_api_discrepancy_report(self):
        """Test /api/audit/discrepancies endpoint."""
        res = self.client.get("/api/audit/discrepancies")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("discrepancies", data)


if __name__ == "__main__":
    unittest.main()

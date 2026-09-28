"""
Interventions Landscape: CT.gov trial discovery pipeline.

Modules:
  - biomarker_ontology: canonical names, aliases, synonyms per biomarker
  - clinicaltrials_client: thin CT.gov API v2 client
  - ctgov_sweep: high-recall multi-search sweep
  - relevance_scoring: score and tier candidates
  - results_extraction: extract posted results from high-tier trials
  - publication_linkage: link trials to publications via Europe PMC
  - run_ctgov_discovery: main pipeline orchestrator
"""
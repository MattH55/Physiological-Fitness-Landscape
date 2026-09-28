"""
Main pipeline orchestrator: run the full CT.gov discovery pipeline
for one or more biomarkers.

Usage:
  python backend/interventions_landscape/run_ctgov_discovery.py --biomarkers high_sensitivity_crp hdl_cholesterol
  python backend/interventions_landscape/run_ctgov_discovery.py --biomarkers all
  python backend/interventions_landscape/run_ctgov_discovery.py --biomarkers high_sensitivity_crp --skip-expansion --skip-publications

Pipeline steps per biomarker:
  1. Run high-recall sweep (A-G searches)
  2. Run intervention expansion (H searches) [optional]
  3. Score and tier all candidates
  4. Extract results for high-tier trials [optional]
  5. Link publications via Europe PMC [optional]
  6. Save all outputs to JSON
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import List, Optional

# Add backend to path for direct script execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .biomarker_ontology import all_biomarker_ids, get_ontology
from .ctgov_sweep import (
    run_sweep,
    run_intervention_expansion,
    run_results_sweep,
    save_sweep_result,
)
from .relevance_scoring import score_sweep_result, tier_distribution
from .results_extraction import extract_high_tier_results, save_results
from .publication_linkage import link_all_publications, save_publication_links

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ctgov_discovery")

DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "ctgov_discovery"
)


def run_pipeline(
    biomarker_id: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    page_size: int = 50,
    max_pages: int = 3,
    pause_seconds: float = 0.3,
    skip_expansion: bool = False,
    skip_results: bool = False,
    skip_publications: bool = False,
    max_results_trials: int = 50,
    max_publication_trials: int = 30,
) -> dict:
    """
    Run the full discovery pipeline for one biomarker.
    Returns a summary dict.
    """
    logger.info(f"{'='*60}")
    logger.info(f"Starting pipeline for: {biomarker_id}")
    logger.info(f"{'='*60}")

    ontology = get_ontology(biomarker_id)
    biomarker_dir = os.path.join(output_dir, biomarker_id)
    os.makedirs(biomarker_dir, exist_ok=True)

    summary = {
        "biomarker_id": biomarker_id,
        "canonical_name": ontology.canonical_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Step 1: High-recall sweep
    logger.info(f"\n[Step 1] Running high-recall sweep...")
    sweep = run_sweep(
        biomarker_id,
        page_size=page_size,
        max_pages=max_pages,
        pause_seconds=pause_seconds,
    )
    summary["sweep"] = sweep.summary()
    sweep_path = save_sweep_result(sweep, output_dir)
    summary["sweep_file"] = sweep_path

    # Step 2: Intervention expansion
    if not skip_expansion:
        logger.info(f"\n[Step 2] Running intervention expansion...")
        sweep = run_intervention_expansion(
            sweep,
            page_size=page_size,
            max_pages=2,
            pause_seconds=pause_seconds,
            max_interventions=20,
        )
        summary["sweep_after_expansion"] = sweep.summary()
        sweep_path = save_sweep_result(sweep, output_dir)
        summary["sweep_file"] = sweep_path
    else:
        logger.info(f"\n[Step 2] Skipping intervention expansion")

    # Step 3: Score and tier
    logger.info(f"\n[Step 3] Scoring and tiering candidates...")
    candidates = score_sweep_result(sweep)
    tier_dist = tier_distribution(candidates)
    summary["tier_distribution"] = tier_dist
    logger.info(f"  Tier distribution: {tier_dist}")

    # Save scored candidates
    candidates_path = os.path.join(
        biomarker_dir, f"candidates_{time.strftime('%Y-%m-%d')}.json"
    )
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "biomarker_id": biomarker_id,
                "total_candidates": len(candidates),
                "tier_distribution": tier_dist,
                "candidates": [c.to_dict() for c in candidates],
            },
            f,
            indent=2,
            default=str,
        )
    summary["candidates_file"] = candidates_path
    logger.info(f"  Saved {len(candidates)} candidates to {candidates_path}")

    # Step 4: Extract results
    if not skip_results:
        logger.info(f"\n[Step 4] Extracting results for high-tier trials...")
        results = extract_high_tier_results(
            candidates,
            max_trials=max_results_trials,
            pause_seconds=pause_seconds,
        )
        results_path = save_results(results, biomarker_id, output_dir)
        summary["results_file"] = results_path
        summary["results_extracted"] = len(results)
        logger.info(f"  Extracted results for {len(results)} trials")
    else:
        logger.info(f"\n[Step 4] Skipping results extraction")

    # Step 5: Link publications
    if not skip_publications:
        logger.info(f"\n[Step 5] Linking publications via Europe PMC...")
        pub_links = link_all_publications(
            candidates,
            biomarker_term=ontology.canonical_name,
            max_trials=max_publication_trials,
            pause_seconds=pause_seconds,
        )
        pub_path = save_publication_links(pub_links, biomarker_id, output_dir)
        summary["publications_file"] = pub_path
        summary["publications_linked"] = len(pub_links)
        logger.info(f"  Linked {len(pub_links)} publications")
    else:
        logger.info(f"\n[Step 5] Skipping publication linkage")

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Pipeline complete for: {biomarker_id}")
    logger.info(f"  Total trials: {summary['sweep'].get('unique_trials', 0)}")
    logger.info(f"  Tier distribution: {tier_dist}")
    if "results_extracted" in summary:
        logger.info(f"  Results extracted: {summary['results_extracted']}")
    if "publications_linked" in summary:
        logger.info(f"  Publications linked: {summary['publications_linked']}")
    logger.info(f"{'='*60}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="CT.gov trial discovery pipeline"
    )
    parser.add_argument(
        "--biomarkers",
        nargs="+",
        required=True,
        help="Biomarker IDs to process (or 'all' for all biomarkers)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for JSON files",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=50,
        help="Page size for CT.gov API (default: 50)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Max pages per search (default: 3)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.3,
        help="Pause between API calls in seconds (default: 0.3)",
    )
    parser.add_argument(
        "--skip-expansion",
        action="store_true",
        help="Skip intervention expansion (H searches)",
    )
    parser.add_argument(
        "--skip-results",
        action="store_true",
        help="Skip results extraction",
    )
    parser.add_argument(
        "--skip-publications",
        action="store_true",
        help="Skip publication linkage",
    )
    parser.add_argument(
        "--max-results-trials",
        type=int,
        default=50,
        help="Max trials to extract results from (default: 50)",
    )
    parser.add_argument(
        "--max-publication-trials",
        type=int,
        default=30,
        help="Max trials to link publications for (default: 30)",
    )

    args = parser.parse_args()

    # Resolve biomarker list
    if "all" in args.biomarkers:
        biomarkers = all_biomarker_ids()
    else:
        biomarkers = args.biomarkers

    logger.info(f"Biomarkers to process: {biomarkers}")
    logger.info(f"Output directory: {args.output_dir}")

    # Run pipeline for each biomarker
    all_summaries = []
    for bm in biomarkers:
        try:
            summary = run_pipeline(
                biomarker_id=bm,
                output_dir=args.output_dir,
                page_size=args.page_size,
                max_pages=args.max_pages,
                pause_seconds=args.pause,
                skip_expansion=args.skip_expansion,
                skip_results=args.skip_results,
                skip_publications=args.skip_publications,
                max_results_trials=args.max_results_trials,
                max_publication_trials=args.max_publication_trials,
            )
            all_summaries.append(summary)
        except Exception as e:
            logger.error(f"Pipeline failed for {bm}: {e}", exc_info=True)
            all_summaries.append({
                "biomarker_id": bm,
                "error": str(e),
            })

    # Save overall summary
    summary_path = os.path.join(
        args.output_dir, f"pipeline_summary_{time.strftime('%Y-%m-%d')}.json"
    )
    os.makedirs(args.output_dir, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2, default=str)
    logger.info(f"\nOverall summary saved to {summary_path}")

    # Print final table
    print(f"\n{'='*80}")
    print(f"{'Biomarker':<30} {'Trials':>8} {'High':>6} {'Review':>8} {'Cand':>6} {'Results':>8} {'Pubs':>6}")
    print(f"{'='*80}")
    for s in all_summaries:
        if "error" in s:
            print(f"{s['biomarker_id']:<30} {'ERROR':>8} {s['error'][:40]}")
            continue
        sweep = s.get("sweep", {})
        tiers = s.get("tier_distribution", {})
        print(
            f"{s['biomarker_id']:<30} "
            f"{sweep.get('unique_trials', 0):>8} "
            f"{tiers.get('high', 0):>6} "
            f"{tiers.get('review', 0):>8} "
            f"{tiers.get('candidate', 0):>6} "
            f"{s.get('results_extracted', '-'):>8} "
            f"{s.get('publications_linked', '-'):>6}"
        )
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
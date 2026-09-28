"""
Batch modifier screening.
"""
from __future__ import annotations
import csv
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.inference.predict import InteractionPredictor, _dense
from src.baselines.baselines import cosine_similarity, correlation


def screen_all_pairs(predictor, modifier_ids=None, output_path=None, method="model"):
    """Score all pairwise combinations of modifiers.

    Args:
        predictor: InteractionPredictor instance
        modifier_ids: list of modifier IDs (uses all profiles if None)
        output_path: optional CSV output path
        method: "model", "cosine", or "correlation"

    Returns: list of dicts {"modifier_a", "modifier_b", "score"}
    """
    if modifier_ids is None:
        modifier_ids = list(predictor.profiles.keys())

    results = []
    n = len(modifier_ids)

    for i in range(n):
        for j in range(i + 1, n):
            a, b = modifier_ids[i], modifier_ids[j]
            if method == "model":
                result = predictor.predict_from_profiles(a, b)
                score = result["prediction"]
            elif method == "cosine":
                score = predictor.baseline_cosine(a, b)
            elif method == "correlation":
                score = predictor.baseline_correlation(a, b)
            else:
                raise ValueError(f"Unknown method: {method}")

            results.append(
                {"modifier_a": a, "modifier_b": b, "score": round(float(score), 6)})

    if output_path:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["modifier_a", "modifier_b", "score"])
            w.writeheader()
            w.writerows(results)
        print(f"Wrote {len(results)} pairs to {output_path}")

    return results


def screen_vs_target(predictor, target_id, modifier_ids=None, output_path=None):
    """Score all modifiers against a single target modifier.

    Args:
        predictor: InteractionPredictor instance
        target_id: modifier ID to compare against
        modifier_ids: list of modifier IDs (uses all except target if None)

    Returns: list of dicts {"modifier_a", "modifier_b", "score"}
    """
    if modifier_ids is None:
        modifier_ids = [m for m in predictor.profiles.keys() if m != target_id]

    results = []
    for m_id in modifier_ids:
        result = predictor.predict_from_profiles(target_id, m_id)
        results.append(result)

    results.sort(key=lambda x: x.get("prediction", x.get("score", 0)), reverse=True)

    if output_path:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["modifier_a", "modifier_b", "prediction"])
            w.writeheader()
            for r in results:
                w.writerow(r)
        print(f"Wrote {len(results)} scores to {output_path}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch modifier screening")
    parser.add_argument("--target", help="Target modifier ID for focused screen")
    parser.add_argument("--all", action="store_true", help="Screen all pairs")
    parser.add_argument("--method", default="model", choices=["model", "cosine", "correlation"])
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument("--model", default=None, help="Model path")
    parser.add_argument("--ppi", default=None, help="PPI edges CSV path")
    parser.add_argument("--profiles", default=None, help="Modifier profiles directory")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profiles_dir = args.profiles or os.path.join(root, "data", "modifier_profiles")
    ppi_path = args.ppi or os.path.join(root, "data", "reference", "ppi_edges.csv")
    model_path = args.model

    predictor = InteractionPredictor(profiles_dir=profiles_dir)
    if os.path.isfile(ppi_path):
        predictor.load_graph(ppi_path)
    else:
        print("No PPI file found, using demo graph")
        predictor.load_graph()

    if model_path and os.path.isfile(model_path):
        predictor.load_model(model_path)
    else:
        print("No model loaded. Use --model to provide a trained model path.")
        print("Screening with baselines only.")

    if args.target:
        results = screen_vs_target(predictor, args.target, output_path=args.output)
        print(f"Top 5 modifiers similar to {args.target}:")
        for r in results[:5]:
            score = r.get("prediction", r.get("score", 0))
            print(f"  {r['modifier_b']}: {score:.4f}")
    elif args.all or not args.target:
        results = screen_all_pairs(predictor, method=args.method, output_path=args.output)
        print(f"Scored {len(results)} modifier pairs.")


if __name__ == "__main__":
    main()
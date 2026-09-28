"""Offline re-parse check: run the improved parser against the already-cached
raw HTML (no network) and show what it now extracts."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ingest_find_a_lab_test import parse_price_comparison_page

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE_DIR, "data", "raw", "test_prices", "find_a_lab_test", "2026-09-12")

for fname in sorted(os.listdir(CACHE)):
    with open(os.path.join(CACHE, fname), encoding="utf-8") as f:
        html = f.read()
    obs = parse_price_comparison_page(html)
    print(f"=== {fname} -> {len(obs)} observations ===")
    for o in obs:
        print(f"  ${o.amount:>8.2f}  {o.provider!r:<20} product={o.product_name!r}")
        print(f"            url={o.source_url}")
    print()
"""One-off: inspect what the ALT parse actually captured.

The card-block parser emits one observation per card, using the store name.
This dumps the raw card structure so we can see whether the repeated
"Jason Health $23.00" rows are distinct products (panels) or duplicate
extraction of the same product.
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PATH = os.path.join(
    BASE_DIR, "data", "raw", "test_prices", "find_a_lab_test", "2026-09-12",
    "https___www_findlabtest_com_lab_test_search_q_qt823.html",
)

with open(PATH, encoding="utf-8") as f:
    html = f.read()

blocks = re.split(r'<div id="card_body_\d+">', html)[1:]
print(f"{len(blocks)} card blocks\n")

for i, b in enumerate(blocks, 1):
    store = re.search(r'data-ga-event-category="store_name_click"\s+data-ga-event-action="([^"]+)"', b)
    total = re.search(r'total price should be\s*\n?\s*\$([\d,]+\.\d{2})', b)
    # Product name = the outbound link text for the store's own product page
    prod = re.search(
        r'data-ga-event-category="outbound_click"[^>]*?data-ga-event-label="([^"]+)"[^>]*>([^<]+)</a>',
        b, re.S,
    )
    store = store.group(1) if store else "?"
    total = total.group(1) if total else "?"
    if prod:
        prod_url, prod_name = prod.group(1), prod.group(2).strip()
    else:
        prod_url, prod_name = "", ""
    print(f"[{i:>2}] {store:<18} ${total:<8} {prod_name}")
    print(f"     {prod_url}")
"""One-off: look for a real product name in a Jason Health card."""
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(
    BASE_DIR, "data", "raw", "test_prices", "find_a_lab_test", "2026-09-12",
    "https___www_findlabtest_com_lab_test_search_q_qt823.html",
)

with open(PATH, encoding="utf-8") as f:
    html = f.read()

blocks = re.split(r'<div id="card_body_\d+">', html)[1:]
# Third card block = a Jason Health one
for i in (1, 2, 4):
    print(f"########## block {i} ##########")
    print(blocks[i][:2600])
    print()
"""One-off verification helper: dump the price fields the standalone pane
actually renders out of the embedded JSON blob in index.html."""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

for name in ("index.html", "frontend/index.html", "dist/index.html"):
    path = os.path.join(BASE_DIR, name)
    if not os.path.exists(path):
        print(f"{name}: MISSING")
        continue
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'<script id="embedded-biomarker-data"[^>]*>(.*?)</script>', content, re.S)
    if not m:
        print(f"{name}: no embedded blob found")
        continue
    data = json.loads(m.group(1))
    priced = [b for b in data["biomarkers"] if b.get("testPriceUSD") is not None]
    print(f"=== {name}: {len(priced)} biomarkers with a price ===")
    problems = []
    for b in sorted(priced, key=lambda x: x["slug"]):
        cms = b.get("cmsReimbursementUSD")
        print(
            f"  {b['slug']:<34} price=${b.get('testPriceUSD')!s:<7} cms=${cms!s:<7} "
            f"src={b.get('testPriceSourceLabel')!s:<60} "
            f"min/max={b.get('testPriceMin')}/{b.get('testPriceMax')} n={b.get('testPriceSourceCount')} "
            f"| standalone={b.get('testPriceStandaloneMedian')!s:<7} "
            f"n_std={b.get('testPriceStandaloneCount')} panelOnly={b.get('testPriceIsPanelDerived')}"
        )

        # Invariants asserted in tests/test_cash_pay_summary.py, re-checked here
        # against what actually shipped in the HTML.
        lo, med, hi = b.get("testPriceMin"), b.get("testPriceUSD"), b.get("testPriceMax")
        if lo is not None and med is not None and hi is not None:
            if not (lo <= med <= hi):
                problems.append(f"{b['slug']}: min/median/max not ordered ({lo}/{med}/{hi})")
        s_med, s_lo, s_hi = (
            b.get("testPriceStandaloneMedian"),
            b.get("testPriceStandaloneMin"),
            b.get("testPriceStandaloneMax"),
        )
        if s_med is not None:
            if s_lo is not None and s_hi is not None and not (s_lo <= s_med <= s_hi):
                problems.append(
                    f"{b['slug']}: standalone min/median/max not ordered ({s_lo}/{s_med}/{s_hi})"
                )
            if lo is not None and hi is not None and not (lo <= s_med <= hi):
                problems.append(
                    f"{b['slug']}: standalone median {s_med} outside blended range {lo}-{hi}"
                )
            if b.get("testPriceIsPanelDerived"):
                problems.append(f"{b['slug']}: has standalone price but flagged panel-only")
        elif b.get("testPriceSourceCount"):
            if not b.get("testPriceIsPanelDerived"):
                problems.append(f"{b['slug']}: no standalone price but not flagged panel-only")
    if problems:
        print("  !! problems:")
        for p in problems:
            print(f"     - {p}")
    else:
        print("  ok: all price invariants hold")
    print()
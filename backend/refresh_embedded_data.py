"""
Refresh the biomarker data embedded in the published HTML files from the
database, without regenerating the page.

build_standalone_html.py's page template is older than the published pages
(it lacks e.g. the age/sex curve selectors), so a full rebuild would drop
features. This swaps only the biomarker-derived parts of the embedded JSON
payload ("biomarkers", "scenarios", "sources", "stats") and leaves the page
markup, scripts and disease data untouched.

Usage:
  python backend/refresh_embedded_data.py [--check]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.build_standalone_html import compile_database_payload

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ["index.html", os.path.join("dist", "index.html"), os.path.join("frontend", "index.html")]
REFRESHED_KEYS = ("biomarkers", "scenarios", "sources")
MARKER = '<script id="embedded-biomarker-data" type="application/json">'


def locate_payload(html):
    start = html.index("{", html.index(MARKER))
    payload, end = json.JSONDecoder().raw_decode(html, start)
    return start, end, payload


def merged_payload(old, fresh):
    new = dict(old)
    for key in REFRESHED_KEYS:
        new[key] = fresh[key]
    # Biomarker counts come from the DB; disease counts stay with the embedded disease data.
    stats = dict(old["stats"])
    for key, value in fresh["stats"].items():
        if not key.startswith("disease"):
            stats[key] = value
    new["stats"] = stats

    live = {b["id"] for b in fresh["biomarkers"]}
    stale = [k for k in old.get("biomarker_diseases", {}) if int(k) not in live]
    if stale:
        raise SystemExit(f"Embedded disease data references removed biomarker ids {stale}")
    return new


def main():
    check = "--check" in sys.argv
    fresh = compile_database_payload()
    for rel in TARGETS:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as f:
            html = f.read()
        start, end, old = locate_payload(html)
        if json.dumps(old, separators=(",", ":"), ensure_ascii=False) != html[start:end] and \
           json.dumps(old, separators=(",", ":")) != html[start:end]:
            raise SystemExit(f"{rel}: embedded payload does not round-trip; refusing to rewrite")
        ascii_only = html[start:end].isascii()
        new = merged_payload(old, fresh)
        blob = json.dumps(new, separators=(",", ":"), ensure_ascii=ascii_only)
        if check:
            print(f"{rel}: {'up to date' if new == old else 'stale'}")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(html[:start] + blob + html[end:])
        print(f"{rel}: refreshed ({len(fresh['biomarkers'])} biomarkers)")


if __name__ == "__main__":
    main()

"""
Look up the preferred MeSH heading (the controlled vocabulary
ClinicalTrials.gov indexes studies against) for every biomarker, via NCBI's
public E-utilities (no API key; rate-limited to ~3 req/sec).

Tries, in order: the biomarker's name with parenthetical abbreviations
stripped, then each alias, until one resolves to a MeSH descriptor. Writes
a JSON cache so this only has to run once.
"""
import io
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def strip_paren(s):
    return re.sub(r"\([^)]*\)", "", s).strip()


def mesh_lookup(term, retries=3):
    q = urllib.parse.quote(f"{term}[MeSH Terms]")
    url = f"{EUTILS}/esearch.fcgi?db=mesh&term={q}&retmode=json&retmax=1"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                d = json.loads(r.read())
            ids = d.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return None
            uid = ids[0]
            time.sleep(0.34)
            url2 = f"{EUTILS}/esummary.fcgi?db=mesh&id={uid}&retmode=json"
            with urllib.request.urlopen(url2, timeout=15) as r:
                d2 = json.loads(r.read())
            info = d2.get("result", {}).get(uid, {})
            terms = info.get("ds_meshterms", [])
            if not terms:
                return None
            descriptor_id = "D" + uid[2:] if uid.startswith("68") and len(uid) > 2 else uid
            return {"mesh_term": terms[0], "mesh_id": descriptor_id, "uid": uid}
        except Exception as e:
            if attempt == retries - 1:
                print(f"    ! lookup failed for '{term}': {e}")
                return None
            time.sleep(1.0)
    return None


def main():
    conn = sqlite3.connect("data/mortality_biomarkers.db")
    cur = conn.cursor()
    cur.execute("SELECT id, slug, name, aliases FROM biomarker ORDER BY id")
    biomarkers = cur.fetchall()

    try:
        with open("backend/_mesh_cache.json", encoding="utf-8") as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}

    total = len(biomarkers)
    for i, (bid, slug, name, aliases_json) in enumerate(biomarkers, 1):
        if slug in cache:
            continue
        aliases = json.loads(aliases_json) if aliases_json else []
        candidates = [strip_paren(name), name] + aliases
        # dedupe, keep order
        seen = set()
        candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]

        result = None
        for term in candidates:
            if len(term) < 3:
                continue
            result = mesh_lookup(term)
            time.sleep(0.34)
            if result:
                break

        cache[slug] = result or {"mesh_term": None, "mesh_id": None, "uid": None}
        status = cache[slug]["mesh_term"] or "NOT FOUND"
        print(f"[{i}/{total}] {slug:<40} -> {status}")

        if i % 20 == 0:
            with open("backend/_mesh_cache.json", "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=1)

    with open("backend/_mesh_cache.json", "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    print("\nDone.")


if __name__ == "__main__":
    main()

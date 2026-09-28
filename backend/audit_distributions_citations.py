"""Audit population distributions and citation Vancouver formatting (strict)."""
import sqlite3
import re
import json

conn = sqlite3.connect('data/mortality_biomarkers.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 70)
print("POPULATION DISTRIBUTION DEEP VERIFICATION")
print("=" * 70)
c.execute("SELECT * FROM population_distribution")
dist_rows = [dict(r) for r in c.fetchall()]

issues = []
for r in dist_rows:
    rid = r.get('id')
    mean, sd = r.get('mean'), r.get('sd')
    p5, p25, p50, p75, p95 = r.get('p5'), r.get('p25'), r.get('p50'), r.get('p75'), r.get('p95')
    n = r.get('sample_n')

    if mean is None or sd is None:
        issues.append(f"Row {rid}: missing mean/sd")
        continue
    if sd <= 0:
        issues.append(f"Row {rid}: non-positive SD={sd}")
    # Percentile ordering
    pts = [p5, p25, p50, p75, p95]
    if all(p is not None for p in pts):
        if not (p5 <= p25 <= p50 <= p75 <= p95):
            issues.append(f"Row {rid}: percentiles not ordered: {pts}")
        # Median should be near mean for roughly normal dists
        if abs(p50 - mean) > 2.5 * sd:
            issues.append(f"Row {rid}: median {p50} far from mean {mean} (sd={sd})")
        # IQR check: p75-p25 should be ~1.35*sd for normal
        iqr = p75 - p25
        if sd > 0 and (iqr < 0.5 * sd or iqr > 3.0 * sd):
            issues.append(f"Row {rid}: IQR {iqr:.2f} inconsistent with SD {sd:.2f}")
    if n is not None and n <= 0:
        issues.append(f"Row {rid}: non-positive sample_n={n}")

print(f"Total distributions: {len(dist_rows)}")
print(f"Issues found: {len(issues)}")
for i in issues[:40]:
    print(f"  - {i}")

# Coverage: each biomarker should have distributions
c.execute("""
    SELECT b.id, b.name, COUNT(pd.id) as n_dist
    FROM biomarker b LEFT JOIN population_distribution pd ON pd.biomarker_id = b.id
    GROUP BY b.id ORDER BY n_dist
""")
no_dist = [(r['id'], r['name']) for r in c.fetchall() if r['n_dist'] == 0]
print(f"\nBiomarkers with NO distribution: {len(no_dist)}")
for bid, name in no_dist:
    print(f"  - [{bid}] {name}")

print("\n" + "=" * 70)
print("CITATION VANCOUVER STYLE AUDIT (STRICT)")
print("=" * 70)
c.execute("SELECT id, citation, pmid, doi, url, year FROM source")
sources = [dict(r) for r in c.fetchall()]
print(f"Total sources: {len(sources)}")

# Vancouver: Author AA, Author BB. Title. Journal Abbrev. Year;Vol(Issue):Pages.
# Key checks:
#  1. Has Year;Vol or Year;Vol(Issue):Pages pattern (allow electronic pages like e43, l1451, S19)
#  2. No periods between author initials (e.g., "Ridker P.M." is wrong; "Ridker PM" is right)
#  3. Journal abbreviated without periods (e.g., "N. Engl. J. Med." wrong; "N Engl J Med" right)
year_vol = re.compile(r"\b(19|20)\d{2};\d+")
periods_initials = re.compile(r"\b[A-Z]\.[A-Z]\.")  # e.g., P.M.
periods_single_initial = re.compile(r"[A-Z][a-z]+\s[A-Z]\.\s")  # "Ridker P. "
journal_periods = re.compile(r"\b[A-Z][a-z]*\.\s+[A-Z][a-z]*\.\s+[A-Z]")  # "N. Engl. J."

non_van = []
for s in sources:
    cit = (s.get('citation') or '').strip()
    problems = []
    if not cit:
        problems.append("EMPTY")
    else:
        if not year_vol.search(cit):
            problems.append("no Year;Vol pattern")
        if periods_initials.search(cit):
            problems.append("initials with periods (e.g. P.M.)")
        if journal_periods.search(cit):
            problems.append("journal name has periods")
    if problems:
        non_van.append({"id": s['id'], "citation": cit, "problems": problems, "pmid": s.get('pmid'), "doi": s.get('doi'), "year": s.get('year')})

print(f"Non-Vancouver: {len(non_van)} / {len(sources)}")
for nv in non_van:
    print(f"\n  [{nv['id']}] PMID={nv['pmid']} DOI={nv['doi']} year={nv['year']}")
    print(f"    Problems: {', '.join(nv['problems'])}")
    print(f"    {nv['citation'][:250]}")

conn.close()

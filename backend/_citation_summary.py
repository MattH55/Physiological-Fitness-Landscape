"""Quick summary of citation issues by type."""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from collections import Counter
from sqlalchemy.orm import sessionmaker
from backend.models import Source, get_engine, init_db

engine = get_engine("sqlite:///data/mortality_biomarkers.db")
init_db(engine)
S = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = S()
sources = db.query(Source).order_by(Source.id).all()

pc = Counter()
for s in sources:
    cit = s.citation or ""
    if re.search(r'PMID[:\s]*\d+', cit):
        pc['TRAILING_PMID_IN_TEXT'] += 1
    if not s.pmid and not s.doi:
        pc['MISSING_PMID_AND_DOI'] += 1
    if not re.search(r'\b(19|20)\d{2}\b', cit):
        pc['MISSING_YEAR'] += 1
    if cit and cit[0].islower():
        pc['AUTHOR_STARTS_LOWERCASE'] += 1
    if any(ord(c) > 127 for c in cit):
        pc['NON_ASCII'] += 1
    # Check for missing title (citation goes straight from authors to journal)
    # Pattern: "Author AA, et al. Journal. Year;Vol:Pages." (no title)
    if re.match(r'^[A-Z][a-z]+ [A-Z]{1,3}(, [a-z]+ [a-z]+)*,? et al\. [A-Z]', cit):
        pc['POSSIBLE_MISSING_TITLE'] += 1

print(f"Total sources: {len(sources)}\n")
print("Issue breakdown:")
for k, v in pc.most_common():
    print(f"  {k}: {v}")

# Show a few examples of each type
print("\n\nExamples of POSSIBLE_MISSING_TITLE:")
count = 0
for s in sources:
    cit = s.citation or ""
    if re.match(r'^[A-Z][a-z]+ [A-Z]{1,3}(, [a-z]+ [a-z]+)*,? et al\. [A-Z]', cit):
        print(f"  ID={s.id}: {cit[:120]}")
        count += 1
        if count >= 5:
            break

print("\nExamples of NON_ASCII:")
count = 0
for s in sources:
    cit = s.citation or ""
    if any(ord(c) > 127 for c in cit):
        non_ascii_chars = set(c for c in cit if ord(c) > 127)
        print(f"  ID={s.id}: chars={non_ascii_chars} | {cit[:100]}")
        count += 1
        if count >= 5:
            break

db.close()
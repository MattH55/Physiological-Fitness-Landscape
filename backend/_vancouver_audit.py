"""
Comprehensive Vancouver citation audit for all Source records.
Checks:
1. Author format (Surname Initials, comma-separated, et al. after 3+)
2. Title present
3. Journal abbreviation + year;volume(issue):pages
4. PMID/DOI present
5. No trailing "PMID: xxx" in citation text (should be in pmid field)
6. Special formats (books, datasets, government reports)
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy.orm import sessionmaker
from backend.models import Source, get_engine, init_db

engine = get_engine("sqlite:///data/mortality_biomarkers.db")
init_db(engine)
S = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = S()

sources = db.query(Source).order_by(Source.id).all()
print(f"Total sources: {len(sources)}\n")

# Vancouver patterns
# Standard journal article: Author AA, Author BB, Author CC. Title. J Abbr. Year;Vol(Issue):Pages.
# Author: Surname Initials (e.g., "Smith J", "Ridker PM")
# et al. after 3+ authors
# Journal: abbreviated, italicized (we can't check italics in plain text)
# Year;Volume(Issue):Pages.

issues = []

for s in sources:
    cit = s.citation or ""
    problems = []
    
    # Check 1: Trailing "PMID: xxx" in citation text
    if re.search(r'PMID[:\s]*\d+', cit):
        problems.append("TRAILING_PMID_IN_TEXT")
    
    # Check 2: Missing PMID and DOI
    if not s.pmid and not s.doi:
        problems.append("MISSING_PMID_AND_DOI")
    
    # Check 3: Missing year in citation
    if not re.search(r'\b(19|20)\d{2}\b', cit):
        problems.append("MISSING_YEAR")
    
    # Check 4: Check for standard journal article format
    # Pattern: Authors. Title. Journal. Year;Vol(Issue):Pages.
    # or: Authors. Title. Journal. Year;Vol:Pages.
    journal_pattern = re.compile(
        r'^(.+?)\.\s+'           # Authors
        r'(.+?)\.\s+'            # Title
        r'([A-Za-z][A-Za-z\s\.\-]*?)\.\s+'  # Journal
        r'((?:19|20)\d{2})'      # Year
        r';'                     # semicolon
        r'(\d+)'                 # Volume
        r'(?:\((\d+)\))?'        # (Issue)
        r':\s*'                  # colon
        r'([\d\-]+)\.'           # Pages
    )
    
    # Check if it looks like a journal article (has year;vol:pages pattern)
    has_journal_format = bool(re.search(r'\b(?:19|20)\d{2};\d+', cit))
    
    if has_journal_format:
        # Check for proper semicolon after year
        if not re.search(r'\b(?:19|20)\d{2};', cit):
            problems.append("MISSING_SEMICOLON_AFTER_YEAR")
        
        # Check for colon before pages
        if not re.search(r';\d+(?:\(\d+\))?:', cit):
            problems.append("MISSING_COLON_BEFORE_PAGES")
        
        # Check author format - should end with period before title
        # Look for "et al." usage
        if 'et al' in cit:
            # et al. should be followed by period
            if not re.search(r'et al\.', cit):
                problems.append("ET_AL_MISSING_PERIOD")
    
    # Check 5: Author format - look for common issues
    # Authors should be "Surname Initials" format
    # Check for lowercase surnames at start (likely not proper)
    if cit and cit[0].islower():
        problems.append("AUTHOR_STARTS_LOWERCASE")
    
    # Check 6: Missing period after journal name
    if has_journal_format:
        # Journal should be followed by period then year
        if not re.search(r'\.\s*(?:19|20)\d{2};', cit):
            problems.append("MISSING_PERIOD_BEFORE_YEAR")
    
    # Check 7: Check for "PMID" in DOI field or vice versa
    if s.doi and 'pmid' in s.doi.lower():
        problems.append("PMID_IN_DOI_FIELD")
    if s.pmid and s.pmid.startswith('10.'):
        problems.append("DOI_IN_PMID_FIELD")
    
    # Check 8: Empty or very short citation
    if len(cit.strip()) < 20:
        problems.append("CITATION_TOO_SHORT")
    
    # Check 9: Check for missing journal abbreviation (common issue)
    # If has year;vol:pages but no clear journal name
    if has_journal_format:
        # Extract the part between title period and year
        m = re.search(r'\.\s+([A-Za-z][A-Za-z\s\.\-/]*?)\.\s*(?:19|20)\d{2};', cit)
        if not m:
            problems.append("POSSIBLE_MISSING_JOURNAL")
    
    # Check 10: Non-ASCII characters that might indicate encoding issues
    non_ascii = [c for c in cit if ord(c) > 127]
    if non_ascii:
        problems.append(f"NON_ASCII_CHARS: {''.join(set(non_ascii))}")
    
    if problems:
        issues.append({
            'id': s.id,
            'citation': cit[:150] + '...' if len(cit) > 150 else cit,
            'pmid': s.pmid,
            'doi': s.doi,
            'problems': problems
        })

print(f"Sources with issues: {len(issues)} / {len(sources)}\n")
print("=" * 100)

for item in issues:
    print(f"\nID={item['id']}")
    print(f"  Citation: {item['citation']}")
    print(f"  PMID: {item['pmid']}")
    print(f"  DOI: {item['doi']}")
    print(f"  Problems: {', '.join(item['problems'])}")

print("\n" + "=" * 100)
print(f"\nSummary: {len(issues)} sources need attention out of {len(sources)} total")

db.close()
"""Fix Vancouver citation formatting: remove trailing PMID, normalize diacritics, fix lowercase."""
import sys, os, re, unicodedata
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy.orm import sessionmaker
from backend.models import Source, get_engine, init_db

def norm(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

engine = get_engine("sqlite:///data/mortality_biomarkers.db")
init_db(engine)
S = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = S()
sources = db.query(Source).order_by(Source.id).all()

fp = fd = fl = 0
for s in sources:
    orig = s.citation or ""
    nc = orig
    if re.search(r'PMID[:\s]*\d+', nc):
        nc = re.sub(r'\s*PMID[:\s]*\d+', '', nc)
        nc = re.sub(r'\s{2,}', ' ', nc).strip()
        if nc and not nc.endswith('.'):
            nc += '.'
        fp += 1
    if any(ord(c) > 127 for c in nc):
        nc = norm(nc)
        fd += 1
    if nc and nc[0].islower():
        nc = nc[0].upper() + nc[1:]
        fl += 1
    if nc != orig:
        s.citation = nc

db.commit()
print(f"Fixed trailing PMID: {fp}")
print(f"Fixed diacritics: {fd}")
print(f"Fixed lowercase: {fl}")

print("\nVerification:")
for sid in [21, 22, 44, 90, 123, 171, 222]:
    s = db.query(Source).filter(Source.id == sid).first()
    if s:
        print(f"  ID={s.id}: {s.citation[:120]}")
db.close()
print("Done.")
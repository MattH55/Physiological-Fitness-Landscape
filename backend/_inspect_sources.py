import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy.orm import sessionmaker
from backend.models import Source, Biomarker, get_engine, init_db

engine = get_engine("sqlite:///data/mortality_biomarkers.db")
init_db(engine)
S = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = S()

print("=== All Sources ===")
sources = db.query(Source).order_by(Source.id).all()
print(f"Total sources: {len(sources)}")
for s in sources:
    print(f"\n  ID={s.id}")
    print(f"  citation: {s.citation}")
    print(f"  pmid: {s.pmid}")
    print(f"  doi: {s.doi}")
    print(f"  url: {s.url}")
    print(f"  year: {s.year}")
    print(f"  study_design: {s.study_design}")

db.close()
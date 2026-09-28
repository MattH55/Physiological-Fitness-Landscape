"""Verify product_name persisted and show blended vs standalone cash-pay."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.consumer_price_sources import is_likely_panel
from backend.models import get_engine
from backend.test_cost_models import LabTest, TestPrice, TestCostSummary

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")

from sqlalchemy.orm import sessionmaker
engine = get_engine(f"sqlite:///{DB_PATH}")
db = sessionmaker(bind=engine)()

with_name = db.query(TestPrice).filter(TestPrice.product_name.isnot(None)).count()
total = db.query(TestPrice).count()
print(f"test_prices with product_name: {with_name}/{total}\n")

tests = db.query(LabTest).order_by(LabTest.test_id).all()
print(f"{'test_id':<34}{'n':>3}{'blended med':>13}{'std-only n':>11}{'std med':>9}")
print("-" * 70)
for t in tests:
    s = db.query(TestCostSummary).filter(TestCostSummary.test_id == t.test_id).first()
    if not s:
        continue
    prices = db.query(TestPrice).filter(TestPrice.test_id == t.test_id).all()
    n_panel = sum(1 for p in prices if is_likely_panel(p.product_name, t.test_name))
    print(f"{t.test_id:<34}{len(prices):>3}"
          f"{(s.cash_pay_median or 0):>13.2f}"
          f"{(s.cash_pay_standalone_count or 0):>11}"
          f"{(s.cash_pay_standalone_median or 0):>9.2f}   panels={n_panel}")

db.close()
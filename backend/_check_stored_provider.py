"""One-off: what provider strings are actually stored for the ALT test?"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
conn = sqlite3.connect(os.path.join(BASE_DIR, "data", "mortality_biomarkers.db"))
cur = conn.cursor()
cur.execute(
    "SELECT provider, amount, source_url, raw_payload_ref FROM test_prices "
    "WHERE test_id = ? AND source_tier = 'consumer_cash_pay' ORDER BY amount",
    ("test_alanine_aminotransferase",),
)
for prov, amt, url, ref in cur.fetchall():
    print(f"{amt:>8.2f}  provider={prov!r:<20} url={url}")
conn.close()
"""
Configuration for the Combinatorial Fitness Landscape module.

Database
--------
The spec targets Postgres (relational, join-heavy schema). For local
development and test parity with the existing landscape.opensourcemed.info
platform (which ships SQLite via SQLAlchemy), the database URL is configurable:

    SYNLETHALITY_DATABASE_URL  e.g. postgresql+psycopg2://user:pass@host/synlethality
                               default: sqlite under ./data/

All models use portable SQLAlchemy types; JSON columns map to JSONB on
Postgres via a variant (see models.JSONBVariant), so the same code runs on
both backends.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path: str) -> None:
    """Minimal .env loader (stdlib only). Real environment variables win;
    lines are KEY=VALUE, '#' comments and blanks are ignored."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(BASE_DIR, ".env"))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_DB_PATH = os.path.join(DATA_DIR, "synlethality_landscape.db")

DATABASE_URL = os.environ.get(
    "SYNLETHALITY_DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH}",
)

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# NCBI E-utilities (GEO downloads, PubMed lookups). With an API key the rate
# limit rises from 3 to 10 requests/second. Set in .env (gitignored) or the
# environment; NCBI also requests a contact email.
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")

# NCI Clinical Trials Search API (clinicaltrialsapi.cancer.gov), build spec
# v4: automated clinical_evidence discovery by NCIt disease code x drug name.
# Free key, request at https://clinicaltrialsapi.cancer.gov/.
NCI_CTS_API_KEY = os.environ.get("NCI_CTS_API_KEY", "")

APP_TITLE = "Combinatorial Fitness Landscape — Drug × Non-Pharmacological Modifier Interactions"
APP_VERSION = "0.1.0"

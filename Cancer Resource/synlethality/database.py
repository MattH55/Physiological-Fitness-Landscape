"""
Engine/session helpers. Mirrors the get_engine()/init_db() pattern used by the
existing Physiological Fitness Landscape platform for consistency.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from synlethality.models import Base


def get_engine(url: str, **kwargs):
    """Create a SQLAlchemy engine, handling SQLite-specific connect args."""
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, future=True, **kwargs)


def init_db(engine):
    """Create all tables (idempotent)."""
    Base.metadata.create_all(bind=engine)


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

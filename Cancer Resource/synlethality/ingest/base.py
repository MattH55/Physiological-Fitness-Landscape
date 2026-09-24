"""
Base class for ingestion pipeline steps.

Design notes (per build spec):
- Steps are idempotent: rerunning upserts rather than duplicating rows.
- Every run writes an IngestionRun row tagged with the source study/dataset,
  so a bad or retracted source can be located and its rows pulled without
  touching the rest of the table.
- No silent failures: extract/transform errors abort the step and record
  status="failed" with the exception message.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from synlethality.models import IngestionRun


class IngestionStep:
    #: short unique step name, e.g. "depmap_prism"
    step_name: str = ""
    #: citation/accession tag(s) recorded for every row this step loads
    source_study_tag: str = ""

    def extract(self) -> list[dict]:
        """Fetch raw records from the source. Returns a list of dicts."""
        raise NotImplementedError

    def transform(self, raw: list[dict]) -> list[dict]:
        """Map raw records to model constructor kwargs."""
        raise NotImplementedError

    def load(self, session: Session, rows: list[dict]) -> int:
        """Upsert transformed rows. Returns number of rows written."""
        raise NotImplementedError

    def run(self, session: Session, dry_run: bool = False) -> IngestionRun:
        run = IngestionRun(
            step_name=self.step_name,
            source_study_tag=self.source_study_tag,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()
        try:
            raw = self.extract()
            rows = self.transform(raw)
            if dry_run:
                run.status = "dry_run"
                run.row_count = len(rows)
                run.message = f"{len(raw)} raw records -> {len(rows)} rows (not written)"
                session.rollback()
                return run
            n = self.load(session, rows)
            session.commit()
            run.status = "success"
            run.row_count = n
        except Exception as exc:  # no silent failures
            session.rollback()
            run.status = "failed"
            run.message = f"{type(exc).__name__}: {exc}"
        finally:
            run.finished_at = datetime.now(timezone.utc)
        # Persist the run record itself (best effort).
        try:
            session.add(run)
            session.commit()
        except Exception:
            session.rollback()
        return run


def upsert_by_key(session: Session, model, key_field: str, rows: list[dict]) -> int:
    """Idempotent load: update existing row matched on key_field, else insert."""
    written = 0
    for row in rows:
        key = row[key_field]
        existing = (
            session.query(model)
            .filter(getattr(model, key_field) == key)
            .one_or_none()
        )
        if existing is None:
            session.add(model(**row))
        else:
            for k, v in row.items():
                if k != key_field:
                    setattr(existing, k, v)
        written += 1
    return written

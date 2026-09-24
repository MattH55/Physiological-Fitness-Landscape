"""
Ingestion step: FerrDB ferroptosis regulator gene set.

FerrDB (http://www.zhounan.org/ferrdb/) curates ferroptosis drivers,
suppressors, and markers. Used to refine the nrf2_ferroptosis signature panel
alongside MSigDB.

Status: structured stub — extract() raises NotImplementedError. Download the
current regulator tables manually and place under data/ferrdb/.
"""

from synlethality.ingest.base import IngestionStep


class FerrDBIngest(IngestionStep):
    step_name = "ferrdb"
    source_study_tag = "ferrdb:regulators"

    def __init__(self, ferrdb_dir: str = "data/ferrdb"):
        self.ferrdb_dir = ferrdb_dir

    def extract(self) -> list[dict]:
        raise NotImplementedError(
            f"Place FerrDB regulator CSV exports under {self.ferrdb_dir}/ and "
            "implement parsing here (drivers / suppressors / markers)."
        )

    def transform(self, raw: list[dict]) -> list[dict]:
        return raw

    def load(self, session, rows: list[dict]) -> int:  # pragma: no cover
        raise NotImplementedError("Gene-set store not yet modeled; consumed "
                                  "by the geo_modifiers scoring step.")

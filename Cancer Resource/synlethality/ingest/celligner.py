"""
Ingestion step: Celligner tumor-model concordance (Broad/DepMap).

Source: Celligner precomputed alignment output, distributed on figshare
(https://figshare.com/articles/dataset/Celligner_data/11965269) per Warren
et al. 2021, Nat Commun ("A framework for aligning tumor and cell-line
transcriptional profiles"). No alignment needs to be run locally — this
ingests the Broad's own precomputed per-line output.

Per the build spec, Celligner's finding is that a meaningful subset of
commonly-used cell lines don't transcriptionally resemble any real tumor
type (often a mesenchymal-shift artifact of long-term culture). Loads into:
`cell_line.tumor_concordance_score` (a continuity/alignment-distance metric
from the Celligner output; exact column depends on the release — document
which one is used when this is implemented) and
`cell_line.tumor_concordance_flag` (good_model / poor_model_mesenchymal_shift
/ unassessed).

Status: structured stub — extract() raises NotImplementedError until the
figshare release has been downloaded and its cell-line ID column mapped to
the CCLE/DepMap canonical cell_line_id used here. No fabricated scores are
ever written; a cell line stays `unassessed` (the curated-seed default, see
seed_data.py) rather than getting a guessed score/flag.
"""

from synlethality.ingest.base import IngestionStep
from synlethality.models import CellLine


class CellignerIngest(IngestionStep):
    step_name = "celligner"
    source_study_tag = "celligner:figshare-11965269"

    def __init__(self, alignment_path: str = "data/celligner/celligner_alignment.csv"):
        self.alignment_path = alignment_path

    def extract(self) -> list[dict]:
        raise NotImplementedError(
            f"Celligner download not enabled. Download the precomputed "
            "alignment output from "
            "https://figshare.com/articles/dataset/Celligner_data/11965269, "
            f"place it at {self.alignment_path}, and implement parsing here. "
            "Map Celligner's own cell-line IDs to the CCLE/DepMap canonical "
            "cell_line_id before loading; do not insert Celligner's raw IDs "
            "directly as cell_line_id."
        )

    def transform(self, raw: list[dict]) -> list[dict]:
        """Expected raw record shape (documented contract):
          {"cell_line_id": ..., "tumor_concordance_score": ...,
           "tumor_concordance_flag": "good_model"|"poor_model_mesenchymal_shift"}
        A line absent from the Celligner release should not be touched here
        (it stays "unassessed" from the curated seed default) rather than
        being assigned a flag by inference.
        """
        return raw

    def load(self, session, rows: list[dict]) -> int:
        n = 0
        for r in rows:
            cl = session.get(CellLine, r["cell_line_id"])
            if cl is None:
                continue  # cell_line must already exist; Celligner only backfills it
            cl.tumor_concordance_score = r.get("tumor_concordance_score")
            cl.tumor_concordance_flag = r.get("tumor_concordance_flag")
            n += 1
        return n

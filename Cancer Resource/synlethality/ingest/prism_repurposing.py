"""
Ingestion step: real PRISM Repurposing monotherapy viability data.

Source: PRISM Repurposing Public 24Q2, mirrored on Figshare (ungated,
unlike depmap.org's own portal -- same access pattern as
ingest/depmap_prism.py):
  https://figshare.com/articles/dataset/Repurposing_Public_24Q2/25917643
  DOI: 10.6084/m9.figshare.25917643.v1
  - Extended_Primary_Compound_List.csv  (per-treatment-row metadata; "IDs"
    column is the BRD compound ID, joins to the matrix's row index)
  - Extended_Primary_Data_Matrix.csv    (rows = treatments/BRD ids,
    columns = DepMap ModelIDs; cells = LFC, see below)

Single dose (2.5 uM), 5-day treatment, ~906 cell lines x 1514 compounds
(extended with the original PRISM Repurposing Primary Screen compounds for
convenience -- 6,790 total treatment rows). Values are log2-fold-change
(LFC) between each treatment and the median of that plate's DMSO negative-
control wells, QC-filtered (error_rate < .05, dynamic range > 2, >=2
passing replicates) and replicate-median-collapsed -- see the release's own
README.txt (downloaded alongside these files) for the full pipeline
(LMFI -> LMFI.normalized -> LFC -> LFC_cb -> this matrix). This is real,
already-processed, citable data -- not something computed or estimated
here.

Downloaded 2026-09-22 via the public Figshare API (api.figshare.com/v2,
ungated) to data/prism/{Extended_Primary_Compound_List,
Extended_Primary_Data_Matrix}.csv.

Scope, deliberately narrow (same posture as ingest/depmap_prism.py):
  - **Monotherapy only.** This is drug-alone viability at a single dose --
    it is NOT combination/dose-response data, so it does not by itself
    unlock Step 1 (classical synergy scoring needs a modifier x drug dose-
    response surface) or Step 2 (needs quantitative Tier 1 *combination*
    labels). It fills `drug_response`, which has been empty since the
    schema was designed for exactly this: real monotherapy context for a
    drug/cell-line pair, joinable against `interaction_effect` claims.
  - **Only our 12 curated cell lines that were actually screened in this
    release** (of the 14 in ingest/depmap_prism.py, 2 -- MCF-10A and HeLa
    -- were not part of this particular PRISM run; left alone, not
    guessed). No new CellLine or Drug rows are created here -- both are
    matched against rows already inserted by ingest/depmap_prism.py, which
    must run first.
  - The BRD compound ID -> our drug_id mapping is re-derived from
    PortalCompounds.csv's own SampleIDs cross-reference column (verified
    2026-09-22: 6,765 of 6,790 matrix rows resolve to a known drug_id by
    exact BRD-ID match) -- not stored as a separate schema field, since
    it's only needed at ingestion time.
"""

import csv
import os

from synlethality import config
from synlethality.ingest.base import IngestionStep
from synlethality.ingest.depmap_prism import CURATED_DRUG_ALIASES
from synlethality.models import Drug, DrugResponse, MetricType

PRISM_DATA_DIR = os.path.join(config.DATA_DIR, "prism")
DEPMAP_DATA_DIR = os.path.join(config.DATA_DIR, "depmap")

#: our curated cell_line_id -> DepMap ModelID (ACH-xxxxxx), for the 12 of
#: our 14 v4-schema-matched lines actually present as a column in this
#: PRISM release. Verified 2026-09-22 directly against both Model.csv and
#: the real matrix header (not guessed): MCF-10A and HeLa are absent from
#: this particular screen, not from an error.
CELL_LINE_ACH_ID = {
    "MCF7_BREAST": "ACH-000019",
    "T47D_BREAST": "ACH-000147",
    "MDAMB231_BREAST": "ACH-000768",
    "MDAMB468_BREAST": "ACH-000849",
    "U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE": "ACH-000406",
    "RKO_LARGE_INTESTINE": "ACH-000943",
    "DU145_PROSTATE": "ACH-000979",
    "A549_LUNG": "ACH-000681",
    "CASKI_CERVIX": "ACH-001336",
    "HCT116_LARGE_INTESTINE": "ACH-000971",
    "U87MG_CENTRAL_NERVOUS_SYSTEM": "ACH-000075",
    "T98G_CENTRAL_NERVOUS_SYSTEM": "ACH-000571",
    # Deliberately absent, not guessed: MCF10A_BREAST, HELA_CERVIX
    # (not part of this PRISM release's cell-line panel).
}

SOURCE_TAG = "PRISM Repurposing Public 24Q2 (2.5uM, 5-day; doi:10.6084/m9.figshare.25917643.v1)"


class PrismRepurposingIngest(IngestionStep):
    step_name = "prism_repurposing"
    source_study_tag = "prism:24Q2-figshare-25917643"

    def __init__(self, prism_dir: str = PRISM_DATA_DIR, depmap_dir: str = DEPMAP_DATA_DIR):
        self.prism_dir = prism_dir
        self.depmap_dir = depmap_dir
        self.compound_csv = os.path.join(prism_dir, "Extended_Primary_Compound_List.csv")
        self.matrix_csv = os.path.join(prism_dir, "Extended_Primary_Data_Matrix.csv")
        self.portal_compounds_csv = os.path.join(depmap_dir, "PortalCompounds.csv")

    def extract(self) -> list[dict]:
        missing = [
            p for p in (self.compound_csv, self.matrix_csv, self.portal_compounds_csv)
            if not os.path.isfile(p)
        ]
        if missing:
            raise NotImplementedError(
                f"Missing required file(s): {missing}. Download "
                "Extended_Primary_Compound_List.csv and "
                "Extended_Primary_Data_Matrix.csv from the DepMap PRISM "
                "Repurposing Public 24Q2 release on Figshare "
                "(https://figshare.com/articles/dataset/Repurposing_Public_24Q2/25917643, "
                f"via the ungated api.figshare.com/v2/articles/25917643 file "
                f"manifest) into {self.prism_dir}/, and ensure "
                "ingest/depmap_prism.py's PortalCompounds.csv has already "
                f"been downloaded to {self.depmap_dir}/."
            )
        # BRD compound ID -> our drug_id, from DepMap's own cross-reference
        # column (see module docstring). Built once here rather than stored,
        # since it's only needed at ingestion time. Compounds DepMap lists
        # under a different identity than one of our curated drugs (see
        # depmap_prism.CURATED_DRUG_ALIASES) redirect here to the curated
        # drug_id -- ingest/depmap_prism.py never creates a Drug row for
        # these CompoundIDs at all, so without this redirect their real
        # viability data would have nowhere valid to attach.
        brd_to_drug_id: dict[str, str] = {}
        with open(self.portal_compounds_csv, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                drug_id = CURATED_DRUG_ALIASES.get(row["CompoundID"], row["CompoundID"])
                for sid in (row.get("SampleIDs") or "").split(";"):
                    if sid.startswith("BRD:"):
                        brd_to_drug_id[sid[4:]] = drug_id

        ach_ids = list(CELL_LINE_ACH_ID.values())
        raw: list[dict] = []
        with open(self.matrix_csv, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            col_index = {ach: header.index(ach) for ach in ach_ids if ach in header}
            for row in reader:
                brd_id = row[0]
                if brd_id.startswith("BRD:"):
                    brd_id = brd_id[4:]
                drug_id = brd_to_drug_id.get(brd_id)
                if drug_id is None:
                    continue  # no known compound for this treatment row; skip, don't guess
                for our_cell_line_id, ach in CELL_LINE_ACH_ID.items():
                    idx = col_index.get(ach)
                    if idx is None:
                        continue
                    value = row[idx].strip()
                    if not value:
                        continue  # QC-filtered/missing cell; never fabricated
                    raw.append({
                        "drug_id": drug_id,
                        "cell_line_id": our_cell_line_id,
                        "viability_metric": float(value),
                    })
        return raw

    def transform(self, raw: list[dict]) -> list[dict]:
        for r in raw:
            r["metric_type"] = MetricType.lfc_2_5um_5d
            r["source"] = SOURCE_TAG
        return raw

    def load(self, session, rows: list[dict]) -> int:
        # At this scale (tens of thousands of rows), a per-row SELECT would
        # be far too slow -- one bulk query for existing rows, then a set
        # for known drug_ids, both checked in memory.
        existing_by_key = {
            (dr.drug_id, dr.cell_line_id): dr
            for dr in session.query(DrugResponse).filter_by(source=SOURCE_TAG).all()
        }
        known_drug_ids = {
            drug_id for (drug_id,) in session.query(Drug.drug_id).all()
        }
        n = 0
        for r in rows:
            if r["drug_id"] not in known_drug_ids:
                continue  # drug must already exist; never created here
            key = (r["drug_id"], r["cell_line_id"])
            existing = existing_by_key.get(key)
            if existing is None:
                session.add(DrugResponse(**r))
            else:
                existing.viability_metric = r["viability_metric"]
                existing.metric_type = r["metric_type"]
            n += 1
        return n

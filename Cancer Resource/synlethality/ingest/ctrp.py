"""
Ingestion step: CTRP (Cancer Therapeutics Response Portal) drug response.

Per the build spec, CTRP's role is the same as GDSC's (see
ingest/gdsc.py, also real): a second independent cross-check against
PRISM/GDSC. Three-way disagreement across PRISM/GDSC/CTRPv2 for the same
(drug_id, cell_line_id) is a stronger data-quality flag than either
two-way comparison alone.

**A genuinely blocked source, found a real workaround for, 2026-09-23**:
CTRP's original NCI CTD2 data portal
(`ocg.cancer.gov/programs/ctd2/data-portal`) no longer resolves at all,
and its FTP host's data directory tree
(`caftpd.nci.nih.gov/pub/OCG-DCC/CTD2/Broad/`) has been removed entirely
-- checked directly, not assumed. The only remaining real mirrors
(Zenodo record 3747829, PharmacoDB, ORCESTRA) serve a `PharmacoSet` -- a
Bioconductor `PharmacoGx` S4 object serialized as `CTRPv2.rds` -- which
Python's `pyreadr` cannot parse at all (`LibrdataError: unrecognized
object`, since `pyreadr` only handles plain data.frames).

**The real workaround**: install base R itself (no admin rights needed --
CRAN's own Windows installer supports a per-user install via
`/DIR=<user path>`) and use R's own `readRDS()`, which loads the object
fine without the `PharmacoGx` package installed at all -- S4 slot values
are still accessible generically via `attr(obj, "<slotName>")`, even
though class-introspection helpers like `slotNames()` do need the
defining package. `scripts/extract_ctrp.R` is the one place in this
project that uses R: it reads the real `.rds` file and writes its
`sensitivity$info`/`sensitivity$profiles` slots (per-experiment cell
line, drug, culture media, and the real recomputed Area-Above-Curve) out
as a plain CSV. Everything downstream of that -- name mapping,
replicate aggregation, DB loading -- is ordinary Python, matching every
other ingestion step in this codebase.

**Real overlap, verified by direct name lookup against the real
extracted data**: CTRPv2's own `drugid`/`cellid` fields are already
human-readable names (e.g. "Oxaliplatin", "MCF-7"), not opaque codes --
7 of 13 curated drugs (oxaliplatin, 5-fluorouracil, doxorubicin,
paclitaxel, erastin, cyclophosphamide, temozolomide -- notably erastin,
which neither GDSC nor LINCS Phase 2 covers) and 11 of 14 curated cell
lines (CaSki, U-87MG, MCF-10A confirmed absent) have real data.

**Real duplicates handled, same posture as gdsc.py's real fix**: CTRP
ran some (drug, cell line) pairs multiple times under genuinely different
conditions (different culture media -- DMEM vs RPMI -- or true biological
replicates within the same media). Unlike GDSC's own duplicates (which had
a real per-row fit-quality metric, RMSE, to pick the better one by), CTRP's
`profiles` table has no equivalent residual/quality column -- so the real,
transparent choice here is the **mean** of all real (non-NA)
`aac_recomputed` values for that pair, documented as such, never silently
picking one arbitrarily.

**Metric stored**: `AUC = 1 - mean(aac_recomputed)` as
`metric_type=MetricType.auc` -- `aac_recomputed` is PharmacoGx's own
real, recomputed Area-Above-Curve on a 0-1 scale; converting to
Area-Under-Curve keeps the same "lower = more killing" convention already
used for PRISM's/GDSC's AUC-style metrics elsewhere in this schema.
"""

import csv
import os

from synlethality.ingest.base import IngestionStep
from synlethality.models import DrugResponse, MetricType

DATA_DIR = "data/ctrp"

#: CTRPv2 cellid (real, verified 2026-09-23 against the real extracted
#: data) -> our curated cell_line_id. CaSki, U-87MG, and MCF-10A are
#: confirmed absent from CTRPv2 -- not omitted by oversight.
CELL_LINE_NAME_MAP = {
    "MCF-7": "MCF7_BREAST",
    "T-47D": "T47D_BREAST",
    "MDA-MB-231": "MDAMB231_BREAST",
    "MDA-MB-468": "MDAMB468_BREAST",
    "HCT 116": "HCT116_LARGE_INTESTINE",
    "RKO": "RKO_LARGE_INTESTINE",
    "DU145": "DU145_PROSTATE",
    "A-549": "A549_LUNG",
    "HeLa": "HELA_CERVIX",
    "T98G": "T98G_CENTRAL_NERVOUS_SYSTEM",
    "U-937": "U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE",
}

#: CTRPv2 drugid (real, exact) -> our curated drug_id. Cisplatin,
#: carboplatin, mitomycin-C, triapine, lomustine, and metformin are
#: confirmed absent from CTRPv2's 544-compound panel -- not omitted by
#: oversight.
DRUG_NAME_MAP = {
    "Oxaliplatin": "oxaliplatin",
    "5-Fluorouracil": "5-fluorouracil",
    "Doxorubicin": "doxorubicin",
    "Paclitaxel": "paclitaxel",
    "Erastin": "erastin",
    "Cyclophosphamide": "cyclophosphamide",
    "Temozolomide": "temozolomide",
}

SOURCE_TAG = "CTRP v2"


class CTRPIngest(IngestionStep):
    step_name = "ctrp"
    source_study_tag = "ctrp:zenodo-3747829-pharmacoset"

    def __init__(self, sensitivity_csv: str = os.path.join(DATA_DIR, "ctrpv2_sensitivity.csv")):
        self.sensitivity_csv = sensitivity_csv

    def extract(self) -> list[dict]:
        if not os.path.isfile(self.sensitivity_csv):
            raise NotImplementedError(
                f"{self.sensitivity_csv} not found. Real path (2026-09-23, "
                "see module docstring for why this needs R): download "
                "CTRPv2.rds from https://zenodo.org/records/3747829, "
                "install R (CRAN, no admin rights needed via a per-user "
                "/DIR= install), then run "
                f"`Rscript scripts/extract_ctrp.R data/ctrp/CTRPv2.rds "
                f"{self.sensitivity_csv}`."
            )
        # Group real per-experiment aac_recomputed values by (drug, cell
        # line), for the mean-across-replicates aggregation documented in
        # the module docstring.
        grouped: dict[tuple[str, str], list[float]] = {}
        with open(self.sensitivity_csv, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cell_line_id = CELL_LINE_NAME_MAP.get(row["cellid"])
                drug_id = DRUG_NAME_MAP.get(row["drugid"])
                if cell_line_id is None or drug_id is None:
                    continue
                grouped.setdefault((drug_id, cell_line_id), []).append(float(row["aac_recomputed"]))
        return [
            {"kind": "drug_response", "drug_id": drug_id, "cell_line_id": cell_line_id,
             "aac_values": values}
            for (drug_id, cell_line_id), values in grouped.items()
        ]

    def transform(self, raw: list[dict]) -> dict:
        out = {"cell_line": [], "drug": [], "drug_response": []}
        for rec in raw:
            aac_values = rec.pop("aac_values")
            mean_aac = sum(aac_values) / len(aac_values)
            rec.pop("kind", None)
            out["drug_response"].append({
                **rec,
                "viability_metric": 1.0 - mean_aac,  # AUC = 1 - AAC
                "metric_type": MetricType.auc,
                "source": SOURCE_TAG,
            })
        return out

    def load(self, session, rows: dict) -> int:
        n = 0
        for r in rows["drug_response"]:
            existing = (
                session.query(DrugResponse)
                .filter_by(drug_id=r["drug_id"], cell_line_id=r["cell_line_id"], source=r["source"])
                .one_or_none()
            )
            if existing is None:
                session.add(DrugResponse(**r))
            else:
                existing.viability_metric = r["viability_metric"]
                existing.metric_type = r["metric_type"]
            n += 1
        return n

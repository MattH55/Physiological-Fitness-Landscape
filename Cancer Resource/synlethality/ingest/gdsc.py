"""
Ingestion step: GDSC (Genomics of Drug Sensitivity in Cancer) drug response.

Real, working implementation (2026-09-23) for both GDSC1 and GDSC2's fitted
dose-response tables. Per the build spec, GDSC's role here is a
cross-validation source against PRISM (synlethality/ingest/prism_repurposing.py):
disagreement between independently-run viability screens for the same
drug x cell-line pair is itself a useful data-quality flag.

**Source, and why not depmap.org/cancerrxgene.org's own web UI**: both
gate behind Cloudflare bot-protection, same problem MDPI/NCI's wiki
presented elsewhere in this codebase. The Wellcome Sanger Institute's own
FTP mirror (ftp.sanger.ac.uk/pub/project/cancerrxgene/releases/release-8.2/)
serves the identical real files with no gate at all -- verified 2026-09-23
by a direct unauthenticated download:
  - GDSC1_fitted_dose_response_25Feb20.csv (48MB, 345 real compounds)
  - GDSC2_fitted_dose_response_25Feb20.csv (21MB, 192 real compounds,
    a later, methodologically distinct assay platform from GDSC1 -- kept
    as a separate `source` tag, "GDSC1"/"GDSC2", never merged into one
    "GDSC" label)

**Real overlap with the curated registry, verified by direct name lookup
against both real downloaded files (not assumed)**: 12 of the 14 curated
cell lines (U-937 and MCF-10A are genuinely absent from both GDSC
releases' cell-line panels -- left absent, not guessed) and 8 of the 13
curated drugs (cisplatin, oxaliplatin, 5-fluorouracil, paclitaxel,
cyclophosphamide, temozolomide in both releases; doxorubicin and
mitomycin-C in GDSC1 only -- the other 5 curated drugs are genuinely not
in either screen's compound panel).

Cell-line names in GDSC's own `CELL_LINE_NAME` column match our curated
names closely (e.g. "HCT-116" vs our "HCT116_LARGE_INTESTINE") --
CELL_LINE_NAME_MAP below is the exact, verified mapping, keyed by GDSC's
own spelling normalized (uppercase, hyphens stripped) to avoid a dozen
near-duplicate hardcoded variants.

**Metric stored**: GDSC's own `AUC` column (already a real, published
0-1-scale dose-normalized area-under-curve, not re-derived here) as
`metric_type=MetricType.auc` -- not `LN_IC50`, which would need a unit
conversion this step doesn't attempt. `viability_metric` in this schema is
"lower = more killing" by AUC's own convention (1.0 = no growth
inhibition across the tested dose range, closer to 0 = strong inhibition),
matching how PRISM's own AUC-adjacent conventions are documented elsewhere
in this codebase (see ingest/prism_repurposing.py's LFC convention note
for the analogous "documented, not silently normalized" posture).
"""

import csv
import os

from synlethality.ingest.base import IngestionStep
from synlethality.models import DrugResponse, MetricType

DATA_DIR = "data/gdsc"

#: GDSC CELL_LINE_NAME (uppercase, hyphens/spaces stripped) -> our curated
#: cell_line_id. Verified 2026-09-23 by direct lookup against both real
#: downloaded GDSC1/GDSC2 files -- U-937 and MCF-10A are confirmed absent
#: from both, not omitted by oversight.
CELL_LINE_NAME_MAP = {
    "MCF7": "MCF7_BREAST",
    "T47D": "T47D_BREAST",
    "MDAMB231": "MDAMB231_BREAST",
    "MDAMB468": "MDAMB468_BREAST",
    "HCT116": "HCT116_LARGE_INTESTINE",
    "RKO": "RKO_LARGE_INTESTINE",
    "DU145": "DU145_PROSTATE",
    "A549": "A549_LUNG",
    "HELA": "HELA_CERVIX",
    "CASKI": "CASKI_CERVIX",
    "U87MG": "U87MG_CENTRAL_NERVOUS_SYSTEM",
    "T98G": "T98G_CENTRAL_NERVOUS_SYSTEM",
}

#: GDSC DRUG_NAME (exact) -> our curated drug_id. Verified 2026-09-23 by a
#: full-vocabulary search against both real downloaded files -- metformin,
#: carboplatin, erastin, triapine, and lomustine are confirmed absent from
#: both GDSC1 and GDSC2's compound panels, not omitted by oversight.
DRUG_NAME_MAP = {
    "Cisplatin": "cisplatin",
    "Oxaliplatin": "oxaliplatin",
    "5-Fluorouracil": "5-fluorouracil",
    "Paclitaxel": "paclitaxel",
    "Cyclophosphamide": "cyclophosphamide",
    "Temozolomide": "temozolomide",
    "Doxorubicin": "doxorubicin",  # GDSC1 only
    "Mitomycin-C": "mitomycin-c",  # GDSC1 only
}


def _normalize_cell_line(name: str) -> str:
    return name.upper().replace("-", "").replace(" ", "")


class GDSCIngest(IngestionStep):
    step_name = "gdsc"
    source_study_tag = "gdsc:sanger-ftp-release-8.2"

    def __init__(self, gdsc1_path: str = os.path.join(DATA_DIR, "GDSC1_fitted_dose_response.csv"),
                 gdsc2_path: str = os.path.join(DATA_DIR, "GDSC2_fitted_dose_response.csv")):
        self.gdsc1_path = gdsc1_path
        self.gdsc2_path = gdsc2_path

    def extract(self) -> list[dict]:
        paths = [("GDSC1", self.gdsc1_path), ("GDSC2", self.gdsc2_path)]
        missing = [p for _, p in paths if not os.path.isfile(p)]
        if missing:
            raise NotImplementedError(
                f"Missing file(s): {missing}. Download "
                "GDSC1_fitted_dose_response_25Feb20.csv and "
                "GDSC2_fitted_dose_response_25Feb20.csv from "
                "https://ftp.sanger.ac.uk/pub/project/cancerrxgene/releases/release-8.2/ "
                f"(no login needed) into {DATA_DIR}/."
            )
        cell_line_normalized = {_normalize_cell_line(k): v for k, v in CELL_LINE_NAME_MAP.items()}
        # (drug_id, cell_line_id, source) -> best row so far, real
        # deduplication key. A single compound can carry >1 real raw row
        # here (found 2026-09-23: GDSC screens the same compound sourced
        # from different vendors/batches under separate internal DRUG_IDs,
        # e.g. real oxaliplatin-in-RKO rows from DRUG_ID 1089 and 1806, with
        # different concentration ranges and RMSE) -- keep the one with the
        # lower RMSE (GDSC's own real curve-fit residual, lower = a better
        # fit to that row's own dose-response data), never averaged or
        # arbitrarily first/last-picked.
        best: dict[tuple[str, str, str], dict] = {}
        for source_tag, path in paths:
            with open(path, encoding="utf-8") as fh:
                for rec in csv.DictReader(fh):
                    cell_line_id = cell_line_normalized.get(_normalize_cell_line(rec["CELL_LINE_NAME"]))
                    drug_id = DRUG_NAME_MAP.get(rec["DRUG_NAME"])
                    if cell_line_id is None or drug_id is None:
                        continue
                    auc = rec.get("AUC")
                    rmse = rec.get("RMSE")
                    if not auc or not rmse:
                        continue
                    key = (drug_id, cell_line_id, source_tag)
                    rmse_val = float(rmse)
                    if key not in best or rmse_val < best[key]["_rmse"]:
                        best[key] = {
                            "kind": "drug_response",
                            "drug_id": drug_id,
                            "cell_line_id": cell_line_id,
                            "viability_metric": float(auc),
                            "metric_type": MetricType.auc,
                            "source": source_tag,
                            "_rmse": rmse_val,
                        }
        for rec in best.values():
            del rec["_rmse"]
        return list(best.values())

    def transform(self, raw: list[dict]) -> dict:
        """Raw records are already load()-ready dicts tagged
        kind="drug_response"; group by kind for the shared load() contract
        (mirrors depmap_prism.py/ctrp.py's shape, even though this step
        only ever produces drug_response rows -- no new cell_line/drug rows,
        both are matched against ones ingest/depmap_prism.py already
        created)."""
        out = {"cell_line": [], "drug": [], "drug_response": []}
        for rec in raw:
            kind = rec.pop("kind", None)
            if kind in out:
                out[kind].append(rec)
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

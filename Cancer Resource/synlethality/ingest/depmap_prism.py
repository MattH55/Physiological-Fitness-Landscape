"""
Ingestion step: DepMap cell-line metadata + compound registry.

Source: DepMap 24Q4 Public release, mirrored on Figshare+ (no bot-gate,
unlike depmap.org's own portal, which sits behind Cloudflare Turnstile and
cannot be fetched programmatically):
  https://plus.figshare.com/articles/dataset/DepMap_24Q4_Public/27993248
  DOI: 10.25452/figshare.plus.27993248.v1
  - Model.csv            (cell line metadata, incl. OncoTree annotation)
  - PortalCompounds.csv  (DepMap's own compound registry: name, gene
    targets, mechanism, synonyms, ChEMBL/PubChem cross-refs)

Downloaded 2026-09-22 via the public Figshare API (api.figshare.com/v2,
which is not gated) to data/depmap/{Model,PortalCompounds}.csv.

Scope of this step, deliberately narrow:
  1. **Cell line backfill only** — never inserts new CellLine rows. Only
     the 4 OncoTree fields (oncotree_code/primary_disease/subtype; ncit_code
     stays NULL, since that needs OncoTree's own oncotree_to_nci() API,
     which 403'd for non-browser requests in this session) are backfilled
     onto cell lines already in our curated seed, matched by
     StrippedCellLineName. A line with no DepMap match (e.g. the murine 4T1
     line, or the isogenic HCT116-p53-null derivative DepMap doesn't track
     as a distinct model) is simply left alone, not guessed.
  2. **Compound registry only, not response/viability data** — inserts one
     `drug` row per DepMap PortalCompounds.csv compound not already in our
     registry. This is the real, comprehensive DepMap drug catalog (~7,000
     compounds), which is what "include every drug in DepMap" can honestly
     mean without fabricating interaction_effect claims for it: every
     bulk-imported drug has zero interactions until a real study is
     curated for it, exactly like every other empty cell in this database.
     PRISM Repurposing viability/AUC data (a separate, larger release) is
     NOT ingested here — drug_response stays empty for these compounds.

Deliberate drug_id scheme note (documented exception to the "lowercase
slug" convention used by the curated seed): bulk-imported rows keep
DepMap's own CompoundID (e.g. "DPC-000001") as drug_id, rather than
slugifying CompoundName. CompoundName values collide across stereoisomer
pairs (e.g. "(+)-JQ-1" vs "(-)-JQ-1" both slugify to "jq-1"), so reusing
DepMap's own stable, globally-unique ID avoids silently merging distinct
compounds.

**Curated-drug identity collision, found and fixed 2026-09-22**: DepMap's
own registry independently lists 12 of our 13 curated drugs, usually under
a different name than ours (e.g. cisplatin as "CIS-DDP", temozolomide as
"M-39831", erastin plainly as "ERASTIN" under its own separate CompoundID).
Naively bulk-importing every PortalCompounds.csv row would have created a
second, disconnected Drug identity for each of these -- and worse, once
ingest/prism_repurposing.py started attaching real monotherapy viability
data by BRD ID, that real data would have landed on the disconnected
duplicate instead of the curated row a user actually navigates to. This is
exactly the identity-fragmentation problem the `drug` table's own v2
docstring says it exists to prevent ("the same compound is named/IDed
differently across each [source library] ... rather than silently
fragmenting into duplicates"). CURATED_DRUG_ALIASES below (keyed by the
verified DPC- id, not by name-matching at runtime) makes sure the bulk
importer never creates these 11 rows, and ingest/prism_repurposing.py
redirects their real BRD-ID data to the correct curated drug_id instead.
Lomustine is not in the DepMap compound catalog under any name/synonym
checked (CCNU, CeeNU) -- absent, not fabricated an alias for.
"""

import csv
import os

from synlethality import config
from synlethality.ingest.base import IngestionStep, upsert_by_key
from synlethality.models import CellLine, Drug

DATA_DIR = os.path.join(config.DATA_DIR, "depmap")
MODEL_CSV = os.path.join(DATA_DIR, "Model.csv")
COMPOUNDS_CSV = os.path.join(DATA_DIR, "PortalCompounds.csv")

#: our curated cell_line_id -> DepMap StrippedCellLineName, hand-mapped and
#: verified against a real download of Model.csv (2026-09-22). Lines with no
#: DepMap match are omitted deliberately, not guessed.
CELL_LINE_STRIPPED_NAME = {
    "MCF7_BREAST": "MCF7",
    "T47D_BREAST": "T47D",
    "MDAMB231_BREAST": "MDAMB231",
    "MDAMB468_BREAST": "MDAMB468",
    "MCF10A_BREAST": "MCF10A",
    "U937_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE": "U937",
    "RKO_LARGE_INTESTINE": "RKO",
    "DU145_PROSTATE": "DU145",
    "A549_LUNG": "A549",
    "HELA_CERVIX": "HELA",
    "CASKI_CERVIX": "CASKI",
    "HCT116_LARGE_INTESTINE": "HCT116",
    "U87MG_CENTRAL_NERVOUS_SYSTEM": "U87MG",
    "T98G_CENTRAL_NERVOUS_SYSTEM": "T98G",
    # Deliberately absent, not guessed:
    #   4T1_BREAST -- murine line, outside DepMap's human-model scope
    #   HCT116P53NULL_LARGE_INTESTINE -- isogenic derivative DepMap doesn't
    #     track as a distinct ModelID from parental HCT116
}

#: DepMap CompoundID -> our curated drug_id, for the 12 curated drugs
#: DepMap's registry lists independently (usually under a different name --
#: see module docstring). Verified 2026-09-22 by exact name/synonym search
#: against a real download of PortalCompounds.csv. Used both to skip
#: creating a duplicate bulk Drug row here, and by
#: ingest/prism_repurposing.py to redirect real BRD-ID monotherapy data to
#: the correct curated drug_id. lomustine has no entry: genuinely absent
#: from this compound catalog under any name/synonym checked, not omitted
#: by mistake.
CURATED_DRUG_ALIASES = {
    "DPC-004121": "metformin",       # listed as "METFORMIN"
    "DPC-001793": "cisplatin",       # listed as "CIS-DDP"
    "DPC-002466": "oxaliplatin",     # listed as "ELOXATIN"
    "DPC-001479": "carboplatin",     # listed as "CARBOPLATIN"
    "DPC-002828": "5-fluorouracil",  # listed as "FLUOROURACIL"
    "DPC-004225": "mitomycin-c",     # listed as "MITOMYCIN"
    "DPC-002342": "doxorubicin",     # listed as "DOXORUBICIN"
    "DPC-004880": "paclitaxel",      # listed as "PACLITAXEL"
    "DPC-002562": "erastin",         # listed as "ERASTIN"
    "DPC-002004": "cyclophosphamide",  # listed as "CYCLOPHOSPHAMIDE"
    "DPC-006617": "triapine",        # listed as "TRIAPINE"
    "DPC-003981": "temozolomide",    # listed as "M-39831"
}


class DepmapPrismIngest(IngestionStep):
    step_name = "depmap_prism"
    source_study_tag = "depmap:24Q4-figshare-plus-27993248"

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.model_csv = os.path.join(data_dir, "Model.csv")
        self.compounds_csv = os.path.join(data_dir, "PortalCompounds.csv")

    def extract(self) -> list[dict]:
        if not (os.path.isfile(self.model_csv) and os.path.isfile(self.compounds_csv)):
            raise NotImplementedError(
                f"Model.csv / PortalCompounds.csv not found under {self.data_dir}. "
                "Download the DepMap 24Q4 Public release from Figshare+ "
                "(https://plus.figshare.com/articles/dataset/DepMap_24Q4_Public/27993248) "
                "via the public Figshare API (api.figshare.com/v2/articles/27993248 "
                "for the file manifest; depmap.org's own portal is Cloudflare-gated "
                "and cannot be fetched programmatically) and place both files there."
            )
        raw: list[dict] = []
        with open(self.model_csv, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                raw.append({"kind": "model_row", **row})
        with open(self.compounds_csv, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                raw.append({"kind": "compound_row", **row})
        return raw

    def transform(self, raw: list[dict]) -> dict:
        stripped_to_our_id = {v: k for k, v in CELL_LINE_STRIPPED_NAME.items()}
        cell_line_rows: list[dict] = []
        drug_rows: list[dict] = []

        for rec in raw:
            kind = rec.get("kind")
            if kind == "model_row":
                our_id = stripped_to_our_id.get(rec.get("StrippedCellLineName", ""))
                if our_id is None:
                    continue  # not one of our curated lines; never insert new ones here
                cell_line_rows.append({
                    "cell_line_id": our_id,
                    "oncotree_code": rec.get("OncotreeCode") or None,
                    "oncotree_primary_disease": rec.get("OncotreePrimaryDisease") or None,
                    "oncotree_subtype": rec.get("OncotreeSubtype") or None,
                })
            elif kind == "compound_row":
                compound_id = rec.get("CompoundID")
                if not compound_id:
                    continue
                if compound_id in CURATED_DRUG_ALIASES:
                    continue  # already a curated drug under a different name/id; never duplicate it
                synonyms_raw = (rec.get("Synonyms") or "").strip()
                synonyms = [s.strip() for s in synonyms_raw.split(";") if s.strip()]
                drug_rows.append({
                    "drug_id": compound_id,  # DepMap's own ID; see module docstring
                    "name": rec.get("CompoundName") or compound_id,
                    "drug_class": rec.get("TargetOrMechanism") or "",
                    "target": rec.get("GeneSymbolOfTargets") or "",
                    "source": "DepMap 24Q4 PortalCompounds.csv",
                    "synonyms": synonyms,
                    "pubchem_cid": rec.get("PubChemCID") or None,
                    "chembl_id": rec.get("ChEMBLID") or None,
                })

        return {"cell_line": cell_line_rows, "drug": drug_rows}

    def load(self, session, rows: dict) -> int:
        n = 0
        # Partial update only: every cell_line_id here already exists in the
        # curated seed (see transform()), so upsert_by_key's "existing"
        # branch (setattr per field present in the dict) is the only path
        # ever taken -- no new CellLine rows are created by this step.
        n += upsert_by_key(session, CellLine, "cell_line_id", rows["cell_line"])
        # Drug rows use DepMap's own CompoundID, which never collides with a
        # curated lowercase slug -- so this only ever inserts new rows,
        # never touches a hand-curated drug. Re-running is still idempotent
        # via upsert_by_key's key match on drug_id for previously-imported
        # DepMap rows.
        n += upsert_by_key(session, Drug, "drug_id", rows["drug"])
        return n

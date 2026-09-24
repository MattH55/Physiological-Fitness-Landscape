"""
Ingestion step: GEO expression datasets for non-pharmacological modifiers.

Real, working implementation (2026-09-22) for **GSE153830** only (glucose
deprivation / beta-hydroxybutyrate, MCF-7 & T47D, Zhang et al. 2021, PMID
33281976) -- the other series listed in SERIES remain structured stubs (see
"Status" below).

Source file: `GSE153830_FPKM_matrix_all_samples.txt`, downloaded 2026-09-22
from `ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE153nnn/GSE153830/suppl/` (no
gate -- NCBI GEO supplementary files are public). This is the study's own
published, already-normalized FPKM matrix, with per-sample Cell_Line/glucose
concentration/BHB concentration recorded directly in its header rows --
real metadata, not inferred from sample titles.

**What's computed, and what isn't**: per-gene log2 fold-change (mean FPKM of
the treatment group vs. the matched control group, both taken directly from
this real matrix, log2((treatment+1)/(control+1))) for the four (modifier,
cell_line) pairs GSE153830 actually covers (see SAMPLE_GROUPS). This is a
real but simplified differential-expression computation -- a proper pipeline
would fit a negative-binomial model on raw counts (e.g. DESeq2/edgeR); this
uses the study's own FPKM values and a mean-log-ratio, which is honest and
reproducible but not equivalent to that gold standard. Documented deviation,
same posture as scoring.py's ZIP-vs-SynergyFinder caveat elsewhere in this
codebase.

The resulting per-gene log2FC table feeds
`synlethality.signature_correlation.geneset_enrichment_score` against real
gene sets (ingest/msigdb.py) to backfill the numeric `score` field on the
matching `stress_signature_score` rows -- rows that, per seed_data.py's own
prior note, were carrying `score=None` specifically "pending pipeline
re-computation from raw counts." Only overwrites rows where a verified real
gene-set mapping exists (GENE_SET_BY_KEY below); a (modifier, cell_line)
pair with no mapped gene set is left at score=None, not filled with a
placeholder.

Status of the rest of SERIES: structured stubs -- GSE48398/GSE10043/GSE75127
(microarray/RAW.tar, need a different parsing path than GSE153830's
already-normalized FPKM matrix) are unchanged from the prior stub behavior;
extract() for those accessions still raises NotImplementedError.
GSE291296 (previously listed here as a hypoxia series) was removed
2026-09-22 -- re-verification found it isn't a hypoxia study at all (see
SERIES' inline comment); this codebase currently has no verified real GEO
series for the hypoxic modifier_type.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil

from synlethality import config
from synlethality.ingest.base import IngestionStep
from synlethality.ingest.msigdb import load_gene_set
from synlethality.models import StressSignatureScore
from synlethality.signature_correlation import geneset_enrichment_score

GEO_DATA_DIR = os.path.join(config.DATA_DIR, "geo")
DEG_CACHE_PATH = os.path.join(GEO_DATA_DIR, "computed_deg_cache.json")

SERIES = {
    "GSE153830": {
        "modifier_type": "dietary_metabolic",
        "citation": "pmid:33281976",
        "note": "glucose deprivation (5%, 96 h); BHB 10/25 mM, 96 h; MCF-7, T47D",
    },
    "GSE48398": {
        "modifier_type": "thermal",
        "citation": "pmid:27245201",
        "note": "42-45 degC heat shock; MCF-7, MDA-MB-231, MDA-MB-468 vs MCF-10A",
    },
    "GSE10043": {
        "modifier_type": "thermal",
        "citation": "pmid:18608577",
        "note": "41 degC/30 min mild hyperthermia; U-937; HSF1/Hsp40/Hsp70",
    },
    # GSE291296 removed 2026-09-22: re-verified directly against a real GEO
    # query and this accession is NOT a hypoxia study -- its real title is
    # "Omics analysis reveals striking effects of progesterone receptor on
    # mitochondria and mitochondria-mediated apoptosis independent of
    # caspases in Breast Cancer cells" (pmid:41444289; MCF-7 +/- PR agonist
    # R5020). "Hypoxia" appears only as one of several Hallmark pathways
    # noted as upregulated in its abstract -- not a hypoxia-modifier study
    # at all. Wrong from whenever this stub entry was first scoped; caught
    # here before any real ingestion ran against it (never reached
    # seed_data.py or any curated content -- verified by a full repo
    # search, so no live/deployed row was ever mis-cited). Net effect: this
    # project currently has **no verified real GEO series for the hypoxic
    # modifier_type** -- an honest gap, not a wrong citation. Replace this
    # entry only with a series independently re-verified end-to-end
    # (title, summary, and actual O2/hypoxia protocol in
    # Series_overall_design), the same way GSE153830 was checked.
    "GSE75127": {
        "modifier_type": "thermal",
        "citation": "geo:GSE75127",
        "note": ("BAG3 knockdown x hyperthermia sensitivity; oral squamous "
                 "cell carcinoma (spec seed list)"),
    },
    # Human physiological-response series registered 2026-09-24 with the
    # matching MODIFIERS rows. Stubs only: extract() still implements
    # GSE153830 alone. Titles were checked against GEO that day.
    "GSE55924": {"modifier_type": "dietary_metabolic", "citation": "pmid:25249505",
                 "note": "24 h fast, skeletal muscle, 12 healthy men"},
    "GSE28016": {"modifier_type": "dietary_metabolic", "citation": "pmid:21641545",
                 "note": "40 h fast vs fed, vastus lateralis, 7 adults"},
    "GSE129843": {"modifier_type": "dietary_metabolic", "citation": "pmid:32938935",
                  "note": "8 h vs 15 h feeding window, 5 days, vastus lateralis"},
    "GSE168705": {"modifier_type": "dietary_metabolic", "citation": "pmid:35912794",
                  "note": "10 h eating window, 8 weeks, adipose"},
    "GSE111551": {"modifier_type": "mechanical_radiative", "citation": "geo:GSE111551",
                  "note": "18-week running, muscle; pair with GSE111552 (PBMC)"},
    "GSE111552": {"modifier_type": "mechanical_radiative", "citation": "geo:GSE111552",
                  "note": "18-week running, PBMC; pair with GSE111551 (muscle)"},
    "GSE252357": {"modifier_type": "mechanical_radiative", "citation": "pmid:38586026",
                  "note": "acute resistance exercise time course, vastus lateralis"},
    "GSE3606": {"modifier_type": "mechanical_radiative", "citation": "pmid:16990507",
                "note": "moderate vs exhaustive treadmill, white blood cells"},
    "GSE156248": {"modifier_type": "thermal", "citation": "pmid:32887608",
                  "note": "10-day cold acclimation, 14-15 degC air, T2D muscle"},
    "GSE156247": {"modifier_type": "mechanical_radiative", "citation": "pmid:32887608",
                  "note": "12-week combined exercise, overweight men, muscle; subseries of GSE156249"},
    "GSE156249": {"modifier_type": "other", "citation": "pmid:32887608",
                  "note": "super series of GSE156248 (cold) and GSE156247 (exercise)"},
    "GSE85620": {"modifier_type": "thermal", "citation": "geo:GSE85620",
                 "note": "10-week strength training ± post-exercise CWI; water temperature not in GEO"},
    "GSE82323": {"modifier_type": "thermal", "citation": "pmid:27486743",
                 "note": "one series, three arms: ~73 degC chamber, passive vibration, NMES"},
    "GSE12474": {"modifier_type": "thermal", "citation": "pmid:20803152",
                 "note": "10-week local heat-and-steam sheet; temperature not stated"},
    "GSE90763": {"modifier_type": "thermal", "citation": "pmid:28842615",
                 "note": "sauna PBMC; abstract 75.7±0.86 degC, GEO summary 78±6 degC"},
    "GSE82093": {"modifier_type": "mechanical_radiative", "citation": "pmid:27669902",
                 "note": "blue light 452 nm, 30 min, 41.4 J/cm2, HaCaT, 24 h"},
    "GSE89083": {"modifier_type": "mechanical_radiative", "citation": "geo:GSE89083",
                 "note": "blue light 7.5 min, 10.35 J/cm2, HaCaT; no PMID on the GEO record"},
    "GSE39170": {"modifier_type": "mechanical_radiative", "citation": "pmid:22931923",
                 "note": "broadband light, human skin, 3-seq"},
}

#: (modifier_id, cell_line_id) -> real sample-group definition, read directly
#: off GSE153830_FPKM_matrix_all_samples.txt's own header rows (Cell_Line,
#: "glucose concentration [g/l]", "beta-hydroxybutyrate [mM]"), verified
#: 2026-09-22 against a real download. `key` matches seed_data.py's
#: SIGNATURE_SCORES entry so the right stress_signature_score row is
#: updated, not guessed by (modifier_id, cell_line_id) alone (both are
#: unique together here, but the explicit key keeps this auditable).
SAMPLE_GROUPS = {
    ("MOD-GLUCOSE-RESTRICT-5PCT-96H", "T47D_BREAST"): {
        "key": "t47d_glucose_nrf2",
        "cell_line": "T47D",
        "treatment": {"glucose": 0.225, "bhb": 0},
        "control": {"glucose": 4.5, "bhb": 0},
        "gene_set_key": "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY",
    },
    ("MOD-GLUCOSE-RESTRICT-5PCT-96H", "MCF7_BREAST"): {
        "key": "mcf7_glucose_hippo",
        "cell_line": "MCF_7",
        "treatment": {"glucose": 0.225, "bhb": 0},
        "control": {"glucose": 4.5, "bhb": 0},
        "gene_set_key": "KEGG_HIPPO_SIGNALING_PATHWAY",
    },
    ("MOD-BHB-10MM-96H", "MCF7_BREAST"): {
        "key": "mcf7_bhb10_null",
        "cell_line": "MCF_7",
        "treatment": {"glucose": 0.225, "bhb": 10},
        "control": {"glucose": 0.225, "bhb": 0},  # glucose-deprived baseline, isolates BHB
        "gene_set_key": "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY",
    },
    ("MOD-BHB-25MM-96H", "T47D_BREAST"): {
        "key": "t47d_bhb25_null",
        "cell_line": "T47D",
        "treatment": {"glucose": 0.225, "bhb": 25},
        "control": {"glucose": 0.225, "bhb": 0},
        "gene_set_key": "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY",
    },
}

SOURCE_TAG = "geo:GSE153830 FPKM matrix (Zhang et al. 2021, pmid:33281976); log2FC computed here"


class GEOModifierIngest(IngestionStep):
    step_name = "geo_modifiers"

    def __init__(self, accession: str,
                 data_dir: str = GEO_DATA_DIR,
                 gene_set_cache_path: str | None = None):
        if accession not in SERIES:
            raise ValueError(f"Unregistered GEO accession '{accession}'. "
                             f"Known: {sorted(SERIES)}")
        self.accession = accession
        self.source_study_tag = f"geo:{accession}"
        self.matrix_path = os.path.join(data_dir, accession, "FPKM_matrix.txt")
        self.matrix_gz_path = self.matrix_path + ".gz"
        self.gene_set_cache_path = gene_set_cache_path

    def extract(self) -> list[dict]:
        if self.accession != "GSE153830":
            raise NotImplementedError(
                f"GEO DEG computation not implemented for {self.accession} yet "
                "(only GSE153830 has a real, reviewed parsing path -- see "
                "module docstring). Known accessions with a real pipeline: "
                "['GSE153830']."
            )
        if not os.path.isfile(self.matrix_path):
            if os.path.isfile(self.matrix_gz_path):
                with gzip.open(self.matrix_gz_path, "rb") as src, \
                        open(self.matrix_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                raise NotImplementedError(
                    f"{self.matrix_path} not found. Download "
                    "GSE153830_FPKM_matrix_all_samples.txt.gz from "
                    "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE153nnn/GSE153830/suppl/ "
                    f"into {os.path.dirname(self.matrix_path)}/."
                )

        with open(self.matrix_path, encoding="utf-8") as fh:
            sample_ids = fh.readline().rstrip("\n").split("\t")[2:]
            cell_lines = fh.readline().rstrip("\n").split("\t")[2:]
            glucose = [float(v) for v in fh.readline().rstrip("\n").split("\t")[2:]]
            bhb = [float(v) for v in fh.readline().rstrip("\n").split("\t")[2:]]
            fh.readline()  # "gene_id\tgene_name\tFPKM\t..." column-type row

            sample_meta = [
                {"sample_id": sid, "cell_line": cl, "glucose": g, "bhb": b}
                for sid, cl, g, b in zip(sample_ids, cell_lines, glucose, bhb)
            ]

            gene_fpkm: dict[str, list[float]] = {}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                gene_name = parts[1]
                if not gene_name:
                    continue
                values = [float(v) for v in parts[2:]]
                # A few gene_ids share a gene_name (multi-mapped loci); sum
                # FPKM across them, matching how the study's own downstream
                # pathway analysis would treat one gene symbol.
                if gene_name in gene_fpkm:
                    gene_fpkm[gene_name] = [a + b for a, b in zip(gene_fpkm[gene_name], values)]
                else:
                    gene_fpkm[gene_name] = values

        return [{"sample_meta": sample_meta, "gene_fpkm": gene_fpkm}]

    def transform(self, raw: list[dict]) -> list[dict]:
        sample_meta = raw[0]["sample_meta"]
        gene_fpkm = raw[0]["gene_fpkm"]
        rows = []
        for (modifier_id, cell_line_id), group in SAMPLE_GROUPS.items():
            treat_idx = [
                i for i, s in enumerate(sample_meta)
                if s["cell_line"] == group["cell_line"]
                and s["glucose"] == group["treatment"]["glucose"]
                and s["bhb"] == group["treatment"]["bhb"]
            ]
            ctrl_idx = [
                i for i, s in enumerate(sample_meta)
                if s["cell_line"] == group["cell_line"]
                and s["glucose"] == group["control"]["glucose"]
                and s["bhb"] == group["control"]["bhb"]
            ]
            if not treat_idx or not ctrl_idx:
                raise ValueError(
                    f"No matching samples for {modifier_id}/{cell_line_id} "
                    f"(treatment idx={treat_idx}, control idx={ctrl_idx}) -- "
                    "SAMPLE_GROUPS no longer matches the real sample sheet.")

            gene_log2fc: dict[str, float] = {}
            for gene, values in gene_fpkm.items():
                treat_mean = sum(values[i] for i in treat_idx) / len(treat_idx)
                ctrl_mean = sum(values[i] for i in ctrl_idx) / len(ctrl_idx)
                gene_log2fc[gene] = _log2_ratio(treat_mean, ctrl_mean)

            rows.append({
                "modifier_id": modifier_id,
                "cell_line_id": cell_line_id,
                "key": group["key"],
                "gene_set_key": group["gene_set_key"],
                "gene_log2fc": gene_log2fc,
                "n_treatment_samples": len(treat_idx),
                "n_control_samples": len(ctrl_idx),
            })
        return rows

    def load(self, session, rows: list[dict]) -> int:
        n = 0
        deg_cache = {}
        if os.path.isfile(DEG_CACHE_PATH):
            with open(DEG_CACHE_PATH, encoding="utf-8") as fh:
                deg_cache = json.load(fh)
        for r in rows:
            try:
                gene_set = load_gene_set(
                    r["gene_set_key"],
                    **({"cache_path": self.gene_set_cache_path} if self.gene_set_cache_path else {}),
                )
            except (FileNotFoundError, KeyError) as exc:
                raise NotImplementedError(
                    f"Gene set '{r['gene_set_key']}' not in the local MSigDB "
                    "cache -- run ingest.msigdb.MSigDBIngest first."
                ) from exc

            result = geneset_enrichment_score(r["gene_log2fc"], gene_set)

            score_row = (
                session.query(StressSignatureScore)
                .filter_by(modifier_id=r["modifier_id"], cell_line_id=r["cell_line_id"])
                .one_or_none()
            )
            if score_row is None:
                raise NotImplementedError(
                    f"No curated stress_signature_score row for "
                    f"({r['modifier_id']}, {r['cell_line_id']}) -- this "
                    "ingestion step only backfills an existing curated row, "
                    "it never creates a new one.")

            score_row.score = result["score"]
            score_row.raw_deg_evidence_ref = SOURCE_TAG
            caveat = (
                "This is a simple, uncorrected standardized-mean-difference "
                "statistic, not the paper's own (likely multiple-testing-"
                "corrected) pathway enrichment test -- a large |z| here does "
                "not necessarily mean the paper would call it significant, "
                "and vice versa. Treat as a real, reproducible number, not a "
                "replication of the paper's own significance call."
            )
            score_row.notes = (
                f"{score_row.notes.split(' [Real DEG backfill')[0].rstrip()} "
                f"[Real DEG backfill 2026-09-22: ssGSEA-style z-score "
                f"{result['score']:.3f} for gene set '{r['gene_set_key']}' "
                f"({result['n_genes_in_set']} genes measured), computed from "
                f"{r['n_treatment_samples']} treatment vs "
                f"{r['n_control_samples']} control real GSE153830 samples. "
                f"{caveat} See synlethality/signature_correlation.py for the "
                "method and its documented deviation from ssGSEA/GSVA proper.]"
            ).strip()
            # Persist the full real per-gene log2FC table (not just this one
            # gene set's enrichment score) so a later, separate correlation
            # step (synlethality.signature_correlation.xsum_correlation, run
            # against a real drug-side LINCS signature in the same cell
            # line -- see ingest/lincs_l1000.py) can use the modifier's real
            # signature without recomputing it from the raw matrix.
            deg_cache[r["key"]] = {
                "modifier_id": r["modifier_id"],
                "cell_line_id": r["cell_line_id"],
                "gene_log2fc": r["gene_log2fc"],
                "source": SOURCE_TAG,
            }
            n += 1
        os.makedirs(os.path.dirname(DEG_CACHE_PATH), exist_ok=True)
        with open(DEG_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(deg_cache, fh)
        return n


def load_deg_cache(key: str, cache_path: str = DEG_CACHE_PATH) -> dict:
    """Real per-gene log2FC table for a SAMPLE_GROUPS `key` (e.g.
    "mcf7_glucose_hippo"), written by GEOModifierIngest.load(). Raises
    FileNotFoundError/KeyError if not yet computed -- callers must run
    GEOModifierIngest first, never fall back to a fabricated signature."""
    with open(cache_path, encoding="utf-8") as fh:
        cache = json.load(fh)
    return cache[key]


def _log2_ratio(treatment: float, control: float, pseudocount: float = 1.0) -> float:
    import math
    return math.log2((treatment + pseudocount) / (control + pseudocount))

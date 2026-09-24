"""
Ingestion step: MSigDB/KEGG stress-relevant gene-set panels.

Pulls the gene sets used to compute real numeric `stress_signature_score`
values (Prediction Methodology Stage 1 -- see PREDICTION_METHODOLOGY.md and
synlethality/signature_correlation.py):
  - ISR/UPR (integrated stress response / unfolded protein response)
  - NRF2 / ferroptosis (see also FerrDB)
  - HSF1 / heat-shock protein
  - DNA damage
  - Senescence
  - Hippo signaling (not a Hallmark collection; needed specifically for the
    GSE153830 MCF-7 glucose-deprivation finding, see GENE_SET_OVERRIDES)

**Source, and why this isn't the originally-planned gsea-msigdb.org
download**: gsea-msigdb.org gates its GMT downloads behind a free-account
login, which this session cannot register for. Enrichr
(maayanlab.cloud/Enrichr) redistributes the same MSigDB Hallmark collection
(as "MSigDB_Hallmark_2020") and the KEGG 2021 Human collection as public,
ungated, plain-text gene-set libraries -- a legitimate, commonly-cited
mirror (Enrichr is itself a widely-used, peer-reviewed enrichment tool; its
gene-set libraries are the same sets other tools query it for). Real gene
lists, not reconstructed or guessed. Fetched via
`https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName=<lib>`.

Note the naming mismatch this required resolving: Enrichr's
"MSigDB_Hallmark_2020" library uses title-case display names (e.g.
"Reactive Oxygen Species Pathway"), not MSigDB's own systematic identifiers
(HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY). GENE_SET_OVERRIDES below maps
our systematic keys to the exact Enrichr display name to fetch, verified by
direct lookup against the real downloaded library (2026-09-22) -- not
guessed from the naming convention.

Status: real, working ingestion (2026-09-22) for the two gene sets actually
consumed this session (see ingest/geo_modifiers.py); extract() fetches only
what PANEL_GENE_SETS/GENE_SET_OVERRIDES reference, not the full library, to
avoid pulling and caching genesets nothing here uses yet. Gene sets are a
lookup resource, not interaction evidence, so they land in a local JSON
cache (data/msigdb/gene_sets_cache.json), not a database table.
"""

from __future__ import annotations

import json
import os

from synlethality import config
from synlethality.ingest.base import IngestionStep

DATA_DIR = os.path.join(config.DATA_DIR, "msigdb")
CACHE_PATH = os.path.join(DATA_DIR, "gene_sets_cache.json")

#: panel -> candidate MSigDB Hallmark collections (curator-reviewed). Systematic
#: MSigDB names, resolved to an actual Enrichr library+set via
#: GENE_SET_OVERRIDES (Enrichr doesn't use MSigDB's systematic naming).
PANEL_GENE_SETS = {
    "isr_upr": ["HALLMARK_UNFOLDED_PROTEIN_RESPONSE", "HALLMARK_PEROXISOME"],
    "nrf2_ferroptosis": ["HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY"],
    "hsf1_hsp": ["HALLMARK_UV_RESPONSE_UP"],  # placeholder; HSF1 regulon from literature
    "dna_damage": ["HALLMARK_DNA_REPAIR", "HALLMARK_P53_PATHWAY", "HALLMARK_G2M_CHECKPOINT"],
    "senescence": ["HALLMARK_SENESCENCE*", "FRIDMAN_SENESCENCE_UP"],
}

#: our systematic gene-set key -> (Enrichr library, Enrichr display name),
#: verified 2026-09-22 by direct lookup against the real downloaded library
#: text (not guessed from naming convention). Only sets actually fetched
#: this session are listed; extend as more panels get real ingestion.
GENE_SET_OVERRIDES = {
    "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY": (
        "MSigDB_Hallmark_2020", "Reactive Oxygen Species Pathway"),
    # Not a Hallmark collection -- KEGG. Needed specifically because the
    # GSE153830 paper (Zhang et al. 2021, PMID 33281976) reports Hippo
    # pathway involvement in glucose-deprived MCF-7 specifically (no Hippo
    # panel exists in the signature_panel enum; see seed_data.py's
    # mcf7_glucose_hippo entry, panel=other).
    "KEGG_HIPPO_SIGNALING_PATHWAY": (
        "KEGG_2021_Human", "Hippo signaling pathway"),
}


def _fetch_library_text(library: str) -> str:
    import requests

    url = f"https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName={library}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.text


def _parse_library(text: str) -> dict[str, list[str]]:
    sets: dict[str, list[str]] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        genes = [g.strip() for g in parts[2:] if g.strip()]
        sets[parts[0]] = genes
    return sets


class MSigDBIngest(IngestionStep):
    step_name = "msigdb"
    source_study_tag = "msigdb:enrichr-mirror-2020-2021"

    def __init__(self, cache_path: str = CACHE_PATH, gene_set_keys: list[str] | None = None):
        self.cache_path = cache_path
        # Default to only the gene sets a real consumer (geo_modifiers.py)
        # actually needs -- avoids pulling/caching whole libraries unused.
        self.gene_set_keys = gene_set_keys or list(GENE_SET_OVERRIDES)

    def extract(self) -> list[dict]:
        unknown = [k for k in self.gene_set_keys if k not in GENE_SET_OVERRIDES]
        if unknown:
            raise NotImplementedError(
                f"No verified Enrichr mapping for gene-set key(s) {unknown}. "
                "Add a (library, display_name) entry to "
                "GENE_SET_OVERRIDES, verified against a real download, "
                "before fetching it here."
            )
        raw: list[dict] = []
        library_cache: dict[str, dict[str, list[str]]] = {}
        for key in self.gene_set_keys:
            library, display_name = GENE_SET_OVERRIDES[key]
            if library not in library_cache:
                library_cache[library] = _parse_library(_fetch_library_text(library))
            genes = library_cache[library].get(display_name)
            if genes is None:
                raise NotImplementedError(
                    f"'{display_name}' not found in Enrichr library '{library}' "
                    f"-- the verified mapping in GENE_SET_OVERRIDES for '{key}' "
                    "no longer matches the live library; re-verify before use."
                )
            raw.append({
                "key": key,
                "library": library,
                "display_name": display_name,
                "genes": genes,
            })
        return raw

    def transform(self, raw: list[dict]) -> list[dict]:
        return raw

    def load(self, session, rows: list[dict]) -> int:
        """Writes to the local JSON cache, not the database -- gene sets are
        a lookup resource for signature_correlation.py, not interaction
        evidence. `session`/`IngestionRun` bookkeeping is still used (via
        IngestionStep.run()) so a bad/retracted gene-set source is tracked
        the same way as every other ingestion step."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        cache = {}
        if os.path.isfile(self.cache_path):
            with open(self.cache_path, encoding="utf-8") as fh:
                cache = json.load(fh)
        for r in rows:
            cache[r["key"]] = {
                "library": r["library"],
                "display_name": r["display_name"],
                "genes": r["genes"],
                "source": self.source_study_tag,
            }
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=1)
        return len(rows)


def load_gene_set(key: str, cache_path: str = CACHE_PATH) -> set[str]:
    """Real gene set for `key` (e.g. "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY"),
    from the local cache MSigDBIngest wrote. Raises FileNotFoundError/KeyError
    if the cache or key isn't present -- callers must run MSigDBIngest first,
    never fall back to a fabricated gene list."""
    with open(cache_path, encoding="utf-8") as fh:
        cache = json.load(fh)
    return set(cache[key]["genes"])

"""Load modifier signatures into MIGEP objects."""
from __future__ import annotations
import json
import os
from src.data.expression import load_genes_978
from src.data.expression_migep import MIGEP, map_to_978, robust_z_normalize, load_expression_profile
from src.data.modifier import ModifierProfile
from src.data.context import resolve_context


def load_signature_library(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def signatures_to_migeps(library_path, genes_path, reference_dir):
    """Real modifier MIGEPs from this project's own Phase 1 signature
    library (synlethality/, data/modifier_signatures/library.json).

    Uses each entry's `normalized_vector`, not the raw `vector` -- the
    library's 33 real signatures come from heterogeneous raw sources
    (microarray log2FC, LINCS clue.io z-scores, DepMap expression) on
    incompatible native scales; `normalized_vector` is the already-
    computed, per-signature robust z-score (Phase 0's harmonization,
    synlethality.signature_space.register_signature) that makes them
    comparable at all. Using the raw `vector` here (an earlier version of
    this function did) would silently reintroduce that scale mismatch --
    caught 2026-09-27, fixed rather than left as a latent inconsistency.
    """
    gene_symbols = load_genes_978(genes_path)
    library = load_signature_library(library_path)
    migeps = []
    for entry in library.get("signatures", []):
        sig_id = entry.get("signature_id", "")
        cell_line = entry.get("cell_line_name", "")
        vector_raw = entry.get("normalized_vector", [])
        if not vector_raw or len(vector_raw) != 978:
            continue
        zero_vec = [0.0] * 978
        migep = MIGEP(treated_values=vector_raw, control_values=zero_vec,
                      gene_symbols=gene_symbols, modifier_id=sig_id,
                      protocol=entry.get("condition_id", ""),
                      biological_context=resolve_context(cell_line),
                      tissue=cell_line, study_id=entry.get("geo_accession", ""),
                      dose=entry.get("dose", {}),
                      duration_hr=entry.get("dose", {}).get("duration_hr"),
                      timepoint_hr=entry.get("timepoint_hr"),
                      platform=entry.get("platform", ""),
                      n_replicates=max(entry.get("n_treatment_samples", 0), 1))
        migeps.append(migep)
    return migeps


def load_modifier_profiles(modifier_profiles_dir, genes_path):
    gene_symbols = load_genes_978(genes_path)
    profiles = {}
    if not os.path.isdir(modifier_profiles_dir):
        return profiles
    for modifier_dir in os.listdir(modifier_profiles_dir):
        full = os.path.join(modifier_profiles_dir, modifier_dir)
        if not os.path.isdir(full):
            continue
        migep_csv = os.path.join(full, "migep.csv")
        meta_json = os.path.join(full, "metadata.json")
        if not os.path.isfile(migep_csv):
            continue
        migep_dict = load_expression_profile(migep_csv)
        vector, coverage, n_present = map_to_978(migep_dict, gene_symbols, 0.0)
        vector = robust_z_normalize(vector)
        metadata = {}
        if os.path.isfile(meta_json):
            with open(meta_json, encoding="utf-8") as f:
                metadata = json.load(f)
        profiles[modifier_dir] = ModifierProfile(
            modifier_id=modifier_dir, protocol=metadata.get("protocol", ""),
            biological_context=metadata.get("biological_context", ""),
            tissue=metadata.get("tissue", ""), study_id=metadata.get("study_id", ""),
            species=metadata.get("species", "human"), dose=metadata.get("dose", {}),
            duration_hr=metadata.get("duration_hr"),
            timepoint_hr=metadata.get("timepoint_hr"),
            platform=metadata.get("platform", ""),
            n_replicates=metadata.get("n_replicates", 1),
            quality_score=float(metadata.get("quality_score", coverage)),
            migep_vector=vector, gene_symbols=gene_symbols,
            migep_source=metadata.get("migep_source", "experimental"),
            metadata=metadata)
    return profiles
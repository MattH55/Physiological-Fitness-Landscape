"""Biological context registry."""
BUILTIN_CONTEXTS = {
    "skeletal_muscle": {"id": "skeletal_muscle", "name": "skeletal muscle", "tissue": "skeletal muscle"},
    "blood": {"id": "blood", "name": "peripheral blood", "tissue": "blood"},
    "adipose": {"id": "adipose", "name": "adipose tissue", "tissue": "adipose"},
    "liver": {"id": "liver", "name": "liver", "tissue": "liver"},
    "mcf7": {"id": "mcf7", "name": "MCF-7 breast cancer", "tissue": "breast", "cell_line": "MCF-7"},
    "t47d": {"id": "t47d", "name": "T-47D breast cancer", "tissue": "breast", "cell_line": "T-47D"},
    "a549": {"id": "a549", "name": "A549 lung", "tissue": "lung", "cell_line": "A549"},
    # Added 2026-09-27 to cover the real cell lines in this project's own
    # Phase 1 modifier library (data/modifier_signatures/library.json) --
    # without these, resolve_context() silently passed each name through
    # unchanged (inconsistent casing, no tissue grouping), which would
    # fragment leave-contexts-out validation rather than erroring loudly.
    "mcf10a": {"id": "mcf10a", "name": "MCF-10A mammary epithelial", "tissue": "breast", "cell_line": "MCF-10A"},
    "mdamb231": {"id": "mdamb231", "name": "MDA-MB-231 breast cancer", "tissue": "breast", "cell_line": "MDA-MB-231"},
    "mdamb468": {"id": "mdamb468", "name": "MDA-MB-468 breast cancer", "tissue": "breast", "cell_line": "MDA-MB-468"},
    "u87mg": {"id": "u87mg", "name": "U87MG glioblastoma", "tissue": "brain", "cell_line": "U87MG"},
    "u937": {"id": "u937", "name": "U937 histiocytic lymphoma", "tissue": "blood", "cell_line": "U937"},
    "lovo": {"id": "lovo", "name": "LoVo colon adenocarcinoma", "tissue": "colon", "cell_line": "LoVo"},
    "hsc3": {"id": "hsc3", "name": "HSC-3 oral squamous cell carcinoma", "tissue": "oral", "cell_line": "HSC-3"},
}
CONTEXT_ALIASES = {
    "skeletal_muscle": "skeletal_muscle", "muscle": "skeletal_muscle",
    "vastus_lateralis": "skeletal_muscle", "skeletal muscle": "skeletal_muscle",
    "human_skeletal_muscle": "skeletal_muscle", "human_vastus_lateralis": "skeletal_muscle",
    "blood": "blood", "pbmc": "blood", "human_pbmc": "blood",
    "human_white_blood_cells": "blood", "white_blood_cells": "blood", "wbc": "blood",
    "adipose": "adipose", "adipose_tissue": "adipose", "human_adipose": "adipose",
    "liver": "liver", "mcf7": "mcf7", "mcf-7": "mcf7", "mcf_7": "mcf7",
    "t47d": "t47d", "t-47d": "t47d", "a549": "a549", "a549_lung": "a549",
    "mcf10a": "mcf10a", "mcf-10a": "mcf10a", "mcf_10a": "mcf10a",
    "mdamb231": "mdamb231", "mda-mb-231": "mdamb231",
    "mdamb468": "mdamb468", "mda-mb-468": "mdamb468",
    "u87mg": "u87mg", "u937": "u937", "lovo": "lovo",
    "hsc3": "hsc3", "hsc-3": "hsc3",
}


def resolve_context(name: str) -> str:
    key = name.strip().lower().replace(" ", "_")
    return CONTEXT_ALIASES.get(key, name.strip())
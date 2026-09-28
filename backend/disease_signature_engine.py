"""
Disease Signature & Combined-Panel Intelligence Engine.
Aggregates disease alterations (Type A-E: Molecular, Lab/Clinical, Scales/PROs, Pathology, Functional)
into structured Disease Signatures and provides multi-metric similarity scoring (Jaccard, Cosine, Weighted Overlap)
for comparing disease pathophysiological profiles and identifying biomarker overlaps.
"""

from typing import Dict, List, Any, Optional, Set, Tuple, Union
import math
from collections import defaultdict
from sqlalchemy.orm import Session

from backend.models import Disease, DiseaseAlteration, Biomarker


def build_disease_signatures(db_session: Session) -> Dict[Union[int, str], Any]:
    """
    Builds structured signature objects for all diseases in the database.
    Returns dictionary indexed by disease ID (or slug).
    """
    diseases = db_session.query(Disease).all()
    all_biomarkers = db_session.query(Biomarker).all()
    b_id_to_slug = {b.id: b.slug for b in all_biomarkers}
    b_id_to_name = {b.id: b.name for b in all_biomarkers}

    signatures = {}

    for d in diseases:
        alterations = db_session.query(DiseaseAlteration).filter_by(disease_id=d.id).all()
        
        panel_dict = {}
        panel_list = []
        by_type = {
            "Functional": [],
            "Lab / Clinical": [],
            "Pathology": [],
            "Scales & PROs": [],
            "Molecular": []
        }
        type_a_molecular = []
        type_b_clinical = []
        type_c_scales = []
        type_d_pathology = []
        type_e_functional = []
        
        biomarker_vector = {}

        # Sort alterations so gene alterations (subtype 'Gene') are LOWEST priority.
        # Non-gene alterations come first; gene alterations are pushed to the end.
        sorted_alterations = sorted(
            alterations,
            key=lambda a: (1 if (a.subtype or "").strip().lower() == "gene" else 0, (a.name or "").lower())
        )

        for alt in sorted_alterations:
            type_key = alt.alteration_type if alt.alteration_type in by_type else "Lab / Clinical"
            alt_info = {
                "id": alt.id,
                "name": alt.name,
                "sub_name": alt.sub_name,
                "subtype": alt.subtype,
                "direction": alt.direction or "Abnormal",
                "evidence_level": alt.evidence_level or "Moderate",
                "frequency": alt.frequency or "—",
                "is_biomarker_match": bool(alt.is_biomarker_match),
                "biomarker_slug": alt.biomarker.slug if alt.biomarker else None,
                "biomarker_name": alt.biomarker.name if alt.biomarker else None
            }
            by_type[type_key].append(alt_info)

            if "Molecular" in type_key or alt.alteration_type == "Type A - Molecular":
                type_a_molecular.append(alt.name)
            elif "Lab" in type_key or "Clinical" in type_key or alt.alteration_type == "Type B - Lab/Clinical":
                type_b_clinical.append(alt.name)
            elif "Scale" in type_key or "PRO" in type_key or alt.alteration_type == "Type C - Scales/PROs":
                type_c_scales.append(alt.name)
            elif "Pathology" in type_key or alt.alteration_type == "Type D - Pathology":
                type_d_pathology.append(alt.name)
            elif "Functional" in type_key or alt.alteration_type == "Type E - Functional":
                type_e_functional.append(alt.name)

            if alt.biomarker_id or alt.is_biomarker_match:
                b_slug = b_id_to_slug.get(alt.biomarker_id) or (alt.name.lower().replace(" ", "_").replace("-", "_"))
                dir_str = (alt.direction or "").lower()
                
                if any(x in dir_str for x in ["elevated", "increased", "upregulated", "high"]):
                    dir_val = 1.0
                    dir_clean = "elevated"
                elif any(x in dir_str for x in ["reduced", "decreased", "downregulated", "low"]):
                    dir_val = -1.0
                    dir_clean = "reduced"
                else:
                    dir_val = 0.5
                    dir_clean = "abnormal"

                ev_weight = 1.2 if alt.evidence_level == "High" else (0.8 if alt.evidence_level == "Low" else 1.0)
                biomarker_vector[b_slug] = dir_val * ev_weight
                
                panel_item = {
                    "biomarker_id": alt.biomarker_id,
                    "biomarker_slug": b_slug,
                    "biomarker_name": b_id_to_name.get(alt.biomarker_id, alt.name),
                    "direction": dir_clean,
                    "direction_weight": dir_val,
                    "evidence": alt.evidence_level or "Moderate",
                    "evidence_level": alt.evidence_level or "Moderate",
                    "alteration_name": alt.name,
                    "alteration_type": alt.alteration_type
                }
                panel_list.append(panel_item)
                panel_dict[b_slug] = {
                    "direction": dir_clean,
                    "evidence": alt.evidence_level or "Moderate"
                }

        type_counts = {k: len(v) for k, v in by_type.items()}

        sig_data = {
            "id": d.id,
            "disease_id": d.id,
            "slug": d.slug,
            "name": d.name,
            "disease_name": d.name,
            "category": d.category,
            "us_dalys": d.us_dalys,
            "global_dalys": d.global_dalys,
            "us_mortality": d.us_mortality,
            "global_mortality": d.global_mortality,
            "spontaneous_remission": d.spontaneous_remission,
            "best_intervention_remission": d.best_intervention_remission,
            "gap_size": d.gap_size,
            "biomarker_panel": panel_dict,
            "panel_list": panel_list,
            "panel_size": len(panel_dict),
            "alterations_by_type": by_type,
            "type_counts": type_counts,
            "alterations_count": len(alterations),
            "total_alterations": len(alterations),
            "type_a_molecular": type_a_molecular,
            "type_b_clinical": type_b_clinical,
            "type_c_scales": type_c_scales,
            "type_d_pathology": type_d_pathology,
            "type_e_functional": type_e_functional,
            "biomarker_vector": biomarker_vector
        }
        signatures[d.id] = sig_data
        # also index by slug for convenient lookup
        signatures[d.slug] = sig_data

    # Return dictionary keyed by ID (or slug)
    return signatures


def compute_disease_similarity(
    sig_a: Dict[str, Any],
    sig_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes multi-scale similarity between two disease signatures:
    1. Biomarker Jaccard Similarity: overlap of mapped biomarkers (|A ∩ B| / |A ∪ B|)
    2. Biomarker Cosine Similarity: directional alignment of shared biomarkers
    3. Type A-E Alteration Jaccard: textual / subtype overlap across all 5 scale types
    4. Composite Pathophysiological Similarity Score (0.0 to 1.0)
    """
    # Extract biomarker panel dictionaries / vectors
    panel_a = sig_a.get("biomarker_panel", {})
    panel_b = sig_b.get("biomarker_panel", {})

    # Vector representations
    vec_a = sig_a.get("biomarker_vector", {})
    vec_b = sig_b.get("biomarker_vector", {})

    if isinstance(panel_a, dict) and not vec_a:
        vec_a = {k: 1.0 if (isinstance(v, dict) and v.get("direction") == "elevated") else (-1.0 if isinstance(v, dict) and v.get("direction") == "reduced" else 0.5) for k, v in panel_a.items()}
    if isinstance(panel_b, dict) and not vec_b:
        vec_b = {k: 1.0 if (isinstance(v, dict) and v.get("direction") == "elevated") else (-1.0 if isinstance(v, dict) and v.get("direction") == "reduced" else 0.5) for k, v in panel_b.items()}

    keys_a = set(vec_a.keys())
    keys_b = set(vec_b.keys())

    # 1. Biomarker Jaccard
    intersection_keys = keys_a.intersection(keys_b)
    union_keys = keys_a.union(keys_b)
    
    biomarker_jaccard = len(intersection_keys) / len(union_keys) if union_keys else 0.0

    # 2. Biomarker Cosine Similarity
    if union_keys:
        dot_product = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in union_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values())) if vec_a else 1e-9
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values())) if vec_b else 1e-9
        biomarker_cosine = dot_product / (norm_a * norm_b) if (norm_a * norm_b) > 0 else 0.0
        biomarker_cosine_norm = max(0.0, min(1.0, (biomarker_cosine + 1.0) / 2.0))
    else:
        biomarker_cosine_norm = 0.0

    # 3. Alteration Name & Type Overlap
    all_names_a = set()
    all_names_b = set()

    # check type_a_molecular ... type_e_functional
    for field in ["type_a_molecular", "type_b_clinical", "type_c_scales", "type_d_pathology", "type_e_functional"]:
        for item in sig_a.get(field, []):
            all_names_a.add(str(item).lower())
        for item in sig_b.get(field, []):
            all_names_b.add(str(item).lower())

    for t in sig_a.get("alterations_by_type", {}).values():
        for alt in t:
            if isinstance(alt, dict) and "name" in alt:
                all_names_a.add(alt["name"].lower())
    for t in sig_b.get("alterations_by_type", {}).values():
        for alt in t:
            if isinstance(alt, dict) and "name" in alt:
                all_names_b.add(alt["name"].lower())

    alt_intersection = all_names_a.intersection(all_names_b)
    alt_union = all_names_a.union(all_names_b)
    alteration_jaccard = len(alt_intersection) / len(alt_union) if alt_union else 0.0

    # 4. Composite Score
    # Weight: 50% Biomarker Jaccard, 30% Directional Cosine, 20% Alteration Jaccard (or vice versa)
    composite_similarity = (
        0.50 * biomarker_cosine_norm +
        0.30 * biomarker_jaccard +
        0.20 * alteration_jaccard
    )

    shared_biomarkers = list(intersection_keys)
    shared_biomarkers_detail = []
    for k in intersection_keys:
        dir_a = "elevated" if vec_a.get(k, 0) > 0 else "reduced"
        dir_b = "elevated" if vec_b.get(k, 0) > 0 else "reduced"
        shared_biomarkers_detail.append({
            "biomarker_slug": k,
            "direction_in_disease_a": dir_a,
            "direction_in_disease_b": dir_b,
            "concordant": (vec_a.get(k, 0) > 0 and vec_b.get(k, 0) > 0) or (vec_a.get(k, 0) < 0 and vec_b.get(k, 0) < 0)
        })

    d_a_name = sig_a.get("disease_name") or sig_a.get("name", "Unknown")
    d_b_name = sig_b.get("disease_name") or sig_b.get("name", "Unknown")
    d_a_slug = sig_a.get("slug", str(sig_a.get("disease_id", "")))
    d_b_slug = sig_b.get("slug", str(sig_b.get("disease_id", "")))

    return {
        "disease_a": d_a_name,
        "disease_b": d_b_name,
        "disease_a_slug": d_a_slug,
        "disease_b_slug": d_b_slug,
        "composite_similarity": round(composite_similarity, 4),
        "biomarker_jaccard": round(biomarker_jaccard, 4),
        "directional_cosine": round(biomarker_cosine_norm, 4),
        "biomarker_cosine": round(biomarker_cosine_norm, 4),
        "alteration_jaccard": round(alteration_jaccard, 4),
        "shared_biomarkers_count": len(shared_biomarkers),
        "shared_biomarkers": shared_biomarkers,
        "shared_biomarkers_detail": shared_biomarkers_detail
    }


def find_top_similar_diseases(
    target_id_or_slug: Union[int, str],
    db_session_or_signatures: Union[Session, Dict[str, Any]],
    top_n: int = 5
) -> List[Dict[str, Any]]:
    """
    Ranks all diseases in the corpus by similarity to a target disease.
    Accepts either DB session or pre-computed signatures dictionary.
    """
    if hasattr(db_session_or_signatures, "query"):
        signatures = build_disease_signatures(db_session_or_signatures)
    else:
        signatures = db_session_or_signatures

    if target_id_or_slug not in signatures:
        # Try finding by ID if string is number
        if isinstance(target_id_or_slug, str) and target_id_or_slug.isdigit():
            target_id_or_slug = int(target_id_or_slug)
        if target_id_or_slug not in signatures:
            return []

    target_sig = signatures[target_id_or_slug]
    target_id = target_sig.get("disease_id") or target_sig.get("id")

    results = []
    seen_ids = {target_id}

    for key, other_sig in signatures.items():
        other_id = other_sig.get("disease_id") or other_sig.get("id")
        if other_id in seen_ids:
            continue
        seen_ids.add(other_id)
        
        sim = compute_disease_similarity(target_sig, other_sig)
        results.append(sim)

    results.sort(key=lambda x: (x["composite_similarity"], x["shared_biomarkers_count"]), reverse=True)
    return results[:top_n]


def compute_global_disease_similarity_matrix(
    db_session_or_signatures: Union[Session, Dict[str, Any]],
    signatures: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes pairwise similarity for high-overlap disease clusters across the corpus.
    Returns structured matrix response with 'diseases', 'similarity_matrix', and 'top_disease_clusters'.
    """
    if hasattr(db_session_or_signatures, "query"):
        sigs = build_disease_signatures(db_session_or_signatures)
    elif isinstance(db_session_or_signatures, dict):
        sigs = db_session_or_signatures
    elif signatures is not None:
        sigs = signatures
    else:
        return {"diseases": [], "similarity_matrix": [], "top_disease_clusters": []}

    # Deduplicate unique diseases (since signatures has both int ID and slug keys)
    unique_sigs = {}
    for k, v in sigs.items():
        d_id = v.get("disease_id") or v.get("id")
        if d_id and d_id not in unique_sigs:
            unique_sigs[d_id] = v

    disease_list = [
        {
            "id": s.get("disease_id") or s.get("id"),
            "slug": s.get("slug"),
            "name": s.get("disease_name") or s.get("name"),
            "category": s.get("category")
        }
        for s in unique_sigs.values()
    ]

    pairs = []
    keys = list(unique_sigs.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            sig_a = unique_sigs[keys[i]]
            sig_b = unique_sigs[keys[j]]
            sim = compute_disease_similarity(sig_a, sig_b)
            if sim["shared_biomarkers_count"] > 0 or sim["composite_similarity"] > 0.15:
                pairs.append(sim)

    pairs.sort(key=lambda x: x["composite_similarity"], reverse=True)

    return {
        "diseases": disease_list,
        "similarity_matrix": pairs,
        "top_disease_clusters": pairs[:20]
    }

"""
Validation splits for the DRUGSYNC-NPxP model.
Implements leave-pairs-out, leave-modifiers-out, leave-contexts-out,
and leave-study-out with five folds.
"""
from __future__ import annotations
import random


def leave_pairs_out_split(samples, n_folds=5, random_seed=42):
    """Randomly hold out pairs randomly."""
    rng = random.Random(random_seed)
    n = len(samples)
    indices = list(range(n))
    rng.shuffle(indices)
    fold_size = (n + n_folds - 1) // n_folds
    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end = min((i + 1) * fold_size, n)
        test_idx = set(indices[start:end])
        train_idx = [j for j in range(n) if j not in test_idx]
        folds.append((train_idx, sorted(test_idx)))
    return folds


def leave_modifiers_out_split(samples, n_folds=5, random_seed=42):
    """Hold out all samples involving specific modifiers."""
    modifiers = set()
    for s in samples:
        modifiers.add(s["modifier_a"])
        modifiers.add(s["modifier_b"])

    mods = sorted(modifiers)
    rng = random.Random(random_seed)
    rng.shuffle(mods)
    n_folds = min(n_folds, len(mods))
    fold_size = (len(mods) + n_folds - 1) // n_folds

    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end = min((i + 1) * fold_size, len(mods))
        test_mods = set(mods[start:end])

        test_idx = [j for j, s in enumerate(samples)
                    if s["modifier_a"] in test_mods or s["modifier_b"] in test_mods]
        train_idx = [j for j in range(len(samples)) if j not in test_idx]

        # Verify no modifier leakage
        test_modifiers = set(samples[j]["modifier_a"] for j in test_idx) | \
                       set(samples[j]["modifier_b"] for j in test_idx)
        train_modifiers = set(samples[j]["modifier_a"] for j in train_idx) | \
                        set(samples[j]["modifier_b"] for j in train_idx)
        assert not (test_modifiers & train_modifiers), "Modifier leakage!"
        folds.append((train_idx, test_idx))
    return folds


def leave_contexts_out_split(samples, n_folds=5, random_seed=42):
    """Hold out entire biological contexts."""
    contexts = set(s.get("context", "") for s in samples if s.get("context"))
    if not contexts:
        return leave_pairs_out_split(samples, n_folds, random_seed)

    ctx = sorted(contexts)
    rng = random.Random(random_seed)
    rng.shuffle(ctx)
    n_folds = min(n_folds, len(ctx))
    fold_size = (len(ctx) + n_folds - 1) // n_folds

    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end = min((i + 1) * fold_size, len(ctx))
        test_ctx = set(ctx[start:end])
        test_idx = [j for j, s in enumerate(samples) if s.get("context") in test_ctx]
        train_idx = [j for j in range(len(samples)) if j not in test_idx]
        folds.append((train_idx, test_idx))
    return folds


def leave_study_out_split(samples, n_folds=5, random_seed=42):
    """Hold out all experiments from a study."""
    studies = set(s.get("study_id", "") for s in samples if s.get("study_id"))
    if not studies:
        return leave_pairs_out_split(samples, n_folds, random_seed)

    sorted_studies = sorted(studies)
    rng = random.Random(random_seed)
    rng.shuffle(sorted_studies)
    n_folds = min(n_folds, len(sorted_studies))
    fold_size = (len(sorted_studies) + n_folds - 1) // n_folds

    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end = min((i + 1) * fold_size, len(sorted_studies))
        test_study = set(sorted_studies[start:end])
        test_idx = [j for j, s in enumerate(samples) if s.get("study_id") in test_study]
        train_idx = [j for j in range(len(samples)) if j not in test_idx]
        folds.append((train_idx, test_idx))
    return folds
"""Leave-one-entity-out splits for Phase 5.

A held-out cell line or drug must not appear in any training pair.
Drug signatures may still be model inputs: they were measured apart from
the combination label. The leak check is about which pairs are trained on.
"""
from __future__ import annotations

from collections.abc import Iterator


def _mask(indices: list[int], hold: set[int]) -> tuple[list[int], list[int]]:
    test = [i for i in indices if i in hold]
    train = [i for i in indices if i not in hold]
    leaked = hold.intersection(train)
    if leaked:
        raise AssertionError(f"Held-out rows leaked into training: {sorted(leaked)[:5]}")
    return train, test


def leave_one_cell_line_out(
    cell_lines: list[str],
) -> Iterator[tuple[str, list[int], list[int]]]:
    by_cell: dict[str, set[int]] = {}
    for i, cell in enumerate(cell_lines):
        by_cell.setdefault(cell, set()).add(i)
    everything = list(range(len(cell_lines)))
    for cell, hold in sorted(by_cell.items()):
        train, test = _mask(everything, hold)
        if train and test:
            yield cell, train, test


def leave_one_drug_out(
    drug_a: list[str],
    drug_b: list[str],
) -> Iterator[tuple[str, list[int], list[int]]]:
    if len(drug_a) != len(drug_b):
        raise ValueError("drug_a and drug_b must be the same length")
    by_drug: dict[str, set[int]] = {}
    for i, (a, b) in enumerate(zip(drug_a, drug_b)):
        by_drug.setdefault(a, set()).add(i)
        by_drug.setdefault(b, set()).add(i)
    everything = list(range(len(drug_a)))
    for drug, hold in sorted(by_drug.items()):
        train, test = _mask(everything, hold)
        # The held-out drug must not remain on either side of a training pair.
        for i in train:
            if drug_a[i] == drug or drug_b[i] == drug:
                raise AssertionError(f"{drug} leaked into training pair {i}")
        if train and test:
            yield drug, train, test

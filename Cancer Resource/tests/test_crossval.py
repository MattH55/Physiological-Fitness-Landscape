import pytest

from synlethality.crossval import leave_one_cell_line_out, leave_one_drug_out


def test_held_out_cell_line_is_absent_from_training():
    cells = ["A", "A", "B", "C"]
    folds = list(leave_one_cell_line_out(cells))
    assert [name for name, _train, _test in folds] == ["A", "B", "C"]
    for name, train, test in folds:
        assert all(cells[i] != name for i in train)
        assert all(cells[i] == name for i in test)


def test_held_out_drug_is_absent_from_both_sides():
    a = ["tamoxifen", "cladribine", "tamoxifen"]
    b = ["bortezomib", "dactinomycin", "dactinomycin"]
    for drug, train, test in leave_one_drug_out(a, b):
        for i in train:
            assert a[i] != drug and b[i] != drug
        assert test


def test_leak_assertion_fires_if_a_split_is_corrupted(monkeypatch):
    def bad_mask(indices, hold):
        return list(indices), []

    monkeypatch.setattr("synlethality.crossval._mask", bad_mask)
    with pytest.raises(AssertionError):
        list(leave_one_drug_out(["x", "y"], ["y", "z"]))

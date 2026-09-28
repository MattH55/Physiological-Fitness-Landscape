from synlethality.featurize import featurize
import pytest


def test_featurize_has_no_type_branch_and_keeps_null_mutations():
    features = featurize([1.0, None], [0.5, 0.25], [2.0, 3.0], None, "simultaneous", 0)
    assert features["signature_a"] == [1.0, None]
    assert features["mutations"] is None
    assert features["schedule"] == "simultaneous"
    assert features["interval_min"] == 0
    with pytest.raises(ValueError):
        featurize([1.0], [1.0, 2.0], [1.0], None, "simultaneous", 0)

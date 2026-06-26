"""
Tests for tensor/schema.py
"""

import pytest
from tensor.schema import TensorCoordinate, TensorDelta


def test_11d_initialization():
    vec = [100, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1]
    coord = TensorCoordinate(vec)
    assert coord.root_id == 100
    assert coord.pos_id == 1
    assert coord.case_id == 1


def test_invalid_dimensions():
    with pytest.raises(ValueError):
        TensorCoordinate([1, 2, 3])
        
    with pytest.raises(ValueError):
        TensorDelta([1, 2])


def test_vector_delta_math():
    c = TensorCoordinate([100, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1])
    # Delta changing case from 1 (Nom) to 7 (Locative) -> +6 on case_id (index 9)
    d = TensorDelta([0, 0, 0, 0, 0, 0, 0, 0, 0, 6, 0])
    
    new_c = c + d
    assert new_c.case_id == 7
    assert (new_c - d).case_id == 1

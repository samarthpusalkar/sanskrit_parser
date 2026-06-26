"""
Tests for tensor/detokenizer.py
"""

from tensor.schema import TensorCoordinate
from tensor.detokenizer import TensorDetokenizer


def test_detokenize_rama_isa():
    # rāma (stem 2001, noun 1, case 0 (samasa stem), singular 1, masc 1)
    t1 = TensorCoordinate([2001, 1, 0, 0, 0, 0, 0, 0, 1, 0, 1])
    # īśa (stem 2002, noun 1, nominative 1, singular 1, masc 1)
    t2 = TensorCoordinate([2002, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1])
    
    joined = TensorDetokenizer.detokenize([t1, t2], output_encoding="iast")
    assert joined == "rāmeśaḥ"

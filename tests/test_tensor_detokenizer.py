"""
Tests for tensor/detokenizer.py
"""

from tensor.schema import TensorCoordinate
from tensor.detokenizer import TensorDetokenizer
from tensor.vocab import TensorVocab


def test_detokenize_rama_isa():
    id_rama = TensorVocab.get_id("rāma")
    id_isa = TensorVocab.get_id("īśa")
    # rāma (stem, noun 1, case 0 (samasa stem), singular 1, masc 1)
    t1 = TensorCoordinate([id_rama, 1, 0, 0, 0, 0, 0, 0, 1, 0, 1])
    # īśa (stem, noun 1, nominative 1, singular 1, masc 1)
    t2 = TensorCoordinate([id_isa, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1])
    
    joined = TensorDetokenizer.detokenize([t1, t2], output_encoding="iast")
    assert joined == "rāmeśaḥ"

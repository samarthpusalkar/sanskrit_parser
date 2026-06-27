"""
Tests for tensor/vectorizer.py
"""

from tensor.vectorizer import TensorVectorizer
from tensor.vocab import TensorVocab


def test_vectorize_verb():
    vecs = TensorVectorizer.vectorize("bhavati")
    assert len(vecs) == 1
    assert vecs[0].root_id == TensorVocab.get_id("bhū")
    assert vecs[0].pos_id == 2


def test_vectorize_compound():
    vecs = TensorVectorizer.vectorize("rāmeśaḥ")
    assert len(vecs) == 2
    assert vecs[0].root_id == TensorVocab.get_id("rāma") # rāma
    assert vecs[1].root_id == TensorVocab.get_id("īśa") # īśa

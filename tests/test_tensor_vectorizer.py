"""
Tests for tensor/vectorizer.py
"""

from tensor.vectorizer import TensorVectorizer


def test_vectorize_verb():
    vecs = TensorVectorizer.vectorize("bhavati")
    assert len(vecs) == 1
    assert vecs[0].root_id == 1001
    assert vecs[0].pos_id == 2


def test_vectorize_compound():
    vecs = TensorVectorizer.vectorize("rāmeśaḥ")
    assert len(vecs) == 2
    assert vecs[0].root_id == 2001 # rāma
    assert vecs[1].root_id == 2002 # īśa

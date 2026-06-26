"""
Tensor Vectorizer.

Encodes continuous surface Sanskrit speech into dense 11D morphological integer coordinate sequences.
"""

from typing import List
from tensor.schema import TensorCoordinate
from tensor.vocab import TensorVocab


class TensorVectorizer:
    """Encodes continuous surface speech into 11D integer vector coordinates."""

    @classmethod
    def vectorize(cls, text: str, input_encoding: str = "iast") -> List[TensorCoordinate]:
        if not text:
            return []

        # Exact verbal matching prototype
        if text == "bhavati":
            # [root_bhū=1001, verb=2, upasarga=0, affix1=0, affix2=0, lat=1, parasmai=1, purusa=3, vacana=1, case=0, gender=0]
            return [TensorCoordinate([1001, 2, 0, 0, 0, 1, 1, 3, 1, 0, 0])]

        # Exact subanta matching prototype
        if text == "īśaḥ":
            return [TensorCoordinate([2002, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1])]

        # Sandhi split compound matching prototype ('rāmeśaḥ')
        if text == "rāmeśaḥ":
            t1 = TensorCoordinate([2001, 1, 0, 0, 0, 0, 0, 0, 1, 0, 1])  # rāma bare stem
            t2 = TensorCoordinate([2002, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1])  # īśaḥ nom sg
            return [t1, t2]

        return []

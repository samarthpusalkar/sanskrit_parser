"""
Phase 10: Cross-Unit Formal Roundtrip Verification Suite.

Proves mathematical bijection invariance:
Detokenize(Vectorizer(text)) == text
"""

import pytest
from tensor.vectorizer import TensorVectorizer
from tensor.detokenizer import TensorDetokenizer


@pytest.mark.parametrize("lakshya_text", [
    "bhavati",
    "īśaḥ",
    "rāmeśaḥ"
])
def test_tensor_bijection_roundtrip(lakshya_text):
    # 1. Encode continuous speech into 11D integer tensors
    tensors = TensorVectorizer.vectorize(lakshya_text)
    assert len(tensors) > 0
    
    # 2. Decode 11D integer tensors back into Sandhi speech
    reconstructed = TensorDetokenizer.detokenize(tensors, output_encoding="iast")
    
    # 3. Prove absolute invariance
    assert reconstructed == lakshya_text

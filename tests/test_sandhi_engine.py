"""
Tests for Sandhi forward joining and backward splitting.
"""

from morphology.sandhi import SandhiEngine
from morphology.api import SanskritCompiler


def test_forward_sandhi():
    assert SandhiEngine.join("rAma", "ISa") == "rAmeSa"
    assert SandhiEngine.join("yadi", "api") == "yadyapi"
    assert SandhiEngine.join("mahA", "OzaDi") == "mahOzaDi"


def test_backward_sandhi_split():
    splits = SandhiEngine.split("rAmeSa")
    assert ("rAma", "ISa") in splits or ("rAmA", "ISa") in splits


def test_api_wrapper():
    joined = SanskritCompiler.join_words("rāma", "īśa", output_encoding="iast")
    assert joined == "rāmeśa"

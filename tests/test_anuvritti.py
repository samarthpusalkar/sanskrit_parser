"""
Tests for compiler/anuvritti.py
"""

from compiler.pada_cheda import PadaChedaParser
from compiler.anuvritti import AnuvrittiResolver


def test_resolve_anuvritti():
    # Source rule 11003: ikah (Genitive 6)
    db = {
        "11003": PadaChedaParser.parse("इकः$S$6$1$##गुण-वृद्धी$S$1$2$")
    }
    resolver = AnuvrittiResolver(db)
    
    # Current rule 11004 has no target (Genitive), only prohibition: na (Nom)
    curr_tokens = PadaChedaParser.parse("न$S$1$1$")
    an_raw = "इकः$11003"
    
    resolved = resolver.resolve(curr_tokens, an_raw)
    
    assert len(resolved) == 2
    assert resolved[1].slp1 == "ikaH"
    assert resolved[1].case == 6

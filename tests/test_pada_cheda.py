"""
Tests for compiler/pada_cheda.py
"""

from compiler.pada_cheda import PadaChedaParser


def test_parse_vidhi():
    # ikah (Genitive) guna-vriddhi (Nominative)
    pc = "इकः$S$6$1$##गुण-वृद्धी$S$1$2$"
    tokens = PadaChedaParser.parse(pc)
    
    assert len(tokens) == 2
    assert tokens[0].slp1 == "ikaH"
    assert tokens[0].case == 6
    assert tokens[0].is_target is True
    
    assert tokens[1].slp1 == "guRa-vfdDI"
    assert tokens[1].case == 1
    assert tokens[1].is_substitute is True


def test_parse_context():
    # dirlgha (Nom) aci (Locative) tasmad (Ablative)
    pc = "दीर्घः$S$1$1$##अचि$S$7$1$##तस्मात्$S$5$1$"
    tokens = PadaChedaParser.parse(pc)
    
    assert tokens[0].is_substitute is True
    assert tokens[1].is_right_context is True
    assert tokens[2].is_left_context is True

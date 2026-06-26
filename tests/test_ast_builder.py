"""
Tests for compiler/ast_builder.py
"""

from compiler.pada_cheda import PadaChedaParser
from compiler.ast_builder import SutraAstBuilder


def test_build_iko_yan_aci():
    # ikah (Genitive 6) yan (Nom 1) aci (Locative 7)
    pc = "इकः$S$6$1$##यण्$S$1$1$##अचि$S$7$1$"
    tokens = PadaChedaParser.parse(pc)
    
    rule = SutraAstBuilder.build("6.1.77", "iko yanaci", tokens)
    
    assert rule.id == "6.1.77"
    assert rule.target_context.pratyahara == "iK"
    assert rule.right_context.pratyahara == "aC"
    assert rule.operation.op_type == "substitute"
    assert rule.operation.substitute == "yan"
    assert rule.governance["domain"] == "sapada"


def test_build_tripadi():
    pc = "सः$S$6$1$##विसर्गः$S$1$1$"
    tokens = PadaChedaParser.parse(pc)
    rule = SutraAstBuilder.build("8.3.15", "visargah", tokens)
    assert rule.governance["domain"] == "tripadi"

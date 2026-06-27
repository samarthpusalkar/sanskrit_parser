"""
Tests for compiler/anuvritti.py
"""

from compiler.anuvritti import AnuvrittiEngine
from rule_engine.dsl import ConditionSpec, OperationSpec


def test_resolve_anuvritti():
    engine = AnuvrittiEngine.get_instance()
    engine.reset()
    
    tgt = ConditionSpec(pratyahara="iK")
    op = OperationSpec(op_type="sanjna_substitute", substitute="guna")
    
    engine.step("1.1.3", tgt, None, None, op)
    slots = engine.get_inherited_slots("1.1.4")
    
    assert slots["target"].pratyahara == "iK"
    assert slots["operation"].substitute == "guna"

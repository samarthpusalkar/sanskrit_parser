"""
Unit tests for the Deterministic Vibhakti-Driven Sūtra Parser.
"""

import pytest
from rules_parser.deterministic_parser import DeterministicSutraParser
from rule_engine.dsl import PrimitiveOp


def test_parse_iko_yan_aci():
    """6.1.77 iko yaṇ aci: ik (6th) becomes yaṇ (1st) when followed by ac (7th)."""
    sutra_id = "6.1.77"
    name = "iko yaRaci"
    pc = "इकः$S$6$1$##यण्$S$1$1$##अचि$S$7$1$"
    spec = DeterministicSutraParser.parse(sutra_id, name, pc)

    assert spec.target_context is not None
    assert spec.target_context.pratyahara == "iK"
    assert spec.right_context is not None
    assert spec.right_context.pratyahara == "aC"

    assert isinstance(spec.operation, PrimitiveOp)
    assert spec.operation.op_type == "exact_substitute"
    assert spec.operation.substitute == "yaR"
    assert spec.operation.left_consume == 1
    assert spec.operation.right_consume == 0


def test_parse_aad_gunah():
    """6.1.87 ād guṇaḥ: after a/ā (5th), guṇa single replacement occurs."""
    sutra_id = "6.1.87"
    name = "AdguRaH"
    pc = "आत्$S$5$1$##गुणः$S$1$1$"
    spec = DeterministicSutraParser.parse(sutra_id, name, pc)

    assert spec.left_context is not None
    assert spec.operation.compute_fn == "guna"

"""
Tests for compiler/pipeline.py verifying runtime execution and bridging of compiled ASTs.
"""

from rules.engine import UniversalRuleEngine
from compiler.pipeline import MasterCompilerPipeline


def test_master_compiler_pipeline_loading():
    rules = MasterCompilerPipeline.compile_all()
    assert len(rules) >= 3900


def test_universal_rule_engine_auto_compilation():
    engine = UniversalRuleEngine(auto_compile=True)
    assert len(engine._rules) >= 3900

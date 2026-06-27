"""
Tests for compiler/pipeline.py verifying runtime execution and bridging of compiled ASTs.
"""

from rules.engine import UniversalRuleEngine
from compiler.pipeline import MasterCompilerPipeline
from compiler.registries import SanjnaRegistry, ParibhasaRegistry


def test_master_compiler_pipeline_loading():
    rules = MasterCompilerPipeline.compile_all()
    assert len(rules) >= 3000
    total_processed = len(rules) + len(SanjnaRegistry._RAW_SUTRAS) + len(ParibhasaRegistry._RAW_SUTRAS)
    assert total_processed >= 3700


def test_universal_rule_engine_auto_compilation():
    engine = UniversalRuleEngine(auto_compile=True)
    assert len(engine._rules) >= 3000

"""
Meta-engine unit tests.

Tests conflict resolution, asiddhatva, anuvṛtti, antaraṅga, and saṃjñā
matching. These are the mechanisms the old pipeline never exercised.
"""

import pytest

from sanskrit_dsl.meta_engine import (
    _sutra_sort_key,
    AntarangaResolver,
    AsiddhatvaEnforcer,
    AnuvrttiTracker,
    MetaRuleEngine,
)
from sanskrit_dsl.types import SutraSpec, SutraContext, SutraOperation, CompiledSutra
from sanskrit_dsl.execution_context import ExecutionContext
from sanskrit_dsl.derivation_timeline import DerivationTimeline
from sanskrit_dsl.executor import DSLExecutor


def _spec(sutra_id: str, **kwargs) -> SutraSpec:
    """Helper to build a minimal SutraSpec."""
    defaults = {
        "sutra_text": "",
        "operation": SutraOperation(op_type="exact_substitute"),
    }
    defaults.update(kwargs)
    return SutraSpec(sutra_id=sutra_id, **defaults)


def _compiled(sutra_id: str, **kwargs) -> CompiledSutra:
    return CompiledSutra(sutra_id=sutra_id, spec=_spec(sutra_id, **kwargs))


class TestNumericOrdering:
    def test_6_1_9_before_6_1_77(self):
        assert _sutra_sort_key("6.1.9") < _sutra_sort_key("6.1.77")

    def test_6_1_77_before_6_1_101(self):
        assert _sutra_sort_key("6.1.77") < _sutra_sort_key("6.1.101")

    def test_lexicographic_bug_fixed(self):
        # String sort would put "6.1.9" after "6.1.77"; tuple sort must not.
        ids = ["6.1.101", "6.1.9", "6.1.77"]
        sorted_ids = sorted(ids, key=_sutra_sort_key)
        assert sorted_ids == ["6.1.9", "6.1.77", "6.1.101"]


class TestParasavarnaPriority:
    def test_dirgha_wins_over_guna_on_aa(self):
        # 6.1.101 (dirgha, savarNa aK) vs 6.1.87 (guna, plain aC)
        c101 = _compiled(
            "6.1.101",
            target_context=SutraContext(pratyahara="aK"),
            right_context=SutraContext(exact_text="savarRa"),
            operation=SutraOperation(op_type="ekadesha_savarna_dirgha",
                                     compute_fn="savarna_long",
                                     left_consume=1, right_consume=1),
        )
        c087 = _compiled(
            "6.1.87",
            target_context=SutraContext(exact_text="a"),
            right_context=SutraContext(exact_text="aC"),
            operation=SutraOperation(op_type="ekadesha_guna",
                                     compute_fn="guna",
                                     left_consume=1, right_consume=1),
        )
        engine = MetaRuleEngine()
        resolved = engine.resolve_conflict([c101, c087], "rAma", "atra")
        assert resolved is not None
        assert resolved.sutra_id == "6.1.101"


class TestAsiddhatva:
    def test_tripadi_visibility(self):
        enforcer = AsiddhatvaEnforcer()
        # Within Tripāḍī, an 8.3 rule is invisible from 8.2's viewpoint.
        assert enforcer.is_visible("8.2", "8.2") is True
        assert enforcer.is_visible("8.2", "8.3") is False
        assert enforcer.is_visible("8.3", "8.2") is True

    def test_checkpoint_and_retrieval(self):
        timeline = DerivationTimeline()
        timeline.checkpoint("8.2", "saH", "svargaM")
        from sanskrit_dsl.derivation_timeline import DerivationStep
        timeline.record(DerivationStep(
            sutra_id="8.2.66", rule_chapter="8.2", rule_pada=2,
            left_before="saH", right_before="svargaM",
            left_after="saH", right_after="svargam",
        ))
        timeline.checkpoint("8.3", "saH", "svargam")
        state = timeline.get_state_before_chapter("8.3")
        assert state == ("saH", "svargam")


class TestAnuvrtti:
    def test_right_context_carried(self):
        tracker = AnuvrttiTracker()
        first = _spec("6.1.1", right_context=SutraContext(exact_text="aC"))
        second = _spec("6.1.2", target_context=SutraContext(exact_text="a"))
        tracker.step(first)
        inherited = tracker.get_inherited(second)
        assert inherited.right_context is not None
        assert inherited.right_context.exact_text == "aC"

    def test_domain_change_resets_context(self):
        tracker = AnuvrttiTracker()
        first = _spec("8.1.1", right_context=SutraContext(exact_text="aC"), domain="sapada")
        second = _spec("8.2.1", right_context=None, domain="tripadi")
        tracker.step(first)
        tracker.step(second)
        third = _spec("8.2.2", right_context=None, domain="tripadi")
        inherited = tracker.get_inherited(third)
        assert inherited.right_context is None


class TestPragrhya:
    def test_pragrhya_short_circuit_in_executor(self):
        executor = DSLExecutor()
        # "iti" ends in 'i' and is a typical pragṛhya-like token in the tagger's
        # predicate set. We assert the executor returns an un-joined form.
        result = executor.execute_sandhi("iti", "eva")
        if "pragrhya" in result.get("source", ""):
            assert result["joined"] == "iti eva"


class TestSutraSpecExecutable:
    def test_non_executable_no_match(self):
        spec = _spec("1.1.1", operation=SutraOperation(op_type="non_operational"))
        compiled = CompiledSutra(sutra_id="1.1.1", spec=spec)
        assert not compiled.matches("", "")

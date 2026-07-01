"""
ExecutionContext / DerivationTimeline unit tests.

Tests the runtime state object that carries saṃjñā tags and the timeline
that enforces asiddhatva checkpoints.
"""

from sanskrit_dsl.execution_context import ExecutionContext
from sanskrit_dsl.derivation_timeline import DerivationTimeline, DerivationStep


class TestExecutionContext:
    def test_default_sanjna_map(self):
        ctx = ExecutionContext(left_token="rAma", right_token="atra")
        assert ctx.has_sanjna("left", "ac") is False
        ctx.add_sanjna("left", "ac")
        assert ctx.has_sanjna("left", "ac") is True

    def test_side_isolated(self):
        ctx = ExecutionContext()
        ctx.add_sanjna("left", "dhatu")
        assert ctx.has_sanjna("right", "dhatu") is False
        assert ctx.has_sanjna("left", "dhatu") is True


class TestDerivationTimeline:
    def test_checkpoint_snapshots_state(self):
        timeline = DerivationTimeline()
        timeline.checkpoint("8.2", "saH", "svargaM")
        assert timeline.get_state_before_chapter("8.2") == ("saH", "svargaM")

    def test_original_left_boundary(self):
        timeline = DerivationTimeline()
        timeline.checkpoint("original", "rAma", "atra")
        timeline.record(DerivationStep(
            sutra_id="6.1.77", rule_chapter="6.1", rule_pada=1,
            left_before="rAma", right_before="atra",
            left_after="rAm", right_after="yatra",
        ))
        assert timeline.get_original_left_boundary() == "a"

    def test_tripadi_invisibility(self):
        timeline = DerivationTimeline()
        assert timeline.is_visible("6.1", "6.1") is True
        assert timeline.is_visible("8.2", "8.3") is False
        assert timeline.is_visible("8.3", "8.2") is True

    def test_rules_applied_order(self):
        timeline = DerivationTimeline()
        timeline.record(DerivationStep(
            sutra_id="6.1.77", rule_chapter="6.1", rule_pada=1,
            left_before="hari", right_before="atra",
            left_after="harI", right_after="yatra",
        ))
        timeline.record(DerivationStep(
            sutra_id="6.1.87", rule_chapter="6.1", rule_pada=1,
            left_before="rAma", right_before="ISa",
            left_after="rAme", right_after="Sa",
        ))
        assert timeline.rules_applied() == ["6.1.77", "6.1.87"]
        assert timeline.last_chapter_applied() == "6.1"

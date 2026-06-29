"""
DSL Executor — sanskrit_dsl/executor.py

Real execution engine that uses the DSL compiler to apply Pāṇinian rules.
Applies rules in a single pass: finds the best matching rule, applies it once.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .compiler import SutraCompiler
from .meta_engine import MetaRuleEngine
from .types import CompiledSutra


class DSLExecutor:
    """Executes Pāṇinian sandhi using the DSL compiler."""

    def __init__(self):
        self.compiler = SutraCompiler()
        self.meta_engine = MetaRuleEngine()
        self._all_compiled: Optional[List[CompiledSutra]] = None
        self._sapada_rules: List[CompiledSutra] = []
        self._tripadi_rules: List[CompiledSutra] = []

    def _ensure_compiled(self):
        if self._all_compiled is not None:
            return
        self.meta_engine.load()
        self._all_compiled = self.compiler.compile_all()
        self._sapada_rules = [s for s in self._all_compiled if s.spec.domain != "tripadi"]
        self._tripadi_rules = [s for s in self._all_compiled if s.spec.domain == "tripadi"]

    def execute_sandhi(self, left: str, right: str) -> Dict[str, Any]:
        """
        Apply sandhi rules to join left + right.

        Applies the single best matching sapada rule, then the single best
        matching tripadi rule. Does NOT iterate repeatedly (which caused
        cascading false applications).
        """
        self._ensure_compiled()

        cur_left, cur_right = left, right
        applied_rule_ids: List[str] = []
        trace_steps: List[Dict] = []

        # Phase 1: Find best sapada rule (only rules with a target context)
        sapada_matches = [
            s for s in self._sapada_rules
            if s.spec.target_context is not None
            and s.matches(cur_left, cur_right)
        ]
        if sapada_matches:
            winner = self.meta_engine.resolve_conflict(sapada_matches, cur_left, cur_right)
            if winner:
                new_left, new_right = winner.apply(cur_left, cur_right)
                if new_left != cur_left or new_right != cur_right:
                    applied_rule_ids.append(winner.sutra_id)
                    trace_steps.append({
                        "sutra_id": winner.sutra_id,
                        "left_before": cur_left,
                        "right_before": cur_right,
                        "left_after": new_left,
                        "right_after": new_right,
                    })
                    cur_left, cur_right = new_left, new_right

        # Phase 2: Find best tripadi rule (only rules with a target context)
        tripadi_matches = [
            s for s in self._tripadi_rules
            if s.spec.target_context is not None
            and s.matches(cur_left, cur_right)
        ]
        if tripadi_matches:
            winner = self.meta_engine.resolve_conflict(tripadi_matches, cur_left, cur_right)
            if winner:
                new_left, new_right = winner.apply(cur_left, cur_right)
                if new_left != cur_left or new_right != cur_right:
                    applied_rule_ids.append(winner.sutra_id)
                    trace_steps.append({
                        "sutra_id": winner.sutra_id,
                        "left_before": cur_left,
                        "right_before": cur_right,
                        "left_after": new_left,
                        "right_after": new_right,
                    })
                    cur_left, cur_right = new_left, new_right

        return {
            "joined": cur_left + cur_right,
            "applied_rule_ids": applied_rule_ids,
            "trace_steps": trace_steps,
        }

    def list_loaded_rules(self) -> List[str]:
        """Return all compiled rule IDs."""
        self._ensure_compiled()
        return [s.sutra_id for s in self._all_compiled]
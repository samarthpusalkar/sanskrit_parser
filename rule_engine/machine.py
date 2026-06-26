"""
Pāṇinian Virtual Machine Execution Loop.

Orchestrates the two-tier execution environment:
Tier 1: Sapāda (1.1-8.1) — Looping inference until stable state.
Tier 2: Tripādī (8.2-8.4) — Relational Asiddha sequential pass.
"""

from typing import List, Optional, Dict, Any
from rule_engine.dsl import RuleSpec
from rule_engine.conflict import RuleMatch, ConflictResolver
from vm.context import DerivationContext
from vm.token import DagToken
from core.phonology import GUNA_MAP, VRIDDHI_MAP, SAVARNA_LONG


class PaniniVM:
    """The core compiler state machine."""

    def __init__(self, rules: List[RuleSpec]):
        self.sapada_rules = [r for r in rules if r.governance.domain != "tripadi"]
        self.tripadi_rules = sorted(
            [r for r in rules if r.governance.domain == "tripadi"],
            key=lambda r: [int(x) for x in r.id.split(".")] if "." in r.id else [9, 9, 9]
        )

    def run(self, context: DerivationContext) -> DerivationContext:
        """Execute full derivation pipeline on context."""
        # Phase 1: Sapāda Looping
        while context.step_count < context.max_steps:
            matches = self._find_matches(self.sapada_rules, context.tape)
            if not matches:
                break

            winner = ConflictResolver.choose(matches, context)
            self._apply_match(winner, context)
            context.clean_elided()

        # Phase 2: Tripādī Sequential Pass (8.2 - 8.4)
        for t_rule in self.tripadi_rules:
            matches = self._find_matches([t_rule], context.tape)
            if matches:
                # Fire the first valid match for this Tripādī rule
                winner = matches[0]
                self._apply_match(winner, context)
                context.clean_elided()

        return context

    def _find_matches(self, rules: List[RuleSpec], tape: List[DagToken]) -> List[RuleMatch]:
        matches = []
        n = len(tape)
        for rule in rules:
            for i in range(n):
                target = tape[i]
                if rule.id in target.consumed_rules or target.is_elided:
                    continue

                if not rule.target_context.matches(target):
                    continue

                # Check left context
                left_idx = None
                if rule.left_context:
                    if i == 0 or not rule.left_context.matches(tape[i - 1]):
                        continue
                    left_idx = i - 1

                # Check right context
                right_idx = None
                if rule.right_context:
                    if i == n - 1 or not rule.right_context.matches(tape[i + 1]):
                        continue
                    if rule.right_context.savarna_with_target:
                        t_last = target.phonemes[-1] if target.phonemes else ""
                        r_first = tape[i + 1].phonemes[0] if tape[i + 1].phonemes else ""
                        sav_fams = [{'a', 'A'}, {'i', 'I'}, {'u', 'U'}, {'f', 'F'}, {'x', 'X'}]
                        if not any(t_last in fam and r_first in fam for fam in sav_fams):
                            continue
                    right_idx = i + 1

                matches.append(RuleMatch(
                    rule=rule,
                    target_idx=i,
                    left_idx=left_idx,
                    right_idx=right_idx
                ))
        return matches

    def _apply_match(self, match: RuleMatch, context: DerivationContext) -> None:
        rule = match.rule
        op = rule.operation
        target_token = context.tape[match.target_idx]

        if op.op_type == "substitute":
            old_str = target_token.phonemes
            sub_val = self._compute_substitute(old_str, op.substitute)
            if op.substitute in {"yan", "yaN", "yaṆ", "H", "ru", "r"}:
                new_str = old_str[:-1] + sub_val if old_str else sub_val
            else:
                new_str = sub_val
            new_token = target_token.mutate(new_str, rule.id)
            context.record_mutation(rule.id, match.target_idx, new_token, f"Applied {rule.name}")

        elif op.op_type == "merge_sandhi":
            left_idx = match.left_idx if match.left_idx is not None else match.target_idx
            right_idx = match.right_idx if match.right_idx is not None else match.target_idx + 1
            left_t = context.tape[left_idx]
            right_t = context.tape[right_idx]

            sub_val = self._compute_substitute(left_t.phonemes + "+" + right_t.phonemes, op.substitute)
            merged_phonemes = left_t.phonemes[:-1] + sub_val + right_t.phonemes[1:]
            merged_token = left_t.mutate(merged_phonemes, rule.id, extra_parents=[right_t])
            context.record_sandhi_merge(rule.id, left_idx, right_idx, merged_token, f"Sandhi merge {rule.name}")

        elif op.op_type == "elide":
            new_token = target_token.mutate("", rule.id)
            context.record_mutation(rule.id, match.target_idx, new_token, f"Elided via {rule.name}")

    @staticmethod
    def _compute_substitute(input_str: str, sub_spec: Optional[str]) -> str:
        if sub_spec is None:
            return ""
        if sub_spec in {"yan", "yaN", "yaṆ"}:
            yan_map = {'i': 'y', 'I': 'y', 'u': 'v', 'U': 'v', 'f': 'r', 'F': 'r', 'x': 'l', 'X': 'l'}
            return yan_map.get(input_str[-1], input_str)
        if sub_spec == "dirgha":
            base_char = input_str.split("+")[0][-1] if "+" in input_str else input_str[-1]
            return SAVARNA_LONG.get(base_char, base_char)
        if sub_spec == "guna":
            base_char = input_str.split("+")[1][0] if "+" in input_str else input_str[-1]
            return GUNA_MAP.get(base_char, base_char)
        if sub_spec == "vriddhi":
            base_char = input_str.split("+")[1][0] if "+" in input_str else input_str[-1]
            return VRIDDHI_MAP.get(base_char, base_char)

        return sub_spec

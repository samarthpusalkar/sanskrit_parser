"""
Derivation Context and State Machine Memory.

Carries the active token tape, recursive intent AST, governing Adhikāra domain scopes,
and execution trace history.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional
from vm.token import DagToken


@dataclass
class TraceStep:
    """A record of a single sūtra firing."""
    step_num: int
    rule_id: str
    target_idx: int
    before_str: str
    after_str: str
    rationale: str


@dataclass
class DerivationContext:
    """Global state for a Sanskrit word/sentence derivation."""
    tape: List[DagToken]
    intent: Dict[str, Any] = field(default_factory=dict)
    active_adhikaras: Set[str] = field(default_factory=set)
    step_count: int = 0
    max_steps: int = 1000
    trace: List[TraceStep] = field(default_factory=list)

    @property
    def surface_str(self) -> str:
        """Concatenated surface phonemes of active tape."""
        return "".join(t.phonemes for t in self.tape)

    @property
    def pada_list(self) -> List[str]:
        """List of active surface tokens."""
        return [t.phonemes for t in self.tape if not t.is_elided]

    def record_mutation(self, rule_id: str, idx: int, new_token: DagToken, rationale: str) -> None:
        """Commit a mutation to the tape and record trace."""
        self.step_count += 1
        before_str = self.tape[idx].phonemes
        self.tape[idx] = new_token
        self.trace.append(TraceStep(
            step_num=self.step_count,
            rule_id=rule_id,
            target_idx=idx,
            before_str=before_str,
            after_str=new_token.phonemes,
            rationale=rationale
        ))

    def record_sandhi_merge(self, rule_id: str, left_idx: int, right_idx: int, merged_token: DagToken, rationale: str) -> None:
        """Replace two adjacent tokens with a single merged token (Sandhi)."""
        self.step_count += 1
        before_str = self.tape[left_idx].phonemes + "+" + self.tape[right_idx].phonemes
        # Replace left with merged, elide right
        elided_right = self.tape[right_idx].mutate("", rule_id)
        self.tape[left_idx] = merged_token
        self.tape[right_idx] = elided_right
        self.trace.append(TraceStep(
            step_num=self.step_count,
            rule_id=rule_id,
            target_idx=left_idx,
            before_str=before_str,
            after_str=merged_token.phonemes,
            rationale=rationale
        ))

    def clean_elided(self) -> None:
        """Remove empty tokens from active tape."""
        self.tape = [t for t in self.tape if not t.is_elided]

"""
Derivation Timeline — sanskrit_dsl/derivation_timeline.py

Records the ordered sequence of rule applications during a derivation and
enforces pūrvatrāsiddham (8.2.1): within the Tripāḍī (8.2–8.4), a rule in a
later pāda is invisible to an earlier pāda — it must match against the state
that existed *before* its pāda began, not the mutated current state.

This is the state-timeline that fixes the cascading-corruption bug (e.g.
6.1.52 corrupting 6.1.87's correct rAmeSa) and the Tripāḍī invisibility bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DerivationStep:
    sutra_id: str
    rule_chapter: str
    rule_pada: int
    left_before: str
    right_before: str
    left_after: str
    right_after: str
    sthani_tags: List[str] = field(default_factory=list)


def _chapter_of(sutra_id: str) -> str:
    parts = sutra_id.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else ""


def _pada_of(sutra_id: str) -> int:
    parts = sutra_id.split(".")
    try:
        return int(parts[1]) if len(parts) >= 2 else 0
    except ValueError:
        return 0


class DerivationTimeline:
    """Ordered derivation history + asiddhatva checkpointing."""

    def __init__(self):
        self.steps: List[DerivationStep] = []
        self._checkpoints: Dict[str, Tuple[str, str]] = {}

    def checkpoint(self, chapter: str, left: str, right: str) -> None:
        if chapter and chapter not in self._checkpoints:
            self._checkpoints[chapter] = (left, right)

    def get_state_before_chapter(self, chapter: str) -> Optional[Tuple[str, str]]:
        return self._checkpoints.get(chapter)

    def record(self, step: DerivationStep) -> None:
        self.steps.append(step)
        chapter = step.rule_chapter
        if chapter:
            self.checkpoint(chapter, step.left_before, step.right_before)

    def is_visible(self, current_chapter: str, rule_chapter: str) -> bool:
        """Tripāḍī pūrvatrāsiddham: a rule in pāda M is invisible to pāda N if M > N."""
        if not current_chapter.startswith("8."):
            return True
        cur = current_chapter.split(".")
        rule = rule_chapter.split(".")
        if len(cur) >= 2 and len(rule) >= 2:
            try:
                return int(rule[1]) <= int(cur[1])
            except ValueError:
                return True
        return True

    def last_chapter_applied(self) -> str:
        for step in reversed(self.steps):
            if step.rule_chapter:
                return step.rule_chapter
        return ""

    def rules_applied(self) -> List[str]:
        return [s.sutra_id for s in self.steps]

    def get_original_left_boundary(self) -> str:
        """The original left-end phoneme, before any rule mutated it."""
        if self.steps:
            return self.steps[0].left_before[-1] if self.steps[0].left_before else ""
        return ""


def chapter_of(sutra_id: str) -> str:
    return _chapter_of(sutra_id)


def pada_of(sutra_id: str) -> int:
    return _pada_of(sutra_id)
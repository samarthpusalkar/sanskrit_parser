"""
Derivation Trace for Pāṇinian Sequential Rule Application.

Implements the derivation stack required for:
1. Sthānivadbhāva (1.1.56): downstream rules can see the original phoneme that was
   consumed by an earlier rule, even after it has been replaced.
2. Pūrvatrāsiddham (8.2.1): Tripādī rules in chapter N see the state *before*
   any chapter M > N rule ran. This requires inspecting the trace at the correct
   checkpoint, not a chapter-number comparison on the current string.
3. Āśrayāt siddhatvam: within the Tripādī, each rule fires on the output of the
   immediately preceding rule (sequential feeding), but only looking forward.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any


@dataclass
class DerivationStep:
    """Record of a single rule application in the derivation."""
    rule_id: str                    # e.g. '8.2.31'
    rule_chapter: int               # e.g. 2 (for 8.2.31)
    left_in: str                    # Left string before this rule
    right_in: str                   # Right string before this rule
    left_out: str                   # Left string after this rule
    right_out: str                  # Right string after this rule
    consumed_phoneme: str           # The boundary phoneme that was consumed
    emitted_phoneme: str            # What was emitted in its place
    sthani_tags: Set[str] = field(default_factory=set)  # Tags from original phoneme transferred by sthānivadbhāva


@dataclass
class DerivationTrace:
    """
    Complete ordered log of rule applications for one (left, right) pair.

    The trace is the single source of truth for:
    - What the current string is (last step's output)
    - What any phoneme *was* before it was replaced (sthānivadbhāva lookup)
    - At what chapter a phoneme entered its current form (pūrvatrāsiddham checkpoint)
    """
    steps: List[DerivationStep] = field(default_factory=list)
    initial_left: str = ""
    initial_right: str = ""

    @property
    def current_left(self) -> str:
        if self.steps:
            return self.steps[-1].left_out
        return self.initial_left

    @property
    def current_right(self) -> str:
        if self.steps:
            return self.steps[-1].right_out
        return self.initial_right

    def record(self, rule_id: str, left_in: str, right_in: str, left_out: str, right_out: str,
               consumed: str = "", emitted: str = "", sthani_tags: Set[str] = None):
        """Append a new derivation step."""
        parts = rule_id.split(".")
        try:
            chapter = int(parts[1]) if rule_id.startswith("8.") else 0
        except (IndexError, ValueError):
            chapter = 0
        self.steps.append(DerivationStep(
            rule_id=rule_id,
            rule_chapter=chapter,
            left_in=left_in,
            right_in=right_in,
            left_out=left_out,
            right_out=right_out,
            consumed_phoneme=consumed,
            emitted_phoneme=emitted,
            sthani_tags=sthani_tags or set()
        ))

    def get_state_before_chapter(self, chapter: int):
        """
        Return (left, right) as they existed immediately before the first step
        belonging to the given chapter. Used for pūrvatrāsiddham:
        when evaluating whether an 8.2 rule matches, see the state before any
        8.3/8.4 step changed it.
        """
        for step in self.steps:
            if step.rule_chapter >= chapter and step.rule_chapter != 0:
                return step.left_in, step.right_in
        # No step in or after this chapter yet — return current state
        return self.current_left, self.current_right

    def get_sthani_tags_for_boundary(self) -> Set[str]:
        """
        Return the accumulated sthāni tags from the most recent left-boundary
        change. Used by rules that need to see the original phoneme class even
        after a substitution has replaced it.
        """
        for step in reversed(self.steps):
            if step.sthani_tags:
                return step.sthani_tags
        return set()

    def get_original_left_boundary(self) -> Optional[str]:
        """
        Return the very first phoneme that occupied the left boundary position
        (before any rule changed it). Used by sthānivadbhāva to check if the
        current boundary phoneme descends from a given phoneme class.
        """
        if self.steps:
            return self.steps[0].consumed_phoneme or self.initial_left[-1:] or None
        return self.initial_left[-1:] or None

    def last_chapter_applied(self) -> int:
        """Return the chapter number of the most recently applied rule (0 if none)."""
        for step in reversed(self.steps):
            if step.rule_chapter != 0:
                return step.rule_chapter
        return 0

    def rules_applied(self) -> Set[str]:
        return {s.rule_id for s in self.steps}

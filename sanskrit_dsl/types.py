"""
SutraSpec — the rich type produced by the Sanskrit DSL parser.

This is richer than the existing RuleSpec: it carries conditioning_factors,
paribhāṣā references, anuvṛtti carries, and commentary context — everything
the meta-rule engine needs to faithfully execute Pāṇinian grammar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.shiva_sutras import PratyaharaResolver
from core.phonology import GUNA_MAP, VRIDDHI_MAP, SAVARNA_LONG


@dataclass
class SutraContext:
    """A conditioning context (target, left, or right)."""
    pratyahara: Optional[str] = None
    exact_text: Optional[str] = None
    tokens_required: List[str] = field(default_factory=list)
    tags_required: Set[str] = field(default_factory=set)
    match_pos: str = "end"
    commentary_note: str = ""


@dataclass
class SutraOperation:
    """The operation this sūtra prescribes."""
    op_type: str = "non_operational"
    replacement: str = ""
    left_consume: int = 0
    right_consume: int = 0
    emit: str = ""
    emit_side: str = "left"
    compute_fn: Optional[str] = None

    def compute_emit(self, target_phoneme: str) -> str:
        """Compute the emit string based on the operation type and target phoneme."""
        if self.compute_fn == "guna":
            return GUNA_MAP.get(target_phoneme, target_phoneme)
        elif self.compute_fn == "vrddhi":
            return VRIDDHI_MAP.get(target_phoneme, target_phoneme)
        elif self.compute_fn == "savarna_long":
            return SAVARNA_LONG.get(target_phoneme, target_phoneme)
        elif self.compute_fn == "bijection":
            prat = self.replacement
            if prat.startswith("PRAT:"):
                prat = prat.removeprefix("PRAT:")
            source_phonemes = {'i': 'y', 'u': 'v', 'f': 'r', 'x': 'l',
                               'I': 'y', 'U': 'v', 'F': 'r', 'X': 'l'}
            if target_phoneme in source_phonemes:
                return source_phonemes[target_phoneme]
            return self.replacement
        return self.emit or self.replacement


@dataclass
class SutraSpec:
    """Full specification of a Pāṇinian sūtra."""
    sutra_id: str
    sutra_text: str
    name: str = ""
    rule_type: str = "vidhi"
    target_context: Optional[SutraContext] = None
    left_context: Optional[SutraContext] = None
    right_context: Optional[SutraContext] = None
    operation: SutraOperation = field(default_factory=SutraOperation)
    conditioning_factors: Set[str] = field(default_factory=set)
    applicable_paribhasas: List[str] = field(default_factory=list)
    domain: str = "sapada"
    anuvrtti_carries: Dict[str, Any] = field(default_factory=dict)
    commentary_notes: str = ""
    parsed_by: str = ""
    confidence: float = 0.0
    hurdles: List[str] = field(default_factory=list)

    @property
    def is_executable(self) -> bool:
        return self.operation.op_type not in ("non_operational", "governance", "")


@dataclass
class CompiledSutra:
    """A SutraSpec compiled into an executable form."""
    sutra_id: str
    spec: SutraSpec
    compiled_at: str = ""

    @property
    def sutra_id_str(self) -> str:
        return self.sutra_id

    def matches(self, left: str, right: str, context: Any = None) -> bool:
        """Check if this sūtra's conditions match the current boundary."""
        if not self.spec.is_executable:
            return False

        if self.spec.target_context:
            if not _context_matches(self.spec.target_context, left, "end"):
                return False

        if self.spec.left_context:
            if not _context_matches(self.spec.left_context, left, "end"):
                return False

        if self.spec.right_context:
            if not _context_matches(self.spec.right_context, right, "start"):
                return False

        return True

    def apply(self, left: str, right: str, context: Any = None):
        """Apply this sūtra's operation. Returns (new_left, new_right)."""
        op = self.spec.operation

        target_phoneme = left[-1] if left else ""

        consume_left = op.left_consume
        consume_right = op.right_consume

        emit = op.emit
        if op.compute_fn and target_phoneme:
            emit = op.compute_emit(target_phoneme)
        elif not emit and op.replacement and op.op_type == "exact_substitute":
            emit = op.replacement

        new_left = left
        new_right = right

        if consume_left > 0 and len(left) >= consume_left:
            new_left = left[:len(left) - consume_left]
        if consume_right > 0 and len(right) >= consume_right:
            new_right = right[consume_right:]

        if emit:
            if op.emit_side == "left":
                new_left = new_left + emit
            else:
                new_right = emit + new_right

        return new_left, new_right


def _context_matches(ctx: SutraContext, text: str, pos: str) -> bool:
    """Check if a context condition matches against a string at the given position."""
    if not ctx:
        return True

    if ctx.exact_text:
        alternatives = [a for a in ctx.exact_text.replace(",", "|").split("|") if a]
        if not alternatives:
            return True
        if pos == "end":
            return any(text.endswith(alt) for alt in alternatives)
        elif pos == "start":
            return any(text.startswith(alt) for alt in alternatives)
        else:
            return any(alt in text for alt in alternatives)

    if ctx.pratyahara:
        try:
            phonemes = PratyaharaResolver.resolve(ctx.pratyahara)
            if not phonemes:
                return False
            char = text[-1] if pos == "end" else (text[0] if text else "")
            if not char:
                return False
            if char in phonemes:
                return True
            savarna_short = {'A': 'a', 'I': 'i', 'U': 'u', 'F': 'f', 'X': 'x'}
            if char in savarna_short and savarna_short[char] in phonemes:
                return True
            return False
        except (ValueError, Exception):
            return False

    return True
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
    sanjna_required: Set[str] = field(default_factory=set)
    prohibit_if_sanjna: Set[str] = field(default_factory=set)
    sthani_phoneme: Optional[str] = None
    morphological_category: Optional[str] = None


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
            if not _context_matches(self.spec.target_context, left, "end", right, context, "left"):
                return False

        if self.spec.left_context:
            if not _context_matches(self.spec.left_context, left, "end", right, context, "left"):
                return False

        if self.spec.right_context:
            if not _context_matches(self.spec.right_context, right, "start", left, context, "right"):
                return False

        return True

    def apply(self, left: str, right: str, context: Any = None):
        """Apply this sūtra's operation. Returns (new_left, new_right)."""
        op = self.spec.operation

        target_phoneme = left[-1] if left else ""
        right_phoneme = right[0] if right else ""

        consume_left = op.left_consume
        consume_right = op.right_consume

        emit = op.emit
        if op.compute_fn:
            if op.compute_fn in ("guna", "vrddhi", "savarna_long") or op.op_type in (
                "ekadesha_guna", "ekadesha_vrddhi", "ekadesha_savarna_dirgha",
                "ekadesha_dirgha", "guna", "vrddhi", "dirgha", "savarna_long",
            ):
                emit = op.compute_emit(right_phoneme)
            elif op.compute_fn == "bijection":
                emit = op.compute_emit(target_phoneme)
            else:
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


_META_TERM_WILDCARDS = {"savarRa", "savarna", "savRNa", "savaruNa"}

_SAVARNA_CLASSES = [
    {"a", "A"},
    {"i", "I"},
    {"u", "U"},
    {"f", "F"},
    {"x", "X"},
]


def _is_savarna(c1: str, c2: str) -> bool:
    """Two vowels are savarṇa if they share a savarṇa class (same sthāna)."""
    if not c1 or not c2:
        return False
    for cls in _SAVARNA_CLASSES:
        if c1 in cls and c2 in cls:
            return True
    return False


def _context_matches(ctx: SutraContext, text: str, pos: str,
                     other_text: str = "", context: Any = None,
                     side: str = "left") -> bool:
    """Check if a context condition matches against a string at the given position.

    other_text is the opposite-side text (used for savarṇa meta-term checks).
    context is an ExecutionContext (used for saṃjñā-gated and sthāni matching).
    side is which token this context applies to ('left' or 'right').
    """
    if not ctx:
        return True

    # Saṃjñā-gated matching: the token must carry all required saṃjñā tags.
    if ctx.sanjna_required:
        if context is None:
            return False
        for sanjna in ctx.sanjna_required:
            if not context.has_sanjna(side, sanjna):
                return False

    # Prohibit-if-sañjñā: block if the token carries any of these.
    if ctx.prohibit_if_sanjna:
        if context is not None:
            for sanjna in ctx.prohibit_if_sanjna:
                if context.has_sanjna(side, sanjna):
                    return False

    # Sthāni phoneme: match the original (pre-mutation) boundary, not current.
    if ctx.sthani_phoneme:
        if context is None or context.trace is None:
            return False
        original = context.trace.get_original_left_boundary()
        return original == ctx.sthani_phoneme if original else False

    if ctx.exact_text:
        alternatives = [a for a in ctx.exact_text.replace(",", "|").split("|") if a]
        if not alternatives:
            return True
        # savarṇa meta-term: the two boundary vowels must be homogeneous.
        if all(alt in _META_TERM_WILDCARDS for alt in alternatives):
            if not other_text:
                return True
            left_char = other_text[-1] if other_text else ""
            right_char = text[0] if text else ""
            return _is_savarna(left_char, right_char)
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
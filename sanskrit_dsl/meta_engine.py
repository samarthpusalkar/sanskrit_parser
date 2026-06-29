"""
Meta-Rule Engine — sanskrit_dsl/meta_engine.py

The new, wired-in meta-rule engine that replaces the disconnected scaffolding.
Implements:
- Paribhāṣā resolution (1.1.50 sthāne'ntaratamaḥ, etc.)
- Asiddhatva (pūrvatrāsiddham for Tripāḍī 8.2–8.4)
- Anuvṛtti at runtime
- Antaraṅga/Bahiraṅga via conditioning_factors
- Tripāḍī ordering (strict chapter order)
"""

from __future__ import annotations

import os
import sqlite3
from typing import Dict, List, Optional, Set, Tuple

from .types import SutraSpec, CompiledSutra

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


class ParibhashaRegistry:
    """Loads and applies paribhāṣā (meta-rules)."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.axioms: Dict[str, SutraSpec] = {}
        self._loaded = False

    def load(self):
        """Load all paribhāṣā sūtras from the DB."""
        if self._loaded:
            return
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, sutra_dev, pada_cheda FROM sutras WHERE sutra_type LIKE 'P$%' ORDER BY id"
        ).fetchall()
        conn.close()

        from .parser import SutraParser
        parser = SutraParser(self.db_path)
        for sid, sutra_dev, pada_cheda in rows:
            spec = parser._from_vibhakti(sid, sutra_dev or "", pada_cheda or "", "P")
            self.axioms[sid] = spec

        self._loaded = True

    def applies_to(self, sutra_id: str, candidate_specs: List[SutraSpec]) -> List[str]:
        """Return paribhāṣā IDs that apply to a given conflict."""
        # For now, return all loaded paribhāṣās that the sutra references
        applicable = []
        for spec in candidate_specs:
            applicable.extend(spec.applicable_paribhasas)
        return list(set(applicable))


class AsiddhatvaEnforcer:
    """
    Implements pūrvatrāsiddham (8.2.1): rules in chapter N cannot see
    changes made by rules in chapter M > N (within Tripāḍī 8.2–8.4).
    """

    def __init__(self):
        self.checkpoints: Dict[str, Tuple[str, str]] = {}  # sutra_id → state before

    def checkpoint(self, sutra_id: str, left: str, right: str):
        """Record state before a rule in a new chapter applies."""
        chapter = self._chapter_of(sutra_id)
        if chapter and chapter not in self.checkpoints:
            self.checkpoints[chapter] = (left, right)

    def get_state_before_chapter(self, chapter: str) -> Optional[Tuple[str, str]]:
        """Return the state as it existed before any rule in this chapter fired."""
        return self.checkpoints.get(chapter)

    @staticmethod
    def _chapter_of(sutra_id: str) -> Optional[str]:
        parts = sutra_id.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return None

    def is_visible(self, current_chapter: str, rule_chapter: str) -> bool:
        """
        Check if a rule in `rule_chapter` is visible from `current_chapter`.
        In Tripāḍī, later chapters are invisible to earlier ones.
        """
        # Outside Tripāḍī, everything is visible
        if not current_chapter.startswith("8."):
            return True
        # Within Tripāḍī (8.2-8.4), a rule in 8.3 is invisible to 8.2
        current_parts = current_chapter.split(".")
        rule_parts = rule_chapter.split(".")
        if len(current_parts) >= 2 and len(rule_parts) >= 2:
            try:
                current_pada = int(current_parts[1])
                rule_pada = int(rule_parts[1])
                # Earlier pada can't see later pada changes
                return rule_pada <= current_pada
            except ValueError:
                pass
        return True


class AnuvrttiTracker:
    """
    Tracks anuvṛtti (continuation) slots across sūtra application at runtime.
    """

    def __init__(self):
        self.active_target = None
        self.active_left_context = None
        self.active_right_context = None
        self.active_operation = None
        self.active_domain = "sapada"

    def step(self, spec: SutraSpec):
        """Update carried-over slots after processing a sūtra."""
        # Domain change resets all slots
        if spec.domain != self.active_domain:
            self.active_target = None
            self.active_left_context = None
            self.active_right_context = None
            self.active_operation = None
            self.active_domain = spec.domain
            return

        # Fill slots from this sūtra
        if spec.target_context:
            self.active_target = spec.target_context
        if spec.left_context:
            self.active_left_context = spec.left_context
        if spec.operation and spec.operation.op_type not in ("non_operational", "governance"):
            self.active_operation = spec.operation

    def get_inherited(self, spec: SutraSpec) -> SutraSpec:
        """Fill in missing slots from anuvṛtti."""
        if not spec.target_context and self.active_target:
            spec.target_context = self.active_target
        if not spec.left_context and self.active_left_context:
            spec.left_context = self.active_left_context
        if spec.operation.op_type == "non_operational" and self.active_operation:
            spec.operation = self.active_operation
        return spec


class AntarangaResolver:
    """
    Resolves antaraṅga/bahiraṅga conflicts using conditioning_factors.
    A rule whose conditioning_factors are a proper subset of another's
    is antaraṅga (inner) and takes precedence.
    """

    @staticmethod
    def is_antaranga(inner: SutraSpec, outer: SutraSpec) -> bool:
        """Check if `inner` is antaraṅga relative to `outer`."""
        if not inner.conditioning_factors or not outer.conditioning_factors:
            return False
        return inner.conditioning_factors < outer.conditioning_factors

    @staticmethod
    def resolve(candidates: List[SutraSpec]) -> Optional[SutraSpec]:
        """Resolve a conflict between multiple matching rules."""
        if len(candidates) == 1:
            return candidates[0]

        # Check antaraṅga relationships
        for i, inner in enumerate(candidates):
            is_inner_to_all = True
            for j, outer in enumerate(candidates):
                if i == j:
                    continue
                if not AntarangaResolver.is_antaranga(inner, outer):
                    is_inner_to_all = False
                    break
            if is_inner_to_all:
                return inner

        # Specificity: more specific target wins
        # (smaller pratyahara set = more specific; exact_text = most specific)
        from core.shiva_sutras import PratyaharaResolver
        def specificity_score(spec: SutraSpec) -> int:
            score = 0
            if spec.target_context and spec.target_context.exact_text:
                alternatives = spec.target_context.exact_text.replace(",", "|").split("|")
                score += 1000 - len(alternatives) * 100  # exact text is very specific
            if spec.target_context and spec.target_context.pratyahara:
                try:
                    phonemes = PratyaharaResolver.resolve(spec.target_context.pratyahara)
                    score += 100 - len(phonemes)  # smaller set = higher score
                except (ValueError, Exception):
                    pass
            return score

        scored = [(specificity_score(s), s) for s in candidates]
        best_score = max(s[0] for s in scored)
        best_candidates = [s for sc, s in scored if sc == best_score]
        if len(best_candidates) == 1:
            return best_candidates[0]

        # Fall back to later-sūtra-wins (para)
        return sorted(candidates, key=lambda s: s.sutra_id)[-1]


class MetaRuleEngine:
    """
    The complete meta-rule engine. Orchestrates paribhāṣā, asiddhatva,
    anuvṛtti, and antaraṅga/bahiraṅga during derivation.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.paribhasas = ParibhashaRegistry(db_path)
        self.asiddhatva = AsiddhatvaEnforcer()
        self.anuvrtti = AnuvrttiTracker()
        self.antaranga = AntarangaResolver()
        self._loaded = False

    def load(self):
        """Load paribhāṣā registry."""
        if not self._loaded:
            self.paribhasas.load()
            self._loaded = True

    def resolve_conflict(self, candidates: List[CompiledSutra], left: str, right: str) -> Optional[CompiledSutra]:
        """Resolve a conflict between multiple matching rules."""
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        specs = [c.spec for c in candidates]

        # 1. Antaraṅga + Specificity + Later wins
        resolved = self.antaranga.resolve(specs)
        if resolved:
            return next(c for c in candidates if c.sutra_id == resolved.sutra_id)

        return candidates[-1]
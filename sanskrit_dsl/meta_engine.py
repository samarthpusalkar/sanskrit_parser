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
from typing import Any, Dict, List, Optional, Set, Tuple

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
            spec = parser._from_vibhakti_clean(sid, sutra_dev or "", pada_cheda or "", "P")
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
        if spec.domain != self.active_domain:
            self.active_target = None
            self.active_left_context = None
            self.active_right_context = None
            self.active_operation = None
            self.active_domain = spec.domain
            return

        # Anuvṛtti carries only left/right *contextual conditions*, never the
        # target phoneme or operation of a previous sūtra. Each sūtra's target
        # and operation are its own.
        if spec.left_context:
            self.active_left_context = spec.left_context
        if spec.right_context:
            self.active_right_context = spec.right_context

    def get_inherited(self, spec: SutraSpec) -> SutraSpec:
        """Fill in missing left/right contextual slots from anuvṛtti."""
        if not spec.left_context and self.active_left_context:
            spec.left_context = self.active_left_context
        if not spec.right_context and self.active_right_context:
            spec.right_context = self.active_right_context
        return spec


class AntarangaResolver:
    """
    Resolves antaraṅga/bahiraṅga conflicts and specificity-based precedence.
    """

    @staticmethod
    def is_antaranga(inner: SutraSpec, outer: SutraSpec) -> bool:
        """Check if `inner` is antaraṅga relative to `outer` (conditioning subset)."""
        if not inner.conditioning_factors or not outer.conditioning_factors:
            return False
        return inner.conditioning_factors < outer.conditioning_factors

    @staticmethod
    def resolve(candidates: List[SutraSpec], left: str = "", right: str = "") -> Optional[SutraSpec]:
        """Resolve a conflict between multiple matching rules.

        Cascade: antaraṅga (subset) → weighted specificity (with parasavaraṇa
        priority) → later-sūtra-wins (numeric tuple ordering, not lexicographic).
        """
        if len(candidates) == 1:
            return candidates[0]

        # 1. Antaraṅga relationships.
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

        # 2. Weighted specificity with parasavaraṇa priority.
        from core.shiva_sutras import PratyaharaResolver
        from .types import _is_savarna, _META_TERM_WILDCARDS

        def context_type_score(ctx):
            if not ctx:
                return 0
            if ctx.sanjna_required:
                return 120
            if ctx.sthani_phoneme:
                return 60
            if ctx.exact_text:
                alts = [a for a in ctx.exact_text.replace(",", "|").split("|") if a]
                if all(a in _META_TERM_WILDCARDS for a in alts):
                    return 90
                return 80
            if ctx.pratyahara:
                return 40
            return 0

        def specificity_score(spec: SutraSpec) -> int:
            score = 0
            if spec.target_context and spec.target_context.exact_text:
                alts = [a for a in spec.target_context.exact_text.replace(",", "|").split("|") if a]
                score += 1000 - len(alts) * 100
            if spec.target_context and spec.target_context.pratyahara:
                try:
                    phonemes = PratyaharaResolver.resolve(spec.target_context.pratyahara)
                    score += 100 - len(phonemes)
                except (ValueError, Exception):
                    pass
            score += context_type_score(spec.right_context)
            score += context_type_score(spec.left_context)
            # Parasavaraṇa priority: a rule requiring savarṇa gets +150 when the
            # pair is actually homogeneous, so it outscores a non-savarṇa rule.
            if spec.right_context and spec.right_context.exact_text:
                alts = [a for a in spec.right_context.exact_text.replace(",", "|").split("|") if a]
                if all(a in _META_TERM_WILDCARDS for a in alts) and left and right:
                    if _is_savarna(left[-1], right[0]):
                        score += 150
            return score

        scored = [(specificity_score(s), s) for s in candidates]
        best_score = max(s[0] for s in scored)
        best_candidates = [s for sc, s in scored if sc == best_score]
        if len(best_candidates) == 1:
            return best_candidates[0]

        # 3. Later-sūtra-wins (para) with NUMERIC tuple ordering.
        return sorted(best_candidates, key=lambda s: _sutra_sort_key(s.sutra_id))[-1]


def _sutra_sort_key(sutra_id: str):
    """Numeric (adhyaya, pada, sutra_no) tuple for correct ordering.

    Fixes the lexicographic bug where '6.1.9' sorted after '6.1.77'.
    """
    parts = sutra_id.split(".")
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2])) if len(parts) == 3 else (0, 0, 0)
    except (ValueError, IndexError):
        return (0, 0, 0)


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

    def resolve_conflict(self, candidates: List[CompiledSutra], left: str, right: str,
                         context: Any = None) -> Optional[CompiledSutra]:
        """Resolve a conflict between multiple matching rules.

        Cascade: apavāda (niyama debar) → antaraṅga/specificity/para.
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # Apavāda / niyama: a niyama (prohibition) rule debars a matching vidhi.
        niyama_ids = {c.sutra_id for c in candidates if c.spec.rule_type == "niyama"}
        if niyama_ids:
            debarrable = set()
            for n in candidates:
                if n.spec.rule_type != "niyama":
                    continue
                for v in candidates:
                    if v.spec.rule_type == "vidhi" and v.sutra_id != n.sutra_id:
                        if self._scope_subsumes(n.spec, v.spec):
                            debarrable.add(v.sutra_id)
            if debarrable:
                candidates = [c for c in candidates if c.sutra_id not in debarrable]
                if len(candidates) == 1:
                    return candidates[0]
                if not candidates:
                    return None

        # Parasavaraṇa debar: on a homogeneous pair, a rule requiring savarṇa
        # debars a rule that does not (e.g. 6.1.101 dirgha debars 6.1.87 guṇa
        # on a+a). This is an asiddhatva-style precedence, not just a score bump.
        from .types import _is_savarna, _META_TERM_WILDCARDS
        if left and right and _is_savarna(left[-1], right[0]):
            savarna_rules = []
            non_savarna_rules = []
            for c in candidates:
                rc = c.spec.right_context
                is_sav = (rc and rc.exact_text and
                          all(a in _META_TERM_WILDCARDS for a in
                              rc.exact_text.replace(",", "|").split("|") if a))
                (savarna_rules if is_sav else non_savarna_rules).append(c)
            if savarna_rules and non_savarna_rules:
                debarrable = {c.sutra_id for c in non_savarna_rules}
                candidates = [c for c in candidates if c.sutra_id not in debarrable]
                if len(candidates) == 1:
                    return candidates[0]
                if not candidates:
                    return None

        specs = [c.spec for c in candidates]
        resolved = self.antaranga.resolve(specs, left, right)
        if resolved:
            return next(c for c in candidates if c.sutra_id == resolved.sutra_id)
        return sorted(candidates, key=lambda c: _sutra_sort_key(c.sutra_id))[-1]

    @staticmethod
    def _scope_subsumes(niyama: SutraSpec, vidhi: SutraSpec) -> bool:
        """Does the niyama's condition scope subsume the vidhi's?"""
        # A niyama with no target context is too abstract to debar a specific vidhi.
        if not niyama.target_context:
            return False
        if vidhi.target_context:
            if niyama.target_context.pratyahara and vidhi.target_context.pratyahara:
                if niyama.target_context.pratyahara == vidhi.target_context.pratyahara:
                    return True
            if niyama.target_context.exact_text and vidhi.target_context.exact_text:
                n_alts = set(niyama.target_context.exact_text.replace(",", "|").split("|"))
                v_alts = set(vidhi.target_context.exact_text.replace(",", "|").split("|"))
                if v_alts <= n_alts:
                    return True
        # Default conservative: do not debar unless scope is clearly shown.
        return False
"""
DSL Executor — sanskrit_dsl/executor.py

Staged Pāṇinian execution engine.

Phases (mirroring the Pāṇinian prakriyā):
  0. Nipātana lookup — irregular ready-made forms.
  1. Saṃjñā tagging — assign technical labels via SanjanaTagger.
  2. Pragṛhya prakṛtibhāva (6.1.125) — pragṛhya + vowel-initial right → no sandhi.
  3. Sapādāsaptādhyāyī (1.1–8.1) — iterate to a fixpoint (cap 15).
  4. Tripāḍī (8.2–8.4) — strict chapter order, pūrvatrāsiddham via DerivationTimeline.

The DerivationTimeline snapshots the original input and per-chapter checkpoints,
so a later rule cannot see an earlier rule's output when asiddhatva forbids it.
This fixes the cascading-corruption and over-application bugs.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .compiler import SutraCompiler
from .meta_engine import MetaRuleEngine
from .types import CompiledSutra, SutraSpec
from .execution_context import ExecutionContext
from .derivation_timeline import DerivationTimeline, DerivationStep, chapter_of, pada_of

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


class DSLExecutor:
    """Executes Pāṇinian sandhi using the staged prakriyā model."""

    def __init__(self):
        self.compiler = SutraCompiler()
        self.meta_engine = MetaRuleEngine()
        self._all_compiled: Optional[List[CompiledSutra]] = None
        self._sapada_rules: List[CompiledSutra] = []
        self._tripadi_rules: List[CompiledSutra] = []
        self._nipatana: Optional[Dict[Tuple[str, str], str]] = None

    def _ensure_compiled(self):
        if self._all_compiled is not None:
            return
        self.meta_engine.load()
        self._all_compiled = self.compiler.compile_all()
        self._sapada_rules = [s for s in self._all_compiled if s.spec.domain != "tripadi"]
        self._tripadi_rules = [s for s in self._all_compiled if s.spec.domain == "tripadi"]
        # Sandhi-executable rules: only 6.x (sandhi/ekādeśa) and 8.1
        # (pada-rules visible to sapāda). Chapter 7.4 is morphological
        # (stri/viḍ/iṭ/guṇa on stems) and must NOT fire in the sandhi pass.
        # Derivational rules (3.x, 4.x, 5.x) belong to the MorphExecutor.
        self._sandhi_sapada = [
            s for s in self._sapada_rules
            if s.sutra_id.split(".")[0] == "6"
            or s.sutra_id.startswith("8.1")
        ]

    def _ensure_nipatana(self):
        if self._nipatana is not None:
            return
        self._nipatana = {}
        if os.path.exists(DB_PATH):
            try:
                conn = sqlite3.connect(DB_PATH)
                for row in conn.execute(
                    "SELECT left_token, right_token, output FROM nipatana_lexicon"
                ).fetchall():
                    l, r, out = row[0] or "", row[1] or "", row[2] or ""
                    self._nipatana[(l, r)] = out
                    if r == "":
                        self._nipatana[(l, None)] = out
                conn.close()
            except Exception:
                pass

    def _nipatana_lookup(self, left: str, right: str) -> Optional[str]:
        self._ensure_nipatana()
        if (left, right) in self._nipatana:
            return self._nipatana[(left, right)]
        if (left, None) in self._nipatana and not right:
            return self._nipatana[(left, None)]
        return None

    # Saṃjñās that imply a morphological/derivational context. If a rule
    # requires one of these, it belongs to the MorphExecutor, not the sandhi
    # pass. This is a principled guard based on the rule's own metadata.
    _MORPHOLOGICAL_SANJNAS = {
        "dhatu", "sup", "ting", "krt", "ardhadhatuka", "sarvadhatuka",
        "gati", "sarvanamasthana", "atmanepada",
    }

    # Recognized sandhi/phonological operation types. A rule in the sandhi
    # pass must use one of these; everything else belongs to morphology.
    _SANDHI_OP_TYPES = frozenset({
        "exact_substitute", "substitute", "merge", "elide", "augment",
        "prakritibhava", "bijection", "bijection_substitute", "yan",
        "dirgha", "savarna_long", "ekadesha_savarna_dirgha",
        "guna", "ekadesha_guna",
        "vrddhi", "ekadesha_vrddhi",
        "visarga_sandhi", "anusvara", "natva", "samprasarana",
        "pararupa", "purva_rupa",
        "prohibit",
    })

    # Vowel-sandhi operations (guṇa, vṛddhi, dīrgha, yaṇ, bijection) occur only in
    # chapter 6.1. The Tripāḍī (8.2–8.4) never performs vowel merging; it handles
    # visarga, anusvāra, natva, and final-consonant substitutions. Any 8.2–8.4
    # rule extracted as a vowel-sandhi operation is therefore a mis-extraction
    # for the sandhi pass (e.g. 8.2.77 "hali ca" is an exception, not dirgha).
    _VOWEL_SANDHI_OPS = frozenset({
        "ekadesha_guna", "guna",
        "ekadesha_vrddhi", "vrddhi",
        "ekadesha_savarna_dirgha", "dirgha", "savarna_long",
        "ekadesha_yan", "yan",
        "bijection", "bijection_substitute",
    })

    # Conditioning-factor keywords that are evaluable in the sandhi pass.
    # Any factor containing a keyword outside this set is assumed to reference
    # morphology/semantics and is blocked from the sandhi pass.
    _EVALUABLE_FACTOR_KEYWORDS = frozenset({
        "samhita", "saMhitA", "sahitA",
        "bahira", "antara",
        "pada-final", "padanta",
        "savarRa", "savarna", "savRNa",
        "vowel", "consonant", "diphthong",
        "final", "initial",
        "followed by", "before", "after",
        "word:", "specific word",
    })

    @staticmethod
    def _is_sandhi_eligible(rule: CompiledSutra, strict: bool = False) -> bool:
        """Return True if the rule's metadata says it belongs in the sandhi pass.

        A rule is sandhi-eligible when:
        - It was LLM-extracted (the vibhakti fallback is not reliable enough
          for autonomous sandhi execution), AND
        - It has a recognized sandhi/phonological operation type, AND
        - It does not reference a morphological category that requires the
          MorphExecutor, AND
        - It does not require a morphological saṃjñā (dhatu, sup, tiṅ, ...).

        In `strict` mode (Tripāḍī), vowel-sandhi operations are additionally
        excluded because they do not occur in the Tripāḍī.
        """
        spec = rule.spec
        # The sandhi pass only trusts LLM-extracted metadata. The vibhakti
        # fallback is kept for morphology and for human review, but it must not
        # autonomously corrupt boundary sandhi.
        if spec.parsed_by != "llm_extract":
            return False

        op_type = spec.operation.op_type
        if op_type not in DSLExecutor._SANDHI_OP_TYPES:
            return False
        if strict and op_type in DSLExecutor._VOWEL_SANDHI_OPS:
            return False

        morph = (spec.target_context and spec.target_context.morphological_category) or ""
        if morph and morph.lower() not in {"avyaya", "nipata", "padanta", "", None}:
            return False

        def _ctx_requires_morphology(ctx):
            if not ctx:
                return False
            required = ctx.sanjna_required or set()
            prohibited = ctx.prohibit_if_sanjna or set()
            return bool(
                (required | prohibited) & DSLExecutor._MORPHOLOGICAL_SANJNAS
            )

        if any(_ctx_requires_morphology(c) for c in
               (spec.target_context, spec.left_context, spec.right_context)):
            return False

        return True

    @staticmethod
    def _factors_are_evaluable_in_sandhi(factors) -> bool:
        """Check that every conditioning factor is sandhi-evaluable.

        A factor is evaluable if it contains at least one known phonological
        keyword. Factors that reference roots, verb classes, sentence types,
        etc. are not evaluable in the sandhi pass.
        """
        for f in factors:
            lf = f.lower()
            if not any(kw.lower() in lf for kw in DSLExecutor._EVALUABLE_FACTOR_KEYWORDS):
                return False
        return True

    @staticmethod
    def _passes_conditioning_factors(rule: CompiledSutra, left: str, right: str,
                                     strict: bool = False) -> bool:
        """Gate conditioning factors for the sandhi pass.

        1. Sandhi-eligibility is checked first via rule metadata (parsed_by,
           operation type, morphological_category, required/prohibited saṃjñās).
        2. Every conditioning factor must be sandhi-evaluable (phonological).
        3. Word-specific factors ("specific words: X, Y") → require left ∈ {X,Y}.
        4. If `strict=True` (Tripāḍī), a rule must also carry at least one
           additional contextual constraint beyond a bare target pratyāhāra.
        """
        if not DSLExecutor._is_sandhi_eligible(rule, strict=strict):
            return False

        spec = rule.spec
        factors = spec.conditioning_factors

        if factors and not DSLExecutor._factors_are_evaluable_in_sandhi(factors):
            return False

        word_restrictions = []
        for f in factors:
            lf = f.lower()
            if "specific word" in lf or lf.startswith("word:"):
                parts = f.replace(",", " ").split()
                for p in parts:
                    p = p.strip()
                    if p and p.lower() not in ("specific", "words:", "word:", "words"):
                        word_restrictions.append(p)

        if word_restrictions:
            return left in word_restrictions

        if strict:
            has_context = (
                spec.left_context is not None
                or spec.right_context is not None
                or word_restrictions
                or (spec.target_context and spec.target_context.exact_text)
            )
            if not has_context:
                return False

        return True

    def _filter_matching(self, rules: List[CompiledSutra], left: str,
                         right: str, ctx: ExecutionContext,
                         strict: bool = False) -> List[CompiledSutra]:
        """Return rules that match AND pass conditioning-factor enforcement."""
        out = []
        for s in rules:
            if s.spec.target_context is None:
                continue
            if not s.matches(left, right, ctx):
                continue
            if not self._passes_conditioning_factors(s, left, right, strict=strict):
                continue
            out.append(s)
        return out

    def execute_sandhi(self, left: str, right: str,
                       left_morph: Optional[Dict[str, Any]] = None,
                       right_morph: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Apply the staged Pāṇinian derivation to join left + right."""
        self._ensure_compiled()

        timeline = DerivationTimeline()
        timeline.checkpoint("original", left, right)
        ctx = ExecutionContext(
            left_token=left, right_token=right, trace=timeline,
            morphological_features={"left": left_morph or {}, "right": right_morph or {}}
        )
        applied_rule_ids: List[str] = []
        trace_steps: List[Dict] = []

        # Phase 0 — Nipātana lookup.
        nip = self._nipatana_lookup(left, right)
        if nip is not None:
            return {
                "joined": nip, "applied_rule_ids": ["nipatana"],
                "trace_steps": [{"sutra_id": "nipatana", "left_before": left,
                                  "right_before": right, "left_after": nip, "right_after": ""}],
                "timeline": timeline, "source": "nipatana",
            }

        # Phase 1 — Saṃjñā tagging.
        from core.sanjña_tagger import SanjanaTagger
        left_morph = ctx.morphological_features.get("left", {})
        right_morph = ctx.morphological_features.get("right", {})
        sanjna_map = SanjanaTagger.tag(left, right, left_morph=left_morph,
                                        right_morph=right_morph)
        ctx.set_sanjnas("left", sanjna_map.get("left", set()))
        ctx.set_sanjnas("right", sanjna_map.get("right", set()))

        # Phase 2 — Pragṛhya prakṛtibhāva (6.1.125): no sandhi if left is pragṛhya
        # and right starts with a vowel.
        if "pragrhya" in ctx.sanjna_map.get("left", set()) and right:
            from core.shiva_sutras import PratyaharaResolver
            try:
                vowels = set(PratyaharaResolver.resolve_list("aC"))
                if right[0] in vowels:
                    return {
                        "joined": left + " " + right, "applied_rule_ids": [],
                        "trace_steps": [{"sutra_id": "6.1.125", "left_before": left,
                                          "right_before": right, "left_after": left,
                                          "right_after": right, "pragrhya": True}],
                        "timeline": timeline, "source": "pragrhya",
                    }
            except Exception:
                pass

        def _inherit(rules: List[CompiledSutra]) -> List[CompiledSutra]:
            """Apply runtime anuvṛtti to rules with empty contexts.

            Preserves all original spec metadata (including parsed_by) and only
            fills in contexts that the tracker can inherit.
            """
            out = []
            for r in rules:
                inherited = self.meta_engine.anuvrtti.get_inherited(r.spec)
                spec = SutraSpec(
                    sutra_id=r.sutra_id,
                    sutra_text=r.spec.sutra_text,
                    operation=r.spec.operation,
                    target_context=inherited.target_context or r.spec.target_context,
                    left_context=inherited.left_context or r.spec.left_context,
                    right_context=inherited.right_context or r.spec.right_context,
                    conditioning_factors=r.spec.conditioning_factors,
                    applicable_paribhasas=r.spec.applicable_paribhasas,
                    domain=r.spec.domain,
                    anuvrtti_carries=r.spec.anuvrtti_carries,
                    commentary_notes=r.spec.commentary_notes,
                    parsed_by=r.spec.parsed_by,
                    confidence=r.spec.confidence,
                    hurdles=r.spec.hurdles,
                )
                out.append(CompiledSutra(sutra_id=r.sutra_id, spec=spec))
            return out

        # Phase 3 — Sapādāsaptādhyāyī (6.x, 7.x, 8.1): iterate to a fixpoint.
        # Multiple rules may apply in sequence on the same boundary in the
        # sapāda derivation (e.g. 6.1.87 then 6.1.52). We cap at 15 to prevent
        # runaway loops from corrupt output.
        cur_left, cur_right = left, right
        sapada_applied = set()
        for _iteration in range(15):
            ctx.left_token, ctx.right_token = cur_left, cur_right
            inherited_rules = _inherit(self._sandhi_sapada)
            sapada_matches = self._filter_matching(
                inherited_rules, cur_left, cur_right, ctx
            )
            if not sapada_matches:
                break
            winner = self.meta_engine.resolve_conflict(
                sapada_matches, cur_left, cur_right, ctx
            )
            if not winner:
                break
            # Asiddhatva visibility check: a later chapter rule is invisible to
            # an earlier chapter rule outside the Tripāḍī this is always True.
            winner_chapter = chapter_of(winner.sutra_id)
            if not timeline.is_visible("6.1", winner_chapter):
                break
            new_left, new_right = winner.apply(cur_left, cur_right, ctx)
            if new_left == cur_left and new_right == cur_right:
                break
            if winner.sutra_id in sapada_applied:
                break
            sapada_applied.add(winner.sutra_id)
            applied_rule_ids.append(winner.sutra_id)
            trace_steps.append({
                "sutra_id": winner.sutra_id,
                "left_before": cur_left, "right_before": cur_right,
                "left_after": new_left, "right_after": new_right,
                "phase": "sapada",
            })
            self.meta_engine.anuvrtti.step(winner.spec)
            cur_left, cur_right = new_left, new_right

        # Phase 4 — Tripāḍī (8.2–8.4): strict chapter order with pūrvatrāsiddham.
        # Each pāda's rules match against the checkpoint state (pre-pāda),
        # not against later pāda mutations.
        tripadi_by_pada: Dict[int, List[CompiledSutra]] = {2: [], 3: [], 4: []}
        for s in self._tripadi_rules:
            p = pada_of(s.sutra_id)
            if p in tripadi_by_pada:
                tripadi_by_pada[p].append(s)

        for pada in (2, 3, 4):
            chapter = f"8.{pada}"
            # Snapshot the state before this pāda's rules fire (pūrvatrāsiddham).
            timeline.checkpoint(chapter, cur_left, cur_right)
            checkpoint_state = timeline.get_state_before_chapter(chapter)
            check_left, check_right = checkpoint_state or (cur_left, cur_right)
            rules = tripadi_by_pada[pada]
            ctx.left_token, ctx.right_token = check_left, check_right
            inherited_rules = _inherit(rules)
            tripadi_matches = self._filter_matching(
                inherited_rules, check_left, check_right, ctx, strict=True
            )
            if not tripadi_matches:
                continue
            winner = self.meta_engine.resolve_conflict(
                tripadi_matches, check_left, check_right, ctx
            )
            if winner is None:
                continue
            new_left, new_right = winner.apply(check_left, check_right, ctx)
            if new_left == check_left and new_right == check_right:
                continue
            applied_rule_ids.append(winner.sutra_id)
            trace_steps.append({
                "sutra_id": winner.sutra_id,
                "left_before": check_left, "right_before": check_right,
                "left_after": new_left, "right_after": new_right,
                "phase": f"tripadi_{pada}",
            })
            self.meta_engine.anuvrtti.step(winner.spec)
            cur_left, cur_right = new_left, new_right

        return {
            "joined": cur_left + cur_right,
            "applied_rule_ids": applied_rule_ids,
            "trace_steps": trace_steps,
            "timeline": timeline,
            "source": "dsl",
        }

    def list_loaded_rules(self) -> List[str]:
        """Return all compiled rule IDs."""
        self._ensure_compiled()
        return [s.sutra_id for s in self._all_compiled]
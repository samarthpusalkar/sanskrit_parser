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
from .types import CompiledSutra
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

    # Whitelist of phonological/sandhi-relevant conditioning-factor keywords.
    _EVALUABLE_FACTOR_KEYWORDS = (
        "samhita", "saMhitA", "sahitA", "bahira", "antara",
        "pada-final", "padanta",
        "savarRa", "savarna", "savRNa",
        "followed by", "word:", "specific word",
    )
    # Blacklist: if ANY factor contains one of these, the rule is blocked
    # from the sandhi pass (it requires morphological/semantic context).
    _NON_EVALUABLE_FACTOR_KEYWORDS = (
        "sentence", "sense", "finite verb", "ti\u1e45", "tiG",
        "censure", "benediction", "command", "praiza", "incomplete",
        "verb", "meaning", "semantic",
        "prayoga", "karma", "kAraka", "vacana", "liGa", "li\u1e45", "prayojana",
        "praSna", "AKyAna", "anantya", "anftaH",
        "pluta", "plUta", "protracted",
        "after roots", "after root", "root ",
        "pragrhya", "pragRhya",
        "dUrAt", "dUrAddhUte", "dUraddhUte",
        "svarita", "anudAtta", "udAtta", "svarit",
        "kziti", "zazi", "zveta", "puroqA", "avayA",
        "AmreDita", "amreDita",
        "calling from afar", "end of sentence",
        "bhartasane", "bhartsane", "bhartrisneha", "bhartrIzneha",
        "kopa", "kutsana", "asUyA", "sammati",
        "bhASAyAm", "bhāṣāyām", "speech",
        "vicAryamANAnAm", "vicāryamāṇānām", "alternatives",
        "odit", "odit root",
        "pUrvam", "pūrvam",
        "vAkyasya", "vākyasya",
        "ekaikasya", "prAcAm",
        "Atmanepada", "Atmane",
    )

    @staticmethod
    def _passes_conditioning_factors(rule: CompiledSutra, left: str, right: str,
                                     strict: bool = False) -> bool:
        """Gate conditioning factors for the sandhi pass.

        1. No factors → allow (purely phonological rules like 6.1.77).
        2. Word-specific factors ("specific words: X, Y") → require left ∈ {X,Y}.
        3. If ANY factor contains a non-evaluable (semantic/morphological)
           keyword → block. These belong to the morph executor.
        4. In strict mode (Tripāḍī): additionally require that every remaining
           factor matches the phonological whitelist — otherwise block.
        5. In strict mode (Tripāḍī): a rule whose only condition is a bare
           pratyāhāra target (no left/right context, no word restriction, no
           saṃjñā gate) is treated as under-specified and blocked, because
           Tripāḍī rules normally carry morphological/semantic context.
        """
        spec = rule.spec
        factors = spec.conditioning_factors

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

        for f in factors:
            if any(kw.lower() in f.lower()
                   for kw in DSLExecutor._NON_EVALUABLE_FACTOR_KEYWORDS):
                return False

        if strict:
            for f in factors:
                if not any(kw.lower() in f.lower()
                           for kw in DSLExecutor._EVALUABLE_FACTOR_KEYWORDS):
                    return False

            # Structural guard: bare pratyāhāra target with no other context is
            # almost always an under-extracted Tripāḍī rule that would match
            # every boundary and corrupt output (e.g. 8.2.77 target=iK, no
            # right_context despite "hali ca" requiring a consonant context).
            if (spec.target_context
                    and spec.target_context.pratyahara
                    and not spec.target_context.exact_text
                    and not spec.left_context
                    and not spec.right_context
                    and not spec.target_context.sanjna_required
                    and not spec.target_context.prohibit_if_sanjna):
                return False

            # Tripāḍī structural guard 2: vowel-sandhi operations (guṇa,
            # vṛddhi, dīrgha, yaṇ) do not occur in the Tripāḍī. Any 8.2–8.4 rule
            # extracted as one of these is a mis-extraction for the sandhi
            # pass and would corrupt output (e.g. 8.2.77 target=iK op=dirgha).
            tripadi_vowel_ops = (
                "ekadesha_guna", "guna", "ekadesha_vrddhi", "vrddhi",
                "ekadesha_savarna_dirgha", "dirgha", "savarna_long",
                "ekadesha_yan", "yan", "bijection_substitute", "bijection",
            )
            if spec.operation.op_type in tripadi_vowel_ops:
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

    def execute_sandhi(self, left: str, right: str) -> Dict[str, Any]:
        """Apply the staged Pāṇinian derivation to join left + right."""
        self._ensure_compiled()

        timeline = DerivationTimeline()
        timeline.checkpoint("original", left, right)
        ctx = ExecutionContext(left_token=left, right_token=right, trace=timeline)
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
        sanjna_map = SanjanaTagger.tag(left, right)
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

        # Phase 3 — Sapādāsaptādhyāyī (6.x, 7.x, 8.1): apply the single best
        # matching rule once. (Iteration across *different* boundaries belongs
        # to morph derivation, not a single-boundary sandhi pass — re-firing on
        # the same boundary cascades and corrupts correct output.)
        cur_left, cur_right = left, right
        ctx.left_token, ctx.right_token = cur_left, cur_right
        sapada_matches = self._filter_matching(self._sandhi_sapada, cur_left, cur_right, ctx)
        if sapada_matches:
            winner = self.meta_engine.resolve_conflict(sapada_matches, cur_left, cur_right, ctx)
            if winner:
                new_left, new_right = winner.apply(cur_left, cur_right, ctx)
                if new_left != cur_left or new_right != cur_right:
                    step = DerivationStep(
                        sutra_id=winner.sutra_id, rule_chapter=chapter_of(winner.sutra_id),
                        rule_pada=pada_of(winner.sutra_id),
                        left_before=cur_left, right_before=cur_right,
                        left_after=new_left, right_after=new_right,
                    )
                    timeline.record(step)
                    applied_rule_ids.append(winner.sutra_id)
                    trace_steps.append({
                        "sutra_id": winner.sutra_id,
                        "left_before": cur_left, "right_before": cur_right,
                        "left_after": new_left, "right_after": new_right,
                        "phase": "sapada",
                    })
                    cur_left, cur_right = new_left, new_right

        # Phase 4 — Tripāḍī (8.2–8.4): strict chapter order with asiddhatva.
        tripadi_by_pada: Dict[int, List[CompiledSutra]] = {2: [], 3: [], 4: []}
        for s in self._tripadi_rules:
            p = pada_of(s.sutra_id)
            if p in tripadi_by_pada:
                tripadi_by_pada[p].append(s)

        for pada in (2, 3, 4):
            chapter = f"8.{pada}"
            # Snapshot the state before this pāda's rules fire (pūrvatrāsiddham).
            timeline.checkpoint(chapter, cur_left, cur_right)
            rules = tripadi_by_pada[pada]
            ctx.left_token, ctx.right_token = cur_left, cur_right
            tripadi_matches = self._filter_matching(rules, cur_left, cur_right, ctx, strict=True)
            if not tripadi_matches:
                continue
            winner = self.meta_engine.resolve_conflict(tripadi_matches, cur_left, cur_right, ctx)
            if winner is None:
                continue
            new_left, new_right = winner.apply(cur_left, cur_right, ctx)
            if new_left == cur_left and new_right == cur_right:
                continue
            step = DerivationStep(
                sutra_id=winner.sutra_id, rule_chapter=chapter,
                rule_pada=pada,
                left_before=cur_left, right_before=cur_right,
                left_after=new_left, right_after=new_right,
            )
            timeline.record(step)
            applied_rule_ids.append(winner.sutra_id)
            trace_steps.append({
                "sutra_id": winner.sutra_id,
                "left_before": cur_left, "right_before": cur_right,
                "left_after": new_left, "right_after": new_right,
                "phase": f"tripadi_{pada}",
            })
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
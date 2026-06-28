"""
Universal Pāṇinian Rule Engine Dispatcher and Operational Conflict Resolver.

Manages active sūtra registries, Tripādī ordering rules (8.2.1 - 8.4.68),
and conflict resolution via Paribhāṣās (e.g. 1.4.2 vipratiṣedhe paraṃ kāryam)
with LRU-cached rule ordering and revert results.
"""

from typing import List, Dict, Any, Tuple, Optional
from rules.base import PaniniRule, VidhiRule
import functools


NATIVE_REPHA_LEXICON = frozenset({'prātar', 'punar', 'antar', 'svar', 'prādur', 'sanutar', 'pratar', 'nitar', 'catur', 'ahor', 'prAtar', 'punar', 'antar', 'svar', 'prAdur', 'sanutar', 'pratar', 'nitar', 'catur', 'ahor'})


class UniversalRuleEngine:
    """Master rule engine orchestrating grammatical transformations."""

    _instance = None

    @classmethod
    def get_instance(cls) -> 'UniversalRuleEngine':
        if cls._instance is None:
            cls._instance = cls(auto_compile=True)
        return cls._instance

    def __init__(self, auto_compile: bool = True):
        self._rules: List[PaniniRule] = []
        self._ordered_cache: Dict[str, List[PaniniRule]] = {}
        self._revert_cache: Dict[str, List[Tuple[str, str]]] = {}
        self._nipatana_cache: Optional[Dict] = None
        if auto_compile:
            from compiler.pipeline import MasterCompilerPipeline
            self._rules.extend(MasterCompilerPipeline.compile_all())

    def register_rule(self, rule: PaniniRule):
        self._rules.append(rule)
        self._ordered_cache.clear()
        self._revert_cache.clear()

    # ------------------------------------------------------------------
    # Nipātana Lexicon  (Phase 0)
    # ------------------------------------------------------------------

    def _load_nipatana(self) -> Dict:
        """Load nipātana_lexicon table from DB (cached)."""
        if self._nipatana_cache is not None:
            return self._nipatana_cache
        import sqlite3, os
        db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        self._nipatana_cache = {}
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(db)
                for row in conn.execute("SELECT left_token, right_token, output FROM nipatana_lexicon"):
                    lt, rt, out = row
                    self._nipatana_cache[(lt, rt or "")] = out
                conn.close()
            except Exception:
                pass
        return self._nipatana_cache

    def _nipatana_lookup(self, left: str, right: str) -> Optional[str]:
        """Return prescribed Nipātana output or None."""
        lex = self._load_nipatana()
        for key in [(left, right), (left, "")]:
            if key in lex:
                return lex[key]
        return None

    # ------------------------------------------------------------------
    # Rule ordering helpers
    # ------------------------------------------------------------------

    def _get_sandhi_ordered_rules(self, scope: str = "external") -> List[PaniniRule]:
        if scope in self._ordered_cache:
            return self._ordered_cache[scope]

        def _sort_key(r: PaniniRule) -> Tuple[int, int, float]:
            spec = getattr(r, "spec", None)
            parts = r.sutra_id.split(".")
            try:
                num_id = float(parts[0]) * 10000 + float(parts[1]) * 100 + float(parts[2])
            except Exception:
                num_id = 999999.0

            domain = getattr(spec, "governance", {}).get("domain", "sapada") if spec and isinstance(getattr(spec, "governance", None), dict) else getattr(getattr(spec, "governance", None), "domain", "sapada")
            domain_rank = 1 if domain == "tripadi" or num_id >= 80200.0 else 0

            def _get_specificity(r: PaniniRule) -> float:
                sp = getattr(r, "spec", None)
                s = 0.0
                if sp:
                    for ctx_obj in [sp.left_context, sp.right_context, sp.target_context]:
                        if ctx_obj:
                            if getattr(ctx_obj, "tokens_required", None):
                                s += sum(100.0 / len(t) for t in ctx_obj.tokens_required)
                            if ctx_obj.exact_text:
                                if ctx_obj.exact_text in {"PAUSE_OR_VOICED", "LONG_VOWEL", "SHORT_VOWEL", "C", "V", "VOWEL", "CONSONANT"}:
                                    s += 2.0
                                else:
                                    s += 100.0 / (ctx_obj.exact_text.count("|") + 1)
                            if ctx_obj.features_required:
                                s += len(ctx_obj.features_required) * 10.0
                            if ctx_obj.pratyahara:
                                s += 5.0
                return s

            op_obj = getattr(spec, "operation", None) if spec else None
            op_type = getattr(op_obj, "op_type", "") if op_obj else ""
            is_prohibit = 0 if op_type in {"prohibit", "prakritibhava"} else 1

            sutra_order = num_id if domain_rank == 1 else -num_id
            if domain_rank == 1:
                return (domain_rank, is_prohibit, sutra_order, -_get_specificity(r))
            return (domain_rank, is_prohibit, -_get_specificity(r), sutra_order)

        def _is_sandhi_rule(r: PaniniRule) -> bool:
            spec = getattr(r, "spec", None)
            op = getattr(spec.operation, "op_type", "") if spec and spec.operation else ""
            if op in {"non_operational", "governance", "sanjna_substitute"}:
                return False
            gov = getattr(spec, "governance", {})
            source = gov.get("source", "") if isinstance(gov, dict) else getattr(gov, "source", "")
            if source == "seed":
                return True
            dom = gov.get("domain", "") if isinstance(gov, dict) else getattr(gov, "domain", "")
            if dom in {"samhita", "tripadi"}:
                return True
            return False

        rules_pool = []
        if scope == "external":
            for r in self._rules:
                if _is_sandhi_rule(r):
                    rules_pool.append(r)
        else:
            rules_pool = self._rules
        ordered = sorted(rules_pool, key=_sort_key)
        self._ordered_cache[scope] = ordered
        return ordered

    # ------------------------------------------------------------------
    # Specificity scorer
    # ------------------------------------------------------------------

    @staticmethod
    def _get_spec(r: PaniniRule) -> float:
        sp = getattr(r, "spec", None)
        s = 0.0
        if sp:
            for ctx_obj in [sp.left_context, sp.right_context, sp.target_context]:
                if ctx_obj:
                    if getattr(ctx_obj, "tokens_required", None):
                        s += sum(1000.0 for _ in ctx_obj.tokens_required)
                    if ctx_obj.exact_text:
                        if ctx_obj.exact_text in {"PAUSE_OR_VOICED", "LONG_VOWEL", "SHORT_VOWEL", "C", "V", "VOWEL", "CONSONANT"}:
                            s += 2.0
                        else:
                            s += 100.0 / (ctx_obj.exact_text.count("|") + 1)
                    if ctx_obj.features_required:
                        s += len(ctx_obj.features_required) * 10.0
                    if ctx_obj.pratyahara:
                        s += 5.0
        return s

    # ------------------------------------------------------------------
    # Forward dispatch
    # ------------------------------------------------------------------

    def dispatch_forward(self, left: str, right: str, context: Dict[str, Any] = None) -> Tuple[str, str]:
        """
        Apply sequential forward sandhi/morphological transformation rules.

        Execution phases (Pāṇinian order):
          Phase 0 — Nipātana check (lexicon override before any rules)
          Phase 1 — Sañjñā tagging (compute token-level labels)
          Phase 2 — Prakṛtibhāva check (Pragṛhya: no sandhi at all)
          Phase 3 — Sapādāsaptādhyāyī (rules 1.1–8.1, highest-spec first)
          Phase 4 — Tripādī (rules 8.2–8.4, strict chapter order + asiddhatva)
        """
        from rule_engine.context import ExecutionContext
        from rule_engine.trace import DerivationTrace
        from core.sanjña_tagger import SanjanaTagger

        raw_ctx = context or {}
        is_samasa = raw_ctx.get("is_samasa", False)

        exec_ctx = ExecutionContext(
            left_token=left,
            right_token=right,
            is_samasa=is_samasa,
        )

        # --- Phase 0: Nipātana lookup ---
        nipatana_out = self._nipatana_lookup(left, right)
        if nipatana_out is not None:
            return nipatana_out, ""

        # --- Phase 1: Sañjñā tagging ---
        morph_left = raw_ctx.get("morph_left", {})
        morph_right = raw_ctx.get("morph_right", {})
        exec_ctx.sanjña_map = SanjanaTagger.tag(left, right, morph_left, morph_right)

        # --- Phase 2: Pragṛhya Prakṛtibhāva check (6.1.125) ---
        if "pragrhya" in exec_ctx.sanjña_map.get("left", set()):
            from core.phonology import VOWELS
            if right and right[0] in VOWELS:
                return left + " ", right

        # Initialise derivation trace
        exec_ctx.trace = DerivationTrace(initial_left=left, initial_right=right)

        cur_l, cur_r = left, right
        scope = raw_ctx.get("scope", "external")
        ordered = self._get_sandhi_ordered_rules(scope=scope)

        sapada_rules = [
            r for r in ordered
            if not (r.sutra_id.startswith("8.2") or r.sutra_id.startswith("8.3") or r.sutra_id.startswith("8.4"))
            and getattr(getattr(r, "spec", None), "governance", {}).get("domain", "sapada") != "tripadi"
        ]
        tripadi_rules = [r for r in ordered if r not in sapada_rules]
        sapada_rules.sort(key=self._get_spec, reverse=True)

        applied_rules = exec_ctx.trace.rules_applied()

        # --- Phase 3: Sapādāsaptādhyāyī ---
        max_steps = 15
        for _ in range(max_steps):
            mutated = False
            for r in sapada_rules:
                if r.sutra_id in applied_rules:
                    continue
                if cur_l in NATIVE_REPHA_LEXICON and getattr(r.spec, "target_context", None) and getattr(r.spec.target_context, "exact_text", "") == "s|H|r":
                    continue
                if r.matches(cur_l, cur_r, exec_ctx):
                    op_type = getattr(getattr(r, "spec", None), "operation", None)
                    if op_type and getattr(op_type, "op_type", "") in {"prohibit", "prakritibhava"}:
                        return cur_l, cur_r
                    new_l, new_r = r.apply(cur_l, cur_r, exec_ctx)
                    if new_l != cur_l or new_r != cur_r:
                        consumed = cur_l[-1] if cur_l else ""
                        exec_ctx.trace.record(
                            r.sutra_id, cur_l, cur_r, new_l, new_r,
                            consumed=consumed, emitted=""
                        )
                        cur_l, cur_r = new_l, new_r
                        applied_rules = exec_ctx.trace.rules_applied()
                        mutated = True
                        break
            if not mutated:
                break

        # --- Phase 4: Tripādī (8.2–8.4) ---
        # Pūrvatrāsiddham (8.2.1): a rule in chapter N sees the state *before*
        # any rule in chapter M > N changed it. Implemented via DerivationTrace
        # checkpoints — earlier chapter rules query their chapter's snapshot state.
        for _ in range(max_steps):
            mutated = False
            matches = []
            last_chapter = exec_ctx.trace.last_chapter_applied()

            for r in tripadi_rules:
                if r.sutra_id in applied_rules:
                    continue
                if cur_l in NATIVE_REPHA_LEXICON and getattr(r.spec, "target_context", None) and getattr(r.spec.target_context, "exact_text", "") == "s|H|r":
                    continue

                try:
                    rule_chapter = int(r.sutra_id.split(".")[1]) if r.sutra_id.startswith("8.") else 0
                except (IndexError, ValueError):
                    rule_chapter = 0

                # Pūrvatrāsiddham: earlier chapter rules see pre-chapter snapshot
                if last_chapter > rule_chapter and rule_chapter != 0:
                    check_l, check_r = exec_ctx.trace.get_state_before_chapter(last_chapter)
                else:
                    check_l, check_r = cur_l, cur_r

                if r.matches(check_l, check_r, exec_ctx):
                    op_type = getattr(getattr(r, "spec", None), "operation", None)
                    if op_type and getattr(op_type, "op_type", "") in {"prohibit", "prakritibhava"}:
                        return cur_l, cur_r
                    candidate_result = r.apply(cur_l, cur_r, exec_ctx)
                    if candidate_result != (cur_l, cur_r):
                        matches.append((r, rule_chapter, candidate_result))

            if not matches:
                break

            best_r, best_chapter, (new_l, new_r) = max(matches, key=lambda x: self._get_spec(x[0]))
            consumed = cur_l[-1] if cur_l else ""
            exec_ctx.trace.record(
                best_r.sutra_id, cur_l, cur_r, new_l, new_r,
                consumed=consumed, emitted=""
            )
            cur_l, cur_r = new_l, new_r
            applied_rules = exec_ctx.trace.rules_applied()
            mutated = True

        return cur_l, cur_r


    def dispatch_revert(self, surface: str, context: Dict[str, Any] = None) -> List[Tuple[str, str]]:
        """Compute all possible backward sandhi splits using pre-indexed rule lookup."""
        cache_key = surface
        if cache_key in self._revert_cache:
            return self._revert_cache[cache_key]

        ctx = context or {}
        scope = ctx.get("scope", "external")
        ordered = self._get_sandhi_ordered_rules(scope=scope)

        # Build substitute index lazily (only built once per scope)
        idx_key = "idx_" + scope
        if idx_key not in self._ordered_cache:
            sub_index: Dict[str, List[PaniniRule]] = {}
            for r in ordered:
                spec = getattr(r, "spec", None)
                if spec is None:
                    continue
                op = getattr(spec, "operation", None)
                sub = getattr(op, "substitute", None) if op else None
                op_type = getattr(op, "op_type", "") if op else ""
                if sub and sub not in {"dirgha", "guna", "vriddhi", "non_operational", "governance"}:
                    # Strip PRAT: prefix for index key
                    key_sub = sub.removeprefix("PRAT:")
                    # Multi-char substitutes stored whole; single-char split to individual chars
                    if "|" in key_sub:
                        for part in key_sub.split("|"):
                            sub_index.setdefault(part, []).append(r)
                    else:
                        sub_index.setdefault(key_sub, []).append(r)
                elif op_type in {"visarga_utva", "purva_rupa"}:
                    sub_index.setdefault("'", []).append(r)
                    sub_index.setdefault("o", []).append(r)
                elif op_type == "natva":
                    sub_index.setdefault("ṇ", []).append(r)
                    sub_index.setdefault("R", []).append(r)  # SLP1 ṇ
                elif op_type == "anusvara":
                    sub_index.setdefault("M", []).append(r)  # SLP1 anusvara
                elif op_type in {"ekadesha_savarna_dirgha", "merge_savarna"}:
                    for c in ["ā", "ī", "ū", "A", "I", "U"]:
                        sub_index.setdefault(c, []).append(r)
                elif op_type in {"ekadesha_guna", "ekadesha_vriddhi", "sanjna_substitute"}:
                    for c in ["e", "o", "ar", "ai", "au", "E", "O"]:
                        sub_index.setdefault(c, []).append(r)
                else:
                    # rules without clear substitute - add to wildcard bucket
                    sub_index.setdefault("*", []).append(r)
            self._ordered_cache[idx_key] = sub_index

        sub_index = self._ordered_cache[idx_key]
        wildcard_rules = sub_index.get("*", [])

        results = set()

        # Fast pre-filter: only check rules whose substitute appears in surface
        candidate_rules: List[PaniniRule] = list(wildcard_rules)
        seen_r_ids = {id(r) for r in wildcard_rules}
        for sub_key, rules in sub_index.items():
            if sub_key == "*":
                continue
            if sub_key in surface:
                for r in rules:
                    rid = id(r)
                    if rid not in seen_r_ids:
                        candidate_rules.append(r)
                        seen_r_ids.add(rid)

        found_split = False
        for r in candidate_rules:
            try:
                raw_splits = r.revert(surface, ctx)
                for l, r_str in raw_splits:
                    if (l, r_str) != (surface, "") and (l, r_str) != ("", surface) and l and r_str is not None:
                        found_split = True
                        results.add((l, r_str))
            except Exception:
                pass

        if not found_split:
            results.add((surface, ""))

        result_list = list(results)
        self._revert_cache[cache_key] = result_list
        return result_list


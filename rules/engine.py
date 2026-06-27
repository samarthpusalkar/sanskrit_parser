"""
Universal Pāṇinian Rule Engine Dispatcher and Operational Conflict Resolver.

Manages active sūtra registries, Tripādī ordering rules (8.2.1 - 8.4.68),
and conflict resolution via Paribhāṣās (e.g. 1.4.2 vipratiṣedhe paraṃ kāryam)
with LRU-cached rule ordering and revert results.
"""

from typing import List, Dict, Any, Tuple, Optional
from rules.base import PaniniRule, VidhiRule
import functools


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
        if auto_compile:
            from compiler.pipeline import MasterCompilerPipeline
            self._rules.extend(MasterCompilerPipeline.compile_all())

    def register_rule(self, rule: PaniniRule):
        self._rules.append(rule)
        self._ordered_cache.clear()
        self._revert_cache.clear()

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

            # Tripādī domain (8.2.1 onwards = 80200) vs Sapādāsaptādhyāyī
            domain = getattr(spec, "governance", {}).get("domain", "sapada") if spec else "sapada"
            domain_rank = 1 if domain == "tripadi" or num_id >= 80200.0 else 0

            # Structural Specificity count (Apavāda over Utsarga)
            specificity = 0
            if spec:
                for ctx_obj in [spec.left_context, spec.right_context, spec.target_context]:
                    if ctx_obj:
                        if ctx_obj.exact_text:
                            specificity += len(ctx_obj.exact_text) * 2
                        if ctx_obj.features_required:
                            specificity += len(ctx_obj.features_required)
                        if ctx_obj.pratyahara:
                            specificity += 1

            # Sūtra ordering: Sapāda respects vipratiṣedhe paraṃ kāryam (1.4.2, later prevails -> -num_id)
            # Tripādī executes sequentially (8.2.1 pūrvatrāsiddham -> num_id)
            sutra_order = num_id if domain_rank == 1 else -num_id
            if domain_rank == 1:
                return (domain_rank, sutra_order, -specificity)
            return (domain_rank, -specificity, sutra_order)

        rules_pool = []
        if scope == "external":
            for r in self._rules:
                dom = getattr(r, "domain", "")
                if dom in {"samhita", "tripadi"}:
                    rules_pool.append(r)
        else:
            rules_pool = self._rules
        ordered = sorted(rules_pool, key=_sort_key)
        self._ordered_cache[scope] = ordered
        return ordered

    def dispatch_forward(self, left: str, right: str, context: Dict[str, Any] = None) -> Tuple[str, str]:
        """Apply sequential forward sandhi/morphological transformation rules."""
        ctx = context or {}
        scope = ctx.get("scope", "external")
        cur_l, cur_r = left, right
        
        ordered = self._get_sandhi_ordered_rules(scope=scope)
        sapada_rules = [r for r in ordered if getattr(r.spec.governance, "domain", "sapada") != "tripadi" and not r.sutra_id.startswith("8.2") and not r.sutra_id.startswith("8.3") and not r.sutra_id.startswith("8.4")]
        tripadi_rules = [r for r in ordered if r not in sapada_rules]

        applied_rules = set()

        # Phase 1: Sapādāsaptādhyāyī (Iterative until convergence)
        max_steps = 10
        for _ in range(max_steps):
            mutated = False
            for r in sapada_rules:
                if r.sutra_id in applied_rules:
                    continue  # Sakṛd eva pravartate
                if r.matches(cur_l, cur_r, ctx):
                    op_type = getattr(getattr(r, "spec", None), "operation", None)
                    if op_type and getattr(op_type, "op_type", "") in {"prohibit", "prakritibhava"}:
                        return cur_l, cur_r
                    new_l, new_r = r.apply(cur_l, cur_r, ctx)
                    if new_l != cur_l or new_r != cur_r:
                        cur_l, cur_r = new_l, new_r
                        applied_rules.add(r.sutra_id)
                        mutated = True
                        break  # Restart scan from highest priority Sapāda rule
            if not mutated:
                break

        # Phase 2: Tripādī (Strictly sequential, no restarts)
        for r in tripadi_rules:
            if r.sutra_id in applied_rules:
                continue
            if r.matches(cur_l, cur_r, ctx):
                new_l, new_r = r.apply(cur_l, cur_r, ctx)
                if new_l != cur_l or new_r != cur_r:
                    cur_l, cur_r = new_l, new_r
                    applied_rules.add(r.sutra_id)
                    # We do NOT break here. Tripādī is strictly linear.

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


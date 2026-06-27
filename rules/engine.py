"""
Universal Pāṇinian Rule Engine Dispatcher and Operational Conflict Resolver.

Manages active sūtra registries, Tripādī ordering rules (8.2.1 - 8.4.68),
and conflict resolution via Paribhāṣās (e.g. 1.4.2 vipratiṣedhe paraṃ kāryam).
"""

from typing import List, Dict, Any, Tuple
from rules.base import PaniniRule, VidhiRule


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
        if auto_compile:
            from compiler.pipeline import MasterCompilerPipeline
            self._rules.extend(MasterCompilerPipeline.compile_all())

    def register_rule(self, rule: PaniniRule):
        self._rules.append(rule)

    def _get_sandhi_ordered_rules(self, scope: str = "external") -> List[PaniniRule]:
        def _sort_key(r: PaniniRule) -> Tuple[int, int, float]:
            spec = getattr(r, "spec", None)
            parts = r.sutra_id.split(".")
            try:
                num_id = float(parts[0]) * 10000 + float(parts[1]) * 100 + float(parts[2])
            except Exception:
                num_id = 999999.0

            # Tripādī domain (8.2.1 onwards = 80201) vs Sapādāsaptādhyāyī
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
            return (domain_rank, -specificity, sutra_order)

        rules_pool = []
        if scope == "external":
            for r in self._rules:
                dom = getattr(r, "domain", "")
                if dom in {"samhita", "tripadi"}:
                    rules_pool.append(r)
        else:
            rules_pool = self._rules
        return sorted(rules_pool, key=_sort_key)

    def dispatch_forward(self, left: str, right: str, context: Dict[str, Any] = None) -> Tuple[str, str]:
        """Apply sequential forward sandhi/morphological transformation rules."""
        ctx = context or {}
        scope = ctx.get("scope", "external")
        cur_l, cur_r = left, right
        ordered = self._get_sandhi_ordered_rules(scope=scope)
        applied_rules = set()

        max_steps = 10
        for _ in range(max_steps):
            mutated = False
            for r in ordered:
                if r.sutra_id in applied_rules:
                    continue  # Sakṛd eva pravartate: a rule applies once per derivation target
                if r.matches(cur_l, cur_r, ctx):
                    new_l, new_r = r.apply(cur_l, cur_r, ctx)
                    if new_l != cur_l or new_r != cur_r:
                        cur_l, cur_r = new_l, new_r
                        applied_rules.add(r.sutra_id)
                        mutated = True
                        break  # Restart scan from highest priority rule
            if not mutated:
                break

        return cur_l, cur_r

    def dispatch_revert(self, surface: str, context: Dict[str, Any] = None) -> List[Tuple[str, str]]:
        """Compute all possible backward sandhi splits using recursive derivation graph traversal."""
        ctx = context or {}
        scope = ctx.get("scope", "external")
        ordered = self._get_sandhi_ordered_rules(scope=scope)

        visited = set()
        results = set()

        def _dfs(cur_surface: str, depth: int):
            if depth > 3 or cur_surface in visited:
                return
            visited.add(cur_surface)
            found_split = False
            for r in ordered:
                try:
                    raw_splits = r.revert(cur_surface, ctx)
                    for l, r_str in raw_splits:
                        if (l, r_str) != (cur_surface, "") and (l, r_str) != ("", cur_surface):
                            found_split = True
                            results.add((l, r_str))
                            # Recursive multi-step chain reversal on left piece
                            if len(l) > 2 and depth < 2:
                                for sub_l, sub_r in r.revert(l, ctx):
                                    if (sub_l, sub_r) != (l, "") and sub_r:
                                        results.add((sub_l, sub_r + r_str))
                except Exception:
                    pass
            if not found_split and depth == 0:
                results.add((cur_surface, ""))

        _dfs(surface, 0)
        return list(results)

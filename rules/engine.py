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
            domain = getattr(spec, "governance", {}).get("domain", "sapada") if spec else "sapada"
            domain_rank = 1 if domain == "tripadi" or r.sutra_id.startswith(("8.2.", "8.3.", "8.4.")) else 0

            # Specificity rank (Apavāda over Utsarga)
            op = getattr(spec, "operation", None) if spec else None
            op_name = getattr(op, "op_type", "") if op else ""
            if op_name in {"ekadesha_savarna_dirgha", "ekadesha_vriddhi", "merge_savarna"}:
                spec_rank = 0
            elif op_name == "ekadesha_guna":
                spec_rank = 1
            elif op_name == "bijection_substitute":
                spec_rank = 2
            else:
                spec_rank = 3

            # Sūtra ordering
            parts = r.sutra_id.split(".")
            try:
                num_id = float(parts[0]) * 10000 + float(parts[1]) * 100 + float(parts[2])
            except Exception:
                num_id = 999999.0

            sutra_order = num_id if domain_rank == 1 else -num_id
            return (domain_rank, spec_rank, sutra_order)

        filtered = self._rules
        if scope == "external":
            filtered = [
                r for r in self._rules
                if r.sutra_id.startswith(("8.2.", "8.3.", "8.4.")) or (
                    r.sutra_id.startswith("6.1.") and len(r.sutra_id.split(".")) == 3 and r.sutra_id.split(".")[2].isdigit() and int(r.sutra_id.split(".")[2]) >= 72
                )
            ]

        return sorted(filtered, key=_sort_key)

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
        """Compute all possible backward sandhi splits."""
        ctx = context or {}
        scope = ctx.get("scope", "external")
        splits = []
        ordered = self._get_sandhi_ordered_rules(scope=scope)
        for r in ordered:
            splits.extend(r.revert(surface, ctx))
        return list(set(splits))

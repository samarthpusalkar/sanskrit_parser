"""
Pairwise (pada-to-pada) sandhi derivation orchestrator.

Reduces a token list left-to-right using DB-loaded rules and PhonologyBridge.
Default fallback when no rule fires: preserve pada boundary with a space.
"""

from __future__ import annotations

from typing import List, Tuple, Optional

from .config import TraditionConfig
from .conflict import RuleObject, ConflictResolver
from .graph import DerivationGraph, MorphoPhonemicToken, TokenState
from .loop import is_eligible
from .phonology import PhonologyBridge
from .pre_grammatical import PratyaharaEngine
from .rule_loader import load_sandhi_rules, make_tradition_config
from .types import LexicalCategory
from .vivaksa import SemanticConditionEvaluator


def _make_pair_state(
    left: str,
    right: str,
    graph: DerivationGraph,
    left_state_id: str,
) -> tuple[MorphoPhonemicToken, MorphoPhonemicToken]:
    """Register two tokens in the graph for one sandhi step."""
    left_id = left_state_id
    right_id = f"{left_state_id}_right"

    left_ts = TokenState(left_id, left, LexicalCategory.ROOT, None, frozenset())
    right_ts = TokenState(right_id, right, LexicalCategory.ROOT, None, frozenset())
    graph.register(left_ts)
    graph.register(right_ts)

    t0 = MorphoPhonemicToken(left_id, graph)
    t1 = MorphoPhonemicToken(right_id, graph)
    return t0, t1


def derive_pair(
    left: str,
    right: str,
    rules: List[RuleObject],
    config: TraditionConfig,
    graph: DerivationGraph,
    left_state_id: str,
    trace: List[str],
) -> Tuple[str, str]:
    """
    Apply sandhi between two surface strings.
    Returns (result_surface, new_left_state_id).
    """
    pe = PratyaharaEngine(config)
    bridge = PhonologyBridge(pe, db_path="data/sanskrit_master.db")
    evaluator = SemanticConditionEvaluator()
    resolver = ConflictResolver(config)

    t0, t1 = _make_pair_state(left, right, graph, left_state_id)
    trace.append(f"Evaluating sandhi: '{left}' + '{right}'")

    from .loop import DerivationState
    state = DerivationState(tokens=[t0, t1], phonology_bridge=bridge)

    candidates = [r for r in rules if is_eligible(r, state, evaluator, config)]

    # Keep only rules that actually mutate this pair (dry-run via bridge)
    sandhi_rules: List[RuleObject] = []
    prakriti_rules: List[RuleObject] = []
    for r in candidates:
        _, mutated = bridge.execute_pairwise_sandhi(left, right, r)
        if not mutated:
            continue
        if r.effect_type == "prakritibhava":
            prakriti_rules.append(r)
        else:
            sandhi_rules.append(r)

    # Include blocking prakritibhava rules alongside sandhi rules so conflict resolution
    # can correctly choose a blocking rule over an otherwise-applicable sandhi rule.
    mutating = sandhi_rules + prakriti_rules

    if not mutating:
        fallback = f"{left} {right}"
        trace.append(f"No sandhi rule fired; pada boundary preserved -> '{fallback}'")
        new_ts = TokenState(
            f"{left_state_id}_padaboundary",
            fallback,
            LexicalCategory.ROOT,
            None,
            frozenset([left_state_id]),
        )
        graph.register(new_ts)
        return fallback, new_ts.state_id

    try:
        result = resolver.resolve(mutating, state)
    except Exception:
        result = type("R", (), {"chosen": mutating[0], "alternatives": mutating})()

    chosen = result.chosen or mutating[0]
    res, _ = bridge.execute_pairwise_sandhi(left, right, chosen)

    new_s0 = TokenState(
        f"{t0.current_state_id}_{chosen.sutra_id}",
        res,
        LexicalCategory.ADESA,
        chosen.sutra_id,
        frozenset([t0.current_state_id, t1.current_state_id]),
    )
    graph.register(new_s0)
    new_s1 = TokenState(
        f"{t1.current_state_id}_lopa_{chosen.sutra_id}",
        "",
        LexicalCategory.LOPA,
        chosen.sutra_id,
        frozenset([t1.current_state_id]),
    )
    graph.register(new_s1)

    trace.append(f"Applied rule {chosen.sutra_id} ({chosen.effect_type}) -> '{res}'")
    return res, new_s0.state_id


def run_pairwise_derivation(
    tokens: List[str],
    rules: Optional[List[RuleObject]] = None,
    config: Optional[TraditionConfig] = None,
    graph: Optional[DerivationGraph] = None,
) -> Tuple[str, List[str]]:
    """
    Sequentially join tokens left-to-right through the Pāṇinian engine.
    Returns (final_surface, trace_log).
    """
    if not tokens:
        return "", []
    if len(tokens) == 1:
        return tokens[0], [f"Single token: {tokens[0]}"]

    rules = rules if rules is not None else load_sandhi_rules()
    config = config or make_tradition_config()
    graph = graph or DerivationGraph()
    trace: List[str] = [f"Starting derivation: {' + '.join(tokens)}"]

    current = tokens[0]
    state_id = "state_init"
    init_ts = TokenState(state_id, current, LexicalCategory.ROOT, None, frozenset())
    graph.register(init_ts)

    for nxt in tokens[1:]:
        current, state_id = derive_pair(
            current, nxt, rules, config, graph, state_id, trace
        )

    trace.append(f"Final surface: '{current}'")
    return current, trace

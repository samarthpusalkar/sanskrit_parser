"""
Vivakṣā Type System, Śābdabodha Injection, and Semantic Bridge for the Paninian Rewriting Engine.
Separates semantic intent from morphological exponent classes and injects external conceptual frames.
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .types import DomainType, ComparisonOp, LogicalOp, Quantifier


# ── Śābdabodha Semantic Frame ─────────────────────────────────────────────

@dataclass(frozen=True)
class KarakaNode:
    nominal_stem: str
    target_role: DomainType       # e.g., DomainType.KARTR, DomainType.KARMAN
    governing_action_id: str


@dataclass
class SabdabodhaFrame:
    """
    External semantic dependency network representing the speaker's conceptual utterance.
    Acts as the ground truth query engine for QuantifierNode evaluation.
    """
    action_nodes: Dict[str, str]                  # action_id -> root_meaning
    karaka_edges: List[KarakaNode]
    upapada_relations: Dict[str, str]             # dependent_id -> head_id

    def resolve_domain(self, domain_type: DomainType) -> List[Any]:
        if domain_type in {
            DomainType.KARTR, DomainType.KARMAN, DomainType.KARANA,
            DomainType.SAMPRADANA, DomainType.APADANA, DomainType.ADHIKARANA
        }:
            return [edge for edge in self.karaka_edges if edge.target_role == domain_type]
        return []


# ── Vivakṣā AST ──────────────────────────────────────────────────────────

class ASTNode:
    pass


@dataclass
class LiteralNode(ASTNode):
    value:       Any
    domain_type: DomainType


@dataclass
class VariableNode(ASTNode):
    name:        str
    domain_type: DomainType


@dataclass
class ApplicationNode(ASTNode):
    operator:  ASTNode
    arguments: List[ASTNode]


@dataclass
class LambdaNode(ASTNode):
    variable: VariableNode
    body:     ASTNode


@dataclass
class VivaksaAST:
    root: ASTNode


# ── LogicalPredicate (sūtra trigger conditions) ───────────────────────────

class PredicateNode:
    pass


@dataclass
class ComparisonNode(PredicateNode):
    left:  ASTNode
    op:    ComparisonOp
    right: ASTNode


@dataclass
class LogicalOpNode(PredicateNode):
    op:       LogicalOp
    operands: List[PredicateNode]


@dataclass
class QuantifierNode(PredicateNode):
    quantifier: Quantifier
    variable:   VariableNode
    body:       PredicateNode


@dataclass
class LogicalPredicate:
    root: PredicateNode


# ── Semantic Condition Evaluator ──────────────────────────────────────────

class SemanticConditionEvaluator:
    """
    Bridges top-down Vivakṣā intent and Śābdabodha conceptual frame to sūtra trigger conditions.
    """
    def eval_condition(
        self,
        vivaksa:    Optional[VivaksaAST],
        condition:  LogicalPredicate,
        context:    Any
    ) -> bool:
        return self._eval_predicate(condition.root, vivaksa, context, bindings={})

    def _eval_predicate(
        self,
        node:     PredicateNode,
        vivaksa:  Optional[VivaksaAST],
        context:  Any,
        bindings: Dict[str, Any]
    ) -> bool:
        if isinstance(node, ComparisonNode):
            left_val  = self._reduce(node.left,  vivaksa, context, bindings)
            right_val = self._reduce(node.right, vivaksa, context, bindings)
            return self._compare(left_val, right_val, node.op)
        elif isinstance(node, LogicalOpNode):
            results = [self._eval_predicate(o, vivaksa, context, bindings) for o in node.operands]
            if not results:
                return True
            if node.op == LogicalOp.AND: return all(results)
            if node.op == LogicalOp.OR:  return any(results)
            if node.op == LogicalOp.NOT: return not results[0]
        elif isinstance(node, QuantifierNode):
            domain = []
            if hasattr(context, "domain_for"):
                domain = context.domain_for(node.variable.domain_type)
            for val in domain:
                bound = dict(bindings)
                bound[node.variable.name] = val
                if self._eval_predicate(node.body, vivaksa, context, bindings=bound):
                    if node.quantifier == Quantifier.EXISTS: return True
            return node.quantifier == Quantifier.FORALL
        raise TypeError(f"Unknown predicate node: {type(node)}")

    def _reduce(self, node: ASTNode, vivaksa: Optional[VivaksaAST], context: Any, bindings: Dict[str, Any]) -> Any:
        if isinstance(node, LiteralNode):
            return node.value
        elif isinstance(node, VariableNode):
            if node.name in bindings:
                return bindings[node.name]
            if hasattr(context, "semantic_state") and node.name in context.semantic_state:
                return context.semantic_state[node.name]
            return node.name
        elif isinstance(node, ApplicationNode):
            op_val = self._reduce(node.operator, vivaksa, context, bindings)
            arg_vals = [self._reduce(arg, vivaksa, context, bindings) for arg in node.arguments]
            if isinstance(op_val, LambdaNode):
                bound = dict(bindings)
                for i, param_arg in enumerate(arg_vals):
                    if i == 0:
                        bound[op_val.variable.name] = param_arg
                return self._reduce(op_val.body, vivaksa, context, bound)
            return (op_val, *arg_vals)
        elif isinstance(node, LambdaNode):
            return node
        return node

    def _compare(self, left: Any, right: Any, op: ComparisonOp) -> bool:
        if op == ComparisonOp.EQUALS:
            if isinstance(left, KarakaNode) and isinstance(right, str):
                return left.nominal_stem == right
            if isinstance(right, KarakaNode) and isinstance(left, str):
                return right.nominal_stem == left
            return left == right
        elif op == ComparisonOp.CONTAINS_TYPE:
            if isinstance(left, (list, tuple, set)):
                return right in left
            return left == right
        elif op == ComparisonOp.IS_SUBSET:
            if isinstance(left, (set, frozenset)) and isinstance(right, (set, frozenset)):
                return left.issubset(right)
            return left == right
        elif op == ComparisonOp.IS_MEMBER_OF:
            if isinstance(right, (list, tuple, set, frozenset, dict)):
                return left in right
            return left == right
        return False

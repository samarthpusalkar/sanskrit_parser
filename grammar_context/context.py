"""
GrammarContext — the running state of Pāṇinian grammar compilation.

As sūtras are processed in canonical order (1.1.1 → 8.4.68), this context
accumulates:
  1. Saṃjñās (technical term definitions)
  2. Adhikāras (scope declarations that govern interpretation of later sūtras)
  3. Anuvṛtti carries (fields that carry forward from one sūtra to the next)
  4. Paribhāṣās (meta-rules / evaluation pragmas in force)

The context is built deterministically from the panini_rules DB — no LLM
involved. It can be checkpointed at any sūtra boundary and replayed.

This module is the foundation for both:
  - LLM extraction (provide context in the prompt)
  - Runtime execution (saṃjñā tagger, adhikāra resolver, anuvṛtti tracker)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SanjnaDefinition:
    """A saṃjñā (technical term) definition."""
    sutra_id: str
    term: str
    definition_type: str = "morphological"
    criteria: Optional[str] = None
    equivalent_sutra_ids: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"{self.term} ({self.definition_type}, defined {self.sutra_id})"


@dataclass
class AdhikaraScope:
    """An adhikāra (scope declaration) in force over a range of sūtras."""
    sutra_id: str
    topic: str
    governs_range_start: Optional[str] = None
    governs_range_end: Optional[str] = None
    scope_condition: Optional[str] = None

    def summary(self) -> str:
        rng = ""
        if self.governs_range_start:
            rng = f" [{self.governs_range_start}–{self.governs_range_end or '…'}]"
        cond = f" when {self.scope_condition}" if self.scope_condition else ""
        return f"{self.topic} (from {self.sutra_id}{rng}{cond})"


@dataclass
class AnuvrttiCarry:
    """A field carried forward via anuvṛtti from a previous sūtra."""
    field_name: str
    value: str
    carried_from_sutra_id: str

    def summary(self) -> str:
        return f"{self.field_name}={self.value} (from {self.carried_from_sutra_id})"


@dataclass
class ParibhasaAxiom:
    """A paribhāṣā (meta-rule) in force."""
    sutra_id: str
    axiom_ast: Optional[str] = None
    category: Optional[str] = None
    scope_sutra_ids: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"{self.category or 'meta-rule'} ({self.sutra_id})"


def _sort_key(sutra_id: str) -> Tuple[int, int, int]:
    parts = sutra_id.split(".")
    if len(parts) == 3:
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return (0, 0, 0)
    return (0, 0, 0)


def _chapter_of(sutra_id: str) -> str:
    parts = sutra_id.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else sutra_id


class GrammarContext:
    """Running state of Pāṇinian grammar as sūtras are processed in order."""

    def __init__(self) -> None:
        self.sanjnas: Dict[str, SanjnaDefinition] = {}
        self.active_adhikaras: List[AdhikaraScope] = []
        self.anuvrtti_carries: Dict[str, AnuvrttiCarry] = {}
        self.paribhasas: List[ParibhasaAxiom] = []
        self.processed_sutras: List[str] = []
        self._current_sutra_id: Optional[str] = None

    def process_sutra(
        self,
        sutra_id: str,
        rule_type: str,
        defined_sanjna: Optional[str] = None,
        definition_type: Optional[str] = None,
        definition_criteria: Optional[str] = None,
        equivalent_sutra_ids: Optional[List[str]] = None,
        adhikara_topic: Optional[str] = None,
        governs_range_start: Optional[str] = None,
        governs_range_end: Optional[str] = None,
        scope_condition: Optional[str] = None,
        anuvrtti_carries_raw: Optional[Any] = None,
        anuvrtti_links: Optional[List[Dict[str, Any]]] = None,
        paribhasa_axiom: Optional[str] = None,
        paribhasa_category: Optional[str] = None,
    ) -> None:
        """Update the context after processing a sūtra.

        This is called for each sūtra in canonical order. It updates the
        accumulated saṃjñās, adhikāras, anuvṛtti carries, and paribhāṣās.
        """
        self._current_sutra_id = sutra_id
        self.processed_sutras.append(sutra_id)

        # 1. Saṃjñā definition
        if rule_type == "samjna_definition" and defined_sanjna:
            self.sanjnas[defined_sanjna] = SanjnaDefinition(
                sutra_id=sutra_id,
                term=defined_sanjna,
                definition_type=definition_type or "morphological",
                criteria=definition_criteria,
                equivalent_sutra_ids=equivalent_sutra_ids or [],
            )

        # 2. Adhikāra scope
        if rule_type == "adhikara" and adhikara_topic:
            scope = AdhikaraScope(
                sutra_id=sutra_id,
                topic=adhikara_topic,
                governs_range_start=governs_range_start,
                governs_range_end=governs_range_end,
                scope_condition=scope_condition,
            )
            self.active_adhikaras.append(scope)

        # 3. Anuvṛtti carries
        if anuvrtti_links:
            for link in anuvrtti_links:
                field_name = link.get("inherited_field", "")
                inherited_from = link.get("inherited_from_sutra_id", "")
                if field_name and inherited_from:
                    self.anuvrtti_carries[field_name] = AnuvrttiCarry(
                        field_name=field_name,
                        value=link.get("inherited_text", ""),
                        carried_from_sutra_id=inherited_from,
                    )

        # 4. Paribhāṣā
        if rule_type == "paribhasa":
            self.paribhasas.append(ParibhasaAxiom(
                sutra_id=sutra_id,
                axiom_ast=paribhasa_axiom,
                category=paribhasa_category,
            ))

    def is_adhikara_active(self, sutra_id: str) -> bool:
        """Check if an adhikāra is still active at the given sūtra."""
        for scope in self.active_adhikaras:
            if scope.governs_range_end and _sort_key(sutra_id) > _sort_key(scope.governs_range_end):
                continue
            if scope.governs_range_start and _sort_key(sutra_id) < _sort_key(scope.governs_range_start):
                continue
            return True
        return False

    def has_sanjna(self, term: str) -> bool:
        return term in self.sanjnas

    def get_sanjna(self, term: str) -> Optional[SanjnaDefinition]:
        return self.sanjnas.get(term)

    def active_adhikara_topics(self) -> List[str]:
        """Return topics of all adhikāras currently in scope."""
        return [s.topic for s in self.active_adhikaras
                if not (s.governs_range_end and self._current_sutra_id
                        and _sort_key(self._current_sutra_id) > _sort_key(s.governs_range_end))]

    def anuvrtti_summary(self) -> List[str]:
        return [c.summary() for c in self.anuvrtti_carries.values()]

    def sanjna_summary(self) -> List[str]:
        return [s.summary() for s in self.sanjnas.values()]

    def adhikara_summary(self) -> List[str]:
        return [s.summary() for s in self.active_adhikaras]

    def paribhasa_summary(self) -> List[str]:
        return [p.summary() for p in self.paribhasas]

    def context_summary(self) -> Dict[str, Any]:
        """Compact summary suitable for LLM prompt inclusion."""
        return {
            "defined_sanjnas": self.sanjna_summary(),
            "active_adhikaras": self.adhikara_summary(),
            "anuvrtti_carries": self.anuvrtti_summary(),
            "paribhasas_in_force": self.paribhasa_summary(),
            "sutras_processed": len(self.processed_sutras),
        }

    def to_json(self) -> str:
        """Serialize the full context state for checkpointing."""
        return json.dumps({
            "sanjnas": {k: {"sutra_id": v.sutra_id, "term": v.term,
                            "definition_type": v.definition_type, "criteria": v.criteria,
                            "equivalent_sutra_ids": v.equivalent_sutra_ids}
                        for k, v in self.sanjnas.items()},
            "active_adhikaras": [{"sutra_id": s.sutra_id, "topic": s.topic,
                                   "governs_range_start": s.governs_range_start,
                                   "governs_range_end": s.governs_range_end,
                                   "scope_condition": s.scope_condition}
                                  for s in self.active_adhikaras],
            "anuvrtti_carries": {k: {"field_name": v.field_name, "value": v.value,
                                      "carried_from_sutra_id": v.carried_from_sutra_id}
                                 for k, v in self.anuvrtti_carries.items()},
            "paribhasas": [{"sutra_id": p.sutra_id, "axiom_ast": p.axiom_ast,
                            "category": p.category, "scope_sutra_ids": p.scope_sutra_ids}
                           for p in self.paribhasas],
            "processed_sutras": self.processed_sutras,
        }, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "GrammarContext":
        """Deserialize a checkpointed context."""
        obj = json.loads(data)
        ctx = cls()
        for term, d in obj.get("sanjnas", {}).items():
            ctx.sanjnas[term] = SanjnaDefinition(
                sutra_id=d["sutra_id"], term=d["term"],
                definition_type=d.get("definition_type", "morphological"),
                criteria=d.get("criteria"),
                equivalent_sutra_ids=d.get("equivalent_sutra_ids", []),
            )
        for d in obj.get("active_adhikaras", []):
            ctx.active_adhikaras.append(AdhikaraScope(
                sutra_id=d["sutra_id"], topic=d["topic"],
                governs_range_start=d.get("governs_range_start"),
                governs_range_end=d.get("governs_range_end"),
                scope_condition=d.get("scope_condition"),
            ))
        for k, d in obj.get("anuvrtti_carries", {}).items():
            ctx.anuvrtti_carries[k] = AnuvrttiCarry(
                field_name=d["field_name"], value=d["value"],
                carried_from_sutra_id=d["carried_from_sutra_id"],
            )
        for d in obj.get("paribhasas", []):
            ctx.paribhasas.append(ParibhasaAxiom(
                sutra_id=d["sutra_id"], axiom_ast=d.get("axiom_ast"),
                category=d.get("category"),
                scope_sutra_ids=d.get("scope_sutra_ids", []),
            ))
        ctx.processed_sutras = obj.get("processed_sutras", [])
        return ctx

    def checkpoint(self) -> "GrammarContext":
        """Return a snapshot copy of the current context."""
        return GrammarContext.from_json(self.to_json())
"""
Execution Context — sanskrit_dsl/execution_context.py

Typed runtime state carried through the Pāṇinian derivation. This is the
single object a rule ever needs during matching/application: the boundary
strings, saṃjñā tags, the derivation timeline (for asiddhatva/sthānivadbhāva),
and morphological features.

This is a rebuild owned by sanskrit_dsl (no dependency on rules/engine.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Set

from .derivation_timeline import DerivationTimeline


@dataclass
class ExecutionContext:
    """Complete runtime context passed to CompiledSutra.matches/apply."""

    left_token: str = ""
    right_token: str = ""

    sanjna_map: Dict[str, Set[str]] = field(
        default_factory=lambda: {"left": set(), "right": set()}
    )

    trace: DerivationTimeline = field(default_factory=DerivationTimeline)

    domain: str = "sapada"
    is_samasa: bool = False
    is_padanta: bool = True

    morphological_features: Dict[str, Any] = field(default_factory=dict)

    def has_sanjna(self, side: str, sanjna: str) -> bool:
        return sanjna in self.sanjna_map.get(side, set())

    def add_sanjna(self, side: str, sanjna: str) -> None:
        self.sanjna_map.setdefault(side, set()).add(sanjna)

    def set_sanjnas(self, side: str, tags: Set[str]) -> None:
        self.sanjna_map[side] = set(tags)
"""
Typed ExecutionContext replacing raw Dict for rule matching and application.

Carries all runtime state needed by a rule evaluation:
- The full input tokens (not just boundary chars)
- Sañjñā tags computed per token by SanjanaTagger
- The derivation trace for sthānivadbhāva and asiddhatva queries
- Morphological features from the upstream morphology layer
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Any, Optional
from rule_engine.trace import DerivationTrace


@dataclass
class ExecutionContext:
    """
    Complete runtime context passed to every rule's matches() and apply() methods.

    Design principle: every piece of information a rule ever needs during matching
    must live here. Rules must NOT reach outside this object.
    """
    # --- Token identity ---
    left_token: str = ""            # Full left word (e.g. "rAma")
    right_token: str = ""           # Full right word (e.g. "ISaH")

    # --- Sañjñā tags computed by SanjanaTagger ---
    # Key: 'left' or 'right'; Value: set of sañjñā names (SLP1)
    sanjña_map: Dict[str, Set[str]] = field(default_factory=lambda: {"left": set(), "right": set()})

    # --- Derivation history ---
    trace: DerivationTrace = field(default_factory=DerivationTrace)

    # --- Domain and compound state ---
    domain: str = "sapada"          # 'sapada', 'tripadi', 'angasya', 'samhita'
    is_samasa: bool = False         # Whether tokens are in a compound

    # --- Morphological signals from upstream layer ---
    # These are optional; tagger uses them to compute sañjñā
    morphological_features: Dict[str, Any] = field(default_factory=dict)

    # --- Legacy compatibility (bool flags still readable by old code) ---
    is_padanta: bool = True

    def has_sanjña(self, side: str, sanjña: str) -> bool:
        """Check if a token (side='left' or 'right') carries a given sañjñā tag."""
        return sanjña in self.sanjña_map.get(side, set())

    def add_sanjña(self, side: str, sanjña: str):
        """Add a sañjñā tag to a side."""
        self.sanjña_map.setdefault(side, set()).add(sanjña)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionContext":
        """Compatibility shim: build from legacy raw dict context."""
        ctx = cls()
        ctx.is_padanta = d.get("is_padanta", True)
        ctx.domain = d.get("domain", "sapada")
        ctx.is_samasa = d.get("is_samasa", False)
        ctx.left_token = d.get("left_token", "")
        ctx.right_token = d.get("right_token", "")
        ctx.morphological_features = d.get("morphological_features", {})
        return ctx

    def to_dict(self) -> Dict[str, Any]:
        """Produce a plain dict for legacy compatibility."""
        return {
            "is_padanta": self.is_padanta,
            "domain": self.domain,
            "is_samasa": self.is_samasa,
            "left_token": self.left_token,
            "right_token": self.right_token,
        }

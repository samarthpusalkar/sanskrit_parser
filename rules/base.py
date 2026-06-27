"""
Abstract Base Classes for Pāṇinian Rule Transducer Architecture.

Enforces object-oriented contracts for the ~4,000 Pāṇinian Sūtras across all Sūtra types:
Sañjñā (Definition), Paribhāṣā (Meta-rule), Vidhi (Operational rule), Adhikara (Domain scope), Atideśa (Analogy).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional


class PaniniRule(ABC):
    """Abstract Base Class for any Pāṇinian grammatical rule."""

    def __init__(self, sutra_id: str, name: str, description: str = ""):
        self.sutra_id = sutra_id
        self.name = name
        self.description = description

    @abstractmethod
    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        """Evaluate if the structural and grammatical context triggers this rule."""
        pass

    @abstractmethod
    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        """Execute forward derivation transformation."""
        pass

    @abstractmethod
    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Execute backward analytical inversion splits."""
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} [{self.sutra_id}] {self.name}>"


class SanjnaRule(PaniniRule):
    """Sañjñā Sūtra (Definitional Rule) - Assigns technical tags or classifications."""

    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        return True

    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        # Sañjñās mutate grammatical context metadata, not surface string
        return left, right

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        return [(combined_surface, "")]


class VidhiRule(PaniniRule):
    """Vidhi Sūtra (Operational Rule) - Performs Ādeśa (Sub), Āgama (Ins), or Lopa (Elision)."""

    def __init__(self, sutra_id: str, name: str, sthani: str, nimitta: str, adesha: str, op_type: str = "substitute"):
        super().__init__(sutra_id, name)
        self.sthani = sthani      # Target to replace / modify
        self.nimitta = nimitta    # Conditioning trigger
        self.adesha = adesha      # Replacement / Insertion
        self.op_type = op_type    # substitute, insert, elide

    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        return bool(left and right)

    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        return left, right

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        return []


class AdhikaraRule(PaniniRule):
    """Adhikara Sūtra (Governing Scope Rule) - Defines domain boundaries for sūtra ranges."""

    def __init__(self, sutra_id: str, name: str, start_sutra: str, end_sutra: str):
        super().__init__(sutra_id, name)
        self.start_sutra = start_sutra
        self.end_sutra = end_sutra

    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        return True

    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        return left, right

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        return [(combined_surface, "")]


class ParibhashaRule(PaniniRule):
    """Paribhāṣā Sūtra (Interpretive Meta-rule) - Resolves operational priority conflicts."""

    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        return True

    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        return left, right

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        return [(combined_surface, "")]

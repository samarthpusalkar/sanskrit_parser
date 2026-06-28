"""
Multi-Axis Configuration for the Paninian Context-Dependent Rewriting Engine.
Each axis (anuvṛtti, paribhāṣā, sūtra text version, gaṇapāṭha version, accent priority)
is independently selectable.
"""
from typing import Set, List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass

from .types import (
    SemanticRole,
    SutraTextVersion,
    GanapathaVersion,
    AccentPriorityRule,
)

if TYPE_CHECKING:
    from .vivaksa import LogicalPredicate


@dataclass
class AnuvrttiTerm:
    term_text:       str
    source_sutra_id: str
    semantic_role:   SemanticRole   # Typed enum


@dataclass
class AnuvrttiPolicy:
    """
    Tradition-specific carryover map. Maps each sūtra ID to the set of
    terms inherited from preceding sūtras under this tradition's reading.
    adhikara_boundaries maps an adhikāra-opening sūtra to the sūtra at
    which its scope terminates.
    """
    inheritance_map:     Dict[str, Set[AnuvrttiTerm]]
    adhikara_boundaries: Dict[str, str]


@dataclass
class ParibhasaAxiom:
    """
    A single paribhāṣā encoded as a named, toggleable axiom.
    source identifies which text introduces it
    (e.g. 'Paribhasendusekhara_1', 'Mahabhasya_on_1.1.3').
    """
    axiom_id:    str
    description: str
    source:      str
    encoded_as:  Optional["LogicalPredicate"] = None


@dataclass
class TraditionConfig:
    """
    Multi-axis configuration. Each axis is independently selectable.
    There is no silent default for paribhasas; derivations halt with
    AmbiguousDerivationError if a conflict arises with no applicable axiom.
    """
    anuvrtti_flow:   AnuvrttiPolicy
    paribhasas:      Set[ParibhasaAxiom]    # No default baseline
    sutra_text:      SutraTextVersion
    ganapatha:       GanapathaVersion
    accent_priority: AccentPriorityRule

    # Phonology configuration
    phoneme_enumeration: List[List[str]]   # 14 Māheśvara lists verbatim
    include_n_in_14th:   bool              # Tradition-specific phoneme variant
    window_size:         int = 2           # Environment window; default 2,
                                           # wider for saṃhitā accent rules

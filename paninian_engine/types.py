"""
Type Foundations for the Paninian Context-Dependent Rewriting Engine.
All string-typed discriminators are promoted to enums to ensure strict typing.
"""
from enum import Enum
from typing import Set, List, Dict, Optional, Callable, FrozenSet, Tuple, Union
from dataclasses import dataclass, field


class SemanticRole(Enum):
    UDDESYA   = "UDDESYA"    # Target of operation
    VIDHEYA   = "VIDHEYA"    # Operation / substitute
    NIMITTA   = "NIMITTA"    # Triggering condition / environment
    ADHIKARA  = "ADHIKARA"   # Governing scope


class DomainIdentifier(Enum):
    ANGASYA      = "ANGASYA"
    PADASYA      = "PADASYA"
    BHASYA       = "BHASYA"
    DHATOH       = "DHATOH"
    PRATYAYASYA  = "PRATYAYASYA"
    TRIPADI      = "TRIPADI"     # 6.4–8.4 asiddhatva domain


class AccentFeature(Enum):
    UDATTA   = "UDATTA"
    ANUDATTA = "ANUDATTA"
    SVARITA  = "SVARITA"
    PRACAYA  = "PRACAYA"   # Ekaśruti: accent-neutral monotone


class LexicalCategory(Enum):
    ROOT   = "ROOT"
    AFFIX  = "AFFIX"
    AGAMA  = "AGAMA"    # Augment
    ADESA  = "ADESA"    # Substitute
    LOPA   = "LOPA"     # Zero-morph deletion trace


class DomainType(Enum):
    # Semantic domain types for the Vivakṣā type system
    AGENT          = "AGENT"
    ACTION         = "ACTION"
    TEMPORAL       = "TEMPORAL"
    ASPECT         = "ASPECT"
    VALENCE        = "VALENCE"
    KARTR          = "KARTR"          # Kāraka: agent
    KARMAN         = "KARMAN"         # Kāraka: object
    KARANA         = "KARANA"         # Kāraka: instrument
    SAMPRADANA     = "SAMPRADANA"     # Kāraka: recipient
    APADANA        = "APADANA"        # Kāraka: ablative source
    ADHIKARANA     = "ADHIKARANA"     # Kāraka: locus
    UPAPADA        = "UPAPADA"        # Upapada syntactic relation
    DERIVATIONAL   = "DERIVATIONAL"   # kṛdanta / taddhitānta purpose


class ComparisonOp(Enum):
    EQUALS        = "EQUALS"
    CONTAINS_TYPE = "CONTAINS_TYPE"
    IS_SUBSET     = "IS_SUBSET"
    IS_MEMBER_OF  = "IS_MEMBER_OF"


class LogicalOp(Enum):
    AND = "AND"
    OR  = "OR"
    NOT = "NOT"


class Quantifier(Enum):
    EXISTS   = "EXISTS"
    FORALL   = "FORALL"


class SutraTextVersion(Enum):
    KASHIKA     = "KASHIKA"
    SIDDHANTA_K = "SIDDHANTA_KAUMUDI"
    LAGHU_K     = "LAGHU_KAUMUDI"
    CRITICAL    = "CRITICAL"          # von Böhtlingk / Böhtlingk-Rieu


class GanapathaVersion(Enum):
    KASHIKA    = "KASHIKA"
    MAHABHASYA = "MAHABHASYA"


class AccentPriorityRule(Enum):
    DHATU_OVER_GANA = "DHATU_OVER_GANA"
    GANA_OVER_DHATU = "GANA_OVER_DHATU"


class AmbiguousDerivationError(Exception):
    """
    Raised when a conflict has prāpti but no paribhāṣā axiom in the
    active TraditionConfig resolves it.
    """
    pass

"""
Pre-Grammatical Engines for the Paninian Context-Dependent Rewriting Engine.
Runs before sūtra evaluation as blocking dependencies. Fully dynamic, without hardcoding.
"""
from typing import Set, List, Dict, Optional, FrozenSet, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass

from .types import AccentFeature
from .config import TraditionConfig

if TYPE_CHECKING:
    from .graph import MorphoPhonemicToken


class PratyaharaEngine:
    """
    Expands pratyāhāras dynamically from the 14 Māheśvara sūtras provided in TraditionConfig.
    Fully respects tradition-specific boundary toggles (e.g., include_n_in_14th) without hardcoding phoneme sets.
    """
    def __init__(self, config: TraditionConfig):
        self.config = config
        self._sutras = config.phoneme_enumeration
        self._cache: Dict[str, FrozenSet[str]] = {}

    def expand(self, pratyahara_name: str) -> FrozenSet[str]:
        """
        Returns the set of phonemes abbreviated by this pratyāhāra.
        """
        if pratyahara_name in self._cache:
            return self._cache[pratyahara_name]

        if len(pratyahara_name) < 2:
            return frozenset()

        start_char = pratyahara_name[:-1]
        it_marker = pratyahara_name[-1]

        # First pass: count how many sūtras after start_char end with it_marker
        matching_sutra_indices = []
        started_check = False
        for idx, sutra in enumerate(self._sutras):
            if not sutra:
                continue
            phonemes = sutra[:-1]
            sutra_it = sutra[-1]
            if start_char in phonemes:
                started_check = True
            if started_check and sutra_it == it_marker:
                matching_sutra_indices.append(idx)

        if not matching_sutra_indices:
            return frozenset()

        # Determine target sūtra index based on tradition configuration
        # If include_n_in_14th is True and multiple IT matches exist (like duplicate 'ṇ'), take the last occurrence.
        # Otherwise, take the first occurrence after start_char.
        if len(matching_sutra_indices) > 1 and self.config.include_n_in_14th:
            target_idx = matching_sutra_indices[-1]
        else:
            target_idx = matching_sutra_indices[0]

        collected: List[str] = []
        started = False

        for idx, sutra in enumerate(self._sutras):
            if not sutra:
                continue
            phonemes = sutra[:-1]

            for ph in phonemes:
                if ph == start_char:
                    started = True
                if started:
                    collected.append(ph)

            if started and idx == target_idx:
                res = frozenset(collected)
                self._cache[pratyahara_name] = res
                return res

        res = frozenset(collected)
        self._cache[pratyahara_name] = res
        return res


@dataclass
class DhatupathaRecord:
    root_form:           str
    inherent_anubandhas: Set[str]
    class_name:          str
    inherent_accent:     AccentFeature


class DhatupathaEngine:
    """
    First-class verbal root registry.
    """
    def __init__(self, records: Optional[List[DhatupathaRecord]] = None):
        self._records: Dict[str, DhatupathaRecord] = {}
        if records:
            for r in records:
                self._records[r.root_form] = r

    def register(self, record: DhatupathaRecord) -> None:
        self._records[record.root_form] = record

    def lookup(self, root_form: str, config: TraditionConfig) -> Optional[DhatupathaRecord]:
        return self._records.get(root_form)


@dataclass
class GanaMembershipRecord:
    root_id:        str
    gana_name:      str
    anubandhas:     Set[str]
    lexical_accent: AccentFeature


class GanapathaEngine:
    """
    First-class nominal/verbal gaṇa registry returning rich records.
    """
    def __init__(self, records: Optional[List[GanaMembershipRecord]] = None):
        self._records: Dict[Tuple[str, str], GanaMembershipRecord] = {}
        if records:
            for r in records:
                self._records[(r.root_id, r.gana_name)] = r

    def register(self, record: GanaMembershipRecord) -> None:
        self._records[(record.root_id, record.gana_name)] = record

    def lookup(
        self,
        token: Any,
        gana_name: str,
        config: TraditionConfig
    ) -> Optional[GanaMembershipRecord]:
        root_id = getattr(token, "root_id", getattr(token, "current_state_id", str(token)))
        return self._records.get((root_id, gana_name))

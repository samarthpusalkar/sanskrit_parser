"""
Lexical Database Interfaces.

Provides query methods for verb roots (Dhātus) and nominal stems (Prātipadikas).
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class DhatuEntry:
    id: int
    root: str
    raw_upadesha: str
    gana: int
    pada: str
    set_status: str
    gloss: str


@dataclass
class StemEntry:
    stem: str
    gender: str
    antya: str


class Lexicon:
    _dhatus: Dict[str, DhatuEntry] = {}
    _stems: Dict[str, StemEntry] = {}
    _loaded: bool = False

    @classmethod
    def load(cls, fixture_path: Optional[Path] = None) -> None:
        if cls._loaded:
            return
        if fixture_path is None:
            fixture_path = Path(__file__).parent / "dhatupatha.json"

        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("roots", []):
            entry = DhatuEntry(**item)
            cls._dhatus[entry.root] = entry

        for item in data.get("nominal_stems", []):
            entry = StemEntry(**item)
            cls._stems[entry.stem] = entry

        cls._loaded = True

    @classmethod
    def get_dhatu(cls, root_slp1: str) -> Optional[DhatuEntry]:
        cls.load()
        return cls._dhatus.get(root_slp1)

    @classmethod
    def get_stem(cls, stem_slp1: str) -> Optional[StemEntry]:
        cls.load()
        return cls._stems.get(stem_slp1)

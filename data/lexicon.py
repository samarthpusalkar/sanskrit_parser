"""
Lexical Database Interfaces backed by Master SQLite Database.

Provides O(1) indexed SQL query methods for ~2,000 verb roots (Dhātus)
and ~40,000 nominal stems (Prātipadikas).
"""

import functools
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class DhatuEntry:
    id: int
    base_index: str
    dhatu_dev: str
    dhatu_slp1: str
    dhatu_iast: str
    gana: int
    pada: str
    settva: str
    karma: str
    artha_eng: str
    tags: str


@dataclass
class StemEntry:
    id: int
    word_dev: str
    word_slp1: str
    word_iast: str
    linga: str
    artha_eng: str
    forms_slp1: str


class Lexicon:
    _db_path = Path(__file__).parent / "sanskrit_master.db"
    _conn: Optional[sqlite3.Connection] = None

    @classmethod
    def _get_conn(cls) -> sqlite3.Connection:
        if cls._conn is None:
            if not cls._db_path.exists():
                from data.db_compiler import compile_database
                compile_database(str(cls._db_path))
            cls._conn = sqlite3.connect(str(cls._db_path))
        return cls._conn

    @classmethod
    def get_dhatu(cls, root_slp1: str) -> Optional[DhatuEntry]:
        conn = cls._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM dhatus WHERE dhatu_slp1 = ? LIMIT 1", (root_slp1,))
        row = cur.fetchone()
        if row:
            return DhatuEntry(*row)
        return None

    @classmethod
    def get_stem(cls, stem_slp1: str) -> Optional[StemEntry]:
        conn = cls._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM pratipadikas WHERE word_slp1 = ? LIMIT 1", (stem_slp1,))
        row = cur.fetchone()
        if row:
            return StemEntry(*row)
        return None

    @classmethod
    def is_valid_stem(cls, stem_slp1: str) -> bool:
        if not stem_slp1:
            return False
        return cls._is_valid_stem_cached(stem_slp1)

    @classmethod
    def _is_valid_stem_cached(cls, stem_slp1: str) -> bool:
        # Delegate to module-level cached function (populated on first call)
        return _cached_is_valid_stem(stem_slp1)

    @classmethod
    def load(cls, fixture_path: Optional[Path] = None) -> None:
        cls._get_conn()


@functools.lru_cache(maxsize=65536)
def _cached_is_valid_stem(stem_slp1: str) -> bool:
    """Module-level cached wrapper for Lexicon.is_valid_stem — prevents repeated SQL hits."""
    conn = Lexicon._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pratipadikas WHERE word_slp1 = ? OR word_iast = ? LIMIT 1", (stem_slp1, stem_slp1))
    if cur.fetchone():
        return True
    cur.execute("SELECT 1 FROM dhatus WHERE dhatu_slp1 = ? OR dhatu_iast = ? LIMIT 1", (stem_slp1, stem_slp1))
    if cur.fetchone():
        return True
    cur.execute("SELECT 1 FROM dhatu_forms WHERE form_slp1 = ? OR form_iast = ? LIMIT 1", (stem_slp1, stem_slp1))
    return bool(cur.fetchone())

"""
Sutra Compiler — sanskrit_dsl/compiler.py

Compiles SutraSpec objects into CompiledSutra objects that the meta-rule
engine can execute. Caches compiled sūtras per-chapter.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from .types import SutraSpec, CompiledSutra
from .parser import SutraParser
from .meta_engine import MetaRuleEngine

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


class SutraCompiler:
    """Compiles sūtras from the DB into executable CompiledSutra objects."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.parser = SutraParser(db_path)
        self.meta_engine = MetaRuleEngine(db_path)
        self._cache: Dict[str, CompiledSutra] = {}
        self._chapter_cache: Dict[str, List[CompiledSutra]] = {}

    def compile_sutra(self, sutra_id: str) -> CompiledSutra:
        """Compile a single sūtra."""
        if sutra_id in self._cache:
            return self._cache[sutra_id]

        spec = self.parser.parse_from_db(sutra_id)

        # Apply anuvṛtti inheritance only for missing operation
        # (don't inherit contexts — they're sutra-specific)
        if spec.operation.op_type == "non_operational" and self.meta_engine.anuvrtti.active_operation:
            spec.operation = self.meta_engine.anuvrtti.active_operation

        # Update anuvṛtti tracker with this sūtra's slots
        self.meta_engine.anuvrtti.step(spec)

        compiled = CompiledSutra(
            sutra_id=sutra_id,
            spec=spec,
            compiled_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        )
        self._cache[sutra_id] = compiled
        return compiled

    def compile_chapter(self, chapter: str) -> List[CompiledSutra]:
        """Compile all sūtras in a chapter."""
        if chapter in self._chapter_cache:
            return self._chapter_cache[chapter]

        self.meta_engine.load()

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id FROM sutras WHERE id LIKE ? ORDER BY id",
            (f"{chapter}.%",)
        ).fetchall()
        conn.close()

        compiled = []
        for (sutra_id,) in rows:
            sutra = self.compile_sutra(sutra_id)
            if sutra.spec.is_executable:
                compiled.append(sutra)

        self._chapter_cache[chapter] = compiled
        return compiled

    def compile_all(self) -> List[CompiledSutra]:
        """Compile all sūtras in the canonical universe."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT id FROM sutras ORDER BY id").fetchall()
        conn.close()

        compiled = []
        for (sutra_id,) in rows:
            sutra = self.compile_sutra(sutra_id)
            if sutra.spec.is_executable:
                compiled.append(sutra)

        return compiled

    def get_stats(self) -> Dict[str, int]:
        """Return compilation statistics."""
        total = len(self._cache)
        executable = sum(1 for s in self._cache.values() if s.spec.is_executable)
        by_parser: Dict[str, int] = {}
        for s in self._cache.values():
            by_parser[s.spec.parsed_by] = by_parser.get(s.spec.parsed_by, 0) + 1

        return {
            "total_compiled": total,
            "executable": executable,
            "non_executable": total - executable,
            "by_parser": by_parser,
        }
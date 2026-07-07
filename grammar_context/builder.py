"""
Context builder — reads panini_rules DB in canonical order and builds
a GrammarContext by processing each sūtra sequentially.

This is the deterministic, no-LLM pass that assembles the accumulated
grammar state from already-extracted rules.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .context import GrammarContext, _sort_key, _chapter_of

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def _json_loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


class ContextBuilder:
    """Builds GrammarContext by sequentially processing panini_rules rows."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _load_sutra_row(self, conn: sqlite3.Connection, sutra_id: str) -> Optional[sqlite3.Row]:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM panini_rules WHERE sutra_id = ?", (sutra_id,)
        ).fetchone()

    def _load_anuvrtti_links(self, conn: sqlite3.Connection, sutra_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT inherited_from_sutra_id, inherited_field, inherited_text "
            "FROM panini_rule_anuvrtti_links WHERE rule_id = ?", (sutra_id,)
        ).fetchall()
        return [{"inherited_from_sutra_id": r[0], "inherited_field": r[1],
                 "inherited_text": r[2]} for r in rows]

    def _load_paribhasa_axiom(self, conn: sqlite3.Connection, sutra_id: str) -> Dict[str, Any]:
        row = conn.execute(
            "SELECT axiom_ast, paribhasa_category, scope_sutra_ids, "
            "applies_to_domains, applies_to_operation_types "
            "FROM panini_rule_paribhasa_axioms WHERE rule_id = ?", (sutra_id,)
        ).fetchone()
        if not row:
            return {}
        return {"axiom_ast": row[0], "paribhasa_category": row[1],
                "scope_sutra_ids": _json_loads(row[2], []),
                "applies_to_domains": _json_loads(row[3], []),
                "applies_to_operation_types": _json_loads(row[4], [])}

    def _all_sutra_ids_in_order(self, conn: sqlite3.Connection, chapter_prefix: Optional[str] = None) -> List[str]:
        if chapter_prefix:
            rows = conn.execute(
                "SELECT sutra_id FROM panini_rules WHERE sutra_id LIKE ? ORDER BY sutra_id",
                (f"{chapter_prefix}.%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT sutra_id FROM panini_rules ORDER BY sutra_id"
            ).fetchall()
        ids = [r[0] for r in rows]
        # Sort canonically (numeric, not lexicographic)
        ids.sort(key=_sort_key)
        return ids

    def build_up_to(
        self,
        target_sutra_id: str,
        start_from: Optional[str] = None,
    ) -> GrammarContext:
        """Build context by processing all sūtras up to (not including) the target.

        If start_from is given, only process sūtras from that point onward
        (useful for resuming from a checkpoint).
        """
        ctx = GrammarContext()
        with self._connect() as conn:
            all_ids = self._all_sutra_ids_in_order(conn)
            target_key = _sort_key(target_sutra_id)
            start_key = _sort_key(start_from) if start_from else (0, 0, 0)

            for sid in all_ids:
                sid_key = _sort_key(sid)
                if sid_key >= target_key:
                    break
                if sid_key < start_key:
                    continue
                self._process_one(conn, ctx, sid)

        return ctx

    def build_for_chapter(self, chapter_prefix: str) -> GrammarContext:
        """Build context up to the start of a chapter (all prior sūtras)."""
        # Find the first sūtra of the chapter
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sutra_id FROM panini_rules WHERE sutra_id LIKE ? ORDER BY sutra_id LIMIT 1",
                (f"{chapter_prefix}.%",),
            ).fetchone()
        if not row:
            return GrammarContext()
        return self.build_up_to(row[0])

    def build_full(self) -> GrammarContext:
        """Build context by processing ALL sūtras in the DB."""
        ctx = GrammarContext()
        with self._connect() as conn:
            all_ids = self._all_sutra_ids_in_order(conn)
            for sid in all_ids:
                self._process_one(conn, ctx, sid)
        return ctx

    def _process_one(self, conn: sqlite3.Connection, ctx: GrammarContext, sutra_id: str) -> None:
        """Process a single sūtra row and update the context."""
        row = self._load_sutra_row(conn, sutra_id)
        if not row:
            return

        anuvrtti_links = self._load_anuvrtti_links(conn, sutra_id)
        paribhasa = self._load_paribhasa_axiom(conn, sutra_id) if row["rule_type"] == "paribhasa" else {}

        ctx.process_sutra(
            sutra_id=sutra_id,
            rule_type=row["rule_type"] or "non_operational",
            defined_sanjna=row["defined_sanjna"],
            definition_type=row["definition_type"],
            definition_criteria=_json_loads(row["definition_criteria"], None),
            equivalent_sutra_ids=_json_loads(row["equivalent_sutra_ids"], []),
            adhikara_topic=row["sutra_dev"] if row["rule_type"] == "adhikara" else None,
            governs_range_start=row["governs_range_start"],
            governs_range_end=row["governs_range_end"],
            scope_condition=_json_loads(row["scope_condition"], None),
            anuvrtti_links=anuvrtti_links,
            paribhasa_axiom=paribhasa.get("axiom_ast"),
            paribhasa_category=paribhasa.get("paribhasa_category"),
        )
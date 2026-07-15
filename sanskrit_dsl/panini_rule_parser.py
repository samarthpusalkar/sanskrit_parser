"""
New schema parser — sanskrit_dsl/panini_rule_parser.py

Reads from the clean `panini_rules` + `panini_rule_*` tables and builds the
SutraSpec objects used by the compiler/executor.

This parser is the bridge between the comprehensive LLM extraction schema and
the runtime Sanskrit engine.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Set

from .types import SutraContext, SutraOperation, SutraSpec

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def _json_loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        val = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
    if val is None:
        return default
    return val


def _as_set(value: Any) -> Set[str]:
    if not value:
        return set()
    try:
        return {str(v) for v in value}
    except TypeError:
        return set()


def _build_context(row: sqlite3.Row) -> Optional[SutraContext]:
    """Build a SutraContext from a panini_rule_contexts row."""
    if row is None:
        return None
    pratyahara = row["pratyahara"]
    exact = _json_loads(row["exact_phonemes"], None)
    sanjna_required = _as_set(_json_loads(row["sanjna_required"], []))
    sanjna_prohibited = _as_set(_json_loads(row["sanjna_prohibited"], []))
    meta_terms = _json_loads(row["meta_terms"], [])
    tokens_required = _json_loads(row["tokens_required"], [])

    has_any = (
        pratyahara or exact or sanjna_required or sanjna_prohibited
        or row["morphological_category"] or row["morphological_features"]
        or row["is_padanta"] or row["is_samhita"] or row["is_savarna"]
        or meta_terms or tokens_required or row["sthani_phoneme"]
    )
    if not has_any:
        return None

    ctx = SutraContext(
        pratyahara=pratyahara,
        exact_text=",".join(exact) if isinstance(exact, list) else exact,
        tokens_required=tokens_required or [],
        tags_required=set(meta_terms or []),
        sanjna_required=sanjna_required,
        prohibit_if_sanjna=sanjna_prohibited,
        sthani_phoneme=row["sthani_phoneme"],
        morphological_category=row["morphological_category"],
        match_pos=row["position"] or "end",
        commentary_note="",
    )
    return ctx


def _build_operation(row: sqlite3.Row) -> SutraOperation:
    """Build a SutraOperation from a panini_rules row."""
    op_type = row["operation_type"] or "non_operational"
    replacement = row["replacement"] or ""
    compute_fn = row["compute_fn"]

    # If compute_fn is unset but op_type implies one, set it.
    if not compute_fn:
        if op_type in ("guna", "ekadesha_guna"):
            compute_fn = "guna"
        elif op_type in ("vrddhi", "ekadesha_vrddhi"):
            compute_fn = "vrddhi"
        elif op_type in ("dirgha", "savarna_long", "ekadesha_savarna_dirgha"):
            compute_fn = "savarna_long"
        elif op_type in ("bijection", "bijection_substitute", "yan"):
            compute_fn = "bijection"

    emit = ""
    if op_type in ("exact_substitute", "substitute", "pratyaya_insert", "augment"):
        emit = replacement

    op = SutraOperation(
        op_type=op_type,
        replacement=replacement,
        emit=emit,
        emit_side=row["emit_side"] or "left",
        left_consume=row["left_consume"] or 0,
        right_consume=row["right_consume"] or 0,
        compute_fn=compute_fn,
    )
    return op


class PaniniRuleParser:
    """Parser that reads from panini_rules schema and produces SutraSpec."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def parse(self, sutra_id: str) -> SutraSpec:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM panini_rules WHERE sutra_id = ?", (sutra_id,)
            ).fetchone()
            if not row:
                return SutraSpec(
                    sutra_id=sutra_id,
                    sutra_text="",
                    parsed_by="not_found",
                )

            contexts = conn.execute(
                "SELECT * FROM panini_rule_contexts WHERE rule_id = ?", (sutra_id,)
            ).fetchall()

            conditions = conn.execute(
                "SELECT * FROM panini_rule_conditions WHERE rule_id = ?", (sutra_id,)
            ).fetchall()

        return self._row_to_spec(row, contexts, conditions)

    def _row_to_spec(
        self,
        row: sqlite3.Row,
        contexts: List[sqlite3.Row],
        conditions: List[sqlite3.Row],
    ) -> SutraSpec:
        sutra_id = row["sutra_id"]

        target_ctx: Optional[SutraContext] = None
        left_ctx: Optional[SutraContext] = None
        right_ctx: Optional[SutraContext] = None

        for ctx_row in contexts:
            ctx = _build_context(ctx_row)
            role = ctx_row["context_role"]
            if role == "target":
                target_ctx = ctx
            elif role == "left":
                left_ctx = ctx
            elif role == "right":
                right_ctx = ctx

        # If the rule has saṃjñā-related metadata but no target context was
        # stored, create an empty target context so the metadata is visible.
        sthani = row["sthani_phoneme"] if "sthani_phoneme" in row.keys() else None
        morph_cat = row["morphological_category"] if "morphological_category" in row.keys() else None
        defined_sanjna = row["defined_sanjna"] if "defined_sanjna" in row.keys() else None
        if target_ctx is None and (sthani or morph_cat or defined_sanjna):
            target_ctx = SutraContext(match_pos="end")

        op = _build_operation(row)

        conditioning_factors: Set[str] = set()
        applicable_paribhasas: List[str] = []
        for cond in conditions:
            text = cond["condition_text"]
            if text:
                conditioning_factors.add(text)

        return SutraSpec(
            sutra_id=sutra_id,
            sutra_text=row["sutra_dev"] or "",
            name=row["sutra_dev"] or "",
            rule_type=row["rule_type"] or "vidhi",
            target_context=target_ctx,
            left_context=left_ctx,
            right_context=right_ctx,
            operation=op,
            conditioning_factors=conditioning_factors,
            applicable_paribhasas=applicable_paribhasas,
            domain=row["domain"] or "sapada",
            anuvrtti_carries=_json_loads(row["anuvrtti_carries"], {}),
            commentary_notes=row["commentary_notes"] or "",
            parsed_by=row["extraction_mode"] or "panini_rules",
            confidence=row["confidence"] or 0.0,
            hurdles=_json_loads(row["hurdles"], []),
            _db_is_executable=bool(row["is_executable"]) if "is_executable" in row.keys() else None,
        )

    def parse_chapter(self, chapter_prefix: str) -> List[SutraSpec]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT sutra_id FROM panini_rules WHERE sutra_id LIKE ? ORDER BY sutra_id",
                (f"{chapter_prefix}.%",),
            ).fetchall()
        return [self.parse(r[0]) for r in rows]

    def list_chapters(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT substr(sutra_id, 1, instr(sutra_id, '.') - 1) || '.' || "
                "substr(sutra_id, instr(sutra_id, '.') + 1, 1) "
                "FROM panini_rules ORDER BY 1"
            ).fetchall()
        return [r[0] for r in rows if r[0]]

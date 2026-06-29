"""
Sutra Text Parser — sanskrit_dsl/parser.py

Parses Pāṇinian sūtra text (Devanagari) directly into SutraSpec objects.
Uses vibhakti (case) semantics to determine roles, resolves pratyāhāras
dynamically, and integrates anuvṛtti and LLM-extracted metadata.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Dict, List, Optional

from .types import SutraSpec, SutraContext, SutraOperation

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


class SutraParser:
    """Parses sūtra text into SutraSpec objects."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def parse_from_db(self, sutra_id: str) -> SutraSpec:
        """Parse a sūtra from the DB, combining vibhakti parsing with LLM metadata."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT id, sutra_dev, pada_cheda, sutra_type FROM sutras WHERE id = ?",
            (sutra_id,)
        ).fetchone()
        llm_row = None
        try:
            llm_row = conn.execute(
                "SELECT * FROM llm_extracted_metadata WHERE sutra_id = ?",
                (sutra_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            pass  # Table doesn't exist yet
        conn.close()

        if not row:
            return SutraSpec(sutra_id=sutra_id, sutra_text="", parsed_by="not_found")

        sid, sutra_dev, pada_cheda, sutra_type = row

        # Start with LLM extraction if available (higher fidelity)
        if llm_row:
            spec = self._from_llm_row(llm_row, sid, sutra_dev)
        else:
            spec = self._from_vibhakti(sid, sutra_dev, pada_cheda or "", sutra_type or "")

        return spec

    def parse_chapter(self, chapter: str) -> List[SutraSpec]:
        """Parse all sūtras in a chapter (e.g., '6.1')."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id FROM sutras WHERE id LIKE ? ORDER BY id",
            (f"{chapter}.%",)
        ).fetchall()
        conn.close()
        return [self.parse_from_db(r[0]) for r in rows]

    def _from_llm_row(self, row, sutra_id: str, sutra_dev: str) -> SutraSpec:
        """Build a SutraSpec from LLM-extracted metadata."""
        (
            _sid, op_type, target, left_ctx, right_ctx, replacement,
            cond_factors_json, paribhasas_json, domain, anuvrtti_json,
            commentary, confidence, hurdles_json, _extracted_at, _model
        ) = row

        op = SutraOperation(
            op_type=op_type or "non_operational",
            replacement=replacement or "",
        )

        target_ctx = SutraContext(exact_text=target) if target else None
        left_context = SutraContext(exact_text=left_ctx) if left_ctx else None
        right_context = SutraContext(exact_text=right_ctx) if right_ctx else None

        return SutraSpec(
            sutra_id=sutra_id,
            sutra_text=sutra_dev,
            operation=op,
            target_context=target_ctx,
            left_context=left_context,
            right_context=right_context,
            conditioning_factors=set(json.loads(cond_factors_json or "[]")),
            applicable_paribhasas=json.loads(paribhasas_json or "[]"),
            domain=domain or "sapada",
            anuvrtti_carries=json.loads(anuvrtti_json or "{}"),
            commentary_notes=commentary or "",
            parsed_by="llm_extract",
            confidence=confidence or 0,
            hurdles=json.loads(hurdles_json or "[]"),
        )

    def _from_vibhakti(self, sutra_id: str, sutra_dev: str, pada_cheda: str, sutra_type: str) -> SutraSpec:
        """
        Parse using vibhakti semantics (the classical approach).
        This is the fallback when no LLM extraction is available.
        """
        from compiler.pada_cheda import PadaChedaParser
        from compiler.ast_builder import SutraAstBuilder
        from research.recorder import record_attempt, record_hurdle

        try:
            tokens = PadaChedaParser.parse(pada_cheda)
            ast_builder = SutraAstBuilder()
            rule_spec = ast_builder.build(sutra_id, sutra_dev, tokens, priority=100)

            # Convert RuleSpec → SutraSpec via PrimitiveOp
            prim = rule_spec.operation.to_primitive() if hasattr(rule_spec.operation, 'to_primitive') else None
            if prim:
                op = SutraOperation(
                    op_type=prim.op_type,
                    replacement=prim.substitute,
                    left_consume=prim.left_consume,
                    right_consume=prim.right_consume,
                    emit=prim.emit,
                    emit_side=prim.emit_side,
                    compute_fn=prim.compute_fn,
                )
            else:
                op = SutraOperation(
                    op_type=getattr(rule_spec.operation, "op_type", "non_operational"),
                    replacement=getattr(rule_spec.operation, "substitute", ""),
                )

            target_ctx = self._convert_condition(rule_spec.target_context)
            left_ctx = self._convert_condition(rule_spec.left_context)
            right_ctx = self._convert_condition(rule_spec.right_context)

            domain = "sapada"
            parts = sutra_id.split(".")
            if len(parts) >= 2:
                try:
                    adhyaya = int(parts[0])
                    pada = int(parts[1])
                    if adhyaya == 8 and pada >= 2:
                        domain = "tripadi"
                except ValueError:
                    pass

            spec = SutraSpec(
                sutra_id=sutra_id,
                sutra_text=sutra_dev,
                operation=op,
                target_context=target_ctx,
                left_context=left_ctx,
                right_context=right_ctx,
                domain=domain,
                parsed_by="vibhakti_parser",
                confidence=0.5,
            )

            if not spec.is_executable:
                record_hurdle(
                    sutra_id,
                    "vocabulary_missing",
                    f"Vibhakti parser could not resolve semantics. op_type={op.op_type}",
                    blocking=False,
                    approach_attempted="vibhakti_parse",
                )

            return spec

        except Exception as e:
            record_hurdle(
                sutra_id,
                "parse_error",
                f"Vibhakti parser raised: {e}",
                blocking=True,
                approach_attempted="vibhakti_parse",
            )
            return SutraSpec(sutra_id=sutra_id, sutra_text=sutra_dev, parsed_by="vibhakti_parse")

    def _convert_condition(self, cond) -> Optional[SutraContext]:
        """Convert a ConditionSpec to a SutraContext."""
        if cond is None:
            return None
        return SutraContext(
            pratyahara=getattr(cond, "pratyahara", None),
            exact_text=getattr(cond, "exact_text", None),
            tokens_required=list(getattr(cond, "tokens_required", []) or []),
            tags_required=set(getattr(cond, "tags_required", set()) or set()),
            match_pos=getattr(cond, "match_pos", "end"),
        )
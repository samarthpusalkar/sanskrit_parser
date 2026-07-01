"""
Sutra Text Parser — sanskrit_dsl/parser.py

Parses Pāṇinian sūtra text into SutraSpec objects.

Primary path: LLM-extracted metadata from llm_extracted_metadata table
  (produced by tools/llm_sutra_extractor.py using Ollama + commentary context)

Fallback path: A clean vibhakti-based parser that does NOT depend on the
  deprecated compiler/ast_builder.py SutraAstBuilder. The old parser
  misassigned vibhakti roles for many sutras and has been deprecated.

The fallback parser is intentionally simple and honest: it parses what it
can and marks the rest as non_executable with a recorded hurdle. It does
NOT pretend to understand sutras it cannot parse.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Dict, List, Optional

from .types import SutraSpec, SutraContext, SutraOperation

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def _safe_loads(raw, default):
    """json.loads that treats None/'null'/errors as the default."""
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
    if value is None:
        return default
    return value


def _as_set(value):
    """Coerce a value into a set of strings (handles None / non-iterables)."""
    if not value:
        return set()
    try:
        return set(str(v) for v in value)
    except TypeError:
        return set()


class SutraParser:
    """Parses sūtra text into SutraSpec objects."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def parse_from_db(self, sutra_id: str) -> SutraSpec:
        """Parse a sūtra from the DB. Prefers LLM extraction, falls back to vibhakti."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT id, sutra_dev, pada_cheda, sutra_type FROM sutras WHERE id = ?",
            (sutra_id,)
        ).fetchone()
        llm_row = None
        try:
            llm_row = conn.execute(
                "SELECT sutra_id, operation_type, target, left_context, right_context, "
                "replacement, conditioning_factors, applicable_paribhasas, domain, "
                "anuvrtti_carries, commentary_notes, confidence, hurdles, extracted_at, model, "
                "sanjna_required, prohibit_if_sanjna, sthani_phoneme, morphological_category "
                "FROM llm_extracted_metadata WHERE sutra_id = ?",
                (sutra_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            pass
        conn.close()

        if not row:
            return SutraSpec(sutra_id=sutra_id, sutra_text="", parsed_by="not_found")

        sid, sutra_dev, pada_cheda, sutra_type = row

        if llm_row:
            return self._from_llm_row(llm_row, sid, sutra_dev)
        else:
            return self._from_vibhakti_clean(sid, sutra_dev, pada_cheda or "", sutra_type or "")

    def parse_chapter(self, chapter: str) -> List[SutraSpec]:
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
            commentary, confidence, hurdles_json, _extracted_at, _model,
            sanjna_required_json, prohibit_if_sanjna_json, sthani_phoneme,
            morphological_category
        ) = row

        op = SutraOperation(
            op_type=op_type or "non_operational",
            replacement=replacement or "",
        )

        if op_type in ("exact_substitute", "substitute") and replacement:
            op.emit = replacement
            op.left_consume = 1
        elif op_type in ("ekadesha_guna", "guna") and replacement:
            op.compute_fn = "guna"
            op.left_consume = 1
            op.right_consume = 1
        elif op_type in ("ekadesha_vriddhi", "vrddhi") and replacement:
            op.compute_fn = "vrddhi"
            op.left_consume = 1
            op.right_consume = 1
        elif op_type in ("ekadesha_savarna_dirgha", "dirgha", "savarna_long") and replacement:
            op.compute_fn = "savarna_long"
            op.left_consume = 1
            op.right_consume = 1
        elif op_type in ("bijection", "bijection_substitute", "yan") and replacement:
            op.compute_fn = "bijection"
            op.left_consume = 1
            op.replacement = replacement

        target_ctx = self._ctx_from_llm_term(target, "end")
        left_context = self._ctx_from_llm_term(left_ctx, "end")
        right_context = self._ctx_from_llm_term(right_ctx, "start")

        sanjna_required = _as_set(_safe_loads(sanjna_required_json, []))
        prohibit_if_sanjna = _as_set(_safe_loads(prohibit_if_sanjna_json, []))
        has_sanjna_meta = bool(sanjna_required or prohibit_if_sanjna
                               or sthani_phoneme or morphological_category)
        if target_ctx is None and has_sanjna_meta:
            target_ctx = SutraContext(match_pos="end")
        if target_ctx is not None:
            target_ctx.sanjna_required = sanjna_required
            target_ctx.prohibit_if_sanjna = prohibit_if_sanjna
            target_ctx.sthani_phoneme = sthani_phoneme or None
            target_ctx.morphological_category = morphological_category or None

        return SutraSpec(
            sutra_id=sutra_id,
            sutra_text=sutra_dev,
            operation=op,
            target_context=target_ctx,
            left_context=left_context,
            right_context=right_context,
            conditioning_factors=_as_set(_safe_loads(cond_factors_json, [])),
            applicable_paribhasas=_safe_loads(paribhasas_json, []),
            domain=domain or "sapada",
            anuvrtti_carries=_safe_loads(anuvrtti_json, {}),
            commentary_notes=commentary or "",
            parsed_by="llm_extract",
            confidence=confidence or 0,
            hurdles=_safe_loads(hurdles_json, []),
        )

    def _from_vibhakti_clean(self, sutra_id: str, sutra_dev: str, pada_cheda: str, sutra_type: str) -> SutraSpec:
        """
        Clean vibhakti-based parser. Does NOT use the deprecated SutraAstBuilder.

        This parser is intentionally conservative: it only extracts semantics
        when the vibhakti roles are unambiguous. When it cannot determine the
        correct interpretation, it marks the sūtra as non_executable and
        records a hurdle.

        This is honest: it doesn't pretend to understand what it can't.
        """
        from compiler.pada_cheda import PadaChedaParser
        from research.recorder import record_hurdle

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

        if sutra_type and sutra_type.startswith("S$"):
            return SutraSpec(
                sutra_id=sutra_id, sutra_text=sutra_dev, domain=domain,
                parsed_by="sanjna_definition",
            )

        if sutra_type and sutra_type.startswith("P$"):
            return SutraSpec(
                sutra_id=sutra_id, sutra_text=sutra_dev, domain=domain,
                parsed_by="paribhasha",
            )

        try:
            tokens = PadaChedaParser.parse(pada_cheda)
        except Exception:
            return SutraSpec(
                sutra_id=sutra_id, sutra_text=sutra_dev, domain=domain,
                parsed_by="parse_failed",
            )

        target_cond = None
        left_cond = None
        right_cond = None
        op = SutraOperation(op_type="non_operational")

        for token in tokens:
            if token.is_target:
                if target_cond is None:
                    target_cond = SutraContext(match_pos="end")
                slp = token.slp1
                prat = self._try_resolve_pratyahara(slp)
                if prat:
                    target_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H")) else slp
                    target_cond.exact_text = norm

            elif token.is_right_context:
                if right_cond is None:
                    right_cond = SutraContext(match_pos="start")
                slp = token.slp1
                prat = self._try_resolve_pratyahara(slp)
                if prat:
                    right_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("i", "e")) else slp
                    right_cond.exact_text = norm

            elif token.is_left_context:
                if left_cond is None:
                    left_cond = SutraContext(match_pos="end")
                slp = token.slp1
                prat = self._try_resolve_pratyahara(slp)
                if prat:
                    left_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H", "t")) else slp
                    left_cond.exact_text = norm

            elif token.is_substitute or (token.case == 1 and not token.is_target):
                slp = token.slp1
                if slp in ("guRa", "guRaH"):
                    op = SutraOperation(op_type="ekadesha_guna", compute_fn="guna",
                                       left_consume=1, right_consume=1, emit_side="left")
                elif slp in ("vfdDi", "vfdDiH"):
                    op = SutraOperation(op_type="ekadesha_vriddhi", compute_fn="vrddhi",
                                       left_consume=1, right_consume=1, emit_side="left")
                elif slp in ("dIrGa", "dIrGaH"):
                    op = SutraOperation(op_type="ekadesha_savarna_dirgha", compute_fn="savarna_long",
                                       left_consume=1, right_consume=1, emit_side="left")
                elif slp in ("yaR", "yaN"):
                    op = SutraOperation(op_type="bijection_substitute", compute_fn="bijection",
                                       replacement="yaR", left_consume=1, emit_side="left")
                elif slp in ("lopa", "lopaH", "adasRNa"):
                    op = SutraOperation(op_type="elide", left_consume=1, emit="")
                else:
                    prat = self._try_resolve_pratyahara(slp)
                    if prat:
                        op = SutraOperation(op_type="bijection_substitute", compute_fn="bijection",
                                           replacement=prat, left_consume=1, emit_side="left")
                    else:
                        norm = slp[:-1] if slp.endswith(("H", "s")) else slp
                        op = SutraOperation(op_type="exact_substitute", replacement=norm,
                                           emit=norm, left_consume=1, emit_side="left")

        spec = SutraSpec(
            sutra_id=sutra_id,
            sutra_text=sutra_dev,
            operation=op,
            target_context=target_cond,
            left_context=left_cond,
            right_context=right_cond,
            domain=domain,
            parsed_by="vibhakti_clean",
            confidence=0.4,
        )

        if not spec.is_executable:
            record_hurdle(
                sutra_id,
                "vibhakti_incomplete",
                f"Clean parser could not extract operation. sutra_type={sutra_type}",
                blocking=False,
                approach_attempted="vibhakti_clean",
            )

        return spec

    def _ctx_from_llm_term(self, term: Optional[str], match_pos: str) -> Optional[SutraContext]:
        """Build a SutraContext from an LLM-extracted term.

        Tries pratyahara resolution first (e.g. 'ak' -> aK pratyahara).
        Falls back to exact_text. Handles pipe/comma alternatives.
        """
        if not term:
            return None
        cleaned = term.strip()
        if not cleaned:
            return None
        # Alternatives separated by '|' or ',' — try each as pratyahara.
        alternatives = [a.strip() for a in cleaned.replace(",", "|").split("|") if a.strip()]
        pratyaharas = []
        exacts = []
        for alt in alternatives:
            prat = self._try_resolve_pratyahara(alt)
            if prat:
                pratyaharas.append(prat)
            else:
                exacts.append(alt)
        ctx = SutraContext(match_pos=match_pos)
        if pratyaharas and not exacts:
            ctx.pratyahara = pratyaharas[0]
        elif pratyaharas and exacts:
            # Mixed: keep exact text alternatives; pratyahara match is a bonus.
            ctx.exact_text = "|".join(exacts)
        else:
            ctx.exact_text = "|".join(extras) if (extras := exacts) else None
            if not ctx.exact_text:
                return None
        return ctx

    def _try_resolve_pratyahara(self, slp: str) -> Optional[str]:
        """Try to resolve a term as a pratyahara using PratyaharaResolver."""
        from core.shiva_sutras import PratyaharaResolver

        candidates = [slp]
        for suffix in ("aH", "AH", "i", "e", "s", "H", "Am"):
            if slp.endswith(suffix) and len(slp) > len(suffix):
                candidates.append(slp[:-len(suffix)])

        for candidate in candidates:
            if len(candidate) >= 2:
                normalized = candidate[:-1] + candidate[-1].upper()
                try:
                    PratyaharaResolver.resolve(normalized)
                    return normalized
                except (ValueError, Exception):
                    pass

        return None
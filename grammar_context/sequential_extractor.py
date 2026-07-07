"""
Sequential Pāṇinian extractor with GrammarContext.

This is the new extractor that processes sūtras in canonical order
(1.1.1 → 8.4.68) and includes the accumulated GrammarContext (saṃjñās,
adhikāras, anuvṛtti carries, paribhāṣās) in every LLM prompt.

It reuses the schema, validation, storage, and LLM caller from the
existing tools/batch_panini_extractor.py but wraps them with context-aware
prompt building and sequential context updates.

Run:
    python -m grammar_context.sequential_extractor --chapter-prefix 3.1 --model deepseek-v4-pro:cloud
    python -m grammar_context.sequential_extractor --chapter-prefix 3 --resume
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Reuse the proven building blocks from the existing extractor.
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(_TOOLS_DIR))

from batch_panini_extractor import (
    ExtractorDB,
    build_extraction_schema,
    validate_extraction,
    store_comprehensive_extraction,
    record_hurdle,
    call_ollama,
    _sutra_block,
    _json,
    _coerce_dict,
    DB_PATH,
    HURDLES_DIR,
)

from .context import GrammarContext
from .builder import ContextBuilder, _sort_key


# ---------------------------------------------------------------------------
# Context-aware prompt builder
# ---------------------------------------------------------------------------

def _context_block(ctx: GrammarContext, max_entries: int = 40) -> List[str]:
    """Build a compact, LLM-readable summary of the accumulated grammar context."""
    lines: List[str] = []
    summary = ctx.context_summary()

    sanjnas = summary["defined_sanjnas"][:max_entries]
    if sanjnas:
        lines.append("DEFINED SAṆJÑĀS IN FORCE (use these terms as-is):")
        for s in sanjnas:
            lines.append(f"  - {s}")
        if len(summary["defined_sanjnas"]) > max_entries:
            lines.append(f"  ... and {len(summary['defined_sanjnas']) - max_entries} more")
        lines.append("")

    adhikaras = summary["active_adhikaras"][:max_entries]
    if adhikaras:
        lines.append("ACTIVE ADHIKĀRAS (scope declarations governing interpretation):")
        for a in adhikaras:
            lines.append(f"  - {a}")
        lines.append("")

    carries = summary["anuvrtti_carries"][:max_entries]
    if carries:
        lines.append("ANUVṚTTI CARRIES (implicit context carried forward from recent sūtras):")
        for c in carries:
            lines.append(f"  - {c}")
        lines.append("")

    paribhasas = summary["paribhasas_in_force"][:max_entries]
    if paribhasas:
        lines.append("PARIBHĀṢĀS IN FORCE (meta-rules affecting evaluation):")
        for p in paribhasas:
            lines.append(f"  - {p}")
        lines.append("")

    return lines


def build_contextual_prompt(
    sutra: Dict[str, Any],
    grammar_ctx: GrammarContext,
    schema: Dict[str, Any],
    include_commentary: bool = True,
) -> str:
    """Build a single-sūtra extraction prompt with full grammar context."""
    lines = [
        "You are a Pāṇinian grammar expert. Extract compiler-ready metadata for the following sūtra.",
        "The sūtra's meaning depends on all previously defined terms and active scope declarations.",
        "",
    ]

    # Grammar context block
    ctx_lines = _context_block(grammar_ctx)
    if ctx_lines:
        lines.extend(ctx_lines)

    # The sūtra itself
    lines.append("SŪTRA TO EXTRACT:")
    lines.extend("  " + l for l in _sutra_block(sutra, include_commentary=include_commentary))
    lines.append("")

    # Schema
    lines.extend([
        "Return a single JSON object matching this schema (use null for unknown fields; all phonemes in SLP1):",
        json.dumps(schema, indent=2, ensure_ascii=False),
        "",
        "Answer these explicitly:",
        "1. rule_type: vidhi or niyama?",
        "2. operation_type and exact target pratyāhāra/phoneme.",
        "3. replacement, compute_fn, left_consume, right_consume.",
        "4. left/right contexts and any required/prohibited saṃjñās.",
        "5. Does this sūtra carry anything forward via anuvṛtti?",
        "Return ONLY the JSON object, no explanation.",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sequential extraction
# ---------------------------------------------------------------------------

class SequentialExtractor:
    """Extract sūtras in canonical order with accumulated grammar context."""

    def __init__(
        self,
        db_path: str = DB_PATH,
        model: str = "deepseek-v4-pro:cloud",
        delay: float = 0.1,
        resume: bool = False,
        timeout: int = 600,
    ) -> None:
        self.db = ExtractorDB(db_path)
        self.builder = ContextBuilder(db_path)
        self.model = model
        self.delay = delay
        self.resume = resume
        self.timeout = timeout
        self.schema = build_extraction_schema()

    def _load_sutras_for_chapter(self, chapter_prefix: str) -> List[Dict[str, Any]]:
        return self.db.load_sutras_for_chapter(chapter_prefix)

    def _all_sutra_ids_in_order(self, chapter_prefix: Optional[str] = None) -> List[str]:
        conn = sqlite3.connect(self.db.db_path)
        if chapter_prefix:
            rows = conn.execute(
                "SELECT sutra_id FROM panini_rules WHERE sutra_id LIKE ? ORDER BY sutra_id",
                (f"{chapter_prefix}.%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT sutra_id FROM panini_rules ORDER BY sutra_id"
            ).fetchall()
        conn.close()
        ids = [r[0] for r in rows]
        ids.sort(key=_sort_key)
        return ids

    def extract_chapter(self, chapter_prefix: str) -> Dict[str, Any]:
        """Extract one chapter sequentially with context."""
        all_sutras = self._load_sutras_for_chapter(chapter_prefix)
        all_sutras.sort(key=lambda s: _sort_key(s["id"]))

        if not all_sutras:
            return {"chapter_prefix": chapter_prefix, "total": 0, "attempted": 0, "stored": 0, "failed": []}

        # Build context up to the first sūtra of this chapter.
        first_id = all_sutras[0]["id"]
        ctx = self.builder.build_up_to(first_id)

        attempted = 0
        stored = 0
        failed: List[str] = []

        for sutra in all_sutras:
            sid = sutra["id"]
            if self.resume and self.db.is_extracted(sid):
                # Skip but still update context from the existing extraction.
                self._advance_context_from_db(ctx, sid)
                continue

            prompt = build_contextual_prompt(sutra, ctx, self.schema)
            attempted += 1
            result = call_ollama(prompt, self.model, timeout=self.timeout, expect_array=False)

            if isinstance(result, dict) and "error" in result:
                record_hurdle(sid, [f"llm error: {result['error']}"])
                failed.append(sid)
                if self.delay > 0:
                    time.sleep(self.delay)
                continue
            if not isinstance(result, dict):
                record_hurdle(sid, ["non-object response"])
                failed.append(sid)
                if self.delay > 0:
                    time.sleep(self.delay)
                continue

            errors = validate_extraction(sid, result)
            if errors:
                record_hurdle(sid, errors)
                failed.append(sid)
                if self.delay > 0:
                    time.sleep(self.delay)
                continue

            with self.db.connect() as conn:
                store_comprehensive_extraction(conn, sutra, result, self.model, "sequential")
            stored += 1

            # Update context with this sūtra's definitions.
            self._advance_context_from_extraction(ctx, sid, result)

            if self.delay > 0:
                time.sleep(self.delay)

        return {
            "chapter_prefix": chapter_prefix,
            "total": len(all_sutras),
            "attempted": attempted,
            "stored": stored,
            "failed": failed,
        }

    def _advance_context_from_db(self, ctx: GrammarContext, sutra_id: str) -> None:
        """Update context from an already-stored sūtra (used for --resume skips)."""
        conn = sqlite3.connect(self.db.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM panini_rules WHERE sutra_id = ?", (sutra_id,)
        ).fetchone()
        if not row:
            conn.close()
            return
        anu_rows = conn.execute(
            "SELECT inherited_from_sutra_id, inherited_field, inherited_text "
            "FROM panini_rule_anuvrtti_links WHERE rule_id = ?", (sutra_id,)
        ).fetchall()
        conn.close()

        ctx.process_sutra(
            sutra_id=sutra_id,
            rule_type=row["rule_type"] or "non_operational",
            defined_sanjna=row["defined_sanjna"],
            definition_type=row["definition_type"],
            definition_criteria=_json_loads_opt(row["definition_criteria"]),
            equivalent_sutra_ids=_json_loads_opt(row["equivalent_sutra_ids"], []),
            adhikara_topic=row["sutra_dev"] if row["rule_type"] == "adhikara" else None,
            governs_range_start=row["governs_range_start"],
            governs_range_end=row["governs_range_end"],
            scope_condition=_json_loads_opt(row["scope_condition"]),
            anuvrtti_links=[{"inherited_from_sutra_id": r[0], "inherited_field": r[1],
                             "inherited_text": r[2]} for r in anu_rows],
        )

    def _advance_context_from_extraction(self, ctx: GrammarContext, sutra_id: str, extraction: Dict[str, Any]) -> None:
        """Update context from a freshly extracted sūtra."""
        sanjna_def = _coerce_dict(extraction.get("sanjna_definition"))
        adhikara_def = _coerce_dict(extraction.get("adhikara_definition"))
        anuvrtti = _coerce_dict(extraction.get("anuvrtti"))

        ctx.process_sutra(
            sutra_id=sutra_id,
            rule_type=extraction.get("rule_type") or "non_operational",
            defined_sanjna=sanjna_def.get("defined_sanjna"),
            definition_type=sanjna_def.get("definition_type"),
            definition_criteria=sanjna_def.get("definition_criteria"),
            equivalent_sutra_ids=sanjna_def.get("equivalent_sutra_ids", []),
            adhikara_topic=extraction.get("sutra_dev") if extraction.get("rule_type") == "adhikara" else None,
            governs_range_start=adhikara_def.get("governs_range_start"),
            governs_range_end=adhikara_def.get("governs_range_end"),
            scope_condition=adhikara_def.get("scope_condition"),
            anuvrtti_links=[{"inherited_from_sutra_id": anuvrtti.get("inherited_from_sutra_id", ""),
                             "inherited_field": f, "inherited_text": ""}
                            for f in anuvrtti.get("carries", [])] if anuvrtti.get("inherited_from_sutra_id") else None,
        )


def _json_loads_opt(raw, default=None):
    if default is None:
        default = []
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sequential Pāṇinian extractor with GrammarContext"
    )
    parser.add_argument("--chapter-prefix", default="all",
                        help="Chapter prefix like 3.1, adhyāya like 3, or 'all'")
    parser.add_argument("--model", default="deepseek-v4-pro:cloud")
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout", type=int, default=600,
                        help="LLM call timeout in seconds")
    args = parser.parse_args(argv)

    extractor = SequentialExtractor(
        model=args.model, delay=args.delay, resume=args.resume, timeout=args.timeout
    )

    # Determine chapter prefixes to process.
    if args.chapter_prefix == "all":
        prefixes = extractor.db.list_chapter_prefixes()
    elif "." not in args.chapter_prefix:
        prefixes = [p for p in extractor.db.list_chapter_prefixes()
                    if p.startswith(args.chapter_prefix + ".")]
        prefixes.sort()
    else:
        prefixes = [args.chapter_prefix]

    if not prefixes:
        print(f"No chapters found for prefix {args.chapter_prefix!r}")
        return 1

    all_stats = []
    for prefix in prefixes:
        print(f"\n=== Sequentially extracting {prefix} ===")
        stats = extractor.extract_chapter(prefix)
        all_stats.append(stats)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n=== Summary ===")
    print(json.dumps(all_stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
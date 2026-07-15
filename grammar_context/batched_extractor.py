"""
Batched Pāṇinian extractor with GrammarContext.

Processes sūtras in batches of N (default 10) per LLM call, but still in
canonical order with accumulated grammar context. The LLM is told to track
context as it parses each sūtra in the batch — definitions from sūtra 1 in
the batch are available to sūtra 2, etc.

This reduces LLM calls by ~10x vs the sequential extractor, while keeping
context-awareness. The prompt includes:
  1. The accumulated GrammarContext from all prior chapters/batches.
  2. The batch of N sūtras to extract, in order.
  3. An instruction to track definitions/operations within the batch.

Run:
    python -m grammar_context.batched_extractor --chapter-prefix 3.1 --model deepseek-v4-pro:cloud
    python -m grammar_context.batched_extractor --chapter-prefix 3 --resume --batch-size 10
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))

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
)

from .context import GrammarContext
from .builder import ContextBuilder, _sort_key
from .sequential_extractor import _context_block, _json_loads_opt


def build_batched_contextual_prompt(
    sutras: List[Dict[str, Any]],
    grammar_ctx: GrammarContext,
    schema: Dict[str, Any],
    include_commentary: bool = True,
) -> str:
    """Build a batch prompt that includes grammar context + N sūtras in order.

    The LLM is instructed to process sūtras sequentially within the batch,
    tracking definitions and operations as it goes.
    """
    lines = [
        "You are a Pāṇinian grammar expert. Extract compiler-ready metadata for EACH of the",
        f"following {len(sutras)} sūtras, processed IN ORDER. Later sūtras in this batch may",
        "depend on definitions from earlier ones in the same batch — track definitions and",
        "operations as you parse each sūtra sequentially.",
        "",
    ]

    # Grammar context block (accumulated from all prior sūtras)
    ctx_lines = _context_block(grammar_ctx)
    if ctx_lines:
        lines.extend(ctx_lines)

    # The batch of sūtras, numbered
    lines.append(f"SŪTRAS TO EXTRACT (batch of {len(sutras)}, in canonical order):")
    for i, sutra in enumerate(sutras, 1):
        lines.append(f"\n--- Sūtra {i}/{len(sutras)} ---")
        lines.extend("  " + l for l in _sutra_block(sutra, include_commentary=include_commentary))
    lines.append("")

    # Schema
    lines.extend([
        "Return a JSON ARRAY of objects, one per sūtra, in the SAME ORDER as listed above.",
        "Each object matches this schema (use null for unknown fields; all phonemes in SLP1):",
        json.dumps(schema, indent=2, ensure_ascii=False),
        "",
        "For EACH sūtra, answer explicitly:",
        "1. rule_type: vidhi or niyama or samjna_definition or paribhasa or adhikara?",
        "2. operation_type and exact target pratyāhāra/phoneme.",
        "3. replacement, compute_fn, left_consume, right_consume.",
        "4. left/right contexts and any required/prohibited saṃjñās.",
        "5. Does this sūtra define a new saṃjñā? If so, set sanjna_definition.defined_sanjna.",
        "6. Does this sūtra carry anything forward via anuvṛtti?",
        "7. Does this sūtra declare an adhikāra scope?",
        "",
        "IMPORTANT: If a sūtra defines a term (e.g. 'vṛddhir ādaiñ' defines vṛddhi), later",
        "sūtras in this batch may use that term — interpret them accordingly.",
        "Return ONLY the JSON array, no explanation.",
    ])
    return "\n".join(lines)


class BatchedContextualExtractor:
    """Extract sūtras in batches with accumulated grammar context."""

    def __init__(
        self,
        db_path: str = DB_PATH,
        model: str = "deepseek-v4-pro:cloud",
        delay: float = 0.1,
        resume: bool = False,
        batch_size: int = 10,
        timeout: int = 600,
    ) -> None:
        self.db = ExtractorDB(db_path)
        self.builder = ContextBuilder(db_path)
        self.model = model
        self.delay = delay
        self.resume = resume
        self.batch_size = batch_size
        self.timeout = timeout
        self.schema = build_extraction_schema()

    def _load_sutras_for_chapter(self, chapter_prefix: str) -> List[Dict[str, Any]]:
        return self.db.load_sutras_for_chapter(chapter_prefix)

    def extract_chapter(self, chapter_prefix: str) -> Dict[str, Any]:
        """Extract one chapter in batches with context."""
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

        # Process in batches
        batches = [all_sutras[i:i + self.batch_size]
                   for i in range(0, len(all_sutras), self.batch_size)]

        for batch in batches:
            # Filter out already-extracted sūtras if resuming
            if self.resume:
                to_extract = [s for s in batch if not self.db.is_extracted(s["id"])]
                already = [s for s in batch if self.db.is_extracted(s["id"])]
                # Update context from already-extracted sūtras
                for s in already:
                    self._advance_context_from_db(ctx, s["id"])
                if not to_extract:
                    continue
                batch_to_process = to_extract
            else:
                batch_to_process = batch

            prompt = build_batched_contextual_prompt(batch_to_process, ctx, self.schema)
            attempted += len(batch_to_process)
            result = call_ollama(prompt, self.model, timeout=self.timeout, expect_array=True)

            if isinstance(result, dict) and "error" in result:
                for s in batch_to_process:
                    record_hurdle(s["id"], [f"batch error: {result['error']}"])
                failed.extend([s["id"] for s in batch_to_process])
                if self.delay > 0:
                    time.sleep(self.delay)
                continue
            if not isinstance(result, list):
                # Try to salvage complete objects from truncated JSON
                from batch_panini_extractor import _repair_truncated_json
                # Re-read the raw text — but we don't have it here since call_ollama
                # returns parsed. The repair already happened inside _safe_parse_json.
                # If we still get non-list, fail the batch.
                for s in batch_to_process:
                    record_hurdle(s["id"], ["batch returned non-array (unparseable response)"])
                failed.extend([s["id"] for s in batch_to_process])
                if self.delay > 0:
                    time.sleep(self.delay)
                continue

            # Process each sūtra's extraction from the batch result.
            # If the array was truncated (fewer objects than expected),
            # store the ones we got and fail only the missing ones.
            for idx, sutra in enumerate(batch_to_process):
                if idx >= len(result):
                    record_hurdle(sutra["id"], ["batch result truncated: missing index"])
                    failed.append(sutra["id"])
                    continue
                extraction = result[idx]
                if not isinstance(extraction, dict):
                    record_hurdle(sutra["id"], ["extraction is not a JSON object"])
                    failed.append(sutra["id"])
                    continue
                errors = validate_extraction(sutra["id"], extraction)
                if errors:
                    record_hurdle(sutra["id"], errors)
                    failed.append(sutra["id"])
                    continue
                with self.db.connect() as conn:
                    store_comprehensive_extraction(conn, sutra, extraction, self.model, "batched_contextual")
                stored += 1
                # Update context with this sūtra's definitions
                self._advance_context_from_extraction(ctx, sutra["id"], extraction)

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
        """Update context from an already-stored sūtra."""
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batched Pāṇinian extractor with GrammarContext"
    )
    parser.add_argument("--chapter-prefix", default="all",
                        help="Chapter prefix like 3.1, adhyāya like 3, or 'all'")
    parser.add_argument("--model", default="deepseek-v4-pro:cloud")
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Sūtras per LLM call (default 10)")
    parser.add_argument("--timeout", type=int, default=600,
                        help="LLM call timeout in seconds")
    args = parser.parse_args(argv)

    extractor = BatchedContextualExtractor(
        model=args.model, delay=args.delay, resume=args.resume,
        batch_size=args.batch_size, timeout=args.timeout,
    )

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
        print(f"\n=== Batched context extraction: {prefix} ===")
        stats = extractor.extract_chapter(prefix)
        all_stats.append(stats)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n=== Summary ===")
    print(json.dumps(all_stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
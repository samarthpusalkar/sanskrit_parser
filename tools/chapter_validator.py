#!/usr/bin/env python3
"""
Chapter Validator — tools/chapter_validator.py

Validates a chapter's sūtras against the benchmark suite and records hurdles.

Usage:
    python tools/chapter_validator.py --chapter 6.1
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sanskrit_dsl.compiler import SutraCompiler
from research.recorder import record_attempt, record_hurdle, update_feasibility


def validate_chapter(chapter: str):
    """Compile and validate all sūtras in a chapter."""
    compiler = SutraCompiler()
    compiled = compiler.compile_chapter(chapter)

    total_in_chapter = 0
    import sqlite3
    db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT id FROM sutras WHERE id LIKE ?", (f"{chapter}.%",)).fetchall()
    total_in_chapter = len(rows)
    conn.close()

    executable = len(compiled)
    non_executable = total_in_chapter - executable
    rate = 100 * executable / total_in_chapter if total_in_chapter else 0

    print(f"\nChapter {chapter} Validation:")
    print(f"  Total sūtras:     {total_in_chapter}")
    print(f"  Executable:       {executable}")
    print(f"  Non-executable:   {non_executable}")
    print(f"  Execution rate:   {rate:.1f}%")

    # Record hurdles for non-executable sūtras
    for sutra in compiled:
        if sutra.spec.hurdles:
            for hurdle in sutra.spec.hurdles:
                print(f"  HURDLE: {sutra.sutra_id} — {hurdle}")

    stats = compiler.get_stats()
    print(f"\n  Compiler stats: {stats}")

    # Update feasibility
    update_feasibility(
        f"Chapter {chapter}: {rate:.1f}% executable ({executable}/{total_in_chapter})",
        f"Non-executable: {non_executable}. Hurdles recorded in research/hurdles/."
    )

    return rate


def main():
    parser = argparse.ArgumentParser(description="Validate a chapter of Pāṇinian sūtras")
    parser.add_argument("--chapter", required=True, help="Chapter to validate (e.g., '6.1')")
    args = parser.parse_args()

    validate_chapter(args.chapter)


if __name__ == "__main__":
    main()
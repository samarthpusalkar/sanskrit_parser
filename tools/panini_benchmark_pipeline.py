#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from benchmarks.pipeline import compare_with_baseline, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Paninian benchmark pipeline.")
    parser.add_argument("--engine", default="local", choices=["local"], help="Engine adapter to run.")
    parser.add_argument("--domain", default="all", choices=["all", "sandhi"], help="Benchmark domain selector.")
    parser.add_argument(
        "--case-path",
        default=os.path.join(ROOT, "tests", "fixtures", "panini_blackbox_cases.json"),
        help="Path to the benchmark case fixture JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(ROOT, "tests", "results"),
        help="Directory for benchmark reports.",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline JSON to compare against.",
    )
    args = parser.parse_args()

    payload = run_pipeline(case_path=args.case_path, output_dir=args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2, sort_keys=True))

    if args.baseline:
        diffs = compare_with_baseline(payload, args.baseline)
        if diffs:
            print("\nBaseline regression detected:")
            for diff in diffs:
                print(f"  - {diff}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

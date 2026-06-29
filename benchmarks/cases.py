from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Dict, Iterable, List

from .models import BenchmarkCase

DEFAULT_CASES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests",
    "fixtures",
    "panini_blackbox_cases.json",
)

VALID_INTERFACES = {"sandhi_join", "dispatch_forward", "conjugate", "decline"}


def load_cases(path: str = DEFAULT_CASES_PATH) -> List[BenchmarkCase]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Benchmark case file must contain a list of case objects.")

    seen_ids = set()
    cases: List[BenchmarkCase] = []
    for raw in payload:
        case = BenchmarkCase(
            case_id=raw["case_id"],
            sutra_id=raw["sutra_id"],
            domain=raw["domain"],
            interface=raw["interface"],
            inputs=raw["inputs"],
            expected_output=raw.get("expected_output"),
            case_kind=raw["case_kind"],
            family_id=raw["family_id"],
            expected_rule_presence=raw.get("expected_rule_presence"),
            notes=raw.get("notes", ""),
            source=raw.get("source", ""),
            tags=list(raw.get("tags", [])),
        )
        validate_case(case)
        if case.case_id in seen_ids:
            raise ValueError(f"Duplicate benchmark case_id: {case.case_id}")
        seen_ids.add(case.case_id)
        cases.append(case)

    return cases


def validate_case(case: BenchmarkCase) -> None:
    if case.case_kind not in {"positive", "negative_control", "perturbation"}:
        raise ValueError(f"Unsupported case_kind for {case.case_id}: {case.case_kind}")
    if case.interface not in VALID_INTERFACES:
        raise ValueError(f"Unsupported interface for {case.case_id}: {case.interface}")
    # sandhi cases require left/right inputs; morphological cases have their own input shapes
    if case.interface in {"sandhi_join", "dispatch_forward"}:
        if "left" not in case.inputs or "right" not in case.inputs:
            raise ValueError(f"{case.case_id} must contain left/right inputs.")
    if case.expected_rule_presence is None:
        case.expected_rule_presence = case.case_kind != "negative_control"


def family_map(cases: Iterable[BenchmarkCase]) -> Dict[str, List[BenchmarkCase]]:
    grouped: Dict[str, List[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        grouped[case.family_id].append(case)
    return dict(grouped)
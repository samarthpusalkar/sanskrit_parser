from __future__ import annotations

import os
import sqlite3
from collections import Counter
from typing import Dict, Iterable, List, Mapping, Set

from .models import RuleUniverseEntry

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "sanskrit_master.db",
)


def load_rule_universe(db_path: str = DB_PATH) -> Dict[str, RuleUniverseEntry]:
    """Load the canonical sutra universe and annotate rule_config availability."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sutra_ids = [row[0] for row in cur.execute("SELECT id FROM sutras ORDER BY id").fetchall()]
    config_counts = {
        sutra_id: count
        for sutra_id, count in cur.execute(
            "SELECT sutra_id, COUNT(*) FROM rule_configs GROUP BY sutra_id"
        ).fetchall()
    }
    conn.close()

    return {
        sutra_id: RuleUniverseEntry(
            sutra_id=sutra_id,
            has_rule_config=sutra_id in config_counts,
            rule_config_count=config_counts.get(sutra_id, 0),
        )
        for sutra_id in sutra_ids
    }


def annotate_rule_universe(
    universe: Mapping[str, RuleUniverseEntry],
    *,
    case_counts: Mapping[str, int],
    loaded_rule_ids: Iterable[str],
    executed_rule_ids: Iterable[str],
    hardcoding_suspect_ids: Iterable[str],
    trace_verified_ids: Iterable[str] = (),
) -> Dict[str, RuleUniverseEntry]:
    """Return a classified copy of the canonical rule universe."""
    loaded = set(loaded_rule_ids)
    executed = set(executed_rule_ids)
    hardcoding = set(hardcoding_suspect_ids)
    trace_verified = set(trace_verified_ids)

    annotated: Dict[str, RuleUniverseEntry] = {}
    for sutra_id, entry in universe.items():
        item = RuleUniverseEntry(
            sutra_id=entry.sutra_id,
            has_rule_config=entry.has_rule_config,
            rule_config_count=entry.rule_config_count,
            case_count=case_counts.get(sutra_id, 0),
            loaded_by_runtime=sutra_id in loaded,
            executed_dynamically=sutra_id in executed,
            adapter_supported=case_counts.get(sutra_id, 0) > 0,
            hardcoding_suspected=sutra_id in hardcoding,
            meta_rule_unverified=sutra_id in executed and sutra_id not in trace_verified,
        )

        if not item.has_rule_config:
            item.classification = "missing_rule_config"
        elif item.case_count == 0 and not item.loaded_by_runtime:
            item.classification = "rule_config_only"
        elif item.case_count == 0:
            item.classification = "adapter_pending"
        elif not item.loaded_by_runtime:
            item.classification = "runtime_unloaded"
        elif item.executed_dynamically:
            if item.meta_rule_unverified:
                item.classification = "executed_meta_unverified"
            else:
                item.classification = "executed"
        else:
            item.classification = "execution_unmapped"

        annotated[sutra_id] = item

    return annotated


def derive_trace_verified_ids(
    results: Iterable["BenchmarkResult"],
    expected_traces: Optional[Mapping[str, Sequence[str]]] = None,
) -> Set[str]:
    """
    Return the set of sutra IDs whose trace was explicitly verified.

    A result is trace-verified when its applied_rule_ids contain the expected
    sutra_id AND the trace_steps are non-empty (derivation evidence exists).
    If expected_traces is provided, each case_id must match the ordered rule
    sequence declared in the fixture.
    """
    verified: Set[str] = set()
    expected = expected_traces or {}
    for result in results:
        if not result.output_match or result.hardcoding_suspected or result.errors:
            continue
        case_id = result.case.case_id
        applied = result.evidence.applied_rule_ids
        trace = result.evidence.trace_steps
        if result.case.sutra_id in applied and trace:
            if case_id in expected:
                if [step.get("sutra_id") for step in trace] == list(expected[case_id]):
                    verified.add(result.case.sutra_id)
            else:
                verified.add(result.case.sutra_id)
    return verified


def case_counts_by_sutra(sutra_ids: Iterable[str]) -> Dict[str, int]:
    return dict(Counter(sutra_ids))


def summarize_classifications(entries: Mapping[str, RuleUniverseEntry]) -> Dict[str, int]:
    return dict(Counter(entry.classification for entry in entries.values()))


def find_unknown_case_sutras(
    universe: Mapping[str, RuleUniverseEntry],
    benchmark_sutra_ids: Iterable[str],
) -> List[str]:
    known = set(universe)
    return sorted({sutra_id for sutra_id in benchmark_sutra_ids if sutra_id not in known})

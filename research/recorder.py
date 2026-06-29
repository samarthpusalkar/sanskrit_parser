"""
Research Recorder — research/recorder.py

Institutional memory for the Paninian DSL project. Every attempt, hurdle,
and approach is logged so we can make first-principles feasibility judgments.

This is append-only. Never delete logs. They are the evidence base.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

RESEARCH_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "research")
LOG_DIR = os.path.join(RESEARCH_DIR, "log")
HURDLES_DIR = os.path.join(RESEARCH_DIR, "hurdles")
APPROACHES_DIR = os.path.join(RESEARCH_DIR, "approaches")
FEASIBILITY_PATH = os.path.join(RESEARCH_DIR, "feasibility.md")


def _timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_dirs():
    for d in (LOG_DIR, HURDLES_DIR, APPROACHES_DIR):
        os.makedirs(d, exist_ok=True)


def record_attempt(sutra_id: str, approach: str, result: str, notes: str = "") -> None:
    """Log a single compilation/execution attempt for a sūtra."""
    _ensure_dirs()
    entry = {
        "timestamp": _timestamp(),
        "sutra_id": sutra_id,
        "approach": approach,
        "result": result,
        "notes": notes,
    }
    log_path = os.path.join(LOG_DIR, f"{datetime.utcnow().strftime('%Y-%m-%d')}.md")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"- [{entry['timestamp']}] `{sutra_id}` | {approach} | **{result}** | {notes}\n")


def record_hurdle(
    sutra_id: str,
    hurdle_type: str,
    description: str,
    blocking: bool = True,
    approach_attempted: str = "",
    commentary_reference: str = "",
    workaround: Optional[str] = None,
) -> None:
    """Record a hurdle that blocked compilation/execution of a sūtra."""
    _ensure_dirs()
    record = {
        "sutra_id": sutra_id,
        "hurdle_type": hurdle_type,
        "description": description,
        "blocking": blocking,
        "approach_attempted": approach_attempted,
        "commentary_reference": commentary_reference,
        "workaround": workaround,
        "recorded_at": _timestamp(),
    }
    hurdle_path = os.path.join(HURDLES_DIR, f"{sutra_id.replace('.', '_')}.json")
    with open(hurdle_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


def record_approach(name: str, description: str, outcome: str, evidence: str = "") -> None:
    """Document an overall approach and its outcome."""
    _ensure_dirs()
    path = os.path.join(APPROACHES_DIR, f"{name}.md")
    content = f"""# Approach: {name}

- **Recorded**: {_timestamp()}
- **Description**: {description}
- **Outcome**: {outcome}
- **Evidence**: {evidence}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def update_feasibility(assessment: str, evidence: str = "") -> None:
    """Update the living feasibility assessment."""
    _ensure_dirs()
    entry = f"""
## Update {_timestamp()}

**Assessment**: {assessment}

**Evidence**: {evidence}
"""
    if os.path.exists(FEASIBILITY_PATH):
        with open(FEASIBILITY_PATH, "r", encoding="utf-8") as f:
            existing = f.read()
    else:
        existing = "# Paninian DSL Feasibility Assessment\n\nThis document is updated after each chapter attempt.\n"

    with open(FEASIBILITY_PATH, "w", encoding="utf-8") as f:
        f.write(existing + entry)


def load_hurdles() -> Dict[str, Any]:
    """Load all hurdle records for analysis."""
    _ensure_dirs()
    hurdles = {}
    for fname in os.listdir(HURDLES_DIR):
        if fname.endswith(".json"):
            path = os.path.join(HURDLES_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
                hurdles[record["sutra_id"]] = record
    return hurdles
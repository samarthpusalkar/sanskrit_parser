"""
Sequential Stateful Anuvṛtti Engine.

Maintains active grammatical context across sūtra boundaries during sequential ingestion.
Enforces Pāṇinian blocking rules where new terms override inherited terms of the same Vibhakti case.
"""

from typing import Dict, Any, Optional
from compiler.registries import AdhikaraContext


class AnuvrittiEngine:
    """Stateful engine tracking active AST conditions across sequential sūtras."""

    _instance = None

    @classmethod
    def get_instance(cls) -> 'AnuvrittiEngine':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.reset()

    def reset(self):
        self.active_target: Optional[Any] = None
        self.active_left_context: Optional[Any] = None
        self.active_right_context: Optional[Any] = None
        self.active_operation: Optional[Any] = None
        self.current_sutra_id: str = ""
        self.active_domain: str = ""

    def step(self, sutra_id: str, target: Any, left: Any, right: Any, op: Any):
        """Update active Anuvṛtti state upon ingesting a sūtra."""
        self.current_sutra_id = sutra_id

        # Check domain boundaries or Adhikāra resets
        props = AdhikaraContext.get_active_properties(sutra_id)
        new_domain = props.get("domain", "")
        if self.active_domain and new_domain != self.active_domain:
            self.active_target = None
            self.active_left_context = None
            self.active_right_context = None
            self.active_operation = None
        self.active_domain = new_domain

        # Update slots if explicitly present in the new sūtra (blocking rule)
        if target is not None:
            self.active_target = target
        if left is not None:
            self.active_left_context = left
        if right is not None:
            self.active_right_context = right
        if op is not None and (getattr(op, "op_type", "") != "substitute" or getattr(op, "substitute", "") != ""):
            self.active_operation = op

    def get_inherited_slots(self, sutra_id: str) -> Dict[str, Any]:
        """Retrieve inherited AST slots for the current sūtra."""
        return {
            "target": self.active_target,
            "left_context": self.active_left_context,
            "right_context": self.active_right_context,
            "operation": self.active_operation
        }

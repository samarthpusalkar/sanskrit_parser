"""
Pāṇinian Compilation & Execution Exceptions.

Provides structured audit error reporting to enforce strict verification
without fallback shortcuts or silent string copying.
"""

from typing import Dict, Any, Optional


class PaninianCompilationError(Exception):
    """Raised when a Sūtra cannot be compiled into an operational AST."""

    def __init__(
        self,
        message: str,
        sutra_id: str = "",
        sutra_text: str = "",
        failed_token: str = "",
        missing_slots: Optional[list] = None,
        anuvritti_trace: Optional[Dict[str, Any]] = None
    ):
        self.sutra_id = sutra_id
        self.sutra_text = sutra_text
        self.failed_token = failed_token
        self.missing_slots = missing_slots or []
        self.anuvritti_trace = anuvritti_trace or {}

        detailed_msg = f"[PaninianCompilationError] {sutra_id} ({sutra_text}): {message}"
        if failed_token:
            detailed_msg += f"\n  Failed Token: '{failed_token}'"
        if self.missing_slots:
            detailed_msg += f"\n  Missing AST Slots: {', '.join(self.missing_slots)}"
        if self.anuvritti_trace:
            detailed_msg += f"\n  Active Anuvṛtti Trace: {self.anuvritti_trace}"

        super().__init__(detailed_msg)

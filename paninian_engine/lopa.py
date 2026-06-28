"""
Lopa Semantics for the Paninian Rewriting Engine.
Distinguishes complete deletions from zero-morph traces accessible to specific sandhi ops.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .visibility import VisibilityMask


class LopaType(Enum):
    FULL_LOPA     = "FULL_LOPA"      # Complete deletion; no zero-morph trace visible
    SHLOPA        = "SHLOPA"         # Zero-morph trace; accessible to specific sandhi ops
    PRAGRIHYA     = "PRAGRIHYA"      # Exempt from sandhi; trace fully visible


@dataclass
class LopaDeletionRecord:
    deleted_state_id: str     # The TokenState that was deleted
    lopa_type:        LopaType
    authority_rule:   str     # Sūtra ID under which deletion occurred


def can_access_lopa_record(record: LopaDeletionRecord, visibility_mask: VisibilityMask) -> bool:
    """
    Access policy: get_state_when may return a LopaDeletionRecord's state
    only if the querying rule's VisibilityMask permits access to the
    authority rule under which the deletion occurred, AND the LopaType is
    not FULL_LOPA. FULL_LOPA states are permanently inaccessible.
    """
    if record.lopa_type == LopaType.FULL_LOPA:
        return False
    return visibility_mask.is_visible(record.authority_rule)

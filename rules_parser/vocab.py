"""
Universal Pāṇinian Vocabulary.

Resolves classical Pāṇinian operational terms (Sañjñās, Paribhāṣās, Āgamas, etc.)
to formal PrimitiveOp tuples by querying the `sanjnas` table in `sanskrit_master.db`.

The `sanjnas` table is bootstrapped from the `sutras` table (data/bootstrap_sanjnas.py)
— every entry traces back to a specific sūtra in the Aṣṭādhyāyī.

No hardcoded Python sets or dictionaries for term classification.
No string-heuristic suffix stripping.
"""

import sqlite3
import os
from typing import Tuple, Optional
from rule_engine.dsl import PrimitiveOp

_DB_PATH = "data/sanskrit_master.db"


def _query_sanjnas(term_slp1: str, is_ekadesha: bool = False, right_cond_present: bool = False) -> Optional[Tuple[PrimitiveOp, str, str]]:
    """
    Query the `sanjnas` table for term_slp1.
    Returns (PrimitiveOp, op_type, substitute) or None.
    """
    if not os.path.exists(_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT op_type, replacement, category FROM sanjnas WHERE term_slp1 = ?",
            (term_slp1,)
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None

        op_type, replacement, category = row

        if category == "ELISION":
            op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left",
                             compute_fn=None, substitute="", op_type="elide")
            return op, "elide", ""

        elif category == "EKADESHA":
            # is_ekadesha flag from the parser determines if both tokens are consumed
            resolved_op_type = op_type if is_ekadesha else "sanjna_substitute"
            if replacement == "dirgha" and is_ekadesha and right_cond_present:
                resolved_op_type = "ekadesha_savarna_dirgha"
            rc = 1 if is_ekadesha else 0
            op = PrimitiveOp(left_consume=1, right_consume=rc, emit="", emit_side="left",
                             compute_fn=replacement, substitute=replacement, op_type=resolved_op_type)
            return op, resolved_op_type, replacement

        elif category == "PURVA_RUPA":
            op = PrimitiveOp(left_consume=0, right_consume=1, emit="'", emit_side="right",
                             compute_fn=None, substitute="'", op_type="purva_rupa")
            return op, "purva_rupa", "'"

        elif category == "PARARUPA":
            op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left",
                             compute_fn=None, substitute="", op_type="pararupa")
            return op, "pararupa", ""

        elif category == "PRAKRITIBHAVA":
            op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left",
                             compute_fn=None, substitute="", op_type="prakritibhava")
            return op, "prakritibhava", ""

        elif category == "GOVERNANCE":
            op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left",
                             compute_fn=None, substitute=term_slp1, op_type="governance")
            return op, "governance", term_slp1

        elif category == "PROHIBIT":
            op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left",
                             compute_fn=None, substitute="prohibit", op_type="prohibit")
            return op, "prohibit", "prohibit"

        elif category == "LITERAL":
            op = PrimitiveOp(left_consume=1, right_consume=0, emit=replacement, emit_side="left",
                             compute_fn=None, substitute=replacement, op_type="substitute")
            return op, "substitute", replacement

        elif category == "AGAMA":
            # `replacement` holds position semantics (before_right / after_left / after_last_vowel / duplicate)
            fn = "duplicate" if replacement == "duplicate" else "agama"
            op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left",
                             compute_fn=fn, substitute="",
                             augment=op_type.replace("augment_", "") if op_type.startswith("augment_") else "",
                             augment_position=replacement, op_type="augment")
            return op, "augment", replacement

        elif category == "NON_OPERATIONAL":
            op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left",
                             compute_fn=None, substitute="", op_type="non_operational")
            return op, "non_operational", ""

    except Exception:
        pass
    return None


def resolve_term_to_primitive(term_slp1: str, is_ekadesha: bool = False, right_cond_present: bool = False) -> Tuple[PrimitiveOp, str, str]:
    """
    Given an operational term in SLP1, return (PrimitiveOp, op_type, substitute).

    Resolution order:
    1. Query `sanjnas` table (derived from the Aṣṭādhyāyī via bootstrap_sanjnas.py)
    2. Check if term is a pratyāhāra (delegate to SutraAstBuilder)
    3. Fall through: treat as a literal phoneme substitute
    """
    db_res = _query_sanjnas(term_slp1, is_ekadesha, right_cond_present)
    if db_res:
        return db_res

    # Pratyāhāra check — resolved by the rule compiler, not here
    from compiler.ast_builder import SutraAstBuilder
    prat = SutraAstBuilder._resolve_pratyahara(term_slp1)
    if prat:
        op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left",
                         compute_fn="bijection", substitute=f"PRAT:{prat}", op_type="exact_substitute")
        return op, "exact_substitute", f"PRAT:{prat}"

    # Final fallback: literal phoneme substitute — the term IS the replacement
    op = PrimitiveOp(left_consume=1, right_consume=0, emit=term_slp1, emit_side="left",
                     compute_fn=None, substitute=term_slp1, op_type="exact_substitute")
    return op, "exact_substitute", term_slp1

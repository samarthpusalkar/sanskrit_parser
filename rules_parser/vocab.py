"""
Universal Pāṇinian Vocabulary.

Maps classical Pāṇinian operational terms, technical definitions (Sañjñās),
meta-rules (Paribhāṣās), and grammatical tokens into formal PrimitiveOp tuples.
"""

import sqlite3
import os
from typing import Dict, Any, Tuple, Optional
from rule_engine.dsl import PrimitiveOp


def _query_db_term(term_slp: str) -> Optional[Tuple[PrimitiveOp, str, str]]:
    db_path = "data/sanskrit_master.db"
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT category, replacement FROM technical_terms WHERE term=?", (term_slp,))
        row = cur.fetchone()
        conn.close()
        if row:
            cat, repl = row
            if cat == "ELISION":
                op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="elide")
                return op, "elide", ""
            elif cat == "EKADESHA":
                op = PrimitiveOp(left_consume=1, right_consume=1, emit="", emit_side="left", compute_fn=repl, substitute=repl, op_type=f"ekadesha_{repl}")
                return op, f"ekadesha_{repl}", repl
            elif cat == "LITERAL":
                op = PrimitiveOp(left_consume=1, right_consume=0, emit=repl, emit_side="left", compute_fn=None, substitute=repl, op_type="substitute")
                return op, "substitute", repl
    except Exception:
        pass
    return None


# Classical Pāṇinian terms indicating elision / deletion (Lopa and its subtypes)
ELISION_TERMS = {
    "lopa", "lopaH", "adarSana", "adarSanam", "luk", "Slu", "lup"
}

# Classical Pāṇinian terms indicating single replacement for both preceding and following (Ekādeśa)
EKADESHA_TERMS = {
    "guRa", "guRaH", "guRa-vfdDI", "vfdDi", "vfdDiH", "vfddhi", "dIrGa", "dIrGaH", "savarRadIrGa"
}

# Classical Pāṇinian terms indicating boundary assimilation
BOUNDARY_TERMS = {
    "pUrvarUpa", "pUrvarUpam", "pararUpa", "pararUpam", "prakftiBAva", "prakftiBAvaH"
}

# Governance and prohibition tokens
GOVERNANCE_TERMS = {
    "viBAzA", "bahulam", "nityam", "anyatarasyAm", "vA", "ca", "tu", "saMyogAdayaH",
    "anudAttam", "svaritaH", "svaritam", "udAttaH", "udAttam", "parasavarRaH", "savarRaH",
    "laGuprayatnataraH", "pUrvam", "param", "antaram", "Amreqitam", "asidDam"
}

PROHIBITION_TERMS = {
    "na", "mA", "prohibit"
}

# Literal replacement stems and phonetic symbols
LITERAL_REPLACEMENTS = {
    "visarjanIya": "H", "visarjanIyaH": "H", "visarga": "H",
    "ru": "r", "roH": "r", "rePa": "r",
    "anusvAra": "M", "anusvAraH": "M",
    "anunAsika": "~", "anunAsikaH": "~",
    "ut": "u", "it": "i", "at": "a", "At": "A"
}

# Augments (āgama) with their positional semantics
# 1.1.46 (ādyantau ṭakitau): ṭ-it -> initial (before_right), k-it -> final (after_left)
# 1.1.47 (mid aco 'ntyāt paraḥ): m-it -> after last vowel
AGAMAS = {
    "wuk": ("t", "before_right"),
    "suw": ("s", "before_right"),
    "nuw": ("n", "before_right"),
    "tuk": ("t", "after_left"),
    "iw": ("i", "before_right"),
    "NamuR": ("N", "after_left"),
    "NamuRnityam": ("N", "after_left"),
    "Num": ("n", "after_last_vowel"),
}

def resolve_term_to_primitive(term_slp: str, is_ekadesha: bool = False, right_cond_present: bool = False) -> Tuple[PrimitiveOp, str, str]:
    """
    Given an operational term in SLP1, returns (PrimitiveOp, op_type, substitute).
    """
    db_res = _query_db_term(term_slp)
    if db_res:
        return db_res

    norm = term_slp[:-1] if term_slp.endswith(("s", "H")) else term_slp

    if term_slp in PROHIBITION_TERMS or norm in PROHIBITION_TERMS:
        op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="prohibit", op_type="prohibit")
        return op, "prohibit", "prohibit"

    if term_slp in GOVERNANCE_TERMS or norm in GOVERNANCE_TERMS:
        op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute=term_slp, op_type="governance")
        return op, "governance", term_slp

    if term_slp in ELISION_TERMS or norm in ELISION_TERMS:
        op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="elide")
        return op, "elide", ""

    if term_slp in {"pUrvarUpa", "pUrvarUpam", "pUrvaH"} or norm in {"pUrvarUpa", "pUrva"}:
        op = PrimitiveOp(left_consume=0, right_consume=1, emit="'", emit_side="right", compute_fn=None, substitute="'", op_type="purva_rupa")
        return op, "purva_rupa", "'"

    if term_slp in {"vAntaH", "vAnto"} or norm == "vAnta":
        op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="non_operational")
        return op, "non_operational", ""

    if term_slp in {"pararUpa", "pararUpam"} or norm == "pararUpa":
        op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="pararupa")
        return op, "pararupa", ""

    if term_slp in {"prakftiBAva", "prakftiBAvaH"} or norm == "prakftiBAva":
        op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="prakritibhava")
        return op, "prakritibhava", ""

    if term_slp in {"guRa", "guRaH", "guRa-vfdDI"} or norm in {"guRa", "guRa-vfdDI"}:
        op_type = "ekadesha_guna" if is_ekadesha else "sanjna_substitute"
        lc = 1 if is_ekadesha else 1
        rc = 1 if is_ekadesha else 0
        op = PrimitiveOp(left_consume=lc, right_consume=rc, emit="", emit_side="left", compute_fn="guna", substitute="guna", op_type=op_type)
        return op, op_type, "guna"

    if term_slp in {"vfdDi", "vfdDiH", "vfddhi"} or norm in {"vfdDi", "vfddhi"}:
        op_type = "ekadesha_vriddhi" if is_ekadesha else "sanjna_substitute"
        lc = 1 if is_ekadesha else 1
        rc = 1 if is_ekadesha else 0
        op = PrimitiveOp(left_consume=lc, right_consume=rc, emit="", emit_side="left", compute_fn="vriddhi", substitute="vriddhi", op_type=op_type)
        return op, op_type, "vriddhi"

    if term_slp in {"dIrGa", "dIrGaH"} or norm == "dIrGa":
        op_type = "ekadesha_savarna_dirgha" if (is_ekadesha and right_cond_present) else "dirgha"
        lc = 1 if is_ekadesha else 1
        rc = 1 if is_ekadesha else 0
        op = PrimitiveOp(left_consume=lc, right_consume=rc, emit="", emit_side="left", compute_fn="dirgha", substitute="dirgha", op_type=op_type)
        return op, op_type, "dirgha"

    if term_slp in {"Namuw", "namuw"}:
        op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn="duplicate", substitute="", op_type="augment")
        return op, "augment", ""

    # Check for agamas (augments)
    aug_val = AGAMAS.get(term_slp, AGAMAS.get(norm))
    if aug_val:
        phoneme, position = aug_val
        op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn="agama", substitute="", augment=phoneme, augment_position=position, op_type="augment")
        return op, "augment", phoneme

    from compiler.ast_builder import SutraAstBuilder
    prat = SutraAstBuilder._resolve_pratyahara(term_slp)
    if prat:
        op = PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", compute_fn="bijection", substitute=f"PRAT:{prat}", op_type="exact_substitute")
        return op, "exact_substitute", f"PRAT:{prat}"

    # Literal replacement check
    sub_val = LITERAL_REPLACEMENTS.get(term_slp, LITERAL_REPLACEMENTS.get(norm, term_slp))
    op = PrimitiveOp(left_consume=1, right_consume=0, emit=sub_val, emit_side="left", compute_fn=None, substitute=sub_val, op_type="exact_substitute")
    return op, "exact_substitute", sub_val

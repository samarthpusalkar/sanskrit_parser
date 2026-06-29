"""
Load sandhi rule_configs from SQLite into paninian_engine RuleObject instances.

Bridges the production rule_configs schema to the declarative PhonologyBridge
execution layer. Converts SLP1 context patterns to IAST for test/runtime input.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional, Set

from core.phonology import slp1_to_iast

from .config import TraditionConfig, AnuvrttiPolicy
from .conflict import RuleObject
from .types import AccentPriorityRule, SutraTextVersion, GanapathaVersion

# Symbolic class tokens used in rule_configs (seed + bootstrap)
_SYMBOLIC_TO_PHONETIC = {
    "VOWEL": "vowel",
    "VOWEL_NON_A": "vowel",
    "CONSONANT": "consonant",
    "SHORT_VOWEL": "short_vowel",
    "NASAL": "nasal",
    "PAUSE_OR_VOICED": "vowel",
    "STOP": "consonant",
    "VOICED": "voiced",
}

# IAST phoneme lists for PratyaharaEngine (from 14 Māheśvara sūtras)
_IAST_PHONEME_ENUMERATION = [
    ["a", "i", "u", "ṇ"],
    ["ṛ", "ḷ", "k"],
    ["e", "o", "ṅ"],
    ["ai", "au", "c"],
    ["h", "y", "v", "r", "ṭ"],
    ["l", "ṇ"],
    ["ñ", "m", "ṅ", "ṇ", "n", "m"],
    ["jh", "bh", "ñ"],
    ["gh", "ḍh", "dh", "ṣ"],
    ["j", "b", "g", "ḍ", "d", "ś"],
    ["kh", "ph", "ch", "ṭh", "th", "c", "ṭ", "t", "v"],
    ["k", "p", "y"],
    ["ś", "ṣ", "s", "r"],
    ["h", "l"],
]

_EXECUTABLE_OP_TYPES = frozenset({
    "savarna_dirgha", "guna", "vriddhi", "yan", "pararupa",
    "ngamut_agama", "mo_anusvarah", "torli", "jhalam_jaso", "jhayo_ho",
    "stutva", "tuk_agama", "natva", "samprasarana", "visarga_sandhi",
    "indeclinable_r", "avagraha", "visarga_utva", "ro_ri_dirgha",
    "sascho_ati", "yaro_anunasike", "prakritibhava",
    "substitute", "exact_substitute", "right_substitute", "bijection_substitute",
})

_SANDHI_CHAPTER_FILTER = """
    (sutra_id GLOB '6.1.*' OR sutra_id GLOB '6.3.*'
     OR sutra_id GLOB '8.2.*' OR sutra_id GLOB '8.3.*' OR sutra_id GLOB '8.4.*')
"""


def _slp1_token_to_iast(token: str) -> str:
    """Convert an SLP1 context token to IAST; pass through if already IAST."""
    if not token:
        return token
    if token in _SYMBOLIC_TO_PHONETIC:
        return token
    if any(ord(c) > 127 for c in token):
        return token
    return "".join(slp1_to_iast(ch) for ch in token)


def _parse_context_pattern(pattern: str) -> Dict[str, Any]:
    """
    Parse a rule_configs context string into a RuleObject context dict.
    Handles PRAT:, TOKEN:, TAG:, EXACT:, symbolic classes, and pipe-separated literals.
    """
    if not pattern or not pattern.strip():
        return {}

    pattern = pattern.strip()
    ctx: Dict[str, Any] = {}

    if pattern.startswith("PRAT:"):
        rest = pattern.removeprefix("PRAT:")
        if "|EXACT:" in rest:
            prat, exact = rest.split("|EXACT:", 1)
            ctx["pratyahara"] = prat.strip()
            ctx["exact_text"] = [_slp1_token_to_iast(p.strip()) for p in exact.split("|") if p.strip()]
        else:
            ctx["pratyahara"] = rest.strip()
        return ctx

    if pattern.startswith("TOKEN:"):
        tokens = [_slp1_token_to_iast(t.strip()) for t in pattern.removeprefix("TOKEN:").split("|") if t.strip()]
        ctx["tokens_required"] = tokens
        ctx["exact_text"] = tokens
        return ctx

    if pattern.startswith("TAG:"):
        ctx["tags_required"] = [t.strip() for t in pattern.removeprefix("TAG:").split("|") if t.strip()]
        return ctx

    if pattern.startswith("EXACT:"):
        parts = [_slp1_token_to_iast(p.strip()) for p in pattern.removeprefix("EXACT:").split("|") if p.strip()]
        ctx["exact_text"] = parts
        return ctx

    if pattern in _SYMBOLIC_TO_PHONETIC:
        ctx["phonetic_class"] = _SYMBOLIC_TO_PHONETIC[pattern]
        return ctx

    if "|" in pattern:
        parts = [_slp1_token_to_iast(p.strip()) for p in pattern.split("|") if p.strip()]
        if len(parts) == 1:
            ctx["exact_text"] = parts[0]
        else:
            ctx["exact_text"] = parts
        return ctx

    ctx["exact_text"] = _slp1_token_to_iast(pattern)
    return ctx


def _map_operation(operation: str, replacement: str, sutra_id: str) -> Dict[str, Any]:
    """Map rule_configs operation + replacement to PhonologyBridge op_type."""
    op = (operation or "").lower()
    repl = replacement or ""
    base = sutra_id.split(".")[0:3]
    sid = ".".join(base) if len(base) >= 3 else sutra_id

    if op in ("external_block", "prakritibhava"):
        return {"op_type": "prakritibhava"}

    if op == "purva_rupa" or repl == "purva_rupa":
        return {"op_type": "avagraha"}

    if op == "visarga_utva":
        return {"op_type": "visarga_utva", "replacement": _slp1_token_to_iast(repl) or "o"}

    if op == "ro_ri_dirgha":
        return {"op_type": "ro_ri_dirgha"}

    if op == "anusvara" or (op == "exact_substitute" and repl in ("M", "ṃ")):
        return {"op_type": "mo_anusvarah"}

    if op == "natva":
        return {"op_type": "natva"}

    if op == "insert" and repl in ("c", "C"):
        return {"op_type": "tuk_agama"}

    if op == "merge":
        repl_iast = _slp1_token_to_iast(repl)
        if repl_iast in ("e", "o", "ar", "al"):
            return {"op_type": "guna", "replacement": repl_iast}
        if repl_iast in ("ā", "ī", "ū", "ṝ") or repl in ("A", "I", "U", "F"):
            return {"op_type": "savarna_dirgha", "replacement": repl_iast}
        if repl_iast in ("ai", "au") or repl in ("E", "O"):
            return {"op_type": "vriddhi", "replacement": repl_iast}

    if op in ("ekadesha_guna",) or repl == "guna":
        return {"op_type": "guna"}

    if op in ("ekadesha_savarna_dirgha", "savarR") or repl == "dirgha":
        return {"op_type": "savarna_dirgha"}

    if op == "ekadesha_vriddhi" or repl == "vriddhi":
        return {"op_type": "vriddhi"}

    if "PRAT:ya" in repl or repl in ("PRAT:yaR", "PRAT:yaN"):
        return {"op_type": "yan"}
    if op == "exact_substitute" and repl in ("r", "ṛ"):
        return {"op_type": "visarga_sandhi"}
    if op == "bijection_substitute":
        if "yaR" in repl or "yaN" in repl:
            return {"op_type": "yan"}
        if repl.startswith("PRAT:ja"):
            return {"op_type": "jhalam_jaso"}
        if "N|" in repl or "Y|" in repl:
            return {"op_type": "yaro_anunasike"}

    if op == "exact_substitute" and "PRAT:ya" in repl:
        return {"op_type": "yan"}

    if sid == "6.1.77" or "yaR" in repl or "yaN" in repl:
        return {"op_type": "yan"}

    if op == "right_substitute":
        return {"op_type": "sascho_ati"}

    if op == "substitute" and repl in ("S", "ś"):
        return {"op_type": "visarga_sandhi"}

    if op == "pararupa" or repl == "pararupa":
        return {"op_type": "pararupa"}

    if op == "prohibit":
        return {"op_type": "prakritibhava"}

    if op in ("governance", "non_operational", "elide"):
        return {"op_type": "prakritibhava"}

    return {"op_type": op or "unknown", "replacement": _slp1_token_to_iast(repl)}


def _build_left_context(target: str, left: str, operation: str) -> Dict[str, Any]:
    """Merge target_context + left_context columns into left (uddeśya) context."""
    target = (target or "").strip()
    left = (left or "").strip()

    if target.startswith("PRAT:") or target.startswith("TOKEN:"):
        return _parse_context_pattern(target)

    if target in ("ma", "m") and operation in ("exact_substitute", "anusvara"):
        return {"exact_text": "m"}

    if target and left and not left.startswith("PRAT:"):
        return _parse_context_pattern(f"{target}|{left}")

    return _parse_context_pattern(target or left)


def _build_right_context(right: str, operation: str) -> Dict[str, Any]:
    """Parse right_context (nimitta); normalize savarṇa markers for dīrgha rules."""
    right = (right or "").strip()
    if right.lower() in ("savarr", "savarṇ", "savarṇa", "savarṇe"):
        return {"pratyahara": "aK"}
    return _parse_context_pattern(right)


def _row_to_rule_object(
    sutra_id: str,
    name: str,
    target_context: str,
    left_context: str,
    right_context: str,
    operation: str,
    replacement: str,
) -> Optional[RuleObject]:
    """Convert one rule_configs row to a RuleObject."""
    op_info = _map_operation(operation, replacement, sutra_id)
    op_type = op_info.get("op_type", "unknown")

    if op_type in ("unknown", "governance") and operation not in (
        "external_block", "prakritibhava", "prohibit"
    ):
        return None

    lc = _build_left_context(target_context, left_context, operation)
    rc = _build_right_context(right_context, operation)

    if op_type == "savarna_dirgha" and not rc:
        rc = {"pratyahara": "aK"}

    if not lc and not rc and op_type == "unknown":
        return None

    return RuleObject(
        sutra_id=sutra_id,
        conditioning_factors=set(),
        effect_type=op_type,
        left_context=lc,
        right_context=rc,
        operation=op_info,
    )


def load_sandhi_rules(db_path: str = "data/sanskrit_master.db") -> List[RuleObject]:
    """Load executable sandhi RuleObjects from rule_configs."""
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    columns = {row[1] for row in cur.execute("PRAGMA table_info(rule_configs)").fetchall()}
    has_target = "target_context" in columns

    if has_target:
        query = f"""
            SELECT sutra_id, name, target_context, left_context, right_context,
                   operation, replacement
            FROM rule_configs
            WHERE (COALESCE(operation, '') NOT IN ('non_operational', 'governance')
              AND {_SANDHI_CHAPTER_FILTER})
              OR COALESCE(operation, '') IN ('prakritibhava', 'external_block')
            ORDER BY sutra_id ASC, id ASC
        """
    else:
        query = f"""
            SELECT sutra_id, name, left_context, NULL, right_context, operation, replacement
            FROM rule_configs
            WHERE (COALESCE(operation, '') != 'non_operational'
              AND {_SANDHI_CHAPTER_FILTER})
              OR COALESCE(operation, '') IN ('prakritibhava', 'external_block')
            ORDER BY sutra_id ASC, id ASC
        """

    rules: List[RuleObject] = []
    seen: Set[str] = set()

    for row in cur.execute(query).fetchall():
        sid, name, tgt, lctx, rctx, op, repl = row
        key = f"{sid}:{name}:{tgt}:{lctx}:{rctx}:{op}"
        if key in seen:
            continue
        seen.add(key)

        rule = _row_to_rule_object(sid, name or sid, tgt or "", lctx or "", rctx or "", op or "", repl or "")
        if rule and rule.effect_type in _EXECUTABLE_OP_TYPES:
            rules.append(rule)

    conn.close()
    return rules


def make_tradition_config(db_path: str = "data/sanskrit_master.db") -> TraditionConfig:
    """Build TraditionConfig with IAST Māheśvara phoneme enumeration."""
    return TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.CRITICAL,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=_IAST_PHONEME_ENUMERATION,
        include_n_in_14th=False,
    )

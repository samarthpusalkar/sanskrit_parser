"""
Manual fix for extraction failures that were rejected due to pratyāhāra validation.

These sūtras reference single phonemes or specific root endings, not pratyāhāras.
We insert corrected records directly into panini_rules.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load_sutra(conn: sqlite3.Connection, sutra_id: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT id, sutra_dev, pada_cheda, sutra_type, samasta_sutra, anuvrtti, adhikara "
        "FROM sutras WHERE id = ?", (sutra_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"sūtra {sutra_id} not found")
    return {
        "id": row[0], "sutra_dev": row[1] or "", "pada_cheda": row[2] or "",
        "sutra_type": row[3] or "", "samasta_sutra": row[4] or "",
        "anuvrtti": row[5] or "", "adhikara": row[6] or "",
    }


def _parse_id(sutra_id: str):
    parts = sutra_id.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _store(conn: sqlite3.Connection, sutra: Dict[str, Any], rule: Dict[str, Any],
           contexts: List[Dict[str, Any]], conditions: List[Dict[str, Any]]) -> None:
    sid = sutra["id"]
    adhyaya, pada, sutra_no = _parse_id(sid)

    conn.execute(
        """INSERT OR REPLACE INTO panini_rules (
            sutra_id, adhyaya, pada, sutra_no, sutra_dev, pada_cheda, sutra_type,
            samasta_sutra, anuvrtti_text, adhikara, adhikara_chain, source_text_hash,
            rule_type, domain, is_executable, is_meta_rule, is_definition,
            anuvrtti_source_sutra_id, anuvrtti_carries,
            operation_type, operation_subtype, replacement, compute_fn,
            left_consume, right_consume, emit_side, emit, preserve_length,
            is_agama, is_lopa, is_nipatana_exception, requires_sthanivadbhava, sthani_phoneme,
            defined_sanjna, definition_type, definition_criteria, equivalent_sutra_ids,
            adhikara_sutra_id, governs_range_start, governs_range_end, scope_condition,
            positive_examples, negative_examples,
            commentary_notes, vyakhya_summary, confidence, extraction_mode, model,
            extracted_at, commentary_used, hurdles, validation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid, adhyaya, pada, sutra_no, sutra["sutra_dev"], sutra["pada_cheda"],
            sutra["sutra_type"], sutra["samasta_sutra"], sutra["anuvrtti"], sutra["adhikara"],
            _json([]), "",
            rule["rule_type"], rule["domain"], int(rule["is_executable"]), int(rule["is_meta_rule"]), int(rule["is_definition"]),
            rule.get("anuvrtti_source_sutra_id"), _json(rule.get("anuvrtti_carries", [])),
            rule["operation_type"], rule.get("operation_subtype"), rule["replacement"], rule.get("compute_fn"),
            rule.get("left_consume", 0), rule.get("right_consume", 0), rule.get("emit_side", "left"), rule.get("emit"),
            int(bool(rule.get("preserve_length"))), int(bool(rule.get("is_agama"))), int(bool(rule.get("is_lopa"))),
            int(bool(rule.get("is_nipatana_exception"))), int(bool(rule.get("requires_sthanivadbhava"))),
            rule.get("sthani_phoneme"),
            rule.get("defined_sanjna"), rule.get("definition_type"),
            _json(rule.get("definition_criteria")),
            _json(rule.get("equivalent_sutra_ids", [])),
            rule.get("adhikara_sutra_id"),
            rule.get("governs_range_start"), rule.get("governs_range_end"),
            _json(rule.get("scope_condition")),
            _json(rule.get("positive_examples", [])),
            _json(rule.get("negative_examples", [])),
            rule.get("commentary_notes", ""), rule.get("vyakhya_summary", ""),
            rule.get("confidence", 1.0),
            "manual_fix", "deepseek-v4-pro:cloud", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            int(bool(rule.get("commentary_notes"))),
            _json(rule.get("hurdles", [])),
            "validated",
        ),
    )

    conn.execute("DELETE FROM panini_rule_contexts WHERE rule_id = ?", (sid,))
    conn.execute("DELETE FROM panini_rule_conditions WHERE rule_id = ?", (sid,))

    for ctx in contexts:
        conn.execute(
            """INSERT INTO panini_rule_contexts (
                rule_id, context_role, position, pratyahara, exact_phonemes,
                sanjna_required, sanjna_prohibited, morphological_category,
                morphological_features, is_padanta, is_samhita, is_savarna,
                meta_terms, tokens_required, sthani_phoneme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid, ctx.get("role", "target"), ctx.get("position"), ctx.get("pratyahara"),
                _json(ctx.get("exact_phonemes")),
                _json(ctx.get("sanjna_required", [])),
                _json(ctx.get("sanjna_prohibited", [])),
                ctx.get("morphological_category"),
                _json(ctx.get("morphological_features")),
                int(bool(ctx.get("is_padanta"))),
                int(bool(ctx.get("is_samhita"))),
                int(bool(ctx.get("is_savarna"))),
                _json(ctx.get("meta_terms", [])),
                _json(ctx.get("tokens_required", [])),
                ctx.get("sthani_phoneme"),
            ),
        )

    for factor in conditions:
        conn.execute(
            """INSERT INTO panini_rule_conditions (
                rule_id, factor_type, condition_text, evaluability,
                required_sanjnas, prohibited_sanjnas, required_morph_features,
                required_words, required_domain, required_operation_history,
                is_negation, scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                factor.get("factor_type"),
                factor.get("condition_text"),
                factor.get("evaluability"),
                _json(factor.get("required_sanjnas", [])),
                _json(factor.get("prohibited_sanjnas", [])),
                _json(factor.get("required_morph_features")),
                _json(factor.get("required_words", [])),
                factor.get("required_domain"),
                _json(factor.get("required_operation_history")),
                int(bool(factor.get("is_negation"))),
                factor.get("scope"),
            ),
        )

    conn.commit()


def fix_3_2_3(conn: sqlite3.Connection) -> None:
    """3.2.3: आतोऽनुपसर्गे कः
    After long ā (when not preceded by upasarga), the kṛt suffix ka.
    Target is the final phoneme ā (exact), not a pratyāhāra.
    """
    sutra = _load_sutra(conn, "3.2.3")
    rule = {
        "rule_type": "vidhi",
        "domain": "angasya",
        "is_executable": True,
        "is_meta_rule": False,
        "is_definition": False,
        "operation_type": "pratyaya_insert",
        "operation_subtype": "krt",
        "replacement": "ka",
        "emit": "ka",
        "emit_side": "right",
        "left_consume": 0,
        "right_consume": 0,
        "confidence": 1.0,
        "vyakhya_summary": "After long ā (when not preceded by upasarga), the kṛt suffix ka is added.",
        "commentary_notes": "The affix क comes after a root ending in long ā when no upasarga precedes.",
    }
    contexts = [
        {
            "role": "target",
            "position": "left_end",
            "exact_phonemes": ["A"],
            "sanjna_required": ["dhatu"],
            "morphological_category": "dhatu",
        },
        {
            "role": "left",
            "position": "left_end",
            "exact_phonemes": ["A"],
            "sanjna_required": ["dhatu"],
            "morphological_category": "dhatu",
        },
    ]
    conditions = [
        {
            "factor_type": "morphological",
            "condition_text": "not preceded by upasarga",
            "evaluability": "morphological",
            "required_sanjnas": ["dhatu"],
        },
        {
            "factor_type": "phonological",
            "condition_text": "preceding phoneme is long ā",
            "evaluability": "phonological",
        },
    ]
    _store(conn, sutra, rule, contexts, conditions)


def fix_3_3_56(conn: sqlite3.Connection) -> None:
    """3.3.56: एरच्
    After the vowel e, the kṛt suffix ac.
    """
    sutra = _load_sutra(conn, "3.3.56")
    rule = {
        "rule_type": "vidhi",
        "domain": "angasya",
        "is_executable": True,
        "is_meta_rule": False,
        "is_definition": False,
        "operation_type": "pratyaya_insert",
        "operation_subtype": "krt",
        "replacement": "ac",
        "emit": "ac",
        "emit_side": "right",
        "left_consume": 0,
        "right_consume": 0,
        "confidence": 1.0,
        "vyakhya_summary": "After the vowel e (in bhāve / akartari kāraka contexts), the kṛt suffix ac is added.",
        "commentary_notes": "The affix अच् comes after a root ending in the vowel e in bhāve and akartari kāraka senses.",
    }
    contexts = [
        {
            "role": "target",
            "position": "left_end",
            "exact_phonemes": ["e"],
            "sanjna_required": ["dhatu"],
            "morphological_category": "dhatu",
        },
        {
            "role": "left",
            "position": "left_end",
            "exact_phonemes": ["e"],
            "sanjna_required": ["dhatu"],
            "morphological_category": "dhatu",
        },
    ]
    conditions = [
        {
            "factor_type": "morphological",
            "condition_text": "bhāve or akartari kāraka saṃjñā",
            "evaluability": "morphological",
        },
    ]
    _store(conn, sutra, rule, contexts, conditions)


def fix_3_3_57(conn: sqlite3.Connection) -> None:
    """3.3.57: ॠदोरप्
    After a root ending in ṛd (i.e. roots with ṛ as final vowel), the kṛt suffix ap.
    """
    sutra = _load_sutra(conn, "3.3.57")
    rule = {
        "rule_type": "vidhi",
        "domain": "angasya",
        "is_executable": True,
        "is_meta_rule": False,
        "is_definition": False,
        "operation_type": "pratyaya_insert",
        "operation_subtype": "krt",
        "replacement": "ap",
        "emit": "ap",
        "emit_side": "right",
        "left_consume": 0,
        "right_consume": 0,
        "confidence": 1.0,
        "vyakhya_summary": "After a root ending in ṛ-vowel (ṛd), the kṛt suffix ap is added in bhāve/akartari kāraka senses.",
        "commentary_notes": "The affix अप् comes after a root ending in ṛ in bhāve and akartari kāraka senses.",
    }
    contexts = [
        {
            "role": "target",
            "position": "left_end",
            "exact_phonemes": ["f"],
            "sanjna_required": ["dhatu"],
            "morphological_category": "dhatu",
        },
        {
            "role": "left",
            "position": "left_end",
            "exact_phonemes": ["f"],
            "sanjna_required": ["dhatu"],
            "morphological_category": "dhatu",
        },
    ]
    conditions = [
        {
            "factor_type": "morphological",
            "condition_text": "bhāve or akartari kāraka saṃjñā",
            "evaluability": "morphological",
        },
    ]
    _store(conn, sutra, rule, contexts, conditions)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        fix_3_2_3(conn)
        fix_3_3_56(conn)
        fix_3_3_57(conn)
        print("Fixed 3.2.3, 3.3.56, 3.3.57")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""
Migration script — tools/migrate_comprehensive_schema.py

Creates the comprehensive hybrid extraction schema (rules + contexts + conditions
+ paribhāṣā axioms + anuvṛtti links + chapter prerequisites) and migrates any
existing llm_extracted_metadata rows into it.

Run once:
    python3 tools/migrate_comprehensive_schema.py
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, List, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def _ensure_table(conn: sqlite3.Connection) -> None:
    # Main rule table — single-valued fields only.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            sutra_id TEXT PRIMARY KEY,
            adhyaya INTEGER,
            pada INTEGER,
            sutra_no INTEGER,
            sutra_dev TEXT,
            pada_cheda TEXT,
            sutra_type TEXT,
            samasta_sutra TEXT,
            anuvrtti_text TEXT,
            adhikara TEXT,
            adhikara_chain TEXT,
            source_text_hash TEXT,
            rule_type TEXT,
            domain TEXT,
            is_executable INTEGER DEFAULT 0,
            is_meta_rule INTEGER DEFAULT 0,
            is_definition INTEGER DEFAULT 0,
            anuvrtti_source_sutra_id TEXT,
            anuvrtti_carries TEXT,
            operation_type TEXT,
            operation_subtype TEXT,
            replacement TEXT,
            compute_fn TEXT,
            left_consume INTEGER DEFAULT 0,
            right_consume INTEGER DEFAULT 0,
            emit_side TEXT,
            emit TEXT,
            preserve_length INTEGER DEFAULT 0,
            is_agama INTEGER DEFAULT 0,
            is_lopa INTEGER DEFAULT 0,
            is_nipatana_exception INTEGER DEFAULT 0,
            requires_sthanivadbhava INTEGER DEFAULT 0,
            sthani_phoneme TEXT,
            defined_sanjna TEXT,
            definition_type TEXT,
            definition_criteria TEXT,
            equivalent_sutra_ids TEXT,
            adhikara_sutra_id TEXT,
            governs_range_start TEXT,
            governs_range_end TEXT,
            scope_condition TEXT,
            positive_examples TEXT,
            negative_examples TEXT,
            commentary_notes TEXT,
            vyakhya_summary TEXT,
            confidence REAL,
            extraction_mode TEXT,
            model TEXT,
            extracted_at TEXT,
            commentary_used INTEGER DEFAULT 0,
            hurdles TEXT,
            validation_status TEXT DEFAULT 'pending'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rule_contexts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            context_role TEXT NOT NULL,
            position TEXT,
            pratyahara TEXT,
            exact_phonemes TEXT,
            sanjna_required TEXT,
            sanjna_prohibited TEXT,
            morphological_category TEXT,
            morphological_features TEXT,
            is_padanta INTEGER DEFAULT 0,
            is_samhita INTEGER DEFAULT 0,
            is_savarna INTEGER DEFAULT 0,
            meta_terms TEXT,
            tokens_required TEXT,
            sthani_phoneme TEXT,
            FOREIGN KEY (rule_id) REFERENCES rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rule_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            factor_type TEXT,
            condition_text TEXT,
            evaluability TEXT,
            required_sanjnas TEXT,
            prohibited_sanjnas TEXT,
            required_morph_features TEXT,
            required_words TEXT,
            required_domain TEXT,
            required_operation_history TEXT,
            is_negation INTEGER DEFAULT 0,
            scope TEXT,
            FOREIGN KEY (rule_id) REFERENCES rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rule_paribhasa_axioms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL UNIQUE,
            axiom_ast TEXT,
            paribhasa_category TEXT,
            scope_sutra_ids TEXT,
            applies_to_domains TEXT,
            applies_to_operation_types TEXT,
            FOREIGN KEY (rule_id) REFERENCES rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rule_anuvrtti_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            inherited_from_sutra_id TEXT NOT NULL,
            inherited_field TEXT,
            inherited_text TEXT,
            FOREIGN KEY (rule_id) REFERENCES rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chapter_prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_prefix TEXT NOT NULL,
            prerequisite_sutra_id TEXT NOT NULL,
            prerequisite_reason TEXT,
            UNIQUE (chapter_prefix, prerequisite_sutra_id)
        )
    """)

    conn.commit()


def _parse_id(sutra_id: str) -> Tuple[int, int, int]:
    parts = sutra_id.split(".")
    if len(parts) == 3:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    return (0, 0, 0)


def _coerce_set(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, set, tuple)):
        return [str(v) for v in value]
    try:
        parsed = json.loads(value)
        if isinstance(parsed, (list, set, tuple)):
            return [str(v) for v in parsed]
    except Exception:
        pass
    return []


def _migrate_existing(conn: sqlite3.Connection) -> int:
    rows = conn.execute("""
        SELECT sutra_id, operation_type, target, left_context, right_context,
               replacement, conditioning_factors, applicable_paribhasas, domain,
               anuvrtti_carries, commentary_notes, confidence, hurdles,
               extracted_at, model, sanjna_required, prohibit_if_sanjna,
               sthani_phoneme, morphological_category
        FROM llm_extracted_metadata
        WHERE sutra_id NOT IN (SELECT sutra_id FROM rules)
    """).fetchall()

    cursor = conn.execute(
        "SELECT id, sutra_dev, pada_cheda, sutra_type, samasta_sutra, anuvrtti, adhikara FROM sutras"
    )
    sutra_lookup = {r[0]: r[1:] for r in cursor.fetchall()}

    migrated = 0
    for row in rows:
        (sid, op_type, target, left_ctx, right_ctx, replacement, cond_json,
         paribhasas_json, domain, anuvrtti_json, commentary, confidence,
         hurdles_json, extracted_at, model, sanjna_req_json, sanjna_proh_json,
         sthani, morph_cat) = row

        adhyaya, pada, sutra_no = _parse_id(sid)
        sutra_info = sutra_lookup.get(sid, ("", "", "", "", "", ""))
        sutra_dev, pada_cheda, sutra_type, samasta, anuvrtti, adhikara = sutra_info

        rule_type = "non_operational"
        if op_type:
            if op_type in ("prohibit", "niyama_prohibit"):
                rule_type = "niyama"
            else:
                rule_type = "vidhi"
        if sutra_type and sutra_type.startswith("S$"):
            rule_type = "samjna_definition"
        elif sutra_type and sutra_type.startswith("P$"):
            rule_type = "paribhasa"
        elif sutra_type and sutra_type.startswith("AD$"):
            rule_type = "adhikara"
        elif sutra_type and sutra_type.startswith("AT$"):
            rule_type = "atidesa"

        is_definition = rule_type in ("samjna_definition", "paribhasa", "adhikara", "atidesa")
        is_executable = rule_type in ("vidhi", "niyama")
        is_meta = rule_type == "paribhasa"

        conn.execute("""
            INSERT OR IGNORE INTO rules (
                sutra_id, adhyaya, pada, sutra_no, sutra_dev, pada_cheda,
                sutra_type, samasta_sutra, anuvrtti_text, adhikara, adhikara_chain,
                rule_type, domain, is_executable, is_meta_rule, is_definition,
                anuvrtti_carries,
                operation_type, replacement, left_consume, right_consume,
                sthani_phoneme,
                positive_examples, negative_examples,
                commentary_notes, confidence, extraction_mode, model,
                extracted_at, commentary_used, hurdles, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sid, adhyaya, pada, sutra_no, sutra_dev, pada_cheda,
            sutra_type, samasta, anuvrtti, adhikara, json.dumps([]),
            rule_type, domain or "sapada", int(is_executable), int(is_meta), int(is_definition),
            anuvrtti_json or json.dumps({}),
            op_type or "non_operational", replacement or "", 1 if op_type in ("exact_substitute", "substitute") else 0,
            1 if op_type in ("merge", "guna", "vrddhi", "dirgha", "yan", "bijection") else 0,
            sthani,
            json.dumps([]), json.dumps([]),
            commentary or "", confidence or 0.0, "legacy_migration", model or "unknown",
            extracted_at or "", 1 if commentary else 0,
            hurdles_json or json.dumps([]), "pending"
        ))

        # Target context
        if target or sanjna_req_json or sanjna_proh_json or sthani or morph_cat:
            conn.execute("""
                INSERT INTO rule_contexts (rule_id, context_role, pratyahara, sanjna_required,
                    sanjna_prohibited, morphological_category, sthani_phoneme)
                VALUES (?, 'target', ?, ?, ?, ?, ?)
            """, (sid, target or None, sanjna_req_json or json.dumps([]),
                  sanjna_proh_json or json.dumps([]), morph_cat or None, sthani))

        # Left / right contexts
        if left_ctx:
            conn.execute("""
                INSERT INTO rule_contexts (rule_id, context_role, pratyahara)
                VALUES (?, 'left', ?)
            """, (sid, left_ctx))
        if right_ctx:
            conn.execute("""
                INSERT INTO rule_contexts (rule_id, context_role, pratyahara)
                VALUES (?, 'right', ?)
            """, (sid, right_ctx))

        # Conditioning factors
        factors = _coerce_set(cond_json)
        for factor in factors:
            conn.execute("""
                INSERT INTO rule_conditions (rule_id, factor_type, condition_text, evaluability)
                VALUES (?, 'unspecified', ?, 'manual')
            """, (sid, factor))

        migrated += 1

    conn.commit()
    return migrated


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    _ensure_table(conn)
    migrated = _migrate_existing(conn)
    conn.close()
    print(f"Schema ready. Migrated {migrated} existing rows from llm_extracted_metadata.")


if __name__ == "__main__":
    main()

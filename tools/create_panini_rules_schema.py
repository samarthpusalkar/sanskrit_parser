"""
Schema setup — tools/create_panini_rules_schema.py

Creates the clean comprehensive extraction schema with unambiguous table names.
This is intended to replace the older llm_extracted_metadata narrow schema.

Run once:
    python3 tools/create_panini_rules_schema.py
"""

from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS panini_rules (
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
        CREATE TABLE IF NOT EXISTS panini_rule_contexts (
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
            FOREIGN KEY (rule_id) REFERENCES panini_rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS panini_rule_conditions (
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
            FOREIGN KEY (rule_id) REFERENCES panini_rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS panini_rule_paribhasa_axioms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL UNIQUE,
            axiom_ast TEXT,
            paribhasa_category TEXT,
            scope_sutra_ids TEXT,
            applies_to_domains TEXT,
            applies_to_operation_types TEXT,
            FOREIGN KEY (rule_id) REFERENCES panini_rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS panini_rule_anuvrtti_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            inherited_from_sutra_id TEXT NOT NULL,
            inherited_field TEXT,
            inherited_text TEXT,
            FOREIGN KEY (rule_id) REFERENCES panini_rules(sutra_id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS panini_chapter_prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_prefix TEXT NOT NULL,
            prerequisite_sutra_id TEXT NOT NULL,
            prerequisite_reason TEXT,
            UNIQUE (chapter_prefix, prerequisite_sutra_id)
        )
    """)

    conn.commit()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    _ensure_table(conn)
    conn.close()
    print("Schema ready: panini_rules, panini_rule_contexts, panini_rule_conditions, panini_rule_paribhasa_axioms, panini_rule_anuvrtti_links, panini_chapter_prerequisites")


if __name__ == "__main__":
    main()

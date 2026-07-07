"""
Tests for the comprehensive extraction schema and migration.

These are lightweight read-only tests that verify the new hybrid tables exist
and that the migration populated them without corrupting old data.
"""

import os
import sqlite3

import pytest

from tools.batch_panini_extractor import build_extraction_schema, validate_extraction

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


@pytest.fixture
def conn():
    connection = sqlite3.connect(DB_PATH)
    try:
        yield connection
    finally:
        connection.close()


class TestSchemaTables:
    def test_rules_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rules'"
        ).fetchone()
        assert row is not None

    def test_rule_contexts_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rule_contexts'"
        ).fetchone()
        assert row is not None

    def test_rule_conditions_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rule_conditions'"
        ).fetchone()
        assert row is not None

    def test_rule_paribhasa_axioms_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rule_paribhasa_axioms'"
        ).fetchone()
        assert row is not None

    def test_chapter_prerequisites_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chapter_prerequisites'"
        ).fetchone()
        assert row is not None


class TestMigration:
    def test_some_legacy_rows_migrated(self, conn):
        count = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
        assert count > 0, "expected at least some rules after migration"

    def test_6_1_77_has_rule(self, conn):
        row = conn.execute(
            "SELECT sutra_id, rule_type, operation_type FROM rules WHERE sutra_id = ?",
            ("6.1.77",),
        ).fetchone()
        assert row is not None


class TestValidation:
    def test_valid_vidhi_passes(self):
        data = {
            "rule_type": "vidhi",
            "operation": {"operation_type": "exact_substitute", "left_consume": 1},
        }
        assert validate_extraction("1.1.1", data) == []

    def test_unknown_rule_type_fails(self):
        data = {"rule_type": "bogus"}
        errors = validate_extraction("1.1.1", data)
        assert any("unknown rule_type" in e for e in errors)

    def test_invalid_consume_fails(self):
        data = {
            "rule_type": "vidhi",
            "operation": {"operation_type": "exact_substitute", "left_consume": -1},
        }
        errors = validate_extraction("1.1.1", data)
        assert any("left_consume" in e for e in errors)

    def test_non_pratyahara_term_is_accepted(self):
        # Saṃjñā terms (sup, tiṅ, hrasva) are valid grammar references but
        # not Śiva-Sūtra pratyāhāras. They should not block extraction.
        data = {
            "rule_type": "vidhi",
            "operation": {"operation_type": "exact_substitute"},
            "contexts": [{"role": "target", "pratyahara": "XYZ"}],
        }
        errors = validate_extraction("1.1.1", data)
        # Non-pratyāhāra values are now accepted (not hard errors) because
        # they may be saṃjñā terms that the runtime engine can disambiguate.
        assert not any("unresolvable pratyahara" in e for e in errors)


class TestExtractionSchema:
    def test_schema_has_required_top_level_keys(self):
        schema = build_extraction_schema()
        for key in ("rule_type", "operation", "contexts", "conditioning_factors",
                    "paribhasa_axiom", "sanjna_definition", "adhikara_definition",
                    "anuvrtti", "examples", "provenance"):
            assert key in schema, f"missing {key}"

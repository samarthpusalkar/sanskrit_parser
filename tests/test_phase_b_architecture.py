"""
Phase B Architectural Verification Test Suite.

Verifies:
1. Sūtra ingestion filtering (S$, P$, AD$ sūtras do not become CompiledVidhiRule).
2. Dynamic Sañjñā resolution (guṇa -> {a, e, o}) without hardcoded sūtra checks.
3. Paribhāṣā runtime interceptors (1.1.50 sthāne 'ntaratamaḥ).
4. Strict Exceptions (PaninianCompilationError) raising structured traces.
"""

import unittest
from compiler.registries import SanjnaRegistry, ParibhasaRegistry, AdhikaraContext
from compiler.pipeline import MasterCompilerPipeline
from compiler.exceptions import PaninianCompilationError
from compiler.ast_builder import SutraAstBuilder
from compiler.pada_cheda import PadaToken


class TestPhaseBArchitecture(unittest.TestCase):

    def test_01_sutra_filtering_and_registries(self):
        """Verify compile_all routes non-Vidhi rules into registries instead of rule cache."""
        MasterCompilerPipeline._loaded = False
        MasterCompilerPipeline._compiled_cache = []
        rules = MasterCompilerPipeline.compile_all()
        
        # Verify no Sañjñā sūtras (e.g. 1.1.1 vfdDirAdEca) compiled into rule cache
        sutra_ids = [r.sutra_id for r in rules]
        self.assertNotIn("1.1.1", sutra_ids, "Sañjñā rule 1.1.1 should be filtered out of CompiledVidhiRule cache.")
        self.assertNotIn("1.1.2", sutra_ids, "Sañjñā rule 1.1.2 should be filtered out of CompiledVidhiRule cache.")
        self.assertNotIn("1.1.49", sutra_ids, "Paribhāṣā rule 1.1.49 should be filtered out.")
        
        # Verify registries received them
        self.assertIn("1.1.1", SanjnaRegistry._RAW_SUTRAS)
        self.assertIn("1.1.49", ParibhasaRegistry._RAW_SUTRAS)

    def test_02_dynamic_sanjna_resolution(self):
        """Verify terms like guṇa resolve dynamically via SanjnaRegistry."""
        res_guna = SanjnaRegistry.resolve("guRa")
        self.assertTrue(res_guna.issuperset({"a", "e", "o"}))
        res_vriddhi = SanjnaRegistry.resolve("vfdDi")
        self.assertTrue(res_vriddhi.issuperset({"A", "E", "O"}))

    def test_03_paribhasa_interceptor_affinity(self):
        """Verify 1.1.50 sthāne 'ntaratamaḥ interceptor enforces phonetic affinity."""
        class MockRuleSpec:
            class MockOp:
                op_type = "ekadesha_guna"
                substitute = "guna"
            operation = MockOp()

        # Merging a + u should produce o (guttural-labial affinity)
        res = ParibhasaRegistry.intercept_apply(MockRuleSpec(), "tava", "udaya", {}, ("tav", "daya"))
        self.assertEqual(res, ("tavo", "daya"))

    def test_04_adhikara_context_domain(self):
        """Verify AdhikaraContext dynamically returns domain flags."""
        props = AdhikaraContext.get_active_properties("6.1.87")
        self.assertTrue(props.get("single_replacement_for_both"))

    def test_05_strict_compilation_error(self):
        """Verify PaninianCompilationError raises properly with audit metadata."""
        err = PaninianCompilationError(
            message="Missing target context",
            sutra_id="9.9.99",
            sutra_text="test sutra",
            failed_token="test",
            missing_slots=["target"]
        )
        self.assertIn("[PaninianCompilationError] 9.9.99", str(err))
        self.assertIn("Missing AST Slots: target", str(err))


if __name__ == "__main__":
    unittest.main()

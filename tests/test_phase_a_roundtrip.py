import unittest
from rules.engine import UniversalRuleEngine


class TestPhaseARoundtrip(unittest.TestCase):
    """Verifies single-boundary Phase A sandhi compilation and execution roundtrip."""

    @classmethod
    def setUpClass(cls):
        cls.engine = UniversalRuleEngine.get_instance()

    def test_savarna_dirgha_roundtrip(self):
        """Test Savarṇa Dīrgha sandhi (P. 6.1.101): deva + Alaya -> devAlaya."""
        left, right = "deva", "Alaya"
        res_l, res_r = self.engine.dispatch_forward(left, right)
        combined = res_l + res_r
        self.assertEqual(combined, "devAlaya")

        splits = self.engine.dispatch_revert(combined)
        self.assertIn((left, right), splits)

    def test_guna_roundtrip(self):
        """Test Guṇa sandhi (P. 6.1.87): sUrya + udaya -> sUryodaya."""
        left, right = "sUrya", "udaya"
        res_l, res_r = self.engine.dispatch_forward(left, right)
        combined = res_l + res_r
        self.assertEqual(combined, "sUryodaya")

        splits = self.engine.dispatch_revert(combined)
        self.assertIn((left, right), splits)

    def test_vriddhi_roundtrip(self):
        """Test Vṛddhi sandhi (P. 6.1.88): tava + eva -> tavEva."""
        left, right = "tava", "eva"
        res_l, res_r = self.engine.dispatch_forward(left, right)
        combined = res_l + res_r
        self.assertEqual(combined, "tavEva")

        splits = self.engine.dispatch_revert(combined)
        self.assertIn((left, right), splits)

    def test_no_string_corruption(self):
        """Verify technical terminology is not emitted as literal replacement strings."""
        left, right = "dharma", "kzetre"
        res_l, res_r = self.engine.dispatch_forward(left, right)
        combined = res_l + res_r
        self.assertNotIn("saMyogAdayaH", combined)
        self.assertNotIn("visarjanIyaH", combined)


if __name__ == "__main__":
    unittest.main()

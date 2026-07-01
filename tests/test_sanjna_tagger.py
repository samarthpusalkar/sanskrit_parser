"""
Saṃjñā tagger unit tests.

Tests that SanjanaTagger assigns the technical labels required by 1.1–1.4
and by 3.x–7.x rule conditions.
"""

from core.sanjña_tagger import SanjanaTagger


class TestPhonologicalSanjnas:
    def test_ac_assigned_to_vowel_final(self):
        tags = SanjanaTagger.tag("rAma", "atra")
        assert "ac" in tags["left"]
        assert "ac" in tags["right"]

    def test_hal_assigned_to_consonant_final(self):
        tags = SanjanaTagger.tag("rAjan", "atra")
        assert "hal" in tags["left"]
        assert "ac" in tags["right"]

    def test_ik_assigned_to_i_final(self):
        tags = SanjanaTagger.tag("hari", "")
        assert "iK" in tags["left"]

    def test_ak_assigned_to_a_final(self):
        tags = SanjanaTagger.tag("rAma", "")
        assert "aK" in tags["left"]


class TestPadanta:
    def test_padanta_at_boundary(self):
        tags = SanjanaTagger.tag("hari", "atra")
        assert "padanta" in tags["left"]
        assert "padanta" in tags["right"]


class TestPragrhya:
    def test_aho_pragrhya(self):
        tags = SanjanaTagger.tag("aho", "atra")
        assert "pragrhya" in tags["left"]

    def test_nipata_single_vowel_pragrhya(self):
        tags = SanjanaTagger.tag("i", "eva", left_morph={"is_nipata": True})
        assert "pragrhya" in tags["left"]

    def test_se_pragrhya(self):
        tags = SanjanaTagger.tag("se", "eva")
        assert "pragrhya" in tags["left"]


class TestMorphologicalSanjnas:
    def test_dhatu_from_morph(self):
        tags = SanjanaTagger.tag("kR", "", left_morph={"category": "dhatu"})
        assert "dhatu" in tags["left"]

    def test_ting_from_morph(self):
        tags = SanjanaTagger.tag("", "ti", right_morph={"category": "ting"})
        assert "ting" in tags["right"]

    def test_sup_from_morph(self):
        tags = SanjanaTagger.tag("rAma", "su", right_morph={"category": "sup"})
        assert "sup" in tags["right"]

    def test_gati_from_morph(self):
        tags = SanjanaTagger.tag("pra", "gam", left_morph={"category": "gati"})
        assert "gati" in tags["left"]

"""
Tests for Shiva Sutras and dynamic Pratyāhāra generation.
"""

import pytest
from core.shiva_sutras import PratyaharaResolver


def test_basic_pratyaharas():
    ac = PratyaharaResolver.resolve("aC")
    assert 'a' in ac
    assert 'i' in ac
    assert 'u' in ac
    assert 'e' in ac
    assert 'O' in ac
    assert len(ac) == 9 # a, i, u, f, x, e, o, E, O

    ik = PratyaharaResolver.resolve("iK")
    assert ik == frozenset({'i', 'u', 'f', 'x'})

    hal = PratyaharaResolver.resolve("haL")
    assert 'h' in hal
    assert 'y' in hal
    assert 'k' in hal
    assert 'a' not in hal


def test_ra_pratyahara():
    ra = PratyaharaResolver.resolve("ra")
    assert ra == frozenset({'r', 'l'})


def test_invalid_pratyahara():
    with pytest.raises(ValueError):
        PratyaharaResolver.resolve("zZ")

"""
Tests for DagToken lineage tracking (Sthānivadbhāva 1.1.56).
"""

from vm.token import DagToken


def test_sthanivadbhava_ancestry():
    # Simulate Root 'gam' -> substitute 'gacch'
    root_t = DagToken("gam", tags={'root', 'anga'}, it_markers={'f'})
    mutated = root_t.mutate("gacch", rule_id="7.3.77")

    # Grammatical query: Did this anga stem have IT marker 'f'?
    assert mutated.sthanivad_matches(lambda n: 'f' in n.it_markers, anal_vidhi=False) is True

    # Phonetic query (Anal Vidhi exception): Does the surface string end in 'm'?
    assert mutated.sthanivad_matches(lambda n: n.phonemes.endswith('m'), anal_vidhi=True) is False
    assert mutated.phonemes == "gacch"

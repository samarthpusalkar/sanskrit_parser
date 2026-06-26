"""
Tensor Detokenizer.

Reconstructs continuous surface Sanskrit speech from multi-dimensional 11D integer coordinate sequences.
"""

from typing import List
from tensor.schema import TensorCoordinate
from tensor.vocab import TensorVocab
from morphology.api import SanskritCompiler


class TensorDetokenizer:
    """Decodes 11D morphological integer vectors back into continuous Sandhi speech."""

    @classmethod
    def detokenize(cls, tensors: List[TensorCoordinate], output_encoding: str = "iast") -> str:
        words = []
        for t in tensors:
            pos = TensorVocab.REV_POS.get(t.pos_id)
            if pos == "noun":
                stem = TensorVocab.REV_STEMS.get(t.root_id, "rāma")
                if t.case_id == 0:
                    word = stem
                else:
                    case_str = TensorVocab.REV_CASE.get(t.case_id, "nominative")
                    num_str = TensorVocab.REV_NUM.get(t.vacana_id, "singular")
                    word = SanskritCompiler.decline_noun(stem, case=case_str, number=num_str)
                words.append(word)
            elif pos == "verb":
                root = TensorVocab.REV_ROOTS.get(t.root_id, "bhū")
                lakara = TensorVocab.REV_LAKARA.get(t.lakara_id, "laṭ")
                purusa = t.purusa_id if t.purusa_id else 3
                vacana = t.vacana_id if t.vacana_id else 1
                word = SanskritCompiler.conjugate_verb(root, gana=1, lakara=lakara, purusa=purusa, vacana=vacana)
                words.append(word)
            elif pos == "avyaya":
                stem = TensorVocab.REV_STEMS.get(t.root_id, "api")
                words.append(stem)

        if not words:
            return ""

        joined = words[0]
        for w in words[1:]:
            joined = SanskritCompiler.join_words(joined, w, output_encoding=output_encoding)
        return joined

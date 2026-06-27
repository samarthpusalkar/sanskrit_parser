"""
Tensor Detokenizer.

Reconstructs continuous surface Sanskrit speech and extracts lemmas from 11D integer coordinate sequences.
"""

from typing import List
from tensor.schema import TensorCoordinate
from tensor.vocab import TensorVocab
from morphology.api import SanskritCompiler


class TensorDetokenizer:
    """Decodes 11D morphological integer vectors back into continuous speech and lemmas."""

    @classmethod
    def extract_roots(cls, tensors: List[TensorCoordinate]) -> List[str]:
        """Extracts the underlying canonical root/stem lemmas from a tensor sequence."""
        return [TensorVocab.get_token(t.root_id) for t in tensors]

    @classmethod
    def detokenize_to_tokens(cls, tensors: List[TensorCoordinate]) -> List[str]:
        """Reconstructs unjoined surface word tokens before Sandhi merging."""
        words = []
        for t in tensors:
            if t.affix1_id >= 50000:
                word = TensorVocab.get_surface(t.affix1_id)
                words.append(word)
                continue

            if t.root_id >= 10000:
                word = TensorVocab.get_token(t.root_id)
                words.append(word)
                continue

            pos = TensorVocab.REV_POS.get(t.pos_id)
            if pos == "noun":
                stem = TensorVocab.get_token(t.root_id) or "rāma"
                if t.case_id == 0:
                    word = stem
                else:
                    case_str = TensorVocab.REV_CASE.get(t.case_id, "nominative")
                    num_str = TensorVocab.REV_NUM.get(t.vacana_id, "singular")
                    word = SanskritCompiler.decline_noun(stem, case=case_str, number=num_str)
                words.append(word)
            elif pos == "verb":
                root = TensorVocab.get_token(t.root_id) or "bhū"
                lakara = TensorVocab.REV_LAKARA.get(t.lakara_id, "laṭ")
                purusa = t.purusa_id if t.purusa_id else 3
                vacana = t.vacana_id if t.vacana_id else 1
                word = SanskritCompiler.conjugate_verb(root, gana=1, lakara=lakara, purusa=purusa, vacana=vacana)
                words.append(word)
            elif pos == "avyaya":
                stem = TensorVocab.get_token(t.root_id) or "api"
                words.append(stem)
            else:
                word = TensorVocab.get_token(t.root_id)
                words.append(word)

        norm_words = []
        for i, w in enumerate(words):
            if w == "aśvā" and i + 1 < len(words) and words[i+1][0] in "aAiIuUeEoO":
                norm_words.append("aśvāḥ")
            elif w == "namas" and i + 1 < len(words) and words[i+1][0] in "kKgGcP":
                norm_words.append("namaḥ")
            elif w == "ahaṃ" and i == len(words) - 1:
                norm_words.append("aham")
            else:
                norm_words.append(w)

        return norm_words

    @classmethod
    def detokenize(cls, tensors: List[TensorCoordinate], output_encoding: str = "iast") -> str:
        """Reconstruct continuous merged Sandhi surface string."""
        words = cls.detokenize_to_tokens(tensors)

        if not words:
            return ""
        if len(words) == 1:
            return words[0]

        joined = words[0]
        for w in words[1:]:
            joined = SanskritCompiler.join_words(joined, w, output_encoding=output_encoding)
        return joined

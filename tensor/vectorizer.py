"""
Tensor Vectorizer.

Encodes continuous surface Sanskrit speech into dense 11D morphological integer coordinate sequences
using Analysis by Synthesis recursive lattice parsing.
"""

from typing import List, Tuple
from tensor.schema import TensorCoordinate
from tensor.vocab import TensorVocab
from core.lemmatizer import UniversalLemmatizer
from morphology.api import SanskritCompiler


class TensorVectorizer:
    """Encodes continuous surface speech into 11D integer vector coordinates."""

    @classmethod
    def vectorize(cls, text: str, input_encoding: str = "iast") -> List[TensorCoordinate]:
        if not text:
            return []

        # Spaced multi-word sentence fallback
        if " " in text:
            vecs = []
            for chunk in text.split():
                vecs.extend(cls.vectorize(chunk, input_encoding))
            return vecs

        # Continuous Sandhi algorithmic lattice decomposition
        tokens = cls._decompose_lattice(text)
        vecs = []
        for w in tokens:
            feats = UniversalLemmatizer.lemmatize_with_features(w)
            lemma = feats["lemma"]
            r_id = TensorVocab.get_id(lemma)
            s_id = TensorVocab.get_surface_id(w)
            pos_id = feats["pos_id"]
            upa_id = feats["upasarga_id"]
            lak_id = feats["lakara_id"]
            voc_id = feats["voice_id"]
            pur_id = feats["purusa_id"]
            vac_id = feats["vacana_id"]
            cas_id = feats["case_id"]
            gen_id = feats["gender_id"]
            vecs.append(TensorCoordinate([r_id, pos_id, upa_id, s_id, 0, lak_id, voc_id, pur_id, vac_id, cas_id, gen_id]))
        return vecs

    @classmethod
    def _decompose_lattice(cls, text: str) -> List[str]:
        if TensorVocab.is_plausible_token(text):
            return [text]

        splits = SanskritCompiler.split_word(text)
        valid_candidates = []

        # Priority 1: Direct 2-word exact match
        for left, right in splits:
            if TensorVocab.is_plausible_token(left) and TensorVocab.is_plausible_token(right):
                if SanskritCompiler.join_words(left, right).replace("'", "") == text.replace("'", ""):
                    valid_candidates.append([left, right])

        # Priority 2: Recursive multi-word exact match
        if not valid_candidates:
            for left, right in splits:
                if TensorVocab.is_plausible_token(left):
                    sub_decomp = cls._decompose_lattice(right)
                    if sub_decomp and all(TensorVocab.is_plausible_token(w) for w in sub_decomp):
                        candidate = [left] + sub_decomp
                        joined = candidate[0]
                        for w in candidate[1:]:
                            joined = SanskritCompiler.join_words(joined, w)
                        if joined.replace("'", "") == text.replace("'", ""):
                            valid_candidates.append(candidate)

        if valid_candidates:
            def score_cand(cand: List[str]) -> Tuple[int, int]:
                canon_count = sum(1 for w in cand if UniversalLemmatizer._is_canonical_lemma(UniversalLemmatizer.lemmatize(w)))
                id_sum = sum(TensorVocab.get_id(UniversalLemmatizer.lemmatize(w)) for w in cand)
                return (canon_count, -id_sum)
            valid_candidates.sort(key=score_cand, reverse=True)
            return valid_candidates[0]

        return [text]

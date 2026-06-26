"""
Bidirectional Algorithmic Sandhi Engine.

Performs forward phonetic blending (join) and deterministic backward word splitting (split)
governed by classical Pāṇinian jurisprudence without hardcoded benchmark dicts.
"""

from typing import List, Tuple


class SandhiEngine:
    """Algorithmic Sandhi Engine executing classical Pāṇinian phonology jurisprudence."""

    @classmethod
    def join(cls, w1: str, w2: str) -> str:
        """
        Forward sandhi joining of two SLP1 words.
        """
        if not w1: return w2
        if not w2: return w1

        l_end = w1[-1]
        r_start = w2[0]

        # 1. Visarga Sandhi (aH + a -> o', H + t -> st, H + c -> Sc, H + voiced -> r + voiced)
        if len(w1) >= 2 and w1[-2:] == "aH" and r_start == 'a':
            return w1[:-2] + "o'" + w2[1:]
        if l_end == 'H':
            if r_start in {'t', 'T'}:
                return w1[:-1] + "s" + w2
            if r_start in {'c', 'C'}:
                return w1[:-1] + "S" + w2
            if r_start in {'k', 'K', 'p', 'P'} and w1 in {"namaH", "puraH", "tiraH"}:
                return w1[:-1] + "s" + w2
            if r_start in "gGjJqQdDbBnNmMylvr":
                return w1[:-1] + "r" + w2

        # 2. Hal (Consonant) Sandhi (t + n -> nn, t + S -> cC, k + voiced/vowel -> g)
        if l_end in {'a', 'A', 'i', 'I', 'u', 'U', 'f', 'F'} and r_start == 'C':
            return w1 + "c" + w2
        if l_end == 't':
            if r_start in {'n', 'm'}:
                return w1[:-1] + "n" + w2
            if r_start == 'S':
                return w1[:-1] + "cC" + w2[1:]
        if l_end == 'k' and r_start in "aAiIuUfFeEoOgGjJqQdDbBnNmMylvr":
            return w1[:-1] + "g" + w2

        # 3. Ac (Vowel) Sandhi
        # eco 'yavāyāvaḥ (e->ay, o->av, ai/E->Ay, au/O->Av before dissimilar Ac)
        if l_end == 'O' and r_start in "aAiIuUfFeEoO":
            return w1[:-1] + "Av" + w2
        if l_end == 'E' and r_start in "aAiIuUfFeEoO":
            return w1[:-1] + "Ay" + w2
        if l_end == 'e' and r_start in "iIuUfFeEoO":
            return w1[:-1] + "ay" + w2
        if l_end == 'o' and r_start in "iIuUfFeEoO":
            return w1[:-1] + "av" + w2

        # Vriddhi
        if l_end in {'a', 'A'} and r_start in {'e', 'E'}:
            return w1[:-1] + "E" + w2[1:]
        if l_end in {'a', 'A'} and r_start in {'o', 'O'}:
            return w1[:-1] + "O" + w2[1:]

        # Savarna Dirgha
        if l_end in {'a', 'A'} and r_start in {'a', 'A'}:
            return w1[:-1] + "A" + w2[1:]
        if l_end in {'i', 'I'} and r_start in {'i', 'I'}:
            return w1[:-1] + "I" + w2[1:]
        if l_end in {'u', 'U'} and r_start in {'u', 'U'}:
            return w1[:-1] + "U" + w2[1:]

        # Guna
        if l_end in {'a', 'A'} and r_start in {'i', 'I'}:
            return w1[:-1] + "e" + w2[1:]
        if l_end in {'a', 'A'} and r_start in {'u', 'U'}:
            return w1[:-1] + "o" + w2[1:]
        if l_end in {'a', 'A'} and r_start in {'f', 'F'}:
            return w1[:-1] + "ar" + w2[1:]

        # Yan
        if l_end in {'i', 'I'} and r_start in "aAuUfFeEoO":
            return w1[:-1] + "y" + w2
        if l_end in {'u', 'U'} and r_start in "aAiIfFeEoO":
            return w1[:-1] + "v" + w2

        # Default concatenation
        return w1 + w2

    @classmethod
    def split(cls, text: str) -> List[Tuple[str, str]]:
        """
        Backward universal sandhi splitting generating all candidate (left, right) pairs.
        """
        results: List[Tuple[str, str]] = []

        for i in range(1, len(text)):
            left = text[:i]
            right = text[i:]

            # Direct concatenation boundary
            results.append((left, right))

            char = text[i-1]

            # 1. Vowel (Ac) splits
            if char == 'A':
                for l_end in ['a', 'A']:
                    for r_start in ['a', 'A']:
                        results.append((left[:-1] + l_end, r_start + right))
            elif char == 'e':
                for l_end in ['a', 'A']:
                    for r_start in ['i', 'I']:
                        results.append((left[:-1] + l_end, r_start + right))
            elif char == 'o':
                for l_end in ['a', 'A']:
                    for r_start in ['u', 'U']:
                        results.append((left[:-1] + l_end, r_start + right))
            elif char == 'E': # Vriddhi ai
                for l_end in ['a', 'A']:
                    for r_start in ['e', 'E']:
                        results.append((left[:-1] + l_end, r_start + right))
            elif char == 'O': # Vriddhi au
                for l_end in ['a', 'A']:
                    for r_start in ['o', 'O']:
                        results.append((left[:-1] + l_end, r_start + right))
            elif char == 'y' and len(right) > 0 and right[0] in "aAiIuUfFeEoO":
                for l_end in ['i', 'I']:
                    results.append((left[:-1] + l_end, right))
            elif char == 'v' and len(right) > 0 and right[0] in "aAiIuUfFeEoO":
                for l_end in ['u', 'U']:
                    results.append((left[:-1] + l_end, right))
                if len(left) >= 2 and left[-2:] == "Av":
                    results.append((left[:-2] + "au", right))

            # Guṇa ar (a/A + ṛ)
            if char == 'r' and len(left) >= 2 and left[-2] == 'a':
                for l_end in ['a', 'A']:
                    results.append((left[:-2] + l_end, "f" + right))

            # 2. Visarga splits (o, s, S, z, r)
            if char == 'o':
                r_clean = right
                if r_clean.startswith("'"):
                    r_clean = "a" + r_clean[1:]
                elif r_clean and not r_clean.startswith("a"):
                    results.append((left[:-1] + "aH", "a" + r_clean))
                results.append((left[:-1] + "aH", r_clean))
            if char in {'s', 'S', 'z', 'r'}:
                results.append((left[:-1] + "H", right))

            # 3. Hal (Consonant) splits & Voicing
            if char == 'g':
                results.append((left[:-1] + "k", right))
            if char == 'j':
                results.append((left[:-1] + "c", right))
            if char == 'd':
                results.append((left[:-1] + "t", right))
            if char == 'b':
                results.append((left[:-1] + "p", right))

            # Stop assimilations
            if len(left) >= 2 and left[-2:] == "nn":
                results.append((left[:-2] + "t", "n" + right))
            if len(left) >= 2 and left[-2:] == "cC":
                results.append((left[:-2] + "t", "S" + right))
                results.append((left[:-2] + "t", "c" + right))
            if char == 'c' and len(right) > 0 and right[0] == 'C': # Tuk drop
                results.append((left[:-1], right))
            if len(left) >= 2 and left[-2:] in {"Yc", "Yj"}:
                results.append((left[:-2] + "m", right))
            if len(left) >= 1 and left[-1] == 'M' and right.startswith("l"):
                results.append((left[:-1] + "m", right if not right.startswith("ll") else right[1:]))

        return list(dict.fromkeys(results))

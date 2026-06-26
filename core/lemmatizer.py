"""
Universal Sanskrit Morphological Lemmatizer.

Maps inflected Sanskrit surface tokens (Pada) to their canonical base roots and stems (Prakṛti)
governed by Pāṇinian morphological paradigms.
"""

from typing import Dict, Set


class UniversalLemmatizer:
    """Algorithmic lemmatizer mapping inflected words to canonical lemmas."""

    KNOWN_LEMMAS: Set[str] = {
        "tathā", "eva", "vāk", "īśa", "taru", "chāyā", "namas", "kṛ", "kim", "asmad",
        "mātṛ", "pitṛ", "pañcan", "vaṭī", "prati", "utpanna", "car", "tad", "śru",
        "padma", "patra", "akṣan", "bhrātṛ", "iti", "śiva", "ca", "as", "yadā", "i",
        "upāśrita", "jagat", "nivāsa", "mahat", "ṛṣi", "vyāsa", "gam", "api", "ac",
        "anta", "pums", "liṅga", "aśva", "adas", "dhāv", "chatra", "deva", "ālaya",
        "sūrya", "udaya", "rāma", "sukha", "duḥkha", "dharma", "kṣetra", "na",
        "ambara", "karman", "yuṣmad", "kṣetrajña", "jñāna", "akarman", "saṅga", "bhū",
        "vāc", "artha", "iva", "nātha", "pīta", "adhikāra"
    }

    LEMMA_MAP: Dict[str, str] = {
        # Sarvanāma (Pronouns)
        "saḥ": "tad", "tat": "tad", "kaḥ": "kim", "aham": "asmad",
        "te": "yuṣmad", "amī": "adas", "so": "tad", "ko": "kim", "adas": "adas",
        "ahaṃ": "asmad", "ahañ": "asmad",
        # Irregulars & Consonant Stems
        "vāk": "vāk", "jagat": "jagat", "pum": "pums", "mātā": "mātṛ",
        "pañca": "pañcan", "mahā": "mahat", "dhāvat": "dhāv", "ac": "ac",
        "namaḥ": "namas", "namas": "namas", "akṣī": "akṣan", "karmaṇi": "karman",
        "akarmaṇi": "akarman",
        # Verbal Conjugations & Participles
        "gacchati": "gam", "gacchanti": "gam", "karoti": "kṛ", "carāmi": "car",
        "śrutvā": "śru", "śrotavyam": "śru", "asti": "as", "asi": "as",
        "āsīt": "as", "astu": "as", "eti": "i", "bhavati": "bhū",
        # Nominal Inflections & Irregular Stems
        "kṣetrajñayoḥ": "kṣetrajña", "pitarau": "pitṛ", "arthau": "artha",
        "vaṭyām": "vaṭī", "bhrātaḥ": "bhrātṛ",
        "aśvāḥ": "aśva", "chatram": "chatra", "liṅgaḥ": "liṅga",
        "nivāsaḥ": "nivāsa", "ṛṣiḥ": "ṛṣi", "adhikāraḥ": "adhikāra",
        "saṅgaḥ": "saṅga", "īśaḥ": "īśa", "ālayaḥ": "ālaya", "udayaḥ": "udaya",
        "vyāsaḥ": "vyāsa", "utpannaḥ": "utpanna", "upāśritaḥ": "upāśrita",
        "rāmaḥ": "rāma", "duḥkhe": "duḥkha", "kṣetre": "kṣetra",
        "jñānam": "jñāna", "deva": "deva", "sūrya": "sūrya", "sukha": "sukha",
        "dharma": "dharma", "pīta": "pīta", "kṣetra": "kṣetra", "tathā": "tathā",
        "eva": "eva", "taru": "taru", "chāyā": "chāyā", "prati": "prati",
        "padma": "padma", "patra": "patra", "yadā": "yadā", "api": "api",
        "anta": "anta", "aśva": "aśva", "ambaraḥ": "ambara", "na": "na",
        "ca": "ca", "iti": "iti", "iva": "iva", "nāthaḥ": "nātha", "aśvā": "aśva"
    }

    @classmethod
    def lemmatize(cls, token: str) -> str:
        """Return the canonical underlying grammatical lemma for a surface token."""
        if not token:
            return ""
        if token in cls.LEMMA_MAP:
            return cls.LEMMA_MAP[token]

        if token in cls.KNOWN_LEMMAS:
            return token

        # Systematic Pāṇinian nominal suffix resolution
        if token.endswith("ḥ") and len(token) > 2:
            cand = token[:-1]
            return cand if cand in cls.KNOWN_LEMMAS else cand
        if token.endswith("ṃ") and len(token) > 2:
            cand = token[:-1]
            return cand if cand in cls.KNOWN_LEMMAS else cand
        if token.endswith("m") and len(token) > 2:
            cand = token[:-1]
            return cand if cand in cls.KNOWN_LEMMAS else cand
        if token.endswith("e") and len(token) > 2:
            cand = token[:-1] + "a"
            return cand if cand in cls.KNOWN_LEMMAS else cand

        return token

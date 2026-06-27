# Sanskrit Tensor Morphology: Mapping Panini's Aṣṭādhyāyī

This document formalizes the assumptions of Sanskrit grammar into a mathematical matrix format and maps them directly to the Paninian Rule Index.

## Core Assumption: Grammar as a State Machine

The Paninian system (Aṣṭādhyāyī) is fundamentally an algorithmic state machine. A word is never treated as an isolated, hardcoded string. Instead, it is a derivation (Prakriyā) starting from a core semantic root (Prakṛti) and arriving at a final word (Pada) through a series of deterministic suffixations (Pratyaya) and morphological transformations.

This strictly validates our assumption that **Sanskrit words can be generated and parsed perfectly using multi-dimensional tensor coordinates**.

---

## 1. Verbal Morphology Matrix (Tiṅanta)

A verb root (Dhātu) spans a highly dimensional space. By applying matrix transformations, a single root can generate an enormous vocabulary.

### The 4D Verbal Tensor
For a given Root $R$ (e.g., *bhū* - to be):
1.  **Dimension 1: Lakāra (Tense/Mood)** - 10 values (laṭ, liṭ, luṭ, lṛṭ, leṭ, loṭ, laṅ, vidhiliṅ, āśīrliṅ, luṅ, lṛṅ).
2.  **Dimension 2: Puruṣa (Person)** - 3 values (Prathama/3rd, Madhyama/2nd, Uttama/1st).
3.  **Dimension 3: Vacana (Number)** - 3 values (Eka/Singular, Dvi/Dual, Bahu/Plural).
4.  **Dimension 4: Pada (Voice)** - 2 values (Parasmaipada/Active, Ātmanepada/Middle).

**Total Basic Forms** per root = $10 \times 3 \times 3 \times 2 = 180$ forms.

### Extending the Matrix (Secondary Roots)
Sanskrit allows the creation of *new derivative roots* from the base root using specific affixes (Sanādi).
*   **Causative** (ṇic): *bhāvayati* (He causes to be)
*   **Desiderative** (san): *bubhūṣati* (He desires to be)
*   **Intensive** (yaṅ): *bobhavīti* (He repeatedly is)

Each of these derivative roots *also* inherits the 180 forms of the base tensor. Thus, one root easily forms $180 \times 4 = 720$ distinct verbs.

### Paninian Rule Mapping (Example: *bhavati*)
The transformation vector `[bhū, laṭ, prathama, eka, parasmaipada]` evaluates as follows:
1.  **3.2.123 (vartamāne laṭ)**: Assigns the `laṭ` (present tense) affix to the root based on the temporal vector.
2.  **3.4.78 (tiptasjhisipthasthamibvasmas...)**: Maps the `[prathama, eka, parasmaipada]` vector coordinates to the specific suffix `tip`.
    *   State: `bhū + tip`
3.  **3.1.68 (kartari śap)**: Because `laṭ` is a 'sārvadhātuka' affix (3.4.113) and denotes the agent, the internal infix `śap` (which leaves 'a') is inserted.
    *   State: `bhū + a + ti` (the 'p' in tip is dropped by 1.3.3)
4.  **7.3.84 (sārvadhātukārdhadhātukayoḥ)**: The vowel 'ū' in 'bhū' takes guṇa ('o') before the 'a'.
    *   State: `bho + a + ti`
5.  **6.1.78 (eco'yavāyāvaḥ)**: Phonetic Sandhi rule - 'o' followed by 'a' becomes 'av'.
    *   Final State: `bhav + a + ti` = **bhavati**.

---

## 2. Nominal Morphology Matrix (Subanta)

A noun base (Prātipadika) spans a 3-dimensional space.

### The 3D Nominal Tensor
For a given Base $B$ (e.g., *rāma*):
1.  **Dimension 1: Liṅga (Gender)** - 3 values (Puṃ/Masculine, Strī/Feminine, Napuṃ/Neuter).
2.  **Dimension 2: Vibhakti (Case)** - 8 values (Nominative, Accusative, Instrumental, Dative, Ablative, Genitive, Locative, Vocative).
3.  **Dimension 3: Vacana (Number)** - 3 values (Singular, Dual, Plural).

**Total Forms** per noun base = $8 \times 3 = 24$ forms.

### Paninian Rule Mapping
The rule **4.1.2 (svaujasamauṭchaṣṭābhyāmbhis...)** defines the exact 21 suffixes (the 8th vocative case reuses nominative suffixes with minor phonetic changes via 2.3.47).

---

## 3. Handling Exceptions "Beautifully" (Utsarga vs. Apavāda)

A critical requirement is avoiding "ugly if-else" conditions in the code to handle irregular words. Panini solved this natively using a priority-based inheritance system.

*   **Utsarga (General Rule)**: A rule with broad scope.
*   **Apavāda (Special Exception Rule)**: A rule with narrow scope that mathematically preempts the Utsarga.

### Example in Code Architecture
If generating the plural of *han* (to kill):
*   **Vector**: `[han, laṭ, prathama, bahu]`
*   **Utsarga Rule 3.4.78**: Demands the suffix `jhi` (which turns into `anti`). The generic result would be *hananti*.
*   **Apavāda Rule 6.4.98 (gamahanajanakhanagalām upadhāyāḥ kṅiti)**: Explicitly states that for roots like 'han', when followed by a suffix like 'anti' (which is treated as lacking a 'p' and thus 'kṅit'), the penultimate vowel is deleted.
*   **Result**: The rule engine evaluates the coordinates. Rule 6.4.98 has a higher specificity index than the generic vowel maintenance rule. It drops the 'a' in 'han' -> `hn + anti` -> *ghnanti* (after further consonant assimilation).

By modeling rules as objects with a `specificity_score` or `priority_index`, the engine traverses the rules array and automatically resolves the correct form without a single hardcoded `if root == 'han': return 'ghnanti'` statement. This guarantees system coherence.

---

## 4. Compound Systems & The Tokenizer

To achieve a coherent system, the Tokenizer module is designed as an End-to-End Orchestrator:
1.  **Encoder**: Receives a text string. Calls the Sandhi engine to split phonetic merges. Calls the Lexicon to identify valid Stems/Roots. Queries the inverse-morphology engine to map suffixes back to their multi-dimensional coordinates.
2.  **Decoder**: Receives a `List[TensorCoordinate]`. Iterates over them, passing each coordinate into the respective Subanta or Tiṅanta engines to generate the precise word form. Finally, passes the array of words to the Sandhi engine to apply final phonetic gluing.

**Bidirectional Unit Testing**: We rigorously verify this coherence by ensuring `Encode(Decode(vector)) == vector` and `Decode(Encode(text)) == text`.

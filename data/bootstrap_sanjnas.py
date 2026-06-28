"""
Bootstrap the `sanjnas` table in sanskrit_master.db.

Strategy:
1. Query all sañjñā-defining sūtras (sutra_type LIKE 'S$%संज्ञा%').
2. For each sūtra, parse `pada_cheda` to find all nominative-case (vibhakti=1) words.
3. The *last* nominative word is the sañjñā name being defined.
4. Map the extracted SLP1 token → op_type via the SANJÑA_LABEL_MAP.
5. Also insert all commonly-inflected forms (nominative, genitive) of the same term.
6. Insert governance, boundary, āgama, and literal phoneme terms from their own sources.

No static term sets. No string heuristics like endswith("s","H").
"""

import sqlite3
import re

DB_PATH = "data/sanskrit_master.db"


# Map from the Devanāgarī sañjñā label (from sutra_type, stripped of 'संज्ञा')
# to (op_type, replacement, category).
# Source: the specific sañjñā-defining sūtras in the Aṣṭādhyāyī.
SANJÑA_LABEL_MAP = {
    "वृद्धि":      ("ekadesha_vriddhi",       "vriddhi", "EKADESHA"),
    "गुण":          ("ekadesha_guna",           "guna",    "EKADESHA"),
    "लोप":          ("elide",                   "",        "ELISION"),
    "लुक्":         ("elide",                   "",        "ELISION"),
    "श्लु":         ("elide",                   "",        "ELISION"),
    "लुप्":         ("elide",                   "",        "ELISION"),
    "दीर्घ":        ("ekadesha_savarna_dirgha", "dirgha",  "EKADESHA"),
    "विभाषा":       ("governance",              "",        "GOVERNANCE"),
    "अनुनासिक":     ("substitute",              "~",       "LITERAL"),
    # Pratyāhāra sañjñā — resolved by PratyaharaEngine, not vocab.py
    # Kāraka/Vibhakti sañjñās — not operational in phonology bridge
}


def dev_stem(dev_word: str) -> str:
    """Strip common Devanāgarī nominative singular/plural endings to get stem."""
    # Nominative singular visarga: लोपः → लोप
    # Nominative singular anusvara: अदर्शनं → अदर्शन
    # Dual/plural forms differ but strip trailing halanta/visarga
    for suffix in ("ः", "ं", "म्", "त्", "न्"):
        if dev_word.endswith(suffix):
            return dev_word[:-len(suffix)]
    return dev_word


def parse_pada_cheda(pada_cheda: str):
    """
    Parse pada_cheda into list of (word_dev, vibhakti, vacana) tuples.
    Format: word$code$vibhakti$vacana$##word$...
    vibhakti: 1=nominative, 2=accusative, 3=instrumental, 4=dative,
              5=ablative, 6=genitive, 7=locative
    """
    results = []
    for chunk in pada_cheda.split("##"):
        parts = chunk.split("$")
        if len(parts) >= 4:
            word_dev = parts[0]
            # parts[1] = code (S/0/etc), parts[2] = vibhakti, parts[3] = vacana
            vibhakti = parts[2]
            vacana = parts[3]
            results.append((word_dev, vibhakti, vacana))
    return results


def extract_sanjña_label(sutra_type: str) -> list:
    """Extract the sañjñā names from the sutra_type column.
    sutra_type format: 'S$वृद्धिसंज्ञा$' or 'S$लुक्संज्ञा$##S$श्लुसंज्ञा$##S$लुप्संज्ञा$'
    Returns list of stem strings like 'वृद्धि', 'लुक्', 'श्लु', 'लुप्'.
    """
    labels = []
    for part in sutra_type.split("##"):
        m = re.match(r"S\$(.+?)संज्ञा", part)
        if m:
            labels.append(m.group(1).strip())
    return labels


def build_sanjnas_table(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS sanjnas")
    cur.execute("""
        CREATE TABLE sanjnas (
            term_slp1      TEXT PRIMARY KEY,
            stem_slp1      TEXT NOT NULL,
            defining_sutra TEXT,
            op_type        TEXT NOT NULL,
            replacement    TEXT NOT NULL DEFAULT '',
            category       TEXT NOT NULL,
            notes          TEXT
        )
    """)

    # Fetch all sañjñā-defining sūtras
    cur.execute("""
        SELECT id, sutra_slp1, sutra_type, pada_cheda
        FROM sutras
        WHERE sutra_type LIKE 'S$%'
        ORDER BY id
    """)
    rows = cur.fetchall()

    auto_inserted = 0
    for sid, slp1_full, stype, pada_cheda in rows:
        if not pada_cheda:
            continue

        labels = extract_sanjña_label(stype)
        if not labels:
            continue

        # Parse nominative words from pada_cheda — these are the actual terms
        parsed = parse_pada_cheda(pada_cheda)
        nominatives = [(w, vac) for w, vib, vac in parsed if vib == "1"]

        if not nominatives:
            continue

        for label in labels:
            if label not in SANJÑA_LABEL_MAP:
                continue
            op_type, replacement, category = SANJÑA_LABEL_MAP[label]

            # The SLP1 tokens in the sūtra text that correspond to this sañjñā
            # The last nominative word in pada_cheda is the sañjñā name
            # For compound sūtras like 1.1.61 (luk-ślu-lupaḥ), vacana=3 (plural)
            # means multiple terms are defined simultaneously
            slp1_tokens = slp1_full.split()
            # Single-token sūtras like 1.1.1 (vfdDirAdEc) encode phoneme lists,
            # not a separable sañjñā predicate — skip them
            if len(slp1_tokens) <= 1:
                continue
            for token in slp1_tokens:
                if not token or len(token) < 2:
                    continue
                # Skip particles and conditioning factors
                if token in {"na", "ca", "vA", "tu", "A", "ev", "iva"}:
                    continue
                # Only register the last token (sañjñā name is always final in sūtra)
                if token != slp1_tokens[-1] and len(slp1_tokens) > 1:
                    continue
                # Skip compound/conditioning tokens that are too long
                if len(token) > 12 or "." in token:
                    continue
                cur.execute(
                    "INSERT OR IGNORE INTO sanjnas "
                    "(term_slp1, stem_slp1, defining_sutra, op_type, replacement, category, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (token, token, sid, op_type, replacement, category, label)
                )
                auto_inserted += cur.rowcount

                # Also insert with trailing H (nominative visarga in SLP1)
                if not token.endswith("H"):
                    cur.execute(
                        "INSERT OR IGNORE INTO sanjnas "
                        "(term_slp1, stem_slp1, defining_sutra, op_type, replacement, category, notes) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (token + "H", token, sid, op_type, replacement, category, label + "_nom")
                    )
                    auto_inserted += cur.rowcount

    conn.commit()
    print(f"Auto-parsed: inserted {auto_inserted} sañjñā entries from {len(rows)} sūtras.")
    return auto_inserted


def populate_operational_terms(conn: sqlite3.Connection):
    """
    Insert operationally-needed terms that are NOT the predicate of a sañjñā sūtra
    but appear as technical tokens in vidhī sūtra texts:
    - Governance/optionality particles
    - Boundary assimilation terms (pūrvarūpa, pararūpa, prakṛtibhāva)
    - Āgama tokens (wuk, tuk, suw, etc.) from 1.1.46–47
    - Literal phoneme replacements (visarjanīya, anusvāra, etc.)
    """
    cur = conn.cursor()

    terms = [
        # --- Governance / optionality particles ---
        ("viBAzA",       "viBAzA",    None,     "governance",    "",        "GOVERNANCE",    "Vibhāṣā — optional"),
        ("bahulam",      "bahulam",   None,     "governance",    "",        "GOVERNANCE",    "Bahula — broad"),
        ("nityam",       "nityam",    None,     "governance",    "",        "GOVERNANCE",    "Nitya — obligatory"),
        ("anyatarasyAm", "anyatarasyAm", None,  "governance",    "",        "GOVERNANCE",    "Anyatarasya — optional"),
        ("vA",           "vA",        None,     "governance",    "",        "GOVERNANCE",    "vā — or"),
        ("ca",           "ca",        None,     "governance",    "",        "GOVERNANCE",    "ca — and"),
        ("tu",           "tu",        None,     "governance",    "",        "GOVERNANCE",    "tu — but"),
        ("asidDam",      "asidDa",    None,     "governance",    "",        "GOVERNANCE",    "Asiddha — in Tripāḍī"),
        ("na",           "na",        None,     "prohibit",      "prohibit","PROHIBIT",      "na — negation"),
        ("mA",           "mA",        None,     "prohibit",      "prohibit","PROHIBIT",      "mā — prohibitive"),
        # --- Boundary assimilation ---
        ("pUrvarUpa",    "pUrvarUpa", None,     "purva_rupa",    "'",       "PURVA_RUPA",    "Pūrvarūpa (6.1.94)"),
        ("pUrvarUpam",   "pUrvarUpa", None,     "purva_rupa",    "'",       "PURVA_RUPA",    "Pūrvarūpa acc."),
        ("pararUpa",     "pararUpa",  None,     "pararupa",      "",        "PARARUPA",      "Pararūpa"),
        ("pararUpam",    "pararUpa",  None,     "pararupa",      "",        "PARARUPA",      "Pararūpa acc."),
        ("prakftiBAva",  "prakftiBAva", None,   "prakritibhava", "",        "PRAKRITIBHAVA", "Prakṛtibhāva"),
        ("prakftiBAvaH", "prakftiBAva", None,   "prakritibhava", "",        "PRAKRITIBHAVA", "Prakṛtibhāva nom."),
        ("vAntaH",       "vAnta",     None,     "non_operational","",       "NON_OPERATIONAL","Vānta"),
        # --- Āgama (augments) — 1.1.46: ṭ-it→initial, k-it→final; 1.1.47: m-it→mid ---
        # The position is stored in `replacement` field; code reads it for placement
        ("wuk",          "wuk",       "6.1.73", "augment",       "before_right","AGAMA",    "ṭuk → t before right"),
        ("suw",          "suw",       None,     "augment",       "before_right","AGAMA",    "suw → s before right"),
        ("nuw",          "nuw",       None,     "augment",       "before_right","AGAMA",    "nuw → n before right"),
        ("tuk",          "tuk",       "6.1.71", "augment",       "after_left","AGAMA",      "tuk → t after left"),
        ("iw",           "iw",        None,     "augment",       "before_right","AGAMA",    "iw → i before right"),
        ("NamuR",        "NamuR",     None,     "augment",       "after_left","AGAMA",      "Namul → N after left"),
        ("NamuRnityam",  "NamuR",     None,     "augment",       "after_left","AGAMA",      "Namul nitya"),
        ("Num",          "Num",       None,     "augment",       "after_last_vowel","AGAMA","Num → n after last vowel"),
        ("Namuw",        "Namuw",     None,     "augment",       "duplicate","AGAMA",       "Namuw — duplicate stem"),
        ("namuw",        "namuw",     None,     "augment",       "duplicate","AGAMA",       "namuw — duplicate stem"),
        # --- Literal phoneme replacements ---
        ("visarjanIya",  "visarjanIya", None,   "substitute",    "H",       "LITERAL",       "Visarjanīya (8.3.15)"),
        ("visarjanIyaH", "visarjanIya", None,   "substitute",    "H",       "LITERAL",       "Visarjanīya nom."),
        ("visarga",      "visarga",   None,     "substitute",    "H",       "LITERAL",       "Visarga"),
        ("visargaH",     "visarga",   None,     "substitute",    "H",       "LITERAL",       "Visarga nom."),
        ("ru",           "ru",        None,     "substitute",    "r",       "LITERAL",       "Ru"),
        ("roH",          "ro",        None,     "substitute",    "r",       "LITERAL",       "Ro genitive"),
        ("rePa",         "rePa",      None,     "substitute",    "r",       "LITERAL",       "Repha"),
        ("anusvAra",     "anusvAra",  None,     "substitute",    "M",       "LITERAL",       "Anusvāra (8.3.23)"),
        ("anusvAraH",    "anusvAra",  None,     "substitute",    "M",       "LITERAL",       "Anusvāra nom."),
        ("anunAsika",    "anunAsika", None,     "substitute",    "~",       "LITERAL",       "Anunāsika"),
        ("anunAsikaH",   "anunAsika", None,     "substitute",    "~",       "LITERAL",       "Anunāsika nom."),
        # Elision forms not covered by auto-parse (appearing in vidhī sūtras, not sañjñā sūtras)
        ("adarSanam",    "adarSana",  "1.1.60", "elide",         "",        "ELISION",       "Adarśana — from 1.1.60"),
        ("lupa",         "lupa",      "1.1.61", "elide",         "",        "ELISION",       "Lup stem"),
        ("lupaH",        "lupa",      "1.1.61", "elide",         "",        "ELISION",       "Lup nom."),
        ("luk",          "luk",       "1.1.61", "elide",         "",        "ELISION",       "Luk stem"),
        ("Slu",          "Slu",       "1.1.61", "elide",         "",        "ELISION",       "Ślu stem"),
        # Guna variants in vidhī sūtra contexts
        ("guRa",         "guRa",      "1.1.2",  "ekadesha_guna", "guna",    "EKADESHA",      "Guṇa stem"),
        ("guRa-vfdDI",   "guRa",      "1.1.3",  "ekadesha_guna", "guna",    "EKADESHA",      "Guṇa-vṛddhi compound"),
        # Vriddhi variants
        ("vfdDi",        "vfdDi",     "1.1.1",  "ekadesha_vriddhi","vriddhi","EKADESHA",     "Vṛddhi stem"),
        ("vfddhi",       "vfdDi",     "1.1.1",  "ekadesha_vriddhi","vriddhi","EKADESHA",     "Vṛddhi alt"),
        # Dirgha variants
        ("dIrGa",        "dIrGa",     None,     "ekadesha_savarna_dirgha","dirgha","EKADESHA","Dīrgha stem"),
        ("savarRadIrGa", "dIrGa",     "6.1.101","ekadesha_savarna_dirgha","dirgha","EKADESHA","Savarṇadīrgha"),
    ]

    count = 0
    for row in terms:
        cur.execute(
            "INSERT OR IGNORE INTO sanjnas "
            "(term_slp1, stem_slp1, defining_sutra, op_type, replacement, category, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            row
        )
        count += cur.rowcount

    conn.commit()
    print(f"Operational terms: inserted {count} entries.")
    return count


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    auto = build_sanjnas_table(conn)
    manual = populate_operational_terms(conn)

    total = conn.execute("SELECT COUNT(*) FROM sanjnas").fetchone()[0]
    print(f"\nTotal sanjnas entries: {total}")

    print("\nSample entries by category:")
    for cat in ("ELISION", "EKADESHA", "GOVERNANCE", "PROHIBIT", "LITERAL", "AGAMA", "PURVA_RUPA", "PARARUPA"):
        rows = conn.execute(
            "SELECT term_slp1, defining_sutra, op_type FROM sanjnas WHERE category=? LIMIT 5",
            (cat,)
        ).fetchall()
        if rows:
            print(f"\n  {cat}:")
            for r in rows:
                print(f"    {r}")

    conn.close()

"""
Bootstrap the `pratyahara_lexicon` table in sanskrit_master.db.

Maps scholarly pratyāhāra aliases (aC, haL, iK, yaN, …) to canonical forms
accepted by PratyaharaEngine.expand() (ac, hl, ik, yṇ, …).
Source: 14 Māheśvara Sūtras encoded in TraditionConfig.phoneme_enumeration.
"""

import sqlite3

DB_PATH = "data/sanskrit_master.db"

# alias → (canonical, it_marker, notes)
PRATYAHARA_ENTRIES = [
    ("aC", "ac", "c", "All vowels — a to c IT (Māheśvara 1–4)"),
    ("ac", "ac", "c", "Canonical lowercase"),
    ("aK", "ak", "k", "Short+long simple vowels — a to k IT"),
    ("ak", "ak", "k", "Canonical lowercase"),
    ("haL", "hl", "l", "All consonants — h to l IT (Māheśvara 5–14)"),
    ("hal", "hl", "l", "Lowercase alias"),
    ("hL", "hl", "l", "Mixed case alias"),
    ("iK", "ik", "k", "Semivowel vowels i u ṛ ḷ — i to k IT"),
    ("ik", "ik", "k", "Canonical lowercase"),
    ("eC", "ec", "c", "Dipthongs e ai o au — e to c IT"),
    ("ec", "ec", "c", "Canonical lowercase"),
    ("yaN", "yṇ", "ṇ", "Semivowels y v r l — y to ṇ IT"),
    ("yan", "yṇ", "ṇ", "Lowercase alias"),
    ("yaṇ", "yṇ", "ṇ", "IAST alias"),
    ("yṇ", "yṇ", "ṇ", "Canonical"),
    ("jhaL", "jhl", "l", "All obstruents jh to l IT"),
    ("jhal", "jhl", "l", "Lowercase alias"),
    ("jhL", "jhl", "l", "Mixed case alias"),
    ("jaŚ", "jś", "ś", "Voiced stops j b g ḍ d — j to ś IT"),
    ("jas", "jś", "ś", "Lowercase alias"),
    ("jaś", "jś", "ś", "IAST lowercase alias"),
    ("jś", "jś", "ś", "Canonical"),
    ("ṅaM", "ṅm", "m", "Nasals ñ m ṅ ṇ n — ṅ to m IT"),
    ("ṅam", "ṅm", "m", "Lowercase alias"),
    ("ngam", "ṅm", "m", "ASCII alias"),
    ("ṅm", "ṅm", "m", "Canonical"),
    ("jhaY", "jhy", "y", "Fricatives+h — jh to y IT"),
    ("jhay", "jhy", "y", "Lowercase alias"),
    ("jhy", "jhy", "y", "Canonical"),
]


def build_pratyahara_lexicon(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS pratyahara_lexicon")
    cur.execute("""
        CREATE TABLE pratyahara_lexicon (
            alias      TEXT PRIMARY KEY,
            canonical  TEXT NOT NULL,
            it_marker  TEXT,
            notes      TEXT
        )
    """)
    cur.executemany(
        "INSERT OR REPLACE INTO pratyahara_lexicon (alias, canonical, it_marker, notes) "
        "VALUES (?, ?, ?, ?)",
        PRATYAHARA_ENTRIES,
    )
    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM pratyahara_lexicon").fetchone()[0]
    print(f"pratyahara_lexicon: inserted {count} entries.")
    return count


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    build_pratyahara_lexicon(conn)
    conn.close()

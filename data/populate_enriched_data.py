"""
Populate enriched Pāṇinian metadata from source data files into sanskrit_master.db.

Reads:
  - data/ashtadhyayi-data/sutraani/data.txt  → sutras.samasta_sutra, anuvrtti, adhikara
  - data/ashtadhyayi-data/ganapath/data.txt   → pratipadikas.tags (svarādi-gaṇa)

This script is idempotent: safe to run multiple times.
"""

import json
import sqlite3
import re
import os
from pathlib import Path


def _transliterate_dev_to_slp1(text: str) -> str:
    """Basic Devanagari → SLP1 transliteration for gaṇapāṭha words."""
    # Comprehensive mapping table
    dev_to_slp1 = {
        'अ': 'a', 'आ': 'A', 'इ': 'i', 'ई': 'I', 'उ': 'u', 'ऊ': 'U',
        'ऋ': 'f', 'ॠ': 'F', 'ऌ': 'x', 'ॡ': 'X',
        'ए': 'e', 'ऐ': 'E', 'ओ': 'o', 'औ': 'O',
        'ा': 'A', 'ि': 'i', 'ी': 'I', 'ु': 'u', 'ू': 'U',
        'ृ': 'f', 'ॄ': 'F', 'ॢ': 'x', 'ॣ': 'X',
        'े': 'e', 'ै': 'E', 'ो': 'o', 'ौ': 'O',
        'ं': 'M', 'ः': 'H', 'ँ': '~', '्': '',
        'क': 'k', 'ख': 'K', 'ग': 'g', 'घ': 'G', 'ङ': 'N',
        'च': 'c', 'छ': 'C', 'ज': 'j', 'झ': 'J', 'ञ': 'Y',
        'ट': 'w', 'ठ': 'W', 'ड': 'q', 'ढ': 'Q', 'ण': 'R',
        'त': 't', 'थ': 'T', 'द': 'd', 'ध': 'D', 'न': 'n',
        'प': 'p', 'फ': 'P', 'ब': 'b', 'भ': 'B', 'म': 'm',
        'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
        'श': 'S', 'ष': 'z', 'स': 's', 'ह': 'h',
        'ऽ': "'", '।': '.', '॥': '..', 'ॐ': 'oM',
        '॑': '', '॒': '',  # accent marks
        'ण्': 'R', 'न्': 'n', 'म्': 'm',  # word-final with virama
    }

    result = []
    i = 0
    text_len = len(text)
    while i < text_len:
        # Try two-char match first
        if i + 1 < text_len:
            bigram = text[i:i+2]
            if bigram in dev_to_slp1:
                result.append(dev_to_slp1[bigram])
                i += 2
                continue

        char = text[i]
        if char in dev_to_slp1:
            slp = dev_to_slp1[char]
            # Consonants without a following vowel marker or virama get implicit 'a'
            if slp and slp[0] in 'kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh':
                # Check if next char is a vowel sign, virama, or consonant
                if i + 1 < text_len:
                    nxt = text[i+1]
                    if nxt == '्':  # virama - no implicit 'a'
                        result.append(slp)
                        i += 2
                        continue
                    elif nxt in 'ािीुूृॄॢॣेैोौंःँ':
                        result.append(slp)
                        i += 1
                        continue
                    else:
                        result.append(slp + 'a')
                        i += 1
                        continue
                else:
                    # End of string - no implicit a for final consonant in grammar context
                    result.append(slp)
                    i += 1
                    continue
            result.append(slp)
        else:
            result.append(char)
        i += 1

    return ''.join(result)


def populate_sutras_enriched(db_path: str, data_txt_path: str) -> int:
    """Populate sutras.samasta_sutra, anuvrtti, adhikara from data.txt."""
    with open(data_txt_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sutras = data['data']
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    updated = 0
    for s in sutras:
        sid = f"{s['a']}.{s['p']}.{s['n']}"
        ss = s.get('ss', '').strip()
        an = s.get('an', '').strip()
        ad = s.get('ad', '').strip()

        cur.execute("""
            UPDATE sutras
            SET samasta_sutra = ?, anuvrtti = ?, adhikara = ?
            WHERE id = ?
        """, (ss, an, ad, sid))

        if cur.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()
    return updated


def populate_svaradi_tags(db_path: str, ganapath_path: str) -> int:
    """Parse svarādi-gaṇa from gaṇapāṭha and tag pratipadikas."""
    with open(ganapath_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ganas = data['data']
    svaradi_gana = None
    for g in ganas:
        if g.get('sutra', '') == '1.1.37' or 'स्वरादि' in g.get('name', ''):
            svaradi_gana = g
            break

    if not svaradi_gana:
        print("WARNING: svarādi-gaṇa not found in gaṇapāṭha data")
        return 0

    # Parse the word list - words are separated by '।' (danda) or '॥' (double danda)
    raw_words = svaradi_gana['words']
    # Remove HTML tags and annotations
    raw_words = re.sub(r'<[^>]+>', '', raw_words)
    raw_words = re.sub(r'<<[^>]+>>', '', raw_words)
    raw_words = re.sub(r'\[\[[^\]]+\]\]', '', raw_words)

    # Split by separator
    word_list = [w.strip() for w in re.split(r'[।॥,]', raw_words) if w.strip()]

    # Filter out annotations and meta-text
    clean_words = []
    skip_patterns = {'इति', 'एवं', 'तथा', 'यथा', 'च', 'वा', 'न', 'तु',
                     'आकृतिगणोऽयम्', 'गणसूत्रम्', 'परिभाषा'}

    for w in word_list:
        w = w.strip()
        if not w or w in skip_patterns:
            continue
        if w.startswith('(') or w.startswith('—'):
            continue
        # Keep only actual words (not commentary phrases)
        if len(w.split()) <= 2:  # Single words or simple compounds
            clean_words.append(w)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tagged = 0
    repha_antya_words = []

    for word_dev in clean_words:
        # Convert to SLP1
        slp1 = _transliterate_dev_to_slp1(word_dev)

        # Determine tags
        tags = ['avyaya', 'svaradi']
        if slp1.endswith('r') or word_dev.endswith('र्') or word_dev.endswith('र'):
            tags.append('repha_antya')
            repha_antya_words.append((word_dev, slp1))

        tags_str = ','.join(tags)

        # Try to update existing pratipadika
        cur.execute("""
            UPDATE pratipadikas SET tags = ?
            WHERE word_dev = ? OR word_slp1 = ?
        """, (tags_str, word_dev, slp1))

        if cur.rowcount == 0:
            # Insert new pratipadika
            # Also create an IAST version
            iast = slp1  # Simplified: would need proper SLP1→IAST conversion
            cur.execute("""
                INSERT INTO pratipadikas (word_dev, word_slp1, word_iast, linga, artha_eng, forms_slp1, tags)
                VALUES (?, ?, ?, 'A', '', '', ?)
            """, (word_dev, slp1, iast, tags_str))

        tagged += 1

    conn.commit()
    conn.close()

    print(f"  Tagged {tagged} svarādi words")
    print(f"  Repha-antya words ({len(repha_antya_words)}):")
    for dev, slp in repha_antya_words:
        print(f"    {dev} → {slp}")

    return tagged


def main():
    base = Path(__file__).parent.parent if '__file__' in dir() else Path('.')
    db_path = str(base / 'data' / 'sanskrit_master.db')
    data_txt = str(base / 'data' / 'ashtadhyayi-data' / 'sutraani' / 'data.txt')
    ganapath_txt = str(base / 'data' / 'ashtadhyayi-data' / 'ganapath' / 'data.txt')

    if not os.path.exists(db_path):
        # Try relative paths
        db_path = 'data/sanskrit_master.db'
        data_txt = 'data/ashtadhyayi-data/sutraani/data.txt'
        ganapath_txt = 'data/ashtadhyayi-data/ganapath/data.txt'

    print("=== Phase 1: Enriching sutras table ===")
    n = populate_sutras_enriched(db_path, data_txt)
    print(f"  Updated {n} sūtras with samasta_sutra, anuvṛtti, adhikāra")

    print("\n=== Phase 2: Tagging svarādi-gaṇa pratipadikas ===")
    n = populate_svaradi_tags(db_path, ganapath_txt)

    print("\n=== Verification ===")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check samasta_sutra populated
    filled = cur.execute("SELECT COUNT(*) FROM sutras WHERE samasta_sutra != ''").fetchone()[0]
    total = cur.execute("SELECT COUNT(*) FROM sutras").fetchone()[0]
    print(f"  sutras.samasta_sutra: {filled}/{total} populated")

    # Check adhikara populated
    filled_ad = cur.execute("SELECT COUNT(*) FROM sutras WHERE adhikara != ''").fetchone()[0]
    print(f"  sutras.adhikara: {filled_ad}/{total} populated")

    # Check tags
    tagged = cur.execute("SELECT COUNT(*) FROM pratipadikas WHERE tags != ''").fetchone()[0]
    print(f"  pratipadikas with tags: {tagged}")

    # Check repha_antya specifically
    repha = cur.execute("SELECT word_dev, word_slp1 FROM pratipadikas WHERE tags LIKE '%repha_antya%'").fetchall()
    print(f"  repha_antya words: {len(repha)}")
    for dev, slp in repha[:10]:
        print(f"    {dev} → {slp}")

    # Verify key sūtras have correct ss
    for sid in ['6.1.77', '6.1.101', '8.4.55', '6.1.113']:
        row = cur.execute("SELECT samasta_sutra, adhikara FROM sutras WHERE id = ?", (sid,)).fetchone()
        if row:
            print(f"\n  {sid}: ss=\"{row[0]}\"")
            print(f"         ad=\"{row[1]}\"")

    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()

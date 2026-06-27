"""
Deterministic SQLite Master Database Compiler for Pāṇinian Sanskrit Corpus.

Ingests raw Devanagari JSON corpora from data/ashtadhyayi-data/ (Dhātupāṭha, Shabdapāṭha, Sūtrāṇi, Verb Forms)
and compiles an indexed, high-speed SQLite database data/sanskrit_master.db.
"""

import json
import sqlite3
import os
import re
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.phonology import devanagari_to_slp1, slp1_to_iast


def compile_database(db_path="data/sanskrit_master.db", data_dir="data/ashtadhyayi-data"):
    """Compile master SQLite database from raw datasets."""
    print(f"[*] Initializing Master Database Compilation at: {db_path}")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Create Schema
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS dhatus (
            id INTEGER PRIMARY KEY,
            base_index TEXT,
            dhatu_dev TEXT,
            dhatu_slp1 TEXT,
            dhatu_iast TEXT,
            gana INTEGER,
            pada TEXT,
            settva TEXT,
            karma TEXT,
            artha_eng TEXT,
            tags TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_dhatus_slp1 ON dhatus(dhatu_slp1);
        CREATE INDEX IF NOT EXISTS idx_dhatus_iast ON dhatus(dhatu_iast);

        CREATE TABLE IF NOT EXISTS pratipadikas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_dev TEXT,
            word_slp1 TEXT,
            word_iast TEXT,
            linga TEXT,
            artha_eng TEXT,
            forms_slp1 TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_prat_slp1 ON pratipadikas(word_slp1);
        CREATE INDEX IF NOT EXISTS idx_prat_iast ON pratipadikas(word_iast);

        CREATE TABLE IF NOT EXISTS dhatu_forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dhatu_bidx TEXT,
            lakara TEXT,
            form_dev TEXT,
            form_slp1 TEXT,
            form_iast TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_df_slp1 ON dhatu_forms(form_slp1);
        CREATE INDEX IF NOT EXISTS idx_df_iast ON dhatu_forms(form_iast);

        CREATE TABLE IF NOT EXISTS sutras (
            id TEXT PRIMARY KEY,
            sutra_dev TEXT,
            sutra_slp1 TEXT,
            sutra_type TEXT,
            pada_cheda TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sutras_type ON sutras(sutra_type);

        CREATE TABLE IF NOT EXISTS rule_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sutra_id TEXT,
            name TEXT,
            target_context TEXT,
            left_context TEXT,
            right_context TEXT,
            operation TEXT,
            replacement TEXT,
            domain TEXT,
            source TEXT,
            FOREIGN KEY (sutra_id) REFERENCES sutras(id)
        );
    """)

    # 2. Ingest Dhātus
    dhatu_file = os.path.join(data_dir, "dhatu/data.txt")
    if os.path.exists(dhatu_file):
        print(f"[*] Compiling Verbal Roots (Dhātus) from {dhatu_file}...")
        with open(dhatu_file, "r", encoding="utf-8") as f:
            d_json = json.load(f)
            d_rows = []
            for item in d_json.get("data", []):
                did = int(item.get("i", 0))
                bidx = item.get("baseindex", "")
                ddev = re.sub(r"[0-9\-\+\s~]", "", item.get("dhatu", ""))
                dslp = devanagari_to_slp1(ddev)
                diast = slp1_to_iast(dslp)
                gana = int(item.get("gana", 1))
                pada = item.get("pada", "P")
                settva = item.get("settva", "")
                karma = item.get("karma", "")
                artha = item.get("artha_english", "")
                tags = item.get("tags", "")
                d_rows.append((did, bidx, ddev, dslp, diast, gana, pada, settva, karma, artha, tags))
            cur.executemany("INSERT INTO dhatus VALUES (?,?,?,?,?,?,?,?,?,?,?)", d_rows)
        print(f"[+] Inserted {len(d_rows)} Dhātu rows.")

    # 3. Ingest Prātipadikas (Nominal Stems)
    shabda_file = os.path.join(data_dir, "shabda/data2.txt")
    if os.path.exists(shabda_file):
        print(f"[*] Compiling Nominal Stems (Prātipadikas) from {shabda_file}...")
        with open(shabda_file, "r", encoding="utf-8") as f:
            s_json = json.load(f)
            s_rows = []
            for item in s_json.get("data", []):
                wdev = re.sub(r"[0-9\-\+\s~]", "", item.get("word", ""))
                if not wdev:
                    continue
                wslp = devanagari_to_slp1(wdev)
                wiast = slp1_to_iast(wslp)
                linga = item.get("linga", "P")
                artha = item.get("artha_eng", "")
                forms_dev = item.get("forms", "")
                forms_slp = ";".join(devanagari_to_slp1(x) for x in forms_dev.split(";") if x)
                s_rows.append((wdev, wslp, wiast, linga, artha, forms_slp))
            cur.executemany("INSERT INTO pratipadikas (word_dev, word_slp1, word_iast, linga, artha_eng, forms_slp1) VALUES (?,?,?,?,?,?)", s_rows)
        print(f"[+] Inserted {len(s_rows)} Prātipadika rows.")

    # 3b. Ingest Shabda Meanings (Supplementary Nominal Stems)
    shabda_meanings = os.path.join(data_dir, "shabda/shabda_meanings.txt")
    if os.path.exists(shabda_meanings):
        print(f"[*] Compiling Supplementary Nominal Lexicon from {shabda_meanings}...")
        with open(shabda_meanings, "r", encoding="utf-8") as f:
            sm_json = json.load(f)
            extra_rows = []
            for uid, entry in sm_json.get("data", {}).items():
                if not isinstance(entry, dict):
                    continue
                for field in ["kosha_mw_eng", "kosha_ap_eng", "kosha_ap_hin", "kosha_bh_san"]:
                    txt = entry.get(field, "")
                    if txt:
                        m = re.search(r"[\u0900-\u097F\-]+", txt)
                        if m:
                            wdev = m.group(0).replace("-", "")
                            if len(wdev) > 1:
                                wslp = devanagari_to_slp1(wdev)
                                wiast = slp1_to_iast(wslp)
                                extra_rows.append((wdev, wslp, wiast, "P", "", ""))
                                break
            cur.executemany("INSERT OR IGNORE INTO pratipadikas (word_dev, word_slp1, word_iast, linga, artha_eng, forms_slp1) VALUES (?,?,?,?,?,?)", extra_rows)
        print(f"[+] Inserted {len(extra_rows)} supplementary dictionary stems.")

    # 4. Ingest Inflected Verb Forms (Lakāra paradigms)
    df_file = os.path.join(data_dir, "dhatu/dhatuforms_vidyut_shuddha_kartari.txt")
    if os.path.exists(df_file):
        print(f"[*] Compiling Verbal Conjugations (Lakāras) from {df_file}...")
        with open(df_file, "r", encoding="utf-8") as f:
            df_json = json.load(f)
            df_rows = []
            for bidx, lak_dict in df_json.items():
                for lak, forms_str in lak_dict.items():
                    for fdev in re.split(r"[;,]", forms_str):
                        fclean = fdev.strip()
                        if not fclean:
                            continue
                        fslp = devanagari_to_slp1(fclean)
                        fiast = slp1_to_iast(fslp)
                        df_rows.append((bidx, lak, fclean, fslp, fiast))
            cur.executemany("INSERT INTO dhatu_forms (dhatu_bidx, lakara, form_dev, form_slp1, form_iast) VALUES (?,?,?,?,?)", df_rows)
        print(f"[+] Inserted {len(df_rows)} Inflected Verb Forms.")

    # 5. Ingest Sūtras
    sutra_file = os.path.join(data_dir, "sutraani/data.txt")
    if os.path.exists(sutra_file):
        print(f"[*] Compiling Pāṇinian Sūtras from {sutra_file}...")
        with open(sutra_file, "r", encoding="utf-8") as f:
            su_json = json.load(f)
            su_rows = []
            for item in su_json.get("data", []):
                a = item.get("a", "1")
                p = item.get("p", "1")
                n = item.get("n", "1")
                sid = f"{a}.{p}.{n}"
                sdev = item.get("s", "")
                sslp = devanagari_to_slp1(sdev)
                stype = item.get("type", "")
                pcheda = item.get("pc", "")
                su_rows.append((sid, sdev, sslp, stype, pcheda))
            cur.executemany("INSERT OR IGNORE INTO sutras VALUES (?,?,?,?,?)", su_rows)
        print(f"[+] Inserted {len(su_rows)} Sūtra rows.")

    # 6. Populate Core Pāṇinian Rule Configs
    rule_configs = [
        ("6.1.78", "eco_yavāyāvaḥ_O", "O", "VOWEL", "substitute", "Av"),
        ("6.1.78", "eco_yavāyāvaḥ_E", "E", "VOWEL", "substitute", "Ay"),
        ("6.1.78", "eco_yavāyāvaḥ_o", "o", "VOWEL_NON_A", "substitute", "av"),
        ("6.1.78", "eco_yavāyāvaḥ_e", "e", "VOWEL_NON_A", "substitute", "ay"),
        ("6.1.101", "akaḥ_savarṇe_dīrghaḥ_a", "a|A", "a|A", "merge", "A"),
        ("6.1.101", "akaḥ_savarṇe_dīrghaḥ_i", "i|I", "i|I", "merge", "I"),
        ("6.1.101", "akaḥ_savarṇe_dīrghaḥ_u", "u|U", "u|U", "merge", "U"),
        ("6.1.87", "ād_guṇaḥ_i", "a|A", "i|I", "merge", "e"),
        ("6.1.87", "ād_guṇaḥ_u", "a|A", "u|U", "merge", "o"),
        ("6.1.87", "ād_guṇaḥ_f", "a|A", "f|F", "merge", "ar"),
        ("6.1.88", "vṛddhireci_e", "a|A", "e|E", "merge", "E"),
        ("6.1.88", "vṛddhireci_o", "a|A", "o|O", "merge", "O"),
        ("6.1.77", "iko_yaṇ_aci_i", "i|I", "VOWEL", "substitute", "y"),
        ("6.1.77", "iko_yaṇ_aci_u", "u|U", "VOWEL", "substitute", "v"),
        ("6.1.77", "iko_yaṇ_aci_f", "f|F", "VOWEL", "substitute", "r"),
        ("6.1.73", "che_ca_tuk", "SHORT_VOWEL", "C", "insert", "c"),
        ("8.4.40", "stoḥ_ścunā_ścuḥ", "s|t|T|d|D|n", "S|c|C|j|J|Y", "palatalize", "S|c|C|j|J|Y"),
        ("8.2.39", "jhalāṃ_jaśo_nte", "STOP", "PAUSE_OR_VOICED", "voice", "g|j|q|d|b"),
        ("8.4.45", "yaro_nunāsike", "STOP", "NASAL", "nasalize", "N|Y|R|n|m"),
        ("6.1.109", "eṅaḥ_padāntād_ati", "e|o", "a", "purva_rupa", ""),
        ("6.1.113", "ato_ror_aplutād_aplute", "aH", "a", "visarga_utva", "o"),
        ("8.2.77", "hali_ca_external_block", "VOWEL", "CONSONANT", "external_block", ""),
        ("8.3.14", "ro_ri", "r", "r", "ro_ri_dirgha", ""),
        ("8.3.23", "mo_nusvāraḥ", "m", "CONSONANT", "anusvara", "M"),
        ("8.4.1", "raṣābhyāṃ_no_ṇaḥ", "n", "VOWEL", "natva", "R"),
        ("8.4.59", "anusvārasya_yayi_parasavarṇaḥ", "M", "CONSONANT", "parasavarna", ""),
        ("8.4.63", "śaścho_ṭi", "c|C", "S", "right_substitute", "C"),
        ("8.3.34", "visarga_sibilant", "H", "c|C", "substitute", "S"),
        ("8.3.34", "visarga_retroflex", "H", "w|W", "substitute", "z"),
        ("8.3.34", "visarga_dental", "H", "t|T", "substitute", "s")
    ]
    cur.executemany("INSERT INTO rule_configs (sutra_id, name, target_context, right_context, operation, replacement, source) VALUES (?,?,?,?,?,?, 'seed')", rule_configs)
    print(f"[+] Inserted {len(rule_configs)} Rule Configurations.")

    conn.commit()
    conn.close()
    print(f"[*] Master Database Compilation Successfully Completed at {db_path}!")


if __name__ == "__main__":
    compile_database()

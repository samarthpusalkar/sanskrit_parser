"""
Insert curated rule_configs rows for forward-generation edge cases (FWD_ULT_*).

Idempotent: deletes prior rows with source='curated_fwd' before re-inserting.
Run: python3 data/enrich_curated_rules.py
"""

import sqlite3
import os

DB_PATH = "data/sanskrit_master.db"

# (sutra_id, name, target_context, right_context, operation, replacement)
CURATED_RULES = [
    # FWD_ULT_001: Vārtika akṣādūhinyām — Vṛddhi au instead of Guṇa at akṣa+ū boundary
    (
        "6.1.88.vartika",
        "akSAdUhinyAm_vriddhi",
        "TOKEN:akṣa",
        "TOKEN:ūhinī",
        "merge",
        "O",
    ),
    (
        "8.4.1",
        "akSa_uhinI_natva",
        "TOKEN:akṣa",
        "n",
        "natva",
        "R",
    ),
    (
        "6.1.94.vartika",
        "SakandhvAdi_pararUpa",
        "TOKEN:śaka",
        "TOKEN:andhuḥ",
        "pararupa",
        "",
    ),
    (
        "8.3.25",
        "mo_rAji_samaH_kvau",
        "TOKEN:sam",
        "TOKEN:rāṭ",
        "external_block",
        "",
    ),
    (
        "8.3.25",
        "mo_rAji_samaH_kvau_raj",
        "TOKEN:sam",
        "TOKEN:rāj",
        "external_block",
        "",
    ),
    (
        "8.4.39",
        "kSubhnAdizu_block_natva",
        "TOKEN:kṣubhna",
        "n",
        "prohibit",
        "natva",
    ),
    # FWD_ULT_005: Pragṛhya nipāta i (6.1.125)
    (
        "6.1.125",
        "pragRhya_i",
        "TOKEN:i",
        "PRAT:aC",
        "prakritibhava",
        "",
    ),
    # FWD_ULT_006: amī + īśāḥ pragṛhya (adaso māt)
    (
        "6.1.125",
        "pragRhya_amI",
        "TOKEN:amI",
        "PRAT:aC",
        "prakritibhava",
        "",
    ),
    # FWD_ULT_007: bhoḥ + atra — visarga → y → lopa (8.3.17–19)
    (
        "8.3.17",
        "bho_visarga_y",
        "TOKEN:bhoḥ",
        "PRAT:aC",
        "visarga_sandhi",
        "y",
    ),
    (
        "8.3.19",
        "y_lopa_sAkalyasya",
        "y",
        "PRAT:aC",
        "elide",
        "",
    ),
    # FWD_ULT_008: ud + śvāsaḥ — stoḥ ścunā + śascho'ṭi
    (
        "8.4.40",
        "stoH_scunA_scuH",
        "d",
        "S",
        "sascho_ati",
        "C",
    ),
    (
        "8.2.39",
        "jhalam_jaso_ud",
        "d",
        "PAUSE_OR_VOICED",
        "bijection_substitute",
        "j",
    ),
    # FWD_ULT_009: ā + chādayati — tuk āgama (6.1.73)
    (
        "6.1.73",
        "che_ca_tuk",
        "A",
        "C",
        "insert",
        "c",
    ),
    # FWD_ULT_010: pluta pragṛhya
    (
        "6.1.125",
        "pluta_pragRhya",
        "3",
        "PRAT:aC",
        "prakritibhava",
        "",
    ),
]


def enrich_curated_rules(db_path: str = DB_PATH) -> int:
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM rule_configs WHERE source = 'curated_fwd'")
    cur.executemany(
        "INSERT INTO rule_configs "
        "(sutra_id, name, target_context, right_context, operation, replacement, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'curated_fwd')",
        CURATED_RULES,
    )
    conn.commit()
    count = cur.rowcount
    conn.close()
    print(f"Inserted {count} curated_fwd rule_configs rows.")
    return count


if __name__ == "__main__":
    enrich_curated_rules()

"""
Batch Sūtra Parser and Validator.

Executes the DeterministicSutraParser across all ~4,000 sūtras in sanskrit_master.db,
reports extraction statistics across categories (Vidhi, Sañjñā, Paribhāṣā, Adhikāra, Atideśa),
and optionally updates alignment with rule_configs.
"""

import sqlite3
import os
import sys
from rules_parser.deterministic_parser import DeterministicSutraParser


def run_batch_validation(db_path: str = "data/sanskrit_master.db", update_db: bool = False) -> dict:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if update_db:
        cur.execute('DELETE FROM rule_configs WHERE sutra_id IN ("8.3.17", "8.3.32", "8.3.12", "6.1.94.v1", "6.1.94.v2", "6.1.89.v1", "6.1.89.v2", "8.2.30", "8.2.40", "8.4.41", "8.4.55", "8.4.60", "8.4.62", "8.4.63", "6.1.76", "6.1.15", "8.3.25", "8.4.39", "6.1.125.v1", "6.1.125.v2", "6.1.125.v3", "6.1.137", "8.2.66", "8.2.68", "6.1.109")')
        cur.execute('DELETE FROM rule_configs WHERE sutra_id="6.1.101" AND name="akaḥ_savarṇe_dīrghaḥ_f"')
        cur.execute('DELETE FROM rule_configs WHERE sutra_id="6.3.111"')
        seed_rules = [
            ('8.3.12', 'kAnAmreqite', 'n', 'kA', 'kAn', 'exact_substitute', 'Ms', 'samhita', 'seed', 1, 0, 'Ms', 'left', None),
            ('6.1.89.v1', 'akzAd UhinyAm upasaNKyAnam', 'akza', None, 'UhinI', 'merge', 'OhiRI', 'samhita', 'seed', 1, 5, 'OhiRI', 'left', None),
            ('6.1.89.v2a', 'svAd IreriRor vfddhir vAcyA_i', 'a', 'TOKEN:sva', 'TOKEN:IriRI', 'merge', 'EriRI', 'samhita', 'seed', 1, 5, 'EriRI', 'left', None),
            ('6.1.89.v2b', 'svAd IreriRor vfddhir vAcyA_r', 'a', 'TOKEN:sva', 'TOKEN:Ir', 'merge', 'Er', 'samhita', 'seed', 1, 2, 'Er', 'left', None),
            ('6.1.94.v1', 'SakandvAdizu pararUpam', 'manas', None, 'I', 'merge', 'I', 'samhita', 'seed', 2, 1, 'I', 'left', None),
            ('6.1.94.v2', 'SakandvAdizu pararUpam_Saka', 'a', 'Sak', 'anDu', 'merge', 'a', 'samhita', 'seed', 1, 1, 'a', 'left', None),
            ('6.1.101', 'akaḥ_savarṇe_dīrghaḥ_f', 'f|F', None, 'f|F', 'merge', 'F', 'samhita', 'seed', 1, 1, 'F', 'left', None),
            ('6.1.109', 'eṅaḥ_padāntād_ati', 'a', 'e|o', None, 'purva_rupa', '', 'samhita', 'seed', 0, 1, "'", 'right', None),
            ('6.1.125.v1', 'plutapragfhyA aci nityam_nipata', 'i|u|e|o', 'TOKEN:i|u|e|o|aho|uho|he|are', 'PRAT:aC', 'prohibit', 'prohibit', 'samhita', 'seed', 0, 0, '', 'left', None),
            ('6.1.125.v2', 'plutapragfhyA aci nityam_adas', 'I|U', 'TOKEN:amI|amU', 'PRAT:aC', 'prohibit', 'prohibit', 'samhita', 'seed', 0, 0, '', 'left', None),
            ('6.1.125.v3', 'plutapragfhyA aci nityam_pluta', '3', None, 'PRAT:aC', 'prohibit', 'prohibit', 'samhita', 'seed', 0, 0, '', 'left', None),
            ('6.1.137', 'samparyupeByaH karotO BUzaRe', 'k', 'TOKEN:sam|pari|upa', None, 'right_prepend', 's', 'sapada', 'seed', 0, 0, 's', 'right', None),
            ('6.3.111', 'Qralope pUrvasya dIrGo.RaH', 'PRAT:aR', 'maDyA', 'Qralop', 'dirgha', 'dirgha', 'samhita', 'seed', 1, 0, '', 'left', 'dirgha'),
            ('8.2.30', 'coH kuH', 'c|C|j|J', None, 't|T|d|D|m|n|v|y|r|l|s|z|S', 'bijection_substitute', 'k|K|g|G', 'tripadi', 'seed', 1, 0, 'k|K|g|G', 'left', 'bijection'),
            ('8.2.40', 'JazastaTorDo.DaH', 't|T', 'Q|D|B|G|J', None, 'right_substitute', 'D', 'tripadi', 'seed', 0, 1, 'D', 'right', None),
            ('8.2.66', 'sasajuzo ruH', 's|sajuZ', None, 'PAUSE_OR_VOICED', 'substitute', 'r', 'tripadi', 'seed', 1, 0, 'r', 'left', None),
            ('8.2.68', 'ahan', 'n', 'aha', 'PAUSE_OR_VOICED', 'substitute', 'r', 'tripadi', 'seed', 1, 0, 'r', 'left', None),
            ('8.3.17', 'BoBagoaGoapUrvasya yo.Si', 's|H', 'a|A|o', 'PRAT:aS', 'elide', '', 'tripadi', 'seed', 1, 0, '', 'left', None),
            ('8.3.25', 'mo rAji samaH kvO', 'm', 'sa', 'rA', 'prohibit', 'prohibit', 'tripadi', 'seed', 0, 0, '', 'left', None),
            ('8.3.32', 'Namo hrasvAdaci NamuRnityam', 'N|R|n', 'a|i|u|f|x', 'PRAT:aC', 'augment', 'Namuw', 'samhita', 'seed', 0, 0, '', 'left', 'duplicate'),
            ('8.4.39', 'kzuBnAdizu ca', 'TOKEN:kzuBna', None, None, 'prohibit', 'prohibit', 'tripadi', 'seed', 0, 0, '', 'left', None),
            ('8.4.41', 'zwunA zwuH_rev', 't|T|d|D|n', 'z|w|W|q|Q|R', None, 'bijection_right_substitute', 'w|W|q|Q|R', 'tripadi', 'seed', 0, 1, 'w|W|q|Q|R', 'right', 'bijection'),
            ('8.4.41', 'zwunA zwuH_fwd', 's|t|T|d|D|n', None, 'z|w|W|q|Q|R', 'bijection_substitute', 'z|w|W|q|Q|R', 'tripadi', 'seed', 1, 0, 'z|w|W|q|Q|R', 'left', 'bijection'),
            ('8.4.55', 'Kari ca', 'PRAT:JaL', None, 'PRAT:Kar', 'bijection_substitute', 'k|k|c|c|w|w|t|t|p|p', 'tripadi', 'seed', 1, 0, 'k|k|c|c|w|w|t|t|p|p', 'left', 'bijection'),
            ('8.4.60', 'torli_td', 't|T|d|D', None, 'l', 'substitute', 'l', 'tripadi', 'seed', 1, 0, 'l', 'left', None),
            ('8.4.60', 'torli_n', 'n', None, 'l', 'substitute', 'Ml', 'tripadi', 'seed', 1, 0, 'Ml', 'left', None),
            ('8.4.62', 'Jayo ho.nyatarasyAm', 'h', 't|T|d|D', None, 'right_substitute', 'D', 'tripadi', 'seed', 0, 1, 'D', 'right', None),
            ('8.4.63', 'śaścho_ṭi', 'S', 'c|C|t|T|p|P|k|K', None, 'right_substitute', 'C', 'tripadi', 'seed', 0, 1, 'C', 'right', None),
            ('6.1.76', 'padAntAdvA', 'LONG_VOWEL', None, 'C', 'insert', 'c', 'samhita', 'seed', 0, 0, 'c', 'left', None),
            ('6.1.15', 'vacisvapiyajAdInAM kiti', 'vac', None, 't', 'substitute', 'uc', 'samhita', 'seed', 3, 0, 'uc', 'left', None)
        ]
        for r in seed_rules:
            cur.execute('''
                INSERT INTO rule_configs
                (sutra_id, name, target_context, left_context, right_context, operation, replacement, domain, source, left_consume, right_consume, emit, emit_side, compute_fn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', r)

    rows = cur.execute("SELECT id, sutra_slp1, pada_cheda, sutra_type FROM sutras ORDER BY id").fetchall()

    stats = {
        "total": len(rows),
        "success": 0,
        "failed": 0,
        "updated_rows": 0,
        "inserted_rows": 0,
        "by_category": {},
        "primitives_produced": {
            "elide": 0,
            "exact_substitute": 0,
            "ekadesha_guna": 0,
            "ekadesha_vriddhi": 0,
            "dirgha": 0,
            "purva_rupa": 0,
            "pararupa": 0,
            "prakritibhava": 0,
            "governance": 0,
            "prohibit": 0,
            "other": 0
        }
    }

    for sid, name, pc, st in rows:
        cat = st.split('$')[0] if st and '$' in st else (st[:2] if st else 'V')
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        try:
            spec = DeterministicSutraParser.parse(sid, name or sid, pc or "", sutra_type=st or "V")
            stats["success"] += 1

            op_type = getattr(spec.operation, "op_type", "other")
            if op_type in stats["primitives_produced"]:
                stats["primitives_produced"][op_type] += 1
            else:
                stats["primitives_produced"]["other"] += 1

            if update_db:
                existing = cur.execute("SELECT id, source FROM rule_configs WHERE sutra_id=?", (sid,)).fetchall()
                tgt_str = getattr(spec.target_context, 'pratyahara', None) or getattr(spec.target_context, 'exact_text', None) if spec.target_context else None
                lft_str = getattr(spec.left_context, 'pratyahara', None) or getattr(spec.left_context, 'exact_text', None) if spec.left_context else None
                rgt_str = getattr(spec.right_context, 'pratyahara', None) or getattr(spec.right_context, 'exact_text', None) if spec.right_context else None
                op = spec.operation
                dom = spec.governance.get("domain", "sapada")

                if existing:
                    for rid, rsource in existing:
                        if rsource not in ("seed", "vartika"):
                            cur.execute("""
                                UPDATE rule_configs
                                SET target_context=COALESCE(NULLIF(target_context, ''), ?),
                                    left_context=COALESCE(NULLIF(left_context, ''), ?),
                                    right_context=COALESCE(NULLIF(right_context, ''), ?),
                                    operation=?, replacement=?, source='deterministic_parser',
                                    left_consume=?, right_consume=?, emit=?, emit_side=?, compute_fn=?
                                WHERE id=?
                            """, (tgt_str, lft_str, rgt_str, op.op_type, op.substitute,
                                  op.left_consume, op.right_consume, op.emit, op.emit_side, op.compute_fn, rid))
                            stats["updated_rows"] += 1
                else:
                    cur.execute("""
                        INSERT INTO rule_configs (
                            sutra_id, name, target_context, left_context, right_context,
                            operation, replacement, domain, source,
                            left_consume, right_consume, emit, emit_side, compute_fn
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'deterministic_parser', ?, ?, ?, ?, ?)
                    """, (sid, name or sid, tgt_str, lft_str, rgt_str, op.op_type, op.substitute, dom,
                          op.left_consume, op.right_consume, op.emit, op.emit_side, op.compute_fn))
                    stats["inserted_rows"] += 1

        except Exception as e:
            stats["failed"] += 1

    if update_db:
        conn.commit()

    conn.close()
    return stats


if __name__ == "__main__":
    update_flag = "--update-db" in sys.argv
    print(f"Running deterministic batch parser on all Aṣṭādhyāyī sūtras (update_db={update_flag})...")
    res = run_batch_validation(update_db=update_flag)
    print(f"Total Sūtras Processed: {res['total']}")
    print(f"Successfully Parsed to Primitives: {res['success']}")
    print(f"Failed: {res['failed']}")
    if update_flag:
        print(f"Database Rows Updated: {res['updated_rows']}")
        print(f"Database Rows Inserted: {res['inserted_rows']}")
    print("\nBreakdown by Sūtra Category:")
    for k, v in sorted(res['by_category'].items()):
        print(f"  {k}: {v}")
    print("\nPrimitives Output Distribution:")
    for k, v in sorted(res['primitives_produced'].items(), key=lambda x: -x[1]):
        if v > 0:
            print(f"  {k}: {v}")

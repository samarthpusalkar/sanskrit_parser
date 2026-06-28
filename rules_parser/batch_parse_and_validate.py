"""
Batch Sūtra Parser and Validator.

Executes the DeterministicSutraParser across all ~4,000 sūtras in sanskrit_master.db,
reports extraction statistics across categories (Vidhi, Sañjñā, Paribhāṣā, Adhikāra, Atideśa),
and optionally updates alignment with rule_configs.
"""

import sqlite3
import os
import sys
from rules_parser.ss_parser import SamastasutraParser


def run_batch_validation(db_path: str = "data/sanskrit_master.db", update_db: bool = False) -> dict:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if update_db:
        # Clear out existing rule_configs generated from previous parser runs
        cur.execute("DELETE FROM rule_configs WHERE source='deterministic_parser' OR source='ss_parser' OR source='seed'")
        
    rows = cur.execute("SELECT id, sutra_slp1, pada_cheda, sutra_type, samasta_sutra, anuvrtti, adhikara FROM sutras ORDER BY id").fetchall()

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

    for sid, name, pc, st, ss, an, ad in rows:
        cat = st.split('$')[0] if st and '$' in st else (st[:2] if st else 'V')
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        try:
            spec = SamastasutraParser.parse(sid, name or sid, ss or "", an or "", ad or "", pc or "", st or "V", cur)
            stats["success"] += 1

            op_type = getattr(spec.operation, "op_type", "other")
            if op_type in stats["primitives_produced"]:
                stats["primitives_produced"][op_type] += 1
            else:
                stats["primitives_produced"]["other"] = stats["primitives_produced"].get("other", 0) + 1

            if update_db:
                tgt_str = getattr(spec.target_context, 'pratyahara', None) or getattr(spec.target_context, 'exact_text', None) if spec.target_context else None
                lft_str = getattr(spec.left_context, 'pratyahara', None) or getattr(spec.left_context, 'exact_text', None) if spec.left_context else None
                rgt_str = getattr(spec.right_context, 'pratyahara', None) or getattr(spec.right_context, 'exact_text', None) if spec.right_context else None
            if update_db:
                existing = cur.execute("SELECT id, source FROM rule_configs WHERE sutra_id=?", (sid,)).fetchall()
                
                def _fmt_cond(c):
                    if not c: return None
                    if getattr(c, 'exact_text', None) and getattr(c, 'exact_text').lower().startswith('savar'): return c.exact_text
                    if getattr(c, 'pratyahara', None):
                        base = f"PRAT:{c.pratyahara}"
                        if getattr(c, 'exact_text', None):
                            base += f"|EXACT:{c.exact_text}"
                        return base
                    if getattr(c, 'tokens_required', None): return f"TOKEN:{'|'.join(c.tokens_required)}"
                    if getattr(c, 'tags_required', None): return f"TAG:{'|'.join(c.tags_required)}"
                    if getattr(c, 'features_required', None): return f"FEAT:{'|'.join(c.features_required)}"
                    return c.exact_text

                tgt_str = _fmt_cond(spec.target_context)
                lft_str = _fmt_cond(spec.left_context)
                rgt_str = _fmt_cond(spec.right_context)
                
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
                                    operation=?, replacement=?, source='ss_parser',
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
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ss_parser', ?, ?, ?, ?, ?)
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

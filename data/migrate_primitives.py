"""
Migration script to add universal primitive columns to rule_configs table.
"""
import sqlite3
from pathlib import Path

def migrate(db_path: str = None):
    if db_path is None:
        db_path = str(Path(__file__).parent / "sanskrit_master.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cols = {row[1] for row in cur.execute("PRAGMA table_info(rule_configs)").fetchall()}
    new_cols = [
        ("left_consume", "INTEGER DEFAULT 0"),
        ("right_consume", "INTEGER DEFAULT 0"),
        ("emit", "TEXT DEFAULT ''"),
        ("emit_side", "TEXT DEFAULT 'left'"),
        ("compute_fn", "TEXT DEFAULT NULL")
    ]
    
    for col_name, col_def in new_cols:
        if col_name not in cols:
            cur.execute(f"ALTER TABLE rule_configs ADD COLUMN {col_name} {col_def}")
            
    # Populate values from legacy operation and replacement
    rows = cur.execute("SELECT id, operation, replacement FROM rule_configs").fetchall()
    
    mapping = {
        "elide":                    (1, 0, "",    "left",  None),
        "pararupa":                 (1, 0, "",    "left",  None),
        "visarga_utva":             (2, 0, "o",   "left",  None),
        "anusvara":                 (1, 0, "M",   "left",  None),
        "purva_rupa":               (0, 1, "'",   "right", None),
        "prakritibhava":            (0, 0, "",    "left",  None),
        "non_operational":          (0, 0, "",    "left",  None),
        "external_block":           (0, 0, "",    "left",  None),
        "governance":               (0, 0, "",    "left",  None),
        "prohibit":                 (0, 0, "",    "left",  None),
        "dirgha":                   (1, 1, "",    "left",  "dirgha"),
        "ekadesha_savarna_dirgha":  (1, 1, "",    "left",  "dirgha"),
        "merge_savarna":            (1, 1, "",    "left",  "dirgha"),
        "ekadesha_guna":            (1, 1, "",    "left",  "guna"),
        "ekadesha_vriddhi":         (1, 1, "",    "left",  "vriddhi"),
        "ro_ri_dirgha":             (2, 0, "",    "left",  "savarna_long"),
        "dhra_lopa_dirgha":         (2, 0, "",    "left",  "savarna_long"),
        "natva":                    (0, 0, "",    "left",  "natva"),
        "shatva":                   (0, 0, "",    "left",  "shatva"),
    }
    
    for row_id, op_type, sub in rows:
        sub = sub or ""
        if op_type == "sanjna_substitute":
            if sub == "guna":
                lc, rc, em, es, cf = (1, 1, "", "left", "guna")
            elif sub == "vriddhi":
                lc, rc, em, es, cf = (1, 1, "", "left", "vriddhi")
            elif sub == "dirgha":
                lc, rc, em, es, cf = (1, 1, "", "left", "dirgha")
            else:
                lc, rc, em, es, cf = (1, 0, sub, "left", None)
        elif op_type in {"substitute", "exact_substitute"}:
            lc, rc, em, es, cf = (1, 0, sub, "left", None)
        elif op_type == "bijection_substitute":
            lc, rc, em, es, cf = (1, 0, sub, "left", "bijection")
        elif op_type == "bijection_right_substitute":
            lc, rc, em, es, cf = (0, 1, sub, "right", "bijection")
        elif op_type == "insert":
            lc, rc, em, es, cf = (0, 0, sub, "left", None)
        elif op_type == "merge":
            lc, rc, em, es, cf = (1, 1, sub, "left", None)
        elif op_type == "right_substitute":
            lc, rc, em, es, cf = (0, 1, sub, "right", None)
        elif op_type == "right_prepend":
            lc, rc, em, es, cf = (0, 0, sub, "right", None)
        else:
            lc, rc, em, es, cf = mapping.get(op_type, (1, 0, sub, "left", None))
            
        cur.execute(
            "UPDATE rule_configs SET left_consume=?, right_consume=?, emit=?, emit_side=?, compute_fn=? WHERE id=?",
            (lc, rc, em, es, cf, row_id)
        )
        
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

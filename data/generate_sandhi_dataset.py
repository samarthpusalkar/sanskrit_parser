"""
Heuristic Reverse Sandhi Dataset Generator.

Generates training data for a neural reverse-sandhi decoder model by:
  1. Drawing pairs of Sanskrit stems/forms from the lexicon database.
  2. Computing the forward sandhi join (using the Pāṇinian rule engine).
  3. Writing (surface, [token1, token2, ...]) records to a JSONL output file.

Each record is a ground-truth training example for a seq2seq model that learns to
split sandhi-merged Sanskrit text back into its constituent tokens.

Usage:
    python data/generate_sandhi_dataset.py --output data/sandhi_train.jsonl --size 10000
    python data/generate_sandhi_dataset.py --output data/sandhi_train.jsonl --size 50000 --max-parts 3
"""

import sys
import os
import json
import argparse
import random
import sqlite3
import time
from pathlib import Path
from typing import List, Tuple, Optional, Iterator

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Sampling helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_db_path() -> str:
    return str(_REPO_ROOT / "data" / "sanskrit_master.db")


def _load_surface_forms(db_path: str, limit: int = 0) -> List[str]:
    """Load inflected surface forms (dhatu_forms + pratipadika stems) from lexicon."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    forms: List[str] = []

    # Verbal forms (conjugated — most likely to appear in text)
    query = "SELECT form_iast FROM dhatu_forms WHERE form_iast != '' AND LENGTH(form_iast) BETWEEN 2 AND 16"
    if limit:
        query += f" ORDER BY RANDOM() LIMIT {limit * 2}"
    for (form,) in cur.execute(query):
        if form:
            forms.append(form.strip())

    # Nominal stems
    query2 = "SELECT word_iast FROM pratipadikas WHERE word_iast != '' AND LENGTH(word_iast) BETWEEN 2 AND 12"
    if limit:
        query2 += f" ORDER BY RANDOM() LIMIT {limit}"
    for (stem,) in cur.execute(query2):
        if stem:
            forms.append(stem.strip())

    conn.close()
    random.shuffle(forms)
    return forms


def _load_stems_only(db_path: str, limit: int = 0) -> List[str]:
    """Load nominal stems for the first token position (more common as first element)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    stems: List[str] = []
    query = "SELECT word_iast FROM pratipadikas WHERE word_iast != '' AND LENGTH(word_iast) BETWEEN 2 AND 10"
    if limit:
        query += f" ORDER BY RANDOM() LIMIT {limit}"
    for (stem,) in cur.execute(query):
        if stem:
            stems.append(stem.strip())
    conn.close()
    return stems


# ─────────────────────────────────────────────────────────────────────────────
# Record generation
# ─────────────────────────────────────────────────────────────────────────────

def _join_tokens(tokens: List[str]) -> Optional[str]:
    """Apply forward sandhi to join a list of tokens into a surface string."""
    try:
        from morphology.sandhi import SandhiEngine
        result = tokens[0]
        for tok in tokens[1:]:
            result = SandhiEngine.join(result, tok)
        return result
    except Exception:
        return None


def _tokens_change_after_join(tokens: List[str], joined: str) -> bool:
    """Return True if sandhi actually transformed the tokens (non-trivial join)."""
    trivial = "".join(tokens)
    return joined != trivial


# ─────────────────────────────────────────────────────────────────────────────
# Frequency Weighting & Configuration
# ─────────────────────────────────────────────────────────────────────────────
HIGH_FREQ_TOKENS = [
    "iti", "eva", "ca", "api", "pra", "vi", "sam", "saḥ", "tat",
    "na", "tu", "hi", "yad", "tad", "kim", "iva", "yathā", "tathā", "atra", "tatra"
]
FREQ_WEIGHT_PROB = 0.35  # 35% of the time, inject a high-freq token
NO_OP_PROB = 0.15        # 15% of records should be intentional no-ops

def _classify_sandhi(tokens: List[str], joined: str) -> str:
    """Classify the sandhi type based on surface characteristics."""
    if len(tokens) < 2:
        return "none"
    if "".join(tokens) == joined:
        return "no_op"
        
    boundary = tokens[0][-1] if tokens[0] else ""
    next_start = tokens[1][0] if tokens[1] else ""
    joined_mid = joined[len(tokens[0]) - 1:len(tokens[0]) + 2] if len(joined) > len(tokens[0]) else ""

    vowels = set("aāiīuūṛṝḷeo")
    nasals = set("ñṇnmṅ")
    stops = set("kgcjṭḍtdpb")

    if boundary in vowels and next_start in vowels:
        if joined_mid and joined_mid[0] in vowels and len(joined_mid) == 1:
            return "vowel_dirgha"
        elif joined_mid and joined_mid[0] in vowels:
            return "vowel_guna"
        return "vowel_sandhi"
    elif boundary in {"ḥ", "H"}:
        return "visarga_sandhi"
    elif boundary in stops and next_start in nasals:
        return "consonant_assimilation"
    elif boundary in stops and next_start in stops:
        return "consonant_sandhi"
    elif boundary in vowels and next_start in stops:
        return "vowel_consonant"
    return "other"


def generate_2part_records(
    forms: List[str],
    n: int,
    require_transformation: bool = True,
) -> Iterator[dict]:
    """Generate n 2-token sandhi records with frequency weighting and no-op injection."""
    forms = [f for f in forms if f and len(f) >= 2]
    random.shuffle(forms)
    generated = 0
    i = 0
    while generated < n and i < len(forms) - 1:
        # Frequency weighting injection
        if random.random() < FREQ_WEIGHT_PROB:
            tok1 = random.choice(HIGH_FREQ_TOKENS) if random.random() < 0.5 else forms[i % len(forms)]
            tok2 = random.choice(HIGH_FREQ_TOKENS) if tok1 != random.choice(HIGH_FREQ_TOKENS) else forms[(i + 7) % len(forms)]
        else:
            tok1 = forms[i % len(forms)]
            tok2 = forms[(i + 7) % len(forms)]
            
        i += 1
        if tok1 == tok2:
            continue
            
        joined = _join_tokens([tok1, tok2])
        if joined is None:
            continue
            
        is_trivial = not _tokens_change_after_join([tok1, tok2], joined)
        
        # Handle NO-OP probability
        if is_trivial:
            # If we require transformation and aren't picking a no-op this time, skip
            if require_transformation and random.random() >= NO_OP_PROB:
                continue
        else:
            # If we happened to roll a no-op but the sandhi isn't trivial, we just keep it
            # (Or we could skip to strictly enforce ratios, but this is simpler)
            pass

        sandhi_type = _classify_sandhi([tok1, tok2], joined)
        yield {
            "surface": joined,
            "tokens": [tok1, tok2],
            "num_tokens": 2,
            "sandhi_type": sandhi_type,
            "difficulty": "no_op" if is_trivial else ("easy" if sandhi_type.startswith("vowel") else "medium"),
        }
        generated += 1


def generate_3part_records(
    forms: List[str],
    n: int,
) -> Iterator[dict]:
    """Generate n 3-token sandhi records with frequency weighting."""
    forms = [f for f in forms if f and len(f) >= 2]
    random.shuffle(forms)
    generated = 0
    i = 0
    while generated < n and i < len(forms) - 2:
        if random.random() < FREQ_WEIGHT_PROB:
            tok1 = random.choice(HIGH_FREQ_TOKENS)
            tok2 = forms[i % len(forms)]
            tok3 = random.choice(HIGH_FREQ_TOKENS) if random.random() < 0.3 else forms[(i + 11) % len(forms)]
        else:
            tok1 = forms[i % len(forms)]
            tok2 = forms[(i + 11) % len(forms)]
            tok3 = forms[(i + 23) % len(forms)]
            
        i += 1
        if len({tok1, tok2, tok3}) < 3:
            continue
            
        # Join progressively
        joined = _join_tokens([tok1, tok2, tok3])
        if joined is None:
            continue
            
        is_trivial = not _tokens_change_after_join([tok1, tok2, tok3], joined)
        if is_trivial and random.random() >= NO_OP_PROB:
            continue
            
        yield {
            "surface": joined,
            "tokens": [tok1, tok2, tok3],
            "num_tokens": 3,
            "sandhi_type": "no_op" if is_trivial else "multi_part",
            "difficulty": "no_op" if is_trivial else "hard",
        }
        generated += 1


# ─────────────────────────────────────────────────────────────────────────────
# Dataset statistics
# ─────────────────────────────────────────────────────────────────────────────

def print_stats(records: List[dict]) -> None:
    from collections import Counter
    print(f"\n{'='*60}")
    print(f"  Dataset Statistics")
    print(f"{'='*60}")
    print(f"  Total records     : {len(records)}")
    by_parts = Counter(r["num_tokens"] for r in records)
    for k, v in sorted(by_parts.items()):
        print(f"  {k}-token records  : {v:>6} ({100*v/len(records):.1f}%)")
    by_type = Counter(r["sandhi_type"] for r in records)
    print(f"\n  Sandhi type distribution:")
    for k, v in by_type.most_common():
        print(f"    {k:<30} {v:>6} ({100*v/len(records):.1f}%)")
    avg_surface_len = sum(len(r["surface"]) for r in records) / len(records)
    print(f"\n  Avg surface length: {avg_surface_len:.1f} chars")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate heuristic reverse-sandhi training dataset."
    )
    parser.add_argument("--output", "-o", default="data/sandhi_train.jsonl",
                        help="Output JSONL file path.")
    parser.add_argument("--size", "-n", type=int, default=5000,
                        help="Total number of records to generate.")
    parser.add_argument("--max-parts", type=int, default=3,
                        help="Maximum number of tokens per record (2 or 3).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility.")
    parser.add_argument("--db", default=None,
                        help="Override path to sanskrit_master.db.")
    parser.add_argument("--stats", action="store_true",
                        help="Print dataset statistics after generation.")
    parser.add_argument("--no-filter", action="store_true",
                        help="Include trivial (no transformation) pairs too.")
    args = parser.parse_args()

    random.seed(args.seed)
    db_path = args.db or _get_db_path()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[*] Loading lexicon from: {db_path}")
    t0 = time.time()
    forms = _load_surface_forms(db_path, limit=args.size * 3)
    print(f"[+] Loaded {len(forms)} surface forms in {time.time()-t0:.1f}s")

    # Split budget: 70% 2-token, 30% 3-token
    n2 = int(args.size * 0.7) if args.max_parts >= 2 else args.size
    n3 = args.size - n2 if args.max_parts >= 3 else 0

    print(f"[*] Generating {n2} 2-token records + {n3} 3-token records...")
    t1 = time.time()

    records = []
    seen_surfaces = set()

    for rec in generate_2part_records(forms, n2 * 2, require_transformation=not args.no_filter):
        if rec["surface"] not in seen_surfaces:
            records.append(rec)
            seen_surfaces.add(rec["surface"])
        if len([r for r in records if r["num_tokens"] == 2]) >= n2:
            break

    for rec in generate_3part_records(forms, n3 * 3):
        if rec["surface"] not in seen_surfaces:
            records.append(rec)
            seen_surfaces.add(rec["surface"])
        if len([r for r in records if r["num_tokens"] == 3]) >= n3:
            break

    random.shuffle(records)
    print(f"[+] Generated {len(records)} unique records in {time.time()-t1:.1f}s")

    # Write JSONL
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[+] Wrote dataset to: {out_path}")

    if args.stats:
        print_stats(records)

    # Write a small sample for inspection
    sample_path = out_path.with_suffix(".sample.json")
    with sample_path.open("w", encoding="utf-8") as f:
        json.dump(records[:20], f, ensure_ascii=False, indent=2)
    print(f"[+] Sample (first 20) written to: {sample_path}")


if __name__ == "__main__":
    main()

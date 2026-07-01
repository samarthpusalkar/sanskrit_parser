#!/usr/bin/env python3
"""
LLM Sutra Extractor — tools/llm_sutra_extractor.py

Extracts structured metadata from Pāṇinian sūtras using an LLM (Ollama).
Processes one chapter at a time with validation. Caches results in the DB.

Uses HTTP API (localhost:11434) with commentary context and anuvṛtti context.

Usage:
    python tools/llm_sutra_extractor.py --chapter 6.1
    python tools/llm_sutra_extractor.py --chapter 6.1 --force
    python tools/llm_sutra_extractor.py --chapter 6.1 --dry-run
    python tools/llm_sutra_extractor.py --chapter 6.1 --model deepseek-v4-pro:cloud
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.recorder import record_attempt, record_hurdle

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
COMMENTARY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ashtadhyayi-data", "sutraani")
OLLAMA_URL = "http://localhost:11434/api/generate"

EXTRACTION_SCHEMA = {
    "operation_type": "one of: exact_substitute, merge, elide, augment, prohibit, prakritibhava, bijection, dirgha, guna, vrddhi, yan, visarga_sandhi, anusvara, natva, samprasarana, pararupa, purva_rupa, non_operational. For guna use 'guna', for vrddhi use 'vrddhi', NOT 'merge'.",
    "target": "the phoneme class being operated on, as a SINGLE pratyahara in SLP1 (e.g. 'aK' for all vowels, 'iK' for i/u/ṛ/ḷ, 'aC' for vowels). Do NOT write descriptive phrases like 'a A ac'. If the target is the preceding vowel, use the pratyahara for that vowel class (e.g. 'a' or 'aK').",
    "left_context": "conditioning left context as a pratyahara or phoneme in SLP1, or null",
    "right_context": "conditioning right context as a pratyahara or phoneme in SLP1, or null. For 'before a vowel' use 'aC'. For 'homogeneous' use 'savarRa'.",
    "replacement": "what the target becomes: for guna use 'guRa', for vrddhi use 'vfdDi', for dirgha use 'dIrGa', for yan use 'yaR'. SLP1.",
    "conditioning_factors": "array of factors making this antaraṅga (inner) vs bahiraṅga (outer)",
    "applicable_paribhasas": "array of paribhāṣā sūtra IDs (e.g., 1.1.50)",
    "domain": "one of: sapada, tripadi, samhita, angasya",
    "anuvrtti_carries": "object: what this sūtra carries forward via anuvṛtti",
    "commentary_notes": "any commentary context needed",
    "confidence": "number 0-1",
    "hurdles": "array of strings: obstacles to extraction",
    "sanjna_required": "array of saṃjñā (technical-label) names the token must carry for this rule to apply (e.g. ['dhatu'], ['sup']). Empty array if none.",
    "prohibit_if_sanjna": "array of saṃjñā names that block this rule if the token carries any of them. Empty array if none.",
    "sthani_phoneme": "the original (sthāni) phoneme to match, if the rule conditions on the pre-mutation boundary (SLP1 or null)",
    "morphological_category": "the morphological category this rule applies to, if any (e.g. 'dhatu', 'sup', 'ting', 'krt', 'avyaya', null otherwise)"
}


def ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_extracted_metadata (
            sutra_id TEXT PRIMARY KEY,
            operation_type TEXT,
            target TEXT,
            left_context TEXT,
            right_context TEXT,
            replacement TEXT,
            conditioning_factors TEXT,
            applicable_paribhasas TEXT,
            domain TEXT,
            anuvrtti_carries TEXT,
            commentary_notes TEXT,
            confidence REAL,
            hurdles TEXT,
            extracted_at TEXT,
            model TEXT,
            sanjna_required TEXT DEFAULT '[]',
            prohibit_if_sanjna TEXT DEFAULT '[]',
            sthani_phoneme TEXT,
            morphological_category TEXT
        )
    """)
    # Migration: add the new saṃjñā columns if they don't exist.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(llm_extracted_metadata)").fetchall()}
    for col, decl in [
        ("sanjna_required", "TEXT DEFAULT '[]'"),
        ("prohibit_if_sanjna", "TEXT DEFAULT '[]'"),
        ("sthani_phoneme", "TEXT"),
        ("morphological_category", "TEXT"),
    ]:
        if col not in cols:
            conn.execute(f"ALTER TABLE llm_extracted_metadata ADD COLUMN {col} {decl}")
    conn.commit()


def get_sutras_for_chapter(conn: sqlite3.Connection, chapter: str) -> List[Dict]:
    pattern = f"{chapter}.%"
    rows = conn.execute(
        "SELECT id, sutra_dev, pada_cheda, sutra_type, samasta_sutra, anuvrtti, adhikara "
        "FROM sutras WHERE id LIKE ? ORDER BY id",
        (pattern,)
    ).fetchall()
    return [
        {"id": r[0], "sutra_dev": r[1] or "", "pada_cheda": r[2] or "",
         "sutra_type": r[3] or "", "samasta_sutra": r[4] or "",
         "anuvrtti": r[5] or "", "adhikara": r[6] or ""}
        for r in rows
    ]


def is_cached(conn: sqlite3.Connection, sutra_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM llm_extracted_metadata WHERE sutra_id = ?", (sutra_id,)
    ).fetchone()
    return row is not None


def load_commentary(sutra_id: str) -> str:
    """Load commentary context for a sūtra from the Vasu English translation."""
    vasu_path = os.path.join(COMMENTARY_DIR, "vasu_english.txt")
    if not os.path.exists(vasu_path):
        return ""

    try:
        with open(vasu_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        parts = sutra_id.split(".")
        if len(parts) == 3:
            adhyaya, pada, sutra_no = parts
            numeric_id = f"{adhyaya}{pada}{int(sutra_no):03d}"
        else:
            numeric_id = sutra_id.replace(".", "")
        commentary = data.get(numeric_id, "")
        if commentary:
            return commentary[:500] + "..." if len(commentary) > 500 else commentary
        return ""
    except Exception:
        return ""


def get_previous_sutras(conn: sqlite3.Connection, sutra_id: str, count: int = 5) -> List[Dict]:
    """Get previous N sūtras for anuvṛtti context, including samasta/anuvrtti/adhikara."""
    rows = conn.execute(
        "SELECT id, sutra_dev, samasta_sutra, anuvrtti, adhikara "
        "FROM sutras WHERE id < ? ORDER BY id DESC LIMIT ?",
        (sutra_id, count)
    ).fetchall()
    out = []
    for r in reversed(rows):
        out.append({"id": r[0], "text": r[1] or "",
                    "samasta_sutra": r[2] or "", "anuvrtti": r[3] or "",
                    "adhikara": r[4] or ""})
    return out


def is_tripadi(sutra_id: str) -> bool:
    parts = sutra_id.split(".")
    if len(parts) >= 2:
        try:
            adhyaya = int(parts[0])
            pada = int(parts[1])
            return adhyaya == 8 and pada >= 2
        except ValueError:
            pass
    return False


def build_prompt(sutra: Dict, previous_sutras: List[Dict], commentary: str) -> str:
    """Build a rich LLM prompt with commentary and anuvṛtti context."""
    sutra_id = sutra["id"]
    tripadi_note = ""
    if is_tripadi(sutra_id):
        tripadi_note = """
IMPORTANT: This sūtra belongs to the Tripāḍī (8.2–8.4), which has special ordering rules:
- Pūrvatrāsiddham (8.2.1): rules in later pādas are invisible to earlier ones.
- Rules must be applied in strict chapter order within the Tripāḍī.
"""

    # Expanded sūtra with anuvṛtti already filled in (samasta_sutra).
    samasta_section = ""
    if sutra.get("samasta_sutra"):
        samasta_section = (
            f"\nExpanded sūtra (samasta, with anuvṛtti words filled in): "
            f"{sutra['samasta_sutra']}\n"
        )

    # Anuvṛtti carried into THIS sūtra (from the DB anuvrtti column).
    anuvrtti_section = ""
    if sutra.get("anuvrtti"):
        anuvrtti_section = (
            f"\nAnuvṛtti carried into this sūtra: {sutra['anuvrtti']}\n"
        )

    # Adhikāra (governing scope) in effect for this sūtra.
    adhikara_section = ""
    if sutra.get("adhikara"):
        adhikara_section = (
            f"\nAdhikāra (governing scope) in effect: {sutra['adhikara']}\n"
        )

    prev_context = ""
    if previous_sutras:
        prev_context = "\nPrevious sūtras (for anuvṛtti context):\n"
        for ps in previous_sutras:
            prev_context += f"  {ps['id']}: {ps['text']}"
            if ps.get("samasta_sutra"):
                prev_context += f"  [expanded: {ps['samasta_sutra']}]"
            if ps.get("anuvrtti"):
                prev_context += f"  [carries: {ps['anuvrtti']}]"
            prev_context += "\n"

    commentary_section = ""
    if commentary:
        commentary_section = f"\nCommentary (Vasu English):\n{commentary}\n"

    return f"""You are a Pāṇinian grammar expert. Extract structured metadata from this Sanskrit sūtra.

Sūtra ID: {sutra_id}
Sūtra Text (Devanagari): {sutra['sutra_dev']}
Pada Cheda (word segmentation): {sutra['pada_cheda']}
Sūtra Type: {sutra['sutra_type']}
{samasta_section}{anuvrtti_section}{adhikara_section}{tripadi_note}{prev_context}{commentary_section}
The expanded sūtra (samasta) and anuvṛtti fields show which words are carried over from earlier sūtras — use them to determine the full conditioning context, not just the literal sūtra text.

Extract the following JSON object. All phonemes should be in SLP1 transliteration.
If you cannot determine a field, use null. Be precise about conditioning contexts.

Expected JSON schema:
{json.dumps(EXTRACTION_SCHEMA, indent=2)}

Return ONLY valid JSON, no explanation."""


def build_batch_prompt(sutras: List[Dict], commentary_map: Dict[str, str]) -> str:
    """Build a batch prompt for definitional (saṃjñā/paribhāṣā) sūtras of a pāda.

    Requests a JSON ARRAY of extraction objects, one per sūtra, in order.
    The full pāda scope is visible so the LLM understands adhikāra/anuvṛtti natively.
    """
    lines = ["You are a Pāṇinian grammar expert. Extract structured metadata for EACH of the following sūtras in order.\n"]
    lines.append("These are definitional sūtras (saṃjñā definitions or paribhāṣā meta-rules) of a single pāda. The adhikāra and anuvṛtti scope spans the whole list — use the full context.\n")
    for i, s in enumerate(sutras, 1):
        lines.append(f"\n--- Sūtra {i}: {s['id']} ---")
        lines.append(f"Text (Devanagari): {s['sutra_dev']}")
        lines.append(f"Pada Cheda: {s['pada_cheda']}")
        lines.append(f"Sūtra Type: {s['sutra_type']}")
        if s.get("samasta_sutra"):
            lines.append(f"Expanded (samasta): {s['samasta_sutra']}")
        if s.get("anuvrtti"):
            lines.append(f"Anuvṛtti carried: {s['anuvrtti']}")
        if s.get("adhikara"):
            lines.append(f"Adhikāra: {s['adhikara']}")
        comm = commentary_map.get(s["id"], "")
        if comm:
            lines.append(f"Commentary (Vasu): {comm}")
    lines.append("\n\nReturn a JSON ARRAY with one object per sūtra above, in the SAME ORDER.")
    lines.append("Each object must follow this schema:")
    lines.append(json.dumps(EXTRACTION_SCHEMA, indent=2))
    lines.append("\nAll phonemes in SLP1. If you cannot determine a field, use null.")
    lines.append("\nReturn ONLY the JSON array, no explanation.")
    return "\n".join(lines)


def call_ollama(prompt: str, model: str = "deepseek-v4-pro:cloud",
                max_retries: int = 5) -> Optional[Dict]:
    """Call Ollama HTTP API to extract metadata. Retries on 429 with backoff."""
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }).encode("utf-8")

            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                response_text = result.get("response", "")

            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start == -1 or end == 0:
                return {"error": "No JSON found in response"}
            json_str = response_text[start:end]
            return json.loads(json_str)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = min(2 ** (attempt + 2), 60)
                time.sleep(wait)
                continue
            return {"error": f"Ollama API error: HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {"error": f"Ollama API error: {e}"}
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Ollama API exhausted retries"}


def call_ollama_array(prompt: str, model: str = "deepseek-v4-pro:cloud",
                      max_retries: int = 5) -> Optional[List[Dict]]:
    """Call Ollama and parse a JSON ARRAY response. Retries on 429."""
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": model, "prompt": prompt,
                "stream": False, "format": "json"
            }).encode("utf-8")
            req = urllib.request.Request(OLLAMA_URL, data=payload,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
                response_text = result.get("response", "")
            start = response_text.find("[")
            end = response_text.rfind("]") + 1
            if start == -1 or end == 0:
                return [{"error": "No JSON array found in response"}]
            arr = json.loads(response_text[start:end])
            if not isinstance(arr, list):
                return [{"error": "Response was not a JSON array"}]
            return arr
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(min(2 ** (attempt + 2), 60))
                continue
            return [{"error": f"HTTP {e.code}: {e.reason}"}]
        except urllib.error.URLError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return [{"error": f"URLError: {e}"}]
        except Exception as e:
            return [{"error": str(e)}]
    return [{"error": "exhausted retries"}]


def store_batch_extraction(conn: sqlite3.Connection, sutra_id: str,
                            extraction: Dict, model: str):
    """Store one element of a batch extraction (same schema as store_extraction)."""
    store_extraction(conn, sutra_id, extraction, model)


def _is_definitional(sutra: Dict) -> bool:
    """A definitional sūtra: saṃjñā (S$) or paribhāṣā (P$)."""
    st = sutra.get("sutra_type", "") or ""
    return st.startswith("S$") or st.startswith("P$")


def store_extraction(conn: sqlite3.Connection, sutra_id: str, extraction: Dict, model: str):
    conn.execute("""
        INSERT OR REPLACE INTO llm_extracted_metadata
        (sutra_id, operation_type, target, left_context, right_context, replacement,
         conditioning_factors, applicable_paribhasas, domain, anuvrtti_carries,
         commentary_notes, confidence, hurdles, extracted_at, model,
         sanjna_required, prohibit_if_sanjna, sthani_phoneme, morphological_category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sutra_id,
        extraction.get("operation_type"),
        extraction.get("target"),
        extraction.get("left_context"),
        extraction.get("right_context"),
        extraction.get("replacement"),
        json.dumps(extraction.get("conditioning_factors", [])),
        json.dumps(extraction.get("applicable_paribhasas", [])),
        extraction.get("domain"),
        json.dumps(extraction.get("anuvrtti_carries", {})),
        extraction.get("commentary_notes"),
        extraction.get("confidence", 0),
        json.dumps(extraction.get("hurdles", [])),
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        model,
        json.dumps(extraction.get("sanjna_required", [])),
        json.dumps(extraction.get("prohibit_if_sanjna", [])),
        extraction.get("sthani_phoneme"),
        extraction.get("morphological_category"),
    ))
    conn.commit()


def extract_chapter(chapter: str, force: bool = False, dry_run: bool = False,
                    model: str = "deepseek-v4-pro:cloud", delay: float = 2.0,
                    max_sutras: int = 0, batch_definitions: bool = False):
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    sutras = get_sutras_for_chapter(conn, chapter)
    print(f"Chapter {chapter}: {len(sutras)} sūtras found")

    extracted = 0
    cached = 0
    failed = 0

    if batch_definitions:
        # Partition into definitional (S$/P$) and operational (V$/others).
        definitional = [s for s in sutras if _is_definitional(s)]
        operational = [s for s in sutras if not _is_definitional(s)]
        print(f"  batch-definitions: {len(definitional)} definitional, {len(operational)} operational")

        # Phase A: batch-extract definitional sūtras not yet cached.
        to_batch = [s for s in definitional if force or not is_cached(conn, s["id"])]
        if to_batch:
            commentary_map = {s["id"]: load_commentary(s["id"]) for s in to_batch}
            prompt = build_batch_prompt(to_batch, commentary_map)
            if dry_run:
                print(f"\n--- BATCH PROMPT ({len(to_batch)} sūtras) ---")
                print(prompt[:1500])
                print("...")
            else:
                print(f"  Batch-extracting {len(to_batch)} definitional sūtras...", end=" ")
                sys.stdout.flush()
                arr = call_ollama_array(prompt, model)
                if arr is None or (arr and "error" in arr[0]):
                    err = arr[0].get("error", "unknown") if arr else "no response"
                    print(f"FAIL ({err})")
                    # Fall back to per-sūtra for all batch sutras.
                    for s in to_batch:
                        sid = s["id"]
                        prev = get_previous_sutras(conn, sid, count=5)
                        p = build_prompt(s, prev, load_commentary(sid))
                        r = call_ollama(p, model)
                        if r and "error" not in r:
                            store_extraction(conn, sid, r, model)
                            extracted += 1
                            print(f"\n    {sid} OK (fallback op={r.get('operation_type')})")
                        else:
                            failed += 1
                else:
                    # Store batch results, aligning by order.
                    stored = 0
                    for i, s in enumerate(to_batch):
                        ext = arr[i] if i < len(arr) else None
                        if ext is None or "error" in ext:
                            # Fallback per-sūtra for this one.
                            sid = s["id"]
                            prev = get_previous_sutras(conn, sid, count=5)
                            p = build_prompt(s, prev, load_commentary(sid))
                            r = call_ollama(p, model)
                            if r and "error" not in r:
                                store_extraction(conn, sid, r, model)
                                extracted += 1
                            else:
                                failed += 1
                        else:
                            store_batch_extraction(conn, s["id"], ext, model)
                            extracted += 1
                            stored += 1
                    print(f"OK ({stored} stored, {len(to_batch) - stored} fallback)")
                if delay > 0:
                    time.sleep(delay)
        else:
            print("  All definitional sūtras already cached.")

        # Phase B: per-sūtra for operational sūtras.
        for sutra in operational:
            sid = sutra["id"]
            if not force and is_cached(conn, sid):
                cached += 1
                continue
            if not sutra["sutra_dev"] and not sutra["pada_cheda"]:
                record_hurdle(sid, "missing_data", "Sūtra has no text or pada_cheda", blocking=True)
                failed += 1
                continue
            if max_sutras and extracted + failed >= max_sutras:
                break
            prev = get_previous_sutras(conn, sid, count=5)
            prompt = build_prompt(sutra, prev, load_commentary(sid))
            if dry_run:
                continue
            print(f"  Extracting {sid}...", end=" ")
            sys.stdout.flush()
            result = call_ollama(prompt, model)
            if result is None or "error" in result:
                err = result.get("error", "unknown") if result else "no response"
                print(f"FAIL ({err})")
                record_hurdle(sid, "llm_extraction_failed", f"LLM returned: {err}", blocking=False)
                failed += 1
                continue
            store_extraction(conn, sid, result, model)
            print(f"OK (op={result.get('operation_type')})")
            extracted += 1
            if delay > 0:
                time.sleep(delay)

        conn.close()
        print(f"\nDone: {extracted} extracted, {cached} cached, {failed} failed")
        return

    for sutra in sutras:
        sid = sutra["id"]

        if not force and is_cached(conn, sid):
            cached += 1
            continue

        if not sutra["sutra_dev"] and not sutra["pada_cheda"]:
            record_hurdle(sid, "missing_data", "Sūtra has no text or pada_cheda", blocking=True)
            failed += 1
            continue

        commentary = load_commentary(sid)
        previous = get_previous_sutras(conn, sid, count=3)
        prompt = build_prompt(sutra, previous, commentary)

        if dry_run:
            print(f"\n--- {sid} ---")
            print(prompt[:800])
            continue

        if max_sutras and extracted + failed >= max_sutras:
            print(f"\nReached --max {max_sutras} new sūtras; stopping (cached: {cached}).")
            break

        print(f"  Extracting {sid}...", end=" ")
        sys.stdout.flush()

        result = call_ollama(prompt, model)

        if result is None or "error" in result:
            err = result.get("error", "unknown") if result else "no response"
            print(f"FAIL ({err})")
            record_attempt(sid, "llm_extract", "failed", f"Error: {err}")
            record_hurdle(sid, "llm_extraction_failed", f"LLM returned: {err}", blocking=False)
            failed += 1
            continue

        store_extraction(conn, sid, result, model)
        record_attempt(sid, "llm_extract", "success", f"op={result.get('operation_type')}, conf={result.get('confidence')}")
        print(f"OK (op={result.get('operation_type')})")
        extracted += 1

        if delay > 0:
            time.sleep(delay)

    conn.close()
    print(f"\nDone: {extracted} extracted, {cached} cached, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="LLM-based Pāṇinian sūtra metadata extractor")
    parser.add_argument("--chapter", required=True, help="Chapter to extract (e.g., '6.1')")
    parser.add_argument("--force", action="store_true", help="Re-extract even if cached")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without calling LLM")
    parser.add_argument("--model", default="deepseek-v4-pro:cloud", help="Ollama model to use")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to wait between LLM calls (rate-limit safety)")
    parser.add_argument("--max", type=int, default=0, help="Stop after N new (non-cached) sūtras (0 = no limit)")
    parser.add_argument("--batch-definitions", action="store_true",
                        help="Batch-extract definitional (S$/P$) sūtras per pāda; per-sūtra for operational (V$)")
    args = parser.parse_args()

    extract_chapter(args.chapter, force=args.force, dry_run=args.dry_run,
                    model=args.model, delay=args.delay, max_sutras=args.max,
                    batch_definitions=args.batch_definitions)


if __name__ == "__main__":
    main()
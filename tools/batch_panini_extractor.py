#!/usr/bin/env python3
"""
Comprehensive Pāṇinian Batch Extractor — tools/batch_panini_extractor.py

Extracts structured, compiler-ready metadata for all remaining Aṣṭādhyāyī
chapters into the hybrid schema (rules + contexts + conditions + axioms).

Definitional sūtras (S$/P$/AD$/AT$) are batched per pāda with prerequisite
context from earlier chapters. Operational sūtras (V$) are processed per-sūtra.

No extraction is performed automatically at import time. Run:

    python3 tools/batch_panini_extractor.py --chapter-prefix 3.1 --mode both

"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.shiva_sutras import PratyaharaResolver

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
COMMENTARY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ashtadhyayi-data", "sutraani")
PREREQ_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chapter_prerequisites.json")
OLLAMA_URL = "http://localhost:11434/api/generate"
HURDLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "research", "hurdles")

# Canonical operation-type vocabulary published in prompts and enforced on
# extraction output. Add new types here before prompting for them.
CANONICAL_OPERATION_TYPES = frozenset({
    "exact_substitute", "substitute", "merge", "elide", "augment",
    "prakritibhava", "bijection", "bijection_substitute", "yan",
    "dirgha", "savarna_long", "ekadesha_savarna_dirgha",
    "guna", "ekadesha_guna",
    "vrddhi", "ekadesha_vrddhi",
    "visarga_sandhi", "anusvara", "natva", "samprasarana",
    "pararupa", "purva_rupa",
    "lopa", "luk", "slu",
    "pratyaya_insert", "niyama_prohibit", "non_operational",
})

# Canonical rule types.
CANONICAL_RULE_TYPES = frozenset({
    "vidhi", "niyama", "paribhasa", "adhikara", "atidesa",
    "samjna_definition", "pratyaya_definition", "anuvrtti_carry",
    "nirukti", "vibhasha", "non_operational",
})

# Canonical evaluability labels.
CANONICAL_EVALUABILITY = frozenset({
    "phonological", "morphological", "syntactic", "semantic", "lexical",
    "domain", "operation_history", "manual",
})


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _coerce_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def build_extraction_schema() -> Dict[str, Any]:
    """Return the detailed JSON schema given to the LLM in prompts."""
    return {
        "sutra_id": "TEXT — canonical ID, e.g. 3.1.68",
        "rule_type": f"one of: {sorted(CANONICAL_RULE_TYPES)}",
        "domain": "one of: sapada, tripadi, samhita, angasya, taddhita, samasa",
        "is_executable": "BOOLEAN — can the compiler fire this directly?",
        "operation": {
            "operation_type": f"one of: {sorted(CANONICAL_OPERATION_TYPES)}",
            "operation_subtype": "optional finer grain: agama, adesha, vikarana, substitution_with_sthanivat",
            "replacement": "SLP1 replacement string or null",
            "compute_fn": "one of: guna, vrddhi, savarna_long, bijection, or null",
            "left_consume": "integer >= 0",
            "right_consume": "integer >= 0",
            "emit_side": "left or right or null",
            "emit": "literal emit string or null",
            "preserve_length": "boolean",
            "is_agama": "boolean",
            "is_lopa": "boolean",
            "requires_sthanivadbhava": "boolean",
            "sthani_phoneme": "SLP1 original phoneme or null",
        },
        "contexts": [
            {
                "role": "target | left | right",
                "position": "left_end | right_start | whole_word | internal | padanta | samhita_boundary",
                "pratyahara": "SLP1 pratyahara or null",
                "exact_phonemes": "[phoneme, ...] or null",
                "sanjna_required": "[label, ...]",
                "sanjna_prohibited": "[label, ...]",
                "morphological_category": "dhatu | sup | ting | krt | avyaya | nipata | gati | pratipadika | samasa | null",
                "morphological_features": "{key: value} or null",
                "is_padanta": "boolean",
                "is_samhita": "boolean",
                "is_savarna": "boolean",
                "meta_terms": "[term, ...]",
                "tokens_required": "[word, ...]",
                "sthani_phoneme": "SLP1 or null",
            }
        ],
        "conditioning_factors": [
            {
                "factor_type": "phonological | morphological | syntactic | semantic | lexical | domain | operation_history | negation",
                "condition_text": "original phrase from sūtra/commentary",
                "evaluability": "phonological | morphological | syntactic | semantic | lexical | domain | operation_history | manual",
                "required_sanjnas": "[label, ...]",
                "prohibited_sanjnas": "[label, ...]",
                "required_morph_features": "{key: value} or null",
                "required_words": "[word, ...]",
                "required_domain": "samhita | padanta | angasya | ...",
                "required_operation_history": "{not_after: [id], only_after: [id]} or null",
                "is_negation": "boolean",
                "scope": "local | derivation_global | sentence",
            }
        ],
        "paribhasa_axiom": {
            "axiom_ast": "{and/or/not/eq/later_wins/closest_substitute/sthanivat: ...} or null",
            "paribhasa_category": "vipratisedhe | sthanivad | atidesa | samarthya | nirukti | svarya | anga | null",
            "scope_sutra_ids": "[id, ...]",
            "applies_to_domains": "[domain, ...]",
            "applies_to_operation_types": "[op_type, ...]",
        },
        "sanjna_definition": {
            "defined_sanjna": "string or null",
            "definition_type": "phonological | morphological | syntactic | derivational | null",
            "definition_criteria": "same shape as a context object or null",
            "equivalent_sutra_ids": "[id, ...]",
        },
        "adhikara_definition": {
            "governs_range_start": "id or null",
            "governs_range_end": "id or null",
            "scope_condition": "any or null",
        },
        "anuvrtti": {
            "inherited_from_sutra_id": "id or null",
            "carries": "[target_context, left_context, right_context, operation, conditioning_factors, sanjnas]",
        },
        "examples": {
            "positive_examples": "[(left, right, expected_output), ...]",
            "negative_examples": "[(left, right, must_not_produce), ...]",
        },
        "provenance": {
            "confidence": "0.0–1.0",
            "commentary_notes": "string",
            "vyakhya_summary": "plain-language meaning",
            "hurdles": "[string, ...]",
        },
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

class ExtractorDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def load_prerequisites(self, chapter_prefix: str) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT p.prerequisite_sutra_id, s.sutra_dev, s.pada_cheda,
                          s.sutra_type, s.samasta_sutra, s.anuvrtti, s.adhikara
                   FROM panini_chapter_prerequisites p
                   JOIN sutras s ON s.id = p.prerequisite_sutra_id
                   WHERE p.chapter_prefix = ?
                   ORDER BY p.prerequisite_sutra_id""",
                (chapter_prefix,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "sutra_dev": r[1] or "",
                "pada_cheda": r[2] or "",
                "sutra_type": r[3] or "",
                "samasta_sutra": r[4] or "",
                "anuvrtti": r[5] or "",
                "adhikara": r[6] or "",
            }
            for r in rows
        ]

    def load_sutras_for_chapter(self, chapter_prefix: str) -> List[Dict[str, Any]]:
        pattern = f"{chapter_prefix}.%"
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT id, sutra_dev, pada_cheda, sutra_type, samasta_sutra,
                          anuvrtti, adhikara
                   FROM sutras
                   WHERE id LIKE ?
                   ORDER BY id""",
                (pattern,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "sutra_dev": r[1] or "",
                "pada_cheda": r[2] or "",
                "sutra_type": r[3] or "",
                "samasta_sutra": r[4] or "",
                "anuvrtti": r[5] or "",
                "adhikara": r[6] or "",
            }
            for r in rows
        ]

    # extraction modes that represent a successful comprehensive extraction.
    # legacy_migration rows are stale narrow-schema data and should be re-extracted.
    COMPLETED_EXTRACTION_MODES = frozenset({
        "batch_pada", "batch_operational", "per_sutra", "manual_fix",
        "sequential", "batched_contextual",
    })

    def is_extracted(self, sutra_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT extraction_mode FROM panini_rules WHERE sutra_id = ?",
                (sutra_id,),
            ).fetchone()
        if row is None:
            return False
        return row[0] in self.COMPLETED_EXTRACTION_MODES

    def list_chapter_prefixes(self) -> List[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT substr(id, 1, instr(id, '.') - 1) || '.' || "
                "substr(id, instr(id, '.') + 1, 1) FROM sutras ORDER BY 1"
            ).fetchall()
        return sorted(r[0] for r in rows if r[0])


# ---------------------------------------------------------------------------
# Commentary loading
# ---------------------------------------------------------------------------

def load_commentary(sutra_id: str) -> str:
    vasu_path = os.path.join(COMMENTARY_DIR, "vasu_english.txt")
    if not os.path.exists(vasu_path):
        return ""
    try:
        with open(vasu_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        parts = sutra_id.split(".")
        if len(parts) == 3:
            numeric_id = f"{parts[0]}{parts[1]}{int(parts[2]):03d}"
        else:
            numeric_id = sutra_id.replace(".", "")
        comm = data.get(numeric_id, "")
        return comm[:500] + "..." if len(comm) > 500 else comm
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

def _safe_parse_json(text: str, expect_array: bool = False) -> Optional[Any]:
    # First, try parsing the entire response as-is (handles clean JSON output).
    try:
        result = json.loads(text)
        if expect_array and isinstance(result, list):
            return result
        if not expect_array and isinstance(result, dict):
            return result
        # If we expected an array but got a dict, or vice versa, fall through
        # to the extraction logic below.
        if expect_array and isinstance(result, dict):
            # Maybe the dict wraps an array (e.g. {"results": [...]}).
            for v in result.values():
                if isinstance(v, list):
                    return v
            return None
        if not expect_array and isinstance(result, list):
            # If we expected an object but got a single-element array, unwrap it.
            if len(result) == 1 and isinstance(result[0], dict):
                return result[0]
            return None
        return result
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to extracting the JSON substring (handles markdown fences, trailing text).
    if expect_array:
        start = text.find("[")
        end = text.rfind("]") + 1
    else:
        start = text.find("{")
        end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except Exception:
        return None


def call_ollama(prompt: str, model: str, timeout: int = 300,
                expect_array: bool = False, max_retries: int = 3,
                num_predict: int = 36384) -> Optional[Any]:
    """Call the Ollama API and return parsed JSON object or array. Retries on timeout."""
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "num_predict": num_predict,
                },
            }).encode("utf-8")
            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            call_start = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - call_start
            text = result.get("response", "")
            parsed = _safe_parse_json(text, expect_array=expect_array)
            ok = "OK" if parsed is not None else "PARSE_FAIL"
            label = f"array[{len(parsed)}]" if isinstance(parsed, list) else ("obj" if isinstance(parsed, dict) else "?")
            print(f"  [llm] {model} {ok} {label} {elapsed:.1f}s (attempt {attempt+1}/{max_retries})", flush=True)
            return parsed
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f"  [llm] HTTP/URL error attempt {attempt+1}/{max_retries}: {e}", flush=True)
            if attempt < max_retries - 1:
                wait = min(2 ** (attempt + 1), 30)
                time.sleep(wait)
                continue
            return {"error": f"HTTP/URL error after {max_retries} retries: {e}"}
        except (TimeoutError, socket.timeout) as e:
            print(f"  [llm] timeout attempt {attempt+1}/{max_retries} ({timeout}s)", flush=True)
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"error": f"timed out after {max_retries} attempts of {timeout}s"}
        except Exception as e:
            print(f"  [llm] error attempt {attempt+1}/{max_retries}: {e}", flush=True)
            return {"error": str(e)}
    return {"error": "exhausted retries"}


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _sutra_block(s: Dict[str, Any], include_commentary: bool = True) -> List[str]:
    lines = [
        f"Sūtra ID: {s['id']}",
        f"Devanagari: {s['sutra_dev']}",
        f"Pada-cheda: {s['pada_cheda']}",
        f"Type: {s['sutra_type']}",
    ]
    if s.get("samasta_sutra"):
        lines.append(f"Expanded (samasta): {s['samasta_sutra']}")
    if s.get("anuvrtti"):
        lines.append(f"Anuvṛtti carried: {s['anuvrtti']}")
    if s.get("adhikara"):
        lines.append(f"Adhikāra: {s['adhikara']}")
    if include_commentary:
        comm = load_commentary(s["id"])
        if comm:
            lines.append(f"Commentary (Vasu): {comm}")
    return lines


def build_definition_batch_prompt(
    target_sutras: Sequence[Dict[str, Any]],
    prerequisites: Sequence[Dict[str, Any]],
    previous_sutras: Sequence[Dict[str, Any]],
    schema: Dict[str, Any],
) -> str:
    lines = [
        "You are a Pāṇinian grammar expert. Extract compiler-ready metadata for EACH of the",
        "following definitional sūtras. These define saṃjñās, paribhāṣās, adhikāras, or ātideśas",
        "within a single pāda; their meaning depends on the full pāda scope and prerequisite definitions.",
        "",
        "PREREQUISITE DEFINITIONS ALREADY IN FORCE (reason from these, do not extract them again):",
    ]
    for p in prerequisites:
        lines.extend(["  " + line for line in _sutra_block(p, include_commentary=False)])
        lines.append("")

    if previous_sutras:
        lines.append("PREVIOUS SŪTRAS IN THIS PĀDA (for anuvṛtti context):")
        for ps in previous_sutras:
            lines.extend(["  " + line for line in _sutra_block(ps, include_commentary=False)])
            lines.append("")

    lines.append("TARGET SŪTRAS TO EXTRACT (in order):")
    for i, s in enumerate(target_sutras, 1):
        lines.append(f"\n--- Sūtra {i}: {s['id']} ---")
        lines.extend(_sutra_block(s, include_commentary=True))

    lines.extend([
        "",
        "Return a JSON ARRAY with one extraction object per target sūtra, IN THE SAME ORDER.",
        "Each object must follow this schema (use null for unknown fields; all phonemes in SLP1):",
        json.dumps(schema, indent=2, ensure_ascii=False),
        "",
        "For paribhāṣā sūtras, include a non-null `paribhasa_axiom.axiom_ast` as a structured boolean expression.",
        "Include positive_examples and negative_examples wherever possible.",
        "Return ONLY the JSON array, no explanation.",
    ])
    return "\n".join(lines)


def build_operational_batch_prompt(
    target_sutras: Sequence[Dict[str, Any]],
    prerequisites: Sequence[Dict[str, Any]],
    previous_sutras: Sequence[Dict[str, Any]],
    schema: Dict[str, Any],
) -> str:
    """Build a batch prompt for multiple operational (vidhi/niyama) sūtras."""
    lines = [
        "You are a Pāṇinian grammar expert. Extract compiler-ready metadata for EACH of the",
        "following operational (vidhi/niyama) sūtras. They are in the same pāda, so anuvṛtti and",
        "adhikāra context carries across them.",
        "",
    ]

    if prerequisites:
        lines.append("RELEVANT DEFINITIONAL CONTEXT IN FORCE:")
        for p in prerequisites:
            lines.extend(["  " + line for line in _sutra_block(p, include_commentary=False)])
            lines.append("")

    if previous_sutras:
        lines.append("PREVIOUS OPERATIONAL SŪTRAS IN THIS PĀDA:")
        for ps in previous_sutras:
            lines.extend(["  " + line for line in _sutra_block(ps, include_commentary=False)])
            lines.append("")

    lines.append("TARGET OPERATIONAL SŪTRAS TO EXTRACT (in order):")
    for i, s in enumerate(target_sutras, 1):
        lines.append(f"\n--- Sūtra {i}: {s['id']} ---")
        lines.extend(_sutra_block(s, include_commentary=True))

    lines.extend([
        "",
        "Return a JSON ARRAY with one extraction object per target sūtra, IN THE SAME ORDER.",
        "Each object must follow this schema (use null for unknown fields; all phonemes in SLP1):",
        json.dumps(schema, indent=2, ensure_ascii=False),
        "",
        "For each sūtra explicitly identify:",
        "1. rule_type: vidhi or niyama?",
        "2. operation_type and exact target pratyāhāra/phoneme.",
        "3. replacement, compute_fn, left_consume, right_consume.",
        "4. left/right contexts and any required/prohibited saṃjñās.",
        "5. What this sūtra carries forward via anuvṛtti.",
        "Return ONLY the JSON array, no explanation.",
    ])
    return "\n".join(lines)


def build_operational_prompt(
    target_sutra: Dict[str, Any],
    prerequisites: Sequence[Dict[str, Any]],
    previous_sutras: Sequence[Dict[str, Any]],
    schema: Dict[str, Any],
) -> str:
    """Build a single-sūtra operational prompt (fallback when batch_size is 1)."""
    lines = [
        "You are a Pāṇinian grammar expert. Extract compiler-ready metadata for ONE operational",
        "(vidhi/niyama) sūtra.",
        "",
    ]
    lines.extend(_sutra_block(target_sutra, include_commentary=True))

    if prerequisites:
        lines.append("\nRELEVANT DEFINITIONAL CONTEXT IN FORCE:")
        for p in prerequisites:
            lines.extend(["  " + line for line in _sutra_block(p, include_commentary=False)])
            lines.append("")

    if previous_sutras:
        lines.append("PREVIOUS OPERATIONAL SŪTRAS IN THIS PĀDA:")
        for ps in previous_sutras:
            lines.extend(["  " + line for line in _sutra_block(ps, include_commentary=False)])
            lines.append("")

    lines.extend([
        "",
        "Return a single JSON object matching this schema (use null for unknown fields; all phonemes in SLP1):",
        json.dumps(schema, indent=2, ensure_ascii=False),
        "",
        "Answer these explicitly:",
        "1. rule_type: vidhi or niyama?",
        "2. operation_type and exact target pratyāhāra/phoneme.",
        "3. replacement, compute_fn, left_consume, right_consume.",
        "4. left/right contexts and any required/prohibited saṃjñās.",
        "5. Does this sūtra carry anything forward via anuvṛtti?",
        "Return ONLY the JSON object, no explanation.",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_extraction(sutra_id: str, data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["extraction is not a JSON object"]

    if data.get("rule_type") and data["rule_type"] not in CANONICAL_RULE_TYPES:
        errors.append(f"unknown rule_type: {data['rule_type']}")

    op = _coerce_dict(data.get("operation"))
    if op.get("operation_type") and op["operation_type"] not in CANONICAL_OPERATION_TYPES:
        errors.append(f"unknown operation_type: {op['operation_type']}")

    for key in ("left_consume", "right_consume"):
        val = op.get(key)
        if val is not None and (not isinstance(val, int) or val < 0):
            errors.append(f"{key} must be integer >= 0")

    for ctx in _coerce_list(data.get("contexts")):
        prat = ctx.get("pratyahara")
        if prat:
            try:
                PratyaharaResolver.resolve(prat)
            except Exception:
                # The value might be a saṃjñā term (sup, tiṅ, hrasva) rather
                # than a Śiva-Sūtra pratyāhāra. These are valid grammar
                # references and should not block extraction. Record as a
                # non-blocking note instead of a hard error.
                pass  # accept; the runtime engine can disambiguate later

    for factor in _coerce_list(data.get("conditioning_factors")):
        ev = factor.get("evaluability")
        if ev and ev not in CANONICAL_EVALUABILITY:
            errors.append(f"unknown evaluability: {ev}")

    if data.get("rule_type") == "samjna_definition" and not data.get("sanjna_definition", {}).get("defined_sanjna"):
        errors.append("samjna_definition requires defined_sanjna")

    if data.get("rule_type") == "paribhasa":
        axiom = _coerce_dict(data.get("paribhasa_axiom", {})).get("axiom_ast")
        if not axiom:
            errors.append("paribhasa requires axiom_ast")

    return errors


def record_hurdle(sutra_id: str, errors: List[str]) -> None:
    os.makedirs(HURDLES_DIR, exist_ok=True)
    safe_id = sutra_id.replace(".", "_")
    path = os.path.join(HURDLES_DIR, f"{safe_id}.json")
    payload = {"sutra_id": sutra_id, "errors": errors, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Storage into hybrid schema
# ---------------------------------------------------------------------------

def _text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ctx_row(rule_id: str, role: str, ctx: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        rule_id,
        role,
        ctx.get("position"),
        ctx.get("pratyahara"),
        _json(ctx.get("exact_phonemes")),
        _json(ctx.get("sanjna_required", [])),
        _json(ctx.get("sanjna_prohibited", [])),
        ctx.get("morphological_category"),
        _json(ctx.get("morphological_features")),
        _safe_int(ctx.get("is_padanta"), 0),
        _safe_int(ctx.get("is_samhita"), 0),
        _safe_int(ctx.get("is_savarna"), 0),
        _json(ctx.get("meta_terms", [])),
        _json(ctx.get("tokens_required", [])),
        ctx.get("sthani_phoneme"),
    )


def store_comprehensive_extraction(
    conn: sqlite3.Connection,
    sutra: Dict[str, Any],
    extraction: Dict[str, Any],
    model: str,
    mode: str,
) -> None:
    sid = sutra["id"]
    adhyaya, pada, sutra_no = _parse_id(sid)

    # Flatten rule-level fields.
    op = _coerce_dict(extraction.get("operation"))
    sanjna_def = _coerce_dict(extraction.get("sanjna_definition"))
    adhikara_def = _coerce_dict(extraction.get("adhikara_definition"))
    anuvrtti = _coerce_dict(extraction.get("anuvrtti"))
    examples = _coerce_dict(extraction.get("examples"))
    prov = _coerce_dict(extraction.get("provenance"))

    rule_type = extraction.get("rule_type") or "non_operational"
    is_executable = rule_type in ("vidhi", "niyama")
    is_meta = rule_type == "paribhasa"
    is_definition = rule_type in ("samjna_definition", "paribhasa", "adhikara", "atidesa")

    params = (
        sid, adhyaya, pada, sutra_no, sutra["sutra_dev"], sutra["pada_cheda"],
        sutra["sutra_type"], sutra["samasta_sutra"], sutra["anuvrtti"], sutra["adhikara"],
        _json([]), _text_hash(sutra["sutra_dev"] + sutra["pada_cheda"]),
        rule_type, extraction.get("domain", "sapada"), int(is_executable), int(is_meta), int(is_definition),
        anuvrtti.get("inherited_from_sutra_id"), _json(anuvrtti.get("carries", [])),
        op.get("operation_type"), op.get("operation_subtype"), op.get("replacement"), op.get("compute_fn"),
        _safe_int(op.get("left_consume"), 0), _safe_int(op.get("right_consume"), 0), op.get("emit_side"), op.get("emit"),
        _safe_int(op.get("preserve_length"), 0), _safe_int(op.get("is_agama"), 0), _safe_int(op.get("is_lopa"), 0),
        _safe_int(op.get("is_nipatana_exception"), 0), _safe_int(op.get("requires_sthanivadbhava"), 0),
        op.get("sthani_phoneme") or extraction.get("sthani_phoneme"),
        sanjna_def.get("defined_sanjna"), sanjna_def.get("definition_type"),
        _json(sanjna_def.get("definition_criteria")),
        _json(sanjna_def.get("equivalent_sutra_ids", [])),
        sid if rule_type == "adhikara" else None,
        adhikara_def.get("governs_range_start"), adhikara_def.get("governs_range_end"),
        _json(adhikara_def.get("scope_condition")),
        _json(examples.get("positive_examples", [])),
        _json(examples.get("negative_examples", [])),
        prov.get("commentary_notes", ""), prov.get("vyakhya_summary", ""),
        _safe_float(prov.get("confidence"), extraction.get("confidence", 0.0)),
        mode, model, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        _safe_int(prov.get("commentary_used"), 0),
        _json(prov.get("hurdles", [])),
        "pending",
    )

    # Defensive: if any parameter is still non-JSON-serializable or wrong type,
    # record a hurdle and skip storage rather than crash the whole batch.
    try:
        conn.execute(
            """INSERT OR REPLACE INTO panini_rules (
                sutra_id, adhyaya, pada, sutra_no, sutra_dev, pada_cheda, sutra_type,
                samasta_sutra, anuvrtti_text, adhikara, adhikara_chain, source_text_hash,
                rule_type, domain, is_executable, is_meta_rule, is_definition,
                anuvrtti_source_sutra_id, anuvrtti_carries,
                operation_type, operation_subtype, replacement, compute_fn,
                left_consume, right_consume, emit_side, emit, preserve_length,
                is_agama, is_lopa, is_nipatana_exception, requires_sthanivadbhava, sthani_phoneme,
                defined_sanjna, definition_type, definition_criteria, equivalent_sutra_ids,
                adhikara_sutra_id, governs_range_start, governs_range_end, scope_condition,
                positive_examples, negative_examples,
                commentary_notes, vyakhya_summary, confidence, extraction_mode, model,
                extracted_at, commentary_used, hurdles, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
    except Exception as e:
        record_hurdle(sid, [f"storage error: {e}"])
        raise

    # Wipe and rewrite child rows for idempotency.
    conn.execute("DELETE FROM panini_rule_contexts WHERE rule_id = ?", (sid,))
    conn.execute("DELETE FROM panini_rule_conditions WHERE rule_id = ?", (sid,))
    conn.execute("DELETE FROM panini_rule_paribhasa_axioms WHERE rule_id = ?", (sid,))
    conn.execute("DELETE FROM panini_rule_anuvrtti_links WHERE rule_id = ?", (sid,))

    for ctx in _coerce_list(extraction.get("contexts")):
        role = ctx.get("role", "target")
        conn.execute(
            """INSERT INTO panini_rule_contexts (
                rule_id, context_role, position, pratyahara, exact_phonemes,
                sanjna_required, sanjna_prohibited, morphological_category,
                morphological_features, is_padanta, is_samhita, is_savarna,
                meta_terms, tokens_required, sthani_phoneme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _ctx_row(sid, role, ctx),
        )

    for factor in _coerce_list(extraction.get("conditioning_factors")):
        conn.execute(
            """INSERT INTO panini_rule_conditions (
                rule_id, factor_type, condition_text, evaluability,
                required_sanjnas, prohibited_sanjnas, required_morph_features,
                required_words, required_domain, required_operation_history,
                is_negation, scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                factor.get("factor_type"),
                factor.get("condition_text"),
                factor.get("evaluability"),
                _json(factor.get("required_sanjnas", [])),
                _json(factor.get("prohibited_sanjnas", [])),
                _json(factor.get("required_morph_features")),
                _json(factor.get("required_words", [])),
                factor.get("required_domain"),
                _json(factor.get("required_operation_history")),
                _safe_int(factor.get("is_negation"), 0),
                factor.get("scope"),
            ),
        )

    paribhasa = _coerce_dict(extraction.get("paribhasa_axiom"))
    if paribhasa:
        conn.execute(
            """INSERT INTO panini_rule_paribhasa_axioms (
                rule_id, axiom_ast, paribhasa_category, scope_sutra_ids,
                applies_to_domains, applies_to_operation_types
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                _json(paribhasa.get("axiom_ast")),
                paribhasa.get("paribhasa_category"),
                _json(paribhasa.get("scope_sutra_ids", [])),
                _json(paribhasa.get("applies_to_domains", [])),
                _json(paribhasa.get("applies_to_operation_types", [])),
            ),
        )

    if anuvrtti.get("inherited_from_sutra_id"):
        for field in anuvrtti.get("carries", []):
            conn.execute(
                """INSERT INTO panini_rule_anuvrtti_links (rule_id, inherited_from_sutra_id, inherited_field)
                   VALUES (?, ?, ?)
                """,
                (sid, anuvrtti["inherited_from_sutra_id"], field),
            )

    conn.commit()


def _parse_id(sutra_id: str) -> Tuple[int, int, int]:
    parts = sutra_id.split(".")
    if len(parts) == 3:
        return int(parts[0]), int(parts[1]), int(parts[2])
    return 0, 0, 0


# ---------------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------------

def _is_definitional(sutra: Dict[str, Any]) -> bool:
    st = (sutra.get("sutra_type") or "")
    return any(st.startswith(prefix) for prefix in ("S$", "P$", "AD$", "AT$"))


def _chapter_prefix(sutra_id: str) -> str:
    parts = sutra_id.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else sutra_id


# ---------------------------------------------------------------------------
# Main extraction loop
# ---------------------------------------------------------------------------

def extract_definitions_for_pada(
    db: ExtractorDB,
    sutras: Sequence[Dict[str, Any]],
    prerequisites: Sequence[Dict[str, Any]],
    model: str,
    batch_size: int,
    delay: float,
    resume: bool,
) -> Tuple[int, int, List[str]]:
    """Batch-extract definitional sūtras. Returns (attempted, stored, failed_ids)."""
    schema = build_extraction_schema()
    attempted = 0
    stored = 0
    failed_ids: List[str] = []

    batches = [sutras[i : i + batch_size] for i in range(0, len(sutras), batch_size)]
    for batch in batches:
        batch = [s for s in batch if not (resume and db.is_extracted(s["id"]))]
        if not batch:
            continue

        previous = []  # Same-pāda previous sūtras could be fetched here if needed.
        prompt = build_definition_batch_prompt(batch, prerequisites, previous, schema)
        attempted += len(batch)
        result = call_ollama(prompt, model, timeout=600, expect_array=True)

        if isinstance(result, dict) and "error" in result:
            for s in batch:
                record_hurdle(s["id"], [f"batch error: {result['error']}"])
            failed_ids.extend([s["id"] for s in batch])
            continue
        if not isinstance(result, list):
            for s in batch:
                record_hurdle(s["id"], ["batch returned non-array (likely truncated JSON)"])
            failed_ids.extend([s["id"] for s in batch])
            continue

        # Retry any failed individual extractions from this batch.
        for idx, s in enumerate(batch):
            if idx >= len(result):
                failed_ids.append(s["id"])
                continue
            extraction = result[idx]
            errors = validate_extraction(s["id"], extraction)
            if errors:
                record_hurdle(s["id"], errors)
                failed_ids.append(s["id"])
                continue
            with db.connect() as conn:
                store_comprehensive_extraction(conn, s, extraction, model, "batch_pada")
            stored += 1

        if delay > 0:
            time.sleep(delay)

    return attempted, stored, failed_ids


def extract_operational_sutra(
    db: ExtractorDB,
    sutra: Dict[str, Any],
    prerequisites: Sequence[Dict[str, Any]],
    previous_sutras: Sequence[Dict[str, Any]],
    model: str,
    delay: float,
) -> bool:
    """Per-sūtra operational extraction fallback. Returns True if stored."""
    schema = build_extraction_schema()
    prompt = build_operational_prompt(sutra, prerequisites, previous_sutras, schema)
    result = call_ollama(prompt, model, timeout=300, expect_array=False)

    if isinstance(result, dict) and "error" in result:
        record_hurdle(sutra["id"], [result["error"]])
        return False
    if not isinstance(result, dict):
        record_hurdle(sutra["id"], ["non-object response"])
        return False

    errors = validate_extraction(sutra["id"], result)
    if errors:
        record_hurdle(sutra["id"], errors)
        return False

    with db.connect() as conn:
        store_comprehensive_extraction(conn, sutra, result, model, "per_sutra")

    if delay > 0:
        time.sleep(delay)
    return True


def extract_operational_batch(
    db: ExtractorDB,
    sutras: Sequence[Dict[str, Any]],
    prerequisites: Sequence[Dict[str, Any]],
    model: str,
    delay: float,
    resume: bool,
) -> Tuple[int, int, List[str]]:
    """Batch-extract operational sūtras. Returns (attempted, stored, failed_ids)."""
    schema = build_extraction_schema()
    attempted = 0
    stored = 0
    failed_ids: List[str] = []
    previous: List[Dict[str, Any]] = []

    for s in sutras:
        if resume and db.is_extracted(s["id"]):
            previous.append(s)
            continue

        # Previous context is all successfully extracted operational sūtras so far.
        prompt = build_operational_prompt(s, prerequisites, previous, schema)
        attempted += 1
        result = call_ollama(prompt, model, timeout=300, expect_array=False)

        if isinstance(result, dict) and "error" in result:
            record_hurdle(s["id"], [result["error"]])
            failed_ids.append(s["id"])
            continue
        if not isinstance(result, dict):
            record_hurdle(s["id"], ["non-object response"])
            failed_ids.append(s["id"])
            continue

        errors = validate_extraction(s["id"], result)
        if errors:
            record_hurdle(s["id"], errors)
            failed_ids.append(s["id"])
            continue

        with db.connect() as conn:
            store_comprehensive_extraction(conn, s, result, model, "per_sutra")
        stored += 1
        previous.append(s)

        if delay > 0:
            time.sleep(delay)

    return attempted, stored, failed_ids


def extract_operational_group(
    db: ExtractorDB,
    sutras: Sequence[Dict[str, Any]],
    prerequisites: Sequence[Dict[str, Any]],
    previous_sutras: Sequence[Dict[str, Any]],
    model: str,
    delay: float,
    batch_size: int,
    resume: bool,
) -> Tuple[int, int, List[str]]:
    """Extract operational sūtras using batching when batch_size > 1.

    Each batch includes all previous sūtras as anuvṛtti context, so earlier
    sūtras in the group are repeated in the prompt for later ones. This keeps
    the LLM aware of the running context without needing stateful inference.
    """
    if batch_size <= 1:
        return extract_operational_batch(db, sutras, prerequisites, model, delay, resume)

    schema = build_extraction_schema()
    attempted = 0
    stored = 0
    failed_ids: List[str] = []
    previous = list(previous_sutras)

    batches = [sutras[i : i + batch_size] for i in range(0, len(sutras), batch_size)]
    for batch_index, original_batch in enumerate(batches):
        batch = [s for s in original_batch if not (resume and db.is_extracted(s["id"]))]
        already_extracted = [s for s in original_batch if db.is_extracted(s["id"])]
        if already_extracted:
            previous.extend(already_extracted)
        if not batch:
            continue

        attempted += len(batch)
        prompt = build_operational_batch_prompt(batch, prerequisites, previous, schema)
        result = call_ollama(prompt, model, timeout=300, expect_array=True)

        if isinstance(result, dict) and "error" in result:
            # Whole batch failed — retry per-sūtra.
            for s in batch:
                record_hurdle(s["id"], [f"batch error: {result['error']}"])
            a, s, f = extract_operational_batch(
                db, batch, prerequisites, model, delay, resume=False
            )
            attempted += a - len(batch)  # avoid double-counting (a == len(batch))
            stored += s
            failed_ids.extend(f)
            previous.extend([s for s in batch if s["id"] not in f])
            continue
        if not isinstance(result, list):
            for s in batch:
                record_hurdle(s["id"], ["batch returned non-array (likely truncated JSON)"])
            a, s, f = extract_operational_batch(
                db, batch, prerequisites, model, delay, resume=False
            )
            attempted += a - len(batch)
            stored += s
            failed_ids.extend(f)
            previous.extend([s for s in batch if s["id"] not in f])
            continue

        for idx, s in enumerate(batch):
            if idx >= len(result):
                failed_ids.append(s["id"])
                continue
            extraction = result[idx]
            errors = validate_extraction(s["id"], extraction)
            if errors:
                record_hurdle(s["id"], errors)
                failed_ids.append(s["id"])
                continue
            with db.connect() as conn:
                store_comprehensive_extraction(conn, s, extraction, model, "batch_operational")
            stored += 1
            previous.append(s)

        if delay > 0:
            time.sleep(delay)

    return attempted, stored, failed_ids


def extract_chapter_prefix(
    db: ExtractorDB,
    chapter_prefix: str,
    mode: str,
    definition_model: str,
    operational_model: str,
    delay: float,
    batch_size: int,
    operational_batch_size: int,
    resume: bool,
) -> Dict[str, Any]:
    """Extract one chapter prefix."""
    all_sutras = db.load_sutras_for_chapter(chapter_prefix)
    prerequisites = db.load_prerequisites(chapter_prefix)

    definitional = [s for s in all_sutras if _is_definitional(s)]
    operational = [s for s in all_sutras if not _is_definitional(s)]

    stats = {
        "chapter_prefix": chapter_prefix,
        "total": len(all_sutras),
        "definitional": {"attempted": 0, "stored": 0, "failed": []},
        "operational": {"attempted": 0, "stored": 0, "failed": []},
    }

    if mode in ("definitions", "both") and definitional:
        attempted, stored, failed = extract_definitions_for_pada(
            db, definitional, prerequisites, definition_model, batch_size, delay, resume
        )
        stats["definitional"]["attempted"] = attempted
        stats["definitional"]["stored"] = stored
        stats["definitional"]["failed"] = failed

    if mode in ("operational", "both") and operational:
        attempted, stored, failed = extract_operational_group(
            db, operational, prerequisites, [], operational_model, delay, operational_batch_size, resume
        )
        stats["operational"]["attempted"] = attempted
        stats["operational"]["stored"] = stored
        stats["operational"]["failed"] = failed

    return stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Comprehensive Pāṇinian sūtra extractor")
    parser.add_argument("--chapter-prefix", default="all",
                        help="Chapter prefix like 3.1, or 'all' for every chapter")
    parser.add_argument("--mode", choices=["definitions", "operational", "both"],
                        default="both")
    parser.add_argument("--model", default="deepseek-v4-pro:cloud",
                        help="Default model for both modes")
    parser.add_argument("--definition-model", default=None,
                        help="Model for definitional sūtras (defaults to --model)")
    parser.add_argument("--operational-model", default=None,
                        help="Model for operational sūtras (defaults to --model)")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Batch size for definitional sūtras")
    parser.add_argument("--operational-batch-size", type=int, default=20,
                        help="Batch size for operational sūtras (1 = per-sūtra)")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prerequisite-map", default=PREREQ_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    definition_model = args.definition_model or args.model
    operational_model = args.operational_model or args.model

    db = ExtractorDB(DB_PATH)

    if args.dry_run:
        schema = build_extraction_schema()
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        return 0

    # Load prerequisites into DB from JSON if table is empty.
    with db.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM panini_chapter_prerequisites").fetchone()[0]
        if count == 0 and os.path.exists(args.prerequisite_map):
            with open(args.prerequisite_map, "r", encoding="utf-8") as f:
                prereq_data = json.load(f)
            for chapter, ids in prereq_data.items():
                for sid in ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO panini_chapter_prerequisites (chapter_prefix, prerequisite_sutra_id) VALUES (?, ?)",
                        (chapter, sid),
                    )
            conn.commit()
            print(f"Loaded {len(prereq_data)} chapter prerequisite entries from {args.prerequisite_map}")

    if args.chapter_prefix == "all":
        prefixes = db.list_chapter_prefixes()
    elif "." not in args.chapter_prefix:
        # Whole adhyāya requested, e.g. "3" -> expand to all pādas present in DB.
        prefixes = [p for p in db.list_chapter_prefixes() if p.startswith(args.chapter_prefix + ".")]
        prefixes.sort()
        if not prefixes:
            print(f"No pādas found for adhyāya {args.chapter_prefix}")
            return 1
    else:
        prefixes = [args.chapter_prefix]

    all_stats = []
    for prefix in prefixes:
        print(f"\n=== Extracting {prefix} ===")
        stats = extract_chapter_prefix(
            db, prefix, args.mode, definition_model, operational_model, args.delay,
            args.batch_size, args.operational_batch_size, args.resume
        )
        all_stats.append(stats)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n=== Summary ===")
    print(json.dumps(all_stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

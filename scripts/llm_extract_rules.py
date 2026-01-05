#!/usr/bin/env python3
# scripts/llm_extract_rules.py
"""
LLM-driven rule extractor (local, JSON-mode) → rules.jsonl

- Reads a PDF (PyMuPDF)
- Sends sliding windows of pages to a local LLM via Ollama Chat (JSON enforced)
- Validates each output item against JSON Schema
- Dedupes by rule_id and appends to data/processed/rules.jsonl

Usage:
  pip install pymupdf pdfminer.six jsonschema requests
  ollama pull llama3:8b   # or any model you prefer
  python3 scripts/llm_extract_rules.py \
      --pdf data/raw/ICDR_excerpt.pdf \
      --out data/processed/rules.jsonl \
      --model llama3:8b \
      --window 3 --overlap 1 \
      --reg-filter 3 22 \
      --dedupe
"""

from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

import requests
from jsonschema import Draft202012Validator
from pathlib import Path
import json
import unicodedata
from typing import Any

# ---------- Few-shot utilities ----------
def load_fewshot_examples(fewshot_path: str | None) -> list[tuple[str, list[dict]]]:
    """
    Load few-shot examples from a JSON file.

    Expected formats:
    - Array of {"input": str, "output": [ {rule...}, ... ]}
    - Or object {"examples": [ {"input": ..., "output": [...]}, ... ]}
    Returns a list of (input_text, output_items) pairs.
    """
    examples: list[tuple[str, list[dict]]] = []
    if not fewshot_path:
        return examples
    p = Path(fewshot_path)
    if not p.exists():
        raise FileNotFoundError(f"Few-shot file not found: {fewshot_path}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse few-shot JSON: {e}")

    data = raw.get("examples") if isinstance(raw, dict) and "examples" in raw else raw
    if not isinstance(data, list):
        raise ValueError("Few-shot file must be a list or an object with an 'examples' list")
    for i, ex in enumerate(data):
        if not isinstance(ex, dict):
            continue
        inp = ex.get("input") or ex.get("text")
        out = ex.get("output") or ex.get("items")
        if isinstance(inp, str) and isinstance(out, list):
            examples.append((inp, out))
    return examples

SCHEMA_PATH = Path("data/schema/rules_schema.json")
RULE_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(RULE_SCHEMA)
ALLOWED_TOP_KEYS = set((RULE_SCHEMA.get("properties") or {}).keys())

# Build an array schema for Ollama JSON schema enforcement (rules array of RULE_SCHEMA items)
ARRAY_RULES_SCHEMA: dict = {
    "type": "array",
    "items": RULE_SCHEMA if RULE_SCHEMA.get("type") == "object" else {"type": "object"}
}

def build_ollama_json_schema_format() -> dict:
    """
    Returns an Ollama 'format' payload that enforces the array-of-rules schema.
    Falls back to plain 'json' at call time if the server doesn't support json_schema.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "rules_array",
            "schema": ARRAY_RULES_SCHEMA
        }
    }


def sanitize_for_schema(item: dict) -> dict:
    """
    Drop any keys not allowed by data/schema/rules_schema.json.
    This is critical because the schema uses additionalProperties:false.
    """
    out: dict = {}
    for k in ALLOWED_TOP_KEYS:
        if k in item:
            out[k] = item[k]

    # sanitize nested structures with additionalProperties:false
    if "source" in out and isinstance(out["source"], dict):
        src = out["source"]
        out["source"] = {
            "pdf": src.get("pdf", ""),
            "pages": src.get("pages", []),
            "span_hint": src.get("span_hint", ""),
            **({"reg": src.get("reg", "")} if "reg" in src else {}),
        }

    if "maps_to" in out and isinstance(out["maps_to"], list):
        cleaned_maps = []
        for m in out["maps_to"]:
            if not isinstance(m, dict):
                continue
            cm = {}
            if "field" in m:
                cm["field"] = m["field"]
            if "type_hint" in m:
                cm["type_hint"] = m["type_hint"]
            if "constraints_text" in m:
                cm["constraints_text"] = m["constraints_text"]
            if cm:
                cleaned_maps.append(cm)
        out["maps_to"] = cleaned_maps

    return out


def extract_first_json_block(text: str) -> str:
    """
    Extract the first top-level JSON object/array block from a string.
    This is robust to leading/trailing non-JSON text and code fences.
    Returns "" if nothing plausible is found.
    """
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    # Drop fenced code wrapper if present
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I).strip()
    s = re.sub(r"\s*```$", "", s).strip()

    # Find first opening brace/bracket
    start = None
    opener = ""
    for i, ch in enumerate(s):
        if ch == "{" or ch == "[":
            start = i
            opener = ch
            break
    if start is None:
        return ""

    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return s[start : j + 1]
    return ""


def coerce_rules_from_parsed(obj: Any) -> list[dict]:
    """
    Accept multiple common shapes and coerce into a list[dict] (rule-like objects).
    Supported:
      - [ {...}, ... ]
      - {"rules":[...]} or {"items":[...]}
      - dict-of-rule_* -> values list
    """
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if "rules" in obj and isinstance(obj["rules"], list):
            return [x for x in obj["rules"] if isinstance(x, dict)]
        if "items" in obj and isinstance(obj["items"], list):
            return [x for x in obj["items"] if isinstance(x, dict)]
        # dict-of-rule_* (values might be dicts; strings are ignored here)
        vals = list(obj.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals  # type: ignore[return-value]
    return []


def flatten_subrules(rule_obj: dict) -> list[dict]:
    """
    If model returns a non-schema object with `subrules`, flatten into separate
    rule objects. Otherwise return [rule_obj].
    Expected shape example:
      {"title": "...", "subrules":[{"number":"7(1)(a)","text":"..."}, ...]}
    """
    subrules = rule_obj.get("subrules")
    if not isinstance(subrules, list):
        return [rule_obj]
    out: list[dict] = []
    parent_title = str(rule_obj.get("title") or "").strip()
    for sr in subrules:
        if not isinstance(sr, dict):
            continue
        num = str(sr.get("number") or "").strip()
        txt = str(sr.get("text") or "").strip()
        if not num or not txt:
            continue
        # Build a best-effort ICDR_* id from clause number like 7(1)(a)
        # 7(2) -> ICDR_7_2 ; 7(1)(a) -> ICDR_7_1_a
        tokens = re.findall(r"\d+|[A-Za-z]+", num)
        if not tokens:
            continue
        reg = tokens[0]
        rest = [t.lower() for t in tokens[1:]]
        rule_id = "ICDR_" + reg + ("_" + "_".join(rest) if rest else "")
        out.append(
            {
                "rule_id": rule_id,
                "domain": "SEBI_ICDR",
                "title": (parent_title + " — " + num).strip(" —") if parent_title else num,
                "text": txt,
                "lean_id": "rule_" + rule_id[5:].lower(),
                "maps_to": [],
                "notes": "",
                "source": {"pdf": "<PDF>", "pages": [0], "reg": "", "span_hint": ""},  # filled later
                "confidence": 0.6,
                "repair_notes": ["flattened_subrules"],
            }
        )
    return out or [rule_obj]

# ---------- Static prompts ----------
SYSTEM_PROMPT = """You are a compliance analyst extracting ATOMIC regulatory rules from SEBI ICDR regulations.
Your output MUST be STRICT JSON (UTF-8, no comments) matching this array schema:

[
  {
    "rule_id": "ICDR_<reg>[_<num>][_a]",
    "domain": "SEBI_ICDR",
    "title": "<concise title>",
    "text": "<verbatim or lightly cleaned clause text (keep legal meaning)>",
    "lean_id": "rule_<reg>[_<num>][_a]",
    "maps_to": [
  {
    "field": "<snake_case field identifier>",
    "type_hint": "Bool | Nat | List Nat | String | OptionBool | OptionNat | OptionListNat | OptionString",
    "constraints_text": "<optional; do NOT put constraints in field name>"
  }
],
"notes": "<optional human explanation; DO NOT include field names here>",
    "source": {
      "pdf": "<filename>",
      "pages": [<page_numbers_int>],
      "reg": "<visible heading if present>",
      "span_hint": "<few words around the start>"
    },
    "confidence": 0.0
  }
]

Rules:
- Extract only clauses that are within the *visible* pages provided.
- Produce ATOMIC items: split by (1)(2)… and (a)(b)… where semantically distinct.
- Preserve numeric thresholds and units (e.g., ₹15 crore, 25%).
- Be conservative: do not infer or normalize beyond the text.
- `rule_id` MUST follow `ICDR_<reg>[_<clause>[_<subclause>]]` using digits for numbered clauses and lowercase letters for sub-clauses (e.g., ICDR_6_1_a, ICDR_14_4_core). Do not emit spaces, hyphens, or Roman numerals.
- Titles should be short and specific. “Title — (1)(b)” is fine when no official title.
- lean_id mirrors rule_id with 'ICDR' → 'rule', e.g., ICDR_6_1_b → rule_6_1_b.
- Use notes only for short human explanation/edge cases. Do not put field names in notes; use maps_to.
- `source.span_hint` must be a direct quote (≤120 chars) copied from the provided text window; no paraphrasing.
- `source.span_hint` should be the first ~10 words of the clause text (strip punctuation), so it is easy to locate verbatim in the PDF.
- `source.span_hint` must be a unique fragment that clearly identifies this clause (e.g. starting from ‘The issuer shall…’). Never use generic phrases like ‘subject to’, ‘the issuer may’, ‘Provided that’.
- Confidence in [0,1]; use lower scores if the clause boundary is ambiguous.
- If no extractable rules are present in this chunk, return [].
- For each legal clause (e.g., Regulation 6(1)(a)), return at most one JSON object. Do not repeat the same clause with different rule_ids.
- In maps_to, field must be a bare identifier. Do not include parentheses, units, bullet letters, or conditions.
- If a rule is not representable as a stable issuer/offer fact, set maps_to: [].
- Never output two objects whose source.reg and source.span_hint refer to the same clause.
"""

FEWSHOT_INPUT = """Regulation 6(1)(b): The issuer shall have an average operating profit of at least ₹15 crore, calculated on a restated and consolidated basis, during the preceding three years, with operating profit in each of these preceding three years."""
FEWSHOT_OUTPUT = [
  {
    "rule_id": "ICDR_6_1_b",
    "domain": "SEBI_ICDR",
    "title": "Operating profit ≥ ₹15 cr in each of last 3 years",
    "text": "The issuer shall have an average operating profit of at least ₹15 crore, calculated on a restated and consolidated basis, during the preceding three years, with operating profit in each of these preceding three years.",
    "lean_id": "rule_6_1_b",
    "maps_to": [
      {
        "field": "operating_profits",
        "type_hint": "List Nat",
        "constraints_text": "length=3; each ≥ ₹15 crore; basis=restated, consolidated"
      }
    ],
    "notes": "Three-year operating profit requirement; computed on restated and consolidated basis.",
    "source": {"pdf":"<PDF>", "pages":[0], "reg":"Regulation 6(1)(b)", "span_hint":"average operating profit of at least"},
    "confidence": 0.95
  }
]

FEWSHOT_BAD_INPUT = """Regulation 6(1)(a) appears once in the excerpt below. Do not create multiple objects for the same clause:
6. (1) (a) it has net tangible assets of at least three crore rupees ...
"""

# IMPORTANT: show only the correct behavior as JSON
FEWSHOT_BAD_OUTPUT = [
  {
    "rule_id": "ICDR_6_1_a",
    "domain": "SEBI_ICDR",
    "title": "Net tangible assets ≥ ₹3 cr",
    "text": "it has net tangible assets of at least three crore rupees ...",
    "lean_id": "rule_6_1_a",
    "maps_to": [
      {
        "field": "net_tangible_assets",
        "type_hint": "List Nat",
        "constraints_text": "length=3 (preceding 3 years if stated); threshold ≥ ₹3 crore"
      }
    ],
    "notes": "Single clause; do not duplicate objects for the same regulation reference.",
    "source": {
      "pdf": "<PDF>",
      "pages": [1],
      "reg": "Regulation 6(1)(a)",
      "span_hint": "net tangible assets of at least three crore"
    },
    "confidence": 0.9
  }
]

# Put the negative guidance in plain text (NOT JSON) in the prompt:
BAD_EXPLANATION = """
Do NOT output duplicates for the same legal clause (e.g., do not output rule_id ICDR_6_1_a twice
with variants). If a clause is mentioned once, return at most one JSON object for it.
"""


# FEWSHOT_BAD_INPUT = """Regulation 6(1)(a) appears once in the excerpt below. Do not create multiple objects for the same clause:
# 6. (1) (a) it has net tangible assets of at least three crore rupees ...
# """
# FEWSHOT_BAD_OUTPUT = [
#   {
#     "rule_id": "ICDR_6_1_a",
#     "domain": "SEBI_ICDR",
#     "title": "Net tangible assets ≥ ₹3 cr",
#     "text": "it has net tangible assets of at least three crore rupees ...",
#     "lean_id": "rule_6_1_a",
#     "notes": "",
#     "source": {"pdf": "<PDF>", "pages": [1], "reg": "Regulation 6(1)(a)", "span_hint": "net tangible assets of at least three crore"},
#     "confidence": 0.9
#   },
#   {
#     "rule_id": "ICDR_6_1_a_variant",
#     "domain": "SEBI_ICDR",
#     "title": "Duplication of same clause (WRONG)",
#     "text": "it has net tangible assets of at least three crore rupees ...",
#     "lean_id": "rule_6_1_a_variant",
#     "notes": "",
#     "source": {"pdf": "<PDF>", "pages": [1], "reg": "Regulation 6(1)(a)", "span_hint": "net tangible assets of at least three crore"},
#     "confidence": 0.9
#   }
# ]

# ---------- Ollama client ----------
def ollama_generate_json(model: str, system: str, user: str, timeout: int = 120, debug: bool = False, debug_raw: bool = False, format_json: bool = True, fewshots: list[tuple[str, list[dict]]] | None = None) -> list[dict]:
    """
    Fallback for older Ollama: use /api/generate with a single prompt and JSON format.
    """
    url = "http://localhost:11434/api/generate"
    # Build few-shot sections (default demo + optional extras)
    fewshot_sections: list[str] = [
        (
            f"Example input:\n{FEWSHOT_INPUT}\n\n"
            f"Example output (JSON array):\n{json.dumps(FEWSHOT_OUTPUT, ensure_ascii=False)}\n"
        )
    ]
    if fewshots:
        for ex_input, ex_output in fewshots:
            try:
                fewshot_sections.append(
                    f"Example input:\n{ex_input}\n\n"
                    f"Example output (JSON array):\n{json.dumps(ex_output, ensure_ascii=False)}\n"
                )
            except Exception:
                continue

    # fewshot_sections.append(
    #     "Bad example (do NOT copy):\n"
    #     f"{FEWSHOT_BAD_INPUT}\n\n"
    #     f"Incorrect output (duplicates the same clause twice, which is forbidden):\n"
    #     f"{json.dumps(FEWSHOT_BAD_OUTPUT, ensure_ascii=False)}\n"
    #     "Never replicate the bad behavior above."
    # )
    fewshot_sections.append(BAD_EXPLANATION)


    prompt = (
        f"{system}\n\n" + "\n\n".join(fewshot_sections) + "\n\n" +
        f"Now extract for this input:\n{user}\n"
    )
    payload = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "prompt": prompt,
        "stream": False,
    }
    if format_json:
        # Prefer Ollama's built-in JSON mode for reliability (no schema enforcement here)
        payload["format"] = "json"
    if debug:
        print("[DEBUG] calling Ollama /api/generate", file=sys.stderr)
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
    except requests.HTTPError as http_err:
        code = http_err.response.status_code if http_err.response is not None else None
        # If server errored (5xx) or rejects format, retry once with format='json' (no further fallbacks)
        if format_json and (code in (400, 415) or (code is not None and 500 <= code < 600)):
            if debug:
                print("[DEBUG] /api/generate retrying once with format='json'", file=sys.stderr)
            payload["format"] = "json"
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
        else:
            raise
    except requests.RequestException as req_err:
        # Network/timeout issues: retry once (keep format='json' if enabled)
        if format_json:
            if debug:
                print("[DEBUG] /api/generate request error → retrying once", file=sys.stderr)
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
        else:
            raise
    data = r.json()
    if debug_raw:
        try:
            print("[DEBUG-RAW] /api/generate HTTP JSON BEGIN", file=sys.stderr)
            print(json.dumps(data)[:2000], file=sys.stderr)
            print("[DEBUG-RAW] /api/generate HTTP JSON END", file=sys.stderr)
        except Exception:
            pass
    content = (data.get("response") or "").strip()
    if debug:
        head = content[:300].replace("\n", " ")
        print(f"[DEBUG] /api/generate raw head[300]: {head}", file=sys.stderr)
    if debug_raw:
        print("[DEBUG-RAW] /api/generate full response BEGIN", file=sys.stderr)
        print(content, file=sys.stderr)
        print("[DEBUG-RAW] /api/generate full response END", file=sys.stderr)
    block = extract_first_json_block(content)
    if not block:
        return []
    try:
        parsed = json.loads(block)
    except Exception:
        return []
    return coerce_rules_from_parsed(parsed)


def ollama_chat_json(model: str, system: str, user: str, timeout: int = 120, debug: bool = False, debug_raw: bool = False, format_json: bool = True, fewshots: list[tuple[str, list[dict]]] | None = None) -> list[dict]:
    """
    Calls Ollama's chat API with a system+user prompt, attempts to coerce JSON output.
    Falls back to /api/generate if /api/chat is not available (404).
    """
    url = "http://localhost:11434/api/chat"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Example:\n{FEWSHOT_INPUT}"},
        {"role": "assistant", "content": json.dumps(FEWSHOT_OUTPUT, ensure_ascii=False)},
    ]
    if fewshots:
        for ex_input, ex_output in fewshots:
            try:
                messages.append({"role": "user", "content": f"Example:\n{ex_input}"})
                messages.append({"role": "assistant", "content": json.dumps(ex_output, ensure_ascii=False)})
            except Exception:
                continue
    # messages.append(
    #     {
    #         "role": "user",
    #         "content": "Bad example (do NOT copy):\n"
    #                    f"{FEWSHOT_BAD_INPUT}\n"
    #                    "Incorrect output (duplicates the same clause twice):"
    #     }
    # )
    # messages.append(
    #     {
    #         "role": "assistant",
    #         "content": json.dumps(FEWSHOT_BAD_OUTPUT, ensure_ascii=False)
    #     }
    # )
    # messages.append({"role": "user", "content": "Never replicate the bad example above."})
    messages.append({"role": "user", "content": BAD_EXPLANATION})
    messages.append({"role": "user", "content": user})

    payload = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "messages": messages,
        "stream": False
    }
    if format_json:
        payload["format"] = "json"
    try:
        if debug:
            print("[DEBUG] calling Ollama /api/chat", file=sys.stderr)
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
    except requests.HTTPError as http_err:
        code = http_err.response.status_code if http_err.response is not None else None
        if code == 404:
            if debug:
                print("[DEBUG] /api/chat 404 → fallback to /api/generate", file=sys.stderr)
            return ollama_generate_json(model, system, user, timeout=timeout, debug=debug, debug_raw=debug_raw)
        # Fallback to plain JSON format if schema format unsupported
        if code in (400, 415):
            if format_json:
                if debug:
                    print("[DEBUG] /api/chat schema format not accepted → retrying with format='json'", file=sys.stderr)
                payload["format"] = "json"
                r = requests.post(url, json=payload, timeout=timeout)
                r.raise_for_status()
        # On server errors (5xx), fallback to generate endpoint
        elif code is not None and 500 <= code < 600:
            if debug:
                print("[DEBUG] /api/chat 5xx → fallback to /api/generate", file=sys.stderr)
            return ollama_generate_json(model, system, user, timeout=timeout, debug=debug, debug_raw=debug_raw, format_json=format_json, fewshots=fewshots)
        else:
            raise
    except requests.RequestException:
        # Network/timeout issues on chat: fallback to generate
        if debug:
            print("[DEBUG] /api/chat request error → fallback to /api/generate", file=sys.stderr)
        return ollama_generate_json(model, system, user, timeout=timeout, debug=debug, debug_raw=debug_raw, format_json=format_json, fewshots=fewshots)

    data = r.json()
    if debug_raw:
        try:
            print("[DEBUG-RAW] /api/chat HTTP JSON BEGIN", file=sys.stderr)
            print(json.dumps(data)[:2000], file=sys.stderr)
            print("[DEBUG-RAW] /api/chat HTTP JSON END", file=sys.stderr)
        except Exception:
            pass
    # Ollama returns {"message":{"content":"<json>"}...}
    content = data.get("message", {}).get("content", "").strip()
    if debug:
        head = content[:300].replace("\n", " ")
        print(f"[DEBUG] /api/chat raw head[300]: {head}", file=sys.stderr)
    if debug_raw:
        print("[DEBUG-RAW] /api/chat full response BEGIN", file=sys.stderr)
        print(content, file=sys.stderr)
        print("[DEBUG-RAW] /api/chat full response END", file=sys.stderr)
    block = extract_first_json_block(content)
    if not block:
        return []
    try:
        parsed = json.loads(block)
    except Exception:
        return []
    return coerce_rules_from_parsed(parsed)

# ---------- PDF utils ----------
def read_pdf_pages(pdf_path: Path) -> list[str]:
    # Try PyMuPDF (fitz) first; fallback to pdfminer.six if unavailable
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path.as_posix())
        pages = [p.get_text("text") for p in doc]
        doc.close()
        return pages
    except Exception:
        try:
            from pdfminer.high_level import extract_text
            from pdfminer.pdfpage import PDFPage
            pages: list[str] = []
            with open(pdf_path, "rb") as f:
                for i, _ in enumerate(PDFPage.get_pages(f)):
                    text = extract_text(pdf_path.as_posix(), page_numbers=[i])
                    pages.append(text or "")
            return pages
        except Exception as e:
            raise RuntimeError(f"Failed to read PDF via PyMuPDF and pdfminer: {e}")

def windowed(pages: list[str], w: int, overlap: int):
    if w <= 0:
        w = 1
    step = max(1, w - overlap)
    i = 0
    while i < len(pages):
        yield (i, pages[i:i+w])          # start index, window pages text
        i += step

# ---------- Validation ----------
def validate_rule(item: dict) -> bool:
    cleaned = sanitize_for_schema(item)
    errors = list(VALIDATOR.iter_errors(cleaned))
    if errors:
        # Helpful debug: surface first error
        try:
            msg = errors[0].message
        except Exception:
            msg = "schema validation failed"
        item.setdefault("repair_notes", []).append(f"schema_invalid:{msg}")
        return False
    # additional consistency checks
    if not str(cleaned.get("rule_id", "")).startswith("ICDR_"):
        return False
    if not str(cleaned.get("lean_id", "")).startswith("rule_"):
        return False
    # keep a schema-clean version for writing
    item["_sanitized"] = cleaned
    return True

# ---------- Regulation detection and span_hint helpers ----------
REG_RE = re.compile(r"(?:Regulation|Reg\.?|Chapter)\s+(\d+)\b", re.I)
CLAUSE_PREFIX_RE = re.compile(r"\b(\d+)\s*\(\d+\)(?:\([a-z]\))?")
HEADING_NUMBER_RE = re.compile(r"^\s*(\d{1,3})\s*\.", re.M)
RULE_ID_PREFIX_RE = re.compile(r"^ICDR[_\-\s]*(.+)$", re.I)
CLAUSE_TOKEN_SPLIT_RE = re.compile(r"[_\s]+")
SOURCE_NUM_RE = re.compile(r"(\d+)")
SOURCE_CLAUSE_RE = re.compile(r"\((\d+|[A-Za-z])\)")

def detect_allowed_regs(window_text: str) -> set[int]:
    """
    Detect regulation numbers explicitly present within the window text.
    Includes explicit 'Regulation X' mentions and clause prefixes like '6(1)(a)'.
    """
    regs: set[int] = set()
    for m in REG_RE.finditer(window_text):
        try:
            regs.add(int(m.group(1)))
        except Exception:
            continue
    for m in CLAUSE_PREFIX_RE.finditer(window_text):
        try:
            regs.add(int(m.group(1)))
        except Exception:
            continue
    for m in HEADING_NUMBER_RE.finditer(window_text):
        try:
            regs.add(int(m.group(1)))
        except Exception:
            continue
    return regs

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()

def contains_span_hint(window_text: str, hint: str) -> bool:
    """
    Case-insensitive, whitespace-normalized containment check for span_hint.
    """
    if not hint or not isinstance(hint, str):
        return False
    wt = normalize_ws(window_text)
    ht = normalize_ws(hint)
    return bool(ht) and ht in wt

def normalize_lenient(s: str) -> str:
    """
    Lenient normalization for PDF text:
    - Unicode NFKC
    - Lowercase
    - Replace non-word characters with single spaces
    - Collapse whitespace
    """
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def contains_span_hint_lenient(window_text: str, hint: str) -> bool:
    if not hint or not isinstance(hint, str):
        return False
    normalized_window = normalize_lenient(window_text)
    normalized_hint = normalize_lenient(hint)
    if not normalized_hint:
        return False
    if normalized_hint in normalized_window:
        return True
    window_tokens = normalized_window.split()
    hint_tokens = normalized_hint.split()
    if not hint_tokens:
        return False
    pos = 0
    for token in hint_tokens:
        try:
            idx = window_tokens.index(token, pos)
        except ValueError:
            return False
        pos = idx + 1
    return True


def contains_span_hint_fuzzy(window_text: str, hint: str, threshold: float = 0.72) -> bool:
    """
    Fuzzy fallback using difflib on normalized text.
    """
    import difflib

    if not hint or not isinstance(hint, str):
        return False
    normalized_window = normalize_lenient(window_text)
    normalized_hint = normalize_lenient(hint)
    if not normalized_hint:
        return False
    if normalized_hint in normalized_window:
        return True
    if len(normalized_hint) < 6:
        return False
    ratio = difflib.SequenceMatcher(None, normalized_hint, normalized_window).quick_ratio()
    return ratio >= threshold


MIN_TEXT_CHARS = 90
TEXT_SIGNATURE_SLICE = 160


def normalize_clause_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def item_score(it: dict) -> tuple[float, int, int, int]:
    try:
        confidence = float(it.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0
    norm_text = it.get("_norm_text") or normalize_clause_text(it.get("text", ""))
    span_hint = ""
    source = it.get("source")
    if isinstance(source, dict):
        span_hint = source.get("span_hint", "") or ""
    repair_penalty = -len(it.get("repair_notes", [])) if isinstance(it.get("repair_notes"), list) else 0
    return (
        round(confidence, 6),
        len(norm_text),
        repair_penalty,
        len(span_hint),
    )


def choose_best_item(existing: dict, candidate: dict) -> dict:
    if item_score(candidate) > item_score(existing):
        return candidate
    return existing


def extract_reg_from_source_text(reg_text: str) -> int | None:
    if not isinstance(reg_text, str):
        return None
    m = REG_RE.search(reg_text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m = SOURCE_NUM_RE.search(reg_text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def normalize_rule_identifier(item: dict) -> int | None:
    raw_rule_id = str(item.get("rule_id", "")).strip()
    if not raw_rule_id:
        return None
    body_match = RULE_ID_PREFIX_RE.match(raw_rule_id)
    if not body_match:
        return None
    body = body_match.group(1)
    body = (
        body.replace("(", "_")
        .replace(")", "_")
        .replace(".", "_")
        .replace("__", "_")
    )
    body = re.sub(r"[^0-9A-Za-z_]+", "_", body)
    body = re.sub(r"_+", "_", body).strip("_")
    tokens = [tok for tok in CLAUSE_TOKEN_SPLIT_RE.split(body) if tok]
    reg_token = None
    rest_tokens: list[str] = []
    for tok in tokens:
        if reg_token is None and tok.isdigit():
            reg_token = tok
        else:
            rest_tokens.append(tok.lower())

    source = item.get("source") or {}
    source_reg = source.get("reg", "") if isinstance(source, dict) else ""
    reg_from_source = extract_reg_from_source_text(source_reg)
    reg_no = None
    repair_notes: list[str] = []
    if reg_token:
        reg_no = int(reg_token)
    if reg_from_source is not None:
        if reg_no is None:
            reg_no = reg_from_source
            repair_notes.append("reg_inferred_from_source")
        elif reg_no != reg_from_source:
            reg_no = reg_from_source
            repair_notes.append(
                f"reg_mismatch(rule:{reg_token}→source:{reg_from_source})"
            )
    if reg_no is None:
        return None

    suffix = "_".join(rest_tokens)
    normalized_rule_id = f"ICDR_{reg_no}"
    if suffix:
        normalized_rule_id += f"_{suffix}"

    item["rule_id_raw"] = raw_rule_id
    item["rule_id"] = normalized_rule_id
    item["rule_id_norm"] = f"ICDR_{reg_no}"
    item["sub_id"] = suffix
    item["lean_id"] = "rule_" + normalized_rule_id[5:].lower()
    if repair_notes:
        item.setdefault("repair_notes", []).extend(repair_notes)
    return reg_no

# ---------- Main pipeline ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default="data/processed/rules.jsonl")
    ap.add_argument("--model", default="llama3:8b")
    ap.add_argument("--window", type=int, default=2, help="pages per window")
    ap.add_argument("--overlap", type=int, default=1, help="overlap pages between windows")
    ap.add_argument("--max-pages", type=int, default=0, help="limit total pages (0 = all)")
    ap.add_argument("--reg-filter", nargs=2, type=int, default=None, metavar=("START","END"),
                    help="Keep only rules whose rule_id mentions regulations in [START..END] (e.g., 14 22)")
    ap.add_argument("--dedupe", action="store_true")
    ap.add_argument("--debug-raw", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--endpoint", choices=["auto","chat","generate"], default="auto",
                    help="Which Ollama endpoint to use (default auto: chat→generate fallback)")
    ap.add_argument("--no-format", action="store_true",
                    help="Do not set format=json; rely on prompt to request JSON")
    ap.add_argument("--fewshot", type=str, default=None,
                    help="Path to JSON file with few-shot examples: [{\"input\": str, \"output\": [..]}]")
    ap.add_argument("--timeout", type=int, default=120,
                    help="HTTP timeout (seconds) per model call")
    ap.add_argument("--span-mode", choices=["strict","lenient"], default="lenient",
                    help="Span hint verification mode: strict (exact, whitespace-insensitive) or lenient (unicode/punctuation-insensitive)")
    ap.add_argument("--no-anchoring", action="store_true",
                    help="Disable regulation anchoring (do not drop rules whose regulation number is not visible in the window)")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # load existing for dedupe
    existing_rule_ids = set()
    if args.dedupe and out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    existing_rule_ids.add(json.loads(line)["rule_id"])
                except Exception:
                    pass

    pages = read_pdf_pages(pdf)
    if args.max_pages and args.max_pages > 0:
        pages = pages[:args.max_pages]

    total_written = 0
    selected_items: dict[str, dict] = {}
    item_order: list[str] = []
    signature_to_key: dict[str, str] = {}

    for start_idx, chunk in windowed(pages, args.window, args.overlap):
        # Build user prompt for this chunk
        visible = "\n\n--- PAGE BREAK ---\n\n".join(chunk)
        if args.debug:
            print(f"[DEBUG] window start={start_idx} chars={len(visible)}", file=sys.stderr)
            if len(visible.strip()) < 200:
                print("[WARN] window text is tiny; PDF text extraction likely failed for this window", file=sys.stderr)
        page_nums = list(range(start_idx+1, start_idx+1+len(chunk)))  # 1-based
        # Detect allowed regulations for anchoring
        allowed_regs = detect_allowed_regs(visible)
        user = (
            f"PDF: {pdf.name}\n"
            f"PAGES: {page_nums}\n\n"
            f"TEXT:\n{visible}\n\n"
            "Extract atomic SEBI ICDR rules ONLY from these pages."
        )

        try:
            format_json = not args.no_format
            fewshots = load_fewshot_examples(args.fewshot)
            endpoint = args.endpoint
            if endpoint == "chat":
                items = ollama_chat_json(args.model, SYSTEM_PROMPT, user, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw, format_json=format_json, fewshots=fewshots)
            elif endpoint == "generate":
                items = ollama_generate_json(args.model, SYSTEM_PROMPT, user, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw, format_json=format_json, fewshots=fewshots)
            else:  # auto
                items = ollama_chat_json(args.model, SYSTEM_PROMPT, user, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw, format_json=format_json, fewshots=fewshots)
                if not items:
                    if args.debug:
                        print("[DEBUG] chat returned no items → trying /api/generate", file=sys.stderr)
                    items = ollama_generate_json(args.model, SYSTEM_PROMPT, user, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw, format_json=format_json, fewshots=fewshots)
        except Exception as e:
            print(f"[WARN] model call failed at pages {page_nums}: {e}", file=sys.stderr)
            continue

        # Salvage: flatten common "subrules" shape into valid rule objects
        flat_items: list[dict] = []
        for it in items:
            if isinstance(it, dict):
                flat_items.extend(flatten_subrules(it))
        if not flat_items and items:
            # if items were non-dicts, nothing to do
            flat_items = [it for it in items if isinstance(it, dict)]

        for it in flat_items:
            # Guard: only process dict items; try to coerce JSON strings
            if not isinstance(it, dict):
                if isinstance(it, str):
                    try:
                        maybe = json.loads(it)
                    except Exception:
                        continue
                    if not isinstance(maybe, dict):
                        continue
                    it = maybe
                else:
                    continue

            # inject/ensure source fields
            it.setdefault("domain", "SEBI_ICDR")
            if not isinstance(it.get("source"), dict):
                it["source"] = {}
            it["source"].setdefault("pdf", pdf.name)
            it["source"].setdefault("pages", page_nums)

            reg_no = normalize_rule_identifier(it)
            if reg_no is None:
                if args.debug:
                    print("[DEBUG] dropping item without normalizable rule_id:", it.get("rule_id"), file=sys.stderr)
                continue

            # Regulation anchoring: drop if normalized regulation not visible (with ±1 tolerance) unless disabled
            if not args.no_anchoring and allowed_regs:
                nearest = min((abs(reg_no - r) for r in allowed_regs), default=None)
                if nearest is None:
                    pass
                elif nearest == 0:
                    pass
                elif nearest == 1:
                    it.setdefault("repair_notes", []).append(
                        f"anchoring_slack±1(allowed={sorted(allowed_regs)})"
                    )
                    try:
                        conf = float(it.get("confidence", 0.9))
                    except Exception:
                        conf = 0.9
                    it["confidence"] = max(0.0, round(conf - 0.1, 3))
                else:
                    if args.debug:
                        print(
                            f"[DEBUG] dropping {it.get('rule_id')} due to anchoring (allowed={sorted(allowed_regs)})",
                            file=sys.stderr,
                        )
                    continue

            # span_hint verification: must exist and be found verbatim (normalized) in window
            span_hint = ""
            if isinstance(it.get("source"), dict):
                span_hint = it["source"].get("span_hint", "") or ""
            if args.span_mode == "lenient":
                ok_span = contains_span_hint_lenient(visible, span_hint) or contains_span_hint_fuzzy(visible, span_hint)
            else:
                ok_span = contains_span_hint(visible, span_hint) or contains_span_hint_fuzzy(visible, span_hint)
            if not ok_span:
                # Keep the item but mark a repair note and lower confidence slightly
                it.setdefault("repair_notes", []).append("span_hint_unmatched")
                try:
                    conf = float(it.get("confidence", 0.9))
                except Exception:
                    conf = 0.9
                it["confidence"] = max(0.0, round(conf - 0.15, 3))
            # filter by regulation range if requested
            if args.reg_filter:
                lo, hi = args.reg_filter
                if reg_no < lo or reg_no > hi:
                    continue

            # validate basic schema
            if not validate_rule(it):
                continue
            rid = it["rule_id"]
            if args.dedupe and rid in existing_rule_ids:
                continue

            normalized_text = normalize_clause_text(it.get("text", ""))
            if len(normalized_text) < MIN_TEXT_CHARS:
                continue
            it["_norm_text"] = normalized_text
            text_signature = normalized_text[:TEXT_SIGNATURE_SLICE]

            base_key = f"{it.get('rule_id_norm')}|{it.get('sub_id') or ''}"
            signature_key = signature_to_key.get(text_signature)
            if signature_key:
                key = signature_key
            else:
                key = base_key
                signature_to_key[text_signature] = key

            existing_item = selected_items.get(key)
            if existing_item is None:
                selected_items[key] = it
                item_order.append(key)
                if args.debug:
                    src_pages = (it.get("source") or {}).get("pages") if isinstance(it.get("source"), dict) else None
                    print(f"[ACCEPT] {it.get('rule_id')} pages={src_pages}", file=sys.stderr)
            else:
                best = choose_best_item(existing_item, it)
                if best is not existing_item:
                    selected_items[key] = best
                    if args.debug:
                        src_pages = (best.get("source") or {}).get("pages") if isinstance(best.get("source"), dict) else None
                        print(f"[ACCEPT] updated {best.get('rule_id')} pages={src_pages}", file=sys.stderr)

        # small pause to be gentle on local model
        time.sleep(0.1)

    if not selected_items:
        print("No Lean content generated (all items filtered); writing nothing.", file=sys.stderr)
        return

    with out.open("a", encoding="utf-8") as f_out:
        for key in item_order:
            item = selected_items[key]
            item.pop("_norm_text", None)
            # Write schema-clean record (drop internal keys like rule_id_norm, repair_notes, etc.)
            to_write = item.get("_sanitized")
            if not isinstance(to_write, dict):
                to_write = sanitize_for_schema(item)
            f_out.write(json.dumps(to_write, ensure_ascii=False) + "\n")
            total_written += 1
            if args.debug:
                rid = to_write.get("rule_id", "?") if isinstance(to_write, dict) else "?"
                pages = (to_write.get("source", {}) or {}).get("pages") if isinstance(to_write, dict) else None
                print(f"[WRITE] {rid} pages={pages}", file=sys.stderr)

    print(f"✅ Wrote {total_written} unique rules → {out}")

if __name__ == "__main__":
    main()

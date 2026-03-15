#!/usr/bin/env python3
"""
infer_issuer_fields_with_llm.py

LLM-augmented issuer field inference from PDF text.
This script is *opt-in* and outputs suggestions only, keeping the deterministic
pipeline unchanged.

Inputs:
  --pdf (required)
  --rules_jsonl (required; used to mark fields already present in maps_to)
  --out (default: data/processed/issuer_fields_suggested.json)
  --report-out (default: data/processed/issuer_fields_llm_report.json)

Behavior:
  - Uses Ollama /api/generate with format=json
  - Extracts candidate fields + evidence quotes from PDF windows
  - Applies deterministic filters:
      * snake_case field names
      * evidence quote must appear in window (lenient match)
      * optional type_hint normalized to vocabulary
  - Deduplicates by field name and sorts deterministically
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
import unicodedata


TYPE_HINT_VOCAB = {
    "Bool",
    "Nat",
    "List Nat",
    "String",
    "OptionBool",
    "OptionNat",
    "OptionListNat",
    "OptionString",
}

GENERIC_PENALTY = {"conditions", "misc", "as_applicable", "other", "notes"}


def extract_first_json_block(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    # strip fenced code
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I).strip()
    s = re.sub(r"\s*```$", "", s).strip()
    start = None
    opener = ""
    for i, ch in enumerate(s):
        if ch in "{[":
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


def normalize_field_token(token: str) -> Tuple[str, List[str]]:
    applied: List[str] = []
    t = token.strip()
    if not t:
        return "", applied
    changed = True
    while changed and t.startswith("(") and t.endswith(")") and len(t) > 1:
        t = t[1:-1].strip()
        applied.append("strip_outer_parens")
        changed = t.startswith("(") and t.endswith(")")
    if "(" in t or ")" in t:
        t = re.sub(r"[()]", " ", t)
        applied.append("drop_paren_chars")
    new_t = re.sub(r"\s*(?:length\s*=\s*\d+|>=|<=|=|>|<).*$", "", t)
    if new_t != t:
        t = new_t
        applied.append("drop_comparator_or_length")
    new_t = t.strip(" ,.;:")
    if new_t != t:
        t = new_t
        applied.append("trim_punct")
    new_t = re.sub(r"[\s\-]+", "_", t)
    if new_t != t:
        t = new_t
        applied.append("collapse_space_hyphen")
    t = t.strip("_")
    if not t:
        return "", applied
    return t, applied


def normalize_type_hint(t: str) -> str:
    t = (t or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t)
    if t in TYPE_HINT_VOCAB:
        return t
    if t == "ListNat":
        return "List Nat"
    return ""


def normalize_lenient(s: str) -> str:
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


def read_jsonl(path: Path) -> List[dict]:
    items: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            items.append(obj)
    return items


def read_pdf_pages(pdf_path: Path) -> List[str]:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path.as_posix())
        pages = [p.get_text("text") for p in doc]
        doc.close()
        return pages
    except Exception:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
        pages: List[str] = []
        with open(pdf_path, "rb") as f:
            for i, _ in enumerate(PDFPage.get_pages(f)):
                text = extract_text(pdf_path.as_posix(), page_numbers=[i])
                pages.append(text or "")
        return pages


def windowed(pages: List[str], w: int, overlap: int):
    if w <= 0:
        w = 1
    step = max(1, w - overlap)
    i = 0
    while i < len(pages):
        yield (i, pages[i : i + w])
        i += step


def ollama_generate_json(model: str, prompt: str, timeout: int = 120, debug: bool = False, debug_raw: bool = False) -> Any:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    if debug:
        head = prompt[:300].replace("\n", " ")
        print(f"[DEBUG] /api/generate prompt head[300]: {head}")
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if debug_raw:
        try:
            print("[DEBUG-RAW] /api/generate HTTP JSON BEGIN")
            print(json.dumps(data)[:2000])
            print("[DEBUG-RAW] /api/generate HTTP JSON END")
        except Exception:
            pass
    content = (data.get("response") or "").strip()
    if debug:
        head = content[:300].replace("\n", " ")
        print(f"[DEBUG] /api/generate raw head[300]: {head}")
    block = extract_first_json_block(content)
    if not block:
        return []
    try:
        return json.loads(block)
    except Exception:
        return []


def build_prompt(chunk_text: str, pdf_name: str, pages: List[int]) -> str:
    # Keep chunk text bounded
    text = chunk_text.strip()
    if len(text) > 12000:
        text = text[:12000] + "\n\n[TRUNCATED]"
    return (
        "You are extracting issuer/offer field candidates from SEBI ICDR text.\n"
        "Return STRICT JSON only (no markdown).\n\n"
        "Output format: JSON array of objects:\n"
        "[\n"
        "  {\n"
        "    \"field\": \"snake_case_name\",\n"
        "    \"type_hint\": \"Bool|Nat|List Nat|String|OptionBool|OptionNat|OptionListNat|OptionString\",\n"
        "    \"evidence_quote\": \"verbatim quote from text (<=120 chars)\"\n"
        "  }\n"
        "]\n\n"
        "Rules:\n"
        "- Only propose fields clearly supported by the text.\n"
        "- Evidence quote MUST be a direct substring from the text window.\n"
        "- Use bare snake_case identifiers (no units/conditions in names).\n"
        "- If unsure about type_hint, use \"\".\n\n"
        f"PDF: {pdf_name}\n"
        f"PAGES: {pages}\n\n"
        f"TEXT:\n{text}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--rules_jsonl", required=True)
    ap.add_argument("--out", default="data/processed/issuer_fields_suggested.json")
    ap.add_argument("--report-out", default="data/processed/issuer_fields_llm_report.json")
    ap.add_argument("--model", default="llama3:8b")
    ap.add_argument("--window", type=int, default=2)
    ap.add_argument("--overlap", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--debug-raw", action="store_true")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    rules = read_jsonl(Path(args.rules_jsonl))
    existing_fields = set()
    for r in rules:
        maps_to = r.get("maps_to")
        if isinstance(maps_to, list):
            for m in maps_to:
                if isinstance(m, dict):
                    raw = str(m.get("field") or "").strip()
                    if raw:
                        normalized, _ = normalize_field_token(raw)
                        if normalized:
                            existing_fields.add(normalized)

    pages = read_pdf_pages(pdf)
    if args.debug:
        print(f"[DEBUG] PDF pages loaded: {len(pages)}")
    suggestions: Dict[str, Dict[str, Any]] = {}
    dropped: List[Dict[str, Any]] = []

    for start_idx, chunk in windowed(pages, args.window, args.overlap):
        visible = "\n\n--- PAGE BREAK ---\n\n".join(chunk)
        page_nums = list(range(start_idx + 1, start_idx + 1 + len(chunk)))
        if args.debug:
            print(f"[DEBUG] window start={start_idx} pages={page_nums} chars={len(visible)}")
        prompt = build_prompt(visible, pdf.name, page_nums)
        try:
            resp = ollama_generate_json(
                args.model,
                prompt,
                timeout=args.timeout,
                debug=args.debug,
                debug_raw=args.debug_raw,
            )
        except Exception as e:
            dropped.append({"window_start": start_idx, "reason": f"llm_error:{type(e).__name__}"})
            if args.debug:
                print(f"[WARN] LLM error at window {start_idx}: {e}")
            continue
        if not isinstance(resp, list):
            dropped.append({"window_start": start_idx, "reason": "bad_json_shape"})
            if args.debug:
                print(f"[WARN] bad JSON shape at window {start_idx}: {type(resp).__name__}")
            continue
        for obj in resp:
            if not isinstance(obj, dict):
                continue
            raw_field = str(obj.get("field") or "").strip()
            raw_quote = str(obj.get("evidence_quote") or "").strip()
            raw_type = str(obj.get("type_hint") or "").strip()
            if not raw_field or not raw_quote:
                dropped.append({"field": raw_field, "reason": "missing_field_or_quote"})
                if args.debug:
                    print(f"[DEBUG] drop field='{raw_field}' reason=missing_field_or_quote")
                continue
            if len(raw_quote) > 120:
                raw_quote = raw_quote[:120].rstrip()
            normalized, _ = normalize_field_token(raw_field)
            if not normalized or not re.match(r"^[a-z][a-z0-9_]*$", normalized):
                dropped.append({"field": raw_field, "reason": "bad_field_name"})
                if args.debug:
                    print(f"[DEBUG] drop field='{raw_field}' reason=bad_field_name")
                continue
            if normalized in GENERIC_PENALTY:
                dropped.append({"field": normalized, "reason": "generic_field"})
                if args.debug:
                    print(f"[DEBUG] drop field='{normalized}' reason=generic_field")
                continue
            if not contains_span_hint_lenient(visible, raw_quote):
                dropped.append({"field": normalized, "reason": "quote_not_in_text"})
                if args.debug:
                    print(f"[DEBUG] drop field='{normalized}' reason=quote_not_in_text")
                continue
            type_hint = normalize_type_hint(raw_type)

            cur = suggestions.get(normalized)
            if cur is None:
                if args.debug:
                    print(f"[DEBUG] accept field='{normalized}' type_hint='{type_hint}'")
                suggestions[normalized] = {
                    "name": normalized,
                    "type_hint": type_hint,
                    "already_in_rules": normalized in existing_fields,
                    "evidence": [
                        {
                            "pdf": pdf.name,
                            "pages": page_nums,
                            "quote": raw_quote,
                        }
                    ],
                }
            else:
                if not cur.get("type_hint") and type_hint:
                    cur["type_hint"] = type_hint
                if args.debug and type_hint:
                    print(f"[DEBUG] update type_hint field='{normalized}' -> '{type_hint}'")
                evidence = cur.get("evidence") or []
                entry = {"pdf": pdf.name, "pages": page_nums, "quote": raw_quote}
                if entry not in evidence:
                    evidence.append(entry)
                cur["evidence"] = evidence

    out_list = sorted(suggestions.values(), key=lambda o: str(o.get("name", "")))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_list, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "pdf": pdf.name,
        "rules_jsonl": str(Path(args.rules_jsonl)),
        "total_suggested": len(out_list),
        "total_dropped": len(dropped),
        "dropped_samples": dropped[:100],
    }
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out_list)} suggested fields to {out_path}")
    print(f"Wrote LLM report to {report_path}")


if __name__ == "__main__":
    main()

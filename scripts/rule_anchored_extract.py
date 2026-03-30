#!/usr/bin/env python3
"""
rule_anchored_extract.py

Rule-anchored evidence extraction from an RHP PDF/text.
For each (rule_id, field) pair in rules.jsonl, attempt to extract:
  - evidence quote (mandatory if value present)
  - page number(s) (best effort)
  - raw value string
  - candidate parses: Bool, Nat, List Nat, String
  - confidence score

Output: JSONL, one record per (rule_id, field) attempt.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

import unicodedata

try:
    from scripts.utils import read_jsonl, parse_bool, parse_number, extract_first_json_block  # type: ignore[import-not-found]
except ImportError:
    from utils import read_jsonl, parse_bool, parse_number, extract_first_json_block  # type: ignore


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


def read_pdf_pages(path: Path) -> List[str]:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path.as_posix())
        pages = [p.get_text("text") for p in doc]
        doc.close()
        return pages
    except Exception:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
        pages: List[str] = []
        with open(path, "rb") as f:
            for i, _ in enumerate(PDFPage.get_pages(f)):
                text = extract_text(path.as_posix(), page_numbers=[i])
                pages.append(text or "")
        return pages


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




def ollama_request(endpoint: str, model: str, prompt: str, timeout: int = 180, debug: bool = False) -> Any:
    url = "http://localhost:11434/api/" + ("generate" if endpoint == "generate" else "chat")
    if endpoint == "chat":
        payload = {
            "model": model,
            "options": {"temperature": 0.1, "top_p": 0.9},
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        }
    else:
        payload = {
            "model": model,
            "options": {"temperature": 0.1, "top_p": 0.9},
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    if debug:
        print(f"[DEBUG] calling Ollama /api/{'generate' if endpoint=='generate' else 'chat'}")
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = (data.get("response") if endpoint == "generate" else (data.get("message", {}) or {}).get("content", "")) or ""
    block = extract_first_json_block(content)
    if not block:
        return {}
    try:
        return json.loads(block)
    except Exception:
        return {}


def simple_keyword_score(text: str, keywords: List[str]) -> int:
    txt = text.lower()
    score = 0
    for kw in keywords:
        k = kw.strip().lower()
        if not k:
            continue
        score += txt.count(k)
    return score


def select_evidence_pages(pages: List[str], rule_text: str, field: str, topk: int) -> List[Tuple[int, str]]:
    tokens = re.findall(r"[A-Za-z]+", rule_text) + re.findall(r"[A-Za-z]+", field.replace("_", " "))
    seen = set()
    keywords = []
    for t in tokens:
        if len(t) < 3:
            continue
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            keywords.append(tl)
    scored = []
    for idx, p in enumerate(pages, start=1):
        scored.append((simple_keyword_score(p, keywords), idx, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    sel = [(idx, p) for (s, idx, p) in scored[:max(1, topk)] if s > 0]
    if not sel and pages:
        sel = [(1, pages[0])]
    return sel




def parse_nat(raw: str) -> int | None:
    return parse_number(raw)


def parse_list_nat(raw: str) -> List[int] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        vals = [parse_nat(x) for x in raw]
        return [v for v in vals if v is not None]
    # Do NOT split on commas; only allow explicit list separators
    s = str(raw)
    if not re.search(r"[;|/]", s):
        return None
    parts = re.split(r"[;|/]+", s)
    vals: List[int] = []
    for p in parts:
        v = parse_number(p)
        if v is not None:
            vals.append(v)
    return vals if vals else None


def parse_table_numbers(values: List[str]) -> List[int]:
    out: List[int] = []
    for v in values:
        num = parse_number(v)
        if num is not None:
            out.append(num)
    return out


def _field_to_keywords(field: str) -> List[str]:
    """
    Generate candidate label-search keywords from a field name.
    Splits on underscores, strips common non-semantic suffixes, and forms
    both the full phrase and individual tokens.
    """
    _STRIP_SUFFIXES = ("_ratio", "_pct", "_count", "_amount", "_value", "_rate", "_flag")
    base = field
    for sfx in _STRIP_SUFFIXES:
        if base.endswith(sfx):
            base = base[: -len(sfx)]
            break
    tokens = [t for t in base.split("_") if len(t) > 1]
    phrase = " ".join(tokens)
    candidates = [phrase]
    # Also include sub-phrases (pairs of adjacent tokens) for compound concepts
    for i in range(len(tokens) - 1):
        candidates.append(f"{tokens[i]} {tokens[i+1]}")
    # Individual tokens (only meaningful ones, len >= 3)
    candidates += [t for t in tokens if len(t) >= 3]
    return candidates


def find_table_row(field: str, rule_text: str, tables: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """
    Search table rows for the best label match for *field*.

    Strategy (in priority order):
    1. High-confidence override map  — exact field-name → keyword list.
    2. Dynamic keyword list via _field_to_keywords()  — substring matching.
    3. Token-overlap fuzzy fallback  — intersect field name tokens against row
       label tokens; require ≥ 2 overlapping tokens to avoid false positives.
    """
    # High-confidence override map — stays as primary path
    _OVERRIDE: Dict[str, List[str]] = {
        "net_tangible_assets": ["net tangible assets"],
        "operating_profits": ["operating profit", "average operating profit"],
        "net_worth": ["net worth"],
        "net_worths": ["net worth"],
        "monetary_asset_ratio": ["percentage of monetary assets", "in %", "(d)/(a)"],
    }

    def _make_result(t: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "page": t.get("page"),
            "table_index": t.get("table_index"),
            "label": row.get("label"),
            "values": row.get("values") or [],
            "unit": row.get("unit") or "",
        }

    # ── Phase 1: keyword substring matching (override or dynamic) ────────────
    ks = _OVERRIDE.get(field) or _field_to_keywords(field)
    best_match: Dict[str, Any] | None = None
    best_score = 0

    if ks:
        for t in tables:
            for row in (t.get("rows") or []):
                label = str(row.get("label") or "").lower()
                score = sum(1 for k in ks if k in label)
                if score > best_score:
                    best_score = score
                    best_match = _make_result(t, row)

    if best_match:
        return best_match

    # ── Phase 2: token-overlap fuzzy fallback ────────────────────────────────
    # Split the field name on underscores, drop short stop-tokens.
    field_tokens = {
        tok for tok in field.lower().replace("_", " ").split()
        if len(tok) >= 3
    }
    if not field_tokens:
        return None

    fuzzy_best: Dict[str, Any] | None = None
    fuzzy_score = 0

    for t in tables:
        for row in (t.get("rows") or []):
            label = str(row.get("label") or "").lower()
            label_tokens = set(label.split())
            overlap = len(field_tokens & label_tokens)
            if overlap >= 2 and overlap > fuzzy_score:
                fuzzy_score = overlap
                fuzzy_best = _make_result(t, row)

    return fuzzy_best


def build_prompt(rule_id: str, field: str, rule_text: str, evidence: str) -> str:
    return (
        "Extract a value for the given field from the evidence text.\n"
        "Return STRICT JSON only (no markdown):\n"
        "{\n"
        "  \"value_raw\": \"...\",\n"
        "  \"evidence_quote\": \"verbatim quote from evidence (<=120 chars)\",\n"
        "  \"span_hint\": \"short hint from the quote\",\n"
        "  \"page\": 0\n"
        "}\n\n"
        "Rules:\n"
        "- evidence_quote must be a direct substring of the evidence text.\n"
        "- If value not found, use value_raw: \"\" and still provide the best evidence_quote.\n\n"
        f"RULE_ID: {rule_id}\nFIELD: {field}\nRULE_TEXT: {rule_text}\n\n"
        f"EVIDENCE TEXT:\n{evidence}\n"
    )


def run_extraction(
    rules_path: Path,
    rhp_path: Path,
    out_path: Path,
    model: str = "mistral:7b-instruct",
    endpoint: str = "generate",
    topk: int = 3,
    timeout: int = 180,
    tables_store_path: Path | None = None,
    max_rules: int = 0,
    debug: bool = False,
) -> int:
    """Core extraction logic, callable directly without argv manipulation."""
    rules = read_jsonl(rules_path)
    pages = read_pdf_pages(rhp_path)
    tables: List[Dict[str, Any]] = []
    if tables_store_path and tables_store_path.exists():
        try:
            tables = json.loads(tables_store_path.read_text(encoding="utf-8"))
        except Exception:
            tables = []
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in rules:
            if max_rules and total >= max_rules:
                break
            rule_id = r.get("rule_id") or r.get("id") or ""
            rule_text = r.get("text") or r.get("title") or ""
            maps_to = r.get("maps_to") if isinstance(r.get("maps_to"), list) else []
            for m in maps_to:
                if not isinstance(m, dict):
                    continue
                field = (m.get("field") or "").strip()
                if not field:
                    continue
                table_hit = find_table_row(field, rule_text, tables) if tables else None
                if table_hit:
                    values = table_hit.get("values") or []
                    nums = parse_table_numbers(values)
                    value_raw = ", ".join([str(v) for v in values])
                    quote = f"{table_hit.get('label')}: {value_raw}".strip()
                    record = {
                        "rule_id": rule_id,
                        "field": field,
                        "value_raw": value_raw,
                        "value_candidates": {
                            "Bool": None,
                            "Nat": nums[0] if nums else None,
                            "List Nat": nums if nums else None,
                            "String": value_raw,
                        },
                        "evidence": {
                            "page": table_hit.get("page") or 0,
                            "quote": quote[:120],
                            "span_hint": str(table_hit.get("label") or "")[:120],
                            "source": f"table:p{table_hit.get('page')}_t{table_hit.get('table_index')}",
                        },
                        "table_hit_used": True,
                        "tables_loaded_count": len(tables),
                        "table_source_id": f"p{table_hit.get('page')}_t{table_hit.get('table_index')}",
                        "used_pages": [table_hit.get("page")] if table_hit.get("page") else [],
                        "extract_confidence": 0.9,
                        "table_row": table_hit,
                        "numeric_policy": "commas removed; decimals dropped; units as presented",
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total += 1
                    continue
                sel = select_evidence_pages(pages, rule_text, field, topk)
                used_pages = [idx for (idx, _) in sel]
                evidence = "\n\n".join([f"[PAGE {idx}]\n{txt}" for (idx, txt) in sel])
                prompt = build_prompt(str(rule_id), field, rule_text, evidence)
                extract_conf = 0.4
                value_raw = ""
                quote = ""
                span_hint = ""
                page = used_pages[0] if used_pages else 0
                try:
                    ep = "generate" if endpoint == "auto" else endpoint
                    resp = ollama_request(ep, model, prompt, timeout=timeout, debug=debug)
                    if isinstance(resp, dict):
                        value_raw = str(resp.get("value_raw") or "")
                        quote = str(resp.get("evidence_quote") or "")
                        span_hint = str(resp.get("span_hint") or "")
                        page = int(resp.get("page") or page)
                except Exception:
                    value_raw = ""
                    quote = ""
                    span_hint = ""
                    extract_conf = 0.0

                if quote and not contains_span_hint_lenient(evidence, quote):
                    quote = ""
                    span_hint = ""
                    extract_conf = min(extract_conf, 0.2)

                bool_val = parse_bool(value_raw)
                nat_val = parse_nat(value_raw)
                list_nat_val = parse_list_nat(value_raw)
                str_val = value_raw if value_raw else ""
                record = {
                    "rule_id": rule_id,
                    "field": field,
                    "value_raw": value_raw,
                    "value_candidates": {
                        "Bool": bool_val,
                        "Nat": nat_val,
                        "List Nat": list_nat_val,
                        "String": str_val,
                    },
                    "evidence": {"page": page, "quote": quote, "span_hint": span_hint, "source": "text"},
                    "table_hit_used": False,
                    "tables_loaded_count": len(tables),
                    "table_source_id": None,
                    "used_pages": used_pages,
                    "extract_confidence": extract_conf,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total += 1

    print(f"Wrote {total} evidence records to {out_path}")
    return total


# Canonical short alias expected by schema_reconcile.py and Phase 1 spec.
run = run_extraction


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True, help="rules.jsonl with maps_to")
    ap.add_argument("--rhp", required=True, help="RHP PDF path")
    ap.add_argument("--out", required=True, help="Output evidence_store.jsonl")
    ap.add_argument("--model", default="mistral:7b-instruct")
    ap.add_argument("--endpoint", choices=["auto", "chat", "generate"], default="generate")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--tables-store", default="", help="Optional tables_store.json")
    ap.add_argument("--max-rules", type=int, default=0)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    tables_store_path = Path(args.tables_store) if args.tables_store else None
    run_extraction(
        rules_path=Path(args.rules),
        rhp_path=Path(args.rhp),
        out_path=Path(args.out),
        model=args.model,
        endpoint=args.endpoint,
        topk=args.topk,
        timeout=args.timeout,
        tables_store_path=tables_store_path,
        max_rules=args.max_rules,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()

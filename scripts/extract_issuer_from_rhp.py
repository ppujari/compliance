#!/usr/bin/env python3
# scripts/extract_issuer_from_rhp.py
"""
Extract issuer data from a Red Herring Prospectus (PDF or text) using:
- issuer schema (optional, not exhaustive)
- issuer questions produced by Lean generation JSON (rules_and_fields*.json)

The script asks a local LLM (Ollama) to answer the questions from the document
and returns a typed JSON issuer instance:
{
  "issuer_id": "<provided or inferred>",
  "source": "<pdf or text path>",
  "fields": { "<field>": <typed_value>, ... }
}
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _fitz_pages_text(path: Path, layout: str = "blocks") -> List[str]:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path.as_posix())
        pages: List[str] = []
        for p in doc:
            if layout == "blocks":
                # Preserve visual grouping; join blocks with blank lines
                blocks = p.get_text("blocks") or []
                # sort by y, then x
                blocks.sort(key=lambda b: (b[1], b[0]))
                page_txt = "\n\n".join([(b[4] or "").strip() for b in blocks if len(b) >= 5 and (b[4] or "").strip()])
                pages.append(page_txt)
            else:
                pages.append(p.get_text("text"))
        doc.close()
        return pages
    except Exception:
        return []

def _pdfminer_pages_text(path: Path) -> List[str]:
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
        texts: List[str] = []
        with open(path, "rb") as f:
            for i, _ in enumerate(PDFPage.get_pages(f)):
                t = extract_text(path.as_posix(), page_numbers=[i]) or ""
                texts.append(t)
        return texts
    except Exception:
        return []

def _pdfplumber_tables_text(path: Path) -> Dict[int, str]:
    """
    Optional table extraction using pdfplumber if available.
    Returns {page_index_1_based: table_text}
    """
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return {}
    tables_by_page: Dict[int, str] = {}
    try:
        with pdfplumber.open(path.as_posix()) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                lines: List[str] = []
                for tbl in tables:
                    # simple TSV-like join
                    for row in (tbl or []):
                        cells = [(c or "").strip() for c in row]
                        lines.append(" | ".join(cells))
                    if tbl:
                        lines.append("")  # blank line between tables
                if lines:
                    tables_by_page[i] = "\n".join(lines).strip()
    except Exception:
        pass
    return tables_by_page

def read_pdf_pages(path: Path, layout: str = "blocks", include_tables: bool = False) -> List[str]:
    # Try fitz first
    pages = _fitz_pages_text(path, layout=layout)
    if not pages:
        pages = _pdfminer_pages_text(path)
    if include_tables:
        tables = _pdfplumber_tables_text(path)
        if tables:
            merged: List[str] = []
            for idx, txt in enumerate(pages, start=1):
                extra = tables.get(idx)
                if extra:
                    merged.append(txt + "\n\n[TABLES]\n" + extra if txt else "[TABLES]\n" + extra)
                else:
                    merged.append(txt)
            pages = merged
    return pages

def split_pages_from_text(src: str, chunk_words: int = 800) -> List[str]:
    """
    If explicit page breaks exist, respect them. Otherwise, split into pseudo-pages by words.
    """
    if "--- PAGE BREAK ---" in src:
        return src.split("\n\n--- PAGE BREAK ---\n\n")
    words = re.split(r"(\s+)", src)
    pages: List[str] = []
    cur: List[str] = []
    count = 0
    for token in words:
        cur.append(token)
        if not token.isspace():
            count += 1
        if count >= chunk_words:
            pages.append("".join(cur).strip())
            cur, count = [], 0
    if cur:
        pages.append("".join(cur).strip())
    return pages


def load_questions(qpath: Path) -> List[Dict[str, str]]:
    obj = json.loads(qpath.read_text(encoding="utf-8"))
    qs = obj.get("issuer_questions") or []
    out: List[Dict[str, str]] = []
    for q in qs:
        field = (q.get("field") or "").strip()
        question = (q.get("question") or "").strip()
        typ = (q.get("type") or "String").strip()
        required_by = q.get("required_by") if isinstance(q, dict) else None
        if field and question:
            out.append({"field": field, "question": question, "type": typ, "required_by": required_by})
    return out

def load_schema_from_questions(qpath: Path) -> Dict[str, str]:
    """
    Prefer issuer_schema embedded in rules_and_fields*.json:
    { "issuer_schema": [ {"field": "...", "type": "Bool|Nat|List Nat|String"}, ... ] }
    Returns a mapping field -> Lean type string.
    """
    obj = json.loads(qpath.read_text(encoding="utf-8"))
    arr = obj.get("issuer_schema") or []
    m: Dict[str, str] = {}
    if isinstance(arr, list):
        for it in arr:
            if not isinstance(it, dict):
                continue
            f = (it.get("field") or "").strip()
            t = (it.get("type") or "").strip()
            if f and t:
                m[f] = t
    return m

def load_rules_index(qpath: Path) -> Dict[str, Dict[str, str]]:
    """
    Build an index {rule_id: {"title": ..., "reference": ...}} from rules array in rules_and_fields JSON.
    """
    obj = json.loads(qpath.read_text(encoding="utf-8"))
    rules = obj.get("rules") or []
    idx: Dict[str, Dict[str, str]] = {}
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("id") or r.get("rule_id") or r.get("reference")
        if not isinstance(rid, str):
            continue
        idx[rid] = {"title": r.get("title") or "", "reference": r.get("reference") or ""}
    return idx


def load_schema(spath: Path | None) -> Dict[str, str]:
    if not spath or not spath.exists():
        return {}
    obj = json.loads(spath.read_text(encoding="utf-8"))
    props = obj.get("properties", {}).get("fields", {}).get("properties", {}) or {}
    m: Dict[str, str] = {}
    for k, v in props.items():
        t = v.get("type")
        if t == "array":
            m[k] = "List Nat"
        elif t == "boolean":
            m[k] = "Bool"
        elif t == "integer":
            m[k] = "Nat"
        else:
            m[k] = "String"
    return m


def ollama_chat(model: str, system: str, user: str, timeout: int = 300, json_schema: Dict[str, Any] | None = None, debug: bool = False) -> str:
    url = "http://localhost:11434/api/chat"
    payload: Dict[str, Any] = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False
    }
    if json_schema:
        payload["format"] = {"type": "json_schema", "json_schema": {"name": "issuer_instance", "schema": json_schema}}
    else:
        payload["format"] = "json"
    if debug:
        print("[DEBUG] calling Ollama /api/chat", file=sys.stderr)
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return (data.get("message", {}) or {}).get("content", "")
    except requests.HTTPError as http_err:
        if debug:
            print(f"[DEBUG] chat error: {http_err}", file=sys.stderr)
        code = http_err.response.status_code if http_err.response is not None else None
        # Relax format on 4xx/5xx before switching endpoint
        if code in (400, 415, 500, 502, 503, 504):
            try:
                payload["format"] = "json"
                r2 = requests.post(url, json=payload, timeout=timeout)
                r2.raise_for_status()
                data2 = r2.json()
                return (data2.get("message", {}) or {}).get("content", "")
            except Exception:
                try:
                    payload.pop("format", None)
                    r3 = requests.post(url, json=payload, timeout=timeout)
                    r3.raise_for_status()
                    data3 = r3.json()
                    return (data3.get("message", {}) or {}).get("content", "")
                except Exception:
                    pass
        # fallback to generate endpoint
        return ollama_generate(model, f"System:\n{system}\n\nUser:\n{user}", timeout=timeout, json_schema=json_schema, debug=debug)


def ollama_generate(model: str, prompt: str, timeout: int = 300, json_schema: Dict[str, Any] | None = None, debug: bool = False) -> str:
    url = "http://localhost:11434/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "prompt": prompt,
        "stream": False
    }
    if json_schema:
        payload["format"] = {"type": "json_schema", "json_schema": {"name": "issuer_instance", "schema": json_schema}}
    else:
        payload["format"] = "json"
    if debug:
        print("[DEBUG] calling Ollama /api/generate", file=sys.stderr)
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return (r.json().get("response") or "").strip()
    except requests.HTTPError as http_err:
        if debug:
            print(f"[DEBUG] generate error: {http_err}", file=sys.stderr)
        code = http_err.response.status_code if http_err.response is not None else None
        if code in (400, 415, 500, 502, 503, 504):
            try:
                payload["format"] = "json"
                r2 = requests.post(url, json=payload, timeout=timeout)
                r2.raise_for_status()
                return (r2.json().get("response") or "").strip()
            except Exception:
                try:
                    payload.pop("format", None)
                    r3 = requests.post(url, json=payload, timeout=timeout)
                    r3.raise_for_status()
                    return (r3.json().get("response") or "").strip()
                except Exception:
                    raise
        raise
    except requests.RequestException as req_err:
        if debug:
            print(f"[DEBUG] generate request error: {req_err}", file=sys.stderr)
        try:
            payload.pop("format", None)
            r3 = requests.post(url, json=payload, timeout=timeout)
            r3.raise_for_status()
            return (r3.json().get("response") or "").strip()
        except Exception:
            raise

def build_issuer_system_prompt(units: str = "paise", use_cot: bool = False) -> str:
    """
    Build a robust, table-aware extraction prompt for issuer fields.
    """
    cot_line = (
        "Think step-by-step to locate evidence and compute values, but DO NOT reveal your reasoning; output JSON only.\n"
        if use_cot else
        "Do not explain your reasoning; output JSON only.\n"
    )
    return (
        "You are an expert financial data extractor for Indian IPO documents (Draft Red Herring Prospectus / Red Herring Prospectus).\n"
        + cot_line +
        "Extraction policy:\n"
        "- Read the provided TEXT and answer the questions exactly; if not found and explicitly required by regulation, select the best-supported value from the most recent section, else return null.\n"
        "- Prefer values from summary tables and financial statements; if multiple occurrences, take the latest period that matches the question.\n"
        "- Tables in plain text may appear as columns separated by spaces; reconstruct headers by proximity and indentation.\n"
        "- Normalize numbers:\n"
        "  * Remove commas and symbols. Parse percentages as integers without the '%'.\n"
        "  * Detect table/unit scale annotations like: '₹ in million', 'Amounts in ₹ million', '₹ in crores', '₹ in lakhs', '₹ thousand'.\n"
        "    - If a scale note applies to the table/section, convert each numeric value to ABSOLUTE RUPEES (integer):\n"
        "      • million → × 1,000,000\n"
        "      • crore   → × 10,000,000\n"
        "      • lakh    → × 100,000\n"
        "      • thousand→ × 1,000\n"
        "    - Do not double-scale: if the cell already includes a full rupee amount (e.g., '₹ 12,345,678'), keep as is.\n"
        "    - If both a global legend and a per-column unit appear, the per-column unit takes precedence.\n"
        "- For Bool questions, return true/false using explicit language in TEXT; if ambiguous, return null.\n"
        "- For List Nat questions (e.g., last 3 years), return a list of integers in chronological order if possible; otherwise the best 3 consecutive periods you can find.\n"
        "- Dates: if needed, use YYYY-MM-DD; otherwise leave null.\n"
        "- Return STRICT JSON, no comments or prose.\n"
        "Output format:\n"
        "{ \"fields\": { \"<field>\": <value>, ... } }\n"
    )


def build_schema_for_fields(fields: List[Tuple[str, str]]) -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    for fname, ftype in fields:
        if ftype == "Bool":
            props[fname] = {"type": "boolean"}
        elif ftype == "Nat":
            props[fname] = {"type": "integer"}
        elif ftype == "List Nat":
            props[fname] = {"type": "array", "items": {"type": "integer"}}
        else:
            props[fname] = {"type": "string"}
    return {
        "type": "object",
        "properties": {k: v for k, v in props.items()},
        "additionalProperties": True
    }

def simple_keyword_score(text: str, keywords: List[str]) -> int:
    txt = text.lower()
    score = 0
    for kw in keywords:
        k = kw.strip().lower()
        if not k:
            continue
        score += txt.count(k)
    return score

def select_evidence_pages(pages: List[str], question: str, field: str, topk: int, required_by: List[str] | None, rules_idx: Dict[str, Dict[str, str]]) -> List[Tuple[int, str]]:
    """
    Return list of (1-based page_index, page_text) for top-k pages by naive keyword score.
    """
    # build keyword list from question, field name, and rule titles/ids
    tokens = re.findall(r"[A-Za-z]+", question) + re.findall(r"[A-Za-z]+", field.replace("_", " "))
    if required_by:
        for rid in required_by:
            tokens += re.findall(r"[A-Za-z]+", rid)
            meta = rules_idx.get(rid) or {}
            tokens += re.findall(r"[A-Za-z]+", (meta.get("title") or ""))
            tokens += re.findall(r"[A-Za-z]+", (meta.get("reference") or ""))
    # de-dup and filter short tokens
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
    if not sel:
        # fallback: first page
        sel = [(1, pages[0])] if pages else []
    return sel

def fallback_assert_booleans(full_text: str, casted: Dict[str, Any]) -> None:
    """
    If some booleans are None/False but the document asserts compliance generically, flip to True.
    This is heuristic; tuned for common assertions around 7(1) and 7(2).
    """
    txt = full_text.lower()
    def contains_any(*phrases: str) -> bool:
        return any(p.lower() in txt for p in phrases)
    # Regulation 7(1)(a): application to stock exchange (in-principle)
    if casted.get("applied_to_stock_exchange") in (None, False):
        if contains_any("regulation 7(1)", "regulation 7 (1)", "in-principle approval", "in principle approval", "applied to stock exchange"):
            casted["applied_to_stock_exchange"] = True
    # 7(1)(b): depository agreement
    if casted.get("has_demat_agreement") in (None, False):
        if contains_any("regulation 7(1)(b)", "depository agreement", "dematerialisation of specified securities"):
            casted["has_demat_agreement"] = True
    # 7(1)(c): promoter demat
    if casted.get("promoter_securities_demat") in (None, False):
        if contains_any("regulation 7(1)(c)", "promoters", "dematerialis"):
            casted["promoter_securities_demat"] = True
    # 7(2): general corporate purposes cap
    if casted.get("general_corp_purpose_ratio") in (None, 0):
        if contains_any("regulation 7(2)", "general corporate purposes", "not exceed twenty five"):
            # leave ratio if unknown; don't set arbitrary number
            pass

# -------------------- Deterministic numeric scaling (absolute rupees) --------------------
_SCALE_PATTERNS = [
    (re.compile(r"\b(in|amounts\s+in)\s+(₹|rs\.?|rupees)?\s*millions?\b", re.I), 1_000_000),
    (re.compile(r"\b(in|amounts\s+in)\s+(₹|rs\.?|rupees)?\s*mn\b", re.I), 1_000_000),
    (re.compile(r"\b(in|amounts\s+in)\s+(₹|rs\.?|rupees)?\s*crores?\b", re.I), 10_000_000),
    (re.compile(r"\b(in|amounts\s+in)\s+(₹|rs\.?|rupees)?\s*cr\b", re.I), 10_000_000),
    (re.compile(r"\b(in|amounts\s+in)\s+(₹|rs\.?|rupees)?\s*l(ak|ac)hs?\b", re.I), 100_000),
    (re.compile(r"\b(in|amounts\s+in)\s+(₹|rs\.?|rupees)?\s*thousands?\b", re.I), 1_000),
]

def detect_scale_multiplier(text: str) -> int:
    t = (text or "").lower()
    for rx, mul in _SCALE_PATTERNS:
        if rx.search(t):
            return mul
    return 1

def is_percent_question(question: str) -> bool:
    q = (question or "").lower()
    return ("%" in q) or ("percent" in q) or ("percentage" in q) or ("ratio" in q)

def is_currency_context(question: str, evidence_text: str) -> bool:
    def has_curr(s: str) -> bool:
        t = (s or "").lower()
        return ("₹" in t) or ("rs" in t) or ("rupee" in t) or ("rupees" in t) or ("inr" in t)
    return has_curr(question) or has_curr(evidence_text)

def apply_scale(value: Any, ftype: str, factor: int, question: str, evidence_text: str) -> Any:
    # General heuristics: don't scale percentage/ratio questions
    if is_percent_question(question):
        return value
    # Only attempt scaling for numeric types when currency is implied by context
    if not is_currency_context(question, evidence_text):
        return value
    if factor <= 1:
        return value
    try:
        if ftype == "Nat" and isinstance(value, int):
            # avoid double scaling if already very large relative to factor
            if value >= factor * 1000:
                return value
            return value * factor
        if ftype == "List Nat" and isinstance(value, list) and all(isinstance(v, int) for v in value):
            if not value:
                return value
            # if median already above threshold, skip scaling
            vs = sorted(value)
            med = vs[len(vs)//2]
            if med >= factor * 1000:
                return value
            return [v * factor for v in value]
    except Exception:
        return value
    return value


def cast_value(v: Any, typ: str) -> Any:
    if v is None:
        return None
    if typ == "Bool":
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("true", "yes", "y", "1"):
            return True
        if s in ("false", "no", "n", "0"):
            return False
        return None
    if typ == "Nat":
        try:
            # extract digits (handle formats like "15 crore" -> 15, but prefer raw int if provided)
            if isinstance(v, (int, float)):
                return int(v)
            digits = re.findall(r"-?\d+", str(v))
            return int(digits[0]) if digits else None
        except Exception:
            return None
    if typ == "List Nat":
        if isinstance(v, list):
            return [cast_value(x, "Nat") for x in v if cast_value(x, "Nat") is not None]
        # try to split on commas or spaces
        parts = re.split(r"[,\s]+", str(v))
        vals: List[int] = []
        for p in parts:
            try:
                if p.strip():
                    vals.append(int(p))
            except Exception:
                continue
        return vals
    # default string
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=str, default="", help="Path to RHP PDF")
    ap.add_argument("--text", type=str, default="", help="Path to text file if not using PDF")
    ap.add_argument("--out", type=str, required=True, help="Output issuer instance JSON")
    ap.add_argument("--questions-json", type=str, required=True, help="Path to rules_and_fields*.json")
    ap.add_argument("--schema", type=str, default="", help="Optional issuer_schema.json")
    ap.add_argument("--issuer-id", type=str, default="", help="Issuer identifier to store in output")
    ap.add_argument("--model", type=str, default="llama3:8b")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--retrieval", choices=["none","page","keyword"], default="keyword",
                    help="Context selection: none=full text; page=per-page for each field; keyword=select top-k pages by naive keyword match")
    ap.add_argument("--layout", choices=["plain","blocks"], default="blocks",
                    help="PDF page text extraction layout (blocks preserves grouping and often tables)")
    ap.add_argument("--tables", action="store_true", help="Try to append table text extracted via pdfplumber (if installed)")
    ap.add_argument("--topk", type=int, default=3, help="Top-k pages to include as evidence when retrieval!=none")
    ap.add_argument("--chunk-words", type=int, default=800, help="Words per pseudo-page when using --text (no explicit page breaks)")
    ap.add_argument("--per-field", action="store_true", help="Ask LLM per field (more calls; better locality)")
    ap.add_argument("--provenance", action="store_true", help="Record evidence pages per field")
    ap.add_argument("--no-format", action="store_true", help="Disable json_schema enforcement (plain json)")
    ap.add_argument("--cot", action="store_true", help="Enable hidden step-by-step reasoning (do not include rationale in output)")
    ap.add_argument("--units", type=str, default="paise", help="Target integer unit for currency normalization (default: paise)")
    ap.add_argument("--max-evidence-chars", type=int, default=20000, help="Truncate evidence text per call to this many characters")
    ap.add_argument("--scale-auto", action="store_true", help="Auto-scale Nat/List Nat fields to absolute rupees based on detected table/unit legends")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    source_text = ""
    src_path = ""
    if args.pdf:
        src_path = args.pdf
        # Build pages with better layout and optional tables
        pdf_pages = read_pdf_pages(Path(args.pdf), layout=args.layout, include_tables=args.tables)
        source_text = "\n\n--- PAGE BREAK ---\n\n".join(pdf_pages)
    elif args.text:
        src_path = args.text
        source_text = read_text_file(Path(args.text))
    else:
        print("Provide --pdf or --text", file=sys.stderr)
        sys.exit(1)

    questions = load_questions(Path(args.questions_json))
    if not questions:
        print("No issuer questions found.", file=sys.stderr)
        sys.exit(2)

    # Prefer schema from the rules_and_fields JSON; optionally overlay with --schema file if provided
    schema_types = load_schema_from_questions(Path(args.questions_json))
    if args.schema:
        schema_types.update(load_schema(Path(args.schema)))
    rules_index = load_rules_index(Path(args.questions_json))
    fields_for_schema: List[Tuple[str, str]] = []
    for q in questions:
        f = q["field"]
        t = q["type"] or schema_types.get(f) or "String"
        fields_for_schema.append((f, t))

    json_schema = None if args.no_format else {
        "type": "object",
        "properties": { "fields": build_schema_for_fields(fields_for_schema) },
        "required": ["fields"]
    }

    system = build_issuer_system_prompt(units=args.units, use_cot=args.cot)
    pages = split_pages_from_text(source_text, chunk_words=args.chunk_words)

    casted: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}

    if args.per_field or args.retrieval != "none":
        # Per-field extraction with optional retrieval
        for q in questions:
            field = q["field"]
            ftype = (q["type"] or schema_types.get(field) or "String")
            evidence = ""
            used_pages: List[int] = []
            if args.retrieval == "none":
                evidence = source_text
            elif args.retrieval in ("page", "keyword"):
                sel = select_evidence_pages(pages, q["question"], field, args.topk, (q.get("required_by") or []), rules_index) if args.retrieval == "keyword" else [(i+1, p) for i, p in enumerate(pages)]
                if args.retrieval == "page":
                    # one-shot: ask per page and merge first confident answer; for simplicity, include first page
                    sel = sel[:args.topk]
                used_pages = [idx for (idx, _) in sel]
                parts = []
                for (idx, txt) in sel:
                    parts.append(f"[PAGE {idx}]\n{txt}")
                evidence = "\n\n".join(parts)
            # Truncate evidence if too large
            if len(evidence) > args.max_evidence_chars:
                evidence = evidence[:args.max_evidence_chars]
            user = (
                "TEXT (evidence pages):\n"
                f"{evidence}\n\n"
                "TASK:\n"
                f"- Field: {field}\n"
                f"- Expected type: {ftype}\n"
                f"- Question: {q['question']}\n\n"
                "Return JSON with only this field under 'fields'. Example:\n"
                f"{{\"fields\": {{\"{field}\": <value>}}}}\n"
            )
            raw = ollama_chat(args.model, system, user, timeout=args.timeout, json_schema={
                "type": "object",
                "properties": { "fields": build_schema_for_fields([(field, ftype)]) },
                "required": ["fields"]
            } if not args.no_format else None, debug=args.debug)
            raw = raw.strip()
            try:
                data = json.loads(raw)
            except Exception:
                m = re.search(r"\{[\s\S]*\}", raw)
                data = json.loads(m.group(0)) if m else {"fields": {}}
            val = data.get("fields", {}).get(field)
            cast_val = cast_value(val, ftype)
            if args.scale_auto:
                factor = detect_scale_multiplier(evidence)
                cast_val = apply_scale(cast_val, ftype, factor, q["question"], evidence)
            casted[field] = cast_val
            if args.provenance:
                provenance[field] = {"pages": used_pages}
    else:
        # Batch mode (full text)
        qlines = []
        for q in questions:
            qlines.append(f"- {q['field']} ({q['type']}): {q['question']}")
        user = (
            "TEXT:\n"
            f"{source_text}\n\n"
            "QUESTIONS (with expected types):\n" + "\n".join(qlines) + "\n\n"
            "Return JSON object with key 'fields' only. Example: {\"fields\": {\"is_debarred\": false, ...}}\n"
        )
        raw = ollama_chat(args.model, system, user, timeout=args.timeout, json_schema=json_schema, debug=args.debug)
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except Exception:
            # try to extract first JSON object
            m = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(m.group(0)) if m else {"fields": {}}
        fields = data.get("fields") or {}
        for fname, ftype in fields_for_schema:
            val = fields.get(fname)
            cast_val = cast_value(val, ftype)
            if args.scale_auto:
                factor = detect_scale_multiplier(source_text)
                # In batch mode, we only have the full text; pass an empty question to rely on currency context in text.
                cast_val = apply_scale(cast_val, ftype, factor, "", source_text)
            casted[fname] = cast_val

    # Heuristic fallback: assert some booleans if explicit compliance statements are present
    fallback_assert_booleans(source_text, casted)

    # Optional scaling step (deterministic currency normalization)
    # Parse optional env or arguments in future; here we keep numbers as-is.

    out_obj = {
        "issuer_id": args.issuer_id or Path(src_path).stem,
        "source": src_path,
        "fields": casted
    }
    if args.provenance:
        out_obj["provenance"] = provenance
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote issuer instance → {args.out}")


if __name__ == "__main__":
    main()



#!/usr/bin/env python3
# scripts/extract_lean_to_json.py
"""
Extract ruleset and issuer fields from a generated Lean file into JSON.

Outputs a JSON object:
{
  "rules": [
    {
      "id": str,
      "title": str,
      "reference": str,
      "remedy": str | null,
      "check_code": str,
      "failReason_code": str
    }, ...
  ],
  "issuer_questions": [ { "field": str, "question": str, "type": str }, ... ],
  "issuer_schema": [ { "field": str, "type": str }, ... ]
}

Usage:
  # Recommended (schema derived from issuerQuestions; no Main.lean dependency):
  python scripts/extract_lean_to_json.py --lean GeneratedRules_v2.lean --out data/processed/rules_and_fields.json

  # Optional (also extract issuer_schema_from_main for drift checks):
  python scripts/extract_lean_to_json.py --lean GeneratedRules_v2.lean --main Main.lean --out data/processed/rules_and_fields.json
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_between_brackets_list(content: str) -> str:
    """
    Given a def ... := [ ... ] block, return the inner content between the outermost [ ... ].
    Assumes the caller has already matched at '... := ['.
    """
    # Find the first '[' from the match start
    start = content.find("[")
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(content)):
        ch = content[i]
        if ch == "[":
            depth += 1
            if depth == 1:
                begin = i + 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                return content[begin:end].strip()
    return ""


def split_top_level_braced_items(list_inner: str) -> List[str]:
    """
    Split a Lean list of records into individual '{ ... }' blocks at top level.
    """
    items: List[str] = []
    depth = 0
    cur_start = None
    i = 0
    while i < len(list_inner):
        ch = list_inner[i]
        if ch == "{":
            if depth == 0:
                cur_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and cur_start is not None:
                block = list_inner[cur_start:i+1]
                items.append(block.strip())
                cur_start = None
        i += 1
    return items


def extract_string_field(block: str, name: str) -> str:
    # Matches: name := "value"
    m = re.search(rf'\b{name}\s*:=\s*"([^"]*)"', block)
    return m.group(1) if m else ""


def extract_optional_string_field(block: str, name: str) -> str | None:
    # Matches: name := some "value"
    m = re.search(rf'\b{name}\s*:=\s*some\s*"([^"]*)"', block)
    if m:
        return m.group(1)
    # None case
    m2 = re.search(rf'\b{name}\s*:=\s*none\b', block)
    if m2:
        return None
    return None


def extract_code_between(block: str, start_key: str, end_key: str) -> str:
    """
    Extract the Lean code between 'start_key :=' and ', <end_key>'.
    Returns trimmed code; if not found, returns "".
    """
    # Find start
    m_start = re.search(rf'\b{re.escape(start_key)}\s*:=', block)
    if not m_start:
        return ""
    start_idx = m_start.end()
    # Find end key occurrence after start
    m_end = re.search(rf',\s*\b{re.escape(end_key)}\b', block[start_idx:], flags=re.S)
    if not m_end:
        # Try until closing brace as fallback
        code = block[start_idx:].strip()
        # strip trailing '}' if present
        return code.rstrip().rstrip("}").strip()
    end_idx = start_idx + m_end.start()
    return block[start_idx:end_idx].strip()


def parse_generated_ruleset(lean_src: str) -> List[Dict[str, Any]]:
    # Find def generatedRuleset ... := [ ... ]
    m = re.search(r'def\s+generatedRuleset\s*:\s*List\s+ComplianceRule\s*:=\s*\[', lean_src)
    if not m:
        return []
    inner = extract_between_brackets_list(lean_src[m.start():])
    blocks = split_top_level_braced_items(inner)
    out: List[Dict[str, Any]] = []
    for b in blocks:
        rule = {
            "id": extract_string_field(b, "id"),
            "title": extract_string_field(b, "title"),
            "reference": extract_string_field(b, "reference"),
            "remedy": extract_optional_string_field(b, "remedy?"),
            "check": extract_code_between(b, "check", "failReason"),
            "failReason": extract_code_between(b, "failReason", "remedy?")
        }
        out.append(rule)
    return out


def parse_issuer_questions(lean_src: str) -> List[Dict[str, str]]:
    # Prefer final 'def issuerQuestions : List (String × String × String) := [ ... ]'
    mq = re.search(r'def\s+issuerQuestions\s*:\s*List\s*\(\s*String\s*×\s*String\s*×\s*String\s*\)\s*:=\s*\[', lean_src)
    content = ""
    if mq:
        content = extract_between_brackets_list(lean_src[mq.start():])
    else:
        # Fallback to collect all issuerQuestionsChunk
        chunks = re.finditer(r'def\s+issuerQuestionsChunk\s*:\s*List\s*\(\s*String\s*×\s*String\s*×\s*String\s*\)\s*:=\s*\[', lean_src)
        parts: List[str] = []
        for mm in chunks:
            inner = extract_between_brackets_list(lean_src[mm.start():])
            if inner:
                parts.append(inner)
        content = (",\n".join(parts)).strip()
    if not content:
        return []
    # Parse tuples ("field","question","type")
    tuples = re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', content)
    return [{"field": f, "question": q, "type": t} for (f, q, t) in tuples]


def parse_issuer_schema(main_src: str) -> List[Dict[str, str]]:
    # Extract structure Issuer where block
    m = re.search(r'^\s*structure\s+Issuer\s+where\s*$', main_src, flags=re.M)
    if not m:
        return []
    start = m.end()
    # Read until 'deriving' or next structure
    tail = main_src[start:]
    stop = re.search(r'^\s*deriving\b|^\s*structure\b', tail, flags=re.M)
    block = tail[:stop.start()] if stop else tail
    fields: List[Dict[str, str]] = []
    for line in block.splitlines():
        mm = re.match(r"^\s{2}([A-Za-z0-9_']+)\s*:\s*(.+?)\s*$", line)
        if mm:
            fields.append({"field": mm.group(1), "type": mm.group(2)})
    return fields


def normalize_question_type(raw: str) -> str:
    """
    Normalize common type strings seen in issuerQuestions into Lean-like strings.
    This function is intentionally small and deterministic.
    """
    t = (raw or "").strip()
    if not t:
        return "String"
    t = re.sub(r"\s+", " ", t)
    mapping = {
        "OptionBool": "Option Bool",
        "OptionNat": "Option Nat",
        "OptionString": "Option String",
        "OptionListNat": "Option (List Nat)",
        "ListNat": "List Nat",
    }
    return mapping.get(t, t)


def base_type_from_question_type(norm: str) -> str:
    """
    Convert a question type into a base field type suitable for issuer_schema.
    Examples:
      Option Bool -> Bool
      Option (List Nat) -> List Nat
    """
    t = (norm or "").strip()
    if t.startswith("Option "):
        inner = t[len("Option ") :].strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1].strip()
        return inner
    return t


def build_issuer_schema_from_questions(issuer_questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Deterministically build a canonical issuer_schema [{field,type}] from issuer_questions.
    Deduplicates by field and prefers stable base types (Bool, Nat, List Nat, String, List String).
    """
    # Dedup questions by field
    by_field: Dict[str, Dict[str, str]] = {}
    for q in issuer_questions:
        field = (q.get("field") or "").strip()
        if not field:
            continue
        qtext = (q.get("question") or "").strip()
        raw_type = q.get("type") or "String"
        norm_type = normalize_question_type(raw_type)
        base_type = base_type_from_question_type(norm_type)
        cur = by_field.get(field)
        if cur is None:
            by_field[field] = {"field": field, "question": qtext, "type": base_type, "type_raw": raw_type, "type_norm": norm_type}
        else:
            # Keep the more informative question (longer non-empty)
            if qtext and (len(qtext) > len(cur.get("question", ""))):
                cur["question"] = qtext
            # Prefer the most specific base type by a fixed precedence
            precedence = ["List Nat", "List String", "String", "Nat", "Bool"]
            cur_type = cur.get("type") or "String"
            if base_type in precedence and cur_type in precedence:
                if precedence.index(base_type) < precedence.index(cur_type):
                    cur["type"] = base_type
            elif base_type and cur_type != base_type:
                # If conflicting and unknown, fall back to String
                cur["type"] = "String"
            cur["type_raw"] = cur.get("type_raw", raw_type)
            cur["type_norm"] = cur.get("type_norm", norm_type)

    schema = [{"field": v["field"], "type": v["type"]} for v in by_field.values()]
    schema.sort(key=lambda x: x["field"])
    return schema


def extract_to_json(lean_path: str, main_path: str | None = None) -> Dict[str, Any]:
    lean_src = read_text(Path(lean_path))
    rules = parse_generated_ruleset(lean_src)
    issuer_questions = parse_issuer_questions(lean_src)
    issuer_schema = build_issuer_schema_from_questions(issuer_questions)
    issuer_schema_from_main: List[Dict[str, str]] = []
    if main_path:
        try:
            main_src = read_text(Path(main_path))
            issuer_schema_from_main = parse_issuer_schema(main_src)
        except Exception:
            issuer_schema_from_main = []
    return {
        "rules": rules,
        "issuer_questions": issuer_questions,
        "issuer_schema": issuer_schema,
        "issuer_schema_from_main": issuer_schema_from_main,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lean", required=True, help="Path to GeneratedRules*.lean")
    ap.add_argument("--main", default="", help="Optional path to Main.lean (only needed to extract issuer_schema_from_main)")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()
    data = extract_to_json(args.lean, args.main or None)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote JSON → {args.out}")


if __name__ == "__main__":
    main()



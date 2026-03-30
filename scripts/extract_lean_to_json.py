#!/usr/bin/env python3
# scripts/extract_lean_to_json.py
"""
[LIBRARY MODULE — Phase 3 consolidation]

This script is consumed as a library by llm_generate_lean.py (via --json-out).
Running it as a standalone pipeline step is no longer required; always pass
--json-out to llm_generate_lean.py instead.

The extract_to_json() function remains importable for backwards compatibility.

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

try:
    from scripts.utils import (  # type: ignore[import-not-found]
        normalize_question_type,
        base_type_from_question_type,
        build_issuer_schema_from_questions,
    )
except ImportError:
    from utils import (  # type: ignore
        normalize_question_type,
        base_type_from_question_type,
        build_issuer_schema_from_questions,
    )


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


def extract_issuer_schema_from_json(json_path: str, out_path: str) -> Dict[str, Any]:
    """
    Read a pre-processed rules_and_fields*.json and extract/rebuild the issuer_schema.
    This is the --rules-and-fields path: the JSON already has issuer_questions/issuer_schema
    embedded; we re-derive a canonical issuer_schema from the questions and write to --out.
    """
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    issuer_questions: List[Dict[str, str]] = raw.get("issuer_questions") or []
    issuer_schema: List[Dict[str, str]] = build_issuer_schema_from_questions(issuer_questions)
    # If the file already has a curated issuer_schema, merge it (questions-derived takes precedence
    # for deduplication, but we keep any extra fields from the embedded schema)
    embedded = raw.get("issuer_schema") or []
    embedded_map = {e["field"]: e["type"] for e in embedded if isinstance(e, dict) and e.get("field")}
    schema_map = {s["field"]: s["type"] for s in issuer_schema}
    for f, t in embedded_map.items():
        if f not in schema_map:
            schema_map[f] = t
    issuer_schema = sorted([{"field": f, "type": t} for f, t in schema_map.items()], key=lambda x: x["field"])
    data = {
        "rules": raw.get("rules") or [],
        "issuer_questions": issuer_questions,
        "issuer_schema": issuer_schema,
        "issuer_schema_from_main": raw.get("issuer_schema_from_main") or [],
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote issuer_schema ({len(issuer_schema)} fields) → {out_path}")
    return data


def main():
    ap = argparse.ArgumentParser(
        description="Extract ruleset and issuer schema from a generated Lean file or a pre-processed JSON."
    )
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--lean", default="", help="Path to GeneratedRules*.lean")
    source.add_argument(
        "--rules-and-fields",
        default="",
        metavar="JSON",
        help="Path to a pre-processed rules_and_fields*.json (from postprocess step); "
             "extracts issuer_schema directly without re-parsing a Lean file.",
    )
    ap.add_argument("--main", default="", help="Optional path to Main.lean (only for drift checks; requires --lean)")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()

    if args.rules_and_fields:
        extract_issuer_schema_from_json(args.rules_and_fields, args.out)
    else:
        data = extract_to_json(args.lean, args.main or None)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Wrote JSON → {args.out}")


if __name__ == "__main__":
    main()



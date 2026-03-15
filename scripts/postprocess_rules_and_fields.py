#!/usr/bin/env python3
"""
postprocess_rules_and_fields.py

Sanity-fix a rules_and_fields*.json produced by:
  - scripts/llm_generate_lean.py --json-out ...
  - scripts/extract_lean_to_json.py

This is a deterministic postprocess step to prevent downstream pain:
  - normalize rule ids (prefer ICDR_*)
  - normalize issuer question types (OptionBool -> Option Bool, etc.)
  - deduplicate issuer questions by field
  - generate canonical issuer_schema derived from issuer_questions
  - stub/repair unsafe check expressions when they reference unknown fields

Usage:
  python scripts/postprocess_rules_and_fields.py \
    --in data/processed/rules_and_fields_debug_v6.json \
    --out data/processed/rules_and_fields_debug_v6_post.json \
    --report data/processed/rules_and_fields_debug_v6_post_report.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


def normalize_rule_id(rule_id: str) -> str:
    s = (rule_id or "").strip()
    if not s:
        return s
    if s.startswith("ICDR_"):
        return s
    if s.startswith("rule_"):
        return "ICDR_" + s[len("rule_") :]
    return s


def normalize_question_type(raw: str) -> str:
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
    t = (norm or "").strip()
    if t.startswith("Option "):
        inner = t[len("Option ") :].strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1].strip()
        return inner
    return t


def build_issuer_schema_from_questions(issuer_questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_field: Dict[str, Dict[str, str]] = {}
    for q in issuer_questions:
        field = (q.get("field") or "").strip()
        if not field:
            continue
        question = (q.get("question") or "").strip()
        t_raw = q.get("type") or "String"
        t_norm = normalize_question_type(t_raw)
        base = base_type_from_question_type(t_norm)
        cur = by_field.get(field)
        if cur is None:
            by_field[field] = {"field": field, "question": question, "type": base}
        else:
            if question and len(question) > len(cur.get("question", "")):
                cur["question"] = question
            # Deterministic precedence
            precedence = ["List Nat", "List String", "String", "Nat", "Bool"]
            cur_type = cur.get("type") or "String"
            if base in precedence and cur_type in precedence:
                if precedence.index(base) < precedence.index(cur_type):
                    cur["type"] = base
            elif base and cur_type != base:
                cur["type"] = "String"
    schema = [{"field": v["field"], "type": v["type"]} for v in by_field.values()]
    schema.sort(key=lambda x: x["field"])
    return schema


def extract_issuer_field_refs(check_expr: str) -> List[str]:
    # naive: i.<field>
    return sorted(set(re.findall(r"\bi\.([A-Za-z_][A-Za-z0-9_]*)\b", check_expr or "")))


def check_looks_like_lean_lambda(s: str) -> bool:
    return isinstance(s, str) and s.strip().startswith("fun ")


def escape_lean_string(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--report", dest="reportp", default="")
    args = ap.parse_args()

    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    rules = data.get("rules") if isinstance(data, dict) else []
    issuer_questions = data.get("issuer_questions") if isinstance(data, dict) else []

    out_rules: List[Dict[str, Any]] = []
    rule_fixes: List[Dict[str, Any]] = []

    # Normalize/dedupe issuer questions first
    normalized_questions: List[Dict[str, str]] = []
    seen_q: Dict[str, Dict[str, str]] = {}
    for q in issuer_questions if isinstance(issuer_questions, list) else []:
        if not isinstance(q, dict):
            continue
        field = str(q.get("field") or "").strip()
        question = str(q.get("question") or "").strip()
        t_norm = normalize_question_type(str(q.get("type") or "String"))
        if not field:
            continue
        prev = seen_q.get(field)
        if prev is None or (question and len(question) > len(prev.get("question", ""))):
            seen_q[field] = {"field": field, "question": question, "type": t_norm}
    normalized_questions = [seen_q[k] for k in sorted(seen_q.keys())]

    issuer_schema = build_issuer_schema_from_questions(normalized_questions)
    schema_fields = {x["field"] for x in issuer_schema}

    for r in rules if isinstance(rules, list) else []:
        if not isinstance(r, dict):
            continue
        rid = normalize_rule_id(str(r.get("id") or r.get("rule_id") or ""))
        title = str(r.get("title") or "")
        reference = str(r.get("reference") or rid)
        check = str(r.get("check") or r.get("check_code") or "fun _ => True")
        fail = str(r.get("failReason") or r.get("failReason_code") or 'fun _ => "(no detail)"')
        remedy = r.get("remedy")

        fix_notes: List[str] = []
        if rid != str(r.get("id") or r.get("rule_id") or ""):
            fix_notes.append("normalized_rule_id")

        # Repair check/failReason to safe stubs when obviously unsafe
        refs = extract_issuer_field_refs(check)
        missing = [f for f in refs if f not in schema_fields]
        unsafe_call = re.search(r"\bi\.[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\b", check) is not None

        if (not check_looks_like_lean_lambda(check)) or missing or unsafe_call:
            fix_notes.append("stubbed_check")
            if missing:
                fix_notes.append(f"missing_fields:{','.join(missing)}")
            if unsafe_call:
                fix_notes.append("suspected_function_field_usage")
            check = "fun _ => True"

        if not check_looks_like_lean_lambda(fail):
            # If it's a raw string, wrap it
            fix_notes.append("wrapped_failReason")
            fail = f'fun _ => "{escape_lean_string(fail.strip().strip("\""))}"'

        out_rules.append(
            {
                "id": rid,
                "title": title,
                "reference": reference,
                "remedy": remedy,
                "check": check,
                "failReason": fail,
            }
        )
        if fix_notes:
            rule_fixes.append({"id": rid, "fixes": fix_notes})

    out_rules.sort(key=lambda x: x.get("id", ""))

    out_data = {
        "rules": out_rules,
        "issuer_questions": normalized_questions,
        "issuer_schema": issuer_schema,
        "issuer_schema_source": "derived_from_issuer_questions",
    }

    Path(args.outp).parent.mkdir(parents=True, exist_ok=True)
    Path(args.outp).write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.reportp:
        report = {
            "input": args.inp,
            "output": args.outp,
            "rules_in": len(rules) if isinstance(rules, list) else 0,
            "rules_out": len(out_rules),
            "issuer_questions_in": len(issuer_questions) if isinstance(issuer_questions, list) else 0,
            "issuer_questions_out": len(normalized_questions),
            "fixes": rule_fixes,
        }
        Path(args.reportp).parent.mkdir(parents=True, exist_ok=True)
        Path(args.reportp).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Wrote postprocessed rules+fields → {args.outp}")
    if args.reportp:
        print(f"✅ Wrote postprocess report → {args.reportp}")


if __name__ == "__main__":
    main()


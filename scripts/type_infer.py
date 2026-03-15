#!/usr/bin/env python3
"""
type_infer.py

Deterministic type inference from evidence_store.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


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


BOOL_TOKENS = ("yes", "no", "true", "false", "complied", "not complied", "met", "not met")
LIST_TOKENS = ("preceding three years", "last three years", "fy", "fy20", "fy21", "fy22", "fy23")


def bool_indicator(raw: str, field: str) -> bool:
    s = (raw or "").lower()
    if any(t in s for t in BOOL_TOKENS):
        return True
    lname = field.lower()
    if lname.startswith(("has_", "is_", "no_", "uses_", "changed_")):
        return True
    return False


def list_indicator(raw: str, field: str) -> bool:
    s = (raw or "").lower()
    if any(t in s for t in LIST_TOKENS):
        return True
    # multiple numbers in one value
    nums = re.findall(r"\d+", s)
    if len(nums) >= 2:
        return True
    # plural field name
    if field.lower().endswith("s"):
        return True
    return False


def missing_indicator(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    return False


ALLOWED_TYPES = {
    "Bool",
    "Nat",
    "List Nat",
    "String",
    "Option Bool",
    "Option Nat",
    "Option (List Nat)",
    "Option String",
}


def choose_type(metrics: Dict[str, float], bool_strong: bool, list_strong: bool) -> str:
    if bool_strong and metrics.get("Bool_parse_rate", 0.0) >= 0.6:
        return "Bool"
    if list_strong and metrics.get("ListNat_parse_rate", 0.0) >= 0.6:
        return "List Nat"
    if metrics.get("Nat_parse_rate", 0.0) >= 0.6:
        return "Nat"
    if metrics.get("Bool_parse_rate", 0.0) >= 0.5:
        return "Bool"
    if metrics.get("ListNat_parse_rate", 0.0) >= 0.5:
        return "List Nat"
    if metrics.get("Nat_parse_rate", 0.0) >= 0.5:
        return "Nat"
    return "String"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    records = read_jsonl(Path(args.evidence))
    by_field: Dict[str, List[dict]] = {}
    for r in records:
        field = r.get("field")
        if not isinstance(field, str) or not field.strip():
            continue
        by_field.setdefault(field, []).append(r)

    report: List[Dict[str, Any]] = []
    schema: List[Dict[str, str]] = []

    for field, items in sorted(by_field.items()):
        total = len(items)
        if total == 0:
            continue
        bool_ok = 0
        nat_ok = 0
        list_ok = 0
        missing = 0
        bool_hint = False
        list_hint = False
        table_evidence_count = 0
        example_table_row = None
        examples: List[Dict[str, Any]] = []

        for r in items:
            cand = r.get("value_candidates") or {}
            vraw = r.get("value_raw") or ""
            ev = r.get("evidence") or {}
            source = str(ev.get("source") or "")
            if source.startswith("table:"):
                table_evidence_count += 1
                if example_table_row is None:
                    example_table_row = r.get("table_row")
            if missing_indicator(vraw):
                missing += 1
            if cand.get("Bool") is not None:
                bool_ok += 1
            if cand.get("Nat") is not None:
                nat_ok += 1
            if cand.get("List Nat"):
                list_ok += 1
            if bool_indicator(vraw, field):
                bool_hint = True
            if list_indicator(vraw, field):
                list_hint = True
            if len(examples) < 3:
                examples.append({
                    "value_raw": vraw,
                    "evidence": r.get("evidence"),
                })

        metrics = {
            "Bool_parse_rate": round(bool_ok / total, 3),
            "Nat_parse_rate": round(nat_ok / total, 3),
            "ListNat_parse_rate": round(list_ok / total, 3),
            "missing_rate": round(missing / total, 3),
        }

        base = choose_type(metrics, bool_hint, list_hint)
        if table_evidence_count > 0 and metrics.get("ListNat_parse_rate", 0.0) > 0.0:
            base = "List Nat"
        final = base
        inactive_field = False
        if metrics["missing_rate"] >= 1.0:
            final = "Option String"
            inactive_field = True
        elif metrics["missing_rate"] > 0.3:
            final = f"Option {base}"

        if final not in ALLOWED_TYPES:
            final = "Option String"

        schema.append({"field": field, "type": final})
        report.append({
            "field": field,
            "provisional_type": "Option Nat",
            "final_type": final,
            "metrics": metrics,
            "table_evidence_count": table_evidence_count,
            "example_table_row": example_table_row,
            "evidence_examples": examples,
            "reason": "bool_indicator" if base == "Bool" else "list_indicator" if base == "List Nat" else "parse_rate",
            "inactive_field": inactive_field,
        })

    out = {
        "issuer_schema": sorted(schema, key=lambda x: x["field"]),
        "type_reconcile_report": report,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote type inference report to {args.out}")


if __name__ == "__main__":
    main()

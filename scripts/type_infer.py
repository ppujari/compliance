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

try:
    from scripts.utils import read_jsonl  # type: ignore[import-not-found]
except ImportError:
    from utils import read_jsonl  # type: ignore


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


_FINANCIAL_SERIES_SUFFIXES = (
    "_years", "_profits", "_assets", "_worths", "_values", "_figures",
    "_revenues", "_losses", "_incomes", "_networths",
)
_MULTI_PERIOD_KEYWORDS = ("preceding three years", "last three years", "three full years", "3 years")


def list_indicator(raw: str, field: str) -> bool:
    s = (raw or "").lower()
    if any(t in s for t in LIST_TOKENS):
        return True
    # multiple numbers in one value
    nums = re.findall(r"\d+", s)
    if len(nums) >= 2:
        return True
    # only treat plural suffix as list signal if the field ends with a known financial series suffix
    lname = field.lower()
    if any(lname.endswith(sfx) for sfx in _FINANCIAL_SERIES_SUFFIXES):
        return True
    if any(kw in s for kw in _MULTI_PERIOD_KEYWORDS):
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


def _process_evidence(
    records: List[dict],
    provisional_map: Dict[str, str] | None = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """Core logic: group evidence by field and infer types. Returns (schema, report)."""
    by_field: Dict[str, List[dict]] = {}
    for r in records:
        field = r.get("field")
        if not isinstance(field, str) or not field.strip():
            continue
        by_field.setdefault(field, []).append(r)

    report: List[Dict[str, Any]] = []
    schema: List[Dict[str, str]] = []
    pmap = provisional_map or {}

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

        # Actual provisional type from schema, not a hardcoded value
        prov_type = pmap.get(field, "Option String")

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
            "provisional_type": prov_type,
            "final_type": final,
            "metrics": metrics,
            "table_evidence_count": table_evidence_count,
            "example_table_row": example_table_row,
            "evidence_examples": examples,
            "reason": "bool_indicator" if base == "Bool" else "list_indicator" if base == "List Nat" else "parse_rate",
            "inactive_field": inactive_field,
        })

    return sorted(schema, key=lambda x: x["field"]), report


def run_type_infer(
    evidence_path: Path,
    out_path: Path,
    provisional_map: Dict[str, str] | None = None,
) -> None:
    """Direct callable (no argv needed), used by schema_reconcile.py."""
    records = read_jsonl(evidence_path)
    schema, report = _process_evidence(records, provisional_map)
    out = {"issuer_schema": schema, "type_reconcile_report": report}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote type inference report to {out_path}")


# Canonical short alias expected by Phase 1 spec.
run = run_type_infer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provisional-schema", default="", help="Optional provisional_schema.json (array of {field,type})")
    args = ap.parse_args()

    provisional_map: Dict[str, str] = {}
    if args.provisional_schema and Path(args.provisional_schema).exists():
        try:
            ps = json.loads(Path(args.provisional_schema).read_text(encoding="utf-8"))
            if isinstance(ps, list):
                provisional_map = {e["field"]: e["type"] for e in ps if isinstance(e, dict) and e.get("field")}
        except Exception:
            pass

    run_type_infer(Path(args.evidence), Path(args.out), provisional_map)


if __name__ == "__main__":
    main()

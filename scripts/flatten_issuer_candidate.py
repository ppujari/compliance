#!/usr/bin/env python3
"""
flatten_issuer_candidate.py

Convert issuer_candidate.json (nested evidence+value format from schema_reconcile)
into a flat issuer instance JSON compatible with extract_issuer_from_rhp.py output
and verify_one.py / lake exe compliance.

Output format:
{
  "issuer_id": "<stem of candidate path>",
  "source": "issuer_candidate",
  "fields": { "<field>": <typed_value>, ... }
}

Fields that are absent from the candidate (inactive/missing) are included as null
so the Lean checker can apply optional defaults.

Usage:
  python scripts/flatten_issuer_candidate.py \
    --candidate data/processed/reconcile_run_v3/issuer_candidate.json \
    --schema    data/processed/reconcile_run_v3/issuer_schema_reconciled.json \
    --report    data/processed/reconcile_run_v3/type_reconcile_report.json \
    --out       data/processed/issuer_facts_flat_v3.json \
    --issuer-id <optional name>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

def _coerce(value: Any, lean_type: str) -> Any:
    """
    Lightly coerce a candidate value to match the declared Lean type.
    Handles the most common mismatches (e.g. List stored as single Nat).
    """
    base = lean_type.replace("Option ", "").replace("(", "").replace(")", "").strip()

    if value is None:
        return None

    if base == "Bool":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("true", "yes", "1", "complied"):
            return True
        if s in ("false", "no", "0"):
            return False
        return None

    if base == "Nat":
        if isinstance(value, list):
            # If the schema says Nat but we have a list, take the first element
            return value[0] if value else None
        if isinstance(value, (int, float)):
            return int(value)
        # Try parsing first integer in string
        import re
        m = re.search(r"\d+", str(value))
        return int(m.group(0)) if m else None

    if base == "List Nat":
        if isinstance(value, list):
            out = []
            for v in value:
                if isinstance(v, (int, float)):
                    out.append(int(v))
                else:
                    import re
                    m = re.search(r"\d+", str(v))
                    if m:
                        out.append(int(m.group(0)))
            return out
        # Scalar → wrap in list
        if isinstance(value, (int, float)):
            return [int(value)]
        return None

    if base == "String":
        return str(value) if value is not None else None

    return value


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

_TYPE_SPECIFICITY = {
    "List Nat": 5, "List String": 4, "Bool": 3,
    "Nat": 2, "String": 1,
}

def _more_specific_type(schema_type: str, candidate_type: str) -> str:
    """
    Return the more specific of the two types (ignoring Option wrappers).
    If the candidate's inferred type is more specific, prefer it.
    This handles the common case where the schema says 'Nat' but the
    candidate has 'Option List Nat' (3-year series from table evidence).
    """
    def base(t: str) -> str:
        return t.replace("Option ", "").replace("(", "").replace(")", "").strip()

    sb = base(schema_type)
    cb = base(candidate_type)
    s_rank = _TYPE_SPECIFICITY.get(sb, 0)
    c_rank = _TYPE_SPECIFICITY.get(cb, 0)
    # Keep the schema's Option wrapper if the candidate agrees on base type
    if c_rank > s_rank:
        # Use candidate base but preserve Option wrapping from schema if present
        is_option = "Option" in schema_type or "Option" in candidate_type
        return f"Option {cb}" if is_option and not cb.startswith("List") else cb
    return schema_type


def flatten(
    candidate: Dict[str, Any],
    schema: List[Dict[str, str]],
    report: List[Dict[str, Any]],
) -> Dict[str, Any]:
    schema_map = {s["field"]: s["type"] for s in schema if isinstance(s, dict) and s.get("field")}
    report_map = {r["field"]: r for r in report if isinstance(r, dict) and r.get("field")}

    fields: Dict[str, Any] = {}
    coverage: List[Dict[str, Any]] = []

    for field, schema_lean_type in sorted(schema_map.items()):
        cand = candidate.get(field)
        rep = report_map.get(field, {})
        inactive = rep.get("inactive_field", False)

        if cand is not None:
            raw_value = cand.get("value")
            confidence = cand.get("extract_confidence", 0.0)
            source = (cand.get("evidence") or {}).get("source", "unknown")
            # Prefer the candidate's own inferred final_type when it is more specific
            cand_final_type = (cand.get("final_type") or "").strip()
            lean_type = (_more_specific_type(schema_lean_type, cand_final_type)
                         if cand_final_type else schema_lean_type)
            coerced = _coerce(raw_value, lean_type)
            fields[field] = coerced
            coverage.append({
                "field": field,
                "lean_type": lean_type,
                "schema_type": schema_lean_type,
                "candidate_type": cand_final_type or None,
                "raw_value": raw_value,
                "coerced_value": coerced,
                "confidence": confidence,
                "source": source,
                "status": "present",
            })
        else:
            fields[field] = None
            status = "inactive" if inactive else "missing"
            coverage.append({
                "field": field,
                "lean_type": schema_lean_type,
                "schema_type": schema_lean_type,
                "candidate_type": None,
                "raw_value": None,
                "coerced_value": None,
                "confidence": 0.0,
                "source": None,
                "status": status,
            })

    return fields, coverage


def print_coverage_report(coverage: List[Dict[str, Any]]) -> None:
    present  = [c for c in coverage if c["status"] == "present"]
    missing  = [c for c in coverage if c["status"] == "missing"]
    inactive = [c for c in coverage if c["status"] == "inactive"]
    low_conf = [c for c in present if c["confidence"] < 0.5]
    no_quote = [c for c in present
                if not (c.get("source") or "").startswith("table:")
                and c["confidence"] < 0.5]

    print(f"\n{'='*60}")
    print(f"  ISSUER CANDIDATE COVERAGE REPORT")
    print(f"{'='*60}")
    print(f"  Total schema fields : {len(coverage)}")
    print(f"  Present (extracted) : {len(present)}")
    print(f"  Missing (not found) : {len(missing)}")
    print(f"  Inactive (no evid.) : {len(inactive)}")
    print(f"  Low-confidence (<0.5): {len(low_conf)}")
    print(f"{'='*60}")

    if missing:
        print("\n[MISSING -- in schema, not extracted, not inactive]")
        for c in missing:
            print(f"  [X]  {c['field']:<45} ({c['lean_type']})")

    if inactive:
        print("\n[INACTIVE -- no evidence found across all RHP pages]")
        for c in inactive:
            print(f"  [~]  {c['field']:<45} ({c['lean_type']})")

    if low_conf:
        print("\n[LOW CONFIDENCE -- extracted but may be unreliable]")
        for c in low_conf:
            flag = "[!!]" if c["confidence"] < 0.3 else "[!] "
            print(f"  {flag}  {c['field']:<45} conf={c['confidence']:.1f}  raw={repr(c['raw_value'])}")

    print(f"\n[PRESENT -- high confidence]")
    for c in [x for x in present if x["confidence"] >= 0.5]:
        src = c.get("source") or "text"
        print(f"  [OK] {c['field']:<45} = {repr(c['coerced_value'])}  [{src}]")

    print(f"\n{'='*60}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Flatten issuer_candidate.json into a flat issuer instance JSON.")
    ap.add_argument("--candidate", required=True, help="issuer_candidate.json from schema_reconcile run")
    ap.add_argument("--schema", required=True, help="issuer_schema_reconciled.json")
    ap.add_argument("--report", default="", help="type_reconcile_report.json (for inactive flags)")
    ap.add_argument("--out", required=True, help="Output flat issuer instance JSON")
    ap.add_argument("--issuer-id", default="", help="Issuer identifier to embed in output")
    ap.add_argument("--coverage-out", default="", help="Optional path to write coverage report JSON")
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    schema    = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    report: List[Dict[str, Any]] = []
    if args.report and Path(args.report).exists():
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))

    if not isinstance(schema, list):
        print("[ERROR] --schema must be an array of {field, type} objects", file=sys.stderr)
        sys.exit(1)

    fields, coverage = flatten(candidate, schema, report)
    print_coverage_report(coverage)

    issuer_id = args.issuer_id or Path(args.candidate).parent.name
    out_obj = {
        "issuer_id": issuer_id,
        "source": "issuer_candidate",
        "fields": fields,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] Wrote flat issuer instance -> {args.out}")

    if args.coverage_out:
        Path(args.coverage_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.coverage_out).write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[DONE] Wrote coverage report     -> {args.coverage_out}")


if __name__ == "__main__":
    main()

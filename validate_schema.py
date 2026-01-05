#!/usr/bin/env python3
"""
Validate rule JSONL entries against required fields or a JSON Schema.

Usage:
  python3 scripts/validate_schema.py --file data/processed/rules.jsonl
  python3 scripts/validate_schema.py --schema data/schema/rule.schema.json

Checks:
  JSON well-formedness
  Required fields present
  Duplicate rule_ids
  Optional JSON Schema validation (if jsonschema lib installed)
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

try:
    from jsonschema import validate, Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

REQUIRED_FIELDS = ["rule_id", "domain", "title", "text", "lean_id", "notes"]

def load_jsonl(path: Path) -> list[dict]:
    data = []
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                data.append(obj)
            except json.JSONDecodeError as e:
                print(f"JSON parse error at line {ln}: {e}")
    return data

def validate_required(record: dict, required_fields: list[str]) -> list[str]:
    return [k for k in required_fields if k not in record or record[k] in (None, "")]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/processed/rules.jsonl",
                    help="JSONL file to validate")
    ap.add_argument("--schema", default=None,
                    help="Optional JSON schema path for deep validation")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        sys.exit(f"File not found: {path}")

    rules = load_jsonl(path)
    print(f"Loaded {len(rules)} rule records")

    # Check for duplicate rule_ids
    seen = {}
    dupes = []
    for idx, r in enumerate(rules):
        rid = r.get("rule_id")
        if rid in seen:
            dupes.append(rid)
        else:
            seen[rid] = idx + 1
    if dupes:
        print(f"Duplicate rule_id(s): {', '.join(set(dupes))}")
    else:
        print("No duplicate rule_ids")

    # Check required fields
    missing = []
    for i, r in enumerate(rules, start=1):
        miss = validate_required(r, REQUIRED_FIELDS)
        if miss:
            missing.append((i, r.get("rule_id"), miss))
    if missing:
        print(f"Missing fields in {len(missing)} records:")
        for i, rid, fields in missing:
            print(f"  Line {i}: {rid or '(no rule_id)'} missing {fields}")
    else:
        print("All required fields present")

    # Optional JSON schema validation
    if args.schema:
        if not HAS_JSONSCHEMA:
            print("jsonschema not installed; skipping schema validation.")
        else:
            schema_path = Path(args.schema)
            if not schema_path.exists():
                sys.exit(f"Schema file not found: {schema_path}")
            schema = json.loads(schema_path.read_text())
            validator = Draft202012Validator(schema)
            print("Validating against schema...")
            errors = []
            for i, rule in enumerate(rules, start=1):
                for err in validator.iter_errors(rule):
                    errors.append((i, rule.get("rule_id"), err.message))
            if errors:
                print(f"Schema validation errors in {len(errors)} rules:")
                for i, rid, msg in errors:
                    print(f"  Line {i} ({rid or '(no id)'}): {msg}")
            else:
                print("Passed schema validation")

    print("Validation complete.")

if __name__ == "__main__":
    main()

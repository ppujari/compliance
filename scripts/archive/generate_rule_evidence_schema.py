#!/usr/bin/env python3
"""
generate_rule_evidence_schema.py

Generate a deterministic RuleEvidence template entry for every rule in a
rules_*.jsonl file. No LLMs used.

Input:
  --rules_jsonl (required)
  --out (default: data/processed/rule_evidence_schema.json)

Output:
  rule_evidence_schema.json (array of objects)
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict

try:
    from scripts.utils import read_jsonl as _read_jsonl_base  # type: ignore[import-not-found]
except ImportError:
    from utils import read_jsonl as _read_jsonl_base  # type: ignore


def read_jsonl(path: Path) -> List[dict]:
    """Read JSONL and sort deterministically by rule_id."""
    items = _read_jsonl_base(path)
    items.sort(key=lambda o: str(o.get("rule_id") or o.get("rule_id_raw") or ""))
    return items


def build_template(rule_id: str) -> Dict[str, object]:
    return {
        "rule_id": rule_id,
        "status_type": "enum(present, absent, unclear)",
        "evidence": [{"page": None, "quote": None}],
        "extracted_values": {},
        "notes": None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules_jsonl", required=True)
    ap.add_argument("--out", default="data/processed/rule_evidence_schema.json")
    args = ap.parse_args()

    rules_path = Path(args.rules_jsonl)
    rules = read_jsonl(rules_path)
    templates = []
    for obj in rules:
        rid = obj.get("rule_id") or obj.get("rule_id_raw") or "UNKNOWN"
        templates.append(build_template(str(rid)))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(templates)} rule evidence templates to {out_path}")


if __name__ == "__main__":
    main()





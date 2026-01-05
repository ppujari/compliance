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
    # Deterministic order by rule_id
    def _rid(o: dict) -> str:
        rid = o.get("rule_id") or o.get("rule_id_raw") or ""
        return str(rid)

    items.sort(key=_rid)
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





#!/usr/bin/env python3
"""
build_facts_schema.py

Construct a two-layer facts schema (IssuerFacts + OfferFacts) from
issuer_fields.json using deterministic heuristics only.

Inputs:
  --rules_jsonl (required but currently unused; reserved for future routing)
  --issuer_fields_json (required)
  --out (default: data/processed/facts_schema.json)

Outputs:
  facts_schema.json with:
    {
      "issuer_facts": [ ... ],
      "offer_facts": [ ... ]
    }
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List


OFFER_KEYWORDS = (
    "offer",
    "issue",
    "fresh_issue",
    "ofs",
    "offer_for_sale",
    "price_band",
    "lot",
    "listing",
    "allocation",
    "qib",
    "anchor",
    "bid",
    "market_maker",
)


def load_issuer_fields(path: Path) -> List[Dict[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items: List[Dict[str, object]] = []
    if isinstance(data, list):
        for obj in data:
            if isinstance(obj, dict) and "name" in obj:
                items.append(obj)
    items.sort(key=lambda o: str(o.get("name", "")))
    return items


def is_offer_field(name: str) -> bool:
    lname = name.lower()
    return any(k in lname for k in OFFER_KEYWORDS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules_jsonl", required=True)
    ap.add_argument("--issuer_fields_json", required=True)
    ap.add_argument("--out", default="data/processed/facts_schema.json")
    args = ap.parse_args()

    issuer_fields_path = Path(args.issuer_fields_json)
    fields = load_issuer_fields(issuer_fields_path)

    issuer_facts: List[Dict[str, object]] = []
    offer_facts: List[Dict[str, object]] = []

    for f in fields:
        name = str(f.get("name", ""))
        target = offer_facts if is_offer_field(name) else issuer_facts
        target.append(f)

    facts_schema = {
        "issuer_facts": issuer_facts,
        "offer_facts": offer_facts,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(facts_schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote facts schema with {len(issuer_facts)} issuer fields and {len(offer_facts)} offer fields to {out_path}")


if __name__ == "__main__":
    main()





#!/usr/bin/env python3
"""
score_rule_to_schema.py

Deterministic "Rule Mapping Judge" that inspects `notes` for
`Map to ...` clauses and reports parsing quality without using LLMs.

Inputs:
  --rules_jsonl (required)
  --issuer_fields_json (optional; used for regression comparison)

Outputs:
  mapping_report.json containing:
    - total_rules
    - map_to_rules_count
    - map_parse_success_count
    - map_parse_failures: [{rule_id, notes, dropped_tokens, reason}]
    - fields_proposed_from_map_to: sorted list
    - stability: currently None (placeholder for repeated-run Jaccard)
    - unmapped_rules: list of rule_ids with no Map to
    - comparison_vs_issuer_fields (if provided)
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


MAP_TO_RE = re.compile(
    r"""
    Map\sto
    \s+
    (?P<fields>.+?)
    (?=$|[.;])
    """,
    re.IGNORECASE | re.VERBOSE,
)

SPLIT_FIELDS_RE = re.compile(
    r"\s*(?:,|\band/or\b|\band\b|\bor\b|/)\s*",
    re.IGNORECASE,
)


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


def normalize_field_token(token: str) -> Tuple[str, List[str]]:
    applied: List[str] = []
    t = token.strip()
    if not t:
        return "", applied

    changed = True
    while changed and t.startswith("(") and t.endswith(")") and len(t) > 1:
        t = t[1:-1].strip()
        applied.append("strip_outer_parens")
        changed = t.startswith("(") and t.endswith(")")

    if "(" in t or ")" in t:
        t = re.sub(r"[()]", " ", t)
        applied.append("drop_paren_chars")

    new_t = re.sub(r"\s*(?:length\s*=\s*\d+|>=|<=|=|>|<).*$", "", t)
    if new_t != t:
        t = new_t
        applied.append("drop_comparator_or_length")

    new_t = t.strip(" ,.;:")
    if new_t != t:
        t = new_t
        applied.append("trim_punct")

    new_t = re.sub(r"[\s\-]+", "_", t)
    if new_t != t:
        t = new_t
        applied.append("collapse_space_hyphen")

    t = t.strip("_")
    if not t:
        return "", applied
    return t, applied


def parse_map_to(notes: str) -> Tuple[List[str], List[str]]:
    """
    Returns (valid_fields, dropped_tokens).
    dropped_tokens are raw tokens that failed normalization/identifier checks.
    """
    valid: List[str] = []
    dropped: List[str] = []
    for m in MAP_TO_RE.finditer(notes):
        fields_str = m.group("fields")
        parts = SPLIT_FIELDS_RE.split(fields_str)
        for p in parts:
            raw = re.sub(r"\s*(>=|<=|=|>|<).*?$", "", p).strip()
            if not raw:
                continue
            normalized, _ = normalize_field_token(raw)
            if normalized and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", normalized):
                valid.append(normalized)
            else:
                dropped.append(raw)
    return valid, dropped


def load_issuer_fields(path: Path) -> List[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    names: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                names.append(str(item["name"]))
    return sorted(set(names))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules_jsonl", required=True)
    ap.add_argument("--issuer_fields_json", default="")
    ap.add_argument("--out", default="mapping_report.json")
    args = ap.parse_args()

    rules_path = Path(args.rules_jsonl)
    rules = read_jsonl(rules_path)

    total_rules = len(rules)
    map_to_rules_count = 0
    map_parse_success_count = 0
    map_parse_failures: List[Dict[str, object]] = []
    fields_proposed: List[str] = []
    unmapped_rules: List[str] = []

    for obj in rules:
        rid = obj.get("rule_id") or obj.get("rule_id_raw") or "UNKNOWN"
        notes = obj.get("notes") or ""
        has_map_to = bool(MAP_TO_RE.search(notes))
        if not has_map_to:
            unmapped_rules.append(str(rid))
            continue
        map_to_rules_count += 1
        valid, dropped = parse_map_to(notes)
        if valid:
            map_parse_success_count += 1
            fields_proposed.extend(valid)
        if dropped or not valid:
            map_parse_failures.append(
                {
                    "rule_id": rid,
                    "notes": notes,
                    "dropped_tokens": dropped,
                    "reason": "no_valid_tokens" if not valid else "dropped_invalid_tokens",
                }
            )

    fields_proposed = sorted(set(fields_proposed))

    comparison = {}
    if args.issuer_fields_json:
        issuer_fields = load_issuer_fields(Path(args.issuer_fields_json))
        proposed_set = set(fields_proposed)
        issuer_set = set(issuer_fields)
        comparison = {
            "issuer_fields_total": len(issuer_fields),
            "proposed_only": sorted(proposed_set - issuer_set),
            "issuer_only": sorted(issuer_set - proposed_set),
            "jaccard": round(
                len(proposed_set & issuer_set) / len(proposed_set | issuer_set), 4
            )
            if (proposed_set or issuer_set)
            else 1.0,
        }

    report = {
        "total_rules": total_rules,
        "map_to_rules_count": map_to_rules_count,
        "map_parse_success_count": map_parse_success_count,
        "map_parse_failures": map_parse_failures,
        "fields_proposed_from_map_to": fields_proposed,
        "stability": None,  # reserved for repeated-run Jaccard
        "unmapped_rules": unmapped_rules,
    }
    if comparison:
        report["comparison_vs_issuer_fields"] = comparison

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote mapping report to {out_path}")


if __name__ == "__main__":
    main()





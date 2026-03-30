#!/usr/bin/env python3
"""
score_rule_to_schema.py

Deterministic "Rule Mapping Judge" that diagnoses mapping coverage without LLMs.

It supports BOTH styles:
  1) legacy: `notes` contains `Map to ...`
  2) preferred: structured `maps_to: [{"field": "..."}]`

Inputs:
  --rules_jsonl (required)
  --issuer_fields_json (optional; used for regression comparison)

Outputs:
  mapping_report.json containing:
    - total_rules
    - map_to_rules_count (legacy notes-based)
    - map_parse_success_count (legacy notes-based)
    - map_parse_failures: [{rule_id, notes, dropped_tokens, reason}]
    - fields_proposed_from_map_to: sorted list (combined)
    - fields_proposed_from_maps_to: sorted list
    - fields_proposed_from_map_to_notes: sorted list
    - stability: currently None (placeholder for repeated-run Jaccard)
    - unmapped_rules: list of rule_ids with no maps_to and no legacy Map to notes
    - comparison_vs_issuer_fields (if provided)
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    from scripts.utils import read_jsonl as _read_jsonl_base  # type: ignore[import-not-found]
except ImportError:
    from utils import read_jsonl as _read_jsonl_base  # type: ignore


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
    """Read JSONL and sort deterministically by rule_id."""
    items = _read_jsonl_base(path)
    items.sort(key=lambda o: str(o.get("rule_id") or o.get("rule_id_raw") or ""))
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


def parse_maps_to(maps_to: object) -> Tuple[List[str], List[str]]:
    """
    Returns (valid_fields, dropped_fields) from structured maps_to.
    """
    valid: List[str] = []
    dropped: List[str] = []
    if not isinstance(maps_to, list):
        return valid, dropped
    for m in maps_to:
        if not isinstance(m, dict):
            continue
        raw = str(m.get("field") or "").strip()
        if not raw:
            continue
        normalized, _ = normalize_field_token(raw)
        # maps_to schema expects snake_case, but accept Lean/Python identifiers too
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
    map_to_rules_count = 0  # legacy notes Map to
    map_parse_success_count = 0  # legacy notes Map to
    map_parse_failures: List[Dict[str, object]] = []
    fields_from_maps_to: List[str] = []
    fields_from_notes: List[str] = []
    unmapped_rules: List[str] = []

    maps_to_rules_count = 0
    maps_to_parse_success_count = 0
    maps_to_parse_failures: List[Dict[str, object]] = []

    for obj in rules:
        rid = obj.get("rule_id") or obj.get("rule_id_raw") or "UNKNOWN"
        notes = obj.get("notes") or ""
        maps_to = obj.get("maps_to")
        valid_m, dropped_m = parse_maps_to(maps_to)
        if isinstance(maps_to, list) and maps_to:
            maps_to_rules_count += 1
            if valid_m:
                maps_to_parse_success_count += 1
                fields_from_maps_to.extend(valid_m)
            if dropped_m or not valid_m:
                maps_to_parse_failures.append(
                    {
                        "rule_id": rid,
                        "maps_to": maps_to,
                        "dropped_fields": dropped_m,
                        "reason": "no_valid_fields" if not valid_m else "dropped_invalid_fields",
                    }
                )

        has_map_to_notes = bool(MAP_TO_RE.search(notes))
        if has_map_to_notes:
            map_to_rules_count += 1
            valid, dropped = parse_map_to(notes)
            if valid:
                map_parse_success_count += 1
                fields_from_notes.extend(valid)
            if dropped or not valid:
                map_parse_failures.append(
                    {
                        "rule_id": rid,
                        "notes": notes,
                        "dropped_tokens": dropped,
                        "reason": "no_valid_tokens" if not valid else "dropped_invalid_tokens",
                    }
                )

        if (not valid_m) and (not has_map_to_notes) and (not isinstance(maps_to, list) or not maps_to):
            unmapped_rules.append(str(rid))

    fields_from_maps_to = sorted(set(fields_from_maps_to))
    fields_from_notes = sorted(set(fields_from_notes))
    fields_proposed = sorted(set(fields_from_maps_to + fields_from_notes))

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
        "maps_to_rules_count": maps_to_rules_count,
        "maps_to_parse_success_count": maps_to_parse_success_count,
        "maps_to_parse_failures": maps_to_parse_failures,
        "fields_proposed_from_maps_to": fields_from_maps_to,
        "fields_proposed_from_map_to_notes": fields_from_notes,
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





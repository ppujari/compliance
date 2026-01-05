#!/usr/bin/env python3
"""
promote_fields.py

Deterministic scoring of fields to keep the core facts schema tight.
No LLM calls. Demotes low-confidence fields to "evidence-only".

Inputs:
  --rules_jsonl
  --facts_schema_json
  --rule_evidence_schema_json

Outputs:
  promotion_report.json
  updated facts_schema_json (overwritten in place)
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

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

GENERIC_PENALTY = {"conditions", "misc", "as_applicable", "other", "notes"}
THRESHOLD = 1  # score must be >= THRESHOLD to stay in facts schema


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


def parse_map_tokens(notes: str) -> List[Tuple[str, bool, List[str]]]:
    """
    Returns list of (normalized_token, had_comparator, applied_normalizations).
    """
    tokens: List[Tuple[str, bool, List[str]]] = []
    for m in MAP_TO_RE.finditer(notes):
        fields_str = m.group("fields")
        parts = SPLIT_FIELDS_RE.split(fields_str)
        for p in parts:
            raw = p.strip()
            had_comparator = bool(re.search(r"(>=|<=|=|>|<)", raw))
            raw = re.sub(r"\s*(>=|<=|=|>|<).*?$", "", raw).strip()
            if not raw:
                continue
            normalized, applied = normalize_field_token(raw)
            if normalized and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", normalized):
                tokens.append((normalized, had_comparator, applied))
    return tokens


def load_facts_schema(path: Path) -> Dict[str, List[dict]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"issuer_facts": [], "offer_facts": []}
    issuer = data.get("issuer_facts") if isinstance(data, dict) else []
    offer = data.get("offer_facts") if isinstance(data, dict) else []
    issuer_list = issuer if isinstance(issuer, list) else []
    offer_list = offer if isinstance(offer, list) else []
    return {
        "issuer_facts": sorted(issuer_list, key=lambda o: str(o.get("name", ""))),
        "offer_facts": sorted(offer_list, key=lambda o: str(o.get("name", ""))),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules_jsonl", required=True)
    ap.add_argument("--facts_schema_json", required=True)
    ap.add_argument("--rule_evidence_schema_json", required=True)
    ap.add_argument("--out", default="promotion_report.json")
    args = ap.parse_args()

    rules = read_jsonl(Path(args.rules_jsonl))
    facts_schema_path = Path(args.facts_schema_json)
    facts_schema = load_facts_schema(facts_schema_path)

    counts: Dict[str, int] = {}
    comparator_ctx: Dict[str, bool] = {}
    paren_counts: Dict[str, int] = {}

    for obj in rules:
        notes = obj.get("notes") or ""
        tokens = parse_map_tokens(notes)
        for name, had_comp, applied in tokens:
            counts[name] = counts.get(name, 0) + 1
            if had_comp:
                comparator_ctx[name] = True
            if "strip_outer_parens" in applied:
                paren_counts[name] = paren_counts.get(name, 0) + 1

    all_fields = facts_schema["issuer_facts"] + facts_schema["offer_facts"]
    scores: List[Dict[str, object]] = []
    demoted: List[str] = []
    kept: List[str] = []

    for f in sorted(all_fields, key=lambda o: str(o.get("name", ""))):
        name = str(f.get("name", ""))
        occ = counts.get(name, 0)
        paren_only = occ > 0 and paren_counts.get(name, 0) == occ
        score = 0
        details: List[str] = []
        if occ >= 2:
            score += 2
            details.append("reusable_2plus_rules")
        if comparator_ctx.get(name, False):
            score += 2
            details.append("numeric_threshold_nearby")
        if name.lower() in GENERIC_PENALTY:
            score -= 3
            details.append("generic_token_penalty")
        if paren_only:
            score -= 2
            details.append("paren_only_penalty")

        keep = score >= THRESHOLD
        if keep:
            kept.append(name)
        else:
            demoted.append(name)

        scores.append(
            {
                "name": name,
                "score": score,
                "occurrences": occ,
                "comparator_context": comparator_ctx.get(name, False),
                "only_in_parens": paren_only,
                "details": details,
                "promoted": keep,
            }
        )

    # Rebuild facts_schema without demoted fields
    def _filter(fields: List[dict]) -> List[dict]:
        kept_names = set(kept)
        return [f for f in fields if str(f.get("name", "")) in kept_names]

    updated_schema = {
        "issuer_facts": _filter(facts_schema["issuer_facts"]),
        "offer_facts": _filter(facts_schema["offer_facts"]),
    }

    # Persist updated schema in place
    facts_schema_path.write_text(json.dumps(updated_schema, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "threshold": THRESHOLD,
        "demoted_fields": sorted(demoted),
        "kept_fields": sorted(kept),
        "scores": scores,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Promotion scoring complete. Kept {len(kept)} fields, demoted {len(demoted)}. Report → {out_path}")


if __name__ == "__main__":
    main()





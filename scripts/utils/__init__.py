"""
scripts/utils/__init__.py
Shared utility functions for the compliance pipeline.

Centralises functions that were previously duplicated across 5+ scripts:
  read_jsonl                      – schema_reconcile, rule_anchored_extract,
                                    type_infer, llm_generate_lean,
                                    infer_issuer_fields, promote_fields,
                                    score_rule_to_schema, generate_rule_evidence_schema
  normalize_question_type         – extract_lean_to_json, postprocess_rules_and_fields
  base_type_from_question_type    – extract_lean_to_json, postprocess_rules_and_fields
  build_issuer_schema_from_questions – extract_lean_to_json, postprocess_rules_and_fields
  parse_number                    – rule_anchored_extract, type_infer
  parse_bool                      – rule_anchored_extract
  extract_first_json_block        – rule_anchored_extract, schema_reconcile
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> List[dict]:
    """Read a JSONL file and return a list of parsed dicts, skipping bad lines."""
    items: List[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
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


def write_jsonl(path: Path, items: List[dict]) -> None:
    """Write a list of dicts as JSONL (one JSON object per line)."""
    with Path(path).open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# JSON block extraction  (bracket-depth aware, handles markdown fences)
# ---------------------------------------------------------------------------

def extract_first_json_block(text: str) -> str:
    """
    Extract the first well-formed JSON object or array from *text*.

    Strips leading/trailing markdown code fences, then walks character-by-character
    tracking string and bracket depth so it returns only balanced content.
    Returns an empty string when nothing is found.
    """
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    # Strip markdown fences
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I).strip()
    s = re.sub(r"\s*```$", "", s).strip()

    # Find the first opening brace or bracket
    start: Optional[int] = None
    opener = ""
    for i, ch in enumerate(s):
        if ch in "{[":
            start = i
            opener = ch
            break
    if start is None:
        return ""

    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return s[start: j + 1]
    return ""


# ---------------------------------------------------------------------------
# Numeric / boolean parsing  (Indian-comma aware)
# ---------------------------------------------------------------------------

def parse_number(raw: Any) -> Optional[int]:
    """
    Parse a number from a string, handling Indian comma formats (1,44,445.3 → 144445).
    Decimals are dropped (floor).  Returns None when no number is found.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw)
    m = re.search(r"[\d,]+(?:\.\d+)?", s)
    if not m:
        return None
    num = m.group(0).replace(",", "")
    if "." in num:
        num = num.split(".", 1)[0]
    return int(num) if num else None


def parse_bool(raw: Any) -> Optional[bool]:
    """
    Parse a boolean from common compliance-document terms.
    Returns None when the value is unrecognised.
    """
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("true", "yes", "y", "1", "complied", "compliance", "complies", "met", "meets"):
        return True
    if s in ("false", "no", "n", "0", "not complied", "not met", "failed"):
        return False
    return None


# ---------------------------------------------------------------------------
# Lean / issuer-schema type normalisation
# ---------------------------------------------------------------------------

def normalize_question_type(raw: str) -> str:
    """
    Normalise common abbreviated type strings (seen in issuerQuestions) into
    canonical Lean-style type strings.

    Examples:
      OptionBool       -> Option Bool
      OptionListNat    -> Option (List Nat)
      ListNat          -> List Nat
      (already valid)  -> unchanged
    """
    t = (raw or "").strip()
    if not t:
        return "String"
    t = re.sub(r"\s+", " ", t)
    mapping: Dict[str, str] = {
        "OptionBool":    "Option Bool",
        "OptionNat":     "Option Nat",
        "OptionString":  "Option String",
        "OptionListNat": "Option (List Nat)",
        "ListNat":       "List Nat",
        "ListString":    "List String",
    }
    return mapping.get(t, t)


def base_type_from_question_type(norm: str) -> str:
    """
    Strip the Option wrapper from a normalised type string to obtain the base type.

    Examples:
      Option Bool        -> Bool
      Option (List Nat)  -> List Nat
      List Nat           -> List Nat  (unchanged)
    """
    t = (norm or "").strip()
    if t.startswith("Option "):
        inner = t[len("Option "):].strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1].strip()
        return inner
    return t


# Type precedence used when the same field appears with conflicting types.
# Lower index = higher priority / more specific.
TYPE_PRECEDENCE: List[str] = [
    "List Nat",
    "List String",
    "String",
    "Nat",
    "Bool",
]


def build_issuer_schema_from_questions(
    issuer_questions: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Deterministically build a canonical issuer schema list  [{field, type}]
    from a list of issuer_questions dicts  [{field, question, type}].

    Deduplicates by field name, resolves type conflicts using TYPE_PRECEDENCE,
    and returns entries sorted alphabetically by field name.
    """
    by_field: Dict[str, Dict[str, str]] = {}
    for q in issuer_questions:
        field = (q.get("field") or "").strip()
        if not field:
            continue
        qtext    = (q.get("question") or "").strip()
        raw_type = q.get("type") or "String"
        norm_type = normalize_question_type(raw_type)
        base_type = base_type_from_question_type(norm_type)

        cur = by_field.get(field)
        if cur is None:
            by_field[field] = {
                "field":     field,
                "question":  qtext,
                "type":      base_type,
                "type_raw":  raw_type,
                "type_norm": norm_type,
            }
        else:
            # Keep the more descriptive question
            if qtext and len(qtext) > len(cur.get("question", "")):
                cur["question"] = qtext
            # Resolve type conflicts with fixed precedence
            cur_type = cur.get("type") or "String"
            if base_type in TYPE_PRECEDENCE and cur_type in TYPE_PRECEDENCE:
                if TYPE_PRECEDENCE.index(base_type) < TYPE_PRECEDENCE.index(cur_type):
                    cur["type"] = base_type
            elif base_type and cur_type != base_type:
                cur["type"] = "String"   # safe fallback on unknown conflict

    schema = [{"field": v["field"], "type": v["type"]} for v in by_field.values()]
    schema.sort(key=lambda x: x["field"])
    return schema

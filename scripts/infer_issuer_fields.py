#!/usr/bin/env python3
"""
infer_issuer_fields.py

Scan rules JSONL files, extract candidate issuer field names from `notes`
(e.g. 'Map to holding_period >= 1 year.'), and infer a simple type
for each field from a small vocabulary:

  Bool, Nat, List Nat, String

Outputs a canonical issuer fields file that can be used to generate:

  - Lean `structure Issuer`
  - Python dataclass / Pydantic model
  - Extraction targets for the RHP parser

Usage (example):

  python scripts/infer_issuer_fields.py \
      --rules data/processed/rules_os_qwen_32b_v4_post_new.jsonl \
      --out data/processed/issuer_fields.json

"""

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Iterable, Tuple, Optional


# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class FieldContext:
    """Aggregated info for one candidate issuer field."""
    name: str
    rule_ids: List[str]
    texts: List[str]      # small snippets from rules["text"]
    notes: List[str]      # full notes where it appeared
    raw_tokens: List[str]  # raw tokens seen prior to normalization
    normalizations: List[str]  # normalization steps applied

@dataclass
class IssuerField:
    """Final schema entry for an issuer field."""
    name: str
    lean_type: str
    python_type: str
    description: str
    from_rules: List[str]
    raw_tokens_seen: List[str]
    normalization_applied: List[str]


# ----------------------------------------------------------------------
# Helpers to read rules JSONL
# ----------------------------------------------------------------------

def read_jsonl(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


# ----------------------------------------------------------------------
# Extract candidate field names from 'notes'
# ----------------------------------------------------------------------

MAP_TO_RE = re.compile(
    r"""
    Map\sto          # literal 'Map to'
    \s+
    (?P<fields>.+?)  # everything until punctuation / end
    (?=$|[.;])
    """,
    re.IGNORECASE | re.VERBOSE
)

# Patterns inside the "fields" capture, e.g.
#  "holding_period"
#  "holding_period and capital_expenditure_utilization"
#  "promoter_lock_in, capital_expenditure_utilization"
# Use token-based separators so identifiers containing letters like
# "and" are not split apart.
SPLIT_FIELDS_RE = re.compile(
    r"\s*(?:,|\band/or\b|\band\b|\bor\b|/)\s*",
    re.IGNORECASE,
)


def normalize_field_token(token: str) -> Tuple[str, List[str]]:
    """
    Normalize a raw token extracted from 'Map to ...' by:
      - stripping outer parentheses
      - removing leftover paren characters
      - trimming trailing constraint fragments (comparators, length=3, etc.)
      - trimming punctuation
      - collapsing whitespace/hyphens to underscores
    Returns (normalized_token, [normalization_steps_applied]).
    """
    applied: List[str] = []
    t = token.strip()
    if not t:
        return "", applied

    # Strip balanced outer parentheses repeatedly
    changed = True
    while changed and t.startswith("(") and t.endswith(")") and len(t) > 1:
        changed = True
        t = t[1:-1].strip()
        applied.append("strip_outer_parens")
        # Check again if new string still wrapped in parens
        changed = t.startswith("(") and t.endswith(")")

    # Remove any remaining paren characters
    if "(" in t or ")" in t:
        t = re.sub(r"[()]", " ", t)
        applied.append("drop_paren_chars")

    # Drop trailing comparator / constraint fragments
    new_t = re.sub(r"\s*(?:length\s*=\s*\d+|>=|<=|=|>|<).*$", "", t)
    if new_t != t:
        t = new_t
        applied.append("drop_comparator_or_length")

    # Trim trailing punctuation
    new_t = t.strip(" ,.;:")
    if new_t != t:
        t = new_t
        applied.append("trim_punct")

    # Collapse whitespace or hyphens to underscore
    new_t = re.sub(r"[\s\-]+", "_", t)
    if new_t != t:
        t = new_t
        applied.append("collapse_space_hyphen")

    t = t.strip("_")
    if not t:
        return "", applied

    return t, applied


def extract_field_names_from_notes(notes: str) -> List[Tuple[str, str, List[str]]]:
    """
    From a 'notes' string like:
      "Map to holding_period >= 1 year."
      "Map to promoter_lock_in and capital_expenditure_utilization."
    return list of tuples (normalized_field, raw_token, normalization_steps)
    """
    result: List[Tuple[str, str, List[str]]] = []
    for m in MAP_TO_RE.finditer(notes):
        fields_str = m.group("fields")
        parts = SPLIT_FIELDS_RE.split(fields_str)
        for p in parts:
            # Strip trailing comparators on each part individually so we
            # do not drop siblings joined by "and", "," etc.
            candidate_raw = re.sub(r"\s*(>=|<=|=|>|<).*?$", "", p).strip()
            if not candidate_raw:
                continue
            normalized, applied = normalize_field_token(candidate_raw)
            # keep only identifiers-like tokens
            if not normalized or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", normalized):
                continue
            result.append((normalized, candidate_raw, applied))

    return result


# ----------------------------------------------------------------------
# Aggregate field contexts
# ----------------------------------------------------------------------

def collect_field_contexts(rule_files: List[str]) -> Dict[str, FieldContext]:
    """
    Go through all rules in the given files, collect candidate field names
    from 'notes', and aggregate context.
    """
    fields: Dict[str, FieldContext] = {}

    for path in rule_files:
        objs = list(read_jsonl(path))
        # Sort deterministically by rule_id (string compare)
        def _rid(o: dict) -> str:
            rid = o.get("rule_id") or o.get("rule_id_raw")
            if rid is None:
                return ""
            return str(rid)

        objs.sort(key=_rid)

        for obj in objs:
            rule_id = obj.get("rule_id") or obj.get("rule_id_raw") or "UNKNOWN"
            notes = obj.get("notes") or ""
            text = obj.get("text") or ""

            field_infos = extract_field_names_from_notes(notes)
            for fname, raw_tok, applied_norms in field_infos:
                if fname not in fields:
                    fields[fname] = FieldContext(
                        name=fname,
                        rule_ids=[],
                        texts=[],
                        notes=[],
                        raw_tokens=[],
                        normalizations=[],
                    )
                ctx = fields[fname]
                if rule_id not in ctx.rule_ids:
                    ctx.rule_ids.append(rule_id)
                if text and text not in ctx.texts:
                    # keep only a few samples to avoid huge blobs
                    if len(ctx.texts) < 3:
                        ctx.texts.append(text)
                if notes and notes not in ctx.notes:
                    if len(ctx.notes) < 5:
                        ctx.notes.append(notes)
                if raw_tok not in ctx.raw_tokens:
                    ctx.raw_tokens.append(raw_tok)
                for step in applied_norms:
                    if step not in ctx.normalizations:
                        ctx.normalizations.append(step)

    return fields


# ----------------------------------------------------------------------
# Heuristic type inference
# ----------------------------------------------------------------------

def guess_python_type(lean_type: str) -> str:
    if lean_type == "Bool":
        return "bool"
    if lean_type == "Nat":
        return "int"
    if lean_type == "List Nat":
        return "List[int]"
    if lean_type == "String":
        return "str"
    # fallback
    return "Any"


def infer_type_for_field(ctx: FieldContext) -> Tuple[str, str, str]:
    """
    Return (lean_type, python_type, description) for a field based on its name
    and a little bit of context.
    """
    name = ctx.name
    lname = name.lower()
    texts_concat = " ".join(ctx.texts).lower()
    notes_concat = " ".join(ctx.notes).lower()
    combined_text = f"{texts_concat} {notes_concat}"

    # --- Heuristic 1: Booleans by naming convention ---
    bool_prefixes = ("is_", "has_", "uses_")
    bool_text_cues = (
        "yes/no",
        "yes or no",
        "whether ",
        "shall not",
        "must not",
        "prohibited",
        "not permitted",
    )
    if lname.startswith(bool_prefixes) or any(cue in combined_text for cue in bool_text_cues):
        lean_type = "Bool"
        py_type = guess_python_type(lean_type)
        descr = f"Boolean flag: {name.replace('_', ' ')}."
        return lean_type, py_type, descr

    # --- Heuristic 2: Ratios / percentages / counts -> Nat ---
    if ("ratio" in lname
        or "percent" in lname
        or lname.endswith("_pct")
        or lname.endswith("_count")
        or "per cent" in texts_concat
        or "%" in texts_concat):
        lean_type = "Nat"
        py_type = guess_python_type(lean_type)
        descr = f"Non-negative integer (e.g. percentage or ratio) for {name.replace('_', ' ')}."
        return lean_type, py_type, descr

    # --- Heuristic 3: multi-year numeric series -> List Nat ---
    has_years = ("preceding three years" in combined_text
                 or "preceding three full years" in combined_text
                 or "last three years" in combined_text
                 or "each of the preceding three" in combined_text)
    if has_years:
        lean_type = "List Nat"
        py_type = guess_python_type(lean_type)
        descr = f"Series of non-negative integers over multiple years for {name.replace('_', ' ')}."
        return lean_type, py_type, descr

    # --- Heuristic 4: contains 'period', 'months', 'years' -> Nat ---
    if (
        "period" in lname
        or "tenure" in lname
        or "duration" in lname
        or "months" in lname
        or "years" in lname
        or "age" in lname
        or "term" in lname
    ):
        lean_type = "Nat"
        py_type = guess_python_type(lean_type)
        descr = f"Non-negative integer duration (months/years) for {name.replace('_', ' ')}."
        return lean_type, py_type, descr

    # --- Heuristic 5: obvious strings / identifiers -> String ---
    string_name_keywords = (
        "name",
        "type",
        "category",
        "class",
        "sector",
        "industry",
        "country",
        "currency",
        "exchange",
        "isin",
        "cin",
        "pan",
        "tin",
        "address",
        "code",
        "rating",
        "identifier",
    )
    string_text_cues = (
        "name of",
        "shall be disclosed",
        "identify",
        "address",
    )
    if any(k in lname for k in string_name_keywords) or any(cue in combined_text for cue in string_text_cues):
        lean_type = "String"
        py_type = guess_python_type(lean_type)
        descr = f"Text/identifier field for {name.replace('_', ' ')}."
        return lean_type, py_type, descr

    # --- Fallback: treat as Nat (numeric) ---
    # You can later manually adjust a few to String/Enum if needed.
    lean_type = "Nat"
    py_type = guess_python_type(lean_type)
    descr = f"Non-negative integer field for {name.replace('_', ' ')}."
    return lean_type, py_type, descr


def build_issuer_fields(
    field_contexts: Dict[str, FieldContext]
) -> List[IssuerField]:
    fields: List[IssuerField] = []
    for name, ctx in sorted(field_contexts.items()):
        ctx.rule_ids.sort()
        ctx.raw_tokens.sort()
        ctx.normalizations.sort()
        lean_type, py_type, descr = infer_type_for_field(ctx)
        fields.append(
            IssuerField(
                name=name,
                lean_type=lean_type,
                python_type=py_type,
                description=descr,
                from_rules=ctx.rule_ids,
                raw_tokens_seen=ctx.raw_tokens,
                normalization_applied=ctx.normalizations,
            )
        )
    return fields


# ----------------------------------------------------------------------
# Pretty-print helpers (optional)
# ----------------------------------------------------------------------

def emit_lean_structure(fields: List[IssuerField]) -> str:
    """
    Emit a Lean `structure Issuer` snippet as a convenience.
    You don't have to use this automatically; you can paste & edit.
    """
    lines = ["structure Issuer where"]
    for f in fields:
        lines.append(f"  {f.name} : {f.lean_type}")
    return "\n".join(lines)


def emit_python_dataclass(fields: List[IssuerField]) -> str:
    """
    Emit a Python @dataclass snippet as a convenience.
    """
    lines = [
        "from dataclasses import dataclass",
        "from typing import List, Optional",
        "",
        "@dataclass",
        "class IssuerModel:",
    ]
    for f in fields:
        # Map List[int] to proper typing
        py_type = f.python_type
        if py_type.startswith("List["):
            lines.append(f"  {f.name}: {py_type}  # {f.description}")
        else:
            lines.append(f"  {f.name}: {py_type}  # {f.description}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rules",
        nargs="+",
        required=True,
        help="One or more rules_*.jsonl files to scan for 'Map to ...' notes.",
    )
    ap.add_argument(
        "--out",
        required=True,
        help="Output path for issuer_fields.json (array of objects).",
    )
    ap.add_argument(
        "--emit-lean",
        default=None,
        help="Optional path to write a Lean `structure Issuer` snippet.",
    )
    ap.add_argument(
        "--emit-py",
        default=None,
        help="Optional path to write a Python dataclass snippet.",
    )
    args = ap.parse_args()

    # 1. collect field contexts
    ctxs = collect_field_contexts(args.rules)
    if not ctxs:
        print("No fields found via 'Map to ...' in the provided rules files.")
        return

    # 2. infer types
    issuer_fields = build_issuer_fields(ctxs)

    # 3. write issuer_fields.json
    out_data = [asdict(f) for f in issuer_fields]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(issuer_fields)} issuer fields to {args.out}")

    # 4. optionally emit helper snippets
    if args.emit_lean:
        lean_src = emit_lean_structure(issuer_fields)
        with open(args.emit_lean, "w", encoding="utf-8") as f:
            f.write(lean_src + "\n")
        print(f"Wrote Lean Issuer snippet to {args.emit_lean}")

    if args.emit_py:
        py_src = emit_python_dataclass(issuer_fields)
        with open(args.emit_py, "w", encoding="utf-8") as f:
            f.write(py_src + "\n")
        print(f"Wrote Python IssuerModel snippet to {args.emit_py}")


if __name__ == "__main__":
    main()

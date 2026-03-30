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

try:
    from scripts.utils import read_jsonl  # type: ignore[import-not-found]
except ImportError:
    from utils import read_jsonl  # type: ignore


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
    type_hints: List[str]  # type hints seen from rules["maps_to"][].type_hint
    constraints_texts: List[str]  # constraints text samples from rules["maps_to"][].constraints_text

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
    type_hints_seen: List[str]
    constraints_text_samples: List[str]


# ----------------------------------------------------------------------
# Helpers to read rules JSONL
# ----------------------------------------------------------------------



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

            # Prefer structured maps_to if present; fall back to legacy "Map to ..." notes parsing.
            field_infos: List[Tuple[str, str, List[str], str, str]] = []

            maps_to = obj.get("maps_to")
            if isinstance(maps_to, list):
                for m in maps_to:
                    if not isinstance(m, dict):
                        continue
                    f = (m.get("field") or "").strip()
                    if not f:
                        continue
                    normalized, applied = normalize_field_token(f)
                    if not normalized or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", normalized):
                        continue
                    type_hint = (m.get("type_hint") or "").strip()
                    constraints_text = (m.get("constraints_text") or "").strip()
                    field_infos.append((normalized, f, applied + ["from_maps_to"], type_hint, constraints_text))

            legacy = extract_field_names_from_notes(notes)
            for fname, raw_tok, applied_norms in legacy:
                field_infos.append((fname, raw_tok, applied_norms + ["from_notes_map_to"], "", ""))

            for fname, raw_tok, applied_norms, type_hint, constraints_text in field_infos:
                if fname not in fields:
                    fields[fname] = FieldContext(
                        name=fname,
                        rule_ids=[],
                        texts=[],
                        notes=[],
                        raw_tokens=[],
                        normalizations=[],
                        type_hints=[],
                        constraints_texts=[],
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
                if type_hint:
                    th = normalize_type_hint(type_hint)
                    if th and th not in ctx.type_hints:
                        ctx.type_hints.append(th)
                if constraints_text and constraints_text not in ctx.constraints_texts:
                    if len(ctx.constraints_texts) < 5:
                        ctx.constraints_texts.append(constraints_text)

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


def normalize_type_hint(type_hint: str) -> str:
    """
    Map extended hints to the core vocabulary used by this script:
      Bool, Nat, List Nat, String
    """
    t = (type_hint or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t)
    # Option* -> underlying
    if t == "OptionBool":
        return "Bool"
    if t == "OptionNat":
        return "Nat"
    if t == "OptionListNat":
        return "List Nat"
    if t == "OptionString":
        return "String"
    # Accept either "List Nat" or "ListNat"
    if t == "ListNat":
        return "List Nat"
    return t


def choose_type_from_hints(type_hints: List[str]) -> str:
    """
    Choose a stable type from a list of type hints.
    Preference is given to the most common normalized hint. Ties break by a
    fixed precedence to keep deterministic output.
    """
    normed = [normalize_type_hint(x) for x in type_hints if x]
    normed = [x for x in normed if x in ("Bool", "Nat", "List Nat", "String")]
    if not normed:
        return ""
    counts: Dict[str, int] = {}
    for x in normed:
        counts[x] = counts.get(x, 0) + 1
    max_ct = max(counts.values())
    top = sorted([k for k, v in counts.items() if v == max_ct])
    precedence = ["List Nat", "String", "Nat", "Bool"]
    for p in precedence:
        if p in top:
            return p
    return top[0]


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
    constraints_concat = " ".join(ctx.constraints_texts).lower()

    # --- Strong signal: explicit type hints from maps_to ---
    hinted = choose_type_from_hints(ctx.type_hints)
    if hinted:
        lean_type = hinted
        py_type = guess_python_type(lean_type)
        descr = f"Field for {name.replace('_', ' ')} (from rule type_hint)."
        return lean_type, py_type, descr

    # --- Strong signal: explicit multi-year series constraints -> List Nat ---
    has_3yr_constraints = (
        "preceding three years" in constraints_concat
        or "preceding three full years" in constraints_concat
        or "last three years" in constraints_concat
        or "each of the preceding three" in constraints_concat
        or re.search(r"\blength\s*=\s*3\b", constraints_concat) is not None
    )
    if has_3yr_constraints:
        lean_type = "List Nat"
        py_type = guess_python_type(lean_type)
        descr = f"Series of non-negative integers over multiple years for {name.replace('_', ' ')} (from constraints_text)."
        return lean_type, py_type, descr

    # --- Name-based booleans (avoid defaulting to Nat for compliance flags) ---
    # Examples: ..._application, ..._agreement, ..._demat(dematerialised), ..._approved, ..._paid_up, ..._forfeited
    bool_contains = (
        "agreement",
        "application",
        "approved",
        "approval",
        "appoint",
        "obtained",
        "created",
        "demat",
        "dematerial",
        "forfeit",
        "forfeited",
        "paid_up",
        "paidup",
        "eligible",
        "required",
        "complied",
        "compliance",
        "consent",
        "default",
    )
    bool_suffixes = (
        "_application",
        "_agreement",
        "_approved",
        "_approval",
        "_appointed",
        "_obtained",
        "_created",
        "_demat",
        "_dematerialised",
        "_dematerialized",
        "_paid_up",
        "_forfeited",
        "_required",
        "_eligible",
        "_complied",
        "_in_default",
    )
    if lname.endswith(bool_suffixes) or any(tok in lname for tok in bool_contains):
        # Guard against obvious non-bool numeric facts
        if not any(k in lname for k in ("period", "tenure", "duration", "months", "years", "age", "term", "ratio", "percent", "_pct", "_count")):
            lean_type = "Bool"
            py_type = guess_python_type(lean_type)
            descr = f"Boolean compliance flag for {name.replace('_', ' ')} (name-based inference)."
            return lean_type, py_type, descr

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

    # --- Fallback: String is the safe default for unclassified fields ---
    # String avoids forcing numeric types onto entity/category/identifier fields.
    lean_type = "String"
    py_type = guess_python_type(lean_type)
    descr = f"Text field for {name.replace('_', ' ')} (type unresolved; review manually)."
    return lean_type, py_type, descr


def build_issuer_fields(
    field_contexts: Dict[str, FieldContext]
) -> List[IssuerField]:
    fields: List[IssuerField] = []
    for name, ctx in sorted(field_contexts.items()):
        ctx.rule_ids.sort()
        ctx.raw_tokens.sort()
        ctx.normalizations.sort()
        ctx.type_hints.sort()
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
                type_hints_seen=ctx.type_hints,
                constraints_text_samples=ctx.constraints_texts,
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

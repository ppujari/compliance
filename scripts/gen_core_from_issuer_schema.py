#!/usr/bin/env python3
# scripts/gen_core_from_issuer_schema.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Tuple


def load_schema(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def discover_fields(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict of fieldName -> jsonschema for the Issuer fields.
    Supports both:
      - top-level "properties" (flat)
      - nested properties under "fields" object as in data/schema/issuer_schema.json
      - combined rules_and_fields format containing "issuer_schema": [{field, type}]
    """
    props = {}
    # Combined "rules_and_fields" format
    issuer_schema = schema.get("issuer_schema")
    if isinstance(issuer_schema, list) and issuer_schema:
        for entry in issuer_schema:
            if not isinstance(entry, dict):
                continue
            name = entry.get("field")
            lean_ty = entry.get("type")
            if isinstance(name, str) and isinstance(lean_ty, str):
                # Mark with special key so type-mapper can short-circuit
                props[name] = {"lean_type": lean_ty}
        if props:
            return props
    # Nested under "fields"
    fields_obj = (((schema.get("properties") or {}).get("fields") or {}) if isinstance(schema.get("properties"), dict) else {})
    fields_props = fields_obj.get("properties") if isinstance(fields_obj, dict) else None
    if isinstance(fields_props, dict) and fields_props:
        props.update(fields_props)
    # Top-level (flat) fields (optional)
    top_props = schema.get("properties")
    if isinstance(top_props, dict):
        # Include any non-meta fields if they look like Issuer fields
        for k, v in top_props.items():
            if k in {"issuer_id", "source", "fields"}:
                continue
            if isinstance(v, dict):
                props.setdefault(k, v)
    return props


def _lean_default_for_lean_type(lean_ty: str) -> str:
    if lean_ty == "Bool":
        return "false"
    if lean_ty == "Nat":
        return "0"
    if lean_ty == "Int":
        return "0"
    if lean_ty == "String":
        return '""'
    if lean_ty.startswith("List"):
        return "[]"
    return '""'


def lean_type_for_schema(s: Dict[str, Any]) -> Tuple[str, str]:
    """
    Map JSON Schema to Lean type and a default literal for normalize.
    """
    # Short-circuit if provided as Lean type (combined file path)
    if isinstance(s, dict) and "lean_type" in s:
        lt = s.get("lean_type") or "String"
        return str(lt), _lean_default_for_lean_type(str(lt))
    t = s.get("type")
    if t == "boolean":
        return "Bool", "false"
    if t == "integer":
        return "Nat", "0"
    if t == "number":
        return "Int", "0"  # conservative
    if t == "string":
        return "String", '""'
    if t == "array":
        items = s.get("items") or {}
        if isinstance(items, dict):
            it = items.get("type")
            if it == "integer":
                return "List Nat", "[]"
            if it == "string":
                return "List String", "[]"
            if it == "boolean":
                return "List Bool", "[]"
        return "List String", "[]"
    # Fallback
    return "String", '""'


def generate_core(namespace: str, fields: Dict[str, Dict[str, Any]]) -> str:
    # Stable header
    header = (
        "import Lean\n"
        "import Lean.Data.Json\n"
        f"\nnamespace {namespace}\n"
        "open Lean\n"
        "\nset_option linter.unusedVariables false\n\n"
    )
    # Build Issuer and IssuerInput
    issuer_fields_lines = []
    issuer_input_fields_lines = []
    normalize_lines = []

    def option_type(lean_ty: str) -> str:
        needs_paren = (" " in lean_ty) or lean_ty.startswith("List") or "(" in lean_ty or ")" in lean_ty
        return f"Option ({lean_ty})" if needs_paren else f"Option {lean_ty}"

    for name, schema in fields.items():
        lean_ty, default_lit = lean_type_for_schema(schema if isinstance(schema, dict) else {})
        issuer_fields_lines.append(f"  {name} : {lean_ty}")
        issuer_input_fields_lines.append(f"  {name} : {option_type(lean_ty)} := none")
        normalize_lines.append(f"  , {name} := x.{name}.getD {default_lit}")

    issuer_struct = (
        "/-- Issuer data model used by compliance rules (auto-generated). -/\n"
        "structure Issuer where\n"
        + "\n".join(issuer_fields_lines) + "\n"
        "  deriving Repr, ToJson\n\n"
    )
    issuer_input_struct = (
        "/-- Input-friendly variant with optional fields for JSON decoding (auto-generated). -/\n"
        "structure IssuerInput where\n"
        + "\n".join(issuer_input_fields_lines) + "\n"
        "  deriving Repr, FromJson\n\n"
    )
    normalize_fn = (
        "/-- Normalize an IssuerInput by filling defaults for missing fields (auto-generated). -/\n"
        "def IssuerInput.normalize (x : IssuerInput) : Issuer :=\n"
        "  { " + (normalize_lines[0][4:] if normalize_lines else "") + "\n"
        + "\n".join(normalize_lines[1:]) + "\n"
        "  }\n\n"
    )
    fromjson_inst = (
        "/-- Custom FromJson instance: decode via IssuerInput and normalize. -/\n"
        "instance : FromJson Issuer where\n"
        "  fromJson? j := do\n"
        "    let inp ← fromJson? (α := IssuerInput) j\n"
        "    pure (IssuerInput.normalize inp)\n\n"
    )
    rules_structs = (
        "/-- One compliance rule with a predicate and metadata. -/\n"
        "structure ComplianceRule where\n"
        "  id         : String\n"
        "  title      : String\n"
        "  reference  : String\n"
        "  check      : Issuer → Bool\n"
        "  failReason : Issuer → String\n"
        "  remedy?    : Option String\n\n"
        "/-- Result of running one rule against an Issuer. -/\n"
        "structure RuleResult where\n"
        "  id        : String\n"
        "  title     : String\n"
        "  reference : String\n"
        "  passed    : Bool\n"
        "  reason?   : Option String\n"
        "  deriving Repr, ToJson, FromJson\n\n"
        "/-- Apply a single rule to an issuer. -/\n"
        "def runRule (i : Issuer) (r : ComplianceRule) : RuleResult :=\n"
        "  let ok := r.check i\n"
        "  { id := r.id\n"
        "  , title := r.title\n"
        "  , reference := r.reference\n"
        "  , passed := ok\n"
        "  , reason? :=\n"
        "      if ok then none\n"
        "      else\n"
        "        some (\n"
        "          r.failReason i ++\n"
        "          match r.remedy? with\n"
        "          | some s => \"\\nSuggested remedy: \" ++ s\n"
        "          | none   => \"\"\n"
        "        )\n"
        "  }\n\n"
        "/-- Helpers used inside rules. -/\n"
        "def allGeNat (xs : List Nat) (n : Nat) : Bool :=\n"
        "  xs.all (fun x => x ≥ n)\n\n"
        "def lengthIs {α} (xs : List α) (k : Nat) : Bool :=\n"
        "  xs.length == k\n\n"
    )
    footer = f"end {namespace}\n"
    return header + issuer_struct + issuer_input_struct + normalize_fn + fromjson_inst + rules_structs + footer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True, help="Path to issuer schema JSON")
    ap.add_argument("--out", required=True, help="Output Lean path, e.g., Src/Core_auto.lean")
    ap.add_argument("--namespace", default="Src.Core_auto", help="Lean namespace for the generated core")
    args = ap.parse_args()

    schema_path = Path(args.schema)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = load_schema(schema_path)
    fields = discover_fields(schema)
    if not fields:
        raise SystemExit("No fields discovered in schema. Ensure 'properties.fields.properties' or top-level 'properties' are present.")

    lean_src = generate_core(args.namespace, fields)
    out_path.write_text(lean_src, encoding="utf-8")
    print(f"✅ Wrote core → {out_path} (namespace {args.namespace})")


if __name__ == "__main__":
    main()



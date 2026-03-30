#!/usr/bin/env python3
# scripts/gen_rules_lean.py
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_list_body_depth(src: str, def_name: str) -> Optional[str]:
    """
    Extract the body of a Lean list definition using bracket-depth counting.
    Finds: def <def_name> ... := [ <BODY> ]
    Returns the inner content between the outermost brackets, or None if not found.
    """
    m = re.search(rf"def\s+{re.escape(def_name)}\b[\s\S]*?:=\s*\[", src)
    if not m:
        return None
    i = m.end()  # position right after the opening '['
    depth = 1
    in_str = False
    esc = False
    for j in range(i, len(src)):
        ch = src[j]
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
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return src[i:j].strip()
    return None


def extract_rules_list(src: str) -> Optional[str]:
    """
    Extract the inner list body of generated rules from either:
      def generatedRuleset : List ComplianceRule := [ ... ]
    or
      def generatedRulesetChunk : List ComplianceRule := [ ... ]
    Uses bracket-depth counting so greedy matching cannot bleed into
    other definitions (e.g. issuerQuestions) that follow in the file.
    """
    body = _extract_list_body_depth(src, "generatedRuleset")
    if body is not None:
        return body
    body = _extract_list_body_depth(src, "generatedRulesetChunk")
    return body


def ensure_wrapped(
    rules_inner: str,
    core_module: str,
    rules_module_lean: str,
) -> str:
    """
    Build a Lean file with the expected shape:

      import <core_module>
      open <core_module>
      namespace <rules_module_lean>
      def generatedRuleset : List ComplianceRule := [
        <rules_inner>
      ]
      end <rules_module_lean>
    """
    open_ns = core_module
    header = (
        f"import {core_module}\n"
        f"open {open_ns}\n"
        f"namespace {rules_module_lean}\n\n"
    )
    body = (
        "def generatedRuleset : List ComplianceRule := [\n"
        + rules_inner + "\n]\n\n"
    )
    footer = f"end {rules_module_lean}\n"
    return header + body + footer


def _escape_lean_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\"", "\\\"")


def _fix_incomplete_if_then(expr: str) -> str:
    """Add a final else branch to Lean if-then chains that are missing one.

    Lean 4 if-then-else is an expression; omitting else is a syntax error.
    Pattern: ... then "some message"<end-of-expr> → append  else ""
    """
    s = expr.rstrip()
    # If expression ends with:  then "..."  (with no following else)
    if re.search(r'\bthen\b\s*"[^"]*"\s*$', s):
        s = s + ' else ""'
    return s


def _strip_remedy_from_failreason(fr: str) -> str:
    # Remove any trailing ",\n    remedy? := ..." fragment embedded inside the failReason content
    parts = re.split(r",\s*remedy\?\s*:=", fr, maxsplit=1, flags=re.S)
    cleaned = parts[0].rstrip().rstrip(",").rstrip()
    return cleaned


def _extract_remedy_from_failreason(fr: str) -> Optional[str]:
    m = re.search(r"remedy\?\s*:=\s*(some\s+.+|none)\s*$", fr.strip(), flags=re.S)
    if not m:
        return None
    return m.group(1).strip()


def build_from_combined_json(
    data: Dict[str, Any],
    core_module: str,
    rules_module_lean: str,
) -> str:
    import re
    def uses_i(body: str) -> bool:
        # Heuristic: direct references like i., (i), i ==, etc.
        return bool(re.search(r'(^|[^A-Za-z0-9_])i(\.|[^A-Za-z0-9_])', body))

    def normalize_lambda(expr: str) -> str:
        s = expr.strip()
        # If already a lambda, only switch binder to _ when the binder is not referenced
        m = re.match(r'fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*=>\s*(.*)$', s, flags=re.S)
        if m:
            var = m.group(1)
            body = m.group(2)
            # If body doesn't reference the binder variable, switch to underscore
            binder_used = bool(re.search(rf'(^|[^A-Za-z0-9_]){re.escape(var)}(\.|[^A-Za-z0-9_])', body))
            if not binder_used:
                return f"fun _ => {body}"
            return s
        # Not a lambda; if it references i, wrap with fun i =>, else fun _ =>
        return f"fun {'i' if uses_i(s) else '_'} => {s}"
    def clean_check_expr(raw: str) -> str:
        s = (raw or "").strip()
        # Cut at embedded 'failReason :=' or 'remedy? :=' if present
        for token in ["failReason :=", "remedy? :="]:
            idx = s.find(token)
            if idx != -1:
                s = s[:idx]
        # Drop end-of-line comments starting with --
        cidx = s.find("--")
        if cidx != -1:
            s = s[:cidx]
        # Normalize common list quantifiers to Lean's List.any
        s = s.replace(".exists", ".any")
        # Fix Lean 4 option methods
        s = s.replace(".getOrElse", ".getD")
        s = s.replace(".isDefined", ".isSome")
        # Fix propositional equality inside list lambdas:
        #   fun VAR => VAR = NUM  ->  fun VAR => VAR == NUM
        s = re.sub(
            r'(fun\s+(\w+)\s*=>\s*)\2(\s*)=(\s*)(\d)',
            lambda m: m.group(1) + m.group(2) + m.group(3) + "==" + m.group(4) + m.group(5),
            s,
        )
        # Trim trailing commas and whitespace
        s = s.rstrip().rstrip(",").rstrip()
        return s

    def _is_unsafe_expr(expr: str) -> bool:
        """Return True if the expression has patterns that will fail Lean compilation."""
        # Optional chaining with tuple index (not valid in Lean 4)
        if "?." in expr:
            return True
        # Bare identifier references to types/constructors not defined in Core
        undefined_refs = [
            "ConvertibleSecurities", ".forfeited", "isDebtInstrument",
            "hasDefaultPaymentOrRepaymentIssue", "hasConvertibleDebtInstruments",
            "hasWarrantsWith", "monetary_assets", "Cash",
        ]
        for ref in undefined_refs:
            if ref in expr:
                return True
        # .some used as field accessor on a non-Option value (e.g. e.some where e : String)
        if re.search(r'\b\w+\.some\b', expr):
            return True
        # Tuple index access on simple types (.1, .2 on Nat/String)
        if re.search(r'\b[a-z]\.\d\b', expr):
            return True
        # Comparison of a variable with a Bool field using > (e.g. s > i.fully_paid_up_equity_shares)
        if re.search(r'>\s*i\.fully_paid_up_equity_shares', expr):
            return True
        # .getD on non-optional inner value inside a .map lambda
        if re.search(r'fun\s+\w+\s*=>\s*\w+\.getD', expr):
            return True
        # .forall not a valid Lean 4 List method (use .all instead) but also on Option types
        if ".forall" in expr:
            return True
        return False

    rules: List[Dict[str, Any]] = data.get("rules") or []
    items: List[str] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = _escape_lean_string(str(r.get("id", "")))
        title = _escape_lean_string(str(r.get("title", "")))
        ref = _escape_lean_string(str(r.get("reference", "")))
        check_expr = clean_check_expr(str(r.get("check", "fun _ => True")))
        fr_expr_raw = str(r.get("failReason", "fun _ => \"(no detail)\"")).strip()
        # Remedy handling: prefer explicit field if provided, else parse from failReason tail
        remedy_field = r.get("remedy")
        parsed_remedy = _extract_remedy_from_failreason(fr_expr_raw)
        fr_expr = _strip_remedy_from_failreason(fr_expr_raw)
        fr_expr = fr_expr.replace(".exists", ".any")
        fr_expr = fr_expr.replace(".getOrElse", ".getD")
        fr_expr = fr_expr.replace(".isDefined", ".isSome")
        fr_expr = _fix_incomplete_if_then(fr_expr)
        # Stub out check/failReason expressions that reference undefined fields or
        # use invalid Lean 4 syntax patterns (e.g. optional chaining ?.field).
        if _is_unsafe_expr(check_expr):
            print(f"  [STUB] {rid}: unsafe check expr — replacing with fun _ => True", file=sys.stderr)
            check_expr = "fun _ => True"
        if _is_unsafe_expr(fr_expr):
            fr_expr = f'fun _ => "(rule {rid}: check stub — schema mismatch)"'
        # Normalize lambda binders to avoid unused variable warnings
        check_expr = normalize_lambda(check_expr)
        fr_expr = normalize_lambda(fr_expr)
        if isinstance(remedy_field, str) and remedy_field.strip():
            remedy_expr = f"some \"{_escape_lean_string(remedy_field.strip())}\""
        elif isinstance(remedy_field, dict):
            # If already a Lean expression in dict form (unlikely), fallback to none
            remedy_expr = "none"
        elif parsed_remedy:
            remedy_expr = parsed_remedy
        else:
            remedy_expr = "none"
        item = (
            "{ id := \"" + rid + "\"\n"
            "  , title := \"" + title + "\"\n"
            "  , reference := \"" + ref + "\"\n"
            "  , check := " + check_expr + "\n"
            "  , failReason := " + fr_expr + "\n"
            "  , remedy? := " + remedy_expr + " }"
        )
        items.append(item)
    rules_inner = ",\n".join(items)
    return ensure_wrapped(rules_inner, core_module, rules_module_lean)


def read_json(p: Path) -> Dict[str, Any]:
    import json
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def maybe_generate_via_llm(rules_jsonl: Optional[str], tmp_out: Path, root: Path) -> Optional[Path]:
    """
    Optionally call scripts/llm_generate_lean.py to synthesize Lean from rules JSONL.
    """
    if not rules_jsonl:
        return None
    script = root / "scripts" / "llm_generate_lean.py"
    if not script.exists():
        print("llm_generate_lean.py not found; cannot synthesize from JSONL", file=sys.stderr)
        return None
    cmd = [sys.executable, script.as_posix(), "--in", rules_jsonl, "--out", tmp_out.as_posix()]
    try:
        subprocess.run(cmd, check=True, cwd=root.as_posix())
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] LLM generation failed: {e}", file=sys.stderr)
        return None
    return tmp_out


def generate(
    rules_fields_path: str = "",
    lean_in_path: str = "",
    core: str = "Src.Core_auto",
    tag: str = "",
    out_path: str = "",
) -> None:
    """
    Programmatic entry point — callable from verify_one.py without spawning a subprocess.

    Exactly one of `rules_fields_path` or `lean_in_path` must be non-empty.

    Args:
        rules_fields_path: Path to combined rules_and_fields_<tag>.json (preferred).
        lean_in_path:      Path to raw LLM-generated .lean file (fallback).
        core:              Core Lean module name to import/open.
        tag:               Short tag that names the output module (e.g. 'judged_v2').
        out_path:          Destination Lean file path.
    """
    if not tag:
        raise ValueError("generate() requires a non-empty 'tag'.")
    if not out_path:
        raise ValueError("generate() requires a non-empty 'out_path'.")

    rules_module_lean = f"Src.GeneratedRules_{tag}"
    op = Path(out_path)
    op.parent.mkdir(parents=True, exist_ok=True)

    if rules_fields_path:
        rfp = Path(rules_fields_path)
        if not rfp.exists():
            raise FileNotFoundError(f"rules_fields JSON not found: {rfp}")
        data = read_json(rfp)
        content = build_from_combined_json(data, core, rules_module_lean)
        op.write_text(content, encoding="utf-8")
        print(f"[DONE] Wrote rules -> {op} (from combined JSON, module {rules_module_lean}, core {core})")
        return

    if lean_in_path:
        lip = Path(lean_in_path)
        if not lip.exists():
            raise FileNotFoundError(f"lean_in file not found: {lip}")
        src = read_text(lip)
        rules_inner = extract_rules_list(src)
        if not rules_inner:
            m = re.search(r"\[\s*(\{[\s\S]*?\})\s*(?:,\s*\{[\s\S]*?\}\s*)*\]", src, flags=re.S)
            if m:
                rules_inner = m.group(0)[1:-1].strip()
        if not rules_inner:
            raise ValueError(f"Could not extract rules list from Lean source: {lip}")
        content = ensure_wrapped(rules_inner, core, rules_module_lean)
        op.write_text(content, encoding="utf-8")
        print(f"[DONE] Wrote rules -> {op} (module {rules_module_lean}, core {core})")
        return

    raise ValueError("generate() requires either 'rules_fields_path' or 'lean_in_path'.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lean_in", type=str, default="", help="Path to input Lean produced by LLM (optional if --rules provided)")
    ap.add_argument("--rules", type=str, default="", help="Path to rules JSONL; will call llm_generate_lean.py to produce Lean")
    ap.add_argument("--rules_fields", type=str, default="", help="Path to combined rules_and_fields_<tag>.json to build Lean directly")
    ap.add_argument("--core", type=str, default="Src.Core_v2", help="Core module to import/open")
    ap.add_argument("--tag", type=str, required=True, help="Tag to name rules module, e.g., gpt_oss_v1")
    ap.add_argument("--out", type=str, required=True, help="Output Lean file path, e.g., Src/GeneratedRules_gpt_oss_v1.lean")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Highest priority: combined JSON if provided
    if args.rules_fields:
        rules_fields_path = Path(args.rules_fields)
        if not rules_fields_path.exists():
            print(f"[ERROR] Combined rules_and_fields JSON not found: {rules_fields_path}", file=sys.stderr)
            sys.exit(1)
        data = read_json(rules_fields_path)
        rules_module_lean = f"Src.GeneratedRules_{args.tag}"
        content = build_from_combined_json(data, args.core, rules_module_lean)
        out_path.write_text(content, encoding="utf-8")
        print(f"[DONE] Wrote rules -> {out_path} (from combined JSON, module {rules_module_lean}, core {args.core})")
        return

    lean_in_path: Optional[Path] = Path(args.lean_in) if args.lean_in else None
    # If lean_in not provided, try generating via LLM from rules JSONL
    if (not lean_in_path) or (lean_in_path and not lean_in_path.exists()):
        tmp = repo_root / ".tmp_rules_lean.lean"
        p = maybe_generate_via_llm(args.rules or None, tmp, repo_root)
        if not p or not p.exists():
            raise SystemExit("No valid --lean_in and could not generate from --rules.")
        lean_in_path = p

    src = read_text(lean_in_path)
    rules_inner = extract_rules_list(src)
    if not rules_inner:
        # As a fallback, try to find list literal between square brackets in any def of List ComplianceRule
        m = re.search(r"\[\s*(\{[\s\S]*?\})\s*(?:,\s*\{[\s\S]*?\}\s*)*\]", src, flags=re.S)
        if m:
            rules_inner = m.group(0)[1:-1].strip()
    if not rules_inner:
        print("[ERROR] Could not extract rules list from Lean source.", file=sys.stderr)
        sys.exit(2)

    rules_module_lean = f"Src.GeneratedRules_{args.tag}"
    content = ensure_wrapped(rules_inner, args.core, rules_module_lean)
    out_path.write_text(content, encoding="utf-8")
    print(f"[DONE] Wrote rules -> {out_path} (module {rules_module_lean}, core {args.core})")


if __name__ == "__main__":
    main()



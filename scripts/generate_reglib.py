#!/usr/bin/env python3
"""Generate a Lean Reglib directory from enriched rules JSONL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROMAN = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
}


def load_rules(path: str) -> list[dict]:
    rules: list[dict] = []
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception as e:
                print(f"[WARN] JSON parse failed at line {i}: {e}", file=sys.stderr)
                continue
            if isinstance(rec, dict):
                rules.append(rec)
    return rules


def chapter_part_key(rule: dict) -> tuple[str, str]:
    chapter = (rule.get("chapter") or {}).get("number") if isinstance(rule.get("chapter"), dict) else None
    part = (rule.get("part") or {}).get("number") if isinstance(rule.get("part"), dict) else None
    reg_num = str(rule.get("regulation_number", "") or "")
    m = re.match(r"(\d+)", reg_num)
    reg_top = int(m.group(1)) if m else None

    # Data hygiene override: Regulations 4-23 are always Chapter II in ICDR 2018.
    if reg_top is not None and 4 <= reg_top <= 23:
        chapter = "II"

    return str(chapter or "II"), str(part or "I")


def part_file_name(chapter_number: str, part_number: str) -> str:
    ch = ROMAN.get(str(chapter_number), chapter_number)
    pt = ROMAN.get(str(part_number), part_number)
    return f"Chapter{ch}_Part{pt}"


def sanitize_def_name(rule_id: str) -> str:
    name = str(rule_id or "").lower().replace("icdr_", "reg_")
    name = re.sub(r"[^a-z0-9_]", "_", name)
    return name.strip("_")


def lean_field_name(field: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(field or "")).strip("_").lower()


def best_lean_type(field: str, type_hint: str) -> str:
    f = str(field or "").lower()
    t = str(type_hint or "")

    if t == "Bool":
        return "Bool"
    if t == "String":
        return "String"
    if "months" in f:
        return "List Months" if t == "List Nat" else "Months"
    if "years" in f:
        return "List Years" if t == "List Nat" else "Years"
    if t in ("Nat", "List Nat") and any(k in f for k in ["pct", "ratio", "min", "max"]):
        return "Nat"
    if t in ("Nat", "List Nat") and any(k in f for k in ["crore", "worth", "profit", "assets", "value", "threshold", "cost"]):
        return "INR_Crore" if t == "Nat" else "List INR_Crore"
    if t == "List Nat":
        return "List INR_Crore"
    if t == "Nat":
        return "Nat"
    return t or "Bool"


def default_value(field: str, type_hint: str) -> str:
    f = str(field or "").lower()
    t = str(type_hint or "")
    if t == "Bool" and any(k in f for k in ["debarred", "defaulter", "fugitive", "outstanding", "pledged", "wilful", "fraudulent"]):
        return "false"
    if t == "Bool":
        return "true"
    if t == "String":
        return '"direct"'
    if t == "List Nat":
        return "[10, 12, 15]"
    if "pct" in f or "ratio" in f:
        return "20"
    if "months" in f:
        return "12"
    if "years" in f:
        return "1"
    if any(k in f for k in ["crore", "worth", "profit", "assets"]):
        return "10"
    return "1"


def reg_sort_key(reg_str: str) -> tuple[int, str]:
    m = re.match(r"(\d+)", str(reg_str or ""))
    return (int(m.group(1)) if m else 10**9, str(reg_str or ""))


def _iter_maps_to(rule: dict) -> list[dict]:
    mt = rule.get("maps_to", [])
    if isinstance(mt, list):
        return [x for x in mt if isinstance(x, dict)]
    return []


def generate_core_lean(rules: list[dict], framework: str) -> str:
    field_defs: dict[str, tuple[str, str, str]] = {}
    by_reg: dict[str, list[str]] = defaultdict(list)

    for rule in rules:
        reg = str(rule.get("regulation_number", "") or "unknown")
        for m in _iter_maps_to(rule):
            raw_field = m.get("field", "")
            f = lean_field_name(raw_field)
            if not f:
                continue
            if f not in field_defs:
                t = best_lean_type(raw_field, m.get("type_hint", ""))
                doc = str(m.get("constraints_text", "") or str(rule.get("text", ""))[:120]).strip()
                field_defs[f] = (t, doc, reg)
                by_reg[reg].append(f)

    lines: list[str] = []
    lines.append(f"-- Auto-generated from {framework}; DO NOT EDIT MANUALLY.")
    lines.append("")
    lines.append("namespace Reglib.ICDR")
    lines.append("")
    lines.append("abbrev INR_Crore := Nat")
    lines.append("abbrev Pct       := Nat")
    lines.append("abbrev Months    := Nat")
    lines.append("abbrev Years     := Nat")
    lines.append("")
    lines.append("inductive IssueType where")
    lines.append("  | IPO | FPO | RightsIssue | QIP | Preferential | SME_IPO")
    lines.append("  deriving DecidableEq, Repr")
    lines.append("")
    lines.append("inductive SecurityType where")
    lines.append("  | EquityShares | ConvertibleDebt | ConvertiblePreference | Warrants")
    lines.append("  deriving DecidableEq, Repr")
    lines.append("")
    lines.append("structure Promoter where")
    lines.append("  is_debarred                       : Bool")
    lines.append("  debarment_period_over             : Bool")
    lines.append("  is_director_of_debarred_company   : Bool")
    lines.append("  is_wilful_defaulter_or_fraudulent : Bool")
    lines.append("  is_fugitive_economic_offender     : Bool")
    lines.append("  holding_pct                       : Pct")
    lines.append("  deriving Repr")
    lines.append("")
    lines.append("structure Issuer where")

    for reg in sorted(by_reg.keys(), key=reg_sort_key):
        lines.append(f"  -- -- Regulation {reg} --")
        for f in by_reg[reg]:
            t, doc, _ = field_defs[f]
            lines.append(f"  /-- {doc[:120]} -/")
            lines.append(f"  {f:<34} : {t}")

    lines.append("  /-- All promoters (for list-level Reg 5 checks) -/")
    lines.append("  promoters                          : List Promoter")
    lines.append("  deriving Repr")
    lines.append("")
    lines.append("end Reglib.ICDR")
    lines.append("")
    return "\n".join(lines)


def _top_reg(rule_id: str) -> str:
    m = re.match(r"ICDR_(\d+)", str(rule_id or ""))
    return m.group(1) if m else ""


def _is_proviso_or_explanation(rule_id: str) -> bool:
    s = str(rule_id or "").lower()
    return ("proviso" in s) or ("explanation" in s)


def _rule_body(rule: dict) -> str:
    maps = _iter_maps_to(rule)
    if not maps:
        return "sorry  -- TODO: no fields extracted"

    text_l = str(rule.get("text", "") or "").lower()
    parts: list[str] = []
    for m in maps:
        raw = m.get("field", "")
        field = lean_field_name(raw)
        if not field:
            continue
        hint = str(m.get("type_hint", "") or "")
        if hint == "Bool":
            neg = any(k in text_l for k in [
                "shall not", "not be eligible", "debarred", "defaulter",
                "fugitive", "pledged", "prohibited",
            ])
            parts.append(f"issuer.{field} = {'false' if neg else 'true'}")
        elif hint == "List Nat":
            n = 3
            m_year = re.search(r"preceding\s+(\d+)\s+years", text_l)
            if m_year:
                try:
                    n = int(m_year.group(1))
                except Exception:
                    n = 3
            parts.append(f"(issuer.{field}.length = {n} ∧ issuer.{field}.all (· ≥ 1))")
        elif hint == "Nat":
            parts.append(f"issuer.{field} ≥ 0  -- TODO: set correct threshold")
        elif hint == "String":
            parts.append(f'issuer.{field} ≠ ""')
        else:
            parts.append(f"issuer.{field} = issuer.{field}")

    return "\n  ∧ ".join(parts) if parts else "sorry  -- TODO: unmapped"


def generate_rules_lean(
    rules: list[dict],
    chapter: str,
    part: str,
    part_title: str,
    file_name: str,
) -> str:
    filtered = [r for r in rules if chapter_part_key(r) == (chapter, part)]
    regs: dict[str, list[dict]] = defaultdict(list)
    for r in filtered:
        regs[_top_reg(r.get("rule_id", ""))].append(r)

    ch_int = ROMAN.get(chapter, chapter)
    pt_int = ROMAN.get(part, part)

    lines: list[str] = []
    lines.append(f"-- Auto-generated rules file: {file_name}.lean")
    lines.append(f"-- Chapter {chapter}, Part {part}: {part_title}")
    lines.append("")
    lines.append("import Reglib.ICDR.definitions.Core")
    lines.append("")
    lines.append("namespace Reglib.ICDR.Rules")
    lines.append("")
    lines.append("open Reglib.ICDR")
    lines.append("")

    composite_regs: list[str] = []
    for reg in sorted(regs.keys(), key=lambda x: int(x) if str(x).isdigit() else 10**9):
        if not reg:
            continue
        lines.append(f"/-! ## Regulation {reg} -/")
        group = regs[reg]
        def_names: list[str] = []
        for r in sorted(group, key=lambda x: str(x.get("rule_id", ""))):
            rid = str(r.get("rule_id", "") or "")
            dname = sanitize_def_name(rid)
            def_names.append(dname)
            text = re.sub(r"\s+", " ", str(r.get("text", "") or "")).strip()
            lines.append(f"/-- Reg {r.get('regulation_number', '')}: {text[:120]}... -/")
            lines.append(f"def {dname} (issuer : Issuer) : Prop :=")
            lines.append(f"  {_rule_body(r)}")
            lines.append("")

        eligible_defs = [
            sanitize_def_name(str(r.get("rule_id", "") or ""))
            for r in group
            if _iter_maps_to(r) and not _is_proviso_or_explanation(r.get("rule_id", ""))
        ]
        if len(eligible_defs) >= 2:
            gate = f"reg_{reg}_eligible"
            composite_regs.append(gate)
            lines.append(f"/-- Combined Regulation {reg} gate -/")
            lines.append(f"def {gate} (issuer : Issuer) : Prop :=")
            lines.append("  " + "\n  ∧ ".join(f"{d} issuer" for d in eligible_defs))
            lines.append("")

    lines.append(f"/-! ## Composite Chapter {chapter} Part {part} Gate -/")
    lines.append("")
    lines.append(f"def chapter{ch_int}_part{pt_int}_eligible (issuer : Issuer) : Prop :=")
    if composite_regs:
        lines.append("  " + "\n  ∧ ".join(f"{g} issuer" for g in composite_regs))
    else:
        lines.append("  True")
    lines.append("")
    lines.append("end Reglib.ICDR.Rules")
    lines.append("")
    return "\n".join(lines)


def generate_compliance_lean(rules: list[dict], part_files: list[str]) -> str:
    field_types: dict[str, str] = {}
    for r in rules:
        for m in _iter_maps_to(r):
            f = lean_field_name(m.get("field", ""))
            if f and f not in field_types:
                field_types[f] = str(m.get("type_hint", "") or "Nat")

    lines: list[str] = []
    lines.append("-- Auto-generated compliance gate file.")
    lines.append("")
    for pf in part_files:
        lines.append(f"import Reglib.ICDR.rules.{pf}")
    lines.append("import Reglib.ICDR.definitions.Core")
    lines.append("")
    lines.append("namespace Reglib.ICDR.Rules")
    lines.append("open Reglib.ICDR")
    lines.append("")
    lines.append("/-! ## Full IPO Compliance Gate -/")
    lines.append("")
    lines.append("def ipo_eligible (issuer : Issuer) : Prop :=")
    gates = []
    for pf in part_files:
        m = re.match(r"Chapter(\d+)_Part(\d+)", pf)
        if m:
            gates.append(f"chapter{m.group(1)}_part{m.group(2)}_eligible issuer")
    lines.append("  " + ("\n  ∧ ".join(gates) if gates else "True"))
    lines.append("")
    lines.append("/-! ## Sample Compliant Issuer -/")
    lines.append("")
    lines.append("def sample_compliant_issuer : Issuer := {")
    for f in sorted(field_types.keys()):
        lines.append(f"  {f} := {default_value(f, field_types[f])},")
    lines.append("  promoters := [")
    lines.append("    { is_debarred := false")
    lines.append("      debarment_period_over := false")
    lines.append("      is_director_of_debarred_company := false")
    lines.append("      is_wilful_defaulter_or_fraudulent := false")
    lines.append("      is_fugitive_economic_offender := false")
    lines.append("      holding_pct := 25 }")
    lines.append("  ]")
    lines.append("}")
    lines.append("")
    lines.append("/-! ## Smoke-Test Proofs -/")
    lines.append("")
    lines.append("theorem sample_passes_reg5 :")
    lines.append("    reg_5_eligible sample_compliant_issuer := by")
    lines.append("  unfold reg_5_eligible reg_5_1_a reg_5_1_b reg_5_1_c reg_5_1_d reg_5_2")
    lines.append("  simp [sample_compliant_issuer, List.all]")
    lines.append("")
    lines.append("end Reglib.ICDR.Rules")
    lines.append("")
    return "\n".join(lines)


def generate_root_import(part_files: list[str]) -> str:
    lines = [
        "-- Reglib.lean",
        "-- Root import -- auto-generated by generate_reglib.py",
        "",
        "import Reglib.ICDR.definitions.Core",
    ]
    for pf in part_files:
        lines.append(f"import Reglib.ICDR.rules.{pf}")
    lines.append("import Reglib.ICDR.rules.Compliance")
    lines.append("")
    return "\n".join(lines)


def generate_lakefile() -> str:
    return """-- Reglib/lakefile.lean
import Lake
open Lake DSL

package Reglib where
  name        := "Reglib"
  version     := "0.1.0"
  description := "Formal regulatory library for SEBI ICDR compliance verification"

lean_lib Reglib where
  roots := #[`Reglib]
"""


def write_text(path: Path, content: str, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        print(f"[SKIP] {path}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[WRITE] {path}", file=sys.stderr)
    return True


def _part_sort_key(k: tuple[str, str]) -> tuple[int, int, str, str]:
    ch, pt = k
    ch_i = int(ROMAN.get(ch, 999)) if str(ROMAN.get(ch, "")).isdigit() else 999
    pt_i = int(ROMAN.get(pt, 999)) if str(ROMAN.get(pt, "")).isdigit() else 999
    return ch_i, pt_i, ch, pt


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Reglib Lean files from enriched JSONL rules.")
    ap.add_argument("--rules", required=True, help="Path to enriched rules JSONL file")
    ap.add_argument("--out-dir", default="Reglib", help="Root output directory for the Lean library")
    ap.add_argument("--framework", default="SEBI_ICDR_2018", help="Regulation framework identifier string")
    ap.add_argument("--year", default="2018", help="Regulation year used as subdirectory name")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files (default: skip if exists)")
    args = ap.parse_args()

    rules = load_rules(args.rules)
    out_dir = Path(args.out_dir)
    definitions_dir = out_dir / "ICDR" / args.year / "definitions"
    rules_dir = out_dir / "ICDR" / args.year / "rules"
    definitions_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.mkdir(parents=True, exist_ok=True)

    writes = 0
    writes += int(write_text(definitions_dir / "Core.lean", generate_core_lean(rules, args.framework), args.overwrite))

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    titles: dict[tuple[str, str], str] = {}
    for r in rules:
        key = chapter_part_key(r)
        groups[key].append(r)
        part_title = (r.get("part") or {}).get("title") if isinstance(r.get("part"), dict) else ""
        if key not in titles:
            titles[key] = str(part_title or "")

    part_files: list[str] = []
    for key in sorted(groups.keys(), key=_part_sort_key):
        ch, pt = key
        fname = part_file_name(ch, pt)
        part_files.append(fname)
        content = generate_rules_lean(rules, ch, pt, titles.get(key, ""), fname)
        writes += int(write_text(rules_dir / f"{fname}.lean", content, args.overwrite))

    # If overwriting, remove stale Chapter*_Part*.lean files not regenerated this run.
    if args.overwrite:
        keep = {f"{name}.lean" for name in part_files}
        for old in rules_dir.glob("Chapter*_Part*.lean"):
            if old.name not in keep:
                old.unlink(missing_ok=True)
                print(f"[WRITE] removed stale {old}", file=sys.stderr)

    compliance = generate_compliance_lean(rules, part_files)
    writes += int(write_text(rules_dir / "Compliance.lean", compliance, args.overwrite))

    root_import = generate_root_import(part_files)
    writes += int(write_text(out_dir / "Reglib.lean", root_import, args.overwrite))
    writes += int(write_text(out_dir / "lakefile.lean", generate_lakefile(), args.overwrite))

    print(f"[DONE] Processed {len(rules)} rules; wrote {writes} files.", file=sys.stderr)


if __name__ == "__main__":
    main()


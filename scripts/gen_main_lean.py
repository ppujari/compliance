#!/usr/bin/env python3
# scripts/gen_main_lean.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path


MAIN_TEMPLATE = """import Lean
import Lean.Data.Json
import {CORE_MODULE}
import {RULES_MODULE}

namespace Src.Main_v2

open Lean
open {CORE_MODULE}
open {RULES_MODULE}

set_option linter.unusedVariables false

/-- Ruleset adapted from SEBI ICDR Regulations (anchors in comments). -/
def ruleset : List ComplianceRule :=
  {RULES_BARE}.generatedRuleset

/-- Run the ruleset and collect results. -/
def runAll (i : Issuer) : List RuleResult :=
  ruleset.map (runRule i)

/-- Compute overall eligibility: all rules that are applicable pass. -/
def overallEligible (results : List RuleResult) : Bool :=
  results.all (·.passed)

/-- Render a human-readable report. -/
def renderReport (results : List RuleResult) : String :=
  let (passed, failed) := results.partition (·.passed)
  let header := if failed.isEmpty then "[DONE] Eligible: All applicable rules satisfied\\n"
                else "[ERROR] Not Eligible: some rules failed\\n"
  let showOne (r : RuleResult) : String :=
    if r.passed then
      s!"[DONE] {r.id} — {r.title}"
    else
      s!"[ERROR] {r.id} — {r.title}\\nReason: {r.reason?.getD "(no detail)"}\\nRef: {r.reference}"
  header ++
  "\\n— Failed —\\n" ++ (if failed.isEmpty then "(none)\\n" else String.intercalate "\\n\\n" (failed.map showOne)) ++
  "\\n\\n— Passed —\\n" ++ (if passed.isEmpty then "(none)\\n" else String.intercalate "\\n" (passed.map showOne))

structure Report where
  eligible : Bool
  failed   : List RuleResult
  passed   : List RuleResult
  deriving Repr, ToJson, FromJson

def buildReport (i : Issuer) : Report :=
  let results := runAll i
  let eligible := overallEligible results
  let (passed, failed) := results.partition (·.passed)
  { eligible := eligible, failed := failed, passed := passed }

/-- Parse Issuer JSON from a string or throw a user-friendly IO error. -/
def parseIssuerJson (s : String) : IO Issuer := do
  let j ← match Lean.Json.parse s with
          | Except.ok j      => pure j
          | Except.error err => throw <| IO.userError s!"Invalid JSON: {err}"
  match Lean.fromJson? (α := Issuer) j with
  | Except.ok issuer   => pure issuer
  | Except.error err   => throw <| IO.userError s!"Invalid Issuer JSON: {err}"

/-- Read entire stdin as text (Lean 4.21). Uses `getLine` in a loop and stops on EOF. -/
partial def readStdinAll : IO String := do
  let h ← IO.getStdin
  let rec loop (acc : String) : IO String := do
    try
      let line ← h.getLine        -- throws on EOF
      loop (acc ++ line)
    catch _ =>
      pure acc
  loop ""

/-- Write Report as compact JSON to file or stdout. -/
def writeReportJson (rep : Report) (outPath? : Option String) : IO Unit := do
  let out := (Lean.toJson rep).compress
  match outPath? with
  | some p => IO.FS.writeFile p out
  | none   => IO.println out

def main (args : List String) : IO Unit := do
  match args with
  | ["--in", inPath] =>
      let data   ← IO.FS.readFile inPath
      let issuer ← parseIssuerJson data
      let rep := buildReport issuer
      writeReportJson rep none
  | ["--in", inPath, "--out", outPath] =>
      let data   ← IO.FS.readFile inPath
      let issuer ← parseIssuerJson data
      let rep := buildReport issuer
      writeReportJson rep (some outPath)
  | _ =>
      IO.eprintln "Usage:\\n  compliance --in <file> [--out <file>]\\n  (or) echo '{Issuer JSON}' | compliance"

end Src.Main_v2

open Src.Main_v2

def main (args : List String) : IO Unit :=
  Src.Main_v2.main args
"""


def generate(core: str, rules: str, out: str = "Src/Main_v2.lean") -> None:
    """
    Programmatic entry point — callable from verify_one.py without spawning a subprocess.

    Args:
        core:  Core Lean module name  (e.g. 'Src.Core_auto').
        rules: Rules Lean module name (e.g. 'Src.GeneratedRules_judged_v2').
        out:   Destination Lean file path (default: 'Src/Main_v2.lean').
    """
    if not core:
        raise ValueError("generate() requires a non-empty 'core' module name.")
    if not rules:
        raise ValueError("generate() requires a non-empty 'rules' module name.")
    content = (
        MAIN_TEMPLATE
        .replace("{CORE_MODULE}", core)
        .replace("{RULES_MODULE}", rules)
        .replace("{RULES_BARE}", rules)
    )
    op = Path(out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(content, encoding="utf-8")
    print(f"[DONE] Wrote main -> {op} (imports: core={core}, rules={rules})")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate Main.lean that imports Core and Rules modules and wires up the compliance runner."
    )
    ap.add_argument("--core", default="", help="Core module name, e.g., Src.Core_v2 or Src.Core_auto")
    ap.add_argument("--rules", default="", help="Rules module name, e.g., Src.GeneratedRules_v3")
    # --issuer-schema: if provided, auto-derive the core namespace from the schema filename
    # (convenience alias; does not auto-generate the Core file — run gen_core_from_issuer_schema.py for that)
    ap.add_argument(
        "--issuer-schema", default="",
        help="Path to issuer_schema_reconciled.json.  When --core is omitted, the core namespace "
             "is inferred from the schema filename (e.g. reconcile_run_v3 -> Src.Core_reconcile_run_v3).",
    )
    ap.add_argument("--out", default="Src/Main_v2.lean", help="Output path; defaults to Src/Main_v2.lean")
    args = ap.parse_args()

    # Derive core module name if not given directly
    core_mod = args.core.strip()
    if not core_mod and args.issuer_schema:
        schema_stem = Path(args.issuer_schema).parent.name or Path(args.issuer_schema).stem
        core_mod = f"Src.Core_{schema_stem}"
        print(f"[INFO] --core not specified; derived core module: {core_mod}", file=__import__("sys").stderr)
    if not core_mod:
        ap.error("--core (or --issuer-schema to derive it) is required")

    rules_mod = args.rules.strip()
    if not rules_mod:
        ap.error("--rules is required")

    # Bare module for the ruleset reference (no trailing spaces)
    rules_bare = rules_mod

    content = (
        MAIN_TEMPLATE
        .replace("{CORE_MODULE}", core_mod)
        .replace("{RULES_MODULE}", rules_mod)
        .replace("{RULES_BARE}", rules_bare)
    )
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(content, encoding="utf-8")
    print(f"[DONE] Wrote main -> {outp} (imports: core={core_mod}, rules={rules_mod})")


if __name__ == "__main__":
    main()



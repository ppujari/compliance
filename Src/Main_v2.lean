import Lean
import Lean.Data.Json
import Src.Core_v2
import Src.GeneratedRules_mistral_7b_v1

namespace Src.Main_v2

open Lean
open Src.Core_v2
open Src.GeneratedRules_mistral_7b_v1

set_option linter.unusedVariables false

/-- Ruleset adapted from SEBI ICDR Regulations (anchors in comments). -/
def ruleset : List ComplianceRule :=
  Src.GeneratedRules_mistral_7b_v1.generatedRuleset

/-- Run the ruleset and collect results. -/
def runAll (i : Issuer) : List RuleResult :=
  ruleset.map (runRule i)

/-- Compute overall eligibility: all rules that are applicable pass. -/
def overallEligible (results : List RuleResult) : Bool :=
  results.all (·.passed)

/-- Render a human-readable report. -/
def renderReport (results : List RuleResult) : String :=
  let (passed, failed) := results.partition (·.passed)
  let header := if failed.isEmpty then "✅ Eligible: All applicable rules satisfied\n"
                else "❌ Not Eligible: some rules failed\n"
  let showOne (r : RuleResult) : String :=
    if r.passed then
      s!"✅ {r.id} — {r.title}"
    else
      s!"❌ {r.id} — {r.title}\nReason: {r.reason?.getD "(no detail)"}\nRef: {r.reference}"
  header ++
  "\n— Failed —\n" ++ (if failed.isEmpty then "(none)\n" else String.intercalate "\n\n" (failed.map showOne)) ++
  "\n\n— Passed —\n" ++ (if passed.isEmpty then "(none)\n" else String.intercalate "\n" (passed.map showOne))

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
      IO.eprintln "Usage:\n  compliance --in <file> [--out <file>]\n  (or) echo '{Issuer JSON}' | compliance"

end Src.Main_v2

open Src.Main_v2

def main (args : List String) : IO Unit :=
  Src.Main_v2.main args

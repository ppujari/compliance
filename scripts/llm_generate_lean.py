#!/usr/bin/env python3
# scripts/llm_generate_lean.py
"""
Generate Lean 4 ruleset (ComplianceRule list) from LLM-extracted JSONL rules.

Inputs:
- JSONL file with items like those produced by scripts/llm_extract_rules.py

Behavior:
- Reads JSONL items
- Sends batched instructions to a local LLM (Ollama) with few-shot examples
- Asks model to output a single Lean code block for the batch
- Extracts the Lean block and writes/merges to a target Lean file

Assumptions:
- You have a local Ollama server running (http://localhost:11434)
- The Lean types Issuer and ComplianceRule are defined in Main.lean
- The generated file imports Main and defines `namespace GeneratedRules` with `def generatedRuleset : List ComplianceRule := [...]`

Usage:
  python3 scripts/llm_generate_lean.py \
    --in data/processed/rules_new.jsonl \
    --out GeneratedRules.lean \
    --model llama3:8b \
    --batch-size 30 --limit 0
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

import requests


DEFAULT_MODEL = "llama3:8b"


def read_jsonl(path: Path, limit: int = 0) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                items.append(obj)
            if limit and len(items) >= limit:
                break
    return items


def chunked(xs: List[Any], n: int) -> List[List[Any]]:
    if n <= 0:
        n = 1
    return [xs[i:i+n] for i in range(0, len(xs), n)]


def extract_lean_code_block(s: str) -> str:
    """Extract the first ```lean ... ``` block; fallback to first triple-backtick block."""
    m = re.search(r"```lean\n([\s\S]*?)```", s)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"```\n([\s\S]*?)```", s)
    if m2:
        return m2.group(1).strip()
    # No fenced block; return whole string
    return s.strip()

def read_fewshots_json(path: Path) -> List[Tuple[str, str]]:
    """
    Reads few-shot examples from JSON.
    Expect shape:
    {
      "examples": [
        {
          "items": [ {rule...}, ... ],
          "lean": "```lean\\n...\\n```" or raw Lean
        }, ...
      ]
    }
    Returns list of (items_json_str, lean_code_str)
    """
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    examples = raw.get("examples") if isinstance(raw, dict) else raw
    out: List[Tuple[str, str]] = []
    if not isinstance(examples, list):
        return out
    for ex in examples:
        if not isinstance(ex, dict):
            continue
        items = ex.get("items")
        lean = ex.get("lean")
        if not isinstance(items, list) or not isinstance(lean, str):
            continue
        items_json = json.dumps(items, ensure_ascii=False, indent=2)
        lean_block = extract_lean_code_block(lean)
        out.append((items_json, lean_block))
    return out


def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def extract_structure_block(src: str, struct_name: str) -> str:
    """Extract `structure <name> where` block (rough heuristic)."""
    # Find start
    m = re.search(rf"^structure\s+{re.escape(struct_name)}\s+where\s*$", src, flags=re.M)
    if not m:
        return ""
    start = m.start()
    # From start to next blank line followed by non-indented token or end
    tail = src[start:]
    # Stop at two consecutive newlines followed by a non-space or at another 'structure'
    stop_match = re.search(r"\n\n(?=\S)|\n(?=structure\s)", tail)
    if stop_match:
        end = stop_match.start()
        block = tail[:end]
    else:
        block = tail
    # To be safer, also cut at a deriving line if present
    d = re.search(r"\n\s*deriving\b.*$", block, flags=re.M)
    if d:
        block = block[:d.end()]
    return block.strip()


def extract_issuer_fields(struct_block: str) -> List[Tuple[str, str]]:
    """Return list of (field, type) from an Issuer structure block."""
    fields: List[Tuple[str, str]] = []
    for line in struct_block.splitlines():
        # Match indented field lines: two spaces then name : type
        m = re.match(r"^\s{2}([A-Za-z0-9_']+)\s*:\s*(.+?)\s*$", line)
        if m:
            fields.append((m.group(1), m.group(2)))
    return fields


def ollama_generate(model: str, prompt: str, timeout: int = 180, debug: bool = False, debug_raw: bool = False) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "prompt": prompt,
        "stream": False,
    }
    if debug:
        print("[DEBUG] calling Ollama /api/generate", file=sys.stderr)
        head_prompt = prompt[:300].replace("\n", " ")
        print(f"[DEBUG] prompt head[300]: {head_prompt}", file=sys.stderr)
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if debug_raw:
        try:
            print("[DEBUG-RAW] /api/generate HTTP JSON BEGIN", file=sys.stderr)
            print(json.dumps(data)[:2000], file=sys.stderr)
            print("[DEBUG-RAW] /api/generate HTTP JSON END", file=sys.stderr)
        except Exception:
            pass
    content = (data.get("response") or "").strip()
    if debug:
        head = content[:300].replace("\n", " ")
        print(f"[DEBUG] /api/generate raw head[300]: {head}", file=sys.stderr)
    return content


def ollama_chat(model: str, system: str, user: str, timeout: int = 180, debug: bool = False, debug_raw: bool = False) -> str:
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "options": {"temperature": 0.1, "top_p": 0.9},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    if debug:
        print("[DEBUG] calling Ollama /api/chat", file=sys.stderr)
        head_user = user[:300].replace("\n", " ")
        print(f"[DEBUG] user head[300]: {head_user}", file=sys.stderr)
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
    except requests.HTTPError as http_err:
        if http_err.response is not None and http_err.response.status_code == 404:
            # Fallback to generate endpoint with a combined prompt
            if debug:
                print("[DEBUG] /api/chat 404 → fallback to /api/generate", file=sys.stderr)
            combined = f"System:\n{system}\n\nUser:\n{user}\n"
            return ollama_generate(model, combined, timeout=timeout, debug=debug, debug_raw=debug_raw)
        raise
    except (requests.ReadTimeout, requests.ConnectionError) as e:
        # Treat timeouts/connection errors similar to chat unavailability in auto mode (handled by caller)
        raise
    data = r.json()
    if debug_raw:
        try:
            print("[DEBUG-RAW] /api/chat HTTP JSON BEGIN", file=sys.stderr)
            print(json.dumps(data)[:2000], file=sys.stderr)
            print("[DEBUG-RAW] /api/chat HTTP JSON END", file=sys.stderr)
        except Exception:
            pass
    content = (data.get("message", {}) or {}).get("content", "")
    if debug:
        head = content[:300].replace("\n", " ")
        print(f"[DEBUG] /api/chat raw head[300]: {head}", file=sys.stderr)
    return content


def build_system_prompt(repo_root: Path) -> str:
    # Dynamically read Main.lean to stay in sync with evolving schema
    main_path = repo_root / "Main.lean"
    main_src = read_text_safe(main_path)
    issuer_block = extract_structure_block(main_src, "Issuer")
    rule_block = extract_structure_block(main_src, "ComplianceRule")
    issuer_fields = extract_issuer_fields(issuer_block) if issuer_block else []

    # Fallbacks (minimal) if extraction fails
    if not issuer_block:
        issuer_block = "structure Issuer where\n  -- (fields elided; use only fields listed in AVAILABLE_FIELDS)"
    if not rule_block:
        rule_block = (
            "structure ComplianceRule where\n"
            "  id         : String\n"
            "  title      : String\n"
            "  reference  : String\n"
            "  check      : Issuer → Bool\n"
            "  failReason : Issuer → String\n"
            "  remedy?    : Option String\n"
        )

    available_fields = ", ".join([f"{name}:{typ}" for name, typ in issuer_fields]) or "(could not parse; do not invent fields)"

    example_rule = (
        "{ id := \"SEBI ICDR 6(1)(b)\",\n"
        "  title := \"Operating profit: ≥ ₹15 cr in each of the last 3 years\",\n"
        "  reference := \"ICDR 6(1)(b)\",\n"
        "  check := fun i => (i.operating_profits.length == 3) && i.operating_profits.all (fun x => x ≥ 150000000),\n"
        "  failReason := fun i =>\n"
        "    if (i.operating_profits.length != 3) then \"Need 3 full-year operating profit figures.\" else\n"
        "    let fails := (List.zip (List.range i.operating_profits.length) i.operating_profits).filter (fun p => p.snd < 150000000);\n"
        "    let years := fails.map (fun p => s!\"Year {p.fst + 1}\");\n"
        "    \"Operating profit below ₹15 cr in: \" ++ String.intercalate \", \" years,\n"
        "  remedy? := some \"Demonstrate ≥ ₹15 cr operating profit in each of the last 3 full financial years (restated, consolidated).\" }\n"
    )

    return (
        "You are to synthesize Lean 4 code implementing machine-checkable compliance rules.\n"
        "The Lean project defines `Issuer` and `ComplianceRule` as below (extracted live). Generate code compatible with these.\n\n"
        "[Issuer]\n" + issuer_block + "\n\n[ComplianceRule]\n" + rule_block + "\n\n"
        f"AVAILABLE_FIELDS (Issuer): {available_fields}\n\n"
        "Constraints:\n"
        "- Import Main and use its definitions (Issuer, ComplianceRule).\n"
        "- Implement each rule item as a `ComplianceRule` literal using only AVAILABLE_FIELDS. Do NOT invent new fields.\n"
        "- Use simple pure checks (no IO).\n"
        "- Title should be short; reference can be the regulation if provided.\n"
        "- Fail reason should be concise and data-driven.\n"
        "- Where JSON `notes` mention specific Issuer fields, prefer those if present in AVAILABLE_FIELDS; otherwise craft a conservative predicate that compiles (e.g., `fun _ => True`) and set a failReason explaining missing data.\n"
        "- Use integer paise values for rupee thresholds as per examples.\n"
        "- Output exactly ONE Lean code block for the entire batch.\n"
        "- The file must define:\n"
        "    import Main\n"
        "    open Main\n"
        "    namespace GeneratedRules\n"
        "    def generatedRulesetChunk : List ComplianceRule := [ ... ]\n"
        "    -- Additionally output the issuerQuestionsChunk that enumerates input prompts for Issuer fields used by these rules.\n"
        "    -- Each entry is (fieldName, question, typeString) where typeString matches the Lean type (e.g., \"Bool\", \"Nat\", \"List Nat\").\n"
        "    def issuerQuestionsChunk : List (String × String × String) := [ ... ]\n"
        "    end GeneratedRules\n\n"
        "Example (style only):\n"
        "```lean\nimport Main\nopen Main\nnamespace GeneratedRules\n/-- example style for one rule -/\n#eval (Nat.succ 0)\n-- Example ComplianceRule expression:\n" + example_rule + "\nend GeneratedRules\n```\n"
    )


def build_user_prompt(batch_items: List[Dict[str, Any]], target_module_name: str = "GeneratedRules") -> str:
    # Provide a compact JSON the model can use to synthesize rules
    compact = []
    for it in batch_items:
        compact.append({
            "rule_id": it.get("rule_id"),
            "title": it.get("title"),
            "text": it.get("text"),
            "lean_id": it.get("lean_id"),
            "notes": it.get("notes"),
            "reference": (it.get("source") or {}).get("reg") or it.get("rule_id") or "",
        })
    items_json = json.dumps(compact, ensure_ascii=False, indent=2)

    return (
        "Synthesize Lean 4 code for these items as one file.\n"
        "Return only one fenced Lean block.\n\n"
        f"ITEMS (JSON):\n{items_json}\n\n"
        "Write Lean: import Main; open Main; namespace GeneratedRules;\n"
        "Define:\n"
        "  def generatedRulesetChunk : List ComplianceRule := [ <one ComplianceRule per item> ]\n"
        "  def issuerQuestionsChunk : List (String × String × String) := [ <one (field, question, type) per Issuer field used> ]\n"
        "Use clear, deterministic checks per `notes` and `text`.\n"
        "If mapping is ambiguous, provide a conservative predicate and a clear failReason.\n"
        "For issuerQuestionsChunk:\n"
        "- Include only fields referenced by your generated checks.\n"
        "- Question should be concise and answerable to populate the field; avoid legalese.\n"
        "- type must match the Lean type of the field (e.g., Bool, Nat, List Nat).\n"
    )


def merge_chunks_to_file(chunks: List[str], out_path: Path) -> None:
    # Compose final Lean file with all chunks under same namespace
    header = (
        "import Main\nopen Main\nnamespace GeneratedRules\n\n"
    )
    footer = "\nend GeneratedRules\n"

    body_rules: List[str] = []
    body_questions: List[str] = []
    for idx, chunk in enumerate(chunks):
        # Extract the list literal from the chunk or keep as-is
        # Try to capture the list inside `def generatedRulesetChunk : List ComplianceRule := [ ... ]`
        m = re.search(r"def\s+generatedRulesetChunk\s*:\s*List\s+ComplianceRule\s*:=\s*\[(.*)\]", chunk, flags=re.S)
        if m:
            inner = m.group(1).strip()
            if inner:
                body_rules.append(inner)
        # Extract issuerQuestionsChunk
        mq = re.search(r"def\s+issuerQuestionsChunk\s*:\s*List\s*\(\s*String\s*×\s*String\s*×\s*String\s*\)\s*:=\s*\[(.*)\]", chunk, flags=re.S)
        if mq:
            innerq = mq.group(1).strip()
            if innerq:
                body_questions.append(innerq)

    # Join rules with commas
    joined_rules = ",\n\n".join([s for s in body_rules if s])
    joined_questions = ",\n".join([s for s in body_questions if s])

    final_content = header
    final_content += "def generatedRuleset : List ComplianceRule := [\n" + joined_rules + "\n]\n\n"
    final_content += "def issuerQuestions : List (String × String × String) := [\n" + joined_questions + "\n]\n"
    final_content += footer

    out_path.write_text(final_content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/processed/rules_new.jsonl")
    ap.add_argument("--out", dest="outp", default="GeneratedRules.lean")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch-size", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0, help="max number of rules to process (0 = all)")
    ap.add_argument("--sleep", type=float, default=0.1)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--debug-raw", action="store_true")
    ap.add_argument("--progress", action="store_true", help="print per-batch progress")
    ap.add_argument("--echo-chunks", action="store_true", help="print each Lean chunk to stdout")
    ap.add_argument("--echo-chars", type=int, default=0, help="if >0, truncate echoed chunks to this many chars")
    ap.add_argument("--endpoint", choices=["auto","chat","generate"], default="auto", help="LLM endpoint mode")
    ap.add_argument("--timeout", type=int, default=300, help="HTTP timeout seconds per request")
    ap.add_argument("--fewshot", type=str, default="", help="Path to few-shot JSON for Lean generation")
    ap.add_argument("--json-out", type=str, default="", help="Optional path to also write extracted JSON (rules + issuer questions + issuer schema)")
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.outp)
    outp.parent.mkdir(parents=True, exist_ok=True)

    items = read_jsonl(inp, limit=args.limit)
    if not items:
        print(f"No items found in {inp}", file=sys.stderr)
        sys.exit(1)

    # Determine repo root (parent of scripts/)
    repo_root = Path(__file__).resolve().parents[1]
    system = build_system_prompt(repo_root)
    chunks_out: List[str] = []
    total_rules = len(items)
    batches = list(chunked(items, args.batch_size))
    num_batches = len(batches)

    fewshots: List[Tuple[str, str]] = []
    if args.fewshot:
        fewshots = read_fewshots_json(Path(args.fewshot))

    for idx, batch in enumerate(batches):
        if args.progress:
            sample_ids = [str(it.get("rule_id", "?")) for it in batch[:5]]
            sample = ", ".join(sample_ids) + (" …" if len(batch) > 5 else "")
            print(f"[{idx+1}/{num_batches}] Synthesizing {len(batch)} rules: {sample}", file=sys.stderr)
        # Build user prompt, optionally prepending few-shot examples
        user = ""
        if fewshots:
            for i, (ex_items_json, ex_lean) in enumerate(fewshots):
                user += f"FEW-SHOT EXAMPLE {i+1} INPUT (JSON):\n{ex_items_json}\n\n"
                user += "FEW-SHOT EXAMPLE OUTPUT (Lean):\n```lean\n" + ex_lean + "\n```\n\n"
        user += build_user_prompt(batch)
        content = ""
        try:
            if args.endpoint == "chat":
                content = ollama_chat(args.model, system, user, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw)
            elif args.endpoint == "generate":
                combined = f"System:\n{system}\n\nUser:\n{user}\n"
                content = ollama_generate(args.model, combined, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw)
            else:  # auto
                try:
                    content = ollama_chat(args.model, system, user, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw)
                except (requests.ReadTimeout, requests.ConnectionError, requests.HTTPError) as e:
                    if args.debug:
                        print(f"[DEBUG] chat failed ({type(e).__name__}) → trying /api/generate", file=sys.stderr)
                    combined = f"System:\n{system}\n\nUser:\n{user}\n"
                    content = ollama_generate(args.model, combined, timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw)
        except Exception as e:
            print(f"[WARN] LLM call failed for a batch: {e}", file=sys.stderr)
            continue
        lean_block = extract_lean_code_block(content)
        if args.debug:
            head = lean_block[:400].replace("\n", " ")
            print(f"[DEBUG] Extracted Lean block head: {head}", file=sys.stderr)
        if args.echo_chunks and lean_block:
            out_txt = lean_block
            if args.echo_chars and args.echo_chars > 0 and len(out_txt) > args.echo_chars:
                out_txt = out_txt[:args.echo_chars] + "\n-- [truncated]"
            print(f"----- BEGIN CHUNK {idx+1}/{num_batches} -----")
            print(out_txt)
            print(f"----- END CHUNK {idx+1}/{num_batches} -----")
        if lean_block:
            chunks_out.append(lean_block)
        time.sleep(args.sleep)

    if not chunks_out:
        print("No Lean content generated.", file=sys.stderr)
        sys.exit(2)

    merge_chunks_to_file(chunks_out, outp)
    print(f"✅ Processed {total_rules} rule items in {num_batches} batches; wrote Lean ruleset → {outp}")

    # Optional: also emit JSON extraction from Lean + Main.lean
    if args.json_out:
        try:
            from scripts.extract_lean_to_json import extract_to_json  # type: ignore
        except Exception:
            # Try relative import if running as module-less
            try:
                import importlib.util, sys as _sys
                _p = Path(__file__).resolve().parents[1] / "scripts" / "extract_lean_to_json.py"
                spec = importlib.util.spec_from_file_location("extract_lean_to_json", _p.as_posix())
                mod = importlib.util.module_from_spec(spec)  # type: ignore
                assert spec and spec.loader
                spec.loader.exec_module(mod)  # type: ignore
                extract_to_json = getattr(mod, "extract_to_json")
            except Exception as e:
                print(f"[WARN] Could not import extractor to write JSON: {e}", file=sys.stderr)
                return
        repo_root = Path(__file__).resolve().parents[1]
        main_path = (repo_root / "Main.lean").as_posix()
        data = extract_to_json(outp.as_posix(), main_path)
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Also wrote JSON extraction → {args.json_out}")


if __name__ == "__main__":
    main()



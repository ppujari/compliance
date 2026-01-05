#!/usr/bin/env python3
# scripts/verify_one.py
from __future__ import annotations

import argparse
import subprocess
import sys
import json
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    try:
        subprocess.run(cmd, check=True, cwd=cwd.as_posix())
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"[ERROR] Command failed ({e.returncode}): {' '.join(cmd)}")

def run_capture(cmd: list[str], cwd: Path, timeout: int = 120) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd.as_posix(), check=False, capture_output=True, text=True, timeout=timeout)
        # We don't treat non-zero as fatal here because the Lean exe prints Usage and returns 0
        return r.stdout or ""
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""

def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Lean files (optional), build with Lake, and run verifier.")
    ap.add_argument("--tag", required=True, help="Rules tag, e.g., gpt_oss_v1 or qwen2_32b_v4")
    ap.add_argument("--issuer", required=True, help="Path to issuer JSON to verify")
    ap.add_argument("--out", required=True, help="Path to write results JSON")
    ap.add_argument("--schema", default="data/schema/issuer_schema.json", help="Issuer schema JSON to generate core (optional; can also pass combined file via --rules-fields)")
    ap.add_argument("--rules-jsonl", default="", help="Rules JSONL; if given and no --lean-in, will synthesize Lean via llm_generate_lean.py")
    ap.add_argument("--rules-fields", default="", help="Combined rules_and_fields_<tag>.json; used for BOTH core gen and rules gen when provided")
    ap.add_argument("--lean-in", default="", help="Lean rules input file (produced by your LLM pipeline); optional if --rules-jsonl is given")
    ap.add_argument("--core-module", default="Src.Core_auto", help="Target core module name for main generation")
    ap.add_argument("--core-out", default="Src/Core_auto.lean", help="Output Lean path for core generation")
    ap.add_argument("--no-core-gen", action="store_true", help="Do not generate Core_auto even if --schema/--rules-fields provided")
    ap.add_argument("--skip-gen", action="store_true", help="Skip generation; only build and run")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    scripts = repo_root / "scripts"

    rules_module = f"Src.GeneratedRules_{args.tag}"
    rules_out = repo_root / f"Src/GeneratedRules_{args.tag}.lean"

    if not args.skip_gen:
        # 1) Generate Core (from schema)
        core_source = args.rules_fields if args.rules_fields else args.schema
        # Skip core generation if explicitly disabled or when using a non-auto core module
        if (not args.no_core_gen) and args.core_module == "Src.Core_auto" and core_source:
            run([sys.executable, (scripts / "gen_core_from_issuer_schema.py").as_posix(),
                 "--schema", core_source,
                 "--out", args.core_out,
                 "--namespace", args.core_module],
                repo_root)
        # 2) Generate Rules (wrap LLM output or synthesize)
        gen_rules_cmd = [sys.executable, (scripts / "gen_rules_lean.py").as_posix(),
                         "--tag", args.tag,
                         "--core", args.core_module,
                         "--out", rules_out.as_posix()]
        if args.lean_in:
            gen_rules_cmd += ["--lean_in", args.lean_in]
        elif args.rules_fields:
            gen_rules_cmd += ["--rules_fields", args.rules_fields]
        elif args.rules_jsonl:
            gen_rules_cmd += ["--rules", args.rules_jsonl]
        else:
            print("[WARN] No --lean-in or --rules-jsonl provided; skipping rules generation step.", file=sys.stderr)
        run(gen_rules_cmd, repo_root)
        # 3) Generate Main (overwrite the Lake root Main_v2.lean)
        run([sys.executable, (scripts / "gen_main_lean.py").as_posix(),
             "--core", args.core_module,
             "--rules", rules_module,
             "--out", "Src/Main_v2.lean"],
            repo_root)

    # 4) Build and run
    run(["lake", "build"], repo_root)
    # Ensure output directory exists
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    # Normalize issuer JSON: accept wrapper { "issuer_id": ..., "fields": { ... } }
    issuer_in = Path(args.issuer)
    if not issuer_in.is_absolute():
        issuer_in = (repo_root / issuer_in).resolve()
    issuer_for_lean = issuer_in
    try:
        raw_txt = issuer_in.read_text(encoding="utf-8")
        obj = json.loads(raw_txt)
        if isinstance(obj, dict) and isinstance(obj.get("fields"), dict):
            normalized = obj["fields"]
            tmp = repo_root / ".tmp_issuer_for_lean.json"
            tmp.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
            issuer_for_lean = tmp
    except Exception:
        pass

    # Remove any stale output file to avoid false positives
    try:
        if out_path.exists():
            out_path.unlink()
    except Exception:
        pass

    run(["lake", "exe", "compliance", "--", "--in", issuer_for_lean.as_posix(), "--out", out_path.as_posix()], repo_root)
    # Wait briefly for file to appear (handles async write timing on some systems)
    import time
    for _ in range(20):
        if out_path.exists():
            break
        time.sleep(0.1)
    # Fallback: if file not present or empty, capture stdout and write it
    if (not out_path.exists()) or (out_path.exists() and out_path.stat().st_size == 0):
        stdout_json = run_capture(["lake", "exe", "compliance", "--", "--in", issuer_for_lean.as_posix()], repo_root)
        try:
            # Validate JSON minimally before writing
            if stdout_json.strip():
                json.loads(stdout_json)
                out_path.write_text(stdout_json, encoding="utf-8")
        except Exception:
            pass

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"✅ Verification complete. Wrote report → {out_path}")
    else:
        print(f"[WARN] Report not created at {out_path}. Please check input JSON and usage. You can also redirect stdout: `lake exe compliance -- --in {issuer_for_lean.as_posix()} > {out_path.as_posix()}`", file=sys.stderr)


if __name__ == "__main__":
    main()



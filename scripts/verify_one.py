#!/usr/bin/env python3
# scripts/verify_one.py
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# ── Direct imports: no subprocess spawning for Lean generation ───────────────
try:
    from scripts.gen_core_from_issuer_schema import generate as gen_core  # type: ignore[import-not-found]
    from scripts.gen_rules_lean import generate as gen_rules               # type: ignore[import-not-found]
    from scripts.gen_main_lean import generate as gen_main                 # type: ignore[import-not-found]
except ImportError:
    from gen_core_from_issuer_schema import generate as gen_core           # type: ignore
    from gen_rules_lean import generate as gen_rules                       # type: ignore
    from gen_main_lean import generate as gen_main                         # type: ignore


def run(cmd: list[str], cwd: Path) -> None:
    """Run a shell command and raise SystemExit on failure."""
    try:
        subprocess.run(cmd, check=True, cwd=cwd.as_posix())
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"[ERROR] Command failed ({e.returncode}): {' '.join(cmd)}")


def run_capture(cmd: list[str], cwd: Path, timeout: int = 180) -> str:
    """Run a command and capture its stdout; non-zero exit is not fatal."""
    try:
        r = subprocess.run(
            cmd, cwd=cwd.as_posix(),
            check=False, capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout or ""
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate Lean files (optional), build with Lake, and run the compliance verifier."
    )
    ap.add_argument("--tag",         required=True,  help="Rules tag, e.g., judged_v2")
    ap.add_argument("--issuer",      required=True,  help="Path to flat issuer JSON to verify")
    ap.add_argument("--out",         required=True,  help="Path to write compliance report JSON")
    ap.add_argument("--schema",      default="data/schema/issuer_schema.json",
                    help="Issuer schema JSON (used when --rules-fields is not provided)")
    ap.add_argument("--rules-jsonl", default="",
                    help="Rules JSONL; when given and --lean-in is absent, synthesise Lean via llm_generate_lean.py")
    ap.add_argument("--rules-fields", default="",
                    help="Combined rules_and_fields_<tag>.json; used for both core gen and rules gen when provided")
    ap.add_argument("--lean-in",     default="",
                    help="Raw LLM-generated .lean file; used when --rules-fields is absent")
    ap.add_argument("--core-module", default="Src.Core_auto",
                    help="Target core module name (default: Src.Core_auto)")
    ap.add_argument("--core-out",    default="Src/Core_auto.lean",
                    help="Output path for the generated core Lean file")
    ap.add_argument("--no-core-gen", action="store_true",
                    help="Skip Core generation even if --schema / --rules-fields is provided")
    ap.add_argument("--skip-gen",    action="store_true",
                    help="Skip ALL generation steps; only build and run verification")
    args = ap.parse_args()

    repo_root  = Path(__file__).resolve().parents[1]
    rules_module = f"Src.GeneratedRules_{args.tag}"
    rules_out    = repo_root / f"Src/GeneratedRules_{args.tag}.lean"

    # ── Generation phase (direct function calls, no subprocesses) ────────────
    if not args.skip_gen:
        core_source = args.rules_fields or args.schema

        # 1) Generate Core (Issuer + ComplianceRule structs)
        if (not args.no_core_gen) and args.core_module == "Src.Core_auto" and core_source:
            gen_core(
                schema_path=core_source,
                out_path=args.core_out,
                namespace=args.core_module,
            )

        # 2) Generate Rules module
        if args.rules_fields:
            gen_rules(
                rules_fields_path=args.rules_fields,
                core=args.core_module,
                tag=args.tag,
                out_path=rules_out.as_posix(),
            )
        elif args.lean_in:
            gen_rules(
                lean_in_path=args.lean_in,
                core=args.core_module,
                tag=args.tag,
                out_path=rules_out.as_posix(),
            )
        else:
            print(
                "[WARN] No --rules-fields or --lean-in provided; skipping Rules generation.",
                file=sys.stderr,
            )

        # 3) Generate Main entrypoint
        gen_main(
            core=args.core_module,
            rules=rules_module,
            out="Src/Main_v2.lean",
        )

    # ── Build phase ───────────────────────────────────────────────────────────
    run(["lake", "build"], repo_root)

    # ── Verification phase ────────────────────────────────────────────────────
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalise issuer JSON: unwrap { issuer_id, fields: {...} } wrappers
    issuer_in = Path(args.issuer)
    if not issuer_in.is_absolute():
        issuer_in = (repo_root / issuer_in).resolve()
    issuer_for_lean = issuer_in
    try:
        obj = json.loads(issuer_in.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and isinstance(obj.get("fields"), dict):
            tmp = repo_root / ".tmp_issuer_for_lean.json"
            tmp.write_text(json.dumps(obj["fields"], ensure_ascii=False), encoding="utf-8")
            issuer_for_lean = tmp
    except Exception:
        pass

    # Remove stale output to avoid false positives
    try:
        if out_path.exists():
            out_path.unlink()
    except Exception:
        pass

    # Note: do NOT use '--' separator; lake passes remaining args directly to the exe.
    stdout_json = run_capture(
        ["lake", "exe", "compliance",
         "--in",  issuer_for_lean.as_posix(),
         "--out", out_path.as_posix()],
        repo_root,
        timeout=180,
    )

    # Brief wait for file-system flush
    for _ in range(20):
        if out_path.exists():
            break
        time.sleep(0.1)

    # Fallback: write from stdout if --out was not honoured (e.g. path-with-spaces issue)
    if not out_path.exists() or out_path.stat().st_size == 0:
        if not stdout_json.strip():
            stdout_json = run_capture(
                ["lake", "exe", "compliance", "--in", issuer_for_lean.as_posix()],
                repo_root,
                timeout=180,
            )
        try:
            if stdout_json.strip():
                json.loads(stdout_json)          # validate before writing
                out_path.write_text(stdout_json, encoding="utf-8")
        except Exception:
            pass

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[DONE] Verification complete. Wrote report -> {out_path}")
    else:
        print(
            f"[WARN] Report not created at {out_path}. "
            f"Check input JSON and usage. You can also run:\n"
            f"  lake exe compliance --in {issuer_for_lean.as_posix()} > {out_path.as_posix()}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()

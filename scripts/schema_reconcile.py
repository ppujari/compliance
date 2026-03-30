#!/usr/bin/env python3
"""
schema_reconcile.py

Pipeline:
1) Build provisional schema from rules+maps_to with conservative types.
2) Run rule-anchored extraction on RHP to collect evidence records.
3) Deterministically infer final types from evidence.
4) Optionally use LLM judge on ambiguous fields.
5) Emit outputs to --out-dir.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from scripts import rule_anchored_extract as rae  # type: ignore[import-not-found]
    from scripts import type_infer as tinfer  # type: ignore[import-not-found]
    from scripts import pdf_tables as ptables  # type: ignore[import-not-found]
    from scripts.utils import read_jsonl, extract_first_json_block  # type: ignore[import-not-found]
except Exception:
    import rule_anchored_extract as rae  # type: ignore
    import type_infer as tinfer  # type: ignore
    import pdf_tables as ptables  # type: ignore
    from utils import read_jsonl, extract_first_json_block  # type: ignore

import requests


ALLOWED_HINTS = {"Bool", "Nat", "List Nat", "String", "OptionBool", "OptionNat", "OptionListNat", "OptionString"}


def provisional_type(field: str, rule_text: str, type_hint: str | None) -> str:
    if type_hint and type_hint in ALLOWED_HINTS:
        # Still use conservative optional wrapper if hint is not in core set
        return type_hint
    lname = field.lower()
    combined = (rule_text or "").lower()
    if any(tok in lname for tok in ("has_", "is_", "no_", "uses_", "changed_")):
        return "Option Bool"
    if "preceding three years" in combined or "preceding three full years" in combined or lname.endswith("s"):
        return "Option (List Nat)"
    if any(tok in lname for tok in ("amount", "ratio", "percent", "pct", "number", "count")):
        return "Option Nat"
    return "Option String"


def build_provisional_schema(rules: List[dict]) -> Tuple[List[Dict[str, str]], Dict[str, List[str]]]:
    fields: Dict[str, str] = {}
    field_links: Dict[str, List[str]] = {}
    for r in rules:
        rule_id = r.get("rule_id") or r.get("id") or ""
        rule_text = r.get("text") or r.get("title") or ""
        maps_to = r.get("maps_to") if isinstance(r.get("maps_to"), list) else []
        for m in maps_to:
            if not isinstance(m, dict):
                continue
            field = (m.get("field") or "").strip()
            if not field:
                continue
            th = (m.get("type_hint") or "").strip()
            ptype = provisional_type(field, rule_text, th)
            if field not in fields:
                fields[field] = ptype
            field_links.setdefault(field, [])
            if rule_id and rule_id not in field_links[field]:
                field_links[field].append(rule_id)
    schema = [{"field": f, "type": t} for f, t in fields.items()]
    schema.sort(key=lambda x: x["field"])
    for k in field_links:
        field_links[k].sort()
    return schema, field_links


def ollama_judge(model: str, payload: dict, timeout: int = 120) -> dict:
    url = "http://localhost:11434/api/generate"
    prompt = (
        "You are a type judge. Choose the final type for the field based on evidence.\n"
        "Return STRICT JSON only:\n"
        "{\"field\":\"...\",\"final_type\":\"Option (List Nat)\",\"confidence\":0.8,\"rationale\":\"...\"}\n\n"
        f"INPUT:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )
    r = requests.post(url, json={"model": model, "prompt": prompt, "stream": False, "format": "json"}, timeout=timeout)
    r.raise_for_status()
    resp = r.json().get("response") or ""
    block = rae.extract_first_json_block(resp)
    if not block:
        return {}
    try:
        return json.loads(block)
    except Exception:
        return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    # Primary arg names
    ap.add_argument("--rules", dest="rules", default="")
    ap.add_argument("--rhp", dest="rhp", default="")
    # Documented aliases (used in run_flow.md)
    ap.add_argument("--rules-jsonl", dest="rules")
    ap.add_argument("--rhp-pdf", dest="rhp")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--issuer-schema", default="", help="Optional pre-built issuer schema JSON to merge into provisional schema")
    ap.add_argument("--extract-model", default="mistral:7b-instruct")
    ap.add_argument("--judge-model", default="qwen2.5:32b-instruct")
    ap.add_argument("--max-rules", type=int, default=0)
    ap.add_argument("--use-llm-judge", type=str, default="false")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    if not args.rules:
        ap.error("--rules / --rules-jsonl is required")
    if not args.rhp:
        ap.error("--rhp / --rhp-pdf is required")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rules = read_jsonl(Path(args.rules))
    provisional_schema, field_links = build_provisional_schema(rules)

    # If an external issuer schema is supplied, merge its types into the provisional schema as overrides
    if args.issuer_schema and Path(args.issuer_schema).exists():
        try:
            ext = json.loads(Path(args.issuer_schema).read_text(encoding="utf-8"))
            if isinstance(ext, list):
                ext_map = {e["field"]: e["type"] for e in ext if isinstance(e, dict) and e.get("field")}
            elif isinstance(ext, dict) and "issuer_schema" in ext:
                ext_map = {e["field"]: e["type"] for e in ext["issuer_schema"] if isinstance(e, dict) and e.get("field")}
            else:
                ext_map = {}
            for s in provisional_schema:
                if s["field"] in ext_map:
                    s["type"] = ext_map[s["field"]]
        except Exception as exc:
            print(f"[WARN] Could not load --issuer-schema: {exc}", file=__import__("sys").stderr)
    (out_dir / "provisional_schema.json").write_text(
        json.dumps(provisional_schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "field_rule_links.json").write_text(
        json.dumps(field_links, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    evidence_path = out_dir / "evidence_store.jsonl"
    tables_path = out_dir / "tables_store.json"
    # extract tables
    try:
        tables = ptables.extract_page_tables(Path(args.rhp))
        tables_path.write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        tables_path.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")

    # Run rule-anchored extraction directly (no argv mutation)
    rae.run_extraction(
        rules_path=Path(args.rules),
        rhp_path=Path(args.rhp),
        out_path=evidence_path,
        model=args.extract_model,
        endpoint="generate",
        topk=3,
        timeout=180,
        tables_store_path=tables_path,
        max_rules=args.max_rules,
        debug=args.debug,
    )

    # Run type inference directly (no argv mutation)
    infer_out = out_dir / "type_reconcile_report.json"
    provisional_map = {s["field"]: s["type"] for s in provisional_schema if isinstance(s, dict) and s.get("field")}
    tinfer.run_type_infer(
        evidence_path=evidence_path,
        out_path=infer_out,
        provisional_map=provisional_map,
    )

    # load inferred schema
    infer_obj = json.loads(infer_out.read_text(encoding="utf-8"))
    schema = infer_obj.get("issuer_schema") or []
    report = infer_obj.get("type_reconcile_report") or []

    use_judge = str(args.use_llm_judge).lower() in ("true", "1", "yes")
    if use_judge:
        # Only apply judge for ambiguous cases
        for row in report:
            if row.get("inactive_field"):
                continue
            metrics = row.get("metrics") or {}
            top = sorted(
                [
                    metrics.get("Bool_parse_rate", 0.0),
                    metrics.get("Nat_parse_rate", 0.0),
                    metrics.get("ListNat_parse_rate", 0.0),
                ],
                reverse=True,
            )
            if len(top) >= 2 and abs(top[0] - top[1]) <= 0.1:
                payload = {
                    "field": row.get("field"),
                    "provisional_type": row.get("provisional_type"),
                    "metrics": metrics,
                    "evidence_examples": row.get("evidence_examples"),
                }
                judge = ollama_judge(args.judge_model, payload, timeout=180)
                if isinstance(judge, dict) and judge.get("final_type"):
                    row["final_type"] = judge["final_type"]
                    row["judge"] = judge

        # update schema with judge decisions
        by_field = {s["field"]: s for s in schema if isinstance(s, dict)}
        for row in report:
            f = row.get("field")
            t = row.get("final_type")
            if f and t and f in by_field:
                by_field[f]["type"] = t
        schema = sorted(by_field.values(), key=lambda x: x["field"])

    # enforce allowed type set using provisional schema as fallback
    allowed = {
        "Bool",
        "Nat",
        "List Nat",
        "String",
        "Option Bool",
        "Option Nat",
        "Option (List Nat)",
        "Option String",
    }
    provisional_map = {s["field"]: s["type"] for s in provisional_schema if isinstance(s, dict) and s.get("field")}
    for s in schema:
        t = s.get("type")
        f = s.get("field")
        if t not in allowed:
            s["type"] = provisional_map.get(f) or "Option String"

    (out_dir / "issuer_schema_reconciled.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "type_reconcile_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # run_debug summary
    table_evidence_count = 0
    if evidence_path.exists():
        with evidence_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                ev = obj.get("evidence") or {}
                if str(ev.get("source") or "").startswith("table:"):
                    table_evidence_count += 1
    run_debug = {
        "tables_loaded": len(tables),
        "table_evidence_records": table_evidence_count,
    }
    (out_dir / "run_debug.json").write_text(
        json.dumps(run_debug, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # issuer_candidate aggregation
    evidence_records = read_jsonl(evidence_path) if evidence_path.exists() else []
    report_map = {r.get("field"): r for r in report if isinstance(r, dict)}
    candidates: Dict[str, Dict[str, Any]] = {}
    conflicts: Dict[str, List[Dict[str, Any]]] = {}

    def base_type(t: str) -> str:
        t = (t or "").strip()
        if t.startswith("Option "):
            inner = t[len("Option ") :].strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1].strip()
            return inner
        return t

    def pick_value(rec: dict, t: str) -> Any:
        vc = rec.get("value_candidates") or {}
        if t == "Bool":
            return vc.get("Bool")
        if t == "Nat":
            return vc.get("Nat")
        if t == "List Nat":
            return vc.get("List Nat")
        if t == "String":
            return rec.get("value_raw")
        return rec.get("value_raw")

    def src_priority(rec: dict) -> int:
        ev = rec.get("evidence") or {}
        src = str(ev.get("source") or "")
        return 0 if src.startswith("table:") else 1

    for rec in evidence_records:
        field = rec.get("field")
        if not field:
            continue
        rep = report_map.get(field) or {}
        final_type = rep.get("final_type") or "Option String"
        if rep.get("inactive_field"):
            final_type = "Option String"
        btype = base_type(final_type)
        val = pick_value(rec, btype)
        if val is None or val == "":
            continue
        cur = candidates.get(field)
        cand_entry = {
            "value": val,
            "final_type": final_type,
            "evidence": rec.get("evidence"),
            "rule_id": rec.get("rule_id"),
            "extract_confidence": rec.get("extract_confidence", 0.0),
            "source_priority": src_priority(rec),
        }
        if cur is None:
            candidates[field] = cand_entry
        else:
            # prefer table, then higher confidence
            if cand_entry["source_priority"] < cur["source_priority"]:
                candidates[field] = cand_entry
            elif cand_entry["source_priority"] == cur["source_priority"] and cand_entry["extract_confidence"] > cur["extract_confidence"]:
                candidates[field] = cand_entry
            elif cand_entry["value"] != cur["value"]:
                conflicts.setdefault(field, []).append(cand_entry)

    (out_dir / "issuer_candidate.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "issuer_candidate_conflicts.json").write_text(
        json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Wrote reconciliation outputs to {out_dir}")


if __name__ == "__main__":
    main()

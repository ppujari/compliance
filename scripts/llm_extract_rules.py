#!/usr/bin/env python3
# scripts/llm_extract_rules.py
"""
LLM-driven rule extractor for SEBI ICDR regulations.

Usage:
  python scripts/llm_extract_rules.py \
      --pdf data/input/SEBI_ICDR_2018.pdf \
      --out data/processed/rules_enriched.jsonl \
      --model qwen2.5:14b-instruct \
      --window 2 --overlap 1 \
      --judge --judge-model deepseek-r1:14b \
      --timeout 600 --debug
"""

from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict

from rule_extraction.pdf_loader import read_pdf_pages, windowed, strip_page_numbers
from rule_extraction.ollama_client import OllamaClient
from rule_extraction.regulation_identifier import (
    pre_identify_regulations, detect_allowed_regs, normalize_rule_identifier,
)
from rule_extraction.rule_extractor import (
    SYSTEM_PROMPT, load_fewshot_examples, flatten_subrules,
    extract_rules_two_pass, extract_rules_single_pass,
    normalize_clause_text, item_score, choose_best_item,
    MIN_TEXT_CHARS, TEXT_SIGNATURE_SLICE,
    FEWSHOT_INPUT, FEWSHOT_OUTPUT, FEWSHOT_BOOL_INPUT, FEWSHOT_BOOL_OUTPUT,
    BAD_EXPLANATION, deduplicate_field_names,
    build_judge_prompt, build_regen_prompt,
    JUDGE_SCHEMA, JUDGE_WEIGHTS, compute_overall_score,
)
from rule_extraction.rule_validator import (
    sanitize_for_schema, clamp_span_hint, validate_rule,
    validate_required_fields, validate_rule_id_format,
    validate_maps_to, validate_source, validate_reg_anchoring,
    override_list_nat_from_text,
    contains_span_hint, contains_span_hint_lenient, contains_span_hint_fuzzy,
)
from rule_extraction.metadata_enricher import (
    ICDRStructureLookup, enrich_batch,
)
from rule_extraction.rule_store import RuleStore

# Keep rule_refiner import as-is
try:
    from scripts.rule_refiner import RuleRefiner, OllamaClient as RefinerOllamaClient  # type: ignore[import-not-found]
except Exception:
    from rule_refiner import RuleRefiner, OllamaClient as RefinerOllamaClient


def main():
    ap = argparse.ArgumentParser(description="Extract regulatory rules from SEBI ICDR PDF")
    ap.add_argument("--pdf", required=True)
    ap.add_argument(
        "--out", default="data/processed/rules.jsonl",
        help="Output JSONL path. WARNING: opened in APPEND mode by default. "
             "Re-running on the same file without --dedupe will accumulate duplicates. "
             "Use --append to opt into append mode explicitly; omit it to overwrite.",
    )
    ap.add_argument("--append", action="store_true", help="Append to --out instead of overwriting (default: overwrite)")
    ap.add_argument("--model", default="qwen2.5:14b-instruct")
    ap.add_argument("--window", type=int, default=2, help="pages per window")
    ap.add_argument("--overlap", type=int, default=1, help="overlap pages between windows")
    ap.add_argument("--max-pages", type=int, default=0, help="limit total pages (0 = all)")
    ap.add_argument("--reg-filter", nargs=2, type=int, default=None, metavar=("START", "END"),
                    help="Keep only rules whose rule_id mentions regulations in [START..END]")
    ap.add_argument("--dedupe", action="store_true")
    ap.add_argument("--debug-raw", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--endpoint", choices=["auto", "chat", "generate"], default="auto",
                    help="Which Ollama endpoint to use (default auto: chat->generate fallback)")
    ap.add_argument("--no-format", action="store_true",
                    help="Do not set format=json; rely on prompt to request JSON")
    ap.add_argument("--fewshot", type=str, default=None,
                    help="Path to JSON file with few-shot examples")
    ap.add_argument("--timeout", type=int, default=120,
                    help="HTTP timeout (seconds) per model call")
    ap.add_argument("--span-mode", choices=["strict", "lenient"], default="lenient",
                    help="Span hint verification mode")
    ap.add_argument("--no-anchoring", action="store_true",
                    help="Disable regulation anchoring")
    ap.add_argument("--judge", action="store_true", help="Enable critic/judge loop with selective regeneration.")
    ap.add_argument("--judge-model", default="", help="Ollama model to use for judging.")
    ap.add_argument("--regen-rounds", type=int, default=2, help="Max regeneration rounds per window.")
    ap.add_argument("--max-regen-per-window", type=int, default=8, help="Max rules to regenerate per window.")
    ap.add_argument("--judge-overall-threshold", type=float, default=0.75)
    ap.add_argument("--judge-fidelity-threshold", type=float, default=0.70)
    ap.add_argument("--judge-report-out", type=str, default="", help="Optional JSONL path to write judge reports.")
    ap.add_argument(
        "--no-two-pass", action="store_true",
        help="Disable two-pass extraction and use legacy single-pass mode.",
    )
    # New arguments for metadata enrichment
    ap.add_argument("--regulation-framework", default="SEBI_ICDR_2018",
                    help="Regulation framework identifier (default: SEBI_ICDR_2018)")
    ap.add_argument("--jurisdiction", default="IN",
                    help="ISO country code (default: IN for India)")
    ap.add_argument("--structure-json", default="data/schema/icdr_structure.json",
                    help="Path to ICDR structure lookup JSON")
    ap.add_argument("--no-enrich", action="store_true",
                    help="Skip metadata enrichment (output raw rules only)")
    # Phase 11: debug intermediate outputs
    ap.add_argument(
        "--debug-dir", type=str, default="",
        help="Directory to write intermediate debug artifacts. "
             "Creates pass1_inventory.jsonl, pass2_pre_judge.jsonl, and "
             "coverage_summary.json. Empty string (default) disables."
    )
    args = ap.parse_args()

    pdf = Path(args.pdf)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Setup client
    client = OllamaClient(timeout=args.timeout)

    # Phase 11: clear debug files at start
    if args.debug_dir:
        debug_dir = Path(args.debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["pass1_inventory.jsonl", "pass2_pre_judge.jsonl"]:
            fpath = debug_dir / fname
            if fpath.exists():
                fpath.write_text("", encoding="utf-8")

    # Load existing for dedupe
    existing_rule_ids = set()
    if args.dedupe and out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    existing_rule_ids.add(json.loads(line)["rule_id"])
                except Exception:
                    pass

    pages = read_pdf_pages(pdf)
    if args.max_pages and args.max_pages > 0:
        pages = pages[:args.max_pages]

    # Structure lookup for metadata enrichment
    structure_lookup = None
    if not args.no_enrich:
        structure_path = Path(args.structure_json)
        if structure_path.exists():
            structure_lookup = ICDRStructureLookup(structure_path)
        else:
            print(f"[WARN] Structure file not found: {structure_path}; skipping enrichment", file=sys.stderr)

    selected_items: dict[str, dict] = {}
    item_order: list[str] = []
    signature_to_key: dict[str, str] = {}
    prev_visible_regs: set[str] = set()  # carry forward from previous window

    for start_idx, chunk in windowed(pages, args.window, args.overlap):
        chunk_cleaned = [strip_page_numbers(p) for p in chunk]
        visible = "\n\n--- PAGE BREAK ---\n\n".join(chunk_cleaned)
        if args.debug:
            print(f"[DEBUG] window start={start_idx} chars={len(visible)}", file=sys.stderr)
            if len(visible.strip()) < 200:
                print("[WARN] window text is tiny; PDF text extraction likely failed for this window", file=sys.stderr)
        page_nums = list(range(start_idx + 1, start_idx + 1 + len(chunk)))

        # Detect allowed regulations for anchoring
        allowed_regs = detect_allowed_regs(visible)

        # Pre-identify regulation numbers from document structure
        visible_regs: set[str] = set()
        for page_text in chunk_cleaned:
            visible_regs.update(pre_identify_regulations(page_text))

        # Carry forward previous window's regs so continuation pages (where a
        # regulation starts on page N but sub-clauses continue on page N+1
        # without a visible header) still get correct parent reg context.
        visible_regs_with_prev = visible_regs | prev_visible_regs

        # Build anchoring context for single-pass
        anchoring_context = ""
        if visible_regs_with_prev:
            reg_list = ", ".join(
                sorted(visible_regs_with_prev, key=lambda x: (int(re.match(r"\d+", x).group()), x))
            )
            anchoring_context = (
                f"REGULATION NUMBERS VISIBLE ON THESE PAGES: {reg_list}\n"
                f"Use ONLY these regulation numbers in your rule_id fields.\n"
                f"Do NOT use regulation numbers from adjacent pages.\n\n"
            )

        user = (
            anchoring_context
            + f"PDF: {pdf.name}\n"
            + f"PAGES: {page_nums}\n\n"
            + f"TEXT:\n{visible}\n\n"
            + "Extract atomic SEBI ICDR rules ONLY from these pages."
        )

        format_json = not args.no_format
        fewshots = load_fewshot_examples(args.fewshot)

        # ── Two-pass or single-pass extraction ──
        items: list[dict] = []
        reg_inventory: list[dict] = []
        if not args.no_two_pass:
            items = extract_rules_two_pass(
                client, args.model, visible, page_nums,
                visible_regs=visible_regs_with_prev,
                pdf_name=pdf.name,
                timeout=args.timeout, debug=args.debug,
            )
            # Capture reg_inventory for debug output
            if args.debug_dir:
                from rule_extraction.regulation_identifier import identify_regulations
                reg_inventory = identify_regulations(
                    client, args.model, visible, page_nums,
                    visible_regs=visible_regs_with_prev,
                    timeout=args.timeout, debug=False,
                ) if not items else []
                # Note: extract_rules_two_pass already called identify_regulations internally.
                # For debug, we re-use its results if items were produced.

            if not items:
                if args.debug:
                    print(f"[TwoPass] Pass 1 empty for pages={page_nums}; falling back to single-pass", file=sys.stderr)
                items = extract_rules_single_pass(
                    client, args.model, SYSTEM_PROMPT, user,
                    fewshots=fewshots,
                    timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw,
                    format_json=format_json, endpoint=args.endpoint,
                )
        else:
            items = extract_rules_single_pass(
                client, args.model, SYSTEM_PROMPT, user,
                fewshots=fewshots,
                timeout=args.timeout, debug=args.debug, debug_raw=args.debug_raw,
                format_json=format_json, endpoint=args.endpoint,
            )

        if not items:
            continue

        # Salvage: flatten common "subrules" shape
        flat_items: list[dict] = []
        for it in items:
            if isinstance(it, dict):
                flat_items.extend(flatten_subrules(it))
        if not flat_items and items:
            flat_items = [it for it in items if isinstance(it, dict)]

        # Phase 11: Write Pass 2 pre-judge output
        if args.debug_dir and flat_items:
            debug_dir = Path(args.debug_dir)
            debug_dir.mkdir(parents=True, exist_ok=True)
            with open(debug_dir / "pass2_pre_judge.jsonl", "a", encoding="utf-8") as f:
                for it in flat_items:
                    record = {
                        "window_start": start_idx,
                        "pages": page_nums,
                        "rule_id": it.get("rule_id"),
                        "title": it.get("title"),
                        "text": (it.get("text") or "")[:300],
                        "maps_to": it.get("maps_to", []),
                        "confidence": it.get("confidence"),
                        "source": it.get("source", {}),
                        "repair_notes": it.get("repair_notes", []),
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # --- Critic/Judge loop ---
        if args.judge and flat_items:
            judge_model = args.judge_model or args.model
            by_id: dict[str, dict] = {}
            for it in flat_items:
                if not isinstance(it, dict):
                    continue
                it.setdefault("domain", "SEBI_ICDR")
                if not isinstance(it.get("source"), dict):
                    it["source"] = {}
                it["source"].setdefault("pdf", pdf.name)
                it["source"].setdefault("pages", page_nums)
                clamp_span_hint(it)
                normalize_rule_identifier(it)
                rid = str(it.get("rule_id") or "").strip()
                if not rid:
                    continue
                prev = by_id.get(rid)
                by_id[rid] = it if prev is None else choose_best_item(prev, it)
            window_rules = [by_id[k] for k in sorted(by_id.keys())]

            # Deterministic validation (hard/soft)
            validation: dict[str, dict[str, List[str]]] = {}
            for r in window_rules:
                rid = str(r.get("rule_id") or "")
                hard: List[str] = []
                soft: List[str] = []
                hard.extend(validate_required_fields(r))
                if rid and not validate_rule_id_format(rid):
                    hard.append("bad_rule_id_format")
                soft.extend(validate_maps_to(r))
                hard.extend(validate_source(r, visible, span_mode=args.span_mode))
                # Bug fix: reg anchoring only runs here (removed from general loop to fix double penalty)
                anchoring_warnings = validate_reg_anchoring(r, visible_regs_with_prev)
                if anchoring_warnings:
                    soft.extend(anchoring_warnings)
                    try:
                        conf = float(r.get("confidence", 0.9))
                    except Exception:
                        conf = 0.9
                    r["confidence"] = max(0.0, round(conf - 0.2, 3))
                    r.setdefault("repair_notes", []).extend(anchoring_warnings)
                validation[rid] = {"hard_fail_reasons": sorted(set(hard)), "soft_fail_reasons": sorted(set(soft))}

            # Refine via RuleRefiner
            candidates = [sanitize_for_schema(r) for r in window_rules if not validation.get(str(r.get("rule_id") or ""), {}).get("hard_fail_reasons")]
            judge_report: Dict[str, Any] = {}
            judge_error: str | None = None
            if candidates:
                try:
                    refiner = RuleRefiner(
                        ollama=RefinerOllamaClient(timeout=args.timeout),
                        judge_model=judge_model,
                        gen_model=args.model,
                    )
                    refined, judge_report = refiner.refine_rules(
                        visible,
                        candidates,
                        max_iterations=max(0, int(args.regen_rounds)),
                        overall_th=float(args.judge_overall_threshold),
                        fidelity_min=float(args.judge_fidelity_threshold),
                        max_regen_per_window=max(0, int(args.max_regen_per_window)),
                    )
                    for rr in refined:
                        rid = str(rr.get("rule_id") or "").strip()
                        if rid:
                            by_id[rid] = rr
                except Exception as e:
                    judge_error = f"{type(e).__name__}: {e}"
                    if args.debug:
                        print(f"[WARN] RuleRefiner failed: {judge_error}", file=sys.stderr)

            # Quarantine hard-failing rules
            for rid, v in validation.items():
                if not v.get("hard_fail_reasons"):
                    continue
                if rid in by_id:
                    by_id[rid]["status"] = "quarantined"
                    by_id[rid]["maps_to"] = []
                    summary = f"[QUARANTINED] hard={v['hard_fail_reasons']} soft={v['soft_fail_reasons']}"
                    by_id[rid]["notes"] = (str(by_id[rid].get("notes") or "") + "\n" + summary).strip()

            # Optional judge report output
            if args.judge_report_out:
                try:
                    rec = {
                        "pdf": pdf.name,
                        "pages": page_nums,
                        "window_start": start_idx,
                        "validation": validation,
                        "judge_report": judge_report,
                        "judge_error": judge_error,
                    }
                    with open(args.judge_report_out, "a", encoding="utf-8") as jf:
                        jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except Exception:
                    pass

            if args.debug:
                try:
                    out_dir = Path("data/processed/judge_reports")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    safe_pdf = re.sub(r"[^A-Za-z0-9_.-]+", "_", pdf.name)
                    out_path = out_dir / f"{safe_pdf}_win{start_idx}_p{page_nums[0]}-{page_nums[-1]}.json"
                    out_path.write_text(
                        json.dumps(
                            {
                                "pdf": pdf.name,
                                "pages": page_nums,
                                "window_start": start_idx,
                                "validation": validation,
                                "judge_report": judge_report,
                                "judge_error": judge_error,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

            flat_items = [by_id[k] for k in sorted(by_id.keys())]

        for it in flat_items:
            # Guard: only process dict items
            if not isinstance(it, dict):
                if isinstance(it, str):
                    try:
                        maybe = json.loads(it)
                    except Exception:
                        continue
                    if not isinstance(maybe, dict):
                        continue
                    it = maybe
                else:
                    continue

            it.setdefault("domain", "SEBI_ICDR")
            if not isinstance(it.get("source"), dict):
                it["source"] = {}
            it["source"].setdefault("pdf", pdf.name)
            it["source"].setdefault("pages", page_nums)
            clamp_span_hint(it)

            reg_no = normalize_rule_identifier(it)
            if reg_no is None:
                if args.debug:
                    print("[DEBUG] dropping item without normalizable rule_id:", it.get("rule_id"), file=sys.stderr)
                continue

            # Soft reg-anchoring check — only for non-judge path (judge path already handled above)
            # Bug fix: removed double anchoring. Only run here if NOT in judge mode.
            if not args.judge and visible_regs_with_prev and not args.no_anchoring:
                from rule_extraction.rule_validator import validate_reg_anchoring as _vra
                anchoring_warns = _vra(it, visible_regs_with_prev)
                if anchoring_warns:
                    it.setdefault("repair_notes", []).extend(anchoring_warns)
                    try:
                        conf = float(it.get("confidence", 0.9))
                    except Exception:
                        conf = 0.9
                    it["confidence"] = max(0.0, round(conf - 0.2, 3))
                    if args.debug:
                        print(f"[WARN] {it.get('rule_id')} anchoring mismatch: {anchoring_warns}", file=sys.stderr)

            # Regulation anchoring: drop if not visible (with +/-1 tolerance)
            if not args.no_anchoring and allowed_regs:
                nearest = min((abs(reg_no - r) for r in allowed_regs), default=None)
                if nearest is None:
                    pass
                elif nearest == 0:
                    pass
                elif nearest == 1:
                    it.setdefault("repair_notes", []).append(
                        f"anchoring_slack+/-1(allowed={sorted(allowed_regs)})"
                    )
                    try:
                        conf = float(it.get("confidence", 0.9))
                    except Exception:
                        conf = 0.9
                    it["confidence"] = max(0.0, round(conf - 0.1, 3))
                else:
                    if args.debug:
                        print(f"[DEBUG] dropping {it.get('rule_id')} due to anchoring (allowed={sorted(allowed_regs)})", file=sys.stderr)
                    continue

            # span_hint verification
            span_hint = ""
            if isinstance(it.get("source"), dict):
                span_hint = it["source"].get("span_hint", "") or ""
            if args.span_mode == "lenient":
                ok_span = contains_span_hint_lenient(visible, span_hint) or contains_span_hint_fuzzy(visible, span_hint)
            else:
                ok_span = contains_span_hint(visible, span_hint) or contains_span_hint_fuzzy(visible, span_hint)
            if not ok_span:
                it.setdefault("repair_notes", []).append("span_hint_unmatched")
                try:
                    conf = float(it.get("confidence", 0.9))
                except Exception:
                    conf = 0.9
                it["confidence"] = max(0.0, round(conf - 0.15, 3))

            # filter by regulation range
            if args.reg_filter:
                lo, hi = args.reg_filter
                if reg_no < lo or reg_no > hi:
                    continue

            if "status" not in it:
                it["status"] = "accepted"
            if not validate_rule(it):
                continue
            rid = it["rule_id"]
            if args.dedupe and rid in existing_rule_ids:
                continue

            normalized_text = normalize_clause_text(it.get("text", ""))
            if len(normalized_text) < MIN_TEXT_CHARS:
                continue
            it["_norm_text"] = normalized_text
            text_signature = normalized_text[:TEXT_SIGNATURE_SLICE]

            base_key = f"{it.get('rule_id_norm')}|{it.get('sub_id') or ''}"
            signature_key = signature_to_key.get(text_signature)
            if signature_key:
                key = signature_key
            else:
                key = base_key
                signature_to_key[text_signature] = key

            existing_item = selected_items.get(key)
            if existing_item is None:
                selected_items[key] = it
                item_order.append(key)
                if args.debug:
                    src_pages = (it.get("source") or {}).get("pages") if isinstance(it.get("source"), dict) else None
                    print(f"[ACCEPT] {it.get('rule_id')} pages={src_pages}", file=sys.stderr)
            else:
                best = choose_best_item(existing_item, it)
                if best is not existing_item:
                    selected_items[key] = best
                    if args.debug:
                        src_pages = (best.get("source") or {}).get("pages") if isinstance(best.get("source"), dict) else None
                        print(f"[ACCEPT] updated {best.get('rule_id')} pages={src_pages}", file=sys.stderr)

        # Update carry-forward regs for next window (current window's own regs only,
        # not the union — prevents stale regs from propagating indefinitely)
        prev_visible_regs = visible_regs

        # small pause to be gentle on local model
        time.sleep(0.1)

    if not selected_items:
        print("No Lean content generated (all items filtered); writing nothing.", file=sys.stderr)
        return

    # Collect final rules list
    all_rules = []
    for key in item_order:
        item = selected_items[key]
        item.pop("_norm_text", None)
        all_rules.append(item)

    # Bug fix 12.6: override Nat -> List Nat where multi-year language is present
    for r in all_rules:
        override_list_nat_from_text(r)

    # Bug fix 12.5: deduplicate field names across regulations
    deduplicate_field_names(all_rules)

    # Phase 11: coverage summary
    if args.debug_dir:
        debug_dir = Path(args.debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        extracted_regs = set()
        extracted_ids = set()
        for item in all_rules:
            extracted_ids.add(item.get("rule_id", ""))
            m = re.match(r"ICDR_(\d+)", item.get("rule_id", ""))
            if m:
                extracted_regs.add(int(m.group(1)))
        coverage = {
            "total_rules_extracted": len(all_rules),
            "regulations_covered": sorted(extracted_regs),
            "all_rule_ids": sorted(extracted_ids),
            "reg_filter": args.reg_filter,
        }
        if args.reg_filter:
            lo, hi = args.reg_filter
            expected = set(range(lo, hi + 1))
            coverage["regulations_missing"] = sorted(expected - extracted_regs)
        (debug_dir / "coverage_summary.json").write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- Metadata enrichment ---
    if structure_lookup and not args.no_enrich:
        enrich_batch(
            all_rules,
            structure_lookup,
            regulation_framework=args.regulation_framework,
            jurisdiction=args.jurisdiction,
        )
        ts = datetime.utcnow().isoformat() + "Z"
        for r in all_rules:
            r["extraction_timestamp"] = ts
            r["extraction_model"] = args.model

    # --- Write to store ---
    store = RuleStore(out, mode="a" if args.append else "w")
    written = store.write_batch(all_rules, dedupe=args.dedupe)
    print(f"[DONE] Wrote {written} enriched rules -> {out}")


if __name__ == "__main__":
    main()

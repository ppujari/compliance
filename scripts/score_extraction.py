#!/usr/bin/env python3
"""
score_extraction.py
===================
Evaluates a rule extraction output JSONL against the gold standard JSONL.

Computes:
  - Precision, Recall, F1 (overall)
  - Per-regulation TP / FN / FP breakdown
  - Duplicate rule_id detection
  - maps_to coverage comparison
  - Version delta table (if --baseline is provided)

Usage:
    python scripts/score_extraction.py \
        --extracted data/processed/rules_refactored_v7.jsonl \
        --gold      data/gold_standard/gold_standard_regs_4_23.jsonl \
        [--baseline data/processed/rules_refactored_v6.jsonl] \
        [--output   reports/v7_score_report.json] \
        [--verbose]

Exit code: 0 if F1 >= 90%, 1 otherwise (useful for CI gating).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_jsonl(path: Path, label: str) -> list[dict]:
    rules = []
    errors = 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rules.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] {label}: JSON parse error at line {i}: {e}",
                      file=sys.stderr)
                errors += 1
    if errors:
        print(f"[WARN] {label}: {errors} lines skipped due to parse errors",
              file=sys.stderr)
    return rules


def top_reg(rule_id: str) -> str:
    """Extract top-level regulation number string from a rule_id.
    'ICDR_6_3_iv_a' -> '6', 'ICDR_8a_c' -> '8a', 'ICDR_10_1' -> '10'
    """
    m = re.match(r"ICDR_(\d+[aA]?)", rule_id, re.I)
    return m.group(1) if m else "?"


def reg_sort_key(reg_str: str):
    """Sort key for regulation numbers: '8a' sorts after '8', before '9'."""
    m = re.match(r"(\d+)([a-zA-Z]*)", str(reg_str))
    if m:
        return (int(m.group(1)), m.group(2).lower())
    return (9999, reg_str)


def compute_scores(extracted_ids: list[str], gold_ids: set[str], label: str) -> dict:
    ext_set = set(extracted_ids)
    tp = len(gold_ids & ext_set)
    fn = len(gold_ids - ext_set)
    fp = len(ext_set - gold_ids)
    recall    = tp / len(gold_ids) * 100 if gold_ids else 0.0
    precision = tp / len(ext_set)  * 100 if ext_set  else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    dupes = {k: v for k, v in Counter(extracted_ids).items() if v > 1}
    return dict(
        label=label,
        gold_total=len(gold_ids),
        extracted_unique=len(ext_set),
        tp=tp, fn=fn, fp=fp,
        recall=recall, precision=precision, f1=f1,
        duplicates=dupes,
        missing=sorted(gold_ids - ext_set),
        extra=sorted(ext_set - gold_ids),
    )


def per_reg_breakdown(
    gold_rules: list[dict],
    extracted_rules: list[dict],
    baseline_rules: Optional[list[dict]] = None,
) -> list[dict]:
    """Compute per-regulation TP/FN/FP for extracted (and optionally baseline)."""
    gold_by_reg: dict[str, set[str]] = {}
    for r in gold_rules:
        g = top_reg(r["rule_id"])
        gold_by_reg.setdefault(g, set()).add(r["rule_id"])

    ext_by_reg: dict[str, set[str]] = {}
    for r in extracted_rules:
        g = top_reg(r["rule_id"])
        ext_by_reg.setdefault(g, set()).add(r["rule_id"])

    base_by_reg: dict[str, set[str]] = {}
    if baseline_rules:
        for r in baseline_rules:
            g = top_reg(r["rule_id"])
            base_by_reg.setdefault(g, set()).add(r["rule_id"])

    all_regs = sorted(
        set(gold_by_reg) | set(ext_by_reg),
        key=reg_sort_key
    )

    rows = []
    for reg in all_regs:
        gold_set = gold_by_reg.get(reg, set())
        ext_set  = ext_by_reg.get(reg,  set())
        base_set = base_by_reg.get(reg, set()) if baseline_rules else None

        tp = len(gold_set & ext_set)
        fn = len(gold_set - ext_set)
        fp = len(ext_set  - gold_set)

        row: dict = dict(reg=reg, gold=len(gold_set), tp=tp, fn=fn, fp=fp,
                         missing=sorted(gold_set - ext_set),
                         extra=sorted(ext_set - gold_set))

        if base_set is not None:
            b_tp = len(gold_set & base_set)
            row["base_tp"] = b_tp
            row["delta_tp"] = tp - b_tp

        rows.append(row)
    return rows


def maps_to_coverage(gold_rules: list[dict], extracted_rules: list[dict]) -> dict:
    """Compare maps_to field population between gold and extracted."""
    gold_lookup   = {r["rule_id"]: r for r in gold_rules}
    ext_lookup    = {r["rule_id"]: r for r in extracted_rules}

    shared_ids = set(gold_lookup) & set(ext_lookup)

    gold_has  = sum(1 for rid in shared_ids if gold_lookup[rid].get("maps_to"))
    ext_has   = sum(1 for rid in shared_ids if ext_lookup[rid].get("maps_to"))
    both_have = sum(1 for rid in shared_ids
                    if gold_lookup[rid].get("maps_to")
                    and ext_lookup[rid].get("maps_to"))
    gold_has_ext_empty = [
        rid for rid in shared_ids
        if gold_lookup[rid].get("maps_to")
        and not ext_lookup[rid].get("maps_to")
    ]
    return dict(
        shared_rule_count=len(shared_ids),
        gold_has_maps_to=gold_has,
        extracted_has_maps_to=ext_has,
        both_have_maps_to=both_have,
        gold_has_extracted_empty=sorted(gold_has_ext_empty),
    )


# ── Formatting ────────────────────────────────────────────────────────────────

SEP  = "=" * 72
SEP2 = "-" * 72


def print_header(label: str, gold_total: int):
    print(SEP)
    print(f"  SEBI ICDR Rule Extraction — Scoring Report")
    print(f"  Candidate : {label}")
    print(f"  Gold std  : {gold_total} rules (Regs 4–23)")
    print(SEP)


def print_overall(scores: dict, baseline_scores: Optional[dict] = None):
    print()
    print("OVERALL SCORES")
    print(SEP2)
    header = f"  {'Metric':<30} {'Candidate':>12}"
    if baseline_scores:
        header += f"  {'Baseline':>10}  {'Delta':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    def row(label, key, fmt="{:.1f}%"):
        v = scores[key]
        line = f"  {label:<30} {fmt.format(v) if isinstance(v, float) else str(v):>12}"
        if baseline_scores:
            bv = baseline_scores[key]
            delta = v - bv if isinstance(v, (int, float)) else ""
            dsign = "+" if isinstance(delta, float) and delta >= 0 else ""
            line += f"  {fmt.format(bv) if isinstance(bv, float) else str(bv):>10}"
            line += f"  {dsign}{delta:.1f}" if isinstance(delta, float) else ""
        print(line)

    row("Gold standard rules",    "gold_total",        fmt="{}")
    row("Extracted (unique IDs)", "extracted_unique",  fmt="{}")
    row("Correctly extracted (TP)","tp",                fmt="{}")
    row("Missing (FN)",           "fn",                fmt="{}")
    row("Wrong/extra IDs (FP)",   "fp",                fmt="{}")
    n_dupes = len(scores["duplicates"])
    print(f"  {'Duplicate rule_ids':<30} {n_dupes:>12}"
          + (f"  {len(baseline_scores['duplicates']):>10}  {n_dupes - len(baseline_scores['duplicates']):>+8}"
             if baseline_scores else ""))
    print()
    row("Recall  (TP / Gold)",    "recall")
    row("Precision (TP / Extracted)", "precision")
    row("F1 Score",               "f1")

    # F1 target indicator
    f1 = scores["f1"]
    target = 90.0
    status = "✓ TARGET MET" if f1 >= target else f"✗ {target - f1:.1f}pp below {target:.0f}% target"
    print(f"\n  F1 Status: {status}")


def print_per_reg(rows: list[dict], has_baseline: bool):
    print()
    print("PER-REGULATION BREAKDOWN")
    print(SEP2)
    if has_baseline:
        print(f"  {'Reg':<6} {'Gold':>5} {'TP':>5} {'FN':>5} {'FP':>5}"
              f"  {'Base TP':>8}  {'Delta':>6}  Issues")
    else:
        print(f"  {'Reg':<6} {'Gold':>5} {'TP':>5} {'FN':>5} {'FP':>5}  Issues")
    print("  " + SEP2)

    for r in rows:
        issues = []
        if r["fn"]:
            issues.append(f"FN={r['fn']}")
        if r["fp"]:
            issues.append(f"FP={r['fp']}")
        issue_str = ", ".join(issues) if issues else "✓ clean"

        line = (f"  {r['reg']:<6} {r['gold']:>5} {r['tp']:>5} "
                f"{r['fn']:>5} {r['fp']:>5}")
        if has_baseline:
            delta = r.get("delta_tp", 0)
            dsign = "+" if delta >= 0 else ""
            line += f"  {r.get('base_tp', '?'):>8}  {dsign}{delta:>5}"
        line += f"  {issue_str}"
        print(line)

        # Show missing IDs in verbose detail
        if r["missing"]:
            for mid in r["missing"]:
                print(f"         MISSING: {mid}")
        if r["extra"]:
            for eid in r["extra"]:
                print(f"         EXTRA  : {eid}")


def print_maps_to(cov: dict):
    print()
    print("MAPS_TO COVERAGE (shared rules only)")
    print(SEP2)
    print(f"  Shared rules (in both gold and extracted):  {cov['shared_rule_count']}")
    print(f"  Gold has maps_to populated:                 {cov['gold_has_maps_to']}")
    print(f"  Extracted has maps_to populated:            {cov['extracted_has_maps_to']}")
    print(f"  Both populated:                             {cov['both_have_maps_to']}")
    if cov["gold_has_extracted_empty"]:
        print(f"\n  Gold has maps_to but extracted is EMPTY ({len(cov['gold_has_extracted_empty'])}):")
        for rid in cov["gold_has_extracted_empty"]:
            print(f"    {rid}")


def print_duplicates(dupes: dict):
    if dupes:
        print()
        print(f"DUPLICATE RULE_IDs ({len(dupes)} found — should be 0)")
        print(SEP2)
        for rid, count in sorted(dupes.items()):
            print(f"  {rid}: appears {count} times")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Score rule extraction output against a gold standard JSONL."
    )
    ap.add_argument(
        "--extracted", required=True,
        help="Path to the extracted rules JSONL to evaluate (e.g. rules_refactored_v7.jsonl)"
    )
    ap.add_argument(
        "--gold", required=True,
        help="Path to the gold standard JSONL (e.g. gold_standard_regs_4_23.jsonl)"
    )
    ap.add_argument(
        "--baseline", default=None,
        help="Optional: path to a prior version JSONL for delta comparison (e.g. rules_refactored_v6.jsonl)"
    )
    ap.add_argument(
        "--output", default=None,
        help="Optional: write full JSON report to this path"
    )
    ap.add_argument(
        "--verbose", action="store_true",
        help="Print missing/extra rule IDs inline in per-reg table (always true for FP/FN > 0)"
    )
    ap.add_argument(
        "--target-f1", type=float, default=90.0,
        help="F1 target percentage for exit-code gating (default: 90.0)"
    )
    args = ap.parse_args()

    # ── Load files ────────────────────────────────────────────────────────────
    gold_rules      = load_jsonl(Path(args.gold),      "gold")
    extracted_rules = load_jsonl(Path(args.extracted), "extracted")
    baseline_rules  = load_jsonl(Path(args.baseline),  "baseline") if args.baseline else None

    gold_ids      = {r["rule_id"] for r in gold_rules}
    extracted_ids = [r["rule_id"] for r in extracted_rules]   # keep dupes for dupe detection
    baseline_ids  = ([r["rule_id"] for r in baseline_rules]
                     if baseline_rules else None)

    # ── Score ─────────────────────────────────────────────────────────────────
    scores          = compute_scores(extracted_ids, gold_ids, label=args.extracted)
    baseline_scores = (compute_scores(baseline_ids, gold_ids, label=args.baseline)
                       if baseline_ids else None)

    reg_rows = per_reg_breakdown(gold_rules, extracted_rules, baseline_rules)
    maps_cov = maps_to_coverage(gold_rules, extracted_rules)

    # ── Print report ──────────────────────────────────────────────────────────
    print_header(args.extracted, len(gold_ids))
    print_overall(scores, baseline_scores)
    print_per_reg(reg_rows, has_baseline=baseline_rules is not None)
    print_maps_to(maps_cov)
    print_duplicates(scores["duplicates"])

    # ── JSON output ───────────────────────────────────────────────────────────
    if args.output:
        report = dict(
            candidate=args.extracted,
            gold=args.gold,
            baseline=args.baseline,
            scores=scores,
            baseline_scores=baseline_scores,
            per_regulation=reg_rows,
            maps_to_coverage=maps_cov,
        )
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[REPORT] Written to {out_path}")

    # ── Exit code for CI gating ───────────────────────────────────────────────
    if scores["f1"] < args.target_f1:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

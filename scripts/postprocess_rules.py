#!/usr/bin/env python3
# scripts/postprocess_rules.py
"""
Post-process extracted ICDR rules JSONL to produce a clean, sequential list.

Features:
- Reads input JSONL of rule items (one JSON object per line)
- Optional regulation range filter (e.g., keep only 3..22)
- Deduplicates by rule_id (merges pages; keeps best item by confidence/text length)
- Sorts sequentially by (reg, clause, subclause) parsed from rule_id
- Optional LLM refinement for title/notes when --refine-model is provided (Ollama)
"""

from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from difflib import SequenceMatcher

# Schema validation (best-effort; we reuse the same schema as extractor)
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path("data/schema/rules_schema.json")
RULE_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(RULE_SCHEMA)

RULE_ID_RE = re.compile(r"^ICDR_(\d+)(?:_(\d+))?(?:_([a-z]+))?$", re.I)
SIMILARITY_THRESHOLD = 0.9

def normalize_clause_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()

def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def item_score(it: Dict[str, Any]) -> Tuple[float, int]:
    conf = it.get("confidence")
    try:
        conf_val = float(conf) if conf is not None else -1.0
    except Exception:
        conf_val = -1.0
    text_len = len((it.get("text") or "").strip())
    return (conf_val, text_len)

def parse_rule_id(rule_id: str) -> Tuple[int, int, str]:
    """
    Returns (reg, clause, subclause) where:
    - reg: integer regulation number
    - clause: integer clause number (0 if missing)
    - subclause: string subclause letters, '' if missing
    """
    m = RULE_ID_RE.match(rule_id or "")
    if not m:
        return (10**9, 10**9, "zzz")  # push invalids to the end
    reg = int(m.group(1))
    clause = int(m.group(2) or 0)
    sub = m.group(3) or ""
    return (reg, clause, sub)

def validate_item(item: Dict[str, Any]) -> bool:
    try:
        errors = list(VALIDATOR.iter_errors(item))
        if errors:
            return False
        if not isinstance(item.get("rule_id"), str):
            return False
        if not isinstance(item.get("lean_id"), str):
            return False
        return True
    except Exception:
        return False

def choose_best_item(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pick the best representative among duplicates with the same rule_id.
    Preference:
      1) higher 'confidence'
      2) longer 'text'
      3) first appearance
    Also merges source.pages (union, sorted) and keeps the chosen core fields.
    """
    items_sorted = sorted(items, key=item_score, reverse=True)
    best = items_sorted[0]
    # merge pages from all
    merged_pages = []
    for it in items:
        src = it.get("source") or {}
        pages = src.get("pages") or []
        if isinstance(pages, list):
            for p in pages:
                if isinstance(p, int):
                    merged_pages.append(p)
    merged_pages = sorted(sorted(set(merged_pages)))
    if isinstance(best.get("source"), dict):
        best["source"]["pages"] = merged_pages or best["source"].get("pages", [])
    return best

def filter_by_reg_range(items: List[Dict[str, Any]], reg_lo: int | None, reg_hi: int | None) -> List[Dict[str, Any]]:
    if reg_lo is None or reg_hi is None:
        return items
    kept = []
    for it in items:
        reg, _, _ = parse_rule_id(it.get("rule_id", ""))
        if reg_lo <= reg <= reg_hi:
            kept.append(it)
    return kept

def filter_explanations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Drop any item where the rule 'text' contains the word 'explanation' (case-insensitive).
    """
    kept: List[Dict[str, Any]] = []
    for it in items:
        text = (it.get("text") or "")
        if "explanation" in text.lower():
            continue
        kept.append(it)
    return kept

def relabel_outliers_by_context(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Do NOT reorder. Walk the items in input order and detect obvious outliers
    like ICDR_4 between ICDR_6 and ICDR_7. When an outlier is found between two
    consecutive regulations (prev_reg and next_reg present) and reg_i is not
    within [min(prev_reg,next_reg) .. max(prev_reg,next_reg)], relabel the item's
    regulation number to prev_reg (keep clause/subclause suffix intact).
    If prev_reg is unavailable, keep as-is. If next_reg is unavailable but the
    deviation from prev_reg is large (>=2), relabel to prev_reg.
    Also smooth local plateaus: when next_reg == prev_reg and reg_i != prev_reg,
    relabel reg_i to prev_reg.
    """
    # Helper to rewrite rule_id and lean_id with a new regulation number
    def rewrite_ids(it: Dict[str, Any], new_reg: int) -> None:
        rid = it.get("rule_id") or ""
        lid = it.get("lean_id") or ""
        it["rule_id"] = re.sub(r"^ICDR_\d+", f"ICDR_{new_reg}", rid)
        it["lean_id"] = re.sub(r"^rule_\d+", f"rule_{new_reg}", lid)

    # Pre-compute raw regs to avoid re-parsing
    regs: List[int] = []
    for it in items:
        reg, _, _ = parse_rule_id(it.get("rule_id", ""))
        regs.append(reg)

    last_valid_reg: int | None = None
    n = len(items)
    for i, it in enumerate(items):
        reg_i = regs[i]
        # find next valid reg ahead
        next_reg: int | None = None
        for j in range(i+1, n):
            if regs[j] != 10**9:  # parsed ok
                next_reg = regs[j]
                break
        # Decide if outlier
        if last_valid_reg is not None and reg_i != 10**9:
            if next_reg is not None:
                # plateau smoothing: prev == next -> force middle to prev
                if next_reg == last_valid_reg and reg_i != last_valid_reg:
                    rewrite_ids(it, last_valid_reg)
                    regs[i] = last_valid_reg
                else:
                    lo, hi = (last_valid_reg, next_reg) if last_valid_reg <= next_reg else (next_reg, last_valid_reg)
                    if not (lo <= reg_i <= hi):
                        # relabel to previous regulation number
                        rewrite_ids(it, last_valid_reg)
                        regs[i] = last_valid_reg
            else:
                # no next_reg: if deviation is large, snap to prev
                if abs(reg_i - last_valid_reg) >= 2:
                    rewrite_ids(it, last_valid_reg)
                    regs[i] = last_valid_reg
        # update last_valid_reg
        if reg_i != 10**9:
            last_valid_reg = regs[i]
    return items

def dedupe_by_similarity(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Preserve order of first appearance, but merge near-duplicate clauses
    that share (reg, clause) and have highly similar text/title.
    """
    clusters: List[Dict[str, Any]] = []
    for idx, it in enumerate(items):
        reg, clause, _ = parse_rule_id(it.get("rule_id", ""))
        norm_text = normalize_clause_text(it.get("text", ""))
        norm_title = normalize_clause_text(it.get("title", ""))
        it["_order"] = idx
        it["_norm_text"] = norm_text
        it["_norm_title"] = norm_title
        target_cluster = None
        for cluster in clusters:
            if cluster["reg"] != reg or cluster["clause"] != clause:
                continue
            if text_similarity(norm_text, cluster["norm_text"]) >= SIMILARITY_THRESHOLD:
                target_cluster = cluster
                break
            if cluster["norm_title"] and norm_title and norm_title == cluster["norm_title"]:
                target_cluster = cluster
                break
        if target_cluster:
            target_cluster["items"].append(it)
            best_candidate = max(target_cluster["items"], key=item_score)
            target_cluster["norm_text"] = normalize_clause_text(best_candidate.get("text", ""))
            target_cluster["norm_title"] = normalize_clause_text(best_candidate.get("title", ""))
        else:
            clusters.append({
                "reg": reg,
                "clause": clause,
                "items": [it],
                "norm_text": norm_text,
                "norm_title": norm_title,
                "order": idx,
            })
    clusters.sort(key=lambda c: c["order"])
    deduped: List[Dict[str, Any]] = []
    for cluster in clusters:
        best = choose_best_item(cluster["items"])
        deduped.append(best)
    deduped.sort(key=lambda it: it.get("_order", 0))
    for it in deduped:
        it.pop("_order", None)
        it.pop("_norm_text", None)
        it.pop("_norm_title", None)
    return deduped

def sort_by_rule_id(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a new list sorted numerically by (reg, clause, subclause).
    """
    def sort_key(it: Dict[str, Any]) -> Tuple[int, int, str]:
        return parse_rule_id(it.get("rule_id", ""))
    return sorted(items, key=sort_key)

# Optional: LLM refinement via Ollama
def ollama_refine(items: List[Dict[str, Any]], model: str, timeout: int) -> List[Dict[str, Any]]:
    import requests
    url = "http://localhost:11434/api/chat"
    system = "You are a precise copyeditor. Standardize titles to be concise and consistent. Keep legal meaning. Do not change rule_id or text."
    refined: List[Dict[str, Any]] = []
    for it in items:
        # Only refine 'title' and 'notes'
        prompt = {
            "rule_id": it.get("rule_id"),
            "title": it.get("title"),
            "notes": it.get("notes", "")
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Standardize the following JSON and return JSON only with keys title and notes:\n{json.dumps(prompt, ensure_ascii=False)}"}
            ],
            "stream": False,
            "format": "json"
        }
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            content = (data.get("message", {}) or {}).get("content", "").strip()
            try:
                out = json.loads(content)
                if isinstance(out, dict):
                    if "title" in out and isinstance(out["title"], str):
                        it["title"] = out["title"]
                    if "notes" in out and isinstance(out["notes"], str):
                        it["notes"] = out["notes"]
            except Exception:
                pass
        except Exception:
            pass
        refined.append(it)
    return refined

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", "--in", dest="inp", required=True, help="Input JSONL file")
    ap.add_argument("--out", required=True, help="Output JSONL file")
    ap.add_argument("--reg-range", nargs=2, type=int, default=None, metavar=("START","END"),
                    help="Keep only rules whose regulation number is in [START..END]")
    ap.add_argument("--refine-model", type=str, default=None,
                    help="Optional Ollama model for standardizing titles/notes (e.g., qwen2.5:7b-instruct)")
    ap.add_argument("--timeout", type=int, default=120, help="Timeout for LLM calls")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    raw_items: List[Dict[str, Any]] = []
    for line in inp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if not validate_item(obj):
            continue
        raw_items.append(obj)

    reg_lo = reg_hi = None
    if args.reg_range:
        reg_lo, reg_hi = args.reg_range

    # 1) optional filter by regulation range
    filtered = filter_by_reg_range(raw_items, reg_lo, reg_hi)
    # 1a) drop explanation items outright
    filtered = filter_explanations(filtered)
    # 2) relabel obvious outliers based on context in original order
    relabeled = relabel_outliers_by_context(filtered)
    # 3) dedupe by similarity (rule family + text/title) while preserving first occurrence order
    cleaned = dedupe_by_similarity(relabeled)
    # 4) optional LLM refinement (titles/notes only)
    if args.refine_model:
        cleaned = ollama_refine(cleaned, args.refine_model, args.timeout)
    # 5) enforce ascending order by regulation/clause
    cleaned = sort_by_rule_id(cleaned)

    with out.open("w", encoding="utf-8") as f_out:
        for it in cleaned:
            f_out.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"✅ Wrote {len(cleaned)} cleaned rules → {out}")

if __name__ == "__main__":
    main()



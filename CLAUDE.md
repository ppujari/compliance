# CLAUDE.md — SEBI ICDR Compliance Pipeline
## Persistent context for Claude Code sessions

> This file is the authoritative source of project state. Read it fully before
> making any code changes. Update the "Current State" section after each session.

---

## What This Project Is

An automated regulatory compliance pipeline that checks whether an Indian IPO
filing (Red Herring Prospectus / RHP) satisfies SEBI ICDR 2018 regulations.

**Core pipeline (7 stages):**
1. Extract atomic rules from ICDR regulations → structured JSONL with `maps_to` hints
2. Build provisional issuer schema from mappings
3. Extract rule-anchored evidence from the RHP (table-aware, not just narrative)
4. Reconcile field types using evidence (evidence-first, never LLM-trusted types)
5. Freeze schema → generate partial issuer candidate
6. Completeness pass over RHP using frozen schema
7. Generate Lean 4 code → run formal compliance checks

**Key design decisions (do not reverse without discussion):**
- Structured `maps_to` over free-text notes
- Evidence-reconciled types over LLM-guessed types
- Tables as first-class evidence (not just narrative bullets)
- Deterministic guards around all LLM outputs: judge loop, bounded retries, quarantine
- Local models (Qwen2.5:14b-instruct) for bulk extraction — privacy-first
- Extract all 301 regulations first, then build definitions/amendment layers

---

## Codebase Map

```
rule_extraction/
  regulation_identifier.py   ← Pass 1: regex + LLM identification of regulation clauses
                               Contains: REG_HEADER_RE, HEADING_NUMBER_RE, FOOTNOTE_*_RE,
                               pre_identify_regulations(), detect_allowed_regs(),
                               identify_regulations(), split_merged_lettered_items(),
                               _PASS1_SYSTEM, _PASS1_USER_TEMPLATE

llm_extract_rules.py         ← Main extraction loop: windowing, carryover hint,
                               anchoring, expand_detected_regs(), pass2 dispatch,
                               KNOWN_ID_RENAMES, normalize_rule_identifier()

rule_extractor.py            ← Pass 2: targeted clause extraction per identified rule
                               Contains: build_targeted_extraction_prompt(), clause_text
                               truncation (CHECK THIS FOR [:300] caps)

scripts/
  score_extraction.py        ← Scoring script: Precision/Recall/F1 vs gold standard
                               Run after EVERY change. Exit 0 = F1 ≥ target.

data/
  gold_standard/
    gold_standard_regs_4_23.jsonl   ← 143-rule gold standard, Regs 4–23
  processed/
    rules_refactored_v6.jsonl       ← v6 baseline: F1=81.3%, TP=100, FN=43, FP=3
    rules_refactored_v7.jsonl       ← v7 result:   F1=68.8%, TP=88,  FN=55, FP=25
  debug_refactored_v7/
    pass2_pre_judge.jsonl           ← Pass 2 input inventory (inspect for truncation)
    pass1_inventory.jsonl           ← Pass 1 clause inventory per window

reports/
  v7_score_report.json             ← Full per-regulation breakdown for v7

data/schema/
  icdr_structure.json              ← Chapter/regulation structure (verified: Regs 4–23
                                     all correctly in Chapter II, no XII mis-assignment)
```

---

## Scoring — Run After Every Change

```bash
python scripts/score_extraction.py \
    --extracted data/processed/rules_refactored_vX.jsonl \
    --gold      data/gold_standard/gold_standard_regs_4_23.jsonl \
    --baseline  data/processed/rules_refactored_v6.jsonl \
    --output    reports/vX_score_report.json
```

- Exit code 0 = F1 ≥ 90% (configurable via `--target-f1`)
- `--baseline` flag prints per-regulation delta column vs v6
- **Never submit a version without running this first**
- Check per-regulation table for regressions — a global F1 improvement can hide a regression on a clean regulation

**v6 is the baseline.** If any per-regulation TP is lower in your new version than in
v6, that is a regression and must be investigated before proceeding.

---

## Current Scores (as of May 2026)

| Version | TP | FN | FP | Recall | Precision | F1 |
|---------|----|----|-----|--------|-----------|-----|
| v5 | 92 | 51 | 26 | 64.3% | 78.0% | 70.5% |
| **v6 (baseline)** | **100** | **43** | **3** | **69.9%** | **97.1%** | **81.3%** |
| v7 (regression) | 88 | 55 | 25 | 61.5% | 77.9% | 68.8% |
| **v8 target** | **~136** | **~7** | **~0** | **>90%** | **>95%** | **>95%** |

**Clean regulations in v6 (do not break these):** 4, 9, 13, 18, 19, 20, 21, 22, 23

---

## v8 Work Plan — Apply In This Order

Apply each fix, run scoring, confirm no regressions before moving to the next.

### Priority 1 — Find ALL truncation caps (Zero risk, highest yield)

**Problem confirmed:** `ICDR_14_b` (len=300) and `ICDR_14_4` (len=300) appear at
exactly 300 chars in `pass2_pre_judge.jsonl` even in v7 — the 1200-char fix was NOT
applied to all locations. This single issue causes all 6 missing Reg 14 provisos, plus
missing Reg 22 and 23 provisos (regressions from v6).

**Action:** Search the entire codebase:
```bash
grep -rn "\[:300\]\|\[:500\]\|max_chars\s*=\s*[3-5][0-9][0-9]\b" --include="*.py"
```
Raise every instance to `[:1200]`. Update any associated prompt template that says
"max 300 chars" or "max 500 chars" to say "max 1200 chars". Check `rule_extractor.py`
specifically — the truncation is likely there, not in `llm_extract_rules.py`.

**Expected recovery:** `ICDR_14_proviso`, `ICDR_14_proviso_2`, `ICDR_14_a_proviso`,
`ICDR_14_c_proviso`, `ICDR_14_4_proviso`, `ICDR_14_4_proviso_2`, `ICDR_22_proviso`,
`ICDR_23_5_proviso` (+8 rules, 0 FP risk).

---

### Priority 2 — Fix `split_merged_lettered_items()` to emit parent first

**Problem confirmed:** v7's `split_merged_lettered_items()` replaces the parent clause
with its children — it never emits the parent clause object. This caused Reg 13 to lose
`ICDR_13_c` entirely (was TP in v6, became FN in v7) and created spurious children
`ICDR_13_c_a`, `ICDR_13_c_b` (FPs).

**File:** `rule_extraction/regulation_identifier.py`

Find `split_merged_lettered_items()`. In the section that builds `chunks` and emits
new items, ADD the parent emission before the children loop:

```python
# After building chunks and confirming len(chunks) > 1:

# 1. Emit the PARENT clause first, trimmed before the first child item
first_child_marker = f"{parent_letter}."
intro_end = clause_text.find(first_child_marker)
if intro_end > 0:
    parent_clause_text = clause_text[:intro_end].rstrip(", ;\n-–:")
else:
    parent_clause_text = splits[0].strip()

if parent_clause_text:
    parent_item = dict(item)
    parent_item["reg_number"] = reg_num   # original reg_number, not split
    parent_item["clause_text"] = parent_clause_text
    parent_item["span_hint"] = " ".join(parent_clause_text.split()[:8])
    result.append(parent_item)

# 2. Then emit each child item
for letter, text in chunks:
    new_item = dict(item)
    new_item["reg_number"] = f"{parent_path}({letter})"
    new_item["clause_text"] = f"{letter}. {text}"
    new_item["span_hint"] = " ".join(text.split()[:8])
    result.append(new_item)
```

**Expected recovery:** `ICDR_13_c` (+1 TP), removes `ICDR_13_c_a`, `ICDR_13_c_b`
spurious FPs (-2 FP). Net: Reg 13 should return to TP=5 (v6 level).

---

### Priority 3 — Add "no phantom sub-levels" rule to `_PASS1_SYSTEM`

**Problem confirmed:** v7 introduced `ICDR_17_1_a`, `ICDR_17_1_b` (phantom `(1)` level),
`ICDR_16_1` (bare, not in gold), `ICDR_5_explanation` (missing `_1` level). The model
is inventing intermediate numbered sub-regulation levels not present in source text.
Root cause: the lettered-item splitting prompt caused the model to assume numbered
sub-regulation wrappers exist.

**File:** `rule_extraction/regulation_identifier.py`

Add to `_PASS1_SYSTEM` (append before the closing quote):

```python
"NEVER INVENT INTERMEDIATE SUB-REGULATION LEVELS:\n"
"If lettered items (a., b., c.) appear directly under a top-level regulation\n"
"number with no intermediate numbered sub-regulation visible in the text,\n"
"the reg_number is 'N(a)', 'N(b)' — NEVER 'N(1)(a)'.\n"
"Only include a numeric sub-level like (1) or (2) if it appears EXPLICITLY\n"
"in the source text. Do not insert numeric levels to 'complete' a structure\n"
"you assume should be there. If you see '17. Nothing in this regulation shall\n"
"apply to: a. equity shares...' then emit reg_number '17(a)', not '17(1)(a)'.\n\n"
```

**Expected recovery:** `ICDR_17_a`, `ICDR_17_b`, `ICDR_17_c` (+3 TP), removes
`ICDR_17_1_a`, `ICDR_17_1_b`, `ICDR_17_1_a_proviso`, `ICDR_17_1_b_proviso` (-4 FP).
Also fixes `ICDR_5_1_explanation` and `ICDR_16_1_explanation` path errors.

---

### Priority 4 — Move carryover hint BEFORE `reg_context` in prompt

**Problem confirmed:** v7 still produces `ICDR_6_v` (pages [4,5]) instead of
`ICDR_6_3_v`. The `reg_context` block (listing `visible_regs = {6, 7}`) appears
earlier in the prompt than the carryover hint, and the model anchors to it, ignoring
the continuation instruction. Prompt position matters — earlier text wins.

**File:** `rule_extraction/regulation_identifier.py`

In `identify_regulations()`, find where `carryover_hint` and `reg_context` are
assembled into the user prompt string. Change the order so `carryover_hint` appears
FIRST:

```python
# BEFORE (current order):
user_prompt = f"{reg_context}\n\n{window_text}\n\n{carryover_hint}"

# AFTER (carryover takes priority):
user_prompt = f"{carryover_hint}\n\n{reg_context}\n\n{window_text}"
```

Also strengthen the `reg_context` note when carryover is active (add after existing
`reg_context` string is built):

```python
if carryover_hint:
    reg_context += (
        "IMPORTANT: Items at the very START of this window may be continuations "
        "from the previous page — the CONTINUATION HINT above takes priority "
        "over this list for those items. Do not assign a bare roman numeral or "
        "letter directly to a top-level regulation when a continuation hint is "
        "present.\n\n"
    )
```

**Expected recovery:** `ICDR_6_3_v` through `ICDR_6_3_ix` and Reg 15 continuation
items (+5–8 rules).

---

### Priority 5 — Confirm Fix 4a (terminal letter strip) is running

**Problem confirmed:** v7 still produces `ICDR_15_1_a_c`, `ICDR_15_1_a_iv_proviso`
(path contains extra `_a` level). This means `prev_window_last_subclause` is still
`15(1)(a)` when processing the next window, not `15(1)` as it should be after
stripping the terminal letter.

**File:** `llm_extract_rules.py`

Find the carry-forward block (where `prev_window_last_subclause` is set). Add a
debug print TEMPORARILY to verify the strip is firing:

```python
raw_last = max(_nums, key=_pass1_depth)
prev_window_last_subclause = re.sub(r"\([a-e]\)$", "", raw_last).strip() or raw_last

# TEMPORARY DEBUG — remove after confirming:
if raw_last != prev_window_last_subclause:
    print(f"[DEBUG carryover] stripped {raw_last!r} -> {prev_window_last_subclause!r}",
          file=sys.stderr)
```

If the debug line never prints for a window where `_nums` contains `15(1)(a)`, the
code block is not being reached (wrong branch, wrong variable name). Trace and fix.

**Expected recovery:** `ICDR_15_1_c`, `ICDR_15_1_d`, `ICDR_15_1_i` through `15_1_iv`
(up to +6 rules), removes `ICDR_15_1_a_c`, `ICDR_15_1_a_iv_*` FPs (-2 FP).

---

### Priority 6 — Pass 2 deduplication (keep longest clause_text per rule_id)

**Problem confirmed:** `pass2_pre_judge.jsonl` contains multiple entries for
`ICDR_14_1` (×2), `ICDR_5_1_a` (×2 with different texts), `ICDR_6_3_ii` (×2 from
overlapping windows), `ICDR_13_c_a` (×3), `ICDR_17_explanation_i` (×2). These produce
duplicate Pass 2 calls and inflate FP counts.

**File:** `llm_extract_rules.py` (or wherever pass2 entries are assembled before dispatch)

Add deduplication after all windows are collected, before Pass 2 runs:

```python
def dedup_pass2_entries(entries: list[dict]) -> list[dict]:
    """
    For duplicate rule_ids in the Pass 2 input list, keep the entry with the
    longest clause_text (most content). Discard shorter duplicates.
    This prevents duplicate Pass 2 calls and redundant rule_id entries in output.
    """
    seen: dict[str, dict] = {}
    for entry in entries:
        rid = entry.get("rule_id", "")
        text = entry.get("clause_text", "") or entry.get("text", "")
        if rid not in seen or len(text) > len(seen[rid].get("clause_text", "")):
            seen[rid] = entry
    return list(seen.values())

# Call before dispatching to Pass 2:
pass2_entries = dedup_pass2_entries(pass2_entries)
```

**Expected impact:** Eliminates duplicate rule_id in output, reduces spurious FPs,
speeds up Pass 2 (fewer calls). Zero regression risk.

---

### Priority 7 — Verify `expand_detected_regs` receives `visible_reg_strings`

**Problem confirmed:** Reg 8 is near-completely missing in v7 (TP=1, was TP=3 in v6).
Only `ICDR_8_explanation` appears in pass2. The main Reg 8 body and all provisos are
absent. The `expand_detected_regs` fix (adding `8` when `8A` is detected) was a
correct design but may not be receiving the right input.

**File:** `llm_extract_rules.py`

Find the call to `expand_detected_regs()`. Confirm it is called with the raw string
list from `pre_identify_regulations()` (which contains `"8A"` as a string), NOT with
the integer set from `detect_allowed_regs()` (which only contains integers):

```python
# WRONG — integers don't match the alphanumeric pattern:
allowed_regs = expand_detected_regs(detected_regs)   # detected_regs is set[int]

# CORRECT — use the string list that contains "8A":
allowed_regs = expand_detected_regs(visible_reg_strings)  # visible_reg_strings is list[str]
```

Also confirm `expand_detected_regs` is called AFTER `visible_regs_with_prev` is
computed (it was called before in an earlier bug):

```python
def expand_detected_regs(visible_reg_strings: list[str]) -> set:
    """When an alphanumeric variant like '8A' is detected, also allow base '8'."""
    expanded = set()
    for reg in visible_reg_strings:
        expanded.add(reg)
        m = re.match(r"^(\d+)[a-zA-Z]+$", str(reg))
        if m:
            expanded.add(int(m.group(1)))   # "8A" -> also allow integer 8
            expanded.add(m.group(1))         # and string "8"
    return expanded
```

**Expected recovery:** `ICDR_8`, `ICDR_8_proviso`, `ICDR_8_proviso_2` (+3 TP minimum).
The `8_proviso_3` block also needs the 1200-char fix (Priority 1) to fully recover.

---

## Key Architectural Rules (Do Not Violate)

### Pass 1 prompt rules — always present in `_PASS1_SYSTEM`
1. **Footnote pattern A** — inline citation markers `25[text]`: strip digit, keep bracket
2. **Footnote pattern B** — definition lines `25 Substituted by SEBI...`: remove entirely
3. **Footnote tail pattern C** — orphaned `(Amendment) Regulations...` fragments: remove
4. **Amendment-inserted sub-regs** — `[(N) text` at line start: treat as sub-reg `(N)` of parent
5. **Explanation blocks** — `Explanation.` after a reg header: separate object with `(explanation)` suffix
6. **Each lettered/roman item is separate** — never merge `a.` and `b.` into one object
7. **Parent always emitted** — when splitting a list, emit the parent clause first
8. **No phantom sub-levels** — never insert `(1)` unless it appears explicitly in text
9. **Continuation hint priority** — when CONTINUATION HINT present, it overrides reg_context

### Anchoring rules — in `llm_extract_rules.py`
- `allowed_regs` must be built from `visible_reg_strings` (strings), not `detected_regs` (ints)
- `expand_detected_regs` must run AFTER `visible_regs_with_prev` is computed
- Carryover-exempt rules (matching the hint's regulation) bypass the anchoring drop
- `prev_window_last_subclause` must have terminal `([a-e])` stripped before storage

### Pass 2 rules — in prompt / `rule_extractor.py`
- `clause_text` cap = 1200 chars (NOT 300 or 500 — check everywhere)
- Nested `Provided that` → separate objects with `_proviso`, `_proviso_2` suffixes
- Main rule and its proviso are NEVER merged into one object
- Deduplication runs before Pass 2 dispatch (keep longest per rule_id)

---

## Known False Positives (Under Investigation)

These IDs appear in v7 output but are not in the gold standard. Do NOT delete them —
they may be valid 2025 SEBI amendment insertions not yet reflected in the gold standard.
Mark as `status = "needs_review"` in post-processing:

```python
SUSPICIOUS_IDS = {
    "ICDR_15_1_b_proviso",    # not in gold — may be 2025 amendment
    "ICDR_16_1_a_proviso",    # not in gold — may be 2025 amendment
}
```

---

## Regulation ID Naming Conventions

```
ICDR_{reg}_{sub}_{item}_{detail}

Examples:
  ICDR_6_3_iv_a          → Reg 6, sub-reg (3), item (iv), clause (a)
  ICDR_14_proviso_2       → Reg 14, second "Provided that"
  ICDR_8_proviso_3_c_ii   → Reg 8, third proviso, clause (c), item (ii)
  ICDR_7_explanation      → Reg 7, Explanation block
  ICDR_8a_c               → Reg 8A, clause (c)
  ICDR_16_1_explanation   → Reg 16, sub-reg (1), Explanation block

Rules:
- Proviso naming: _proviso, _proviso_2, _proviso_3 (count of "Provided that" in order)
- Explanation naming: _explanation (always singular, attached to its parent level)
- Alphanumeric regulations: 8a (lowercase), not 8A in the ID
- Never use _1 as an intermediate level unless (1) appears explicitly in source text
```

---

## Extraction Run Command

```bash
python scripts/llm_extract_rules.py \
    --pdf  data/input/ICDR_rules_4_22.pdf \
    --out  data/processed/rules_refactored_v8.jsonl \
    --model qwen2.5:14b-instruct \
    --window 2 --overlap 1 \
    --reg-filter 4 23 \
    --timeout 600 \
    --debug \
    --debug-dir data/processed/debug_refactored_v8
```

After each run, immediately score:
```bash
python scripts/score_extraction.py \
    --extracted data/processed/rules_refactored_v8.jsonl \
    --gold      data/gold_standard/gold_standard_regs_4_23.jsonl \
    --baseline  data/processed/rules_refactored_v6.jsonl \
    --output    reports/v8_score_report.json
```

Check these specific verifications after scoring:
```bash
# 1. Confirm no truncation at 300 chars
python3 -c "
import json
entries = [json.loads(l) for l in open('data/processed/debug_refactored_v8/pass2_pre_judge.jsonl') if l.strip()]
trunc = [(e['rule_id'], len(e.get('text','') or e.get('clause_text','')))
         for e in entries if len(e.get('text','') or e.get('clause_text','')) == 300]
print('Still at 300 chars (should be empty):', trunc)
"

# 2. Confirm no phantom (1) levels
python3 -c "
import json, re
rules = [json.loads(l) for l in open('data/processed/rules_refactored_v8.jsonl') if l.strip()]
phantom = [r['rule_id'] for r in rules if re.search(r'_\d+_[a-e]$', r['rule_id'])
           and not any(r['rule_id'].startswith(p) for p in ['ICDR_10_1','ICDR_15_1'])]
print('Potential phantom sub-levels:', phantom)
"

# 3. Confirm Reg 8 is recovered
python3 -c "
import json
rules = [json.loads(l) for l in open('data/processed/rules_refactored_v8.jsonl') if l.strip()]
print('Reg 8 IDs:', sorted(r['rule_id'] for r in rules if r['rule_id'].startswith('ICDR_8')))
"
```

---

## Longer-Term Roadmap (Post Regs 4–23)

1. **Expand to full 301 regulations** — pipeline generalizes, use `--skip-existing` / `--resume`
2. **31 empty `maps_to` rules** — targeted re-pass with CoT prompting
3. **Per-rule amendment linkage** — `strip_footnotes_with_linkage()` with correct context assignment
4. **APOLLO repair loop** in `verify_one.py` — biggest pending Lean improvement (5% → 40%+ proof success)
5. **Lean compiler error feedback** — pipe generated Lean through REPL, feed errors back to LLM judge
6. **Generator/Corrector split** — split `llm_generate_lean.py` into two distinct prompts
7. **BEq+ evaluation metric** — bidirectional equivalence check for Lean formalization quality

---

## Academic Positioning

This project is the **first formally verified regulatory compliance system for
financial documents**. Neither APOLLO nor Compliance-to-Code uses a formal proof
kernel (Lean) as the verification oracle — they use LLM judges or Python executors.

Target venues: ICAIL, FinNLP, or a formal methods venue.

The SEBI ICDR corpus (once complete) would be the first publicly available dataset
mapping real regulatory text to executable compliance logic in the financial sector.

---

*Last updated: May 9, 2026*
*Next session: Start with Priority 1 (find ALL [:300] caps) — zero risk, highest yield*

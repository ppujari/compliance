# Progress Update: SEBI ICDR Compliance Pipeline
## Rule Extraction - Footnote Handling, Linkage-Aware Amendment Enrichment & Quality Audit
**April 5 – April 25, 2026**

---

## 1. Overview

This round of work built directly on the MVP modularization and bug fixes completed in the April 5 report. Three areas were addressed:

1. **Footnote stripping** - correctly identifying and removing Indian statutory PDF footnotes (both inline citation markers and definition lines) that were being misidentified as regulation numbers by Pass 1.
2. **Amendment linkage enrichment** - upgrading the metadata enricher from a flat PDF-level footnote dump to per-rule, citation-position-aware amendment history.
3. **Output quality audit** - systematic review of `rules_refactored_v5.jsonl` (119 rules, Regulations 4–23) identifying structural, naming, and coverage issues.

Additionally, a strategic direction decision was made on pipeline scope: **extract all 301 regulations first, then build definitions and amendment layers** rather than enriching a partial corpus.

---

## 2. Footnote Stripping

### 2.1 Problem

Indian statutory PDFs embed amendment footnotes in two distinct patterns, both of which caused Pass 1 to misidentify footnote numbers as regulation numbers:

**Pattern A - Inline citation markers** appear mid-sentence, immediately before a `[` bracket containing the substituted text:

```
as on the date of 25[filing] the offer document
is a 26[wilful defaulter or a fraudulent borrower.]
29[(3) If an issuer has issued SR equity shares...]
```

The number is a footnote reference, not a regulation number. The bracket text is the current amended law. Pattern A caused Pass 1 to identify spurious "regulations" 25, 26, 27, 28, 29, 30, 31 and - most damagingly - to parse `29[(3)` as Regulation 29(3) with sub-clauses 29(3)(i) through 29(3)(ix), when the actual regulation is 6(3).

**Pattern B - Footnote definition lines** appear at the bottom of pages, starting at column zero, structurally identical to regulation headers:

```
25 Substituted by the Securities and Exchange Board of India...2019...
26 Substituted by the Securities and Exchange Board of India...2022...
27 Inserted by the Securities and Exchange Board of India...2025...
```

### 2.2 Fix Implemented

Two new regex patterns added to `regex_patterns.py`:

- `INLINE_FOOTNOTE_RE` - matches digits immediately before `[`, preceded by a word/punctuation character (mid-sentence position).
- `FOOTNOTE_DEF_RE` - matches a full footnote definition line: digit(s) at line start, followed by spaces, then one of `Substituted|Inserted|Renumbered|Omitted|Added|Amended`, followed by `by`.

A `strip_footnotes()` preprocessing function runs on raw PDF text **before** any Pass 1 processing. It removes Pattern B lines entirely and strips Pattern A numeric markers while preserving the bracketed amendment text (which is the current legal text). A blank-line cleanup pass follows.

The Pass 1 LLM system prompt (`_PASS1_SYSTEM`) was also updated with generic, regulation-agnostic instructions explaining both footnote patterns and warning the model not to treat bracketed numbers as regulation numbers.

### 2.3 Results

After applying the fix to the pages covering Regulations 4–23:

- Pass 1 no longer identifies footnote numbers 25–31 as regulations.
- `29[(3) If an issuer...]` is correctly parsed as belonging to Regulation 6(3), not Regulation 29(3).
- Bracket text `[filing]`, `[wilful defaulter or a fraudulent borrower.]`, `[(3) If an issuer...]` is preserved in the cleaned text passed to the LLM.
- Footnote definition lines are fully removed from the window text.

---

## 3. Sub-clause Continuation Across Page Boundaries

### 3.1 Problem

Regulation 6(3)(iv) has five lettered sub-clauses (a–e) that were split across a page boundary by the footnote 29/30 definition block. After stripping, sub-clauses `a` and `b` appear on one page, `c`, `d`, `e` on the next - with no visible parent regulation header on the second page. Pass 1 only recovered `b`, missing `a`, `c`, `d`, `e`.

The root cause is a finer-grained version of the continuation page problem: the existing `prev_window_regs` carryover carries top-level regulation numbers (e.g., `6`) but not sub-clause depth (e.g., `6(3)(iv)`).

### 3.2 Fix Implemented

Two additions to the main extraction loop in `llm_extract_rules.py`:

- `prev_window_last_subclause` - tracks the deepest `reg_number` returned by Pass 1 from the previous window, using bracket-character count as a depth proxy.
- `carryover_hint` - a natural-language hint injected into the Pass 1 **user prompt** (not system prompt) when `prev_window_last_subclause` is set, e.g.: *"The previous window ended mid-way through sub-clause 6(3)(iv). Lettered items at the start of this window with no visible parent are continuations of 6(3)(iv)."*

The `_PASS1_SYSTEM` was updated with generic rules for handling pages that open with lettered (`a.`, `b.`, `c.`) or roman numeral (`i.`, `ii.`, `iii.`) items without a visible parent regulation number, directing the model to use the carryover hint to assign them correctly. The Regulation 6-specific example that was previously hardcoded in the system prompt was replaced with a generic pattern description.

---

## 4. Amendment Linkage Enrichment

### 4.1 Previous State

`enrich_rule()` in `metadata_enricher.py` dumped the entire list of PDF-level footnote definitions onto every rule's `amendment_history` field - all 40 footnotes on every one of 119 rules, regardless of which footnote actually amended that rule.

### 4.2 Redesign

`strip_footnotes_with_linkage()` replaces the old `strip_footnotes()`. Before stripping, it scans for inline citation positions (Pattern A) and records:
- `footnote_number` - the citation number found
- `amended_text` - the bracketed text immediately following (the substituted content, up to 200 chars)
- `reg_context` - set to `""` (empty; see note below)

The old `strip_footnotes()` is retained as a compatibility wrapper calling the new function and discarding linkage records.

In the main extraction loop, after each page is processed, linkage records are merged into `accumulated_pdf_footnotes`: for each inline citation found, its `amended_text` is attached to the matching footnote definition entry under a `citations` list.

In `enrich_rule()`, `amendment_history` is now filtered to only footnotes whose `citations[].reg_context` matches the rule's `regulation_number` via prefix logic: a footnote applies to a rule if the rule's regulation number starts with the citation's context, or vice versa (parent inherits child amendments). Empty `reg_context` entries are skipped.

### 4.3 Correctness Fix: `current_reg_context`

The initial implementation passed `current_reg_context=prev_window_last_subclause` to `strip_footnotes_with_linkage()`. This was incorrect: `prev_window_last_subclause` is the deepest clause from the *previous* window, so footnotes found on a page containing Regulation 5(1)(c) text would be tagged with the prior window's context (e.g., `6(3)(iv)`).

The fix is to pass `current_reg_context=""` unconditionally. Linkage records still capture `footnote_number` and `amended_text` correctly; the empty context is safely filtered by `enrich_rule()`.

The prefix matching logic (`startswith`) was verified not to produce false positives for the `regulation_number` format produced by `enrich_rule()` (e.g., `6(3)(ii)`), because the parenthesised format provides natural boundaries.

---

## 5. Output Quality Audit: `rules_refactored_v5.jsonl`

A systematic audit of the 119-rule v5 output (Regulations 4–23) was conducted. Findings by severity:

### 5.1 Structural / Correctness Issues

| Issue | Detail |
|---|---|
| `ICDR_6_3` misattribution | The rule at line 36 with text about "general corporate purposes" and unidentified acquisition targets is not Regulation 6(3). The extractor assigned it the wrong regulation number due to context loss across windows. Requires manual verification against source text. |
| `ICDR_6_3_iv_b` before `ICDR_6_3_iv` | Sub-clause `b` (lines 18–19) appears before its parent `iv` in the file due to different window origins. Sub-clauses `a`, `c`, `d`, `e` are still missing - the continuation page fix is in progress. |
| Duplicate `ICDR_17_proviso` | Lines 95 and 99 share the same `rule_id` but are genuinely different clauses: line 95 is the main exception list, line 99 is the VC fund lock-in sub-condition. Should be `ICDR_17_proviso` and `ICDR_17_proviso_2`. |
| `ICDR_8` ordering | `ICDR_8_proviso` and `ICDR_8_2` appear before `ICDR_8` itself - same root cause as the `6(3)(iv)` ordering issue. |

### 5.2 Naming Issues

| Issue | Detail |
|---|---|
| `ICDR_14_1_proviso_2_that` | The word "that" leaked into the rule ID from "Provided further that". Should be `ICDR_14_1_proviso_2`. The `canonicalize_proviso_markers()` regex strips "Provided further" but leaves "that" when there is no space before it. |
| `_explanation` IDs flagged by malformed checker | The malformed ID checker pattern is too broad - `_explanation` is a legitimate ICDR structural marker. The checker should only flag `_xplanation` (truncated). |

### 5.3 Coverage Gaps

| Issue | Detail |
|---|---|
| 31 rules with empty `maps_to` (26% of output) | Some are legitimately unmappable (procedural rules). Others - `ICDR_6_3_i`, `ICDR_22`, etc. - should have fields. A targeted re-pass with CoT prompting is planned. |
| `6(3)(iv)` sub-clauses `a`, `c`, `d`, `e` missing | Only `b` recovered. Resolution in progress via carryover hint fix. |

### 5.4 Confirmed Good

- All top-level regulations 4–23 present.
- No JSON parse errors.
- No truncated `rovided` or `xplanation` IDs (proviso canonicalization fix holding).
- All 119 rules have `amendment_history` populated (though currently PDF-level, not per-rule - see Section 4).
- Confidence 0.9–1.0 for 97% of rules.
- All rules `accepted` status.

---

## 6. Strategic Direction: Full Extraction Before Definitions

A decision was made on pipeline scope and sequencing:

**Extract all 301 regulations across all 12 chapters first, then build the definitions and amendment layers.**

Rationale: The reglib design requires `definitions/Core.lean` to be built from a complete picture of what fields all rules actually reference. Extracting Regulation 2 definitions (60+ sub-clauses) before having the full rule corpus would mean building `Core.lean` on a partial foundation - many field types referenced by Chapters III–XI (Rights Issues, FPOs, QIPs, SME IPOs, etc.) would not yet be known. The full ICDR PDF (475 pages, 301 regulations) provides the complete input; the chapter structure is parallel (each chapter has Parts I–IV mirroring Chapter II) so the extraction pipeline generalises directly.

---

## 7. Next Steps

1. **Fix the three correctness issues** identified in the audit (duplicate `ICDR_17_proviso`, `ICDR_14_1_proviso_2_that`, `ICDR_6_3` misattribution) via a targeted post-processing script rather than re-extraction.
2. **Validate the carryover hint fix** on Regulation 6(3)(iv) pages - confirm sub-clauses `a`, `c`, `d`, `e` are recovered.
3. **Run full ICDR extraction** over all 475 pages / 301 regulations using the production pipeline with `--skip-existing` and `--resume` flags.
4. **Targeted re-pass on 31 empty `maps_to` rules** using chain-of-thought prompting.
5. **Integrate per-rule amendment linkage** into enrichment once the full corpus is extracted, using `strip_footnotes_with_linkage()` with correct context assignment.

# SEBI ICDR Compliance Pipeline — Full Progress Summary

> **Project:** Automated regulatory compliance verification for IPO filings (Red Herring Prospectuses) against SEBI ICDR regulations using LLMs for extraction and Lean 4 for formal verification.

---

## Phase 0 — Project Genesis & Architecture Design
**~Early 2026 (pre-January 31)**

### What was built
- Core pipeline concept: extract atomic rules from ICDR regulations → build issuer schema → extract evidence from RHP → generate Lean 4 code → run formal compliance checks.
- Seven-stage pipeline architecture:
  1. Extract atomic rules from ICDR regulations (with `maps_to` field hints)
  2. Build a provisional issuer schema from mappings
  3. Extract rule-anchored evidence from the RHP (table-aware)
  4. Reconcile field types using evidence (evidence-first, not LLM-guess-first)
  5. Freeze schema → generate partial issuer candidate
  6. Completeness pass over RHP using frozen schema
  7. Generate Lean code → run formal compliance checks
- Key early maturity decisions: structured `maps_to` over free-text notes; evidence-reconciled types over LLM-trusted types; tables as first-class evidence; deterministic guards around LLM outputs (judge loop, bounded retries, quarantine).

### Known rough edges at this stage
- Lean validation of generated code not yet working reliably
- Schema promotion/demotion tuning needed
- End-to-end hardening across diverse RHP formats not done

---

## Phase 1 — LLM Theorem Proving Research & Literature Review
**~Mid-January to Mid-March 2026**

### Chat: "LLM approaches to theorem proving and Lean Co-pilot integration"

- Reviewed LeanCopilot (LeanDojo framework) and adjacent literature.
- Found two high-priority papers with directly borrowable ideas:
  - **APOLLO** — generate-then-repair loop: sorrify failing Lean blocks → hit each sorry with `omega`/`decide`/`simp` → send surviving goals back to LLM → reassemble. Shows jump from ~5% to 40%+ Lean proof success with no fine-tuning.
  - **Compliance-to-Code** (Jiang et al., 2025) — code-centric compliance with a structured Compliance Unit (CU) schema mapping to subject/condition/constraint/contextual info.
  - **MA-LoT** — Generator/Corrector split for Lean generation.
  - **MIT VER-LLM framework** — three-component: knowledge acquisition → verification LLM → feedback loop. Our pipeline mirrors this with the key differentiator that our verification step targets Lean (formally sound oracle) rather than another LLM.
- Produced a formal literature review PDF (`paper_review.pdf`) with a 12-item actionable ideas list mapped to pipeline phases, a comparison table against adjacent papers, and positioning for publication at ICAIL, FinNLP, or a formal methods venue.

### Key academic positioning
- No publicly available dataset mapping real regulatory text to executable compliance logic in the financial sector exists. The SEBI ICDR corpus, once complete, would be the first.
- Pipeline is the **first formally verified** regulatory compliance system for financial documents (Lean kernel as formally sound oracle — neither APOLLO nor Compliance-to-Code has this).

---

## Phase 2 — Pipeline Review & New Capabilities Planning
**~Late March 2026**

### Chat: "Project summary review and improvement"
- Reviewed full pipeline architecture and codebase status.
- Decision: focus on **new capabilities** rather than hardening existing code.
- Identified four immediate high-impact changes borrowable from literature:
  1. **APOLLO-style repair loop** in `verify_one.py` — biggest impact item, not yet implemented
  2. **Lean compiler error feedback loop** — pipe generated Lean through REPL, feed type errors back to LLM judge
  3. **MA-LoT Generator/Corrector split** — split `llm_generate_lean.py` into two distinct prompts
  4. **Chain-of-thought (CoT) for rule extraction** — prompt LLM to reason step-by-step before emitting `maps_to`; confirmed by ARCV study to substantially outperform vanilla prompting

### Chat: "Critical ideas from the document"
- Prioritized the four APOLLO/CU ideas for immediate integration.
- Identified key RHP extraction problems:
  - `find_table_row` fuzzy matching needed (highest-leverage single RHP fix)
  - `March 31, YYYY` pattern missing from `FY_HEADER_RE` in `pdf_tables.py`
  - ICDR regulation cross-reference detection in `rule_anchored_extract.py`
  - Eligibility section detection heuristic (`ELIGIBILITY_SECTION_RE`)
- Discussed API vs. local model tradeoffs; decided on local models (Qwen 14B) for bulk extraction for privacy/cost, with frontier API as potential judge-loop fallback.

---

## Phase 3 — Superscript/Footnote Bug Discovery & Fix
**~Late March 2026**

### Chat: "Superscript regulation number parsing issue"
- **Bug found:** Indian statutory PDFs embed amendment footnotes as inline superscript numerals (e.g., `29[(3)` where `29` is a footnote reference). Pass 1 was treating `29` as Regulation 29, creating spurious `29(3)(i)` through `29(3)(ix)` rules when the actual regulation was 6(3).
- **Root cause:** `pre_identify_regulations()` regex had no line-start requirement or lookbehind exclusion for mid-sentence digits.
- **Fix designed:** Tighten `REG_HEADER_PATTERN` with line-start anchor and negative lookbehind `(?<![a-zA-Z0-9])`. Update Pass 1 LLM prompt with explicit footnote-vs-regulation instructions.

---

## Phase 4 — MVP Modularization & Metadata Enhancement
**~April 5, 2026**

### Chat: "Rule extraction and metadata enhancement for MVP"
- Graduated from POC to **production-grade rule store** targeting multi-jurisdiction deployment.
- Designed comprehensive metadata schema enrichment:

| Group | Fields Added |
|---|---|
| Identity & hierarchy | `regulation_framework`, `regulation_number`, `chapter`, `part` |
| Jurisdiction | `jurisdiction`, `regulator`, `country` |
| Classification | `rule_type`, `condition_type`, `compliance_actor`, `applicability_scope` |
| Amendment tracking | `original_effective_date`, `last_amended_date`, `amendment_history`, `is_current` |
| Cross-references | `references_regulations`, `referenced_by` |

- Modularized `llm_rextract_rules.py` into separate regex, LLM, and metadata functions.
- Strategic scope decision: **extract all 301 regulations first, then build definitions and amendment layers** (rather than enriching a partial corpus).
- Produced `reglib_design.tex/.pdf` — full design document for the regulation library.

---

## Phase 5 — Footnote Stripping, Amendment Linkage & v5 Audit
**April 5 – April 25, 2026**

### Progress File: `Progress_Apr25_2026.md` / `Progress_Apr26_2026.md`

#### 5.1 Footnote Stripping (implemented)
- Two footnote patterns fully addressed:
  - **Pattern A** (inline citation markers): digits immediately before `[` brackets, mid-sentence
  - **Pattern B** (footnote definition lines): `25 Substituted by SEBI...` at line start
- Two new regexes added to `regex_patterns.py`: `INLINE_FOOTNOTE_RE`, `FOOTNOTE_DEF_RE`
- `strip_footnotes()` preprocessing runs before Pass 1 on all raw PDF text
- Result: Pass 1 no longer identifies footnote numbers 25–31 as regulations; `29[(3)]` correctly parsed as Reg 6(3)

#### 5.2 Sub-clause Continuation Across Page Boundaries (implemented)
- `prev_window_last_subclause` — tracks deepest `reg_number` from previous window (bracket-count depth proxy)
- `carryover_hint` — natural-language hint injected into Pass 1 user prompt for continuation pages
- System prompt updated with generic (non-hardcoded) instructions for lettered/roman-numeral continuation items

#### 5.3 Amendment Linkage Enrichment (implemented)
- Replaced flat footnote dump with `strip_footnotes_with_linkage()` — per-rule, citation-position-aware amendment history
- `enrich_rule()` now filters `amendment_history` to only footnotes matching the rule's `regulation_number` via prefix logic
- Bug fixed: `current_reg_context` must be `""` (not `prev_window_last_subclause`) to avoid cross-window contamination

#### 5.4 v5 Quality Audit (conducted)
- **v5 output:** 119 rules, Regulations 4–23, `rules_refactored_v5.jsonl`
- Structural issues found: `ICDR_6_3` misattribution, `ICDR_6_3_iv_b` before parent, duplicate `ICDR_17_proviso`, `ICDR_8` ordering
- Naming issues: `ICDR_14_1_proviso_2_that` (word leak), `_explanation` over-flagged
- Coverage gaps: 31 rules with empty `maps_to` (26%), `6(3)(iv)` sub-clauses a/c/d/e missing
- Confirmed good: all top-level Regs 4–23 present, no JSON parse errors, 97% confidence 0.9–1.0

---

## Phase 6 — Gold Standard Creation & v6 Scoring
**~Late April 2026**

### Artifacts: `gold_standard_regs_4_23.jsonl`, `cursor_generate_reglib.md`

- Created **gold standard JSONL** with 143 rules for Regulations 4–23 with full metadata schema
- Built scoring framework computing TP/FN/FP per regulation + overall Recall/Precision/F1
- **v5 scores:** F1 = 70.5% (92 TP, 51 FN, 26 FP) — 119 rules extracted
- **v6 scores:** F1 = 81.3% (100 TP, 43 FN, 3 FP) — dramatic precision improvement but regression on Reg 6 due to over-tight anchoring
  - v6 improvement: +8 TP, -23 FP (precision: 78% → 97.1%)
  - v6 regression: Reg 6(3) lost ~7 TP vs v5 due to tighter anchoring incorrectly dropping valid SR equity share sub-clauses
- Metric targets established for next iteration: F1 > 90%, Recall > 85%, Precision > 95%

---

## Phase 7 — v7 Improvement Planning & Cursor Instructions
**April 26, 2026**

### Chats: "Context extraction from project chats", "V7 code improvements and scoring metrics"
### Files: `v7_improvement_plan.md`, `cursor_v7_improvements.md`, `cursor_v7_liverun_fixes.md`

Eight root causes diagnosed from `pass2_pre_judge.jsonl` and `coverage_summary.json`, accounting for all 43 missing rules:

| Fix | Issue | Rules Recovered | Effort |
|---|---|---|---|
| **Fix 1** | Reg 6(3) continuation pages: grandparent carryover hint + anchoring exemption for carryover context | 12 | Medium |
| **Fix 2** | Reg 7(3) amendment-inserted sub-reg `[(N)` pattern not caught by `REG_HEADER_RE` | 3 | Low |
| **Fix 3** | Reg 8 proviso-3 block: base-reg expansion (`8A` → also allow `8`) + explanation structural elements | 7 | Low |
| **Fix 4** | Deep provisos truncated at 300 chars: raise cap to 1200 chars + nested proviso split instruction in Pass 2 | 12 | Medium |
| **Fix 5** | `icdr_structure.json` chapter assignment: Regs 5(1)(a–d), 5(2) wrongly in Chapter XII | 0 (metadata) | Trivial |
| **Fix 6** | `ICDR_10_iv` wrong ID: add `KNOWN_ID_RENAMES` mapping to `ICDR_10_1_d_iv` | 1 | Trivial |
| **Fix 7** | Reg 12 main rule merged into proviso by Pass 2: add separation instruction | 1 | Low |
| **Fix 8** | Flag suspicious FPs (`ICDR_15_1_b_proviso`, `ICDR_16_1_a_proviso`) as `needs_review` | 0 (quality) | Trivial |

**Projected v7:** TP ≈ 136, FN ≈ 7, FP ≈ 0–1 → **F1 ≈ 93–95%**

#### Additional live-run fixes identified (from `cursor_v7_liverun_fixes.md`)
- `HEADING_NUMBER_RE` in `detect_allowed_regs` — works for any Reg 1–100 (covers Reg 4 missing issue)
- `REG_HEADER_RE` lowercase — covers headings starting with lowercase word, guarded by `> 100` filter
- `FOOTNOTE_TAIL_RE` Pattern C — matches any cross-page amendment fragment starting with amendment action words
- `split_merged_lettered_items` splitter — purely structural, splits on `b.`/`c.`/`d.`/`e.` boundaries

#### Scoring script packaged
```bash
python scripts/score_extraction.py \
    --extracted data/processed/rules_refactored_v7.jsonl \
    --gold      data/gold_standard/gold_standard_regs_4_23.jsonl \
    --baseline  data/processed/rules_refactored_v6.jsonl \
    --output    reports/v7_score_report.json
```
Exit code 0 = F1 ≥ 90% target met. `--baseline` flag prints delta column against v6.

---

## Phase 8 — Compliance Metrics & Academic Literature Integration
**~April 2026**

### Chat: "Critical ideas from the document" (continued)

Identified evaluation metrics from adjacent literature applicable to the pipeline:

| Metric | Source | Application |
|---|---|---|
| **Pass@k** | Compliance-to-Code | % of generated Lean files passing `lake build` on first (k=1) or k attempts |
| **CodeBLEU** | Compliance-to-Code | Lexical/syntactic/semantic similarity to reference solutions (useful once a verified corpus exists) |
| **Commentary Traceability** | Compliance-to-Code | % of input compliance units explicitly referenced in generated code comments |
| **BEq / BEq+** | FormalAlign (ICLR 2025) | Bidirectional equivalence check: proves each formalization from the other inside Lean; catches semantic misalignment that typecheck alone misses |

Key insight: typecheck alone is insufficient — a valid-in-Lean check function encoding the wrong threshold is worse than one that fails to compile. BEq+ correlates strongly with human judgment.

---

## Current State Summary (as of May 2, 2026)

| Dimension | Status |
|---|---|
| **Rule extraction (Regs 4–23)** | v6 complete, F1 = 81.3%; v7 fixes designed and Cursor instructions written |
| **Full ICDR extraction (301 regs)** | Planned; pipeline generalizes from Ch. II structure |
| **Gold standard** | 143 rules, Regs 4–23, complete |
| **Scoring script** | Designed; to be implemented as `scripts/score_extraction.py` |
| **Metadata schema** | Designed and partially implemented (jurisdiction, amendment history, classification) |
| **Lean code generation** | Structurally built; APOLLO repair loop not yet implemented |
| **RHP evidence extraction** | Table-aware; fuzzy matching improvements planned |
| **Publication positioning** | Paper review complete; contribution framing done |

---

## Immediate Next Steps

1. **Run v7 Cursor instructions** (`cursor_v7_improvements.md` + `cursor_v7_liverun_fixes.md`) and validate against gold standard
2. **Implement `scripts/score_extraction.py`** scoring script
3. **Expand extraction to full 301 regulations** using production pipeline with `--skip-existing`/`--resume`
4. **Targeted re-pass on 31 empty `maps_to` rules** with CoT prompting
5. **Implement APOLLO repair loop** in `verify_one.py` (biggest pending Lean improvement)
6. **Per-rule amendment linkage** integration using `strip_footnotes_with_linkage()` with correct context

---

*Compiled May 2, 2026 — Internal Reference*

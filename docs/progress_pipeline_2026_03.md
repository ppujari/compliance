# Pipeline progress — March 2026

This document records substantive engineering work completed across recent sessions: pipeline consolidation, rule-extraction quality, Lean generation hardening, and repository hygiene. For day-to-day commands, see [run_flow.md](run_flow.md).

---

## 1. Pipeline consolidation (Phases 0–4)

### Phase 0 — Shared utilities

- Added `scripts/utils/__init__.py` with shared helpers: `read_jsonl`, `write_jsonl`, `extract_first_json_block`, `parse_number`, `parse_bool`, `normalize_question_type`, `base_type_from_question_type`, `build_issuer_schema_from_questions`.
- Multiple scripts import from `scripts.utils` with a `try` / `except ImportError` fallback for direct execution.

### Phase 1 — Critical bug fixes

- **`schema_reconcile.py`**: Sub-pipeline stages call `rule_anchored_extract` and `type_infer` via direct function entry points instead of mutating `sys.argv`.
- **`type_infer.py`**: Reconciliation report rows use the real `provisional_type` per field (not a hardcoded placeholder).
- **`rule_anchored_extract.py`**: Table row matching uses overrides, dynamic keywords from field names, and token-overlap fallback so table evidence is not limited to a tiny hardcoded map.
- **`llm_generate_lean.py`**: Indentation and merge logic corrected; reconciled schema is the default issuer schema input.

### Phase 2 — Archive legacy scripts

- Moved superseded tools to `scripts/archive/` (e.g. old `infer_issuer_fields`, `promote_fields`, `build_facts_schema`, etc.) with `scripts/archive/README.md` explaining why.
- **`llm_generate_lean.py`** default `--issuer-schema-json` points at `data/processed/reconcile_run_v3/issuer_schema_reconciled.json` (evidence-first ordering: reconcile before Lean generation).

### Phase 3 — `extract_lean_to_json.py` as library

- Documented as a library module; `llm_generate_lean.py` always uses `--json-out` so JSON extraction is not a separate manual step.

### Phase 4 — Lean generators inside `verify_one.py`

- **`generate()`** entry points added to `gen_core_from_issuer_schema.py`, `gen_rules_lean.py`, and `gen_main_lean.py`.
- **`verify_one.py`** calls these in-process instead of spawning three Python subprocesses for core/rules/main generation. `lake build` and `lake exe compliance` remain subprocess calls.
- Fixed **`verify_one.py`**: removed an extra `--` before `lake exe compliance` arguments so `--in` / `--out` reach the executable.

### Other consolidation fixes (same period)

- **`gen_core_from_issuer_schema.py`**: Correct defaults for `Option` types (no double-wrap; sensible `.getD` defaults).
- **`gen_rules_lean.py`**: Safer extraction of `generatedRuleset`, incomplete `if-then` patching in `failReason`, expanded unsafe-expression detection and stubs, Lean 4 method rewrites (e.g. `.getD`, `==` in list lambdas).
- Windows-safe logging: replaced emoji / problematic Unicode in CLI help and prints where it broke `cp1252` consoles.

---

## 2. Rule extraction (`llm_extract_rules.py`)

### Problem themes addressed

1. **Missing regulations** — dense PDF windows and mixed clauses led to empty or partial extraction.
2. **Misattributed `rule_id`** — adjacent regulations in one window confused the model.
3. **`maps_to` quality** — generic field names, wrong `type_hint`, missing Bool hints.

### Fix 3 — Regulation anchoring (deterministic, no LLM)

- **`pre_identify_regulations(page_text)`** — Regex detects top-level headings like `N.` / `8A.` with footnote guards.
- **`validate_reg_anchoring(rule, visible_regs)`** — Soft check: if `rule_id`’s regulation is not in the regex-visible set, lower confidence and append `repair_notes` (do not hard-drop).
- **Prompt injection** — `REGULATION NUMBERS VISIBLE ON THESE PAGES: …` prepended to the extraction user prompt.
- **`strip_page_numbers(page_text)`** — Removes a bare 1–3 digit first line (printed page number) so Pass 1 and anchoring are not fooled by “14” / “15” at the top of a page.

### Fix 2 — CoT and few-shot for `maps_to`

- **`SYSTEM_PROMPT`** extended with **MAPS_TO REASONING** (three steps: constraint type, specific unique field name, `type_hint`).
- Second built-in few-shot: **Regulation 7(1)(b)** depository agreement → `has_depository_agreement` / `Bool`, wired into both `ollama_chat_json` and `ollama_generate_json` message / prompt construction.

### Fix 1 — Two-pass extraction (default)

- **Pass 1 — `identify_regulations()`** — Lightweight inventory: `reg_number`, `clause_text`, `span_hint`, `is_proviso`. No `maps_to` / typing.
- **`visible_regs` context** — Regex-detected parent regulation numbers are injected into the Pass 1 prompt so sub-clauses like `(3)(ii)` are emitted as `6(3)(ii)`, not bare `(3)(ii)`.
- **Pass 2 — `build_targeted_extraction_prompt()`** — One clause at a time with pre-validated `RULE_ID` / `LEAN_ID` and decomposition instructions before `maps_to`.
- **`--no-two-pass`** — Restores legacy single full-window call for A/B comparison.
- **Pass 1 debugging** — With `--debug`: `debug_raw` on the Pass 1 chat call and a log line for raw parsed result type and JSON snippet before coercion.

### Parser fix (both passes)

- **`coerce_rules_from_parsed()`** — If the top-level JSON is a **bare dict** with `rule_id` **or** `reg_number`, wrap it as a one-element list. This fixes:
  - Pass 2 returning a single object instead of an array.
  - Pass 1 returning a single clause object instead of an array.

---

## 3. Data layout hygiene

- **`data/processed/archive/`** — Retired loose artifacts (old model runs, debug schemas, superseded `rules_*.jsonl`, old `reconcile_run_v1` / `v2`, historical `judge_reports/`, etc.).
- **Active `data/processed/`** (at time of cleanup) kept for the current chain: e.g. `rules_judged_v2.jsonl`, `rules_and_fields_from_lean_v3.json`, `reconcile_run_v3/`, `issuer_facts_flat_v3*.json`, `compliance_report_v3.json`, `GeneratedRules_v3.lean`, and the latest `rules_debug_v3.jsonl` as needed.

Re-run extraction or reconciliation to repopulate anything you intentionally removed from the active folder.

---

## 4. Git / remote

- Consolidation work was committed and pushed to `main` on the project remote (see repo history around the “Consolidate pipeline…” commit).

---

## 5. How this doc relates to `run_flow.md`

| Document | Purpose |
|----------|---------|
| **[run_flow.md](run_flow.md)** | Ordered commands, paths, evidence-first steps. |
| **This file** | *Why* things changed and *what* was fixed architecturally. |

When you adopt new rule outputs (e.g. `rules_judged_v4.jsonl`), update `run_flow.md` paths and any pinned filenames in scripts or docs to match.

---

## 6. Suggested verification checklist

1. **Rules**: Run `llm_extract_rules.py` with your model; confirm Pass 1 logs show identified clauses when `--debug` is on; spot-check `rule_id` prefixes on cross-page regulations.
2. **Reconcile**: `schema_reconcile.py` → `issuer_schema_reconciled.json` present and valid types only.
3. **Lean**: `llm_generate_lean.py` with `--json-out` → `lake build` → `scripts/verify_one.py` → `compliance_report_*.json`.

---

*Last updated: March 2026.*

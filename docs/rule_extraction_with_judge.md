# Rule Extraction with Critic/Judge Loop (PDF → rules.jsonl)

This doc describes the **rule extraction pipeline** implemented in `scripts/llm_extract_rules.py`, including the **critic/judge loop** (generator → validators → judge → targeted regeneration → quarantine).

The output is a `rules_*.jsonl` suitable for downstream deterministic schema + Lean generation.

---

## Summary of the pipeline

For each sliding **PDF window** (pages `[start..start+window)`):

1. **Generator LLM** produces candidate rules (JSON) for that window.
2. **Deterministic normalization** standardizes ids and fields (e.g., `rule_id` → `ICDR_*`).
3. **Deterministic validators** reject obvious failures (schema, id format, missing source, span alignment).
4. **LLM judge** evaluates each candidate rule against a **fixed rubric** and emits:
   - scores per criterion
   - failure_modes
   - fix_instructions
5. **Selective regeneration**: only failing `rule_id`s are regenerated (bounded rounds).
6. **Re-judge** regenerated rules.
7. **Accept or quarantine**:
   - accepted rules are written normally
   - still-failing rules after max rounds are written with `status="quarantined"` and `maps_to=[]`

---

## Output format (rules.jsonl)

Each line in `rules.jsonl` is a JSON object validated against `data/schema/rules_schema.json`.

Key fields:
- **`rule_id`**: normalized to `ICDR_<reg>[_<clause>[_<subclause>]]`
- **`domain`**: typically `"SEBI_ICDR"`
- **`title`**, **`text`**
- **`lean_id`**: `rule_<...>` derived from `rule_id`
- **`maps_to`**: optional stable mapping targets, may be empty for procedural/uncheckable rules
- **`source`**:
  - `pdf`
  - `pages` (1-based page numbers for the window)
  - `reg` (optional)
  - `span_hint` (≤120 chars, direct quote substring)
- **`status`** *(optional)*:
  - `"accepted"` *(implicit if missing)*
  - `"quarantined"` *(explicit when a rule fails after max regen rounds)*

---

## Deterministic validators

The following validators run in code (no LLM):

### Required fields
`validate_required_fields(rule) -> list[str]`
- Ensures `rule_id`, `domain`, `title`, `text`, `lean_id`, and `source` exist.
- Ensures `source.pdf`, `source.pages`, `source.span_hint` exist.

### Rule id format
`validate_rule_id_format(rule_id) -> bool`
- Must match: `ICDR_<reg>[_<n>]*[_<a>]` (digits and optional lowercase letter suffix)

### maps_to validity
`validate_maps_to(rule) -> list[str]`
- `maps_to` must be an array of objects
- each `field` must be snake_case (`^[a-z][a-z0-9_]*$`)
- `type_hint` (if present) must be one of:
  - `Bool | Nat | List Nat | String | OptionBool | OptionNat | OptionListNat | OptionString`

### Source alignment
`validate_source(rule, chunk_text) -> list[str]`
- `span_hint` length must be ≤120
- `span_hint` must appear in `chunk_text`
  - strict mode: whitespace-normalized containment
  - lenient mode: unicode/punctuation-insensitive containment
  - fuzzy fallback (difflib) is used as a last resort

### Duplicate detection (within a window)
Rules are consolidated per `rule_id` inside a window using a deterministic “best item” chooser (confidence/length/span_hint/repair penalties).

---

## Judge output schema (per rule)

The judge MUST output a JSON array of objects matching:

```json
{
  "rule_id": "ICDR_7_1_a",
  "scores": {
    "atomicity": 0.0,
    "fidelity": 0.0,
    "completeness": 0.0,
    "maps_to_quality": 0.0,
    "source_alignment": 0.0
  },
  "overall": 0.0,
  "failure_modes": ["NOT_ATOMIC"],
  "fix_instructions": "Split clause; keep numeric thresholds; maps_to should include applied_to_stock_exchange:Bool"
}
```

Notes:
- The rubric is **deterministic in code** (weights/thresholds are not invented by the judge).
- The judge provides **fix instructions**, but the pass/fail decision is computed in code.

---

## Judge rubric + pass criteria

### Rubric criteria (0..1 each)
- **atomicity**: one atomic legal requirement (not bundled)
- **fidelity**: matches clause text; no hallucinations
- **completeness**: includes thresholds/units/exceptions present in text
- **maps_to_quality**: mappings are appropriate and typed, or empty if procedural
- **source_alignment**: clearly from provided chunk; span_hint is a direct quote

### Deterministic weights (hard-coded)
- fidelity: 0.30
- atomicity: 0.25
- completeness: 0.20
- maps_to_quality: 0.15
- source_alignment: 0.10

Overall score is computed in code:
\[
overall = \sum_k score_k \cdot weight_k
\]

### Pass thresholds (default)
A rule passes if:
- **overall ≥ 0.75**
- **fidelity ≥ 0.70**
- and there are **no hard validation failures**

---

## Selective regeneration (targeted)

Only failing `rule_id`s are regenerated for the SAME chunk.

### Constraints enforced
The regen prompt requires:
- output exactly **ONE JSON object**
- preserve the same `rule_id`
- preserve numeric thresholds and units
- preserve `source.pdf` and `source.pages`
- choose a `source.span_hint` that is a **direct quote substring** of the chunk (≤120 chars)
- if procedural/uncheckable: set `maps_to: []`

### Bounded loop
- `--max-regen-rounds` (default 2)
- `--max-regen-per-window` (default 8)

---

## Quarantine behavior

If a rule still fails after max regen rounds:
- `status` is set to `"quarantined"`
- `maps_to` is cleared to `[]`
- `notes` is appended with a failure summary
- `text` and `source` are retained (so coverage is preserved without infinite retries)

---

## CLI flags

### Core extraction flags
- `--pdf <path>`
- `--out <rules.jsonl>`
- `--model <ollama-model>`
- `--window <n>` / `--overlap <n>`
- `--reg-filter <START> <END>` *(optional)*
- `--dedupe` *(optional)*
- `--span-mode strict|lenient`
- `--no-anchoring` *(optional)*
- `--timeout <seconds>`
- `--endpoint auto|chat|generate`
- `--debug` / `--debug-raw`

### Judge flags
- `--judge` *(enable critic/judge loop)*
- `--judge-model <ollama-model>` *(defaults to `--model`)*
- `--max-regen-rounds <n>` *(default 2)*
- `--max-regen-per-window <n>` *(default 8)*
- `--judge-overall-threshold <float>` *(default 0.75)*
- `--judge-fidelity-threshold <float>` *(default 0.70)*
- `--judge-report-out <path>` *(optional JSONL per-window judge/validation dump)*

---

## Example command (PowerShell)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/llm_extract_rules.py --pdf data/input/ICDR_rules_4_22.pdf --out data/processed/rules_judged.jsonl --model mistral:7b-instruct --judge --judge-model mistral:7b-instruct --max-regen-rounds 2 --max-regen-per-window 8 --judge-overall-threshold 0.75 --judge-fidelity-threshold 0.70 --judge-report-out data/processed/judge_report.jsonl --window 4 --overlap 2 --no-anchoring --span-mode lenient --timeout 600 --debug
```


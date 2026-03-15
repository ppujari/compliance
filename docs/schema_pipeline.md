# Deterministic Schema + Evidence Pipeline (Rules → Facts → Reports)

This repo supports a **2-stage compliance workflow**:

1. **Rule extraction**: extract atomic ICDR rules into a `rules_*.jsonl` file.
2. **Deterministic schema pipeline (no LLMs)**: from a single `rules_*.jsonl`, generate:
   - a stable **facts schema** (`IssuerFacts` + `OfferFacts`)
   - a complete **RuleEvidence schema** (one slot per rule)
   - deterministic **reports** diagnosing mapping gaps and promotions/demotions

The goal is to keep the **core schema tight and stable**, even if some rules are messy, by pushing low-confidence items into **evidence-only** buckets.

---

## Inputs and outputs

### Input
- `data/processed/rules_*.jsonl`: JSONL where each line is a rule object (validated against `data/schema/rules_schema.json`).

### Outputs (deterministic)
- `mapping_report.json` (or `data/processed/mapping_report.json`)
- `issuer_fields.json` (or `data/processed/issuer_fields.json`)
- `data/processed/rule_evidence_schema.json`
- `data/processed/facts_schema.json`
- `promotion_report.json` (or `data/processed/promotion_report.json`)

---

## Script overview

### 0) (Optional) Extract rules with an LLM

**Script**: `scripts/llm_extract_rules.py`  
**Purpose**: PDF → `rules.jsonl` (LLM-assisted extraction)

Key behaviors:
- Reads PDF pages (PyMuPDF preferred; pdfminer fallback)
- Calls Ollama (`/api/chat` or `/api/generate`) with `format="json"`
- Parses a variety of model output shapes:
  - `[{...}, ...]`
  - `{"rules":[...]}`
  - `{"items":[...]}`
  - dict-of-`rule_*` (values as objects)
  - dict with `subrules` (flattened into multiple rule objects)
- Validates/writes **schema-clean** objects only (because schema uses `additionalProperties: false`)
- Debug prints:
  - window length (`chars=...`)
  - accepted rules (`[ACCEPT] ...`)
  - written rules (`[WRITE] ...`)

Common flags:
- `--no-anchoring`: disables regulation-number anchoring (useful when PDF text headers are messy)
- `--debug --debug-raw`: detailed model + pipeline logs

---

## Deterministic pipeline (no LLM calls)

### 1) Score/diagnose “Map to …” quality

**Script**: `scripts/score_rule_to_schema.py`  
**Output**: `mapping_report.json`

What it computes:
- `total_rules`
- `map_to_rules_count` (rules containing `Map to ...` in notes)
- `map_parse_success_count`
- `map_parse_failures`: `{rule_id, notes, dropped_tokens, reason}`
- `fields_proposed_from_map_to`: sorted unique list
- `unmapped_rules`: rule_ids with no `Map to ...`
- optional comparison vs an existing `issuer_fields.json` (Jaccard + diffs)

Why it matters:
- This is your **deterministic “Rule Mapping Judge”**: a crisp report each run showing where mapping is failing and why.

---

### 2) Infer stable issuer fields (with debug metadata)

**Script**: `scripts/infer_issuer_fields.py`  
**Output**: `issuer_fields.json`

Key behaviors:
- Extracts candidate field names from `notes` (looks for `Map to ...`)
- Normalizes tokens (parens/constraints/punct/whitespace → clean identifiers)
- Deterministic:
  - sorts rules by `rule_id`
  - sorts output fields alphabetically
- Emits debug metadata per field:
  - `from_rules`
  - `raw_tokens_seen`
  - `normalization_applied`

Why it matters:
- This is the primary step to keep **field inference tight** and reproducible.

---

### 3) Guarantee RuleEvidence coverage for *all* rules

**Script**: `scripts/generate_rule_evidence_schema.py`  
**Output**: `data/processed/rule_evidence_schema.json`

Behavior:
- Creates one evidence template per `rule_id`:
  - `status_type: enum(present, absent, unclear)`
  - `evidence: [{page:null, quote:null}]`
  - `extracted_values: {}`

Why it matters:
- Ensures **N rules ⇒ N evidence slots**, so you never lose coverage due to schema pruning.

---

### 4) Split facts into IssuerFacts + OfferFacts

**Script**: `scripts/build_facts_schema.py`  
**Output**: `data/processed/facts_schema.json`

Heuristic routing:
- If field name contains offer/issue/listing/allocation/price-band/lot/qib/etc → **OfferFacts**
- Else → **IssuerFacts**

Why it matters:
- Keeps the facts model organized without needing an LLM judge.

---

### 5) Promotion scoring: keep core schema tight

**Script**: `scripts/promote_fields.py`  
**Outputs**:
- `promotion_report.json`
- overwrites `facts_schema.json` (demotes low-score fields)

Scoring (deterministic):
- +2 if field appears in ≥2 rules
- +2 if numeric threshold/comparator context detected near the field
- -3 if token is generic (`conditions`, `misc`, `as_applicable`, `other`)
- -2 if field appears only in parentheses/notes context (heuristic)

Why it matters:
- Prevents weak/noisy fields from polluting the core facts schema while still preserving rule coverage via RuleEvidence.

---

## Recommended run order (one command sequence)

From repo root:

```bash
# 1) Diagnose "Map to ..."
python scripts/score_rule_to_schema.py \
  --rules_jsonl data/processed/rules.jsonl \
  --out data/processed/mapping_report.json

# 2) Infer stable fields (issuer schema)
python scripts/infer_issuer_fields.py \
  --rules data/processed/rules.jsonl \
  --out data/processed/issuer_fields.json

# 3) Ensure 1 evidence slot per rule
python scripts/generate_rule_evidence_schema.py \
  --rules_jsonl data/processed/rules.jsonl \
  --out data/processed/rule_evidence_schema.json

# 4) Split IssuerFacts vs OfferFacts
python scripts/build_facts_schema.py \
  --rules_jsonl data/processed/rules.jsonl \
  --issuer_fields_json data/processed/issuer_fields.json \
  --out data/processed/facts_schema.json

# 5) Promotion scoring and prune facts schema
python scripts/promote_fields.py \
  --rules_jsonl data/processed/rules.jsonl \
  --facts_schema_json data/processed/facts_schema.json \
  --rule_evidence_schema_json data/processed/rule_evidence_schema.json \
  --out data/processed/promotion_report.json
```

---

## Regression/stability test

**Test**: `tests/test_schema_stability.py`

What it checks:
- Running issuer field inference twice yields identical field sets
- Every `rule_id` has a RuleEvidence entry
- All field names are valid Lean identifiers

Note: requires `pytest` (`python -m pip install pytest`).

---

## How to interpret the reports

### `mapping_report.json`
- **High `map_parse_failures`**: fix rule authoring (notes) or token normalization rules.
- **Many `unmapped_rules`**: rules are evidence-only (fine), or you need better `maps_to` upstream.

### `promotion_report.json`
- **Demoted fields**: not reliable enough to be core schema; they remain covered via RuleEvidence.
- **Kept fields**: stable reusable facts suitable for extraction and downstream typing.





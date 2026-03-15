## Issuer Schema Reconciliation Pipeline (RHP‑anchored)

This pipeline builds a stable issuer schema by combining rule mappings with **evidence extracted from the Red Herring Prospectus (RHP)**. It is designed to fix incorrect `type_hint` values and prevent schema drift.

---

### Overview (high level)

1) **Rules extraction** → `rules.jsonl`
2) **Provisional schema** from `maps_to` (conservative types)
3) **Rule‑anchored evidence extraction** from RHP (tables + text)
4) **Deterministic type reconciliation** (optionally LLM judge on ambiguous fields)
5) **Reconciled schema** → used for issuer extraction + Lean

---

## Stage 1 — Rules extraction

**Input:** `data/processed/rules_judged_v2.jsonl`  
**Key fields:** `rule_id`, `text`, `maps_to[].field`, `maps_to[].type_hint`

We treat `maps_to.field` as *mostly correct*, but we **do not trust `type_hint`**.

---

## Stage 2 — Provisional schema (conservative)

Script: `scripts/schema_reconcile.py`  
Output: `provisional_schema.json`

Rules:

- If rule text mentions “preceding three years” → `Option (List Nat)`
- If field looks boolean (`has_`, `is_`, `no_`) → `Option Bool`
- Numeric‑looking fields → `Option Nat`
- Otherwise → `Option String`

This avoids locking into a wrong type before seeing evidence.

**Example (provisional):**

```json
[
  { "field": "operating_profits", "type": "Option (List Nat)" },
  { "field": "net_worth", "type": "Option (List Nat)" },
  { "field": "agreement_with_depository", "type": "Option Bool" }
]
```

---

## Stage 3 — Rule‑anchored evidence extraction (RHP)

Script: `scripts/rule_anchored_extract.py`  
Inputs:

- rules JSONL
- RHP PDF
- optional `tables_store.json` from `scripts/pdf_tables.py`

Output: `evidence_store.jsonl`

Evidence extraction attempts **table first**, then falls back to text/LLM.

### Table‑usage proof (debug fields)

Every evidence record includes:

- `table_hit_used: true|false`
- `tables_loaded_count: <int>`
- `table_source_id: "pX_tY" | null`
- `evidence.source: "table:pX_tY" | "text"`

Additionally, `schema_reconcile.py` writes `run_debug.json` with:

```json
{ "tables_loaded": 12, "table_evidence_records": 9 }
```

### Table‑aware extraction

If a row is found in an RHP table (e.g., “Operating profit”), we emit:

```json
{
  "rule_id": "ICDR_6_1_b",
  "field": "operating_profits",
  "value_raw": "29,532.9 | 31,004.2 | 28,115.0",
  "value_candidates": { "List Nat": [29532, 31004, 28115] },
  "evidence": {
    "page": 112,
    "quote": "Operating profit: 29,532.9 | 31,004.2 | 28,115.0",
    "source": "table:p112_t2"
  }
}
```

**Numeric policy:** remove commas, **drop decimals**, keep units as presented.

**Number parsing rules (strict):**

- Parse with `[\d,]+(\.\d+)?`
- Strip commas
- Drop decimals deterministically (floor)
- **Never split lists on commas** (lists only from table columns or explicit separators like `; | /`)

---

## Stage 4 — Deterministic type reconciliation

Script: `scripts/type_infer.py`  
Input: `evidence_store.jsonl`  
Output: `type_reconcile_report.json` + `issuer_schema_reconciled.json`

Decision rules:

- If table evidence exists and `ListNat_parse_rate > 0` → **List Nat**
- Else if strong boolean indicators + Bool parse rate → **Bool**
- Else if Nat parse rate high → **Nat**
- Else → **String**

Optionality:

- If missing rate > 0.3 → wrap in `Option ...`
- If `missing_rate == 1.0` → force `Option String` and mark `inactive_field = true`

**Example (report snippet):**

```json
{
  "field": "operating_profits",
  "provisional_type": "Option Nat",
  "final_type": "Option (List Nat)",
  "metrics": {
    "Nat_parse_rate": 0.2,
    "ListNat_parse_rate": 0.9,
    "missing_rate": 0.1
  },
  "table_evidence_count": 2,
  "example_table_row": { "label": "Operating profit", "values": ["29,532.9", "31,004.2", "28,115.0"] },
  "reason": "list_indicator"
}
```

### Strict type validation (post‑reconcile)

Final types are validated against:

```
Bool
Nat
List Nat
String
Option Bool
Option Nat
Option (List Nat)
Option String
```

Invalid types are replaced with:

- provisional deterministic type if available
- otherwise `Option String`

---

## Stage 5 — Reconciled schema (frozen)

Output: `issuer_schema_reconciled.json`

This is the **ground truth schema** used for:

- issuer extraction from RHP (`extract_issuer_from_rhp.py`)
- Lean generation
- downstream validation

---

## Stage 6 — Issuer extraction (schema‑consistent)

Script: `scripts/extract_issuer_from_rhp.py`

Use the reconciled schema:

```bash
python scripts/extract_issuer_from_rhp.py \
  --pdf data/POC/POC_red_herring.pdf \
  --questions-json data/processed/rules_and_fields_from_lean_v3.json \
  --schema-reconciled data/processed/reconcile_run_v2/issuer_schema_reconciled.json \
  --out data/processed/issuer_facts_extracted_v3.json \
  --per-field --retrieval keyword --topk 2 --provenance
```

---

## Stage 7 — Issuer candidate aggregation (from reconciliation)

`schema_reconcile.py` also emits:

- `issuer_candidate.json` (best value per field with provenance)
- `issuer_candidate_conflicts.json` (ties/mismatches)

Selection rules:

- prefer **table evidence** over text
- then prefer **higher confidence**

Expected examples:

```
operating_profits: List Nat
net_worth: List Nat
net_tangible_assets: List Nat
```

---

## Suggested run order

1) `llm_extract_rules.py` → rules JSONL  
2) `schema_reconcile.py` → reconciled schema + evidence store  
3) `llm_generate_lean.py` → Lean rules  
4) `extract_issuer_from_rhp.py` → issuer facts  
5) `lake build` → compile gate


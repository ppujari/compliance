# Step-by-step Run Flow  (Evidence-first: RHP → Schema → Lean → Verification)

> **Consolidated pipeline (post Phase 2/3 cleanup).**
> Active scripts: 13. Archived/library-only scripts: 8.
> Key ordering change: `schema_reconcile.py` runs **before** `llm_generate_lean.py`
> so the LLM uses evidence-based types, not heuristic guesses.

---

## Inputs required

| Input | Path | Notes |
|-------|------|-------|
| ICDR rules PDF | `data/input/ICDR_rules_4_22.pdf` | Source regulation document |
| RHP PDF | `data/input/<rhp>.pdf` | Red Herring Prospectus |
| Tag | e.g. `v3` | Short suffix for all output files |

---

## Step 1 — Extract rules from ICDR PDF  (LLM)

> Skip if you already have a `rules_*.jsonl`.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/llm_extract_rules.py `
  --pdf data/input/ICDR_rules_4_22.pdf `
  --out data/processed/rules_v3.jsonl `
  --model mistral:7b-instruct `
  --window 4 --overlap 2 `
  --endpoint chat --timeout 600 `
  --fewshot data/input/fewshots_icdr_5.json
```

Output: `data/processed/rules_v3.jsonl`

---

## Step 2 — Schema reconciliation from RHP evidence  (deterministic)

This is the **first major step**. It extracts values from the RHP, infers types
from evidence, and writes the canonical `issuer_schema_reconciled.json`.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/schema_reconcile.py `
  --rules-jsonl data/processed/rules_judged_v2.jsonl `
  --rhp-pdf data/input/<rhp>.pdf `
  --out-dir data/processed/reconcile_run_v3
```

Outputs in `data/processed/reconcile_run_v3/`:
- `issuer_schema_reconciled.json` — canonical field+type schema (used by Step 3)
- `issuer_candidate.json` — extracted issuer values with provenance
- `type_reconcile_report.json` — per-field type inference report
- `evidence_store.jsonl` — all raw evidence records

---

## Step 3 — Generate Lean rules + JSON  (LLM, schema-informed)

`schema_reconcile.py` **must run first** so the LLM receives evidence-backed types.
`--json-out` is always passed; `extract_lean_to_json.py` runs as a library internally
and does not need to be invoked separately.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/llm_generate_lean.py `
  --in data/processed/rules_judged_v2.jsonl `
  --out data/processed/GeneratedRules_v3.lean `
  --model mistral:7b-instruct `
  --batch-size 10 --limit 0 --progress `
  --issuer-schema-json data/processed/reconcile_run_v3/issuer_schema_reconciled.json `
  --json-out data/processed/rules_and_fields_from_lean_v3.json
```

Outputs:
- `data/processed/GeneratedRules_v3.lean` — raw LLM Lean output
- `data/processed/rules_and_fields_from_lean_v3.json` — rules + issuer questions + schema

---

## Step 4 — Postprocess rules+fields JSON  (deterministic)

Normalises IDs, types, dedupes questions, and stubs unsafe check expressions.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/postprocess_rules_and_fields.py `
  --in data/processed/rules_and_fields_from_lean_v3.json `
  --out data/processed/rules_and_fields_post_v3.json `
  --report data/processed/rules_and_fields_post_v3_report.json
```

Output: `data/processed/rules_and_fields_post_v3.json`

---

## Step 5 — Flatten issuer candidate for Lean input  (deterministic)

Converts the rich `issuer_candidate.json` to a flat `{field: value}` JSON
that the Lean executable can parse.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/flatten_issuer_candidate.py `
  --candidate data/processed/reconcile_run_v3/issuer_candidate.json `
  --schema    data/processed/reconcile_run_v3/issuer_schema_reconciled.json `
  --report    data/processed/reconcile_run_v3/type_reconcile_report.json `
  --out       data/processed/issuer_facts_flat_v3.json
```

Output: `data/processed/issuer_facts_flat_v3.json`

---

## Step 6 — Generate Lean artifacts  (deterministic)

### 6a — Core module (Issuer + ComplianceRule structs)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/gen_core_from_issuer_schema.py `
  --issuer-schema data/processed/reconcile_run_v3/issuer_schema_reconciled.json `
  --out Src/Core_auto.lean `
  --namespace Src.Core_auto
```

### 6b — Rules module (wraps LLM Lean output)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/gen_rules_lean.py `
  --rules_fields data/processed/rules_and_fields_from_lean_v3.json `
  --core Src.Core_auto `
  --tag judged_v2 `
  --out Src/GeneratedRules_judged_v2.lean
```

### 6c — Main entrypoint

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"
python scripts/gen_main_lean.py `
  --core  Src.Core_auto `
  --rules Src.GeneratedRules_judged_v2 `
  --out   Src/Main_v2.lean
```

---

## Step 7 — Build and verify  (Lean / lake)

```powershell
$env:PATH += ";C:\Users\sauna\.elan\bin"
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"

# Build
lake build

# Run compliance check
python scripts/verify_one.py `
  --tag judged_v2 `
  --issuer data/processed/issuer_facts_flat_v3.json `
  --out data/processed/compliance_report_v3.json `
  --rules-fields data/processed/rules_and_fields_from_lean_v3.json `
  --lean-in data/processed/GeneratedRules_v3.lean `
  --core-module Src.Core_auto `
  --core-out Src/Core_auto.lean `
  --skip-gen
```

Output: `data/processed/compliance_report_v3.json`

---

## Pipeline at a glance

```
ICDR PDF ──► llm_extract_rules.py ──► rules_judged_v2.jsonl
                                              │
RHP PDF ─────────────────────────► schema_reconcile.py ──► issuer_schema_reconciled.json
                                              │                      │
                                              │              flatten_issuer_candidate.py
                                              │                      │
                                              ▼                      ▼
                              llm_generate_lean.py         issuer_facts_flat_v3.json
                              (uses reconciled schema)             │
                                              │                    │
                                              ▼                    │
                              postprocess_rules_and_fields.py      │
                                              │                    │
                              ┌───────────────┴──────────────┐     │
                              ▼               ▼              ▼     │
                    gen_core_from_    gen_rules_lean.py  gen_main_lean.py
                    issuer_schema.py       │                   │
                              │           │                   │
                              └───────────┴──── lake build ───┘
                                                    │
                                           verify_one.py
                                                    │
                                    compliance_report_v3.json
```

---

## Archived scripts (not in active pipeline)

See `scripts/archive/README.md` for the full list and rationale.
Scripts archived: `build_facts_schema.py`, `promote_fields.py`,
`score_rule_to_schema.py`, `generate_rule_evidence_schema.py`,
`infer_issuer_fields_with_llm.py`, `postprocess_rules.py`, `infer_issuer_fields.py`.

`extract_lean_to_json.py` is kept as a **library module** used internally by
`llm_generate_lean.py` (via `--json-out`). Do not run it as a standalone step.

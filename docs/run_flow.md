# Step-by-step Run Flow (Rules → Schema → Lean → Extraction)

This is the recommended end-to-end runbook for the current repo, assuming **ground truth schema comes from extracted rules** (`maps_to`), not from `Main.lean`.

The flow has 3 phases:

1. **Rules JSONL** (from PDF or existing rules file)
2. **Deterministic schema pipeline** (issuer fields, facts, evidence, promotion)
3. **Lean artifacts + execution** (Core, Rules, Main; build + run)

---

## 0) Inputs you need

- **Rules JSONL**: `data/processed/rules_<tag>.jsonl`
  - Each line is a rule dict, ideally with `maps_to: [{field, type_hint?, constraints_text?}]`.
- **Tag**: a short name for outputs, e.g. `debug_v8`

Example:
- rules file: `data/processed/rules_debug_v3.jsonl`
- tag: `debug_v8`

---

## 1) (Optional) Generate rules JSONL from PDF (LLM)

If you already have a `rules_*.jsonl`, skip this.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/llm_extract_rules.py --pdf data/input/ICDR_rules_4_22.pdf --out data/processed/rules_debug_v3.jsonl --model llama3:8b --window 4 --overlap 2 --no-anchoring --debug --endpoint chat --timeout 600 --fewshot data/input/fewshots_icdr_5.json
```

---

## 2) Deterministic schema pipeline (no LLM)

### 2.1 Mapping diagnostics (optional but recommended)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/score_rule_to_schema.py --rules_jsonl data/processed/rules_debug_v3.jsonl --out data/processed/mapping_report_debug_v8.json
```

### 2.2 Infer issuer fields from `maps_to` (stable)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/infer_issuer_fields.py --rules data/processed/rules_debug_v3.jsonl --out data/processed/issuer_fields_debug_v8.json
```

### 2.3 Split into IssuerFacts / OfferFacts

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/build_facts_schema.py --rules_jsonl data/processed/rules_debug_v3.jsonl --issuer_fields_json data/processed/issuer_fields_debug_v8.json --out data/processed/facts_schema_debug_v8.json
```

### 2.4 Generate RuleEvidence schema (one slot per rule)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/generate_rule_evidence_schema.py --rules_jsonl data/processed/rules_debug_v3.jsonl --out data/processed/rule_evidence_schema_debug_v8.json
```

### 2.5 Promotion scoring (core + extended)

This produces:
- `facts_schema_core_<tag>.json` (tight core)
- `facts_schema_extended_<tag>.json` (all or non-generic)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/promote_fields.py --rules_jsonl data/processed/rules_debug_v3.jsonl --facts_schema_json data/processed/facts_schema_debug_v8.json --rule_evidence_schema_json data/processed/rule_evidence_schema_debug_v8.json --out data/processed/promotion_report_debug_v8.json --out-core data/processed/facts_schema_core_debug_v8.json --out-extended data/processed/facts_schema_extended_debug_v8.json --extended-mode non_generic
```

---

## 3) Lean generation pipeline

There are two supported ways to generate Lean rules:

### Option A (recommended for now): LLM Lean generation → postprocess → deterministic Lean modules

#### 3.1 Generate Lean rules + rules_and_fields JSON

Important: pass `--issuer-schema-json` so the model doesn’t invent Issuer fields.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/llm_generate_lean.py --in data/processed/rules_debug_v3.jsonl --out GeneratedRules_debug_v8.lean --model llama3:8b --batch-size 10 --limit 0 --progress --issuer-schema-json data/processed/issuer_fields_debug_v8.json --json-out data/processed/rules_and_fields_debug_v8.json
```

#### 3.2 Postprocess the rules_and_fields JSON (highly recommended)

This normalizes ids/types, dedupes questions, and stubs unsafe checks.

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/postprocess_rules_and_fields.py --in data/processed/rules_and_fields_debug_v8.json --out data/processed/rules_and_fields_debug_v8_post.json --report data/processed/rules_and_fields_debug_v8_post_report.json
```

#### 3.3 Generate Core (Issuer + ComplianceRule) from postprocessed schema

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/gen_core_from_issuer_schema.py --schema data/processed/rules_and_fields_debug_v8_post.json --out Src/Core_auto_debug_v8.lean --namespace Src.Core_auto_debug_v8
```

#### 3.4 Generate Rules module from postprocessed JSON (deterministic)

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/gen_rules_lean.py --rules_fields data/processed/rules_and_fields_debug_v8_post.json --core Src.Core_auto_debug_v8 --tag debug_v8 --out Src/GeneratedRules_debug_v8.lean
```

#### 3.5 Generate a Main entrypoint module

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/gen_main_lean.py --core Src.Core_auto_debug_v8 --rules Src.GeneratedRules_debug_v8 --out Src/Main_v8.lean
```

#### 3.6 Compile gate

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; lake build
```

---

## 4) Issuer extraction from an RHP (LLM-assisted)

Once you have `rules_and_fields_debug_v8_post.json`, you can extract issuer values from an RHP:

```powershell
cd "C:/Users/sauna/Dropbox/Compliance Project/compliance"; python scripts/extract_issuer_from_rhp.py --pdf <PATH_TO_RHP_PDF> --out data/processed/issuer_instance_debug_v8.json --questions-json data/processed/rules_and_fields_debug_v8_post.json --model llama3:8b --retrieval keyword --topk 3 --per-field --provenance
```

---

## 5) Run the Lean rules on an issuer instance (optional)

After `lake build`, run the built executable/binary for your lake package (depends on your `lakefile.lean` setup). If you want, paste your `lakefile.lean` and I’ll give you the exact command for your build target.


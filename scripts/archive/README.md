# scripts/archive

Scripts in this folder are **not part of the active pipeline**. They are kept for
reference and may be useful if requirements change.

| Script | Superseded by | Archived |
|--------|--------------|---------|
| `build_facts_schema.py` | Flat reconciled schema from `schema_reconcile.py` | Phase 2 |
| `promote_fields.py` | Evidence-based type inference in `type_infer.py` | Phase 2 |
| `score_rule_to_schema.py` | Diagnostic only; not in active flow | Phase 2 |
| `generate_rule_evidence_schema.py` | Rule-anchored extraction in `rule_anchored_extract.py` | Phase 2 |
| `infer_issuer_fields_with_llm.py` | Opt-in; never called by pipeline | Phase 2 |
| `postprocess_rules.py` | `postprocess_rules_and_fields.py` | Phase 2 |
| `infer_issuer_fields.py` | `schema_reconcile.py` (evidence-first reconciled schema) | Phase 2 |

> To restore a script to the active pipeline, move it back to `scripts/` and
> update any callers accordingly.

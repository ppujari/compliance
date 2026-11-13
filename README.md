# compliance_model
Code Verifier in Lean
Rules Framework with Lean

## Pipeline documentation

See `docs/schema_pipeline.md` for the deterministic flow:
rules JSONL → mapping report → issuer fields → facts schema → promotion report → rule evidence schema.

See `docs/run_flow.md` for a copy/paste step-by-step runbook (commands).

## Rule extraction (with judge loop)

See `docs/rule_extraction_with_judge.md` for the generator→validators→judge→regen→quarantine flow and scoring criteria.

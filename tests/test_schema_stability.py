import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "data" / "processed" / "rules_mistral_7b_v1.jsonl"


def run_cmd(args):
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT)


def load_rules(path: Path):
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            items.append(obj)
    return items


def test_schema_stability_and_coverage():
    if not RULES_PATH.exists():
        raise RuntimeError(f"Missing test rules file: {RULES_PATH}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp1 = Path(tmpdir) / "issuer_fields_1.json"
        tmp2 = Path(tmpdir) / "issuer_fields_2.json"
        evidence_out = Path(tmpdir) / "rule_evidence_schema.json"

        run_cmd(["scripts/infer_issuer_fields.py", "--rules", str(RULES_PATH), "--out", str(tmp1)])
        run_cmd(["scripts/infer_issuer_fields.py", "--rules", str(RULES_PATH), "--out", str(tmp2)])

        fields1 = json.loads(tmp1.read_text(encoding="utf-8"))
        fields2 = json.loads(tmp2.read_text(encoding="utf-8"))

        names1 = {f["name"] for f in fields1}
        names2 = {f["name"] for f in fields2}

        assert names1 == names2, "Issuer fields should be deterministic across runs"

        ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for n in names1:
            assert ident_re.match(n), f"Invalid Lean identifier: {n}"

        # Coverage: every rule_id must appear in RuleEvidence schema
        run_cmd(["scripts/generate_rule_evidence_schema.py", "--rules_jsonl", str(RULES_PATH), "--out", str(evidence_out)])
        evidence = json.loads(evidence_out.read_text(encoding="utf-8"))
        evidence_ids = {e.get("rule_id") for e in evidence}

        rule_ids = set()
        for obj in load_rules(RULES_PATH):
            rid = obj.get("rule_id") or obj.get("rule_id_raw") or "UNKNOWN"
            rule_ids.add(str(rid))

        assert evidence_ids == rule_ids, "RuleEvidence schema must cover all rule_ids"





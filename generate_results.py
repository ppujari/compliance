# scripts/generate_results.py (only the run_one changes)
import json, subprocess, tempfile
from pathlib import Path

EXE = Path(".lake/build/bin/compliance")

def run_one(issuer_rec: dict) -> dict:
    payload = issuer_rec["fields"]
    # write to a temp file and use --in (no stdin)
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tf:
        json.dump(payload, tf)
        tf.flush()
        proc = subprocess.run(
            [str(EXE), "--in", tf.name],  # <-- use file mode
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode())
    report = json.loads(proc.stdout.decode())
    report["issuer_id"] = issuer_rec["issuer_id"]
    return report

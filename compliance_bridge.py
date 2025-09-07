import json, subprocess
from pathlib import Path
from typing import Dict, Any, List

EXE = Path(".lake/build/bin/compliance")

def run_compliance(issuer: Dict[str, Any], exe: Path = EXE) -> Dict[str, Any]:
    """Send Issuer JSON to Lean binary via stdin; return Report JSON as dict."""
    proc = subprocess.run(
        [str(exe)],
        input=json.dumps(issuer).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Lean error:\n{proc.stderr.decode()}")
    return json.loads(proc.stdout.decode())

def run_compliance_from_file(path: Path, exe: Path = EXE) -> Dict[str, Any]:
    proc = subprocess.run(
        [str(exe), "--in", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Lean error:\n{proc.stderr.decode()}")
    return json.loads(proc.stdout.decode())

def summarize(report: Dict[str, Any]) -> str:
    status = "✅ Eligible" if report.get("eligible") else "❌ Not Eligible"
    failed = report.get("failed", [])
    lines = [status, ""]
    if failed:
        lines.append("— Failed —")
        for r in failed:
            lines.append(f"❌ {r['id']} — {r['title']}")
            reason = r.get("reason?") or r.get("reasonOpt") or ""
            if reason:
                lines.append(f"   {reason}")
        lines.append("")
    passed = report.get("passed", [])
    if passed:
        lines.append("— Passed —")
        for r in passed:
            lines.append(f"✅ {r['id']} — {r['title']}")
    return "\n".join(lines)

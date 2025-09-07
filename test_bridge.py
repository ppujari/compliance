import json
from pathlib import Path
from compliance_bridge import run_compliance_from_file, summarize

rep = run_compliance_from_file(Path("issuer.json"))
# Debug view (optional)
# print(json.dumps(rep, indent=2))

# Human-readable summary
print(summarize(rep))
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

# ----------------------------
# Utilities
# ----------------------------


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if "```" not in s:
        return s
    m = re.search(r"```json\s*(.*?)\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)\s*```", s, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    return s


def extract_first_json_block(text: str) -> str:
    """
    Extract the first top-level JSON object/array block from a string.
    Robust to leading/trailing non-JSON text and code fences.
    Returns "" if nothing plausible is found.
    """
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    s = _strip_code_fences(s)

    start = None
    opener = ""
    for i, ch in enumerate(s):
        if ch in "{[":
            start = i
            opener = ch
            break
    if start is None:
        return ""

    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return s[start : j + 1]
    return ""


def _extract_first_json(s: str) -> Any:
    """
    Extract first valid JSON object/array from a string.
    Defensive against extra prose or multiple JSON blocks.
    """
    s = _strip_code_fences(s)
    try:
        return json.loads(s)
    except Exception:
        pass
    block = extract_first_json_block(s)
    if not block:
        raise ValueError("Could not parse JSON from model output.")
    return json.loads(block)


def normalize_whitespace(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "")).strip()


def clamp_span_hint(span_hint: str, limit: int = 120) -> str:
    s = (span_hint or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit].rstrip()


# ----------------------------
# Ollama client
# ----------------------------


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434"
    timeout: int = 120

    def generate(self, model: str, prompt: str, temperature: float = 0.1, format_json: bool = False) -> str:
        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "options": {"temperature": temperature},
            "stream": False,
        }
        if format_json:
            payload["format"] = "json"
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "") or ""


# ----------------------------
# Judge + Regen prompts
# ----------------------------


# Keep type_hint vocabulary compatible with data/schema/rules_schema.json
TYPE_HINT_VOCAB = "Bool, Nat, List Nat, String, OptionBool, OptionNat, OptionListNat, OptionString"


def build_judge_prompt(chunk_text: str, rules: List[Dict[str, Any]]) -> str:
    # Bound text to reduce judge failures / empty JSON
    chunk_text = (chunk_text or "").strip()
    if len(chunk_text) > 12000:
        chunk_text = chunk_text[:12000] + "\n\n[TRUNCATED]"
    rules_json = json.dumps(rules, ensure_ascii=False, indent=2)
    return f"""
You are a compliance rule quality judge for SEBI ICDR extraction.

Return STRICT JSON only (no markdown), with this exact schema:
{{
  "judgments": [
    {{
      "rule_id": "ICDR_7_1_a",
      "scores": {{
        "atomicity": 0.0,
        "fidelity": 0.0,
        "completeness": 0.0,
        "maps_to_quality": 0.0,
        "source_alignment": 0.0
      }},
      "overall": 0.0,
      "failure_modes": ["NOT_ATOMIC"],
      "feedback_for_refinement": "..."
    }}
  ]
}}

Rubric (0..1):
- atomicity: exactly ONE obligation/condition; split merged (a)(b)(c)
- fidelity: preserves legal meaning + all numeric thresholds/units; no hallucinations
- completeness: includes provisos/qualifiers that change meaning
- maps_to_quality: maps_to fields are bare snake_case, correct type_hint ({TYPE_HINT_VOCAB}), no conditions in names
- source_alignment: source.span_hint is <=120 chars and is a direct substring of CHUNK_TEXT

Weights:
overall = 0.30*fidelity + 0.25*atomicity + 0.20*completeness + 0.15*maps_to_quality + 0.10*source_alignment

PASS criteria (you still output judgments either way):
overall >= 0.75 AND fidelity >= 0.70

Failure modes (use only these):
NOT_ATOMIC, LOSES_THRESHOLD, HALLUCINATION, MISSING_QUALIFIER,
MAPS_TO_BAD_FIELD, MAPS_TO_BAD_TYPE, BAD_SPAN_HINT, OTHER

CHUNK_TEXT:
<<<{chunk_text}>>>

RULES_JSON:
<<<{rules_json}>>>
""".strip()


def build_regen_prompt(chunk_text: str, bad_rule: Dict[str, Any], feedback: str) -> str:
    chunk_text = (chunk_text or "").strip()
    if len(chunk_text) > 12000:
        chunk_text = chunk_text[:12000] + "\n\n[TRUNCATED]"
    bad_rule_json = json.dumps(bad_rule, ensure_ascii=False, indent=2)
    return f"""
You are re-generating ONE failed compliance rule from SEBI ICDR text.

Return STRICT JSON for a single rule object (not an array). No markdown.

Constraints:
- Must preserve legal meaning and all numeric thresholds/units.
- Must be ATOMIC (one obligation/condition only).
- Keep rule_id the SAME as in PREVIOUS_RULE unless BAD_RULE_ID is explicitly stated in feedback.
- source.pdf and source.pages MUST stay the same as PREVIOUS_RULE.
- source.span_hint must be a direct substring of CHUNK_TEXT (<=120 chars), not generic.
- maps_to.field must be bare snake_case. No conditions/units/parentheses in field names.
- type_hint must be one of: {TYPE_HINT_VOCAB}

CHUNK_TEXT:
<<<{chunk_text}>>>

PREVIOUS_RULE:
<<<{bad_rule_json}>>>

FEEDBACK:
<<<{feedback}>>>
""".strip()


# ----------------------------
# Core class
# ----------------------------


class RuleRefiner:
    def __init__(self, ollama: OllamaClient, judge_model: str, gen_model: str):
        self.ollama = ollama
        self.judge_model = judge_model
        self.gen_model = gen_model

    def judge(self, chunk_text: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = build_judge_prompt(chunk_text, rules)
        raw = self.ollama.generate(self.judge_model, prompt, temperature=0.1, format_json=True)
        parsed = _extract_first_json(raw)
        if not isinstance(parsed, dict) or "judgments" not in parsed:
            raise ValueError("Judge returned invalid JSON shape.")
        return parsed

    def regen_one(self, chunk_text: str, bad_rule: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        prompt = build_regen_prompt(chunk_text, bad_rule, feedback)
        raw = self.ollama.generate(self.gen_model, prompt, temperature=0.2, format_json=True)
        parsed = _extract_first_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Regenerator did not return a JSON object.")
        return parsed

    @staticmethod
    def needs_regen(j: Dict[str, Any], overall_th: float = 0.75, fidelity_min: float = 0.70) -> bool:
        scores = j.get("scores", {}) or {}
        fidelity = float(scores.get("fidelity", 0.0))
        overall = float(j.get("overall", 0.0))
        return (overall < overall_th) or (fidelity < fidelity_min)

    def refine_rules(
        self,
        chunk_text: str,
        rules: List[Dict[str, Any]],
        max_iterations: int = 2,
        overall_th: float = 0.75,
        fidelity_min: float = 0.70,
        max_regen_per_window: int = 8,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Returns (final_rules, judge_report).
        Adds status fields: accepted/fixed/quarantined.
        """
        rule_by_id = {r.get("rule_id"): r for r in rules if isinstance(r, dict) and r.get("rule_id")}
        history: List[Dict[str, Any]] = []

        for it in range(1, max_iterations + 1):
            report = self.judge(chunk_text, list(rule_by_id.values()))
            judgments = report.get("judgments", []) or []
            history.append({"iteration": it, "report": report})

            to_regen: List[Dict[str, Any]] = []
            for j in judgments:
                rid = j.get("rule_id")
                if rid in rule_by_id and self.needs_regen(j, overall_th, fidelity_min):
                    to_regen.append(j)

            if not to_regen:
                for r in rule_by_id.values():
                    r["status"] = "accepted" if it == 1 else "fixed"
                    # clamp span_hint to schema requirement
                    src = r.get("source")
                    if isinstance(src, dict) and "span_hint" in src:
                        src["span_hint"] = clamp_span_hint(str(src.get("span_hint") or ""))
                report["history"] = history
                return list(rule_by_id.values()), report

            # regenerate only failing rules (bounded)
            to_regen = to_regen[: max(0, int(max_regen_per_window))]
            for j in to_regen:
                rid = j["rule_id"]
                feedback = j.get("feedback_for_refinement", "") or ""
                new_rule = self.regen_one(chunk_text, rule_by_id[rid], feedback)

                # keep rule_id stable if regenerator drifted
                if new_rule.get("rule_id") != rid:
                    new_rule["rule_id"] = rid

                # preserve pdf/pages
                prev_src = rule_by_id[rid].get("source") if isinstance(rule_by_id[rid].get("source"), dict) else {}
                new_rule.setdefault("source", {})
                if isinstance(new_rule["source"], dict):
                    if isinstance(prev_src, dict):
                        new_rule["source"]["pdf"] = prev_src.get("pdf", new_rule["source"].get("pdf", ""))
                        new_rule["source"]["pages"] = prev_src.get("pages", new_rule["source"].get("pages", []))
                    if "span_hint" in new_rule["source"]:
                        new_rule["source"]["span_hint"] = clamp_span_hint(str(new_rule["source"]["span_hint"]))
                rule_by_id[rid] = new_rule

        # After max iterations: quarantine remaining failing
        final_report = self.judge(chunk_text, list(rule_by_id.values()))
        for j in final_report.get("judgments", []) or []:
            rid = j.get("rule_id")
            if rid in rule_by_id and self.needs_regen(j, overall_th, fidelity_min):
                rule_by_id[rid]["status"] = "quarantined"
                rule_by_id[rid]["maps_to"] = []
                rule_by_id[rid]["notes"] = (
                    (rule_by_id[rid].get("notes", "") or "") + " | QUARANTINED: " + ",".join(j.get("failure_modes", []) or [])
                ).strip(" |")
            else:
                rule_by_id[rid].setdefault("status", "accepted")

        # clamp hints
        for r in rule_by_id.values():
            src = r.get("source")
            if isinstance(src, dict) and "span_hint" in src:
                src["span_hint"] = clamp_span_hint(str(src.get("span_hint") or ""))

        final_report["history"] = history
        return list(rule_by_id.values()), final_report


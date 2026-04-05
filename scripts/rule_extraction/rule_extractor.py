"""LLM prompts, few-shot examples, judge rubric, and extraction orchestration."""

from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any, List, Dict

from jsonschema import Draft202012Validator

from .ollama_client import OllamaClient, coerce_rules_from_parsed
from .regulation_identifier import (
    identify_regulations, build_targeted_extraction_prompt,
    normalize_rule_identifier,
)
from .rule_validator import (
    sanitize_for_schema, clamp_span_hint,
    validate_required_fields, validate_rule_id_format,
    validate_maps_to, validate_source, validate_reg_anchoring,
)


# ---------- Few-shot utilities ----------

def load_fewshot_examples(fewshot_path: str | None) -> list[tuple[str, list[dict]]]:
    """Load few-shot examples from a JSON file."""
    examples: list[tuple[str, list[dict]]] = []
    if not fewshot_path:
        return examples
    p = Path(fewshot_path)
    if not p.exists():
        raise FileNotFoundError(f"Few-shot file not found: {fewshot_path}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse few-shot JSON: {e}")

    data = raw.get("examples") if isinstance(raw, dict) and "examples" in raw else raw
    if not isinstance(data, list):
        raise ValueError("Few-shot file must be a list or an object with an 'examples' list")
    for i, ex in enumerate(data):
        if not isinstance(ex, dict):
            continue
        inp = ex.get("input") or ex.get("text")
        out = ex.get("output") or ex.get("items")
        if isinstance(inp, str) and isinstance(out, list):
            examples.append((inp, out))
    return examples


# ---------- Judge schema ----------

JUDGE_SCHEMA: dict = {
    "type": "object",
    "required": ["rule_id", "scores", "overall", "failure_modes", "fix_instructions"],
    "properties": {
        "rule_id": {"type": "string"},
        "scores": {
            "type": "object",
            "required": ["atomicity", "fidelity", "completeness", "maps_to_quality", "source_alignment"],
            "properties": {
                "atomicity": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "fidelity": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "completeness": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "maps_to_quality": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "source_alignment": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "additionalProperties": False,
        },
        "overall": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "failure_modes": {"type": "array", "items": {"type": "string"}},
        "fix_instructions": {"type": "string"},
    },
    "additionalProperties": False,
}

ARRAY_JUDGE_SCHEMA: dict = {"type": "array", "items": JUDGE_SCHEMA}
JUDGE_VALIDATOR = Draft202012Validator(ARRAY_JUDGE_SCHEMA)

JUDGE_WEIGHTS = {
    "fidelity": 0.30,
    "atomicity": 0.25,
    "completeness": 0.20,
    "maps_to_quality": 0.15,
    "source_alignment": 0.10,
}


def compute_overall_score(scores: dict) -> float:
    total = 0.0
    for k, w in JUDGE_WEIGHTS.items():
        try:
            total += float(scores.get(k, 0.0)) * w
        except Exception:
            total += 0.0
    return round(total, 4)


def build_judge_prompt(chunk_text: str, rules: List[dict]) -> str:
    """Fixed rubric judge prompt."""
    rubric = (
        "Score each rule using this fixed rubric (0..1 each):\n"
        "- atomicity: is it ONE atomic legal requirement (not bundled)?\n"
        "- fidelity: does it match the clause text without hallucination?\n"
        "- completeness: includes thresholds/units/exceptions present in text?\n"
        "- maps_to_quality: maps_to fields are appropriate and correctly typed, or empty if procedural.\n"
        "- source_alignment: rule clearly comes from the provided chunk and span_hint is a direct quote.\n\n"
        "Weights (do NOT change): fidelity 0.30, atomicity 0.25, completeness 0.20, maps_to_quality 0.15, source_alignment 0.10.\n"
        "Pass rule if: overall >= 0.75 AND fidelity >= 0.70.\n"
        "If a rule is procedural/uncheckable, recommend quarantine: maps_to should be [].\n"
        "Return STRICT JSON only (no markdown, no prose).\n"
    )
    items = []
    for r in rules:
        items.append(
            {
                "rule_id": r.get("rule_id"),
                "title": r.get("title"),
                "text": r.get("text"),
                "maps_to": r.get("maps_to", []),
                "notes": r.get("notes", ""),
                "source": r.get("source", {}),
            }
        )
    chunk_text = (chunk_text or "")
    if len(chunk_text) > 12000:
        chunk_text = chunk_text[:12000] + "\n\n[TRUNCATED]"
    return (
        rubric
        + "\nCHUNK_TEXT:\n"
        + chunk_text
        + "\n\nRULES (JSON):\n"
        + json.dumps(items, ensure_ascii=False, indent=2)
        + "\n\nOUTPUT FORMAT: JSON array of objects, one per rule_id, each matching:\n"
        + json.dumps(JUDGE_SCHEMA, ensure_ascii=False)
    )


def build_regen_prompt(chunk_text: str, bad_rule: dict, judge_feedback: dict,
                       hard_reasons: List[str], soft_reasons: List[str]) -> str:
    """Targeted regeneration prompt for exactly ONE rule object."""
    return (
        "Regenerate EXACTLY ONE rule JSON object for the SAME legal clause, from the SAME chunk text.\n"
        "Constraints:\n"
        "- Output MUST be a single JSON object (not an array).\n"
        "- rule_id MUST be the same.\n"
        "- Preserve numeric thresholds and units.\n"
        "- source.pdf and source.pages MUST be preserved; source.span_hint MUST be a direct quote substring from CHUNK_TEXT (<=120 chars).\n"
        "- If the rule is procedural/uncheckable, set maps_to to [].\n"
        "- Do NOT invent information not present in CHUNK_TEXT.\n\n"
        f"CHUNK_TEXT:\n{chunk_text}\n\n"
        f"BAD_RULE:\n{json.dumps(bad_rule, ensure_ascii=False, indent=2)}\n\n"
        f"JUDGE_FEEDBACK:\n{json.dumps(judge_feedback, ensure_ascii=False, indent=2)}\n\n"
        f"DETERMINISTIC_VALIDATION:\n{json.dumps({'hard_fail_reasons': hard_reasons, 'soft_fail_reasons': soft_reasons}, ensure_ascii=False, indent=2)}\n\n"
        "Return ONLY the corrected JSON object."
    )


# ---------- Static prompts ----------

SYSTEM_PROMPT = """You are a compliance analyst extracting ATOMIC regulatory rules from SEBI ICDR regulations.
Your output MUST be STRICT JSON (UTF-8, no comments) matching this array schema:

[
  {
    "rule_id": "ICDR_<reg>[_<num>][_a]",
    "domain": "SEBI_ICDR",
    "title": "<concise title>",
    "text": "<verbatim or lightly cleaned clause text (keep legal meaning)>",
    "lean_id": "rule_<reg>[_<num>][_a]",
    "maps_to": [
  {
    "field": "<snake_case field identifier>",
    "type_hint": "Bool | Nat | List Nat | String | OptionBool | OptionNat | OptionListNat | OptionString",
    "constraints_text": "<optional; do NOT put constraints in field name>"
  }
],
"notes": "<optional human explanation; DO NOT include field names here>",
    "source": {
      "pdf": "<filename>",
      "pages": [<page_numbers_int>],
      "reg": "<visible heading if present>",
      "span_hint": "<few words around the start>"
    },
    "confidence": 0.0
  }
]

MAPS_TO REASONING -- apply these three steps BEFORE emitting maps_to for each rule:

Step 1 - Identify the constraint type from the clause text:
  - Numeric threshold (e.g. 'at least three crore', '25 per cent')? -> Nat or List Nat
  - Yes/no compliance check ('shall have entered into', 'shall not be eligible',
    'has been debarred', 'fully paid up')? -> Bool
  - Time period or duration ('for a period of 18 months')? -> Nat
  - Multi-year series ('in each of the preceding three years',
    'during the preceding three years')? -> List Nat (length = N years)
  - Percentage or ratio? -> Nat
  - Text identifier or category (name, type, CIN, ISIN)? -> String
  - Procedural / cannot be checked from issuer data alone? -> maps_to: []

Step 2 - Choose a SPECIFIC field name (must be unique across ALL regulations):
  BAD:  'conditions', 'exceptions', 'securities', 'lock_in_period', 'amount'
  GOOD: 'is_debarred', 'promoter_min_contribution_pct', 'net_tangible_assets_3yr',
        'ofs_holding_period_years', 'has_depository_agreement',
        'promoter_shares_dematerialised'
  - Bool flags: prefix with 'is_' or 'has_' or 'no_'
  - Durations: suffix with '_months' or '_years'
  - Multi-year series: suffix with '_3yr' or '_Nyr'
  - Never use bare nouns that appear in multiple regulations.

Step 3 - Assign type_hint (NEVER leave blank for checkable rules):
  Bool     -> yes/no, has/has not, complied/not complied
  Nat      -> single numeric value, percentage, duration, threshold
  List Nat -> multi-year series, list of values across periods
  String   -> text identifiers, names, categories
  If uncertain between Nat and List Nat, prefer List Nat (reconciliation corrects later).

Rules:
- Extract only clauses that are within the *visible* pages provided.
- Produce ATOMIC items: split by (1)(2)... and (a)(b)... where semantically distinct.
- Preserve numeric thresholds and units (e.g., ₹15 crore, 25%).
- Be conservative: do not infer or normalize beyond the text.
- `rule_id` MUST follow `ICDR_<reg>[_<clause>[_<subclause>]]` using digits for numbered clauses and lowercase letters for sub-clauses (e.g., ICDR_6_1_a, ICDR_14_4_core). Do not emit spaces, hyphens, or Roman numerals.
- Titles should be short and specific. "Title -- (1)(b)" is fine when no official title.
- lean_id mirrors rule_id with 'ICDR' -> 'rule', e.g., ICDR_6_1_b -> rule_6_1_b.
- Use notes only for short human explanation/edge cases. Do not put field names in notes; use maps_to.
- `source.span_hint` must be a direct quote (<=120 chars) copied from the provided text window; no paraphrasing.
- `source.span_hint` should be the first ~10 words of the clause text (strip punctuation), so it is easy to locate verbatim in the PDF.
- `source.span_hint` must be a unique fragment that clearly identifies this clause (e.g. starting from 'The issuer shall...'). Never use generic phrases like 'subject to', 'the issuer may', 'Provided that'.
- Confidence in [0,1]; use lower scores if the clause boundary is ambiguous.
- If no extractable rules are present in this chunk, return [].
- For each legal clause (e.g., Regulation 6(1)(a)), return at most one JSON object. Do not repeat the same clause with different rule_ids.
- In maps_to, field must be a bare identifier. Do not include parentheses, units, bullet letters, or conditions.
- If a rule is not representable as a stable issuer/offer fact, set maps_to: [].
- Never output two objects whose source.reg and source.span_hint refer to the same clause.
"""

FEWSHOT_INPUT = """Regulation 6(1)(b): The issuer shall have an average operating profit of at least ₹15 crore, calculated on a restated and consolidated basis, during the preceding three years, with operating profit in each of these preceding three years."""
FEWSHOT_OUTPUT = [
  {
    "rule_id": "ICDR_6_1_b",
    "domain": "SEBI_ICDR",
    "title": "Operating profit >= ₹15 cr in each of last 3 years",
    "text": "The issuer shall have an average operating profit of at least ₹15 crore, calculated on a restated and consolidated basis, during the preceding three years, with operating profit in each of these preceding three years.",
    "lean_id": "rule_6_1_b",
    "maps_to": [
      {
        "field": "operating_profits",
        "type_hint": "List Nat",
        "constraints_text": "length=3; each >= ₹15 crore; basis=restated, consolidated"
      }
    ],
    "notes": "Three-year operating profit requirement; computed on restated and consolidated basis.",
    "source": {"pdf":"<PDF>", "pages":[0], "reg":"Regulation 6(1)(b)", "span_hint":"average operating profit of at least"},
    "confidence": 0.95
  }
]

FEWSHOT_BOOL_INPUT = (
    "Regulation 7(1)(b): it has entered into an agreement with a depository for "
    "dematerialisation of the specified securities already issued and proposed to be issued."
)
FEWSHOT_BOOL_OUTPUT = [
    {
        "rule_id": "ICDR_7_1_b",
        "domain": "SEBI_ICDR",
        "title": "Agreement with depository for dematerialisation",
        "text": (
            "it has entered into an agreement with a depository for dematerialisation "
            "of the specified securities already issued and proposed to be issued."
        ),
        "lean_id": "rule_7_1_b",
        "maps_to": [
            {
                "field": "has_depository_agreement",
                "type_hint": "Bool",
                "constraints_text": "must have entered agreement with a depository",
            }
        ],
        "notes": "Binary compliance check -- agreement either exists or it does not.",
        "source": {
            "pdf": "<PDF>",
            "pages": [0],
            "reg": "Regulation 7(1)(b)",
            "span_hint": "entered into an agreement with a depository",
        },
        "confidence": 0.95,
    }
]

FEWSHOT_BAD_INPUT = """Regulation 6(1)(a) appears once in the excerpt below. Do not create multiple objects for the same clause:
6. (1) (a) it has net tangible assets of at least three crore rupees ...
"""

FEWSHOT_BAD_OUTPUT = [
  {
    "rule_id": "ICDR_6_1_a",
    "domain": "SEBI_ICDR",
    "title": "Net tangible assets >= ₹3 cr",
    "text": "it has net tangible assets of at least three crore rupees ...",
    "lean_id": "rule_6_1_a",
    "maps_to": [
      {
        "field": "net_tangible_assets",
        "type_hint": "List Nat",
        "constraints_text": "length=3 (preceding 3 years if stated); threshold >= ₹3 crore"
      }
    ],
    "notes": "Single clause; do not duplicate objects for the same regulation reference.",
    "source": {
      "pdf": "<PDF>",
      "pages": [1],
      "reg": "Regulation 6(1)(a)",
      "span_hint": "net tangible assets of at least three crore"
    },
    "confidence": 0.9
  }
]

BAD_EXPLANATION = """
Do NOT output duplicates for the same legal clause (e.g., do not output rule_id ICDR_6_1_a twice
with variants). If a clause is mentioned once, return at most one JSON object for it.
"""


# ---------- Subrule flattening ----------

def flatten_subrules(rule_obj: dict) -> list[dict]:
    """If model returns a non-schema object with `subrules`, flatten into separate rule objects."""
    subrules = rule_obj.get("subrules")
    if not isinstance(subrules, list):
        return [rule_obj]
    out: list[dict] = []
    parent_title = str(rule_obj.get("title") or "").strip()
    for sr in subrules:
        if not isinstance(sr, dict):
            continue
        num = str(sr.get("number") or "").strip()
        txt = str(sr.get("text") or "").strip()
        if not num or not txt:
            continue
        tokens = re.findall(r"\d+|[A-Za-z]+", num)
        if not tokens:
            continue
        reg = tokens[0]
        rest = [t.lower() for t in tokens[1:]]
        rule_id = "ICDR_" + reg + ("_" + "_".join(rest) if rest else "")
        out.append(
            {
                "rule_id": rule_id,
                "domain": "SEBI_ICDR",
                "title": (parent_title + " -- " + num).strip(" -") if parent_title else num,
                "text": txt,
                "lean_id": "rule_" + rule_id[5:].lower(),
                "maps_to": [],
                "notes": "",
                "source": {"pdf": "<PDF>", "pages": [0], "reg": "", "span_hint": ""},
                "confidence": 0.6,
                "repair_notes": ["flattened_subrules"],
            }
        )
    return out or [rule_obj]


# ---------- Dedup/scoring helpers ----------

MIN_TEXT_CHARS = 90
TEXT_SIGNATURE_SLICE = 160


def normalize_clause_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def item_score(it: dict) -> tuple[float, int, int, int]:
    try:
        confidence = float(it.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0
    norm_text = it.get("_norm_text") or normalize_clause_text(it.get("text", ""))
    span_hint = ""
    source = it.get("source")
    if isinstance(source, dict):
        span_hint = source.get("span_hint", "") or ""
    repair_penalty = -len(it.get("repair_notes", [])) if isinstance(it.get("repair_notes"), list) else 0
    return (
        round(confidence, 6),
        len(norm_text),
        repair_penalty,
        len(span_hint),
    )


def choose_best_item(existing: dict, candidate: dict) -> dict:
    if item_score(candidate) > item_score(existing):
        return candidate
    return existing


# --- Bug fix 12.5: Deduplicate field names across regulations ---

def deduplicate_field_names(rules: list[dict]) -> list[dict]:
    """When multiple rules map to the same field name, disambiguate by appending the regulation number."""
    field_to_rules: dict[str, list[str]] = {}
    for r in rules:
        rid = r.get("rule_id", "")
        for m in r.get("maps_to", []):
            field = m.get("field", "")
            if field:
                field_to_rules.setdefault(field, []).append(rid)

    collisions = {f: rids for f, rids in field_to_rules.items() if len(rids) > 1}

    if not collisions:
        return rules

    for r in rules:
        rid = r.get("rule_id", "")
        reg_match = re.match(r"ICDR_(\d+[A-Z]?)", rid)
        reg_suffix = f"_reg{reg_match.group(1)}" if reg_match else ""

        for m in r.get("maps_to", []):
            field = m.get("field", "")
            if field in collisions:
                m["field"] = field + reg_suffix
                r.setdefault("repair_notes", []).append(
                    f"field_disambiguated:{field}->{m['field']}"
                )

    return rules


# ---------- Two-pass extraction wrappers ----------

def extract_rules_two_pass(
    client: OllamaClient,
    model: str,
    window_text: str,
    page_nums: list[int],
    visible_regs: set[str] | None = None,
    pdf_name: str = "<PDF>",
    timeout: int = 120,
    debug: bool = False,
) -> list[dict]:
    """Two-pass extraction: identify clauses, then extract per clause."""
    import sys
    reg_inventory = identify_regulations(
        client, model, window_text, page_nums,
        visible_regs=visible_regs,
        timeout=timeout, debug=debug,
    )
    if not reg_inventory:
        return []

    items: list[dict] = []
    for reg_info in reg_inventory:
        reg_num = (reg_info.get("reg_number") or "").strip()
        clause_text = (reg_info.get("clause_text") or "").strip()
        if not reg_num or not clause_text:
            continue
        p2_prompt = build_targeted_extraction_prompt(
            reg_num, clause_text, page_nums, pdf_name=pdf_name
        )
        if debug:
            print(f"[Pass2] extracting reg {reg_num} ({len(clause_text)} chars)", file=sys.stderr)
        try:
            raw = client.chat_json_any(
                model, SYSTEM_PROMPT, p2_prompt,
                timeout=timeout, debug=debug,
            )
        except Exception as e:
            print(f"[WARN] Pass 2 call failed for reg {reg_num}: {e}", file=sys.stderr)
            continue
        if raw is None:
            continue
        extracted = coerce_rules_from_parsed(raw)
        if not extracted and isinstance(raw, dict) and raw:
            extracted = [raw]
        items.extend(extracted)

    if debug:
        print(f"[TwoPass] pages={page_nums}: {len(reg_inventory)} clauses -> {len(items)} raw items", file=sys.stderr)
    return items


def extract_rules_single_pass(
    client: OllamaClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
    fewshots: list[tuple[str, list[dict]]] | None = None,
    timeout: int = 120,
    debug: bool = False,
    debug_raw: bool = False,
    format_json: bool = True,
    endpoint: str = "auto",
) -> list[dict]:
    """Legacy single-pass extraction."""
    try:
        if endpoint == "chat":
            return client.chat_json(
                model, system_prompt, user_prompt,
                fewshots=fewshots, timeout=timeout, debug=debug, debug_raw=debug_raw,
                format_json=format_json,
                fewshot_input=FEWSHOT_INPUT, fewshot_output=FEWSHOT_OUTPUT,
                fewshot_bool_input=FEWSHOT_BOOL_INPUT, fewshot_bool_output=FEWSHOT_BOOL_OUTPUT,
                bad_explanation=BAD_EXPLANATION,
            )
        elif endpoint == "generate":
            return client.generate_json(
                model, system_prompt, user_prompt,
                fewshots=fewshots, timeout=timeout, debug=debug, debug_raw=debug_raw,
                format_json=format_json,
                fewshot_input=FEWSHOT_INPUT, fewshot_output=FEWSHOT_OUTPUT,
                fewshot_bool_input=FEWSHOT_BOOL_INPUT, fewshot_bool_output=FEWSHOT_BOOL_OUTPUT,
                bad_explanation=BAD_EXPLANATION,
            )
        else:  # auto
            result = client.chat_json(
                model, system_prompt, user_prompt,
                fewshots=fewshots, timeout=timeout, debug=debug, debug_raw=debug_raw,
                format_json=format_json,
                fewshot_input=FEWSHOT_INPUT, fewshot_output=FEWSHOT_OUTPUT,
                fewshot_bool_input=FEWSHOT_BOOL_INPUT, fewshot_bool_output=FEWSHOT_BOOL_OUTPUT,
                bad_explanation=BAD_EXPLANATION,
            )
            if not result:
                if debug:
                    import sys
                    print("[DEBUG] chat returned no items -> trying /api/generate", file=sys.stderr)
                result = client.generate_json(
                    model, system_prompt, user_prompt,
                    fewshots=fewshots, timeout=timeout, debug=debug, debug_raw=debug_raw,
                    format_json=format_json,
                    fewshot_input=FEWSHOT_INPUT, fewshot_output=FEWSHOT_OUTPUT,
                    fewshot_bool_input=FEWSHOT_BOOL_INPUT, fewshot_bool_output=FEWSHOT_BOOL_OUTPUT,
                    bad_explanation=BAD_EXPLANATION,
                )
            return result
    except Exception as e:
        import sys
        print(f"[WARN] model call failed: {e}", file=sys.stderr)
        return []

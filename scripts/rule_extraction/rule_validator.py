"""Rule validation, schema enforcement, and span hint verification."""

from __future__ import annotations
import json, re, unicodedata
from pathlib import Path
from typing import List, Dict

from jsonschema import Draft202012Validator

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent  # scripts/rule_extraction/ -> scripts/ -> repo root
SCHEMA_PATH = _REPO_ROOT / "data" / "schema" / "rules_schema.json"
RULE_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(RULE_SCHEMA)
ALLOWED_TOP_KEYS = set((RULE_SCHEMA.get("properties") or {}).keys())

ARRAY_RULES_SCHEMA: dict = {
    "type": "array",
    "items": RULE_SCHEMA if RULE_SCHEMA.get("type") == "object" else {"type": "object"}
}


def build_ollama_json_schema_format() -> dict:
    """Returns an Ollama 'format' payload that enforces the array-of-rules schema."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "rules_array",
            "schema": ARRAY_RULES_SCHEMA
        }
    }


def sanitize_for_schema(item: dict) -> dict:
    """Drop any keys not allowed by data/schema/rules_schema.json."""
    out: dict = {}
    for k in ALLOWED_TOP_KEYS:
        if k in item:
            out[k] = item[k]

    # sanitize nested structures with additionalProperties:false
    if "source" in out and isinstance(out["source"], dict):
        src = out["source"]
        span_hint = src.get("span_hint", "") or ""
        if isinstance(span_hint, str) and len(span_hint) > 120:
            span_hint = span_hint[:120].rstrip()
        out["source"] = {
            "pdf": src.get("pdf", ""),
            "pages": src.get("pages", []),
            "span_hint": span_hint,
            **({"reg": src.get("reg", "")} if "reg" in src else {}),
        }

    if "maps_to" in out and isinstance(out["maps_to"], list):
        cleaned_maps = []
        for m in out["maps_to"]:
            if not isinstance(m, dict):
                continue
            cm = {}
            if "field" in m:
                cm["field"] = m["field"]
            if "type_hint" in m:
                cm["type_hint"] = m["type_hint"]
            if "constraints_text" in m:
                cm["constraints_text"] = m["constraints_text"]
            if cm:
                cleaned_maps.append(cm)
        out["maps_to"] = cleaned_maps

    return out


def clamp_span_hint(rule: dict) -> None:
    """Deterministically clamp span_hint length to schema limit."""
    src = rule.get("source")
    if not isinstance(src, dict):
        return
    sh = src.get("span_hint")
    if isinstance(sh, str) and len(sh) > 120:
        src["span_hint"] = sh[:120].rstrip()


RULE_ID_FORMAT_RE = re.compile(r"^ICDR_\d+(?:_\d+)*(?:_[a-z]+)?$", re.I)
MAPS_TO_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_required_fields(rule: dict) -> List[str]:
    reasons: List[str] = []
    for k in ["rule_id", "domain", "title", "text", "lean_id", "source"]:
        if k not in rule:
            reasons.append(f"missing_{k}")
    src = rule.get("source")
    if not isinstance(src, dict):
        reasons.append("missing_source_object")
    else:
        for k in ["pdf", "pages", "span_hint"]:
            if k not in src:
                reasons.append(f"missing_source_{k}")
    return reasons


def validate_rule_id_format(rule_id: str) -> bool:
    return bool(RULE_ID_FORMAT_RE.match((rule_id or "").strip()))


def validate_maps_to(rule: dict) -> List[str]:
    reasons: List[str] = []
    maps_to = rule.get("maps_to")
    if maps_to is None:
        return reasons
    if not isinstance(maps_to, list):
        return ["maps_to_not_list"]
    for idx, m in enumerate(maps_to):
        if not isinstance(m, dict):
            reasons.append(f"maps_to[{idx}]_not_object")
            continue
        field = (m.get("field") or "").strip()
        if not field:
            reasons.append(f"maps_to[{idx}]_missing_field")
            continue
        if not MAPS_TO_FIELD_RE.match(field):
            reasons.append(f"maps_to[{idx}]_bad_field:{field}")
        th = (m.get("type_hint") or "").strip()
        if th and th not in ("Bool", "Nat", "List Nat", "String", "OptionBool", "OptionNat", "OptionListNat", "OptionString"):
            reasons.append(f"maps_to[{idx}]_bad_type_hint:{th}")
    return reasons


def validate_source(rule: dict, chunk_text: str, span_mode: str = "lenient") -> List[str]:
    reasons: List[str] = []
    src = rule.get("source")
    if not isinstance(src, dict):
        return ["missing_source_object"]
    span_hint = (src.get("span_hint") or "").strip()
    if not span_hint:
        reasons.append("missing_span_hint")
        return reasons
    if len(span_hint) > 120:
        reasons.append("span_hint_too_long")
    ok = False
    if span_mode == "strict":
        ok = contains_span_hint(chunk_text, span_hint) or contains_span_hint_fuzzy(chunk_text, span_hint)
    else:
        ok = contains_span_hint_lenient(chunk_text, span_hint) or contains_span_hint_fuzzy(chunk_text, span_hint)
    if not ok:
        reasons.append("span_hint_not_in_chunk")
    return reasons


def validate_reg_anchoring(rule: dict, visible_regs: set[str]) -> List[str]:
    """
    Soft validation: check that the rule's regulation number was actually visible
    on the pages of the window it came from.
    """
    reasons: List[str] = []
    if not visible_regs:
        return reasons
    rid = rule.get("rule_id", "") or ""
    m = re.match(r"ICDR_(\d+[A-Z]?)", rid, re.I)
    if not m:
        return reasons
    rule_reg = m.group(1).upper()
    visible_upper = {r.upper() for r in visible_regs}
    if rule_reg not in visible_upper:
        reasons.append(
            f"reg_anchoring_mismatch:rule_says_{rule_reg}"
            f"_but_page_shows_{sorted(visible_upper)}"
        )
    return reasons


def detect_duplicates(rules: List[dict]) -> Dict[str, int]:
    """Return dict of rule_id -> count (only for duplicates)."""
    counts: Dict[str, int] = {}
    for r in rules:
        rid = str(r.get("rule_id") or "").strip()
        if not rid:
            continue
        counts[rid] = counts.get(rid, 0) + 1
    return {k: v for (k, v) in counts.items() if v > 1}


def validate_rule(item: dict) -> bool:
    cleaned = sanitize_for_schema(item)
    errors = list(VALIDATOR.iter_errors(cleaned))
    if errors:
        try:
            msg = errors[0].message
        except Exception:
            msg = "schema validation failed"
        item.setdefault("repair_notes", []).append(f"schema_invalid:{msg}")
        return False
    if not str(cleaned.get("rule_id", "")).startswith("ICDR_"):
        return False
    if not str(cleaned.get("lean_id", "")).startswith("rule_"):
        return False
    item["_sanitized"] = cleaned
    return True


# --- Span hint helpers ---

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def contains_span_hint(window_text: str, hint: str) -> bool:
    """Case-insensitive, whitespace-normalized containment check."""
    if not hint or not isinstance(hint, str):
        return False
    wt = normalize_ws(window_text)
    ht = normalize_ws(hint)
    return bool(ht) and ht in wt


def normalize_lenient(s: str) -> str:
    """Lenient normalization: NFKC, lowercase, non-word -> space, collapse."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def contains_span_hint_lenient(window_text: str, hint: str) -> bool:
    if not hint or not isinstance(hint, str):
        return False
    normalized_window = normalize_lenient(window_text)
    normalized_hint = normalize_lenient(hint)
    if not normalized_hint:
        return False
    if normalized_hint in normalized_window:
        return True
    window_tokens = normalized_window.split()
    hint_tokens = normalized_hint.split()
    if not hint_tokens:
        return False
    pos = 0
    for token in hint_tokens:
        try:
            idx = window_tokens.index(token, pos)
        except ValueError:
            return False
        pos = idx + 1
    return True


def contains_span_hint_fuzzy(window_text: str, hint: str, threshold: float = 0.72) -> bool:
    """Fuzzy fallback using difflib on normalized text."""
    import difflib
    if not hint or not isinstance(hint, str):
        return False
    normalized_window = normalize_lenient(window_text)
    normalized_hint = normalize_lenient(hint)
    if not normalized_hint:
        return False
    if normalized_hint in normalized_window:
        return True
    if len(normalized_hint) < 6:
        return False
    ratio = difflib.SequenceMatcher(None, normalized_hint, normalized_window).quick_ratio()
    return ratio >= threshold


# --- Bug fix 12.6: List Nat type override ---

_MULTI_YEAR_RE = re.compile(
    r"(?:preceding|last|previous)\s+(\w+)\s+(?:financial\s+)?years?",
    re.I,
)
_WORD_TO_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}


def override_list_nat_from_text(rule: dict) -> None:
    """
    If the rule text contains multi-year language ('preceding three years'),
    override any Nat type_hint to List Nat on numeric fields.
    """
    text = rule.get("text", "")
    m = _MULTI_YEAR_RE.search(text)
    if not m:
        return

    n_word = m.group(1).lower()
    n = _WORD_TO_NUM.get(n_word)
    if not n:
        try:
            n = int(n_word)
        except ValueError:
            return

    for mt in rule.get("maps_to", []):
        th = mt.get("type_hint", "")
        if th == "Nat":
            mt["type_hint"] = "List Nat"
            existing = mt.get("constraints_text", "")
            if f"length={n}" not in existing:
                mt["constraints_text"] = f"length={n}; " + existing if existing else f"length={n}"
            rule.setdefault("repair_notes", []).append(
                f"type_override:Nat->ListNat(n={n})_for_{mt.get('field','')}"
            )

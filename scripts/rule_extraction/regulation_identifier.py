"""Deterministic regulation identification from PDF text structure."""

from __future__ import annotations
import json, re, sys
from typing import Any, List

from .ollama_client import OllamaClient, coerce_rules_from_parsed

# --- Compiled regexes ---

REG_RE = re.compile(r"(?:Regulation|Reg\.?|Chapter)\s+(\d+)\b", re.I)
CLAUSE_PREFIX_RE = re.compile(r"\b(\d+)\s*\(\d+\)(?:\([a-z]\))?")
HEADING_NUMBER_RE = re.compile(r"^\s*(\d{1,3})\s*\.", re.M)
RULE_ID_PREFIX_RE = re.compile(r"^ICDR[_\-\s]*(.+)$", re.I)
CLAUSE_TOKEN_SPLIT_RE = re.compile(r"[_\s]+")
SOURCE_NUM_RE = re.compile(r"(\d+)")
SOURCE_CLAUSE_RE = re.compile(r"\((\d+|[A-Za-z])\)")

# Pre-identification: matches ICDR regulation headings like "4.", "8A.", "22. (1) A..."
REG_HEADER_RE = re.compile(
    r"(?:^|\n)\s*"          # line start / after newline
    r"(\d+[A-Z]?)"          # regulation number, e.g. 8, 8A
    r"\."                   # literal dot
    r"\s+"                  # whitespace after dot
    r"(?:\(\d+\)\s*)?"      # optional sub-reg like (1)
    r"([A-Z])",             # clause text starts with capital letter
    re.MULTILINE,
)

# Footnote amendment markers to exclude
FOOTNOTE_RE = re.compile(r"\d+\[(?:Substituted|Inserted|Re-?numbered)", re.I)

# Regex for converting "5(1)(a)" -> tokens ["5","1","a"]
_REG_NUM_TOKEN_RE = re.compile(r"(\d+[A-Z]?|[a-z]+)")


# --- Bug fix 12.1: Canonicalize proviso markers BEFORE tokenization ---

def canonicalize_proviso_markers(reg_number: str) -> str:
    """
    Replace natural-language proviso/explanation markers with canonical short tokens
    BEFORE the regex tokenizer runs. This prevents the tokenizer from mangling
    uppercase-initial words like 'Provided' into 'rovided'.

    Examples:
        "6(1)(Provided further)" -> "6(1)(proviso2)"
        "8(Provided)"           -> "8(proviso)"
        "6(3)(Explanation)"     -> "6(3)(explanation)"
        "Provided further"      -> "proviso2"
        "Provided that"         -> "proviso"
    """
    s = reg_number
    # Order matters: match "Provided further" before bare "Provided"
    # Use \s* (not \s+) to also catch "ProvidedFurther" with no space
    s = re.sub(r"Provided\s*further", "proviso2", s, flags=re.I)
    s = re.sub(r"Provided\s*that", "proviso", s, flags=re.I)
    s = re.sub(r"Provided", "proviso", s, flags=re.I)
    s = re.sub(r"Explanation", "explanation", s, flags=re.I)
    s = re.sub(r"Category", "category", s, flags=re.I)
    return s


def pre_identify_regulations(page_text: str) -> List[str]:
    """
    Deterministically identify ICDR regulation numbers visible on a single page.
    Returns a sorted list of regulation number strings, e.g. ['5', '6', '8A'].
    """
    found: set[str] = set()
    for m in REG_HEADER_RE.finditer(page_text):
        reg_num = m.group(1)
        ctx_start = max(0, m.start() - 5)
        context = page_text[ctx_start : m.end() + 20]
        if FOOTNOTE_RE.search(context):
            continue
        try:
            if int(re.match(r"\d+", reg_num).group()) > 100:
                continue
        except Exception:
            continue
        found.add(reg_num)
    return sorted(found, key=lambda x: (int(re.match(r"\d+", x).group()), x))


def detect_allowed_regs(window_text: str) -> set[int]:
    """Detect regulation numbers explicitly present within the window text."""
    regs: set[int] = set()
    for m in REG_RE.finditer(window_text):
        try:
            regs.add(int(m.group(1)))
        except Exception:
            continue
    for m in CLAUSE_PREFIX_RE.finditer(window_text):
        try:
            regs.add(int(m.group(1)))
        except Exception:
            continue
    for m in HEADING_NUMBER_RE.finditer(window_text):
        try:
            regs.add(int(m.group(1)))
        except Exception:
            continue
    return regs


def extract_reg_from_source_text(reg_text: str) -> int | None:
    if not isinstance(reg_text, str):
        return None
    m = REG_RE.search(reg_text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m = SOURCE_NUM_RE.search(reg_text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def normalize_rule_identifier(item: dict) -> int | None:
    """Normalize a rule_id to canonical ICDR_N_... format."""
    raw_rule_id = str(item.get("rule_id", "")).strip()
    if not raw_rule_id:
        return None
    body_match = RULE_ID_PREFIX_RE.match(raw_rule_id)
    if not body_match:
        return None
    body = body_match.group(1)
    # Bug fix 12.1: canonicalize proviso markers before tokenization
    body = canonicalize_proviso_markers(body)
    body = (
        body.replace("(", "_")
        .replace(")", "_")
        .replace(".", "_")
        .replace("__", "_")
    )
    body = re.sub(r"[^0-9A-Za-z_]+", "_", body)
    body = re.sub(r"_+", "_", body).strip("_")
    tokens = [tok for tok in CLAUSE_TOKEN_SPLIT_RE.split(body) if tok]
    reg_token = None
    rest_tokens: list[str] = []
    for tok in tokens:
        # Bug fix 12.3: handle alphanumeric regulation numbers like "8A"
        if reg_token is None and re.match(r"^\d+[A-Za-z]?$", tok):
            reg_token = tok
        else:
            rest_tokens.append(tok.lower())

    source = item.get("source") or {}
    source_reg = source.get("reg", "") if isinstance(source, dict) else ""
    reg_from_source = extract_reg_from_source_text(source_reg)
    reg_no = None
    repair_notes: list[str] = []
    if reg_token:
        try:
            reg_no = int(re.match(r"\d+", reg_token).group())
        except Exception:
            pass
    if reg_from_source is not None:
        if reg_no is None:
            reg_no = reg_from_source
            repair_notes.append("reg_inferred_from_source")
        elif reg_no != reg_from_source:
            reg_no = reg_from_source
            repair_notes.append(
                f"reg_mismatch(rule:{reg_token}->source:{reg_from_source})"
            )
    if reg_no is None:
        return None

    # Use the full reg_token (e.g. "8A") if it has a letter suffix
    reg_prefix = reg_token if (reg_token and re.match(r"^\d+[A-Za-z]$", reg_token)) else str(reg_no)

    suffix = "_".join(rest_tokens)
    normalized_rule_id = f"ICDR_{reg_prefix}"
    if suffix:
        normalized_rule_id += f"_{suffix}"

    # Bug fix 12.2: truncate absurdly long rule_ids from full-text reg_numbers
    if len(normalized_rule_id) > 50:
        parts = normalized_rule_id.split("_")
        if len(parts) > 5:
            normalized_rule_id = "_".join(parts[:5])
            repair_notes.append(f"rule_id_truncated_from_{len(parts)}_tokens")

    item["rule_id_raw"] = raw_rule_id
    item["rule_id"] = normalized_rule_id
    item["rule_id_norm"] = f"ICDR_{reg_no}"
    item["sub_id"] = suffix
    item["lean_id"] = "rule_" + normalized_rule_id[5:].lower()
    if repair_notes:
        item.setdefault("repair_notes", []).extend(repair_notes)
    return reg_no


# --- Two-pass extraction helpers ---

_PASS1_SYSTEM = (
    "You are a legal document analyst. Your ONLY task is to identify and list "
    "all numbered regulation clauses visible in the text provided. "
    "Do NOT extract rules, do NOT assign field types, do NOT add maps_to. "
    "Return a JSON array of clause objects."
)

_PASS1_USER_TEMPLATE = """\
Identify ALL numbered regulation clauses visible in the text below.

For each clause return a JSON object with these exact keys:
  "reg_number"  : the clause number as it appears (e.g. "5(1)(a)", "14(1)", "8A")
  "clause_text" : verbatim text of the clause, max 500 chars
  "span_hint"   : first 10 words of the clause text
  "is_proviso"  : true if this is a Provided/Explanation clause, else false

Rules:
- Look for patterns like "N. (1)" or "(a)" at line starts.
- The regulation number is the FIRST number before (1), (2), etc.
  e.g. "8. Only such fully paid-up..." means Regulation 8.
- Ignore footnote superscripts like 25[], 26[Substituted...].
- Include provisos and explanations as separate entries with is_proviso=true.
- If no clauses are found, return [].

TEXT:
{page_text}
"""


def identify_regulations(
    client: OllamaClient,
    model: str,
    page_text: str,
    page_nums: list[int],
    visible_regs: set[str] | None = None,
    timeout: int = 120,
    debug: bool = False,
) -> list[dict]:
    """
    Pass 1: Identify which regulation clauses appear in this text window.
    Returns a list of dicts: {reg_number, clause_text, span_hint, is_proviso}.
    """
    reg_context = ""
    if visible_regs:
        reg_list = ", ".join(
            sorted(visible_regs, key=lambda x: (int(re.match(r"\d+", x).group()), x))
        )
        reg_context = (
            f"IMPORTANT CONTEXT: The following top-level regulation numbers are "
            f"structurally visible on these pages: {reg_list}\n"
            f"Sub-clauses like (1)(a), (2), (3)(ii) belong to one of these parent "
            f"regulations. Always prefix with the parent number.\n"
            f"Example -- if Regulation 6 and 7 are visible:\n"
            f"  (3)(ii) under Reg 6  ->  reg_number: '6(3)(ii)'\n"
            f"  (1)(a) under Reg 7   ->  reg_number: '7(1)(a)'\n"
            f"Never output a bare '(1)' or '(3)(ii)' without its parent number.\n\n"
        )

    user = reg_context + _PASS1_USER_TEMPLATE.format(page_text=page_text[:8000])
    if debug:
        print(f"[Pass1] Sending {len(user)} chars to model", file=sys.stderr)
    try:
        result = client.chat_json_any(model, _PASS1_SYSTEM, user, timeout=timeout, debug=debug, debug_raw=debug)
    except Exception as e:
        if debug:
            print(f"[Pass1] model call failed: {e}", file=sys.stderr)
        return []
    if debug:
        print(f"[Pass1] raw result type={type(result).__name__} value={json.dumps(result, default=str)[:500]}", file=sys.stderr)
    if not result:
        return []
    items = coerce_rules_from_parsed(result) if isinstance(result, (dict, list)) else []
    if debug:
        regs = [r.get("reg_number") for r in items if isinstance(r, dict)]
        print(f"[Pass1] pages={page_nums} identified: {regs}", file=sys.stderr)
    items = [r for r in items if isinstance(r, dict) and r.get("reg_number")]

    # Bug fix 12.4: If regex found more regulations than the LLM, retry once
    if visible_regs and len(items) < len(visible_regs):
        if debug:
            print(f"[Pass1] LLM found {len(items)} clauses but regex found "
                  f"{len(visible_regs)} regs; retrying with explicit enumeration",
                  file=sys.stderr)
        missing_hint = (
            f"\nWARNING: You may have missed some clauses. The following regulations "
            f"are structurally visible: {sorted(visible_regs)}. "
            f"You found clauses for: {[r.get('reg_number','')[:10] for r in items]}. "
            f"Please re-check and include ALL sub-clauses.\n\n"
        )
        user_retry = missing_hint + reg_context + _PASS1_USER_TEMPLATE.format(
            page_text=page_text[:8000]
        )
        try:
            result_retry = client.chat_json_any(model, _PASS1_SYSTEM, user_retry,
                                                 timeout=timeout, debug=debug)
            if result_retry:
                items_retry = coerce_rules_from_parsed(result_retry)
                items_retry = [r for r in items_retry if isinstance(r, dict) and r.get("reg_number")]
                if len(items_retry) > len(items):
                    items = items_retry
                    if debug:
                        print(f"[Pass1] Retry improved: {len(items)} clauses", file=sys.stderr)
        except Exception:
            pass  # Keep original results

    return items


def build_targeted_extraction_prompt(
    reg_number: str,
    clause_text: str,
    page_nums: list[int],
    pdf_name: str = "<PDF>",
) -> str:
    """
    Pass 2: Build an extraction prompt for a single pre-identified clause.
    """
    # Bug fix 12.2: If reg_number is unreasonably long, it's proviso text
    if len(reg_number) > 40:
        prefix_match = re.match(r"(\d+[A-Za-z]?(?:\(\d+\))*)", reg_number)
        if prefix_match:
            reg_number = prefix_match.group(1) + "_proviso"

    # Bug fix 12.1: canonicalize proviso markers before tokenization
    reg_number_clean = canonicalize_proviso_markers(reg_number)
    tokens = _REG_NUM_TOKEN_RE.findall(reg_number_clean)
    rule_id = "ICDR_" + "_".join(t.lower() for t in tokens) if tokens else "ICDR_unknown"
    lean_id = "rule_" + "_".join(t.lower() for t in tokens) if tokens else "rule_unknown"

    return (
        f"Extract ONE atomic compliance rule from this regulation clause.\n"
        f"\n"
        f"REGULATION NUMBER (pre-validated -- DO NOT change): {reg_number}\n"
        f"RULE_ID to use: {rule_id}\n"
        f"LEAN_ID to use: {lean_id}\n"
        f"SOURCE PAGES: {page_nums}\n"
        f"SOURCE PDF: {pdf_name}\n"
        f"\n"
        f"Before emitting maps_to, decompose the clause:\n"
        f"  1. SUBJECT   - Who must comply? (issuer, promoter, director, etc.)\n"
        f"  2. CONDITION - What triggers the requirement?\n"
        f"  3. CONSTRAINT- What is the measurable check?\n"
        f"  4. CONTEXT   - Exceptions, provisos, explanations\n"
        f"\n"
        f"Derive maps_to from the CONSTRAINT only:\n"
        f"  - Numeric threshold? -> Nat (single) or List Nat (multi-year)\n"
        f"  - Yes/no compliance flag? -> Bool\n"
        f"  - 'in each of the preceding N years'? -> List Nat (length=N)\n"
        f"  - Field name must be UNIQUE across all regulations:\n"
        f"    BAD:  'conditions', 'exceptions', 'securities'\n"
        f"    GOOD: 'promoter_min_contribution_pct', 'is_debarred', 'ofs_holding_years'\n"
        f"\n"
        f"Output a single JSON object (NOT an array) matching the rule schema.\n"
        f"\n"
        f"CLAUSE TEXT:\n{clause_text[:1500]}\n"
    )

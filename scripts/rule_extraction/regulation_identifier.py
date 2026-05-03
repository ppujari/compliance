"""Deterministic regulation identification from PDF text structure."""

from __future__ import annotations
import json, re, sys
from typing import Any, List, Dict

from .ollama_client import OllamaClient, coerce_rules_from_parsed
from .regex_patterns import FOOTNOTE_DEF_RE, INLINE_FOOTNOTE_RE, INSERTED_SUBREG_RE

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
    r"([A-Za-z])",          # clause start — some prints use lowercase after the dot
    re.MULTILINE,
)

# Footnote amendment markers to exclude
FOOTNOTE_RE = re.compile(r"\d+\[(?:Substituted|Inserted|Re-?numbered)", re.I)

# Pattern C: orphaned amendment footnote tails — cross-page footnote continuation
# fragments that begin mid-sentence with "(Amendment) Regulations..." without a
# leading digit. These survive Pattern B because they have no digit at line start.
FOOTNOTE_TAIL_RE = re.compile(
    r"^\s*\((?:Amendment|Ammendment|Substitut\w+|Insert\w+|Renumber\w+|Omitt\w+)"
    r"[^)]*\)\s+(?:Regulations?|Rules?|Act)\b[^\n]*(?:\n|$)",
    re.MULTILINE | re.IGNORECASE,
)

# Regex for converting "5(1)(a)" -> tokens ["5","1","a"]
_REG_NUM_TOKEN_RE = re.compile(r"(\d+[A-Z]?|[a-z]+)")


# --- Bug fix 12.1: Canonicalize proviso markers BEFORE tokenization ---

def extract_amendment_footnotes(window_text: str) -> List[Dict[str, Any]]:
    """
    Extract amendment metadata from footnote definition lines before they are stripped.
    Returns list of dicts with footnote_number, action, and notification text.
    """
    results: List[Dict[str, Any]] = []
    for m in re.finditer(
        r"^[ \t]*(\d{1,3})[ \t]+"
        r"(Substituted|Inserted|Renumbered|Omitted|Added|Amended)"
        r"\s+by\s+(.+?)(?:\n|$)",
        window_text,
        re.MULTILINE | re.IGNORECASE,
    ):
        results.append(
            {
                "footnote_number": int(m.group(1)),
                "action": m.group(2).capitalize(),
                "notification_text": m.group(3).strip(),
            }
        )
    return results


def strip_footnotes_with_linkage(
    window_text: str,
    current_reg_context: str = "",
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Strip footnotes and return (cleaned_text, linkage_records).

    Each linkage record maps a footnote number to the regulation clause
    it was found inside, based on position in the raw text.
    """
    linkage: List[Dict[str, Any]] = []

    # Find inline citations with their position before stripping.
    for m in INLINE_FOOTNOTE_RE.finditer(window_text):
        footnote_num = int(m.group(1))
        bracket_start = m.end()  # points to "["
        bracket_end = window_text.find("]", bracket_start)
        amended_text = (
            window_text[bracket_start + 1 : bracket_end].strip()
            if bracket_end != -1 else ""
        )
        linkage.append(
            {
                "footnote_number": footnote_num,
                "amended_text": amended_text[:200],
                "reg_context": current_reg_context,
            }
        )

    # Pattern B first: remove entire footnote definition lines
    text = FOOTNOTE_DEF_RE.sub("", window_text)
    # Pattern A: strip numeric citation marker, keep bracketed text
    text = INLINE_FOOTNOTE_RE.sub("", text)
    # Pattern C: remove orphaned amendment tails (cross-page footnote fragments
    # that start with "(Amendment)..." without a leading digit)
    text = FOOTNOTE_TAIL_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, linkage


def strip_footnotes(window_text: str) -> str:
    """
    Remove footnote markers and footnote definition lines from PDF-extracted text
    before Pass 1 processing.

    Handles two patterns from Indian statutory PDFs:

    Pattern A — inline citation: '25[filing]' → '[filing]'
        Strips the footnote number; keeps the bracketed substituted text
        because it IS the current legal text.

    Pattern B — footnote definition line:
        '25 Substituted by the Securities and Exchange Board...'
        Removes the ENTIRE line — it is editorial apparatus, not regulatory content.
    """
    text, _ = strip_footnotes_with_linkage(window_text)
    return text


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
    inserted_subregs: set[str] = set()
    last_seen_top_reg = ""
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
        last_seen_top_reg = reg_num

    # Detect amendment-inserted sub-regulations (e.g. "[(3) The amount for:")
    for m in INSERTED_SUBREG_RE.finditer(page_text):
        inserted_num = m.group(1)
        if last_seen_top_reg:
            inserted_id = f"{last_seen_top_reg}({inserted_num})"
            inserted_subregs.add(inserted_id)
            found.add(inserted_id)

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
    # Fallback — bare heading numbers like "4." at line start (regs with no
    # sub-clauses never appear as "Regulation N" in their own body text).
    for m in HEADING_NUMBER_RE.finditer(window_text):
        try:
            n = int(m.group(1))
            if 1 <= n <= 100:
                regs.add(n)
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
    "Return a JSON object with a single key \"clauses\" containing the array. Example: {{\"clauses\": [...]}}.\n"
    "- IGNORE footnote citation numbers. In Indian statutory PDFs these appear as:\n"
    "  (a) A number immediately before a \"[\" bracket mid-text: e.g. \"25[filing]\", "
    "\"14[(3) some clause text]\". The number is a footnote reference, NOT a regulation "
    "number. The text in brackets is the current amended content of that regulation.\n"
    "  (b) A number at line start followed by \"Substituted by\", \"Inserted by\", "
    "\"Renumbered by\": e.g. \"25 Substituted by the Securities and Exchange Board...\". "
    "These are footnote definitions — ignore the entire line.\n"
    "- Sub-clauses of a regulation may use different formatting styles:\n"
    "  Standard parenthesised: (a), (b), (i), (ii)\n"
    "  Indented dot style: a., b., c. or i., ii., iii. (letter/numeral with dot, no parentheses)\n"
    "  Both styles are valid sub-clauses and must be captured.\n"
    "- When a page opens with lettered items (a., b., c.) or roman numeral items "
    "(i., ii., iii.) and NO visible parent regulation number, treat them as continuations "
    "of the last known regulation from visible_regs and any CONTINUATION HINT provided. "
    "Assign them under the deepest sub-clause level indicated by the hint.\n"
    "AMENDMENT-INSERTED SUB-REGULATIONS:\n"
    "Some sub-regulations were inserted by amendment and appear as text beginning with "
    "\"[(N)\" at the start of a line, for example \"[(3) The amount for general corporate "
    "purposes...\". The leading \"[\" is a residual amendment bracket -- it does NOT mean "
    "the sub-regulation number is wrong.\n"
    "- When you encounter \"[(N) ...\" at line start, treat it as sub-regulation (N) of "
    "the most recently seen parent regulation.\n"
    "- Example: if Regulation 7 was the last top-level header and you see \"[(3) The "
    "amount for:\", extract it as reg_number \"7(3)\" with clause_text starting from "
    "\"The amount for:\".\n"
    "- Similarly extract any \"Provided that\" clauses within that block as "
    "\"7(3)(proviso)\" and \"7(3)(proviso)(2)\".\n"
    "EXPLANATION BLOCKS:\n"
    "Text beginning with \"Explanation.\" or \"Explanation :\" immediately following a "
    "regulation or sub-regulation is a separate structural element. Extract it as a "
    "separate clause with reg_number \"N(explanation)\" where N is the parent regulation "
    "number -- for example, Regulation 8's Explanation block should have reg_number "
    "\"8(explanation)\".\n"
    "Do not merge explanation text into the clause_text of the parent rule.\n"
    "LISTS OF LETTERED OR ROMAN-NUMERAL ITEMS — EMIT EACH AS A SEPARATE OBJECT:\n"
    "When a clause contains a list introduced by a colon or dash, followed by\n"
    "lettered items (a., b., c.) or roman-numeral items (i., ii., iii.), each\n"
    "item in the list is a SEPARATE clause and must appear as a SEPARATE object\n"
    "in the output array. Do NOT merge two or more list items into one object.\n"
    "Do NOT include 'b. ...' text inside an object whose reg_number ends in '(a)'.\n\n"
    "For the parent clause that introduces the list:\n"
    "  - Its clause_text must end BEFORE the first listed item (at the dash or colon).\n"
    "  - Each listed item gets its own object with reg_number = parent + (letter).\n\n"
    "Example: a clause reading 'The notice shall specify:\n"
    "  a. the size of the issue,\n"
    "  b. the ratio of voting rights,\n"
    "  c. the lock-in period'\n"
    "must produce FOUR objects: one for the parent ending at 'specify:', then\n"
    "one each for (a), (b), and (c) — never a single merged object.\n"
)

_PASS1_USER_TEMPLATE = """\
Identify ALL numbered regulation clauses visible in the text below.

For each clause return a JSON object with these exact keys:
  "reg_number"  : the clause number as it appears (e.g. "5(1)(a)", "14(1)", "8A")
  "clause_text" : verbatim text of the clause INCLUDING any "Provided that" or
                  "Provided further that" sub-clauses nested within it.
                  Max 1200 chars. If the clause is longer, include the full
                  opening sentence and all Provided/Explanation blocks even if
                  you must omit middle body text.
  "span_hint"   : first 10 words of the clause text
  "is_proviso"  : true if this is a Provided/Explanation clause, else false

Rules:
- Look for patterns like "N. (1)" or "(a)" at line starts.
- The regulation number is the FIRST number before (1), (2), etc.
  e.g. "8. Only such fully paid-up..." means Regulation 8.
- Ignore footnote superscripts like 25[], 26[Substituted...].
- Include provisos and explanations as separate entries with is_proviso=true.
- Each lettered item (a., b., c.) and each roman-numeral item (i., ii., iii.)
  is a SEPARATE clause — emit exactly one object per item, never merge two into one.
- When a parent clause ends with a colon or dash followed by a list, the parent's
  clause_text ends at the colon/dash. Each list item follows as its own object.
- Return a JSON object with a single key "clauses" containing the array. Example: {{"clauses": [...]}}.
- If no clauses are found, return {{"clauses": []}}.

TEXT:
{page_text}
"""


def split_merged_lettered_items(items: list[dict]) -> list[dict]:
    """
    Deterministic post-processing: if a Pass 1 clause object whose reg_number
    ends in a single letter (e.g. 'N(X)(a)') has clause_text that contains
    multiple lettered items merged together (e.g. 'a. text1, b. text2, c. text3'),
    split it into one object per item.

    Safety net for cases where the LLM ignores the prompt instruction to emit
    separate objects. Regulation-agnostic.
    """
    # Matches a lettered item boundary after the first item: "b. ", "c. " etc.
    ITEM_SPLIT_RE = re.compile(
        r"(?:(?:^|(?<=,)|(?<=;))\s*)([b-e])\.\s+",
        re.MULTILINE,
    )
    TERMINAL_LETTER_RE = re.compile(r"\(([a-e])\)$")

    result = []
    for item in items:
        reg_num = (item.get("reg_number") or "").strip()
        clause_text = (item.get("clause_text") or "").strip()

        m = TERMINAL_LETTER_RE.search(reg_num)
        if not m:
            result.append(item)
            continue

        parent_letter = m.group(1)
        parent_path = reg_num[: m.start()]

        splits = ITEM_SPLIT_RE.split(clause_text)
        if len(splits) <= 1:
            result.append(item)
            continue

        # splits = [text_of_a, "b", text_of_b, "c", text_of_c, ...]
        chunks: list[tuple[str, str]] = []
        first_text = splits[0].strip()
        if first_text:
            chunks.append((parent_letter, first_text))
        i = 1
        while i < len(splits) - 1:
            letter = splits[i]
            text = splits[i + 1].strip()
            if text:
                chunks.append((letter, text))
            i += 2

        if len(chunks) <= 1:
            result.append(item)
            continue

        for letter, text in chunks:
            new_item = dict(item)
            new_item["reg_number"] = f"{parent_path}({letter})"
            new_item["clause_text"] = f"{letter}. {text}"
            new_item["span_hint"] = " ".join(text.split()[:10])
            new_item["is_proviso"] = item.get("is_proviso", False)
            result.append(new_item)

    return result


def identify_regulations(
    client: OllamaClient,
    model: str,
    page_text: str,
    page_nums: list[int],
    visible_regs: set[str] | None = None,
    carryover_hint: str = "",
    system_prefix: str = "",
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
        # When a carryover hint is also present, explicitly warn the model that
        # items at the very start of the window may be continuations from the
        # previous window and the continuation hint takes priority over the
        # top-level list for those items.
        if carryover_hint:
            reg_context += (
                f"NOTE: Items at the very start of this window may be continuations "
                f"from the previous window — see the CONTINUATION HINT. "
                f"The continuation hint takes priority over inferring parent from "
                f"the top-level list alone. Do not assign a bare roman numeral or "
                f"letter directly to a top-level regulation when a continuation "
                f"hint is present.\n\n"
            )

    base_user = reg_context + _PASS1_USER_TEMPLATE.format(page_text=page_text[:8000])
    ch = (carryover_hint or "").strip()
    user = (ch + "\n\n" + base_user) if ch else base_user
    pass1_system = f"{system_prefix or ''}{_PASS1_SYSTEM}"
    if debug:
        print(f"[Pass1] Sending {len(user)} chars to model", file=sys.stderr)
    try:
        result = client.chat_json_any(model, pass1_system, user, timeout=timeout, debug=debug, debug_raw=debug)
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
        base_retry = missing_hint + reg_context + _PASS1_USER_TEMPLATE.format(
            page_text=page_text[:8000]
        )
        user_retry = (ch + "\n\n" + base_retry) if ch else base_retry
        try:
            result_retry = client.chat_json_any(model, pass1_system, user_retry,
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

    # Deterministic safety net: split any merged lettered items the LLM produced
    items = split_merged_lettered_items(items)

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

    nested_proviso_instruction = (
        "NESTED PROVISOS -- CRITICAL:\n"
        "If the clause_text contains one or more \"Provided that\" or \"Provided further that\"\n"
        "sub-clauses, you MUST emit them as SEPARATE JSON objects in your output array.\n"
        "Do NOT fold proviso text into the parent rule's text field.\n\n"
        "Naming convention:\n"
        "- First \"Provided that\"  -> rule_id = \"{parent_id}_proviso\"\n"
        "- Second \"Provided that\" -> rule_id = \"{parent_id}_proviso_2\"\n"
        "- \"Provided further that\" -> rule_id = \"{parent_id}_proviso_2\" (or _proviso_3 if a third)\n\n"
        "Always emit the parent rule AND each proviso as separate objects. Never merge them.\n\n"
        "MAIN RULE + PROVISO SEPARATION -- ALWAYS REQUIRED:\n"
        "If a clause begins with the main regulatory obligation AND also contains a\n"
        "\"Provided that\" sub-clause, you MUST emit them as two separate JSON objects:\n"
        "1. The main rule (with rule_id = \"{reg_id}\") containing only the prohibition\n"
        "   or requirement text, NOT the proviso.\n"
        "2. The proviso (with rule_id = \"{reg_id}_proviso\") containing the \"Provided\n"
        "   that...\" text.\n"
        "Never merge a main rule and its proviso into a single object.\n"
    )

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
        f"{nested_proviso_instruction}\n"
        f"Output JSON matching the rule schema. If no provisos exist, emit one object. "
        f"If provisos exist, emit an array of objects.\n"
        f"\n"
        f"CLAUSE TEXT:\n{clause_text[:1200]}\n"
    )

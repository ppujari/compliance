# Rule Extraction MVP: Modularization & Metadata Enrichment

## Instructions for Claude Code CLI

**Model recommendation:** Use `claude-opus-4-6` for this task. The refactoring involves architectural decisions across 7+ files, understanding of regulatory domain semantics, and maintaining backward compatibility with the existing pipeline. Opus is the right choice for the complexity and judgment required. If token budget is a concern, `claude-sonnet-4-6` is acceptable for the simpler phases (1-3) but Opus should be used for Phases 4-6.

**Working directory:** `compliance/` (the root of the repo at `github.com/saunakp123/compliance`)

---

## Context: What This Project Is

This is an automated regulatory compliance pipeline that extracts rules from SEBI ICDR (Securities and Exchange Board of India, Issue of Capital and Disclosure Requirements) regulations, then formally verifies IPO filings against those rules using Lean 4. The pipeline runs locally on Windows with Ollama serving open-source LLMs (typically `qwen2.5:14b-instruct` for extraction, `deepseek-r1:14b` for judging).

The current rule extraction script (`scripts/llm_extract_rules.py`) is a single 1874-line file that handles everything: PDF reading, regex-based regulation identification, LLM-based extraction, validation, judging, and output. It works for a POC (regulations 4-22 of ICDR Chapter II), but needs to be modularized and enriched with regulatory metadata to become an MVP that can:

1. Scale to the full ICDR (301 regulations, 12 chapters, 20 schedules, 252 pages)
2. Track amendment history and effective dates
3. Support multiple jurisdictions in the future (US SEC, UK FCA, etc.)
4. Serve a product that answers "which regulations apply to this IPO?"

---

## Current State of `llm_extract_rules.py`

The file has these logical sections (approximate line ranges):

| Lines | Section | Description |
|-------|---------|-------------|
| 1-40 | Imports & setup | Imports, rule_refiner import |
| 42-77 | Few-shot loader | `load_fewshot_examples()` |
| 74-120 | Schema setup | `RULE_SCHEMA`, `VALIDATOR`, `ARRAY_RULES_SCHEMA` |
| 80-114 | Judge schema | `JUDGE_SCHEMA`, `JUDGE_WEIGHTS` |
| 122-176 | Sanitization | `build_ollama_json_schema_format()`, `sanitize_for_schema()`, `clamp_span_hint()` |
| 191-299 | Validation functions | `validate_required_fields()`, `validate_rule_id_format()`, `validate_maps_to()`, `validate_source()`, `validate_reg_anchoring()`, `detect_duplicates()` |
| 302-373 | Judge/regen prompts | `compute_overall_score()`, `build_judge_prompt()`, `build_regen_prompt()` |
| 376-480 | Ollama client | `ollama_chat_json_any()`, `extract_first_json_block()`, `coerce_rules_from_parsed()` |
| 482-523 | Subrule flattening | `flatten_subrules()` |
| 526-718 | Static prompts | `SYSTEM_PROMPT`, few-shot examples (3 examples + bad explanation) |
| 720-924 | Ollama endpoints | `ollama_generate_json()`, `ollama_chat_json()` with fallback logic |
| 926-956 | PDF utils | `read_pdf_pages()`, `windowed()` |
| 958-1050 | Regulation detection | `REG_HEADER_RE`, `strip_page_numbers()`, `pre_identify_regulations()` |
| 1052-1253 | Normalization/anchoring | `detect_allowed_regs()`, span hint helpers, `normalize_rule_identifier()` |
| 1255-1393 | Two-pass helpers | `identify_regulations()`, `build_targeted_extraction_prompt()` |
| 1396-1874 | Main pipeline | `main()` — argparse, window loop, two-pass orchestration, judge loop, validation, dedup, output |

### Key dependencies:
- `scripts/rule_refiner.py` — imported as `RuleRefiner`, `OllamaClient`; handles judge+regen loop
- `data/schema/rules_schema.json` — JSON Schema for rule validation
- Ollama running locally at `http://localhost:11434`

### Known issues in current code:
1. `--model` default is still `llama3:8b` (line 1407) — should be updated
2. Double anchoring validation: `validate_reg_anchoring` runs in both judge block (line 1624) and general loop (line 1749), penalizing mismatched rules by 0.4 total instead of 0.2
3. Pass 1 and Pass 2 both use `args.model` — no separate `--model-identify` and `--model-extract` flags
4. All metadata is SEBI-ICDR-specific and hardcoded (`domain: "SEBI_ICDR"`, `rule_id: "ICDR_..."`)

---

## Phase 1: Create the Module Structure

Create the following directory structure under `scripts/`:

```
scripts/
  rule_extraction/
    __init__.py              # Package init, re-exports key functions
    pdf_loader.py            # PDF reading, page windowing, page number stripping
    regulation_identifier.py # Regex-based pre_identify_regulations, REG_HEADER_RE, etc.
    rule_extractor.py        # LLM prompts, two-pass orchestration, few-shot examples
    rule_validator.py        # Schema validation, reg anchoring, span hint checks
    metadata_enricher.py     # NEW: chapter/part/schedule lookup, jurisdiction tagging
    rule_store.py            # NEW: enriched JSONL/JSON output with versioning
    ollama_client.py         # Ollama HTTP client, JSON extraction, retry/fallback logic
  llm_extract_rules.py      # Slim orchestrator that imports from rule_extraction/
  rule_refiner.py            # Unchanged (already separate)
```

### `__init__.py`

```python
"""Rule extraction package for regulatory compliance pipeline."""
```

Do NOT re-export everything from `__init__.py`. Each module should be imported explicitly where needed: `from scripts.rule_extraction.pdf_loader import read_pdf_pages, windowed`.

---

## Phase 2: Extract `ollama_client.py`

Move these functions from `llm_extract_rules.py`:

- `extract_first_json_block()` (lines 398-448)
- `coerce_rules_from_parsed()` (lines 451-479)
- `ollama_chat_json_any()` (lines 376-394)
- `ollama_generate_json()` (lines 721-818)
- `ollama_chat_json()` (lines 821-924)

Also move the Ollama URL constant and create a proper client class:

```python
# scripts/rule_extraction/ollama_client.py

OLLAMA_BASE_URL = "http://localhost:11434"

class OllamaClient:
    """Wrapper for Ollama API calls with JSON mode and fallback logic."""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: int = 120,
                 temperature: float = 0.1, top_p: float = 0.9):
        self.base_url = base_url
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
    
    def chat_json(self, model, system, user, fewshots=None, debug=False, debug_raw=False):
        """Chat endpoint with JSON mode. Falls back to generate endpoint on 404."""
        ...
    
    def chat_json_any(self, model, system, user, debug=False, debug_raw=False):
        """Single-call JSON extraction (used by Pass 1 and Pass 2)."""
        ...
    
    def generate_json(self, model, system, user, fewshots=None, debug=False, debug_raw=False):
        """Generate endpoint fallback."""
        ...
```

**Important:** `rule_refiner.py` already has its own `OllamaClient` class. The existing import at line 36 renames it: `from rule_refiner import OllamaClient as RefinerOllamaClient`. Keep that import working — the refiner's client should remain separate for now. In a future pass, both can be unified.

**Test:** After this phase, run `python -c "from scripts.rule_extraction.ollama_client import OllamaClient"` to verify the import works.

---

## Phase 3: Extract `pdf_loader.py`

Move these functions:

- `read_pdf_pages()` (lines 927-946)
- `windowed()` (lines 948-955)
- `strip_page_numbers()` (lines 1004-1019)

```python
# scripts/rule_extraction/pdf_loader.py
"""PDF reading utilities for regulatory document extraction."""

from pathlib import Path

def read_pdf_pages(pdf_path: Path) -> list[str]:
    """Extract text from each page of a PDF. Tries PyMuPDF first, falls back to pdfminer."""
    ...

def windowed(pages: list[str], w: int, overlap: int):
    """Yield (start_index, page_list) tuples for sliding window over pages."""
    ...

def strip_page_numbers(page_text: str) -> str:
    """Remove bare page numbers from the top of a PDF page."""
    ...
```

**Test:** `python -c "from scripts.rule_extraction.pdf_loader import read_pdf_pages; pages = read_pdf_pages(Path('data/input/SEBI_ICDR_2018.pdf')); print(f'{len(pages)} pages')"` — should print `252 pages`.

---

## Phase 4: Extract `regulation_identifier.py`

Move all the regex-based regulation detection:

- All compiled regexes: `REG_RE`, `CLAUSE_PREFIX_RE`, `HEADING_NUMBER_RE`, `RULE_ID_PREFIX_RE`, `CLAUSE_TOKEN_SPLIT_RE`, `SOURCE_NUM_RE`, `SOURCE_CLAUSE_RE`, `REG_HEADER_RE`, `FOOTNOTE_RE`, `_REG_NUM_TOKEN_RE` (lines 979-1001, 1344-1345)
- `pre_identify_regulations()` (lines 1022-1050)
- `detect_allowed_regs()` (lines 1053-1074)
- `normalize_rule_identifier()` (lines 1197-1253)
- `extract_reg_from_source_text()` (lines 1179-1194)

Also move the two-pass identification function:
- `identify_regulations()` (lines 1287-1341) — this calls `ollama_chat_json_any`, so it needs the ollama_client import

And the targeted extraction prompt builder:
- `build_targeted_extraction_prompt()` (lines 1348-1393)

```python
# scripts/rule_extraction/regulation_identifier.py
"""Deterministic regulation identification from PDF text structure."""

import re
from typing import List

# --- Compiled regexes ---
REG_HEADER_RE = re.compile(...)  # Pre-identification regex
FOOTNOTE_RE = re.compile(...)
# ... all other regexes

def pre_identify_regulations(page_text: str) -> List[str]:
    """Deterministically identify ICDR regulation numbers visible on a single page."""
    ...

def detect_allowed_regs(window_text: str) -> set[int]:
    """Detect regulation numbers explicitly present within the window text."""
    ...

def identify_regulations(client, model, page_text, page_nums, visible_regs=None, timeout=120, debug=False):
    """Pass 1: LLM-based clause identification with regex anchoring context."""
    ...

def build_targeted_extraction_prompt(reg_number, clause_text, page_nums, pdf_name="<PDF>"):
    """Pass 2: Build extraction prompt for a single pre-identified clause."""
    ...

def normalize_rule_identifier(item: dict) -> int | None:
    """Normalize a rule_id to canonical ICDR_N_... format."""
    ...
```

**Note on `identify_regulations`:** This function currently calls `ollama_chat_json_any` directly. Refactor it to accept an `OllamaClient` instance as its first parameter instead of a model string. The `_PASS1_SYSTEM` and `_PASS1_USER_TEMPLATE` strings (lines 1258-1284) should move here too.

---

## Phase 5: Extract `rule_validator.py`

Move all validation logic:

- `RULE_ID_FORMAT_RE`, `MAPS_TO_FIELD_RE` (lines 191-192)
- `validate_required_fields()` (lines 195-207)
- `validate_rule_id_format()` (lines 210-211)
- `validate_maps_to()` (lines 214-234)
- `validate_source()` (lines 237-255)
- `validate_reg_anchoring()` (lines 258-286)
- `validate_rule()` (lines 958-976)
- `detect_duplicates()` (lines 289-299)
- All span hint helpers: `normalize_ws()`, `contains_span_hint()`, `normalize_lenient()`, `contains_span_hint_lenient()`, `contains_span_hint_fuzzy()` (lines 1076-1143)
- `sanitize_for_schema()` (lines 136-176)
- `clamp_span_hint()` (lines 179-188)

Also move the schema loading and validation setup:

- `SCHEMA_PATH`, `RULE_SCHEMA`, `VALIDATOR`, `ALLOWED_TOP_KEYS` (lines 74-77)
- `ARRAY_RULES_SCHEMA`, `build_ollama_json_schema_format()` (lines 117-133)

```python
# scripts/rule_extraction/rule_validator.py
"""Rule validation, schema enforcement, and span hint verification."""

from pathlib import Path
from jsonschema import Draft202012Validator
import json, re, unicodedata

SCHEMA_PATH = Path("data/schema/rules_schema.json")
RULE_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(RULE_SCHEMA)
ALLOWED_TOP_KEYS = set((RULE_SCHEMA.get("properties") or {}).keys())

def sanitize_for_schema(item: dict) -> dict: ...
def validate_required_fields(rule: dict) -> list[str]: ...
def validate_rule_id_format(rule_id: str) -> bool: ...
def validate_maps_to(rule: dict) -> list[str]: ...
def validate_source(rule: dict, chunk_text: str, span_mode: str = "lenient") -> list[str]: ...
def validate_reg_anchoring(rule: dict, visible_regs: set[str]) -> list[str]: ...
def validate_rule(item: dict) -> bool: ...
# ... etc
```

---

## Phase 6: Extract `rule_extractor.py`

Move the prompts and extraction-specific logic:

- `SYSTEM_PROMPT` (lines 526-602)
- All few-shot examples: `FEWSHOT_INPUT`, `FEWSHOT_OUTPUT`, `FEWSHOT_BOOL_INPUT`, `FEWSHOT_BOOL_OUTPUT`, `FEWSHOT_BAD_INPUT`, `FEWSHOT_BAD_OUTPUT`, `BAD_EXPLANATION` (lines 604-718)
- `load_fewshot_examples()` (lines 42-72)
- `flatten_subrules()` (lines 482-523)
- Judge-related prompts and scoring: `JUDGE_SCHEMA`, `ARRAY_JUDGE_SCHEMA`, `JUDGE_VALIDATOR`, `JUDGE_WEIGHTS`, `compute_overall_score()`, `build_judge_prompt()`, `build_regen_prompt()` (lines 80-373)
- Dedup/scoring helpers: `MIN_TEXT_CHARS`, `TEXT_SIGNATURE_SLICE`, `normalize_clause_text()`, `item_score()`, `choose_best_item()` (lines 1146-1176)

```python
# scripts/rule_extraction/rule_extractor.py
"""LLM prompts, few-shot examples, judge rubric, and extraction orchestration."""

SYSTEM_PROMPT = """..."""
# ... all prompts and few-shots

def extract_rules_two_pass(client, model, window_text, page_nums, visible_regs, ...):
    """Two-pass extraction: identify clauses, then extract per clause."""
    ...

def extract_rules_single_pass(client, model, system_prompt, user_prompt, ...):
    """Legacy single-pass extraction."""
    ...
```

---

## Phase 7: Create `metadata_enricher.py` (NEW)

This is the key new module. It enriches raw extracted rules with regulatory metadata.

### 7.1 ICDR Structure Lookup Table

A file `data/schema/icdr_structure.json` should be created (or use the one attached as `icdr_structure.json`). It contains the full chapter → part → regulation hierarchy extracted from the SEBI ICDR 2018 PDF. The enricher loads this at startup and uses it to look up which chapter/part a regulation belongs to.

The structure is:
```json
{
  "chapters": [
    {
      "number": "II",
      "title": "INITIAL PUBLIC OFFER ON MAIN BOARD",
      "parts": [
        {
          "number": "I",
          "title": "ELIGIBILITY REQUIREMENTS",
          "regulations": [
            {"number": "4", "title_hint": "Unless otherwise provided..."},
            {"number": "5", "title_hint": "An issuer shall not be eligible..."},
            {"number": "6", "title_hint": "An issuer shall be eligible..."},
            {"number": "7", "title_hint": "An issuer making an initial..."},
            {"number": "8", "title_hint": "Only such fully paid-up..."}
          ]
        },
        ...
      ]
    },
    ...
  ],
  "schedules": [
    {"number": "I", "title": "LEAD MANAGERS' INTER-SE ALLOCATION OF..."},
    ...
  ]
}
```

### 7.2 The Enricher Module

```python
# scripts/rule_extraction/metadata_enricher.py
"""Enrich extracted rules with regulatory metadata: hierarchy, jurisdiction, cross-references."""

import json, re
from pathlib import Path
from typing import Any, Optional
from datetime import date

# --- ICDR Document Structure Lookup ---

_STRUCTURE_PATH = Path("data/schema/icdr_structure.json")

class ICDRStructureLookup:
    """Maps regulation numbers to their chapter/part/schedule context."""
    
    def __init__(self, structure_path: Path = _STRUCTURE_PATH):
        with structure_path.open("r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._reg_to_location = self._build_index()
    
    def _build_index(self) -> dict[str, dict]:
        """Build reg_number -> {chapter, part} index."""
        index = {}
        for chapter in self._data.get("chapters", []):
            ch_info = {"number": chapter["number"], "title": chapter["title"]}
            # Regulations directly under chapter (no part)
            for reg in chapter.get("regulations", []):
                index[reg["number"]] = {"chapter": ch_info, "part": None}
            # Regulations under parts
            for part in chapter.get("parts", []):
                pt_info = {"number": part["number"], "title": part["title"]}
                for reg in part.get("regulations", []):
                    index[reg["number"]] = {"chapter": ch_info, "part": pt_info}
        return index
    
    def lookup(self, reg_number: str) -> dict | None:
        """Look up chapter/part for a regulation number like '6' or '14'."""
        # Extract the top-level regulation number (e.g., '6' from 'ICDR_6_1_a')
        m = re.match(r"(\d+[A-Z]?)", str(reg_number))
        if not m:
            return None
        return self._reg_to_location.get(m.group(1))
    
    def get_schedules(self) -> list[dict]:
        return self._data.get("schedules", [])


# --- Cross-Reference Detection ---

# Patterns for detecting cross-references in rule text
_CROSS_REF_REG = re.compile(r"(?:regulation|sub-regulation)\s+(\d+[A-Z]?(?:\(\d+\))*)", re.I)
_CROSS_REF_SCHEDULE = re.compile(r"Schedule\s+([IVXLC]+)", re.I)
_CROSS_REF_EXTERNAL = re.compile(
    r"(?:Companies Act,?\s*(\d{4}))"
    r"|(?:Securities and Exchange Board of India Act,?\s*(\d{4}))"
    r"|(?:Depositories Act,?\s*(\d{4}))"
    r"|(?:Reserve Bank of India Act,?\s*(\d{4}))",
    re.I,
)

def extract_cross_references(text: str) -> dict:
    """Extract regulation, schedule, and external law references from rule text."""
    refs = {
        "regulations": [],
        "schedules": [],
        "external_acts": [],
    }
    for m in _CROSS_REF_REG.finditer(text):
        reg_ref = m.group(1)
        if reg_ref not in refs["regulations"]:
            refs["regulations"].append(reg_ref)
    for m in _CROSS_REF_SCHEDULE.finditer(text):
        sched = m.group(1)
        if sched not in refs["schedules"]:
            refs["schedules"].append(sched)
    for m in _CROSS_REF_EXTERNAL.finditer(text):
        for i, act_name in enumerate([
            "Companies Act", "SEBI Act", "Depositories Act", "RBI Act"
        ]):
            year = m.group(i + 1)
            if year:
                entry = {"act": act_name, "year": int(year)}
                if entry not in refs["external_acts"]:
                    refs["external_acts"].append(entry)
    return refs


# --- Rule Classification ---

_RULE_TYPE_KEYWORDS = {
    "eligibility": ["eligible", "eligibility", "shall not be eligible", "ineligible"],
    "disclosure": ["disclose", "disclosure", "shall contain", "shall include"],
    "lock_in": ["lock-in", "locked-in", "not be transferable", "lock in"],
    "pricing": ["price", "pricing", "floor price", "price band"],
    "promoter_contribution": ["promoter", "promoters' contribution", "minimum contribution"],
    "procedural": ["shall file", "shall submit", "shall furnish", "shall obtain"],
    "prohibition": ["shall not", "prohibited", "shall not be eligible", "debarred"],
    "allotment": ["allotment", "allot", "basis of allotment"],
}

_ACTOR_KEYWORDS = {
    "issuer": ["issuer", "the issuer shall"],
    "promoter": ["promoter", "promoters'", "promoter group"],
    "lead_manager": ["lead manager", "merchant banker", "book running"],
    "board_of_directors": ["board of directors", "board of the issuer"],
    "selling_shareholder": ["selling shareholder"],
}

_SCOPE_FROM_CHAPTER = {
    "II": ["IPO"],
    "III": ["rights_issue"],
    "IV": ["FPO"],
    "V": ["preferential_issue"],
    "VI": ["QIP"],
    "VII": ["IDR_IPO"],
    "VIII": ["IDR_rights"],
    "IX": ["SME_IPO"],
    "X": ["ITP"],
    "XI": ["bonus_issue"],
}

def classify_rule_type(text: str) -> str:
    """Classify a rule's type based on keyword analysis of its text."""
    text_lower = text.lower()
    best_type = "general"
    best_score = 0
    for rtype, keywords in _RULE_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_type = rtype
    return best_type

def classify_compliance_actor(text: str) -> str:
    """Identify the primary compliance actor from rule text."""
    text_lower = text.lower()
    best_actor = "issuer"  # default
    best_score = 0
    for actor, keywords in _ACTOR_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_actor = actor
    return best_actor

def classify_condition_type(text: str) -> str:
    """Classify as positive_requirement, prohibition, or carve_out."""
    text_lower = text.lower()
    if "shall not" in text_lower or "prohibited" in text_lower or "debarred" in text_lower:
        return "prohibition"
    if "provided that" in text_lower or "nothing contained" in text_lower:
        return "carve_out"
    return "positive_requirement"

def detect_applicability_scope(chapter_number: str | None) -> list[str]:
    """Derive applicability scope from chapter number."""
    if chapter_number:
        return _SCOPE_FROM_CHAPTER.get(chapter_number, ["general"])
    return ["general"]


# --- Proviso Linking ---

def detect_proviso_parent(rule_id: str, is_proviso: bool, all_rule_ids: list[str]) -> str | None:
    """If this rule is a proviso, find its likely parent regulation."""
    if not is_proviso:
        return None
    # Proviso rule_ids typically end with _proviso or _prov or _explanation
    # The parent is the rule_id without the proviso suffix
    base = re.sub(r"_(?:proviso|prov|explanation|expl).*$", "", rule_id, flags=re.I)
    if base != rule_id and base in all_rule_ids:
        return base
    # Also try stripping the last segment
    parts = rule_id.rsplit("_", 1)
    if len(parts) == 2 and parts[0] in all_rule_ids:
        return parts[0]
    return None


# --- Main Enrichment Function ---

def enrich_rule(
    rule: dict,
    structure_lookup: ICDRStructureLookup,
    all_rule_ids: list[str] | None = None,
    regulation_framework: str = "SEBI_ICDR_2018",
    jurisdiction: str = "IN",
    regulator: str = "SEBI",
    gazette_notification: str = "SEBI/LAD-NRO/GN/2018/31",
    original_effective_date: str = "2018-11-10",
    pipeline_version: str = "0.3.0",
) -> dict:
    """
    Enrich a raw extracted rule with full regulatory metadata.
    
    This function is ADDITIVE — it adds new fields but never removes or modifies
    existing fields (rule_id, text, maps_to, source, etc. are preserved).
    
    Returns the enriched rule dict (mutates in place AND returns).
    """
    rule_id = rule.get("rule_id", "")
    text = rule.get("text", "")
    
    # --- Extract top-level regulation number ---
    reg_match = re.match(r"ICDR_(\d+[A-Z]?)", rule_id, re.I)
    top_reg = reg_match.group(1) if reg_match else None
    
    # --- Hierarchy from structure lookup ---
    location = structure_lookup.lookup(top_reg) if top_reg else None
    chapter_info = location["chapter"] if location else None
    part_info = location["part"] if location else None
    
    rule["regulation_framework"] = regulation_framework
    rule["jurisdiction"] = jurisdiction
    rule["regulator"] = regulator
    rule["country"] = "India"
    
    if chapter_info:
        rule["chapter"] = chapter_info
    if part_info:
        rule["part"] = part_info
    
    # --- Extract sub-clause path ---
    clause_match = re.match(r"ICDR_(.+)", rule_id)
    if clause_match:
        # "6_1_a" -> "6(1)(a)"
        tokens = clause_match.group(1).split("_")
        if len(tokens) >= 1:
            formatted = tokens[0]
            for t in tokens[1:]:
                if t.isdigit():
                    formatted += f"({t})"
                else:
                    formatted += f"({t})"
            rule["regulation_number"] = formatted
    
    # --- Classification ---
    rule["rule_type"] = classify_rule_type(text)
    rule["condition_type"] = classify_condition_type(text)
    rule["compliance_actor"] = classify_compliance_actor(text)
    rule["applicability_scope"] = detect_applicability_scope(
        chapter_info["number"] if chapter_info else None
    )
    
    # --- Amendment tracking ---
    rule["original_effective_date"] = original_effective_date
    rule["last_amended_date"] = None  # To be populated when amendment data is available
    rule["amendment_history"] = []
    rule["gazette_notification"] = gazette_notification
    rule["is_current"] = True
    
    # --- Cross-references ---
    refs = extract_cross_references(text)
    rule["references_regulations"] = refs["regulations"]
    rule["references_schedules"] = refs["schedules"]
    rule["references_external"] = refs["external_acts"]
    
    # --- Proviso structure ---
    is_proviso = rule.get("is_proviso", False)
    if not is_proviso:
        # Check if the text starts with "Provided that" or "Explanation"
        text_stripped = text.strip()
        if text_stripped.lower().startswith("provided that") or text_stripped.lower().startswith("explanation"):
            is_proviso = True
            rule["is_proviso"] = True
    
    if all_rule_ids:
        parent = detect_proviso_parent(rule_id, is_proviso, all_rule_ids)
        if parent:
            rule["exception_to"] = parent
    
    # --- Pipeline metadata ---
    rule["extraction_timestamp"] = None  # Set by caller
    rule["pipeline_version"] = pipeline_version
    
    return rule


def enrich_batch(
    rules: list[dict],
    structure_lookup: ICDRStructureLookup,
    **kwargs,
) -> list[dict]:
    """Enrich a batch of rules, passing all_rule_ids for proviso linking."""
    all_ids = [r.get("rule_id", "") for r in rules]
    for rule in rules:
        enrich_rule(rule, structure_lookup, all_rule_ids=all_ids, **kwargs)
    return rules
```

### 7.3 Important: Enrichment is a post-processing step

The enricher runs AFTER extraction and validation, BEFORE writing to the store. It should be called in the main orchestrator between the validation loop and the output write. It does NOT affect the extraction quality — it adds metadata to already-extracted rules.

---

## Phase 8: Create `rule_store.py` (NEW)

```python
# scripts/rule_extraction/rule_store.py
"""Persistence layer for enriched regulatory rules."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

class RuleStore:
    """
    Writes enriched rules to JSONL with versioning and deduplication.
    
    Future: graduate to SQLite or Postgres for query support.
    """
    
    def __init__(self, output_path: Path, mode: str = "w"):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self._existing_ids: set[str] = set()
        self._written_count = 0
        
        if mode == "a" and output_path.exists():
            self._load_existing_ids()
    
    def _load_existing_ids(self):
        for line in self.output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    self._existing_ids.add(json.loads(line)["rule_id"])
                except Exception:
                    pass
    
    def write_rule(self, rule: dict, dedupe: bool = True) -> bool:
        """Write a single rule. Returns True if written, False if skipped (dedup)."""
        rid = rule.get("rule_id", "")
        if dedupe and rid in self._existing_ids:
            return False
        
        # Strip internal keys before writing
        to_write = {k: v for k, v in rule.items() if not k.startswith("_")}
        
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(to_write, ensure_ascii=False) + "\n")
        
        self._existing_ids.add(rid)
        self._written_count += 1
        return True
    
    def write_batch(self, rules: list[dict], dedupe: bool = True) -> int:
        """Write a batch of rules. Returns count written."""
        if self.mode == "w" and self._written_count == 0:
            # First write in overwrite mode — clear the file
            self.output_path.write_text("", encoding="utf-8")
        
        count = 0
        for rule in rules:
            if self.write_rule(rule, dedupe=dedupe):
                count += 1
        return count
    
    @property
    def written_count(self) -> int:
        return self._written_count
```

---

## Phase 9: Refactor `llm_extract_rules.py` as Slim Orchestrator

After phases 2-8, the main script should shrink from ~1874 lines to ~200-300 lines. It becomes a thin orchestrator:

```python
#!/usr/bin/env python3
# scripts/llm_extract_rules.py
"""
LLM-driven rule extractor for SEBI ICDR regulations.

Usage:
  python scripts/llm_extract_rules.py \
      --pdf data/input/SEBI_ICDR_2018.pdf \
      --out data/processed/rules_enriched.jsonl \
      --model qwen2.5:14b-instruct \
      --window 2 --overlap 1 \
      --judge --judge-model deepseek-r1:14b \
      --timeout 600 --debug
"""

import argparse, json, sys, time
from pathlib import Path
from datetime import datetime

from rule_extraction.pdf_loader import read_pdf_pages, windowed, strip_page_numbers
from rule_extraction.ollama_client import OllamaClient
from rule_extraction.regulation_identifier import (
    pre_identify_regulations, detect_allowed_regs, normalize_rule_identifier,
    identify_regulations, build_targeted_extraction_prompt,
)
from rule_extraction.rule_extractor import (
    SYSTEM_PROMPT, load_fewshot_examples, flatten_subrules,
    extract_rules_two_pass, extract_rules_single_pass,
    normalize_clause_text, item_score, choose_best_item,
    MIN_TEXT_CHARS, TEXT_SIGNATURE_SLICE,
)
from rule_extraction.rule_validator import (
    sanitize_for_schema, clamp_span_hint, validate_rule,
    validate_required_fields, validate_rule_id_format,
    validate_maps_to, validate_source, validate_reg_anchoring,
)
from rule_extraction.metadata_enricher import (
    ICDRStructureLookup, enrich_batch,
)
from rule_extraction.rule_store import RuleStore

# Keep rule_refiner import as-is
try:
    from scripts.rule_refiner import RuleRefiner, OllamaClient as RefinerOllamaClient
except Exception:
    from rule_refiner import RuleRefiner, OllamaClient as RefinerOllamaClient


def main():
    ap = argparse.ArgumentParser(description="Extract regulatory rules from SEBI ICDR PDF")
    # ... (keep all existing argparse arguments)
    # ADD these new arguments:
    ap.add_argument("--regulation-framework", default="SEBI_ICDR_2018",
                    help="Regulation framework identifier (default: SEBI_ICDR_2018)")
    ap.add_argument("--jurisdiction", default="IN",
                    help="ISO country code (default: IN for India)")
    ap.add_argument("--structure-json", default="data/schema/icdr_structure.json",
                    help="Path to ICDR structure lookup JSON")
    ap.add_argument("--no-enrich", action="store_true",
                    help="Skip metadata enrichment (output raw rules only)")
    args = ap.parse_args()
    
    # Setup
    client = OllamaClient(timeout=args.timeout)
    pdf = Path(args.pdf)
    pages = read_pdf_pages(pdf)
    if args.max_pages and args.max_pages > 0:
        pages = pages[:args.max_pages]
    
    # Structure lookup for metadata enrichment
    structure_lookup = None
    if not args.no_enrich:
        structure_path = Path(args.structure_json)
        if structure_path.exists():
            structure_lookup = ICDRStructureLookup(structure_path)
        else:
            print(f"[WARN] Structure file not found: {structure_path}; skipping enrichment", file=sys.stderr)
    
    store = RuleStore(Path(args.out), mode="a" if args.append else "w")
    
    # Main window loop — same structure as before, but using module functions
    all_rules = []  # Collect all rules for batch enrichment at the end
    
    for start_idx, chunk in windowed(pages, args.window, args.overlap):
        chunk_cleaned = [strip_page_numbers(p) for p in chunk]
        visible = "\n\n--- PAGE BREAK ---\n\n".join(chunk_cleaned)
        page_nums = list(range(start_idx + 1, start_idx + 1 + len(chunk)))
        
        # Regulation identification
        visible_regs = set()
        for page_text in chunk_cleaned:
            visible_regs.update(pre_identify_regulations(page_text))
        allowed_regs = detect_allowed_regs(visible)
        
        # Two-pass or single-pass extraction
        if not args.no_two_pass:
            items = extract_rules_two_pass(
                client, args.model, visible, page_nums,
                visible_regs=visible_regs,
                pdf_name=pdf.name,
                timeout=args.timeout, debug=args.debug,
            )
            if not items:
                items = extract_rules_single_pass(
                    client, args.model, SYSTEM_PROMPT,
                    visible, page_nums, pdf_name=pdf.name,
                    fewshots=load_fewshot_examples(args.fewshot),
                    timeout=args.timeout, debug=args.debug,
                )
        else:
            items = extract_rules_single_pass(...)
        
        if not items:
            continue
        
        # Flatten, validate, judge, normalize — same logic as before
        # ... (keep the existing judge loop and validation logic)
        
        # Collect for batch enrichment
        all_rules.extend(validated_items)
    
    # --- Metadata enrichment (NEW) ---
    if structure_lookup and all_rules:
        enrich_batch(
            all_rules,
            structure_lookup,
            regulation_framework=args.regulation_framework,
            jurisdiction=args.jurisdiction,
        )
        # Set extraction timestamp
        ts = datetime.utcnow().isoformat() + "Z"
        for r in all_rules:
            r["extraction_timestamp"] = ts
            r["extraction_model"] = args.model
    
    # --- Write to store ---
    written = store.write_batch(all_rules, dedupe=args.dedupe)
    print(f"[DONE] Wrote {written} enriched rules -> {args.out}")


if __name__ == "__main__":
    main()
```

### Important: What to preserve exactly

The main loop logic (lines 1469-1848 in the current file) is complex and battle-tested. Do NOT rewrite it from scratch. Instead:

1. Replace direct function calls with module imports (e.g., `pre_identify_regulations(page_text)` stays the same, just imported from `regulation_identifier`)
2. Replace `ollama_chat_json(args.model, ...)` calls with `client.chat_json(args.model, ...)` 
3. Add the enrichment step between the collection loop and the write step
4. Keep all argparse arguments — add the new ones, don't remove any

### Fix the double anchoring bug while refactoring

In the current code, `validate_reg_anchoring` runs at line 1624 (inside the judge block) AND at line 1749 (in the general validation loop). Both lower confidence by 0.2, so a mismatched rule gets penalized by 0.4. During the refactor, ensure it only runs ONCE. The general validation loop (line 1749) is the right place — remove it from the judge block.

---

## Phase 10: Update `data/schema/rules_schema.json`

The current schema only validates the POC fields. Add the new metadata fields as optional properties so existing pipeline stages that consume the JSONL don't break:

```json
{
  "type": "object",
  "required": ["rule_id", "domain", "title", "text", "lean_id", "source"],
  "properties": {
    ... existing properties ...
    
    "regulation_framework": {"type": "string"},
    "regulation_number": {"type": "string"},
    "jurisdiction": {"type": "string"},
    "regulator": {"type": "string"},
    "country": {"type": "string"},
    "chapter": {
      "type": "object",
      "properties": {
        "number": {"type": "string"},
        "title": {"type": "string"}
      }
    },
    "part": {
      "type": ["object", "null"],
      "properties": {
        "number": {"type": "string"},
        "title": {"type": "string"}
      }
    },
    "rule_type": {"type": "string"},
    "condition_type": {"type": "string"},
    "compliance_actor": {"type": "string"},
    "applicability_scope": {"type": "array", "items": {"type": "string"}},
    "original_effective_date": {"type": ["string", "null"]},
    "last_amended_date": {"type": ["string", "null"]},
    "amendment_history": {"type": "array"},
    "gazette_notification": {"type": ["string", "null"]},
    "is_current": {"type": "boolean"},
    "references_regulations": {"type": "array", "items": {"type": "string"}},
    "references_schedules": {"type": "array", "items": {"type": "string"}},
    "references_external": {"type": "array"},
    "is_proviso": {"type": "boolean"},
    "exception_to": {"type": ["string", "null"]},
    "extraction_timestamp": {"type": ["string", "null"]},
    "extraction_model": {"type": ["string", "null"]},
    "pipeline_version": {"type": ["string", "null"]}
  },
  "additionalProperties": false
}
```

**Critical:** All new fields must be added to the `properties` object AND to `ALLOWED_TOP_KEYS` — because `sanitize_for_schema()` drops anything not in `ALLOWED_TOP_KEYS`. The enricher must run AFTER `sanitize_for_schema()`, or the new fields must be added to the allowed set in `rule_validator.py`.

The cleaner approach: run `sanitize_for_schema()` for validation purposes only, but write the full enriched dict to the store (skipping internal `_` prefixed keys). The `rule_store.py` already does this.

---

## Testing Checklist

After completing all phases, verify:

1. **Import chain works:**
   ```bash
   python -c "from scripts.rule_extraction.ollama_client import OllamaClient; print('OK')"
   python -c "from scripts.rule_extraction.pdf_loader import read_pdf_pages; print('OK')"
   python -c "from scripts.rule_extraction.regulation_identifier import pre_identify_regulations; print('OK')"
   python -c "from scripts.rule_extraction.rule_validator import validate_rule; print('OK')"
   python -c "from scripts.rule_extraction.metadata_enricher import ICDRStructureLookup, enrich_rule; print('OK')"
   python -c "from scripts.rule_extraction.rule_store import RuleStore; print('OK')"
   ```

2. **Enricher works standalone:**
   ```python
   from scripts.rule_extraction.metadata_enricher import ICDRStructureLookup, enrich_rule
   lookup = ICDRStructureLookup(Path("data/schema/icdr_structure.json"))
   
   test_rule = {
       "rule_id": "ICDR_6_1_b",
       "text": "The issuer shall have an average operating profit of at least fifteen crore rupees...",
       "maps_to": [{"field": "operating_profits", "type_hint": "List Nat"}],
   }
   enriched = enrich_rule(test_rule, lookup)
   assert enriched["chapter"]["number"] == "II"
   assert enriched["part"]["title"] == "ELIGIBILITY REQUIREMENTS"
   assert enriched["rule_type"] == "eligibility"
   assert enriched["jurisdiction"] == "IN"
   assert "6(1)(b)" in enriched.get("regulation_number", "")
   print("Enricher test passed!")
   ```

3. **Full pipeline still runs:**
   ```bash
   python scripts/llm_extract_rules.py \
       --pdf data/input/ICDR_rules_4_22.pdf \
       --out data/processed/rules_enriched_test.jsonl \
       --model qwen2.5:14b-instruct \
       --window 2 --overlap 1 \
       --reg-filter 4 22 \
       --timeout 600 --debug
   ```
   Verify the output JSONL has the new metadata fields.

4. **Backward compatibility:** Downstream scripts (`schema_reconcile.py`, `rule_anchored_extract.py`, `llm_generate_lean.py`) should still work because all original fields are preserved and new fields are additive.

---

## Summary of Deliverables

| Phase | Module | Lines (approx) | Status |
|-------|--------|-----------------|--------|
| 2 | `ollama_client.py` | ~250 | Extract from existing |
| 3 | `pdf_loader.py` | ~60 | Extract from existing |
| 4 | `regulation_identifier.py` | ~350 | Extract from existing |
| 5 | `rule_validator.py` | ~300 | Extract from existing |
| 6 | `rule_extractor.py` | ~400 | Extract from existing |
| 7 | `metadata_enricher.py` | ~300 | **NEW** |
| 8 | `rule_store.py` | ~80 | **NEW** |
| 9 | `llm_extract_rules.py` | ~250 | Refactored orchestrator |
| 10 | `rules_schema.json` | ~update | Add new fields |
| — | `icdr_structure.json` | ~1740 | **NEW** data file |

**Recommended execution order:** 2 → 3 → 4 → 5 → 6 → 7 → 8 → 10 → 9. Do phases 2-6 first (pure extraction, no new logic). Then add the new modules (7-8). Update the schema (10). Finally, refactor the orchestrator (9) to wire everything together.

---

## Appendix: Enriched Rule Record Example

After enrichment, a rule record for ICDR Regulation 6(1)(b) should look like:

```json
{
  "rule_id": "ICDR_6_1_b",
  "domain": "SEBI_ICDR",
  "title": "Operating profit ≥ ₹15 cr in each of last 3 years",
  "text": "The issuer shall have an average operating profit...",
  "lean_id": "rule_6_1_b",
  "maps_to": [
    {
      "field": "operating_profits",
      "type_hint": "List Nat",
      "constraints_text": "length=3; each ≥ ₹15 crore; basis=restated, consolidated"
    }
  ],
  "notes": "Three-year operating profit requirement...",
  "source": {
    "pdf": "SEBI_ICDR_2018.pdf",
    "pages": [12, 13],
    "reg": "Regulation 6(1)(b)",
    "span_hint": "average operating profit of at least"
  },
  "confidence": 0.95,
  "status": "accepted",
  
  "regulation_framework": "SEBI_ICDR_2018",
  "regulation_number": "6(1)(b)",
  "jurisdiction": "IN",
  "regulator": "SEBI",
  "country": "India",
  "chapter": {"number": "II", "title": "INITIAL PUBLIC OFFER ON MAIN BOARD"},
  "part": {"number": "I", "title": "ELIGIBILITY REQUIREMENTS"},
  
  "rule_type": "eligibility",
  "condition_type": "positive_requirement",
  "compliance_actor": "issuer",
  "applicability_scope": ["IPO"],
  
  "original_effective_date": "2018-11-10",
  "last_amended_date": null,
  "amendment_history": [],
  "gazette_notification": "SEBI/LAD-NRO/GN/2018/31",
  "is_current": true,
  
  "references_regulations": [],
  "references_schedules": [],
  "references_external": [],
  "is_proviso": false,
  "exception_to": null,
  
  "extraction_timestamp": "2026-04-04T23:15:00Z",
  "extraction_model": "qwen2.5:14b-instruct",
  "pipeline_version": "0.3.0"
}
```

---

## Phase 11: Debug Intermediate Outputs

### Problem

The current code runs the judge loop **per-window** (inside the `for start_idx, chunk in windowed(...)` loop, line 1591). This means there is no way to inspect the full set of extracted rules before the judge modifies them. Debugging requires visibility into three stages:

1. **Post-Pass-1**: What clause identifiers did `identify_regulations()` find on each window?
2. **Post-Pass-2 / Pre-Judge**: What structured rules did the LLM extract before the judge scores, quarantines, or regenerates them?
3. **Post-Judge**: The current judge report output (already exists via `--judge-report-out`).

### 11.1 Add `--debug-dir` argument

Add a new CLI argument to `llm_extract_rules.py` (and wire it through the orchestrator in Phase 9):

```python
ap.add_argument(
    "--debug-dir", type=str, default="",
    help="Directory to write intermediate debug artifacts. "
         "Creates pass1_inventory.jsonl, pass2_pre_judge.jsonl, and "
         "per-window debug files. Empty string (default) disables."
)
```

### 11.2 Write Pass 1 inventory after each window

Immediately after the `identify_regulations()` call (currently around line 1542), write the raw inventory:

```python
# Inside the window loop, right after identify_regulations() returns:
if args.debug_dir and reg_inventory:
    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    with open(debug_dir / "pass1_inventory.jsonl", "a", encoding="utf-8") as f:
        record = {
            "window_start": start_idx,
            "pages": page_nums,
            "visible_regs_regex": sorted(visible_regs),
            "pass1_clauses": [
                {
                    "reg_number": c.get("reg_number"),
                    "clause_text": (c.get("clause_text") or "")[:200],
                    "span_hint": c.get("span_hint"),
                    "is_proviso": c.get("is_proviso"),
                }
                for c in reg_inventory
            ],
        }
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

**Output format** (`pass1_inventory.jsonl` — one line per window):
```json
{
  "window_start": 0,
  "pages": [1, 2],
  "visible_regs_regex": ["4", "5", "6"],
  "pass1_clauses": [
    {"reg_number": "4", "clause_text": "Unless otherwise provided...", "span_hint": "Unless otherwise", "is_proviso": false},
    {"reg_number": "5(1)(a)", "clause_text": "if the issuer, any of its...", "span_hint": "if the issuer", "is_proviso": false}
  ]
}
```

This lets you immediately see:
- Did Pass 1 find all the clauses on each page?
- Are regex-detected `visible_regs` correct?
- Is the LLM returning garbage `reg_number` values (like `"Provided further"` as a standalone reg)?

### 11.3 Write Pass 2 pre-judge output after each window

After the two-pass extraction produces `items` but BEFORE the judge block (currently line 1591), write the raw extracted rules:

```python
# After flat_items is assembled (around line 1588), before "if args.judge and flat_items:"
if args.debug_dir and flat_items:
    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    with open(debug_dir / "pass2_pre_judge.jsonl", "a", encoding="utf-8") as f:
        for it in flat_items:
            record = {
                "window_start": start_idx,
                "pages": page_nums,
                "rule_id": it.get("rule_id"),
                "title": it.get("title"),
                "text": (it.get("text") or "")[:300],
                "maps_to": it.get("maps_to", []),
                "confidence": it.get("confidence"),
                "source": it.get("source", {}),
                "repair_notes": it.get("repair_notes", []),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

### 11.4 Write a coverage summary at the end

After the main loop completes, before writing the final output, write a coverage report:

```python
# After the window loop, before enrichment/store write
if args.debug_dir:
    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # Coverage: which regulations were extracted vs which were expected
    extracted_regs = set()
    extracted_ids = set()
    for key in item_order:
        item = selected_items[key]
        extracted_ids.add(item.get("rule_id", ""))
        m = re.match(r"ICDR_(\d+)", item.get("rule_id", ""))
        if m:
            extracted_regs.add(int(m.group(1)))
    
    coverage = {
        "total_rules_extracted": len(selected_items),
        "regulations_covered": sorted(extracted_regs),
        "all_rule_ids": sorted(extracted_ids),
        "reg_filter": args.reg_filter,
    }
    
    # If reg_filter is set, check for gaps
    if args.reg_filter:
        lo, hi = args.reg_filter
        expected = set(range(lo, hi + 1))
        coverage["regulations_missing"] = sorted(expected - extracted_regs)
    
    (debug_dir / "coverage_summary.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

### 11.5 Clear debug files at start of run

Since these files are opened in append mode per-window, they must be cleared at the start of each run:

```python
# Right after argparse, before the window loop:
if args.debug_dir:
    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    for fname in ["pass1_inventory.jsonl", "pass2_pre_judge.jsonl"]:
        fpath = debug_dir / fname
        if fpath.exists():
            fpath.write_text("", encoding="utf-8")
```

### 11.6 Example usage

```bash
python scripts/llm_extract_rules.py \
    --pdf data/input/ICDR_rules_4_22.pdf \
    --out data/processed/rules_judged_v5.jsonl \
    --model qwen2.5:14b-instruct \
    --window 2 --overlap 1 \
    --reg-filter 4 22 \
    --judge --judge-model deepseek-r1:14b \
    --timeout 600 \
    --debug \
    --debug-dir data/processed/debug_run_v5
```

After the run, inspect:
```bash
# What did Pass 1 find?
cat data/processed/debug_run_v5/pass1_inventory.jsonl | python3 -m json.tool

# What did Pass 2 extract before the judge?
cat data/processed/debug_run_v5/pass2_pre_judge.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    print(f'{r[\"rule_id\"]:<40} maps_to={[m[\"field\"] for m in r.get(\"maps_to\",[])]}')
"

# What regulations are missing?
cat data/processed/debug_run_v5/coverage_summary.json | python3 -m json.tool
```

---

## Phase 12: Bug Fixes from Output Validation

These bugs were identified by analyzing the output of `rules_judged_v4.jsonl` (92 rules extracted from ICDR regulations 4-22). They should be fixed during the modularization, primarily in `regulation_identifier.py` (Phase 4) and `rule_validator.py` (Phase 5).

### 12.1 BUG (CRITICAL): First letter stripped from "Provided" / "Explanation" / "Category"

**Symptom:** 31 out of 92 rule_ids contain `rovided`, `xplanation`, or `ategory` instead of `provided`, `explanation`, `category`.

**Root cause:** The tokenizer regex `_REG_NUM_TOKEN_RE = re.compile(r"(\d+[A-Z]?|[a-z]+)")` matches either digits+optional-uppercase OR lowercase-only. An uppercase letter like `P` in `Provided` matches neither branch — the digits branch needs a leading digit, and the lowercase branch rejects uppercase. So `"Provided"` tokenizes as `["rovided"]`, losing the `P`.

**Affected functions:** `build_targeted_extraction_prompt()` (line 1363) and `normalize_rule_identifier()` (lines 1205-1212), both in `regulation_identifier.py` after Phase 4.

**Fix — two parts:**

**Part A:** Canonicalize proviso/explanation markers BEFORE tokenization. Add this function to `regulation_identifier.py`:

```python
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
    s = re.sub(r"Provided\s+further", "proviso2", s, flags=re.I)
    s = re.sub(r"Provided\s+that", "proviso", s, flags=re.I)
    s = re.sub(r"Provided", "proviso", s, flags=re.I)
    s = re.sub(r"Explanation", "explanation", s, flags=re.I)
    s = re.sub(r"Category", "category", s, flags=re.I)
    return s
```

**Part B:** Call `canonicalize_proviso_markers()` in both affected functions:

In `build_targeted_extraction_prompt()`:
```python
def build_targeted_extraction_prompt(reg_number, clause_text, page_nums, pdf_name="<PDF>"):
    reg_number_clean = canonicalize_proviso_markers(reg_number)  # ADD THIS
    tokens = _REG_NUM_TOKEN_RE.findall(reg_number_clean)         # was: reg_number
    # ... rest unchanged
```

In `normalize_rule_identifier()`, apply it to the body after ICDR prefix extraction:
```python
body = body_match.group(1)
body = canonicalize_proviso_markers(body)  # ADD THIS LINE
body = (
    body.replace("(", "_")
    .replace(")", "_")
    # ... rest unchanged
```

**Expected result:** `ICDR_6_1_rovided` → `ICDR_6_1_proviso`, `ICDR_8_rovided_further` → `ICDR_8_proviso2`, `ICDR_6_3_xplanation` → `ICDR_6_3_explanation`.

### 12.2 BUG (MEDIUM): Full proviso text dumped into rule_id (237+ chars)

**Symptom:** `ICDR_17_rovided_that_such_equity_shares_shall_be_locked_in_for_a_period_of_at_least_six_months...` (237 characters). The entire proviso text becomes the rule_id.

**Root cause:** Pass 1 returns `reg_number` as the full text of the proviso rather than a structured identifier. The tokenizer then converts every word into an underscore-separated suffix.

**Fix:** Add a length guard in `normalize_rule_identifier()` in `regulation_identifier.py`. After assembling the normalized rule_id, truncate:

```python
# At the end of normalize_rule_identifier(), before the return:
# Guard against absurdly long rule_ids from full-text reg_numbers
if len(normalized_rule_id) > 50:
    # Keep only the first 3 meaningful suffix tokens after the regulation number
    parts = normalized_rule_id.split("_")
    # parts[0] = "ICDR", parts[1] = reg_number, rest = suffix tokens
    if len(parts) > 5:
        normalized_rule_id = "_".join(parts[:5])
        item.setdefault("repair_notes", []).append(
            f"rule_id_truncated_from_{len(parts)}_tokens"
        )
```

Also add a guard in `build_targeted_extraction_prompt()`:

```python
# If reg_number is unreasonably long, it's proviso text, not a clause ID.
# Extract just the numeric prefix.
if len(reg_number) > 40:
    prefix_match = re.match(r"(\d+[A-Z]?(?:\(\d+\))*)", reg_number)
    if prefix_match:
        reg_number = prefix_match.group(1) + "_proviso"
```

### 12.3 BUG (MEDIUM): Regulation 8A encoded as ICDR_8_8a (doubled prefix)

**Symptom:** `ICDR_8_8a`, `ICDR_8_8a_a`, `ICDR_8_8a_b`, `ICDR_8_8a_c` — Regulation 8A is a standalone regulation but appears as a sub-clause of Regulation 8.

**Root cause:** The LLM returns `source.reg: "Regulation 8A"` and `reg_number: "8A"`. The tokenizer `_REG_NUM_TOKEN_RE.findall("8A")` correctly produces `["8A"]`. But `normalize_rule_identifier()` processes the rule_id that the LLM emitted (not the reg_number). If the LLM emitted `rule_id: "ICDR_8A"`, normalize parses it as body=`"8A"`, then `tokens = CLAUSE_TOKEN_SPLIT_RE.split("8A")` → `["8A"]`, and `reg_token = "8"` (because `"8A".isdigit()` is False, it enters the else branch... actually `"8A".isdigit()` is False). Let me trace more carefully:

The token loop at line 1216:
```python
for tok in tokens:
    if reg_token is None and tok.isdigit():  # "8A".isdigit() = False
        reg_token = tok
    else:
        rest_tokens.append(tok.lower())  # appends "8a"
```

So `reg_token` stays None, `rest_tokens = ["8a"]`. Then `reg_from_source` picks up `8` from `source.reg`. Result: `ICDR_8_8a`.

**Fix:** Change the token detection to handle alphanumeric regulation numbers:

```python
for tok in tokens:
    if reg_token is None and re.match(r"^\d+[A-Za-z]?$", tok):
        reg_token = tok
    else:
        rest_tokens.append(tok.lower())
```

This makes `"8A"` match as the regulation token. The resulting rule_id becomes `ICDR_8A` (with `reg_no = 8` for the integer comparison, extracted via `int(re.match(r"\d+", reg_token).group())`).

### 12.4 BUG (CRITICAL): Missing 7 key sub-clauses

**Symptom:** `ICDR_6_1_b` (operating profit), `ICDR_6_1_e`, `ICDR_5_1_d`, `ICDR_14_4`, `ICDR_10_1_a`, `ICDR_13_b`, `ICDR_15_1_c` are not in the output.

**Root cause:** Most likely Pass 1 identification failure — the LLM doesn't list all clauses on dense pages. `ICDR_6_1_b` is especially telling because it's the few-shot example, meaning the clause exists in the text but Pass 1 skipped it.

**Fix (multi-part):**

**Part A — Coverage check (Phase 9 orchestrator):** After the window loop, compare extracted rule_ids against a "ground truth" list derived from `pre_identify_regulations()`. Log any regulation numbers that had structural matches but no corresponding extracted rules.

**Part B — Model quality:** Ensure the recommended model is at least `qwen2.5:14b-instruct`. The `--model` default should be updated from `llama3:8b`.

**Part C — Pass 1 retry on sparse results:** If Pass 1 returns fewer clauses than `pre_identify_regulations()` detected regulation numbers, retry Pass 1 once with a more explicit prompt. Add this to `regulation_identifier.py`:

```python
def identify_regulations(client, model, page_text, page_nums, visible_regs=None, ...):
    # ... existing code ...
    items = [r for r in items if isinstance(r, dict) and r.get("reg_number")]
    
    # If regex found more regulations than the LLM, the LLM likely missed some.
    # Retry once with explicit enumeration.
    if visible_regs and len(items) < len(visible_regs):
        if debug:
            print(f"[Pass1] LLM found {len(items)} clauses but regex found "
                  f"{len(visible_regs)} regs; retrying with explicit enumeration",
                  file=sys.stderr)
        # Build a more explicit prompt listing the expected regulations
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
```

### 12.5 BUG (MEDIUM): Duplicate field names across regulations

**Symptom:** `ofs_holding_period_years` appears in 5 rules (Reg 8, 16, 17, 19). `has_depository_agreement` in 2 (Reg 7, 20).

**Root cause:** Pass 2 extracts one clause at a time with no memory of previously assigned field names. The SYSTEM_PROMPT instructs unique names but the LLM cannot enforce this across windows.

**Fix:** Add a post-extraction deduplication pass in `rule_extractor.py` or in the orchestrator. Run this after all windows are processed but before enrichment:

```python
def deduplicate_field_names(rules: list[dict]) -> list[dict]:
    """
    When multiple rules map to the same field name, disambiguate by
    appending the regulation number.
    """
    from collections import Counter
    
    # Count field usage across all rules
    field_to_rules: dict[str, list[str]] = {}
    for r in rules:
        rid = r.get("rule_id", "")
        for m in r.get("maps_to", []):
            field = m.get("field", "")
            if field:
                field_to_rules.setdefault(field, []).append(rid)
    
    # Find collisions
    collisions = {f: rids for f, rids in field_to_rules.items() if len(rids) > 1}
    
    if not collisions:
        return rules
    
    # Disambiguate: append regulation number to field name
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
```

### 12.6 BUG (LOW-MEDIUM): List Nat underrepresentation

**Symptom:** Only 2 out of 73 typed fields use `List Nat`. Rules with "preceding three years" / "each of the preceding N years" are typed as `Nat` or `Bool`.

**Fix:** Add a deterministic type override in `rule_validator.py` or as a post-processing step:

```python
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
            # Preserve the count in constraints_text
            existing = mt.get("constraints_text", "")
            if f"length={n}" not in existing:
                mt["constraints_text"] = f"length={n}; " + existing if existing else f"length={n}"
            rule.setdefault("repair_notes", []).append(
                f"type_override:Nat->ListNat(n={n})_for_{mt.get('field','')}"
            )
```

Call this function in the orchestrator after extraction, before enrichment, for every rule.

### 12.7 Summary of Bug Fix Locations in Modularized Code

| Bug | Fix Function | Module | Phase |
|-----|-------------|--------|-------|
| 12.1 First-letter stripping | `canonicalize_proviso_markers()` | `regulation_identifier.py` | 4 |
| 12.2 Text-dump rule_ids | Length guard in `normalize_rule_identifier()` + `build_targeted_extraction_prompt()` | `regulation_identifier.py` | 4 |
| 12.3 Reg 8A doubled | Token detection fix in `normalize_rule_identifier()` | `regulation_identifier.py` | 4 |
| 12.4 Missing sub-clauses | Pass 1 retry + coverage check + model default update | `regulation_identifier.py` + orchestrator | 4, 9 |
| 12.5 Duplicate fields | `deduplicate_field_names()` | `rule_extractor.py` or orchestrator | 6 or 9 |
| 12.6 List Nat undercount | `override_list_nat_from_text()` | `rule_validator.py` | 5 |

**Recommended execution order for bug fixes:** 12.1 → 12.2 → 12.3 (all in the same file, do them together during Phase 4) → 12.4 (during Phase 4 + Phase 9) → 12.6 (during Phase 5) → 12.5 (during Phase 9).

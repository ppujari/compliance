"""Enrich extracted rules with regulatory metadata: hierarchy, jurisdiction, cross-references."""

from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any, Optional
from datetime import date

# --- ICDR Document Structure Lookup ---

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent  # scripts/rule_extraction/ -> scripts/ -> repo root
_STRUCTURE_PATH = _REPO_ROOT / "data" / "schema" / "icdr_structure.json"


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
        m = re.match(r"(\d+[A-Z]?)", str(reg_number))
        if not m:
            return None
        return self._reg_to_location.get(m.group(1))

    def get_schedules(self) -> list[dict]:
        return self._data.get("schedules", [])


# --- Cross-Reference Detection ---

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
    base = re.sub(r"_(?:proviso|prov|explanation|expl).*$", "", rule_id, flags=re.I)
    if base != rule_id and base in all_rule_ids:
        return base
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

    This function is ADDITIVE -- it adds new fields but never removes or modifies
    existing fields (rule_id, text, maps_to, source, etc. are preserved).

    Returns the enriched rule dict (mutates in place AND returns).
    """
    rule_id = rule.get("rule_id", "")
    text = rule.get("text", "")

    # Extract top-level regulation number
    reg_match = re.match(r"ICDR_(\d+[A-Z]?)", rule_id, re.I)
    top_reg = reg_match.group(1) if reg_match else None

    # Hierarchy from structure lookup
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

    # Extract sub-clause path
    clause_match = re.match(r"ICDR_(.+)", rule_id)
    if clause_match:
        tokens = clause_match.group(1).split("_")
        if len(tokens) >= 1:
            formatted = tokens[0]
            for t in tokens[1:]:
                formatted += f"({t})"
            rule["regulation_number"] = formatted

    # Classification
    rule["rule_type"] = classify_rule_type(text)
    rule["condition_type"] = classify_condition_type(text)
    rule["compliance_actor"] = classify_compliance_actor(text)
    rule["applicability_scope"] = detect_applicability_scope(
        chapter_info["number"] if chapter_info else None
    )

    # Amendment tracking
    rule["original_effective_date"] = original_effective_date
    rule["last_amended_date"] = None
    rule["amendment_history"] = []
    rule["gazette_notification"] = gazette_notification
    rule["is_current"] = True

    # Cross-references
    refs = extract_cross_references(text)
    rule["references_regulations"] = refs["regulations"]
    rule["references_schedules"] = refs["schedules"]
    rule["references_external"] = refs["external_acts"]

    # Proviso structure
    is_proviso = rule.get("is_proviso", False)
    if not is_proviso:
        text_stripped = text.strip()
        if text_stripped.lower().startswith("provided that") or text_stripped.lower().startswith("explanation"):
            is_proviso = True
            rule["is_proviso"] = True

    if all_rule_ids:
        parent = detect_proviso_parent(rule_id, is_proviso, all_rule_ids)
        if parent:
            rule["exception_to"] = parent

    # Pipeline metadata
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

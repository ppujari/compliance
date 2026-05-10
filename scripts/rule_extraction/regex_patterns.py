"""Compiled regex constants shared across rule extraction."""

from __future__ import annotations

import re

# Pattern A: inline footnote citation — number glued to "[" bracket
# Matches: "25[filing]", "27[(b) outstanding...]", "29[(3) If an issuer...]"
# The lookbehind ensures the number is preceded by a word/punct char (mid-sentence)
INLINE_FOOTNOTE_RE = re.compile(
    r"(?<=[a-zA-Z0-9.,;:)\]\"\'\s])"  # preceded by word char, punctuation, or whitespace
    r"(\d{1,3})"  # footnote number (1-3 digits)
    r"(?=\[)",  # immediately followed by "[" (no space)
)

# Pattern B: footnote definition line at page bottom (entire line removed in strip_footnotes)
FOOTNOTE_DEF_RE = re.compile(
    r"^[ \t]*"  # optional leading whitespace
    r"\d{1,3}"  # footnote number
    r"[ \t]+"  # one or more spaces
    r"(?:Substituted|Inserted|Renumbered|Omitted|Added|Amended)"  # action verb
    r"\s+by\b"  # followed by "by"
    r"[^\n]*(?:\n|\Z)",  # rest of line and newline (or end of string)
    re.MULTILINE | re.IGNORECASE,
)

# Matches amendment-inserted sub-regulations like: "[(3) The amount for:"
INSERTED_SUBREG_RE = re.compile(
    r"^\[(\d+)\s*\(",
    re.MULTILINE,
)

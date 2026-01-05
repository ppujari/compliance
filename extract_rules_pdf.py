#!/usr/bin/env python3
"""
Extract atomic SEBI ICDR rules from a PDF into JSONL.

- Reads PDF with PyMuPDF (fitz)
- Finds "Regulation <N>" (or fallback to "<N>. " heading) sections
- Splits each section into subclauses: (1), (2), ... then (a), (b), ...
- Writes JSONL: {"rule_id","domain","title","text","lean_id","notes"}

Usage:
  python3 scripts/extract_rules_pdf.py \
    --pdf "data/raw/ICDR_excerpt.pdf" \
    --out "data/processed/rules.jsonl" \
    --domain "SEBI_ICDR" \
    --prefix "ICDR" \
    --reg-start 14 --reg-end 22 \
    --dedupe

Notes:
- If your PDF headings differ, adjust REG_HEADER_PAT/FALLBACK_HEADER_PAT.
- Titles are taken from header line; if missing, we use the first sentence of the clause.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

# --------------------------
# Configurable patterns
# --------------------------
# e.g., "Regulation 14: Minimum promoter contribution"
REG_HEADER_PAT = re.compile(r"(?mi)^\s*Regulation\s+(\d+)\s*[:.\-]?\s*(.*)$")
# fallback if the PDF uses "14. Title" instead of the word Regulation
FALLBACK_HEADER_PAT = re.compile(r"(?mi)^\s*(\d{1,3})\.\s+([A-Z].*)$")

# subclause (1) (2) ... then (a) (b) ...
PAREN_NUM_PAT = re.compile(r"(?m)^\s*\((\d+)\)\s*")
PAREN_LET_PAT = re.compile(r"(?m)^\s*\(([a-z])\)\s*")

# --------------------------
# Utilities
# --------------------------
def read_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF (fitz) not installed. Install with: pip install pymupdf", file=sys.stderr)
        sys.exit(1)
    doc = fitz.open(pdf_path.as_posix())
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    return "\n".join(parts)

def normalize_text(s: str) -> str:
    # Basic cleanup: normalize spaces, strip trailing spaces, collapse runs of blank lines
    s = s.replace("\r", "")
    lines = [re.sub(r"[ \t]+$", "", L) for L in s.split("\n")]
    # collapse multiple blank lines
    out = []
    blanks = 0
    for L in lines:
        if L.strip() == "":
            blanks += 1
            if blanks <= 1:
                out.append("")
        else:
            blanks = 0
            out.append(L)
    return "\n".join(out).strip()

def slugify_title(t: str, max_len: int = 60) -> str:
    t = t.strip()
    t = re.sub(r"[^A-Za-z0-9]+", "_", t)
    return t.strip("_")[:max_len].lower()

def first_sentence(s: str) -> str:
    s = s.strip()
    m = re.search(r"([^.?!]+[.?!])", s)
    return (m.group(1).strip() if m else s[:120])

def sectionize(text: str):
    """
    Yield tuples (reg_no:int, header_title:str, body:str) by locating headers.
    Tries 'Regulation N' first, falls back to 'N. Title' headings.
    """
    m_all = list(REG_HEADER_PAT.finditer(text))
    if not m_all:
        m_all = list(FALLBACK_HEADER_PAT.finditer(text))
        if not m_all:
            return  # nothing found

        # Using fallback pattern
        # Build slices by header indices:
        for idx, m in enumerate(m_all):
            reg_no = int(m.group(1))
            header_title = m.group(2).strip()
            start = m.end()
            end = (m_all[idx + 1].start() if idx + 1 < len(m_all) else len(text))
            yield reg_no, header_title, text[start:end].strip()
        return

    # Using "Regulation N" pattern
    for idx, m in enumerate(m_all):
        reg_no = int(m.group(1))
        header_title = m.group(2).strip()
        start = m.end()
        end = (m_all[idx + 1].start() if idx + 1 < len(m_all) else len(text))
        yield reg_no, header_title, text[start:end].strip()

def split_paren_blocks(body: str, top_pat: re.Pattern) -> list[tuple[str, str]]:
    """
    Split body by a top-level pattern like (1) (2) ...
    Returns list of (label, chunk_text)
    If no matches, return [(None, body)]
    """
    matches = list(top_pat.finditer(body))
    if not matches:
        return [("","" + body.strip())]
    out = []
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((label, body[start:end].strip()))
    return out

def emit_rule(rec: dict, out_f):
    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# --------------------------
# Main extraction
# --------------------------
def extract_rules(pdf_path: Path, out_path: Path, domain: str, prefix: str,
                  reg_start: int | None, reg_end: int | None, dedupe: bool):
    text = normalize_text(read_pdf_text(pdf_path))

    # Load existing for dedupe, if needed
    existing_ids = set()
    if dedupe and out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                try:
                    existing_ids.add(json.loads(line)["rule_id"])
                except Exception:
                    pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = out_path.open("a", encoding="utf-8")

    count = 0
    for reg_no, header_title, body in sectionize(text):
        if reg_start is not None and reg_no < reg_start:
            continue
        if reg_end is not None and reg_no > reg_end:
            continue

        body = body.strip()
        # First split by numeric subclauses (1)(2)...
        lvl1 = split_paren_blocks(body, PAREN_NUM_PAT)
        if len(lvl1) == 1 and lvl1[0][0] == "":  # no (1)(2) found
            # Single atomic rule for the whole regulation
            rule_id = f"{prefix}_{reg_no}"
            if rule_id not in existing_ids:
                rec = {
                    "rule_id": rule_id,
                    "domain": domain,
                    "title": header_title or first_sentence(body),
                    "text": body,
                    "lean_id": f"rule_{reg_no}",
                    "notes": "Auto-extracted; refine title/text as needed."
                }
                emit_rule(rec, out)
                count += 1
            continue

        # Otherwise, go deeper into lettered subclauses (a)(b) within each (n)
        for (n_label, n_chunk) in lvl1:
            n_chunk = n_chunk.strip()
            lvl2 = split_paren_blocks(n_chunk, PAREN_LET_PAT)
            if len(lvl2) == 1 and lvl2[0][0] == "":  # only numeric level
                # (n) only
                text_block = n_chunk
                title = first_sentence(text_block)
                rule_id = f"{prefix}_{reg_no}_{n_label}"
                if dedupe and rule_id in existing_ids:
                    continue
                rec = {
                    "rule_id": rule_id,
                    "domain": domain,
                    "title": f"{header_title} — ({n_label})" if header_title else title,
                    "text": text_block,
                    "lean_id": f"rule_{reg_no}_{n_label}",
                    "notes": "Auto-extracted subclause (n); review mapping."
                }
                emit_rule(rec, out); count += 1
            else:
                # numeric + lettered subclauses
                for (a_label, a_chunk) in lvl2:
                    text_block = a_chunk.strip()
                    if not text_block:
                        continue
                    title = first_sentence(text_block)
                    rule_id = f"{prefix}_{reg_no}_{n_label}_{a_label}"
                    if dedupe and rule_id in existing_ids:
                        continue
                    rec = {
                        "rule_id": rule_id,
                        "domain": domain,
                        "title": f"{header_title} — ({n_label})({a_label})" if header_title else title,
                        "text": text_block,
                        "lean_id": f"rule_{reg_no}_{n_label}_{a_label}",
                        "notes": "Auto-extracted subclause (n)(a); review mapping."
                    }
                    emit_rule(rec, out); count += 1

    out.close()
    print(f"✅ Wrote {count} rule records to {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to the rules PDF")
    ap.add_argument("--out", default="data/processed/rules.jsonl", help="Output JSONL path")
    ap.add_argument("--domain", default="SEBI_ICDR", help="Domain label")
    ap.add_argument("--prefix", default="ICDR", help="Rule ID prefix, e.g., 'ICDR'")
    ap.add_argument("--reg-start", type=int, default=None, help="First regulation number to include")
    ap.add_argument("--reg-end", type=int, default=None, help="Last regulation number to include")
    ap.add_argument("--dedupe", action="store_true", help="Skip rule_ids already present in output file")
    args = ap.parse_args()

    extract_rules(
        pdf_path=Path(args.pdf),
        out_path=Path(args.out),
        domain=args.domain,
        prefix=args.prefix,
        reg_start=args.reg_start,
        reg_end=args.reg_end,
        dedupe=args.dedupe
    )

if __name__ == "__main__":
    main()

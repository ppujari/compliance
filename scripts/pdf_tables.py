#!/usr/bin/env python3
"""
pdf_tables.py

Extract table-like data from PDF pages using pdfplumber.
Output is a JSON array of tables with normalized FY columns and rows.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


FY_HEADER_RE = re.compile(r"(financial\s+year\s+ended|fy\s?\d{2,4}|\d{4})", re.I)
UNIT_RE = re.compile(r"(₹|rs\.?|rupees)?\s*(in\s+)?(million|mn|crore|cr|lakh|lac|thousand|%)", re.I)


def _clean_cell(cell: Any) -> str:
    return str(cell or "").strip()


def _is_numeric_cell(s: str) -> bool:
    if not s:
        return False
    return bool(re.search(r"\d", s))


def _detect_unit(text: str) -> str:
    if not text:
        return ""
    m = UNIT_RE.search(text)
    if not m:
        return ""
    unit = m.group(3) or ""
    unit = unit.lower().replace("mn", "million").replace("cr", "crore").replace("lac", "lakh")
    if "%" in text:
        return "%"
    return unit


def _find_header_row(rows: List[List[str]]) -> Tuple[int, List[str]]:
    best_idx = -1
    best_row: List[str] = []
    best_count = 0
    for idx, row in enumerate(rows):
        count = 0
        for cell in row:
            if FY_HEADER_RE.search(cell or ""):
                count += 1
        if count > best_count:
            best_count = count
            best_idx = idx
            best_row = row
    if best_count >= 2:
        return best_idx, best_row
    return -1, []


def _numeric_columns(rows: List[List[str]]) -> List[int]:
    if not rows:
        return []
    col_count = max(len(r) for r in rows)
    numeric_counts = [0] * col_count
    for r in rows:
        for i, c in enumerate(r):
            if _is_numeric_cell(c):
                numeric_counts[i] += 1
    # keep columns with numeric presence in at least 2 rows
    return [i for i, ct in enumerate(numeric_counts) if ct >= 2]


def extract_page_tables(pdf_path: Path) -> List[Dict[str, Any]]:
    try:
        import pdfplumber  # type: ignore
    except Exception as e:
        raise RuntimeError("pdfplumber is required for table extraction") from e

    tables_out: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path.as_posix()) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for t_idx, tbl in enumerate(tables, start=1):
                if not tbl:
                    continue
                rows = [[_clean_cell(c) for c in row] for row in tbl]
                header_idx, header = _find_header_row(rows)
                numeric_cols = _numeric_columns(rows)
                if len(numeric_cols) < 3 and header_idx < 0:
                    continue
                fy_cols = []
                if header_idx >= 0:
                    for i, c in enumerate(header):
                        if FY_HEADER_RE.search(c):
                            fy_cols.append(i)
                if not fy_cols:
                    fy_cols = numeric_cols
                # Map FY label columns to value columns.
                # Strategy 1: look leftward for the nearest numeric column.
                # Strategy 2: if no column found to the left, try using the FY column
                #   itself as the value column (common RHP layout: metric | FY23 | FY22 | FY21).
                value_cols = []
                if header_idx >= 0 and fy_cols:
                    for fc in fy_cols:
                        chosen = None
                        # scan left to find nearest numeric column present in data rows
                        for j in range(fc - 1, -1, -1):
                            if j in numeric_cols:
                                chosen = j
                                break
                        if chosen is None and fc in numeric_cols:
                            # FY column IS the value column (e.g. metric | FY23val | FY22val)
                            chosen = fc
                        if chosen is not None and chosen not in value_cols:
                            value_cols.append(chosen)
                if not value_cols:
                    # Last resort: if multiple FY columns are adjacent numerics, use them all
                    value_cols = [fc for fc in fy_cols if fc in numeric_cols] or fy_cols
                # build rows
                data_rows: List[Dict[str, Any]] = []
                for r in rows[header_idx + 1 :] if header_idx >= 0 else rows:
                    if not r:
                        continue
                    label = _clean_cell(r[0]) if r else ""
                    if not label:
                        continue
                    values = [r[i] if i < len(r) else "" for i in value_cols]
                    if not any(_is_numeric_cell(v) for v in values):
                        continue
                    unit = _detect_unit(label) or _detect_unit(" ".join(header))
                    data_rows.append(
                        {"label": label, "values": values, "unit": unit}
                    )
                if not data_rows:
                    continue
                tables_out.append(
                    {
                        "page": page_idx,
                        "table_index": t_idx,
                        "header": header,
                        "fy_cols": fy_cols,
                        "value_cols": value_cols,
                        "rows": data_rows,
                    }
                )
    return tables_out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tables = extract_page_tables(Path(args.pdf))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(tables)} tables to {args.out}")


if __name__ == "__main__":
    main()

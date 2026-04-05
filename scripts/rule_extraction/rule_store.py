"""Persistence layer for enriched regulatory rules."""

from __future__ import annotations
import json
from pathlib import Path


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
            # First write in overwrite mode -- clear the file
            self.output_path.write_text("", encoding="utf-8")

        count = 0
        for rule in rules:
            if self.write_rule(rule, dedupe=dedupe):
                count += 1
        return count

    @property
    def written_count(self) -> int:
        return self._written_count

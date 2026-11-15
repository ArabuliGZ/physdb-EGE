"""Reapply local website edits after rebuilding the PhysEGE database."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from answer_units import format_answer_unit_tex  # noqa: E402

DEFAULT_DB = ROOT / "data" / "phyege.sqlite3"
DEFAULT_LOG = ROOT / "tools" / "site_edits" / "problem_text_edits.json"
FIELDS = {"statement", "answer", "solution", "answer_prefix", "answer_unit", "answer_table_labels"}
EMPTY_FIELDS = {"answer_prefix", "answer_unit"}


def apply_edits(db: Path, log: Path) -> int:
    data = json.loads(log.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("problems"), dict):
        raise ValueError("Invalid site edit log")
    con = sqlite3.connect(db)
    applied = 0
    try:
        if "answer_table_labels" not in {column[1] for column in con.execute("PRAGMA table_info(problems)")}:
            con.execute("ALTER TABLE problems ADD COLUMN answer_table_labels TEXT")
        for problem_id, edit in data["problems"].items():
            exists = con.execute("SELECT 1 FROM problems WHERE id=?", (problem_id,)).fetchone()
            if not exists:
                raise ValueError(f"Edited problem no longer exists: {problem_id}")
            fields = edit.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise ValueError(f"Missing edited fields for {problem_id}")
            for field, value in fields.items():
                if (field not in FIELDS or not isinstance(value, str) or
                        field not in EMPTY_FIELDS and not value.strip()):
                    raise ValueError(f"Invalid {field!r} edit for {problem_id}")
                value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
                if field == "answer_unit":
                    value = format_answer_unit_tex(value)
                if field == "answer_table_labels":
                    labels = json.loads(value)
                    if (not isinstance(labels, list) or not 2 <= len(labels) <= 6 or
                            any(not isinstance(label, str) or not label.strip() or
                                len(label) > 500 for label in labels)):
                        raise ValueError(f"Invalid answer table labels for {problem_id}")
                con.execute(f"UPDATE problems SET {field}=? WHERE id=?", (value, problem_id))
                applied += 1
        con.commit()
    finally:
        con.close()
    return applied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()
    applied = apply_edits(args.db, args.log)
    print(f"Applied site text edits: {applied}")


if __name__ == "__main__":
    main()

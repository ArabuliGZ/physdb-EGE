r"""Replace unsupported ``\degree`` in the database and saved site edits.

The importers call ``text_repairs.normalize_degree_notation`` too, so the
replacement survives a database rebuild and replay of local edits.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from text_repairs import normalize_degree_notation


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
from editor import read_edit_log, write_edit_log  # noqa: E402


DB_FIELDS = ("statement", "answer", "solution", "criteria", "answer_prefix", "answer_unit")


def normalize_database(path: Path) -> tuple[int, int]:
    changed_rows = 0
    replacements = 0
    with sqlite3.connect(path) as con:
        columns = {column[1] for column in con.execute("PRAGMA table_info(problems)")}
        fields = tuple(field for field in DB_FIELDS if field in columns)
        query = "SELECT id," + ",".join(fields) + " FROM problems"
        for row in con.execute(query).fetchall():
            updates = {}
            for field, value in zip(fields, row[1:]):
                if not isinstance(value, str):
                    continue
                normalized = normalize_degree_notation(value)
                if normalized != value:
                    updates[field] = normalized
                    replacements += value.count(r"\degree")
            if updates:
                assignments = ",".join(f"{field}=?" for field in updates)
                con.execute(f"UPDATE problems SET {assignments} WHERE id=?",
                            (*updates.values(), row[0]))
                changed_rows += 1
    return changed_rows, replacements


def normalize_edit_log(path: Path) -> tuple[int, int]:
    data = read_edit_log(path)
    changed_records = 0
    replacements = 0
    for entry in data["problems"].values():
        fields = entry.get("fields", {})
        changed = False
        for field, value in fields.items():
            if not isinstance(value, str):
                continue
            normalized = normalize_degree_notation(value)
            if normalized != value:
                fields[field] = normalized
                replacements += value.count(r"\degree")
                changed = True
        changed_records += changed
    if changed_records:
        write_edit_log(path, data)
    return changed_records, replacements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "phyege.sqlite3")
    parser.add_argument("--log", type=Path,
                        default=ROOT / "tools" / "site_edits" / "problem_text_edits.json")
    args = parser.parse_args()
    db_rows, db_replacements = normalize_database(args.db)
    log_rows, log_replacements = normalize_edit_log(args.log)
    print(f"Database: {db_rows} tasks, {db_replacements} degree commands replaced")
    print(f"Site edits: {log_rows} tasks, {log_replacements} degree commands replaced")


if __name__ == "__main__":
    main()

"""Normalize stored answer-field suffixes to inline TeX."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from answer_units import format_answer_unit_tex  # noqa: E402
from editor import read_edit_log, write_edit_log  # noqa: E402

DEFAULT_DB = ROOT / "data" / "phyege.sqlite3"
DEFAULT_LOG = ROOT / "tools" / "site_edits" / "problem_text_edits.json"


def normalize(db: Path, log_path: Path, write: bool) -> tuple[int, int]:
    con = sqlite3.connect(db)
    db_changes = 0
    try:
        rows = con.execute(
            "SELECT id,answer_unit FROM problems WHERE answer_unit IS NOT NULL").fetchall()
        for problem_id, current in rows:
            formatted = format_answer_unit_tex(current)
            if formatted == current:
                continue
            db_changes += 1
            if write:
                con.execute("UPDATE problems SET answer_unit=? WHERE id=?",
                            (formatted, problem_id))
        if write:
            con.commit()
    finally:
        con.close()

    log_changes = 0
    data = read_edit_log(log_path)
    for edit in data["problems"].values():
        fields = edit.get("fields", {})
        if "answer_unit" not in fields:
            continue
        formatted = format_answer_unit_tex(fields["answer_unit"])
        if formatted == fields["answer_unit"]:
            continue
        fields["answer_unit"] = formatted
        log_changes += 1
    if write and log_changes:
        write_edit_log(log_path, data)
    return db_changes, log_changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    db_changes, log_changes = normalize(args.db, args.log, args.write)
    action = "Formatted" if args.write else "Would format"
    print(f"{action} answer units: database — {db_changes}, edit log — {log_changes}")


if __name__ == "__main__":
    main()

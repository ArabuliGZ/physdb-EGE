"""Exercise local LaTeX editing and reproducible replay on temporary files."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "tools"))

from editor import save_text_edit  # noqa: E402
from server import attach_answer_metadata  # noqa: E402
from apply_site_text_edits import apply_edits  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="physege-editor-") as name:
        root = Path(name)
        db = root / "test.sqlite3"
        log = root / "problem_text_edits.json"
        shutil.copy2(ROOT / "data" / "phyege.sqlite3", db)
        con = sqlite3.connect(db)
        problem_id, original_answer, original_prefix, original_unit = con.execute(
            """SELECT id,answer,answer_prefix,answer_unit FROM problems
            WHERE answer<>'' AND COALESCE(answer_format,'')<>'number_pair'
            ORDER BY id LIMIT 1""").fetchone()
        table_problem_id = con.execute("""SELECT id FROM problems
            WHERE answer_format='matching' ORDER BY id LIMIT 1""").fetchone()[0]
        con.close()
        edited_answer = original_answer + " \\(x=x\\)"
        result = save_text_edit(db, log, problem_id, "answer", edited_answer)
        if not result["changed"]:
            raise ValueError("Editor did not report a change")
        result = save_text_edit(db, log, problem_id, "answer_field",
                                "Ответ: в ____________ \\(\\text{м/с}\\)")
        if not result["changed"]:
            raise ValueError("Answer-field editor did not report a change")
        result = save_text_edit(db, log, table_problem_id, "answer_table",
                                "А\n\\(\\text{давление}\\)")
        if not result["changed"]:
            raise ValueError("Answer-table editor did not report a change")
        con = sqlite3.connect(db)
        stored = con.execute(
            "SELECT answer,answer_prefix,answer_unit FROM problems WHERE id=?",
            (problem_id,)).fetchone()
        con.execute("""UPDATE problems SET answer=?,answer_prefix=?,answer_unit=?
            WHERE id=?""", (original_answer, original_prefix, original_unit, problem_id))
        stored_table = con.execute("SELECT answer_table_labels FROM problems WHERE id=?",
                                   (table_problem_id,)).fetchone()[0]
        con.execute("UPDATE problems SET answer_table_labels=NULL WHERE id=?", (table_problem_id,))
        con.commit()
        con.close()
        if stored != (edited_answer, "в", r"\(\text{м/с}\)"):
            raise ValueError("Editor did not update answer fields in SQLite")
        if stored_table != json.dumps(["А", r"\(\text{давление}\)"], ensure_ascii=False):
            raise ValueError("Editor did not update answer-table labels in SQLite")
        if apply_edits(db, log) != 4:
            raise ValueError("Edit replay count is incorrect")
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        replayed = tuple(con.execute(
            "SELECT answer,answer_prefix,answer_unit FROM problems WHERE id=?",
            (problem_id,)).fetchone())
        replayed_table = con.execute("SELECT answer_table_labels FROM problems WHERE id=?",
                                     (table_problem_id,)).fetchone()[0]
        table_problem = dict(con.execute("""SELECT p.*,v.exam_year,v.variant_number
            FROM problems p JOIN variants v ON v.id=p.variant_id WHERE p.id=?""",
            (table_problem_id,)).fetchone())
        con.close()
        if replayed != stored:
            raise ValueError("Editor log did not replay the change")
        if replayed_table != stored_table:
            raise ValueError("Editor log did not replay the answer table")
        attach_answer_metadata(table_problem)
        if table_problem["answer_field"]["labels"] != ["А", r"\(\text{давление}\)"]:
            raise ValueError("Edited answer table is missing from the site metadata")
    print("Checked local LaTeX editor and replay log")


if __name__ == "__main__":
    main()

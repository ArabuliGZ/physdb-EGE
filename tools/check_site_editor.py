"""Exercise local LaTeX editing and reproducible replay on temporary files."""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "tools"))

from editor import save_text_edit  # noqa: E402
from apply_site_text_edits import apply_edits  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="physege-editor-") as name:
        root = Path(name)
        db = root / "test.sqlite3"
        log = root / "problem_text_edits.json"
        shutil.copy2(ROOT / "data" / "phyege.sqlite3", db)
        con = sqlite3.connect(db)
        problem_id, original = con.execute(
            "SELECT id,statement FROM problems ORDER BY id LIMIT 1").fetchone()
        con.close()
        edited = original + "\n\nПроверка локального редактора: \\(x=x\\)."
        result = save_text_edit(db, log, problem_id, "statement", edited)
        if not result["changed"]:
            raise ValueError("Editor did not report a change")
        con = sqlite3.connect(db)
        stored = con.execute("SELECT statement FROM problems WHERE id=?", (problem_id,)).fetchone()[0]
        con.execute("UPDATE problems SET statement=? WHERE id=?", (original, problem_id))
        con.commit()
        con.close()
        if stored != edited:
            raise ValueError("Editor did not update SQLite")
        if apply_edits(db, log) != 1:
            raise ValueError("Edit replay count is incorrect")
        con = sqlite3.connect(db)
        replayed = con.execute("SELECT statement FROM problems WHERE id=?", (problem_id,)).fetchone()[0]
        con.close()
        if replayed != edited:
            raise ValueError("Editor log did not replay the change")
    print("Checked local LaTeX editor and replay log")


if __name__ == "__main__":
    main()

"""Check the scanned-book variant 3 import and preserved site-editor changes."""
from __future__ import annotations

import json
import sqlite3

from apply_site_text_edits import DEFAULT_LOG
from fipi_2027_3_figures import SOLUTION_FIGURES, STATEMENT_FIGURES
from fipi_2027_3_transcription import ANSWERS, ANSWER_TABLE_LABELS
from import_examples import DB, ROOT
from tex_format import format_quantities


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    variants = con.execute(
        """SELECT id,source_path FROM variants
           WHERE exam_year=2027 AND variant_number='3'"""
    ).fetchall()
    assert len(variants) == 1
    variant = variants[0]
    assert (ROOT / variant["source_path"]).exists()
    tasks = {
        row["problem_number"]: row for row in con.execute(
            "SELECT * FROM problems WHERE variant_id=?", (variant["id"],)
        )
    }
    assert set(tasks) == set(range(1, 27))
    for number, task in tasks.items():
        assert task["answer"] == format_quantities(ANSWERS[number]), number
        assert task["extraction_status"] == "needs_review", number
        assert task["statement"].strip() and "стр." in task["source_locator"]
        if number in ANSWER_TABLE_LABELS:
            assert json.loads(task["answer_table_labels"]) == ANSWER_TABLE_LABELS[number]
        if number >= 21:
            assert task["solution"] and task["criteria"], number
        assets = con.execute(
            """SELECT pa.role,a.storage_path FROM problem_assets pa
               JOIN assets a ON a.id=pa.asset_id
               WHERE pa.problem_id=? ORDER BY pa.rowid""",
            (task["id"],),
        ).fetchall()
        for role, figures in (
            ("statement_figure", STATEMENT_FIGURES),
            ("solution_figure", SOLUTION_FIGURES),
        ):
            actual = [asset for asset in assets if asset["role"] == role]
            assert len(actual) == len(figures.get(number, [])), (number, role)
            assert all((ROOT / asset["storage_path"]).exists() for asset in actual)
        relevance = con.execute(
            """SELECT verdict,target_problem_number FROM relevance
               WHERE problem_id=? AND exam_year=2027""",
            (task["id"],),
        ).fetchone()
        assert relevance and relevance["target_problem_number"] == number
        assert relevance["verdict"] == ("partial" if number == 22 else "yes")
    assert len(STATEMENT_FIGURES[14]) == 2
    assert len(STATEMENT_FIGURES[17]) == 1
    assert 20 not in STATEMENT_FIGURES
    assert all(f"{i})" in tasks[20]["statement"] for i in range(1, 6))
    assert all(text in tasks[17]["statement"] for text in (
        "ПРОЦЕССЫ", "ЭНЕРГИЯ ФОТОНА", "А)", "Б)", "4)",
    ))

    edits = json.loads(DEFAULT_LOG.read_text(encoding="utf-8"))["problems"]
    for problem_id, entry in edits.items():
        row = con.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
        assert row is not None, f"Edited task disappeared: {problem_id}"
        for field, value in entry["fields"].items():
            if field == "answer_unit":
                from answer_units import format_answer_unit_tex
                value = format_answer_unit_tex(value)
            assert row[field] == value.strip(), f"Editor text changed: {problem_id}.{field}"
    print(
        "Book variant 3: 26 tasks, key, figures, layouts and relevance valid; "
        f"{sum(len(entry['fields']) for entry in edits.values())} site edits preserved"
    )


if __name__ == "__main__":
    main()

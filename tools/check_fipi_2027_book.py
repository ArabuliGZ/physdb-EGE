"""Check the first scanned-book import against its source index and site edits."""
from __future__ import annotations

import json
import sqlite3

from apply_site_text_edits import DEFAULT_LOG
from fipi_2027_1_figures import SOLUTION_FIGURES, STATEMENT_FIGURES
from fipi_2027_1_transcription import ANSWERS, ANSWER_TABLE_LABELS
from import_examples import DB, ROOT
from tex_format import format_quantities


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    variants = con.execute("""SELECT id,source_path FROM variants
        WHERE exam_year=2027 AND variant_number='1'""").fetchall()
    assert len(variants) == 1, "Expected one imported book variant"
    variant = variants[0]
    assert (ROOT / variant["source_path"]).exists()
    tasks = {row["problem_number"]: row for row in con.execute(
        "SELECT * FROM problems WHERE variant_id=?", (variant["id"],))}
    assert set(tasks) == set(range(1, 27)), "Missing or extra tasks"
    for number, task in tasks.items():
        assert task["answer"] == format_quantities(ANSWERS[number]), f"Key differs for task {number}"
        assert task["extraction_status"] == "needs_review", number
        assert task["statement"].strip() and "стр." in task["source_locator"]
        if number in ANSWER_TABLE_LABELS:
            assert json.loads(task["answer_table_labels"]) == ANSWER_TABLE_LABELS[number]
        if number >= 21:
            assert task["solution"] and task["criteria"], number
        assets = con.execute("""SELECT pa.role,a.storage_path FROM problem_assets pa
            JOIN assets a ON a.id=pa.asset_id WHERE pa.problem_id=?
            ORDER BY pa.rowid""", (task["id"],)).fetchall()
        for role, expected in (("statement_figure", STATEMENT_FIGURES),
                               ("solution_figure", SOLUTION_FIGURES)):
            actual = [a for a in assets if a["role"] == role]
            assert len(actual) == len(expected.get(number, [])), (number, role)
            assert all((ROOT / a["storage_path"]).exists() for a in actual)
        relevance = con.execute("""SELECT verdict,target_problem_number FROM relevance
            WHERE problem_id=? AND exam_year=2027""", (task["id"],)).fetchone()
        assert relevance and relevance["target_problem_number"] == number
        assert relevance["verdict"] == ("partial" if number == 22 else "yes")

    edits = json.loads(DEFAULT_LOG.read_text(encoding="utf-8"))["problems"]
    for problem_id, entry in edits.items():
        row = con.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
        assert row is not None, f"Edited task disappeared: {problem_id}"
        for field, value in entry["fields"].items():
            if field == "answer_unit":
                from answer_units import format_answer_unit_tex
                value = format_answer_unit_tex(value)
            assert row[field] == value.strip(), f"Editor text changed: {problem_id}.{field}"
    print(f"Book variant 1: 26 tasks, key, figures and relevance valid; "
          f"{sum(len(x['fields']) for x in edits.values())} site edits preserved")


if __name__ == "__main__":
    main()

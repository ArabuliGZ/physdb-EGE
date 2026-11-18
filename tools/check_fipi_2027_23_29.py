"""Verify the reproducible imports of FIPI 2027 variants 23, 25, 27, 29."""
from __future__ import annotations

import importlib
import json
import sqlite3

from apply_site_text_edits import DEFAULT_LOG
from import_examples import DB, ROOT
from tex_format import format_quantities


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    for number in (23, 25, 27, 29):
        data = importlib.import_module(f"fipi_2027_{number}_transcription")
        figures = importlib.import_module(f"fipi_2027_{number}_figures")
        variants = con.execute(
            "SELECT id,source_path FROM variants WHERE exam_year=2027 AND variant_number=?",
            (str(number),),
        ).fetchall()
        assert len(variants) == 1, number
        variant = variants[0]
        assert (ROOT / variant["source_path"]).exists(), number
        tasks = {
            row["problem_number"]: row for row in con.execute(
                "SELECT * FROM problems WHERE variant_id=?", (variant["id"],)
            )
        }
        assert set(tasks) == set(range(1, 27)), number
        for task_number, task in tasks.items():
            assert task["statement"].strip(), (number, task_number)
            assert task["answer"] == format_quantities(data.ANSWERS[task_number]), (number, task_number)
            assert task["extraction_status"] == "needs_review", (number, task_number)
            assert f"стр. {data.SOURCE_PAGES[task_number]}" in task["source_locator"]
            if task_number >= 21:
                assert task["solution"] and task["criteria"], (number, task_number)
            if task_number in data.ANSWER_TABLE_LABELS:
                assert json.loads(task["answer_table_labels"]) == data.ANSWER_TABLE_LABELS[task_number]
            assets = con.execute(
                """SELECT pa.role,a.storage_path FROM problem_assets pa
                   JOIN assets a ON a.id=pa.asset_id WHERE pa.problem_id=?""",
                (task["id"],),
            ).fetchall()
            for role, mapping in (
                ("statement_figure", figures.STATEMENT_FIGURES),
                ("solution_figure", figures.SOLUTION_FIGURES),
            ):
                actual = [asset for asset in assets if asset["role"] == role]
                assert len(actual) == len(mapping.get(task_number, [])), (number, task_number, role)
                assert all((ROOT / asset["storage_path"]).exists() for asset in actual)
            relevance = con.execute(
                """SELECT verdict,target_problem_number FROM relevance
                   WHERE problem_id=? AND exam_year=2027""", (task["id"],)
            ).fetchone()
            assert relevance and relevance["target_problem_number"] == task_number
            assert relevance["verdict"] in ("yes", "partial"), (number, task_number)
        print(f"Variant {number}: 26 tasks, key, source, figures and relevance valid")

    edits = json.loads(DEFAULT_LOG.read_text(encoding="utf-8"))["problems"]
    for problem_id, entry in edits.items():
        task = con.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
        assert task is not None, f"Editor task disappeared: {problem_id}"
        for field, value in entry["fields"].items():
            if field == "answer_unit":
                from answer_units import format_answer_unit_tex
                value = format_answer_unit_tex(value)
            assert task[field] == value.strip(), f"Editor text changed: {problem_id}.{field}"
    print(f"Preserved {sum(len(entry['fields']) for entry in edits.values())} site edits")


if __name__ == "__main__":
    main()

"""Check the three 30-task sources and the separate 2027 catalogue mapping."""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from docx import Document

from import_2023 import SOURCE_ROOT, source_key
from import_examples import DB, ROOT
from mapping_2023_2027 import SOURCE_FORMAT, SOURCE_POINTS, assessment
from tex_format import format_quantities


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    problems = con.execute("""SELECT p.*,v.variant_number,v.source_path,v.source_sha256
        FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2023 ORDER BY v.variant_number,p.problem_number""").fetchall()
    assert len(problems) == 90, len(problems)
    by_variant: dict[str, list[sqlite3.Row]] = {str(n): [] for n in (1, 2, 3)}
    for problem in problems:
        by_variant[problem["variant_number"]].append(problem)
    figure_counts = Counter()
    for variant, rows in by_variant.items():
        source = SOURCE_ROOT / f"2023 В{variant}.docx"
        assert source == ROOT / rows[0]["source_path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == rows[0]["source_sha256"]
        key = source_key(Document(source))
        assert [row["problem_number"] for row in rows] == list(range(1, 31))
        for row in rows:
            number = row["problem_number"]
            assert row["statement"].strip() and row["source_locator"].startswith("DOCX paragraphs ")
            assert row["max_points"] == SOURCE_POINTS[number]
            assert row["answer_format"] == SOURCE_FORMAT[number]
            assert row["extraction_status"] == "needs_review"
            assert row["answer"] == (format_quantities(key[number]) if number <= 23 else None)
            assert bool(row["solution"]) == bool(row["criteria"]) == (number >= 24)
            if number == 24:
                assert "Полное правильное решение" not in row["statement"]
                assert r"\begin{tabular}{l|l}" not in row["statement"]
                assert "F, НN, Н" not in row["statement"]
            for field in ("statement", "answer", "solution", "criteria"):
                text = row[field] or ""
                assert "[[formula:" not in text and "[[SRCFORMULA" not in text
                assert "[формула в исходном" not in text
            relevance = con.execute("""SELECT target_problem_number,verdict,topic_match,format_match
                FROM relevance WHERE problem_id=? AND exam_year=2027""", (row["id"],)).fetchall()
            assert len(relevance) == 1, (variant, number, relevance)
            target, verdict, topic_ok, format_ok, _ = assessment(int(variant), number)
            assert tuple(relevance[0]) == (target, verdict, topic_ok, format_ok), (variant, number, relevance)
            for asset in con.execute("""SELECT a.storage_path,a.sha256,pa.role FROM problem_assets pa
                JOIN assets a ON a.id=pa.asset_id WHERE pa.problem_id=?""", (row["id"],)):
                path = ROOT / asset["storage_path"]
                assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
                figure_counts[(variant, asset["role"])] += 1
        assert all(r"Критерий \(1\)" in row["criteria"] and r"Критерий \(2\)" in row["criteria"]
                   for row in rows if row["problem_number"] == 30)
        print(f"2023-{variant}: 30 tasks, 23 matching author answers, 7 solutions and rubrics")
    # The count is source occurrences, not 2027 positions; some old lines map
    # to the same target position, and incompatible lines remain in the source.
    assert sum(row["verdict"] in ("yes", "partial") for row in con.execute("""SELECT r.verdict
        FROM relevance r JOIN problems p ON p.id=r.problem_id JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2023 AND r.exam_year=2027""")) == 79
    sys.path.insert(0, str(ROOT / "web"))
    import server
    for number in range(1, 27):
        assert all(row["target_problem_number"] == number and row["verdict"] in ("yes", "partial")
                   for row in server.list_problems({"number": [str(number)]}))
    assert all(row["verdict"] in ("yes", "partial") for row in server.variant_options())
    assert all(len(server.selected_problems(v["id"], None)) == 30
               for v in server.variants() if v["exam_year"] == 2023)
    print("2027 catalogue: 26 target numbers, only fully or partially suitable tasks")
    print("2023 figure occurrences:", dict(figure_counts))


if __name__ == "__main__":
    main()

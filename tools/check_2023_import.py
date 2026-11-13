"""Check the three 30-task sources and the separate 2027 catalogue mapping."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from docx import Document

from import_2023 import SOURCE_ROOT, numbered, source_key
from curated_answers_2023 import EXTENDED_ANSWERS
from import_examples import DB, ROOT
from mapping_2023_2027 import SOURCE_FORMAT, SOURCE_POINTS, assessment
from tex_format import format_quantities


PRINTED_KEYS = {
    "1": "0 4 0,25 235 12 23 180 100 60 35 41 3 2 6 13 13 31 4 13 145 125 362 15",
    "2": "8 70 0,8 23 31 43 300 216 6 134 12 135 1,25 30 12 13 24 0,2 33 24 433 3,60,1 15",
    "3": "-2,5 0,32 1,4 25 33 43 1,5 100 1 145 23 6 1 6 15 11 31 20 31 135 253 111 14",
}
# Transcribed independently from the printed answer pages of the author PDFs:
# page 17 for variants 1–2, page 16 for variant 3.


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
        doc = Document(source)
        key = source_key(doc)
        assert [key[number].replace(" ", "") for number in range(1, 24)] == (
            PRINTED_KEYS[variant].split()
        ), (variant, key)
        key_start = next(i for i, paragraph in enumerate(doc.paragraphs)
                         if "Ответы к заданиям" in paragraph.text)
        source_starts = numbered(doc, 0, key_start, 1, 30)
        if variant == "1":
            source_starts[29] = 435  # floating task label in this author file
        pair_answers = {"1": ("362", r"\(36\pm2\)"),
                        "2": ("3,60,1", r"\(3{,}6\pm0{,}1\)"),
                        "3": ("111", r"\(11\pm1\)")}
        assert key[22] == pair_answers[variant][0]
        assert [row["problem_number"] for row in rows] == list(range(1, 31))
        for row in rows:
            number = row["problem_number"]
            assert row["statement"].strip() and row["source_locator"].startswith("DOCX paragraphs ")
            source_prose = " ".join(paragraph.text for paragraph in
                                    doc.paragraphs[source_starts[number]:
                                                   source_starts.get(number + 1, key_start)])
            if number == 22:
                source_prose = source_prose.split("В бланк ответов")[0]
            elif number == 23:
                source_prose = source_prose.split("Часть 2")[0]
            elif number == 24:
                source_prose = source_prose.split("Полное правильное решение")[0]
            words = lambda value: set(word.lower() for word in
                                      re.findall(r"[А-Яа-яЁё]{4,}", value))
            # Word text loses embedded MathType symbols; this checks prose only.
            editorial = {"ответ"}
            if (variant, number) == ("2", 14):
                editorial.add("градусов")  # answer-unit instruction
            if (variant, number) == ("2", 29):
                editorial.add("авых")  # replaced by A_{вых}
            if (variant, number) == ("3", 21):
                editorial.update(("массой", "жёсткостью"))  # author typo repaired
            missing = words(source_prose) - words(row["statement"]) - editorial
            assert not missing, (variant, number, sorted(missing))
            assert row["max_points"] == SOURCE_POINTS[number]
            assert row["answer_format"] == SOURCE_FORMAT[number]
            assert row["extraction_status"] == "needs_review"
            expected_answer = (format_quantities(EXTENDED_ANSWERS[(int(variant), number)]) if number >= 24 else
                               pair_answers[variant][1] if number == 22 else
                               format_quantities(key[number]))
            assert row["answer"] == expected_answer, (variant, number, row["answer"])
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
            if re.search(r"рисунк|график|диаграмм", row["statement"], re.I):
                assert con.execute("""SELECT COUNT(*) FROM problem_assets WHERE problem_id=?
                    AND role='statement_figure'""", (row["id"],)).fetchone()[0] >= 1, (variant, number)
        assert all(r"Критерий \(1\)" in row["criteria"] and r"Критерий \(2\)" in row["criteria"]
                   for row in rows if row["problem_number"] == 30)
        print(f"2023-{variant}: 30 tasks, 23 matching author answers, 7 solutions and rubrics")
    # The count is source occurrences, not 2027 positions; some old lines map
    # to the same target position, and incompatible lines remain in the source.
    assert sum(row["verdict"] in ("yes", "partial") for row in con.execute("""SELECT r.verdict
        FROM relevance r JOIN problems p ON p.id=r.problem_id JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2023 AND r.exam_year=2027""")) == 74
    assert con.execute("""SELECT COUNT(*) FROM relevance r JOIN problems p ON p.id=r.problem_id
        JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2023 AND
        v.variant_number='2' AND p.problem_number=26 AND r.exam_year=2027 AND
        r.target_problem_number=25 AND r.verdict='partial'""").fetchone()[0] == 1
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

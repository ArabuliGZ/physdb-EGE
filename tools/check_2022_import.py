"""Regression checks for all four Demidova 2022 source variants."""
from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter

from docx import Document

from curated_answers_2022 import EXTENDED_ANSWERS
from import_2022 import SOURCE_ROOT, SOURCES, PAIRED_KEYS, ORDERED_STATEMENT_FIGURES, FORMULAS, source_key
from import_examples import DB, ROOT
from mapping_2022_2027 import SOURCE_FORMAT, assessment, source_points
from tex_format import format_quantities


# Independently transcribed from the printed answer tables.
PRINTED_KEYS = {
    1: "124 524 –10 48 18,5 12 12 31 750 560 8 13 23 8 8 60 124 21 41 192 22 0,800,05 24",
    2: "24 144 0 50 2040 15 21 23 1 100 2 13 21 3 2 1 24 32 14 254 24 0,40,1 14",
    3: "134 324 3 0,16 0,3 125 33 34 200 500 50 15 13 40 20 2 15 21 14 40 23 451 13",
    4: "23 431 2,7 90 1,8 25 32 43 1 6 200 134 23 140 1 0,002 245 22 41 78 13 3,80,1 25",
}


def main() -> None:
    assert len(FORMULAS) == 237
    for sha, formula in FORMULAS.items():
        assert len(sha) == 64 and formula["tex"]
        assert "source PDF p" in formula.get("source_locator", ""), sha
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT p.*,v.exam_year,v.variant_number,v.source_path,v.source_sha256
        FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2022 ORDER BY v.variant_number,p.problem_number""").fetchall()
    assert len(rows) == 120, len(rows)
    verdicts = Counter()
    for variant, source_name in SOURCES.items():
        group = [row for row in rows if row["variant_number"] == str(variant)]
        assert [row["problem_number"] for row in group] == list(range(1, 31))
        source = SOURCE_ROOT / source_name
        assert ROOT / group[0]["source_path"] == source
        assert hashlib.sha256(source.read_bytes()).hexdigest() == group[0]["source_sha256"]
        key = source_key(Document(source))
        assert [key[number] for number in range(1, 24)] == PRINTED_KEYS[variant].split()
        for row in group:
            number = row["problem_number"]
            assert row["statement"].strip() and row["answer"].strip()
            assert row["source_locator"].startswith("DOCX paragraphs ")
            assert row["max_points"] == source_points(variant, number)
            assert row["answer_format"] == SOURCE_FORMAT[number]
            assert row["extraction_status"] == "needs_review"
            expected_answer = (format_quantities(EXTENDED_ANSWERS[(variant, number)]) if number >= 24 else
                               PAIRED_KEYS[variant][1] if number == 22 else key[number])
            if number < 24 and number != 22:
                expected_answer = format_quantities(expected_answer)
            assert row["answer"] == expected_answer, (variant, number, row["answer"])
            assert bool(row["solution"]) == bool(row["criteria"]) == (number >= 24)
            for field in ("statement", "answer", "solution", "criteria"):
                value = row[field] or ""
                assert "[[formula:" not in value and "[[SRCFORMULA" not in value
                assert "[формула в исходном" not in value
            actual = con.execute("""SELECT target_problem_number,verdict,topic_match,format_match
                FROM relevance WHERE problem_id=? AND exam_year=2027""", (row["id"],)).fetchall()
            assert len(actual) == 1, (variant, number)
            target, verdict, topic_ok, format_ok, _ = assessment(variant, number)
            assert tuple(actual[0]) == (target, verdict, topic_ok, format_ok), (variant, number)
            verdicts[verdict] += 1
            for asset in con.execute("""SELECT a.storage_path,a.sha256 FROM problem_assets pa
                JOIN assets a ON a.id=pa.asset_id WHERE pa.problem_id=?""", (row["id"],)):
                path = ROOT / asset["storage_path"]
                assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        print(f"2022-{variant}: 30 tasks; keys, solutions, rubrics and 2027 mapping present")
    assert verdicts == Counter({"yes": 99, "no": 18, "partial": 3}), verdicts
    expected_figures = {
        (1, 12): 1, (1, 22): 1, (1, 23): 1,
        (2, 2): 5, (2, 3): 1, (2, 23): 0,
        (3, 2): 5, (3, 3): 1, (3, 23): 5,
        (4, 23): 0,
    }
    for (variant, number), expected in expected_figures.items():
        count = con.execute("""SELECT COUNT(*) FROM problem_assets pa
            JOIN problems p ON p.id=pa.problem_id JOIN variants v ON v.id=p.variant_id
            WHERE v.exam_year=2022 AND v.variant_number=? AND p.problem_number=?
            AND pa.role='statement_figure'""", (str(variant), number)).fetchone()[0]
        assert count == expected, (variant, number, count, expected)
    for (variant, number), expected in ORDERED_STATEMENT_FIGURES.items():
        actual = [row[0] for row in con.execute("""SELECT a.sha256 FROM problem_assets pa
            JOIN problems p ON p.id=pa.problem_id JOIN variants v ON v.id=p.variant_id
            JOIN assets a ON a.id=pa.asset_id
            WHERE v.exam_year=2022 AND v.variant_number=? AND p.problem_number=?
            AND pa.role='statement_figure' ORDER BY pa.rowid""",
            (str(variant), number))]
        assert actual == list(expected), (variant, number, actual)
    assert con.execute("""SELECT COUNT(*) FROM problem_assets pa
        JOIN problems p ON p.id=pa.problem_id JOIN variants v ON v.id=p.variant_id
        JOIN assets a ON a.id=pa.asset_id WHERE v.exam_year=2022 AND pa.role='statement_figure'
        AND a.sha256='f0114b5d5b6e1c480e82b74c07df3981b1b0926a7fc00d240672e6648173ae1d'""").fetchone()[0] == 0
    assert con.execute("PRAGMA foreign_key_check").fetchone() is None
    print("2022 compatibility:", dict(verdicts))


if __name__ == "__main__":
    main()

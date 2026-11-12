"""Check completeness and source links for the three staged 2026 imports."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from import_2026_remaining import NON_FIGURE_PNG_SHA

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
con.row_factory = sqlite3.Row
expected_lists = {
    2: {5: 5, 6: 3, 9: 5, 10: 3, 14: 5, 15: 3, 17: 3, 18: 5},
    3: {5: 5, 6: 3, 9: 5, 10: 3, 14: 5, 15: 3, 17: 3, 18: 4},
    4: {5: 5, 6: 4, 9: 5, 10: 3, 14: 5, 15: 3, 17: 4, 18: 5},
}
for variant_number, list_counts in expected_lists.items():
    variant = con.execute("""SELECT * FROM variants WHERE exam_year=2026
        AND variant_number=?""", (str(variant_number),)).fetchone()
    assert variant is not None, variant_number
    source = ROOT / variant["source_path"]
    assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == variant["source_sha256"]
    tasks = con.execute("SELECT * FROM problems WHERE variant_id=? ORDER BY problem_number", (variant["id"],)).fetchall()
    assert [task["problem_number"] for task in tasks] == list(range(1, 27))
    assert sum(task["answer"] is not None for task in tasks) == 20
    assert sum(task["solution"] is not None and task["criteria"] is not None for task in tasks) == 6
    assert all(task["extraction_status"] == "needs_review" for task in tasks)
    for task in tasks:
        statement = task["statement"]
        assert statement.strip() and "Система оценивания экзаменационной работы" not in statement
        assert "формула в исходном DOCX" not in statement and "&%" not in statement
        assert statement.count(r"\begin{tabular}") == statement.count(r"\end{tabular}"), (variant_number, task["problem_number"])
        if task["problem_number"] in list_counts:
            count = len(re.findall(r"(?m)^\d+\)\s", statement))
            assert count == list_counts[task["problem_number"]], (variant_number, task["problem_number"], count)
    print(f"2026-{variant_number}: 26 tasks, 20 key answers, 6 solutions and rubrics; source hash matches")
assert "Ученик выполнял лабораторную работу" not in con.execute("""SELECT p.statement FROM problems p
    JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2026 AND v.variant_number='3'
    AND p.problem_number=3""").fetchone()[0]
assert "Ученик выполнял лабораторную работу" in con.execute("""SELECT p.statement FROM problems p
    JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2026 AND v.variant_number='3'
    AND p.problem_number=4""").fetchone()[0]
missing_assets = [path for (path,) in con.execute("SELECT storage_path FROM assets") if not (ROOT / path).is_file()]
assert not missing_assets, missing_assets
assert not con.execute("SELECT 1 FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)").fetchone()
for variant_number, number in [(2, 24), (4, 11)]:
    count = con.execute("""SELECT count(*) FROM problem_assets pa JOIN problems p ON p.id=pa.problem_id
        JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2026 AND v.variant_number=?
        AND p.problem_number=? AND pa.role='statement_figure'
        AND pa.source_locator LIKE 'DOCX preheading figure%'""",
        (str(variant_number), number)).fetchone()[0]
    assert count == 1, (variant_number, number)
assert not con.execute("SELECT 1 FROM assets WHERE sha256 IN (" +
                       ",".join("?" * len(NON_FIGURE_PNG_SHA)) + ")",
                       tuple(NON_FIGURE_PNG_SHA)).fetchone()
print("All linked image files present; no orphan assets")

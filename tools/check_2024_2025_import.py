"""Check completeness, provenance and source list structure of older imports."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from docx import Document

from import_2024_2025 import CURATED_FIGURES, RENDERED_FIGURES, sources, repair_floating
from import_2026_remaining import NON_FIGURE_PNG_SHA, numbered_paragraphs, paragraph_interval, element_text

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
con.row_factory = sqlite3.Row
# Source list counts checked from each original Word variant, in task order
# 5, 6, 9, 10, 14, 15, 17, 18.
EXPECTED_LISTS = {
    (2024, "1-1"): (5, 4, 5, 3, 5, 3, 3, 5),
    (2024, "1-2"): (5, 3, 5, 3, 5, 3, 3, 5),
    (2024, "1-3"): (5, 3, 5, 4, 5, 4, 4, 5),
    (2024, "1-4"): (5, 4, 5, 4, 5, 3, 3, 5),
    (2024, "2-1"): (5, 3, 5, 3, 5, 3, 3, 5),
    (2024, "2-2"): (5, 4, 5, 3, 5, 3, 3, 5),
    (2024, "2-3"): (5, 4, 5, 3, 5, 3, 3, 5),
    (2024, "2-4"): (5, 4, 5, 3, 5, 3, 3, 5),
    (2025, "1-1"): (5, 3, 5, 3, 5, 3, 4, 5),
    (2025, "1-2"): (5, 3, 5, 3, 5, 4, 3, 5),
    (2025, "1-3"): (5, 3, 5, 3, 5, 3, 3, 5),
    (2025, "2-1"): (5, 3, 5, 3, 5, 3, 4, 5),
    (2025, "2-2"): (5, 3, 5, 3, 5, 4, 3, 5),
    (2025, "2-3"): (5, 3, 5, 3, 5, 3, 3, 5),
}
variants = con.execute("SELECT * FROM variants WHERE exam_year IN (2024,2025)").fetchall()
assert len(variants) == 14, len(variants)
for variant in variants:
    source = ROOT / variant["source_path"]
    assert source.is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == variant["source_sha256"]
    tasks = con.execute("SELECT * FROM problems WHERE variant_id=? ORDER BY problem_number",
                        (variant["id"],)).fetchall()
    assert [task["problem_number"] for task in tasks] == list(range(1, 27))
    assert sum(task["answer"] is not None for task in tasks) == 20
    assert sum(task["solution"] is not None and task["criteria"] is not None for task in tasks) == 6
    assert all(task["extraction_status"] == "needs_review" for task in tasks)
    assert all(task["statement"].strip() and "&%" not in task["statement"] for task in tasks)
    assert all(task["statement"].count(r"\begin{tabular}") == task["statement"].count(r"\end{tabular}") for task in tasks)
    for task in tasks:
        if re.search(r"рисун|\bрис\.|график", task["statement"], re.I):
            linked = con.execute("""SELECT count(*) FROM problem_assets
                WHERE problem_id=? AND role='statement_figure'""", (task["id"],)).fetchone()[0]
            assert linked, (variant["exam_year"], variant["variant_number"], task["problem_number"])
    counts = tuple(len(re.findall(r"(?m)^\d+\)\s", tasks[n - 1]["statement"]))
                   for n in (5, 6, 9, 10, 14, 15, 17, 18))
    assert counts == EXPECTED_LISTS[(variant["exam_year"], variant["variant_number"])], counts
    own_relevance = con.execute("""SELECT count(*) FROM relevance r JOIN problems p ON p.id=r.problem_id
        WHERE p.variant_id=? AND r.exam_year=2027 AND r.target_problem_number=p.problem_number""",
        (variant["id"],)).fetchone()[0]
    assert own_relevance == 26, (variant["variant_number"], own_relevance)
    print(variant["exam_year"], variant["variant_number"], "26 tasks, 20 answers, 6 rubrics; hash and lists match")
companions = con.execute("SELECT * FROM variant_sources").fetchall()
assert len(companions) == 10
for item in companions:
    path = ROOT / item["source_path"]
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == item["source_sha256"]
assert not con.execute("SELECT 1 FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)").fetchone()
assert all((ROOT / row[0]).is_file() for row in con.execute("SELECT storage_path FROM assets"))
print("10 companion sources and all linked images present; no orphan assets")

for year, series, number, source, parsed, _ in sources():
    doc = Document(parsed)
    end = next((i for i, p in enumerate(doc.paragraphs)
                if "Критерии оценивания выполнения заданий с развёрнутым ответом" in p.text),
               len(doc.paragraphs))
    starts = numbered_paragraphs(doc, 0, end)
    repair_floating(doc, starts, end)
    if (year, series, number) == (2024, 2, 2):
        starts[7], starts[8] = 145, 157
    for n in range(1, 21):
        blocks = paragraph_interval(doc, starts[n], starts[n + 1])
        markers = sum(element_text(block, doc, []).count("Ответ:") for block in blocks)
        assert markers <= 1, (year, series, number, n, markers)
        if n in (1, 2, 3, 4, 7, 8, 11, 12, 13, 16, 19):
            assert markers == 1, (year, series, number, n, markers)
print("Numeric task boundaries match their answer boxes in all 14 sources")

for (label, number), filename in RENDERED_FIGURES.items():
    year, series, variant = label.split("-")
    sha = hashlib.sha256((CURATED_FIGURES / filename).read_bytes()).hexdigest()
    matches = con.execute("""SELECT count(*) FROM problem_assets pa
        JOIN problems p ON p.id=pa.problem_id JOIN variants v ON v.id=p.variant_id
        JOIN assets a ON a.id=pa.asset_id WHERE v.exam_year=? AND v.variant_number=?
        AND p.problem_number=? AND pa.role='statement_figure' AND a.sha256=?""",
        (int(year), f"{series}-{variant}", number, sha)).fetchone()[0]
    assert matches == 1, (label, number, filename)
for year, variant, number in [(2024, "2-1", 24), (2024, "2-3", 22),
                               (2024, "2-3", 24), (2024, "2-4", 10),
                               (2025, "1-1", 14), (2025, "2-1", 14)]:
    corrected = con.execute("""SELECT count(*) FROM problem_assets pa
        JOIN problems p ON p.id=pa.problem_id JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=? AND v.variant_number=? AND p.problem_number=?
        AND pa.role='statement_figure' AND pa.source_locator LIKE 'DOCX preheading figure%'""",
        (year, variant, number)).fetchone()[0]
    assert corrected == 1, (year, variant, number)
assert not con.execute("SELECT 1 FROM assets WHERE sha256 IN (" +
                       ",".join("?" * len(NON_FIGURE_PNG_SHA)) + ")",
                       tuple(NON_FIGURE_PNG_SHA)).fetchone()
print("Rendered vector diagrams, shifted figures, and decorative-image exclusions match")

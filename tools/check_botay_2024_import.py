"""Validate the four archived 2024 Botay papers and preserved site edits."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from answer_units import format_answer_unit_tex
from apply_site_text_edits import DEFAULT_LOG
from fetch_botay_2024 import SLUGS
from import_botay_2024 import VARIANTS, verify_archive
from import_examples import DB, ROOT

EXPECTED = {
    "2024-real-11-24105": (0, 0, 17, 1, 0),
    "2024-real-11-24107": (0, 6, 12, 1, 6),
    "2024-real-11-24109": (0, 6, 20, 4, 0),
    "2024-otkryt-11-1": (6, 6, 14, 0, 1),
}
TABLES = {
    ("2024-real-11-24105", 20): 1,
    ("2024-real-11-24107", 20): 1,
    ("2024-real-11-24109", 4): 1,
    ("2024-real-11-24109", 5): 2,
    ("2024-otkryt-11-1", 20): 1,
}
RELEVANCE_EXCEPTIONS = {
    ("2024-real-11-24105", 7): "no",
    ("2024-real-11-24105", 21): "no",
    ("2024-real-11-24105", 23): "no",
    ("2024-real-11-24107", 7): "no",
    ("2024-real-11-24107", 22): "partial",
    ("2024-real-11-24109", 21): "no",
    ("2024-real-11-24109", 22): "partial",
    ("2024-real-11-24109", 23): "no",
    ("2024-otkryt-11-1", 7): "no",
    ("2024-otkryt-11-1", 21): "no",
    ("2024-otkryt-11-1", 22): "partial",
    ("2024-otkryt-11-1", 23): "no",
    ("2024-otkryt-11-1", 25): "no",
}


def main() -> None:
    verify_archive()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        for slug in SLUGS:
            number, title = VARIANTS[slug]
            variants = con.execute(
                "SELECT * FROM variants WHERE exam_year=2024 AND variant_number=?", (number,),
            ).fetchall()
            assert len(variants) == 1 and variants[0]["title"] == title, slug
            variant = variants[0]
            assert (ROOT / variant["source_path"]).exists(), slug
            rows = con.execute(
                "SELECT * FROM problems WHERE variant_id=? ORDER BY problem_number", (variant["id"],),
            ).fetchall()
            assert [row["problem_number"] for row in rows] == list(range(1, 27)), slug
            keys = solutions = figures = source_pages = solution_figures = 0
            for row in rows:
                n = row["problem_number"]
                assert row["statement"].strip() and row["extraction_status"] == "needs_review", (slug, n)
                assert row["criteria"] is None and "[[formula:" not in row["statement"], (slug, n)
                assert f"/{slug}/#z{n}" in row["source_locator"], (slug, n)
                assert row["statement"].count(r"\begin{tabular}") == TABLES.get((slug, n), 0), (slug, n)
                assert "$$" not in (row["solution"] or ""), (slug, n)
                if row["answer_unit"]:
                    assert format_answer_unit_tex(row["answer_unit"]) == row["answer_unit"], (slug, n)
                if n in (6, 10, 15, 17):
                    assert len(json.loads(row["answer_table_labels"])) == 2, (slug, n)
                relevance = con.execute(
                    "SELECT verdict FROM relevance WHERE problem_id=? AND exam_year=2027 AND target_problem_number=?",
                    (row["id"], n),
                ).fetchone()
                assert relevance and relevance["verdict"] == RELEVANCE_EXCEPTIONS.get((slug, n), "yes"), (slug, n)
                keys += bool(row["answer"])
                solutions += bool(row["solution"])
                for asset in con.execute(
                    """SELECT a.storage_path,pa.role FROM problem_assets pa JOIN assets a
                       ON a.id=pa.asset_id WHERE pa.problem_id=?""", (row["id"],),
                ):
                    assert (ROOT / asset["storage_path"]).exists(), (slug, n)
                    figures += asset["role"] == "statement_figure"
                    source_pages += asset["role"] == "source_page"
                    solution_figures += asset["role"] == "solution_figure"
            actual = (keys, solutions, figures, source_pages, solution_figures)
            assert actual == EXPECTED[slug], (slug, actual)
            print(f"{slug}: 26 tasks, {keys} keys, {solutions} solutions, "
                  f"{figures} figures, {source_pages} source tables, "
                  f"{solution_figures} solution figures")
        edits = json.loads(DEFAULT_LOG.read_text(encoding="utf-8"))["problems"]
        for pid, entry in edits.items():
            row = con.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
            assert row is not None, pid
            for field, value in entry["fields"].items():
                if field == "answer_unit":
                    value = format_answer_unit_tex(value)
                assert row[field] == value.strip(), (pid, field)
        print(f"Preserved {sum(len(entry['fields']) for entry in edits.values())} site edits")
    finally:
        con.close()


if __name__ == "__main__":
    main()

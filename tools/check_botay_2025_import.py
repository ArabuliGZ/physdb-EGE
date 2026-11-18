"""Validate the seven archived 2025 Botay papers after import."""
from __future__ import annotations

import json
import sqlite3

from apply_site_text_edits import DEFAULT_LOG
from answer_units import format_answer_unit_tex
from fetch_botay_2025 import SLUGS
from import_botay_2025 import VARIANTS, verify_archive
from import_examples import DB, ROOT


EXPECTED_IMAGES = {
    "2025-osnov-11-7": 10,
    "2025-osnov-11-centr-6": 10,
    "2025-osnov-11-dv-1": 11,
    "2025-osnov-11-dv-2": 11,
    "2025-osnov-11-sib-3": 16,
    "2025-osnov-11-sz-4": 13,
    "2025-osnov-11-ural-5": 10,  # Three additional Ural images document source tables.
}
TABLES = {
    ("2025-osnov-11-centr-6", 7): 1,
    ("2025-osnov-11-dv-1", 5): 1,
    ("2025-osnov-11-dv-1", 14): 1,
    ("2025-osnov-11-dv-1", 20): 1,
    ("2025-osnov-11-dv-2", 14): 1,
    ("2025-osnov-11-sib-3", 7): 1,
    ("2025-osnov-11-sib-3", 20): 1,
    ("2025-osnov-11-sz-4", 5): 2,
    ("2025-osnov-11-sz-4", 20): 1,
    ("2025-osnov-11-ural-5", 5): 1,
    ("2025-osnov-11-ural-5", 14): 1,
    ("2025-osnov-11-ural-5", 20): 1,
}


def main() -> None:
    verify_archive()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    for slug in SLUGS:
        number, title = VARIANTS[slug]
        variants = con.execute(
            "SELECT * FROM variants WHERE exam_year=2025 AND variant_number=?", (number,)
        ).fetchall()
        assert len(variants) == 1 and variants[0]["title"] == title, slug
        variant = variants[0]
        assert (ROOT / variant["source_path"]).exists(), slug
        rows = con.execute(
            "SELECT * FROM problems WHERE variant_id=? ORDER BY problem_number", (variant["id"],)
        ).fetchall()
        assert [row["problem_number"] for row in rows] == list(range(1, 27)), slug
        keys = solutions = images = 0
        for row in rows:
            n = row["problem_number"]
            assert row["statement"].strip() and row["extraction_status"] == "needs_review", (slug, n)
            assert row["criteria"] is None and r"[[formula:" not in row["statement"], (slug, n)
            assert f"/{slug}/#z{n}" in row["source_locator"], (slug, n)
            assert row["statement"].count(r"\begin{tabular}") == TABLES.get((slug, n), 0), (slug, n)
            if row["answer_unit"]:
                assert format_answer_unit_tex(row["answer_unit"]) == row["answer_unit"], (slug, n)
            if n in (6, 10, 15, 17) and not (slug.endswith("ural-5") and n == 10):
                assert len(json.loads(row["answer_table_labels"])) == 2, (slug, n)
            if slug.endswith("ural-5") and n == 10:
                assert row["answer_format"] == "multiple_choice" and not row["answer_table_labels"]
            verdict = con.execute(
                "SELECT verdict FROM relevance WHERE problem_id=? AND exam_year=2027 AND target_problem_number=?",
                (row["id"], n),
            ).fetchone()
            assert verdict and verdict["verdict"] in ("yes", "partial", "no"), (slug, n)
            keys += bool(row["answer"])
            solutions += bool(row["solution"])
            for asset in con.execute(
                """SELECT a.storage_path,pa.role FROM problem_assets pa JOIN assets a
                   ON a.id=pa.asset_id WHERE pa.problem_id=?""", (row["id"],)
            ):
                assert (ROOT / asset["storage_path"]).exists(), (slug, n)
                images += asset["role"] == "statement_figure"
        expected_keys = 26 if slug.endswith("-7") else 0
        expected_solutions = 6 if slug.endswith("-7") else 0
        assert (keys, solutions, images) == (
            expected_keys, expected_solutions, EXPECTED_IMAGES[slug]
        ), (slug, keys, solutions, images)
        print(f"{slug}: 26 tasks, {keys} keys, {solutions} solutions, {images} figures")
    edits = json.loads(DEFAULT_LOG.read_text(encoding="utf-8"))["problems"]
    for pid, entry in edits.items():
        task = con.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
        assert task is not None, pid
        for field, value in entry["fields"].items():
            if field == "answer_unit":
                value = format_answer_unit_tex(value)
            assert task[field] == value.strip(), (pid, field)
    print(f"Preserved {sum(len(entry['fields']) for entry in edits.values())} site edits")


if __name__ == "__main__":
    main()

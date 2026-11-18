"""Check all three 2026 Botay variants and preserve admin edits."""
from __future__ import annotations

import json
import sqlite3

from apply_site_text_edits import DEFAULT_LOG
from answer_units import format_answer_unit_tex
from import_botay_2026 import ARCHIVE, SLUGS, verify_archive
from import_examples import DB, ROOT


def main() -> None:
    verify_archive()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    expected_counts = {
        "2026-osnov-11-dv-1": (0, 6, 12),
        "2026-otkryt-11-1": (0, 0, 15),
        "2026-dosrok-11-1": (26, 6, 15),
    }
    for slug, (number, title) in SLUGS.items():
        variants = con.execute(
            "SELECT * FROM variants WHERE exam_year=2026 AND variant_number=?",
            (number,),
        ).fetchall()
        assert len(variants) == 1 and variants[0]["title"] == title, slug
        variant = variants[0]
        assert (ROOT / variant["source_path"]).exists(), slug
        tasks = con.execute(
            "SELECT * FROM problems WHERE variant_id=? ORDER BY problem_number",
            (variant["id"],),
        ).fetchall()
        assert [row["problem_number"] for row in tasks] == list(range(1, 27)), slug
        actual = (
            sum(bool(row["answer"]) for row in tasks),
            sum(bool(row["solution"]) for row in tasks),
            sum(con.execute(
                "SELECT COUNT(*) FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                (row["id"],),
            ).fetchone()[0] for row in tasks),
        )
        assert actual == expected_counts[slug], (slug, actual)
        for row in tasks:
            n = row["problem_number"]
            assert row["statement"].strip() and row["extraction_status"] == "needs_review"
            assert row["criteria"] is None
            assert f"/{slug}/#z{n}" in row["source_locator"]
            assert r"\underline" not in row["statement"], (slug, n)
            if row["answer_unit"]:
                assert format_answer_unit_tex(row["answer_unit"]) == row["answer_unit"]
            if n in (6, 10, 15, 17):
                assert len(json.loads(row["answer_table_labels"])) == 2, (slug, n)
            verdict = con.execute(
                "SELECT verdict FROM relevance WHERE problem_id=? AND exam_year=2027 AND target_problem_number=?",
                (row["id"], n),
            ).fetchone()
            assert verdict and verdict["verdict"] == ("no" if n in (21, 23) else "yes")
            if n in (21, 23):
                assert row["topic"] == ("molecular" if n == 21 else "electrodynamics")
            for asset in con.execute(
                """SELECT a.storage_path FROM problem_assets pa
                   JOIN assets a ON a.id=pa.asset_id WHERE pa.problem_id=?""",
                (row["id"],),
            ):
                assert (ROOT / asset["storage_path"]).exists(), (slug, n)
        print(f"{slug}: 26 tasks, {actual[0]} answers, {actual[1]} solutions, {actual[2]} figures")
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

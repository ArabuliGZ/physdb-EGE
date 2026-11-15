"""Apply checked figure-link repairs without reimporting manually edited text."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from import_examples import DB, link_asset, store_asset  # noqa: E402
from import_2023 import CURATED_FIGURES, CURATED_STATEMENT_FIGURES  # noqa: E402
from import_2024_2025 import RENDERED_FIGURES  # noqa: E402


def problem(con: sqlite3.Connection, year: int, variant: str, number: int) -> tuple[str, str]:
    row = con.execute("""SELECT p.id,p.review_notes FROM problems p
        JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=?
        AND v.variant_number=? AND p.problem_number=? AND p.alternative_number=1""",
                      (year, variant, number)).fetchone()
    if row is None:
        raise ValueError(f"Missing {year}-{variant} task {number}")
    return row


def replace_figure(con: sqlite3.Connection, problem_id: str, source: Path,
                   locator: str) -> None:
    con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                (problem_id,))
    asset_id = store_asset(con, source.read_bytes(), ".png", "image/png")
    link_asset(con, problem_id, asset_id, "statement_figure", locator)


def append_note(con: sqlite3.Connection, problem_id: str, notes: str, note: str) -> None:
    if note not in (notes or ""):
        notes = ((notes or "").rstrip() + " " + note).strip()
        con.execute("UPDATE problems SET review_notes=? WHERE id=?", (notes, problem_id))


def main() -> None:
    con = sqlite3.connect(DB)
    orphaned: list[Path] = []
    with con:
        problem_id, notes = problem(con, 2024, "2-3", 26)
        filename = RENDERED_FIGURES[("2024-2-3", 26)]
        replace_figure(
            con, problem_id, CURATED_FIGURES / filename,
            f"visually checked source-page crop: {filename}; source page 14",
        )
        append_note(con, problem_id, notes,
                    "Рисунок условия визуально сверён по странице 14 исходного Word-документа.")

        for variant in ("1", "2", "3"):
            problem_id, notes = problem(con, 2023, variant, 23)
            con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                        (problem_id,))
            append_note(
                con, problem_id, notes,
                "Страница 13 исходного Word-документа не содержит рисунка задания; "
                "служебный значок конца части исключён.",
            )

        for task, page, description in (
                (27, 15, "схемы цилиндра"),
                (28, 15, "электрической схемы")):
            problem_id, notes = problem(con, 2023, "3", task)
            filename, _ = CURATED_STATEMENT_FIGURES[(3, task)]
            replace_figure(
                con, problem_id, CURATED_FIGURES / filename,
                f"visually checked source-page crop: {filename}; source page {page}",
            )
            append_note(
                con, problem_id, notes,
                f"Привязка {description} визуально сверена по странице {page} исходного Word-документа.",
            )

        orphaned = [ROOT / path for (path,) in con.execute("""SELECT storage_path FROM assets
            WHERE id NOT IN (SELECT asset_id FROM problem_assets)""")]
        con.execute("DELETE FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)")
    con.close()

    for path in orphaned:
        if path.resolve().is_relative_to((ROOT / "assets" / "objects").resolve()) and path.is_file():
            path.unlink()
    print("Repaired five requested figure associations")


if __name__ == "__main__":
    main()

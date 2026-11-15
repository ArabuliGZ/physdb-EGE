"""Attach the checked piston diagram to 2022-4 task 27."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from import_2022 import CURATED_STATEMENT_FIGURES
from import_examples import DB, ROOT, link_asset, store_asset


def main() -> None:
    con = sqlite3.connect(DB)
    with con:
        row = con.execute("""SELECT p.id,p.review_notes FROM problems p
            JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2022
            AND v.variant_number='4' AND p.problem_number=27
            AND p.alternative_number=1""").fetchone()
        if row is None:
            raise ValueError("Missing 2022-4 task 27")
        problem_id, notes = row
        filename, expected_sha = CURATED_STATEMENT_FIGURES[(4, 27)]
        source = ROOT / "assets" / "curated" / "figure_repairs" / filename
        content = source.read_bytes()
        asset_id = store_asset(con, content, ".png", "image/png")
        actual_sha = con.execute("SELECT sha256 FROM assets WHERE id=?", (asset_id,)).fetchone()[0]
        if actual_sha != expected_sha:
            raise ValueError(f"Unexpected curated figure hash: {actual_sha}")
        con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                    (problem_id,))
        link_asset(con, problem_id, asset_id, "statement_figure",
                   f"visually checked source-page crop: {filename}; source page 12")
        note = ("Рисунок условия визуально сверён по странице 12 исходного Word-документа "
                "и предоставлен пользователем в совпадающем виде.")
        if note not in (notes or ""):
            con.execute("UPDATE problems SET review_notes=? WHERE id=?",
                        ((((notes or "").rstrip() + " " + note).strip()), problem_id))
    con.close()
    print("Attached checked figure to 2022-4 task 27")


if __name__ == "__main__":
    main()

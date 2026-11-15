"""Move the three 2022-3 statement figures to their checked tasks."""
from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
FIGURES = {
    28: "e1a2e8863db9101606fd8b9d563f082d9a4041c9f941e64af2be4bf47536417d",
    29: "8a13e7a1e59067e18f6f85c1dc12b2d738bd9f258d72d641fb7256d5fd9dc211",
    30: "0e95a95519fe78e495d807616d0555440b5188d833b082db7326fa165e3dd68b",
}


def main() -> None:
    con = sqlite3.connect(DB)
    with con:
        problems = dict(con.execute("""SELECT p.problem_number,p.id FROM problems p
            JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2022
            AND v.variant_number='3' AND p.problem_number IN (28,29,30)
            AND p.alternative_number=1"""))
        if set(problems) != set(FIGURES):
            raise ValueError(f"Missing 2022-3 tasks 28-30: {problems}")

        assets = {}
        for number, sha in FIGURES.items():
            row = con.execute("SELECT id FROM assets WHERE sha256=?", (sha,)).fetchone()
            if row is None:
                raise ValueError(f"Missing source figure for task {number}: {sha}")
            assets[number] = row[0]

        for problem_id in problems.values():
            con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                        (problem_id,))
        for number, problem_id in problems.items():
            con.execute("""INSERT INTO problem_assets
                (problem_id,asset_id,role,source_locator) VALUES (?,?,?,?)""",
                (problem_id, assets[number], "statement_figure",
                 f"visually checked source-page figure for 2022-3 task {number}; source page 16"))
            row = con.execute("SELECT review_notes FROM problems WHERE id=?", (problem_id,)).fetchone()
            note = ("Привязка рисунка условия визуально сверена по странице 16 "
                    "исходного Word-документа.")
            notes = row[0] or ""
            if note not in notes:
                con.execute("UPDATE problems SET review_notes=? WHERE id=?",
                            (((notes.rstrip() + " " + note).strip()), problem_id))
    con.close()
    print("Corrected 2022-3 statement figures for tasks 28-30")


if __name__ == "__main__":
    main()

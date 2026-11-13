"""Apply the same source-backed notation repairs to an already imported DB."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from text_repairs import repair_text


DB = Path(__file__).resolve().parents[1] / "data" / "phyege.sqlite3"


def main() -> None:
    con = sqlite3.connect(DB)
    rows = con.execute("""SELECT p.id, v.exam_year, v.variant_number, p.problem_number,
        p.statement, p.solution, p.criteria FROM problems p
        JOIN variants v ON v.id=p.variant_id""").fetchall()
    changed = 0
    with con:
        for pid, year, variant, number, statement, solution, criteria in rows:
            label = f"{year}-{variant}"
            repaired = tuple(repair_text(label, number, field, value) for field, value in
                             (("statement", statement), ("solution", solution), ("criteria", criteria)))
            if repaired != (statement, solution, criteria):
                con.execute("""UPDATE problems SET statement=?, solution=?, criteria=?
                    WHERE id=?""", (*repaired, pid))
                changed += 1
    print(f"Repaired {changed} of {len(rows)} problem records")


if __name__ == "__main__":
    main()

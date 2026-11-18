"""Restore published keys from the 2024 variant PDFs with scoring tables.

These PDFs are independently archived beside the Botay source files. Keys below
are transcribed from the printed 'Система оценивания' table (not inferred by AI).
Only empty fields are filled, so local site-editor corrections take precedence.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
ARCHIVE = ROOT / "Материалы" / "ЕГЭ 2024 Botay"
# PDF variant 1 = Botay 24107, variant 2 = 24109, variant 3 = 24105.
KEYS = {
    "БОТАЙ-ОСНОВ-1": (
        3, 15, ("-2", "90", "106", "45", "15", "41", "450", "4", "15", "23",
                "4", "2", "2", "235", "32", "38", "21", "34", "3,6±0,2", "15")),
    "БОТАЙ-ОСНОВ-2": (
        1, 13, ("-5", "0,5", "48", "6", "345", "11", "6", "255", "23", "32",
                "1", "1,5", "0,9", "34", "22", "125", "31", "25", "0,46±0,02", "12")),
    "БОТАЙ-ОСНОВ-3": (
        2, 14, ("32,5", "200", "1,4", "160", "135", "31", "200", "400", "135", "11",
                "3", "1,25", "70", "245", "12", "170", "11", "125", "2,2±0,1", "13")),
}


def tex_answer(raw: str) -> str:
    return "\\(" + raw.replace(",", "{,}").replace("±", r"\pm") + "\\)"


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    count = 0
    for variant, (pdf_number, page, keys) in KEYS.items():
        source = ARCHIVE / f"variant_{pdf_number}_fizika-ege-2024-0205_solutions.pdf"
        if not source.is_file():
            raise FileNotFoundError(source)
        rows = list(con.execute("""SELECT p.id,p.problem_number,p.answer FROM problems p
            JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2024
            AND v.variant_number=? AND p.alternative_number=1 AND p.problem_number<=20
            ORDER BY p.problem_number""", (variant,)))
        if len(rows) != 20 or [row[1] for row in rows] != list(range(1, 21)):
            raise ValueError(f"Unexpected task set in {variant}")
        for pid, number, current in rows:
            if current:
                continue
            answer = tex_answer(keys[number - 1])
            print(f"2024-{variant} №{number}: {answer}")
            count += 1
            if write:
                note = (f" Ответ по таблице оценивания: {source.relative_to(ROOT).as_posix()}, "
                        f"PDF с. {page}, №{number}.")
                con.execute("""UPDATE problems SET answer=?,review_notes=COALESCE(review_notes,'') || ?
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""", (answer, note, pid))
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    con = sqlite3.connect(DB)
    try:
        with con:
            print(f"Completed published keys: {run(con, write=args.write)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()

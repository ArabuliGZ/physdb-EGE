"""Restore the question omitted from Botay 2025 DV1 task 26 extraction."""
from __future__ import annotations

import hashlib
import sqlite3

from complete_botay_from_solutions import DB
from site_edit_guard import edited_fields

EXPECTED_SHA = "0364094c343c2bf9"
SOURCE = "https://100ballnik.com/wp-content/uploads/2025/06/variant-ege-fizika-2-2025.pdf"
TAIL = ("Определите массу рычага, если стальной диск имеет массу "
        r"\(250\,\text{г}\). Сделайте рисунок, на котором укажите все силы, "
        "действующие на рычаг и диск. Обоснуйте применимость законов, "
        "используемых для решения задачи.")


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    row = con.execute("""SELECT p.id,p.statement FROM problems p JOIN variants v
        ON v.id=p.variant_id WHERE v.exam_year=2025 AND
        v.variant_number='БОТАЙ-ДВ-1' AND p.problem_number=26""").fetchone()
    if not row:
        raise ValueError("Missing 2025 DV1 task 26")
    pid, statement = row
    if TAIL in statement or "statement" in edited_fields(pid):
        return 0
    if hashlib.sha256(statement.encode()).hexdigest()[:16] != EXPECTED_SHA:
        print("Skip edited 2025 DV1 №26 condition")
        return 0
    if write:
        con.execute("""UPDATE problems SET statement=?,
            review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
            WHERE id=?""", (statement.rstrip()+"\n\n"+TAIL,
                f" statement: восстановлен вопрос из опубликованного PDF {SOURCE}, с. 101.", pid))
    return 1


if __name__ == "__main__":
    with sqlite3.connect(DB) as con:
        print(f"Restored 2025 DV1 task 26 question: {run(con, write=True)}")

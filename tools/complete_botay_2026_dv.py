"""Matched 2026 Far East keys from the published 2026 exam collection.

Task 21 is deliberately excluded: the similar published card uses a different
thermodynamic cycle. Task 23 is independently calculated from the Botay text.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

from complete_botay_from_solutions import DB
from site_edit_guard import edited_fields

SOURCE = "https://phys-ege.sdamgia.ru/test?id=11428027"
KEYS = {
    1: ("-2", 50690, "cb05dcc42534ae64"),
    2: ("0,3", 50695, "1d6ee7bb391c3510"),
    3: ("4", 50702, "307fc4bfb120b3d2"),
    4: ("20", 50708, "54a82b92bdf80953"),
    5: ("25", 50720, "d5b93480d5f08d5d"),
    6: ("22", 50729, "c8e69759dc2dd046"),
    7: ("100", 50730, "cf18776d8f0d9ebe"),
    8: ("4", 50735, "61b9b7ffcfa03c96"),
    9: ("35", 50742, "c8e6fc6777d1e99b"),
    10: ("33", 50761, "73927d8ecb605463"),
    11: ("2,25", 50717, "f898f0ea89adda0a"),
    12: ("12", 50750, "c328abc5fba02cb5"),
    13: ("90", 50767, "c48635a235ca62b6"),
    14: ("25", 50773, "169e08e7939af622"),
    15: ("21", 50779, "a2cbc9450ed5dffe"),
    16: ("29", 50786, "f76adc73751965eb"),
    17: ("22", 50791, "0a0883640f468996"),
    18: ("135", 50801, "1464365e55048349"),
    19: ("136±2", 50809, "d08b2b25f01055f3"),
    20: ("24", 50854, "3bda3a4fbf71fa00"),
    22: ("0,5", 50840, "061cfe3660457b81"),
    23: (r"6\cdot10^8\,\text{Кл}/\text{кг}", 50829, "f80e052106b6940a"),
    24: ("39\\%", 50817, "3a200611f5a62430"),
    25: (r"5\,\text{см}^2", 50808, "440dad2a5ca6063e"),
    26: (r"1000\,\text{кг}", 50794, "44cb39d47fcf6cb7"),
}


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    count = 0
    for number, (raw, source_id, expected_hash) in KEYS.items():
        row = con.execute("""SELECT p.id,p.statement,p.answer,p.review_notes FROM problems p
            JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2026
            AND v.variant_number='ОСНОВ-ДВ-1' AND p.problem_number=?
            AND p.alternative_number=1""", (number,)).fetchone()
        if not row:
            raise ValueError(f"Missing 2026 Far East #{number}")
        pid, statement, answer, notes = row
        if hashlib.sha256(statement.encode()).hexdigest()[:16] != expected_hash:
            print(f"Skip 2026 Far East №{number}: condition changed")
            continue
        if "answer" in edited_fields(pid):
            continue
        value = r"\(" + re.sub(r"(?<!\\),(?=\d)", "{,}", raw).replace("±", r"\pm") + r"\)"
        owned = (f"карточка {source_id}" in (notes or ""))
        if answer == value or answer and not owned:
            continue
        count += 1
        if write:
            if owned:
                con.execute("UPDATE problems SET answer=? WHERE id=?", (value, pid))
                continue
            source = (f"расчёт ИИ по условию, опубликованная карточка {source_id} без ключа"
                      if number == 23 else f"опубликованный ключ {SOURCE}, карточка {source_id}")
            note = f" answer: {source}; требуется проверка."
            con.execute("""UPDATE problems SET answer=?,
                review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                WHERE id=? AND (answer IS NULL OR trim(answer)='')""", (value, note, pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed 2026 Far East answers: {run(connection, write=True)}")

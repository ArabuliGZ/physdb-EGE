"""Published and independently solved keys for Botay 2025 early variant 1.

The source PDF itself mislabels task 20: its apparatus table permits studying
external resistance, not EMF. Restore the published wording for that task.
"""
from __future__ import annotations

import hashlib
import sqlite3

from complete_botay_from_solutions import DB, tex_answer
from site_edit_guard import edited_fields

SOURCE = "https://phys-ege.sdamgia.ru/test?id=10303509"
KEYS = {
    # number: (answer, published problem ID or None for AI result, statement SHA prefix)
    1: ("-10", 42267, "47d5aefcbf25c4ad"),
    2: ("150", 42268, "e4fc00bbf03d44ce"),
    3: ("16", 42269, "228c972edfd6f1b9"),
    4: ("6250", 42270, "6b4d68fc63aa5ef8"),
    5: ("14", None, "eccea827654e0913"),
    6: ("31", None, "24a180d5adeae694"),
    7: ("4", 42273, "4e5795fafb483c3d"),
    8: ("100", 42274, "3155da49067ee602"),
    9: ("12", 42275, "493d6c6cc6518a4f"),
    10: ("32", None, "7fdc2b0aebbebea1"),
    11: ("1,5", 42277, "ff751ca7079c2a64"),
    12: ("3", 42278, "a4387d8b99e2a124"),
    13: ("2", 42279, "f132910a8411cdb9"),
    14: ("124", 42280, "b27beffeff3ac5ee"),
    15: ("32", None, "2897a0b5c044be3b"),
    16: ("25", None, "221f408f8b2c2e86"),
    17: ("13", None, "bcc046e8e9e27677"),
    18: ("25", None, "8c294fb7dcdc9d1a"),
    19: (r"\(44\pm2\)", 42285, "8805e802efc8e2d0"),
    20: ("15", 42286, "878a957ed6d9bb56"),
    21: (r"\(3\)", 42287, "64557107a7c21401"),
    22: (r"\(\approx0{,}17\,\text{мл}\)", None, "9bc01c4b253b8c5b"),
    23: (r"\(16\,\text{см}\)", None, "96f850ebd2e63c64"),
    24: (r"\(\approx9{,}5\%\)", None, "cd45a538f6b80a00"),
    25: (r"\(4{,}1\,\text{Тл}\), если направление поля не менялось; условие требует уточнения.", None, "f68227f8fa3e8910"),
    26: (r"\(4\,\text{кг}\)", 42292, "da6860456774df12"),
}
DIRECT_TEX = {19, 21, 22, 23, 24, 25, 26}
DIRECT_TEXT = set()
REPAIR_20_FROM = "от ЭДС источника"
REPAIR_20_TO = "от внешнего сопротивления"


def run(con: sqlite3.Connection, *, write: bool = False) -> dict[str, int]:
    counts = {"statement": 0, "answer": 0}
    for number, (raw, source_id, expected_hash) in KEYS.items():
        row = con.execute("""SELECT p.id,p.statement,p.answer,p.review_notes FROM problems p
            JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2025
            AND v.variant_number='БОТАЙ-ДОСРОК-1' AND p.problem_number=?
            AND p.alternative_number=1""", (number,)).fetchone()
        if not row:
            raise ValueError(f"Missing 2025 early task {number}")
        pid, statement, answer, notes = row
        fields = edited_fields(pid)
        if number == 20 and REPAIR_20_FROM in statement and "statement" not in fields:
            if hashlib.sha256(statement.encode()).hexdigest()[:16] != expected_hash:
                raise ValueError("Unexpected early task 20 statement")
            counts["statement"] += 1
            statement = statement.replace(REPAIR_20_FROM, REPAIR_20_TO)
            if write:
                con.execute("""UPDATE problems SET statement=?,
                    review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                    WHERE id=?""",
                    (statement, f" statement: PDF с. 8 содержит неверное «от ЭДС»; исправлено по таблице и {SOURCE}, карточка 42286. ", pid))
        elif hashlib.sha256(statement.encode()).hexdigest()[:16] != expected_hash and not (
                number == 20 and REPAIR_20_TO in statement):
            print(f"Skip 2025 early #{number}: condition changed")
            continue
        if number == 21 and answer == "Ускорение направлено внутрь траектории; на схеме — правее направления силы натяжения нити." and "answer" not in fields:
            if write:
                con.execute("UPDATE problems SET answer=? WHERE id=?", (raw, pid))
            continue
        if answer and answer.strip() or "answer" in fields:
            continue
        value = raw if number in DIRECT_TEX | DIRECT_TEXT else tex_answer(raw)
        counts["answer"] += 1
        if write:
            provenance = (f"опубликованный ключ {SOURCE}, карточка {source_id}" if source_id
                          else "расчёт ИИ по условию")
            note = f" answer: {provenance}; требуется проверка."
            if number == 25:
                note += " Не указано, сохраняется ли направление магнитного поля."
            con.execute("""UPDATE problems SET answer=?,
                review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                WHERE id=? AND (answer IS NULL OR trim(answer)='')""", (value, note, pid))
    return counts


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed 2025 early variant: {run(connection, write=True)}")

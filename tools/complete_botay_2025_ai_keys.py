"""Independently derived keys for 2025 real variants, pinned to source text.

All image-dependent values were read from the archived Botay images in the
respective variant directory. AI results stay needs_review until editorial QA.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from complete_botay_from_solutions import DB, tex_answer
from site_edit_guard import edited_fields

KEYS = {
    "БОТАЙ-ДВ-2": {5: "24", 6: "31", 10: "32", 19: "3,0±0,2"},
    "БОТАЙ-СЗ-4": {
        1: "193,75", 2: "2", 3: "135", 5: "45", 6: "33",
        11: "45", 13: "1", 15: "24", 20: "14",
        21: "113", 24: "17,8", 25: "4,704",
    },
    "БОТАЙ-СИБ-3": {6: "13", 9: "135"},
    "БОТАЙ-УРАЛ-5": {
        4: "3", 5: "14", 6: "31", 7: "200", 8: "250", 9: "134",
        10: "45", 11: "95", 12: "0,02", 14: "14", 15: "13",
        16: "0,025", 17: "13", 19: "0,46±0,02", 20: "12", 21: "21",
        22: "4,0\\cdot10^5", 24: "25", 25: "6,32",
    },
    "БОТАЙ-ЦЕНТР-6": {
        1: "35", 4: "0,005", 5: "34", 6: "11", 7: "2", 8: "5",
        9: "35", 10: "23", 11: "120", 12: "24", 13: "0,4",
        14: "15", 15: "13", 16: "76", 17: "23", 19: "36±2", 20: "13",
        21: "По наклонной плоскости: \\(h=v_0^2/(2g)\\) больше высоты свободного полёта \\(v_0^2\\sin^2\\alpha/(2g)\\).",
        22: "0,019",
    },
}

STATEMENT_SHA = json.loads(
    Path(__file__).with_name("botay_2025_ai_keys_sha.json").read_text(encoding="utf-8")
)


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    count = 0
    for variant, entries in KEYS.items():
        for number, raw in entries.items():
            row = con.execute("""SELECT p.id,p.statement,p.answer FROM problems p
                JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2025
                AND v.variant_number=? AND p.problem_number=? AND p.alternative_number=1""",
                (variant, number)).fetchone()
            if not row:
                raise ValueError(f"Missing {variant} №{number}")
            pid, statement, current = row
            if hashlib.sha256(statement.encode()).hexdigest()[:16] != STATEMENT_SHA[f"{variant}|{number}"]:
                print(f"Skip changed {variant} №{number}")
                continue
            if number >= 21 and current == raw and raw[0].isdigit() and "answer" not in edited_fields(pid):
                if write:
                    con.execute("UPDATE problems SET answer=? WHERE id=?", (tex_answer(raw), pid))
                continue
            if current and current.strip() or "answer" in edited_fields(pid):
                continue
            value = raw if number >= 21 and not raw[0].isdigit() else tex_answer(raw)
            count += 1
            if write:
                note = (" answer: расчёт ИИ по исходному условию и рисунку Botay; "
                        "требуется независимая проверка.")
                con.execute("""UPDATE problems SET answer=?,
                    review_notes=COALESCE(review_notes,'') || ?, extraction_status='needs_review'
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""",
                    (value, note, pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed 2025 AI-calculated keys: {run(connection, write=True)}")

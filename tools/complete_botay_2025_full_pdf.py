"""Keys checked against the expanded Shkolkovo real-EGE 2025 worked PDF.

Page numbers are PDF page indices (one-based). These are published solutions,
not official answer keys. Text hashes pin each transfer to the archived Botay
condition. Visually dependent ambiguous items are deliberately omitted.
"""
from __future__ import annotations

import hashlib
import sqlite3

from complete_botay_from_solutions import DB, ROOT, tex_answer
from site_edit_guard import edited_fields

SOURCE = ROOT / "Материалы/ЕГЭ 2025 Botay/real_exam_2025_shkolkovo_full.pdf"
SOURCE_SHA256 = "4e1e50a45476d291690ad6344ccea33ad42a4ad85766e3ac45aa48746f918a80"
SOURCE_URL = "https://onlyege.ru/wp-content/uploads/2025/06/Fizika_EGE-2025_ekzam_02.06.2025_ot_Shkolkovo_zadachi_s_reshen.pdf"

# Variant, task -> raw key, source task ID, PDF page.
KEYS = {
    "БОТАЙ-СЗ-4": {
        4: ("0,5", 125796, 22), 9: ("34", 117354, 50),
        10: ("13", 92300, 55), 14: ("245", 103150, 74),
        16: ("10", 91784, 87), 17: ("23", 117357, 94),
        18: ("134", 125798, 101), 19: ("755±3", 117345, 106),
        22: ("20,8", 14563, 131), 26: ("7,5", 63736, 178),
    },
    "БОТАЙ-СИБ-3": {
        2: ("0,4", 102933, 9), 3: ("112", 102713, 16),
        4: ("0,11", 13023, 23), 8: ("0,33", 11244, 45),
        10: ("23", 65090, 53), 12: ("0,8", 109858, 62),
        14: ("23", 96097, 72), 16: ("5", 91697, 86),
        17: ("23", 95173, 92), 19: ("745±1", 64808, 105),
    },
    "БОТАЙ-УРАЛ-5": {
        1: ("100", 16643, 6), 2: ("400", 104118, 11),
        3: ("10", 96662, 18), 13: ("70", 85586, 67),
        18: ("145", 112820, 99), 23: ("2", 107932, 144),
        26: ("0,37", 125801, 180),
    },
    "БОТАЙ-ЦЕНТР-6": {
        2: ("2", 103391, 12), 18: ("135", 125799, 102),
        23: ("2", 19856, 145), 24: ("1,5", 88700, 154),
        25: ("0,1", 125807, 166), 26: ("1", 98798, 185),
    },
}

# Generated from the source statement text at verification time.
STATEMENT_SHA = {
    ('БОТАЙ-СЗ-4', 4): '88da64d6186219f6',
    ('БОТАЙ-СЗ-4', 9): 'f736bf2daee87733',
    ('БОТАЙ-СЗ-4', 10): 'a26fe1da0d9f90d5',
    ('БОТАЙ-СЗ-4', 14): '6d8e04e93030eda3',
    ('БОТАЙ-СЗ-4', 16): '786a992fd20019bd',
    ('БОТАЙ-СЗ-4', 17): '0a8dd2fa83996c92',
    ('БОТАЙ-СЗ-4', 18): 'c28a1abb56bad1a1',
    ('БОТАЙ-СЗ-4', 19): '0bf3d1ee974ee806',
    ('БОТАЙ-СЗ-4', 22): '6dda31abd371ebff',
    ('БОТАЙ-СЗ-4', 26): 'b83b2e9ceac72284',
    ('БОТАЙ-СИБ-3', 2): '66968096d9d1f264',
    ('БОТАЙ-СИБ-3', 3): 'ded97d7103daf229',
    ('БОТАЙ-СИБ-3', 4): 'c96b4d012fd29f13',
    ('БОТАЙ-СИБ-3', 8): 'ec45d9b0c362eaf4',
    ('БОТАЙ-СИБ-3', 10): '3358ef0bb5f4a4db',
    ('БОТАЙ-СИБ-3', 12): '40aa8d8dae265dfc',
    ('БОТАЙ-СИБ-3', 14): '3e01822da5ac5b7c',
    ('БОТАЙ-СИБ-3', 16): 'f6e7aea22244847e',
    ('БОТАЙ-СИБ-3', 17): '8aa91cae68b5a5c2',
    ('БОТАЙ-СИБ-3', 19): '4cea6d6b62c12544',
    ('БОТАЙ-УРАЛ-5', 1): '0bf9e7910b7d3bdd',
    ('БОТАЙ-УРАЛ-5', 2): '3353b2c7e4181850',
    ('БОТАЙ-УРАЛ-5', 3): 'b1b2b407959b2539',
    ('БОТАЙ-УРАЛ-5', 13): '97b8b2ebd356174a',
    ('БОТАЙ-УРАЛ-5', 18): '61241b6225877356',
    ('БОТАЙ-УРАЛ-5', 23): '826e12b53cbdb544',
    ('БОТАЙ-УРАЛ-5', 26): '1e8f7b4856526e82',
    ('БОТАЙ-ЦЕНТР-6', 2): '797a7228ef7e141c',
    ('БОТАЙ-ЦЕНТР-6', 18): '981c4f4ac57f2933',
    ('БОТАЙ-ЦЕНТР-6', 23): 'f4b5320e82ad99be',
    ('БОТАЙ-ЦЕНТР-6', 24): '31fc18306cd9987f',
    ('БОТАЙ-ЦЕНТР-6', 25): '82842697bf990847',
    ('БОТАЙ-ЦЕНТР-6', 26): '23fccadf9e3f160a',
}


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Published 2025 PDF checksum changed")
    count = 0
    for variant, entries in KEYS.items():
        for number, (raw, source_id, page) in entries.items():
            row = con.execute("""SELECT p.id,p.statement,p.answer FROM problems p
                JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2025
                AND v.variant_number=? AND p.problem_number=? AND p.alternative_number=1""",
                (variant, number)).fetchone()
            if not row:
                raise ValueError(f"Missing {variant} №{number}")
            pid, statement, current = row
            if hashlib.sha256(statement.encode()).hexdigest()[:16] != STATEMENT_SHA[(variant, number)]:
                print(f"Skip changed {variant} №{number}")
                continue
            if current and current.strip() or "answer" in edited_fields(pid):
                continue
            count += 1
            if write:
                note = (f" answer: опубликованный разбор {SOURCE_URL}, PDF с. {page}, "
                        f"задача #{source_id}; требуется независимая сверка.")
                con.execute("""UPDATE problems SET answer=?,
                    review_notes=COALESCE(review_notes,'') || ?, extraction_status='needs_review'
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""",
                    (tex_answer(raw), note, pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed expanded 2025 PDF keys: {run(connection, write=True)}")

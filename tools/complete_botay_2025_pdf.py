"""Published short keys from the 2025 Shkolkovo real-exam worked PDF.

Every tuple is (answer, source task ID, statement SHA-256 prefix). The PDF
contains parallel tasks for several regions; hashes prevent cross-variant
answer transfer after an editor changes a condition.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from complete_botay_from_solutions import DB, ROOT, tex_answer
from site_edit_guard import edited_fields

SOURCE = ROOT / "Материалы/ЕГЭ 2025 Botay/real_exam_2025_shkolkovo_solutions.pdf"
SOURCE_SHA256 = "b21ee750a52f10dbf41eb30f5abc69bf527b6777793b59aee77afef1fa4db5fb"
SOURCE_URL = "https://100ballnik.com/wp-content/uploads/2025/06/variant-ege-fizika-2-2025.pdf"

KEYS = {
    "БОТАЙ-ДВ-1": {
        1: ("-1,5", 125782, "e556181c79ea8b54"),
        2: ("150", 121604, "b9e9e0ed5fc7d94d"),
        3: ("18", 121636, "09fcb31f5f0de39d"),
        4: ("0,1", 13007, "3b5464f3d098eb0b"),
        5: ("235", 65084, "911b7a967e44379d"),
        6: ("23", 117362, "3ead6864e8959ca9"),
        7: ("2", 121855, "2739ae65a9f35f8d"),
        8: ("2,5", 91984, "aef03be9864130b4"),
        9: ("14", 125792, "8cb4764401ffe296"),
        10: ("22", 125786, "2271f4fbcc62449f"),
        11: ("180", 96671, "a736baf7eed53c1b"),
        12: ("4", 12767, "482ad9ad17bf2f9e"),
        13: ("70", 92301, "ff4cee98e453a282"),
        14: ("25", 11968, "938932c71dda2ff3"),
        15: ("13", 121878, "ac0e7b6f48ef6168"),
        16: ("8", 125780, "3469bbbe5e39de8a"),
        17: ("31", 117335, "bb41fd25a84f8d52"),
        18: ("35", 125793, "5db6c0ff74af60d8"),
        19: ("0,500±0,025", 125772, "cb2d519bc5beed3d"),
        20: ("13", 125788, "a97fa93dd029586b"),
    },
    "БОТАЙ-ДВ-2": {
        1: ("0,5", 125783, "3558a6989b560042"),
        2: ("2", 125762, "79e2669d7bcb3f85"),
        3: ("100", 125763, "8817c7161328d088"),
        4: ("3,2", 125764, "d5f7bef56807d974"),
        7: ("800", 11091, "c70f7b3249d06869"),
        8: ("200", 103121, "a490d97f73396b02"),
        9: ("35", 125784, "b273ecac16c4ad04"),
        11: ("20", 96717, "39c4aa9d328ae8b7"),
        12: ("2", 12768, "8d9e71e5f440d328"),
        13: ("68", 125767, "0577d221d1e8fb17"),
        14: ("245", 16870, "198c90dac6f88e8b"),
        15: ("23", 14144, "73c5877f6df8197e"),
        16: ("4", 121879, "5a1475423915caca"),
        17: ("14", 103375, "4cb2e2bdd6154ecb"),
        18: ("134", 125641, "93b094dda6ba0571"),
        20: ("13", 84087, "0df0287e7aff836d"),
    },
    "БОТАЙ-СИБ-3": {
        1: ("131,25", 113639, "d4c8af2b001d489a"),
        5: ("35", 13395, "24005b79ddf75652"),
        7: ("4", 96917, "eb53cb57377c859e"),
        11: ("100", 102055, "fd7cf8297e8f0aac"),
        13: ("90", 84072, "bca22c5ea5e6968e"),
        15: ("13", 103373, "73de4c3bfbbdd64f"),
        18: ("134", 65310, "fd563d3143289b4e"),
        20: ("25", 96876, "1fa32c41d7b90a49"),
    },
}

# Final results from the same worked PDF. Three changed numerical conditions
# require independent calculations and are explicitly marked as AI results.
LONG_KEYS = {
    "БОТАЙ-ДВ-1": {
        21: (r"\(21\)", 117346, "192e864b6df4a79a", False),
        22: (r"\(\approx0{,}17\,\text{м}/\text{с}\)", 14398, "8bc14d24dde32f82", False),
        23: (r"\(N_2/N_1=1\)", 119383, "3018a04101bb1f9c", False),
        24: (r"\(\approx9{,}5\%\)", 14593, "adb02633cf30c968", False),
        25: (r"\(\approx0{,}048\,\text{Тл}\)", None, "31422a9bdd6a982e", True),
        26: (r"\(\approx0{,}16\,\text{кг}\)", 102188, "0364094c343c2bf9", False),
    },
    "БОТАЙ-ДВ-2": {
        21: (r"\(2\)", 49121, "3548d2842e7e7e86", False),
        22: (r"\(0{,}6\,\text{м}/\text{с}\)", 125769, "6868ceef7c8fd951", False),
        23: (r"\(N_2/N_1=2/3\)", 125781, "04844390a05c57dc", False),
        24: (r"\(\approx9\%\)", 125787, "ad02397d7b155a30", True),
        25: (r"\(0{,}2\,\text{Тл}\)", 125770, "6069402c206b95e2", False),
        26: (r"\(0{,}16\,\text{кг}\)", 125771, "3190cf54b77d151e", False),
    },
    "БОТАЙ-СИБ-3": {
        21: (r"\(21\)", 125790, "752798045901289b", False),
        22: (r"\(1{,}5\,\text{м}/\text{с}\)", 102956, "32c5ffc222595833", False),
        23: (r"\(10^5\,\text{Па}\)", 125789, "e8e34ccb24518dd9", False),
        24: (r"\(9\,\text{Дж}\)", 125791, "ac7f7c784f031d30", False),
        25: (r"\(\approx0{,}28\,\text{Н}\)", None, "6cdc1cd6b821fd38", True),
        26: (r"\(\approx68{,}3\,\text{см}\)", 18430, "94ce7be1c9dcbb93", False),
    },
}


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The 2025 published source PDF has changed")
    count = 0
    for variant, entries in KEYS.items():
        for number, (raw, source_id, expected_hash) in entries.items():
            row = con.execute("""SELECT p.id,p.statement,p.answer,p.review_notes FROM problems p
                JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2025
                AND v.variant_number=? AND p.problem_number=? AND p.alternative_number=1""",
                (variant, number)).fetchone()
            if not row:
                raise ValueError(f"Missing task {variant} #{number}")
            pid, statement, current, notes = row
            if hashlib.sha256(statement.encode()).hexdigest()[:16] != expected_hash:
                print(f"Skip {variant} №{number}: condition has changed")
                continue
            if "answer" in edited_fields(pid) or current and current.strip():
                continue
            count += 1
            if write:
                note = (f" answer: опубликованный разбор {SOURCE_URL}, задание #{source_id}; "
                        "требуется независимая сверка с исходником.")
                con.execute("""UPDATE problems SET answer=?,
                    review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""",
                    (tex_answer(raw), note, pid))
    for variant, entries in LONG_KEYS.items():
        for number, (value, source_id, expected_hash, ai) in entries.items():
            row = con.execute("""SELECT p.id,p.statement,p.answer,p.review_notes FROM problems p
                JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2025
                AND v.variant_number=? AND p.problem_number=? AND p.alternative_number=1""",
                (variant, number)).fetchone()
            if not row:
                raise ValueError(f"Missing task {variant} #{number}")
            pid, statement, current, notes = row
            digest = hashlib.sha256(statement.encode()).hexdigest()[:16]
            if digest != expected_hash and not (
                    variant == "БОТАЙ-ДВ-1" and number == 26 and digest == "fb3f6261d4c63222"):
                print(f"Skip {variant} №{number}: condition has changed")
                continue
            owned = ("answer: опубликованный разбор " + SOURCE_URL in (notes or "") or
                     "answer: расчёт ИИ по условию" in (notes or ""))
            if "answer" in edited_fields(pid) or current == value or current and not owned:
                continue
            count += 1
            if write:
                if owned:
                    con.execute("UPDATE problems SET answer=? WHERE id=?", (value, pid))
                    continue
                provenance = ("расчёт ИИ по условию" if ai else
                              f"опубликованный разбор {SOURCE_URL}, задание #{source_id}")
                con.execute("""UPDATE problems SET answer=?,
                    review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""",
                    (value, f" answer: {provenance}; требуется проверка.", pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed 2025 published short keys: {run(connection, write=True)}")

"""Restore exact published answer keys from matched Решу ЕГЭ task cards.

Each match was checked against the Botay condition in its original order.
Statement hashes prevent replaying a stale key after a site-editor change.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from complete_botay_from_solutions import tex_answer


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
# (raw key, first 16 hex digits of condition SHA-256, Решу ЕГЭ problem id)
KEYS = {
    (2024, "БОТАЙ-ОТКРЫТ-1"): (
        ("-0,5", "8a8f2b5163b5d3f1", 38183),
        ("9", "201f142b2b4c13c3", 38184),
        ("1", "e6c829881ae095ea", 38185),
        ("215", "fdaa9da321f82492", 38186),
        ("24", "3bf5c0d454d6e331", 38187),
        ("11", "c522f42d9736559c", 38188),
        ("80", "b374c294a694ff08", 38189),
        ("0,5", "8536a9f535de7429", 38190),
        ("124", "9e1889dc38e51d70", 38191),
        ("11", "c4ee3f54ae7ca09a", 38192),
        ("100", "5b5e3617c9eee41c", 38193),
        ("0,4", "c6890ab792b91a6a", 38194),
        ("12", "0f4003b3014c5fc4", 38195),
        ("25", "50cc2195d72e549d", 38196),
        ("32", "a3afaacf13e73652", 38197),
        ("82", "8c8c58c44b64f97b", 38198),
        ("31", "e6c99e261f4747fa", 38199),
        ("145", "fe6912be6b8100b4", 38200),
        ("3,8±0,2", "bfafaebb69945cc2", 38201),
        ("14", "679fe2664cca79a3", 38202),
    ),
    (2025, "БОТАЙ-ОТКРЫТ-1"): (
        ("-10", "3e88d3044a0abc7c", 42629),
        ("150", "b9e9e0ed5fc7d94d", 42630),
        ("18", "09fcb31f5f0de39d", 42631),
        ("4000", "9bd51bc990619abc", 42632),
        ("14", "665af1537a00be7f", 42633),
        ("22", "aadd0a5138c23e76", 42634),
        ("2", "2739ae65a9f35f8d", 42635),
        ("5", "497bc5a8e35dbca9", 42636),
        ("135", "01d9ea6f8dd459b4", 42637),
        ("32", "f473d64b282c2820", 42638),
        ("500", "bf11a90a0b2eda78", 42639),
        ("4", "fc11ee2d034f2298", 42640),
        ("1", "2f52a2f969b28153", 42641),
        ("15", "3cce3585e8e84e5f", 42642),
        ("13", "6fe43bedc4d998c4", 42643),
        ("4", "cf8561413128b1be", 42644),
        ("21", "09a07dfb0ee6798b", 42645),
        ("25", "e2987dd23fa65900", 42646),
        ("421", "4b2e0b35fa8dad29", 42647),
        ("24", "f3e3b4e225e8c745", 42648),
    ),
    (2026, "ОТКРЫТ-1"): (
        ("-16", "ffccbb90f6dbc8a4", 49621),
        ("250", "9ac835b9506a0e12", 49622),
        ("48", "42c7c932cdeaa7eb", 49623),
        ("0,01", "42811363c20daecb", 49624),
        ("124", "d43e1612664dc607", 49625),
        ("12", "6b4d7ab00a95df5e", 49626),
        ("3", "21282961786bc1ad", 49627),
        ("2200", "d8a432686a08dbe4", 49628),
        ("245", "9f9b9e553b0a704c", 49629),
        ("11", "1db9edcb31522fb9", 49630),
        ("3", "cd7d3a9c29cedd39", 49631),
        ("4", "596ac004162bc485", 49632),
        ("1", "ba00b5fce0ae1863", 49633),
        ("245", "175c7cbe4d5dde6d", 49634),
        ("31", "d4b2a0be4150ec70", 49635),
        ("0,2", "2f891e3a8682c2de", 49636),
        ("21", "636562dc23389fc9", 49637),
        ("35", "edd8a165a464e038", 49638),
        ("0,18±0,02", "a577d734ab5e7200", 49639),
        ("15", "54da3c0992353435", 49640),
    ),
}

# The first task of the second part is qualitative in both open variants.
LONG_KEYS = {
    (2025, "БОТАЙ-ОТКРЫТ-1"): (
        ("Ускорение шарика направлено внутрь траектории, между направлением к точке подвеса и касательной к положению равновесия.", "0677ea0b99eb1372", 42649),
        ("\\(0{,}0075\\)", "7d557593ec874af6", 42650),
        ("\\(8\\,\\text{см}\\)", "65b96973bef94707", 42651),
        ("\\(6\\%\\)", "eac123417ddd51d2", 42652),
        ("\\(8\\,\\text{мКл}\\)", "60d35667789aff20", 42653),
        ("\\(0{,}25\\)", "229fa5d1b6f8df2f", 42654),
    ),
    (2026, "ОТКРЫТ-1"): (
        ("Работа газа в процессе \\(2\\)–\\(3\\) больше работы внешних сил в процессе \\(3\\)–\\(1\\); в координатах \\(p\\)–\\(V\\) участки \\(1\\)–\\(2\\), \\(2\\)–\\(3\\), \\(3\\)–\\(1\\) являются соответственно изохорой, изотермой и изобарой.", "f975a61b8bf94441", 49641),
        ("\\(0{,}09\\,\\text{м}/\\text{с}\\)", "a4f441a4460ef03b", 49642),
        ("\\(5\\,\\text{А}\\)", "fca8b2b2e661ece2", 49643),
        ("\\(6{,}6\\,\\text{кПа}\\)", "d8699505372b34a0", 49644),
        ("\\(26{,}7\\,\\text{см}\\)", "97ccdabdaa29e317", 49645),
        ("\\(72\\,\\text{Н}/\\text{м}\\)", "d6f4976fe9213534", 49646),
    ),
}


def run(con: sqlite3.Connection, *, write: bool = False, year_filter: int | None = None) -> int:
    count = 0
    for (year, variant), keys in KEYS.items():
        if year_filter is not None and year != year_filter:
            continue
        rows = list(con.execute("""SELECT p.id,p.problem_number,p.statement,p.answer
            FROM problems p JOIN variants v ON p.variant_id=v.id
            WHERE v.exam_year=? AND v.variant_number=? AND p.alternative_number=1
            AND p.problem_number BETWEEN 1 AND ? ORDER BY p.problem_number""",
            (year, variant, len(keys))))
        if [r[1] for r in rows] != list(range(1, len(keys) + 1)):
            raise ValueError(f"Unexpected task set in {year}-{variant}")
        for pid, number, statement, current in rows:
            raw, expected_sha, source_id = keys[number - 1]
            if hashlib.sha256(statement.encode()).hexdigest()[:16] != expected_sha:
                print(f"Skip {year}-{variant} №{number}: condition has changed")
                continue
            if current:
                continue
            answer = tex_answer(raw)
            count += 1
            print(f"{year}-{variant} №{number}: {answer} (Решу ЕГЭ {source_id})")
            if write:
                source = f"https://phys-ege.sdamgia.ru/problem?id={source_id}"
                con.execute("""UPDATE problems SET answer=?,
                    review_notes=COALESCE(review_notes,'') || ?
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""",
                    (answer, f" Ответ опубликован: {source}; условие сверено.", pid))
    for (year, variant), keys in LONG_KEYS.items():
        if year_filter is not None and year != year_filter:
            continue
        rows = list(con.execute("""SELECT p.id,p.problem_number,p.statement,p.answer
            FROM problems p JOIN variants v ON p.variant_id=v.id
            WHERE v.exam_year=? AND v.variant_number=? AND p.alternative_number=1
            AND p.problem_number BETWEEN 21 AND 26 ORDER BY p.problem_number""",
            (year, variant)))
        if [r[1] for r in rows] != list(range(21, 27)):
            raise ValueError(f"Unexpected long task set in {year}-{variant}")
        for pid, number, statement, current in rows:
            answer, expected_sha, source_id = keys[number - 21]
            if hashlib.sha256(statement.encode()).hexdigest()[:16] != expected_sha:
                print(f"Skip {year}-{variant} №{number}: condition has changed")
                continue
            if current:
                continue
            count += 1
            print(f"{year}-{variant} №{number}: {answer} (Решу ЕГЭ {source_id})")
            if write:
                source = f"https://phys-ege.sdamgia.ru/problem?id={source_id}"
                con.execute("""UPDATE problems SET answer=?,
                    review_notes=COALESCE(review_notes,'') || ?
                    WHERE id=? AND (answer IS NULL OR trim(answer)='')""",
                    (answer, f" Ответ опубликован: {source}; условие сверено.", pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed matched keys: {run(connection, write=True)}")

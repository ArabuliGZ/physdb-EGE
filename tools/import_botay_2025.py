"""Import archived real, open, and early 2025 EGE papers from Botay.

Botay provides full keys and worked solutions only for the Centre 7 paper.
The remaining answer/solution fields stay empty; hints are not solutions.
All tables and text repairs below are reproduced on every import.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from lxml import html

from apply_site_text_edits import DEFAULT_LOG, apply_edits
from fetch_botay_2025 import DEST as ARCHIVE, SLUGS
from import_botay_2026 import parse_task
from import_examples import (
    DB, FORMATS, POINTS, ROOT, TOPICS, link_asset, store_asset,
    upsert_problem, upsert_variant,
)

VARIANTS = {
    "2025-osnov-11-7": ("БОТАЙ-ЦЕНТР-7", "ЕГЭ 2025 — Центр, вариант 7"),
    "2025-osnov-11-centr-6": ("БОТАЙ-ЦЕНТР-6", "ЕГЭ 2025 — Центр, вариант 6"),
    "2025-osnov-11-dv-1": ("БОТАЙ-ДВ-1", "ЕГЭ 2025 — Дальний Восток, вариант 1"),
    "2025-osnov-11-dv-2": ("БОТАЙ-ДВ-2", "ЕГЭ 2025 — Дальний Восток, вариант 2"),
    "2025-osnov-11-sib-3": ("БОТАЙ-СИБ-3", "ЕГЭ 2025 — Сибирь, вариант 3"),
    "2025-osnov-11-sz-4": ("БОТАЙ-СЗ-4", "ЕГЭ 2025 — Северо-Запад, вариант 4"),
    "2025-osnov-11-ural-5": ("БОТАЙ-УРАЛ-5", "ЕГЭ 2025 — Урал, вариант 5"),
    "2025-otkryt-11-1": ("БОТАЙ-ОТКРЫТ-1", "ЕГЭ 2025 — открытый вариант"),
    "2025-dosrok-11-1": ("БОТАЙ-ДОСРОК-1", "ЕГЭ 2025 — досрочный вариант"),
}


def verify_archive() -> None:
    manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
    for relative, record in manifest.items():
        path = ARCHIVE / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Archived source changed: {relative}")


def cell(value: str) -> str:
    if re.fullmatch(r"-?\d+(?:,\d+)?", value):
        return r"\(" + value.replace(",", "{,}") + r"\)"
    return value


def table(rows: list[list[str]]) -> str:
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("Uneven table row")
    lines = [r"\begin{tabular}{" + "|l" + "|c" * (width - 1) + "|}", r"\hline"]
    for row in rows:
        lines.extend([" & ".join(cell(value) for value in row) + r"\\", r"\hline"])
    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def replace_once(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f"Table/text source pattern not found: {pattern}")
    return updated


def restore_tables(text: str, slug: str, number: int) -> str:
    key = (slug, number)
    if key == ("2025-osnov-11-centr-6", 7):
        rows = [
            ["Состояние", r"\(p,\ 10^5\,\text{Па}\)", r"\(V,\ 10^{-3}\,\text{м}^3\)", r"\(T,\ \text{К}\)"],
            ["A", "0,5", "6", "1200"], ["B", "1,0", "?", "800"],
        ]
        return replace_once(text, r"\n\n1\) Состояние A:.*", "\n\n" + table(rows))
    if key == ("2025-osnov-11-sib-3", 7):
        rows = [
            ["Состояние", r"\(p,\ 10^5\,\text{Па}\)", r"\(V,\ 10^{-3}\,\text{м}^3\)", r"\(T,\ \text{К}\)"],
            ["A", "1,0", "4", "300"], ["B", "?", "2", "600"],
        ]
        return replace_once(text, r"\n\nСостояние \\\(A\\\):.*", "\n\n" + table(rows))
    if key in (("2025-osnov-11-dv-1", 5), ("2025-osnov-11-ural-5", 5)):
        rows = [
            [r"Время \(t\), \(\text{с}\)", *map(str, range(7))],
            [r"Скорость \(v\), \(\text{м}/\text{с}\)", "0", "0,5", "1,0", "1,5", "2,0", "2,5", "3,0"],
        ]
        if number == 5 and slug.endswith("dv-1"):
            return replace_once(text, r"Время \\\(t\\\), с:.*?Выберите все верные",
                                table(rows) + "\n\nВыберите все верные")
        return replace_once(text, r"Зависимость скорости бруска от времени приведена в таблице\.",
                            "Зависимость скорости бруска от времени приведена в таблице.\n\n" + table(rows))
    if key in (("2025-osnov-11-dv-1", 14), ("2025-osnov-11-ural-5", 14)):
        values = (["4", "2", "0", "-2", "-4", "-2", "0", "2", "4", "2"] if slug.endswith("dv-1")
                  else ["2", "1,41", "0", "-1,41", "-2", "-1,41", "0", "1,41", "2", "1,41"])
        scale = r"\(\text{нКл}\)" if slug.endswith("dv-1") else r"\(10^{-9}\,\text{Кл}\)"
        rows = [[r"Время \(t\), \(\text{мкс}\)", *map(str, range(10))],
                [r"Заряд \(q\), " + scale, *values]]
        if slug.endswith("dv-1"):
            return replace_once(text, r"Время \\\(t\\\), мкс:.*?Выберите все верные",
                                table(rows) + "\n\nВыберите все верные")
        return replace_once(text, r"Выберите все верные утверждения о данной ситуации и укажите их номера\.",
                            "Выберите все верные утверждения о данной ситуации и укажите их номера.\n\n" + table(rows))
    if key == ("2025-osnov-11-dv-2", 14):
        rows = [[r"Время \(t\), \(\text{мкс}\)", *map(str, range(10))],
                [r"Сила тока \(I\), \(\text{А}\)", "0,0", "2,2", "3,0", "2,2", "0,0", "-2,2", "-3,0", "-2,2", "0,0", "2,2"]]
        return replace_once(text, r"\\\(t\\\), мкс:.*?(?=\n\n1\))", table(rows))
    if key == ("2025-osnov-11-dv-1", 20):
        rows = [["№ сосуда", r"Объём, \(\text{л}\)", r"Температура, \(\text{К}\)", "Газ"],
                ["1", "6", "320", "аргон"], ["2", "5", "350", "неон"],
                ["3", "4", "320", "аргон"], ["4", "4", "270", "аргон"], ["5", "4", "300", "неон"]]
        return replace_once(text, r"Таблица:.*", table(rows))
    if key == ("2025-osnov-11-sib-3", 20):
        rows = [["№ проводника", r"Длина, \(\text{м}\)", r"Диаметр, \(\text{мм}\)", "Материал"],
                ["1", "65", "1,0", "медь"], ["2", "10", "0,5", "медь"],
                ["3", "20", "1,0", "алюминий"], ["4", "10", "0,5", "алюминий"],
                ["5", "10", "1,0", "медь"]]
        return replace_once(text, r"Таблица \(номер проводника.*", table(rows))
    if key == ("2025-osnov-11-sz-4", 5):
        times = ["0,0", "0,2", "0,4", "0,6", "0,8", "1,0", "1,2", "1,4", "1,6",
                 "1,8", "2,0", "2,2", "2,4", "2,6", "2,8", "3,0", "3,2"]
        positions = ["0", "5", "9", "12", "14", "15", "14", "12", "9",
                     "5", "0", "-5", "-9", "-12", "-14", "-15", "-14"]
        parts = []
        for start, end in ((0, 9), (9, 17)):
            parts.append(table([[r"Время \(t\), \(\text{с}\)", *times[start:end]],
                                [r"Координата \(x\), \(\text{мм}\)", *positions[start:end]]]))
        return replace_once(text, r"Таблица \(время.*?(?=\n\n1\))", "\n\n".join(parts) + "\n\n")
    if key == ("2025-osnov-11-sz-4", 20):
        rows = [["№ сосуда", r"Давление, \(\text{кПа}\)", r"Температура, \({}^\circ\text{C}\)", r"Масса, \(\text{г}\)"],
                ["1", "150", "50", "10"], ["2", "200", "50", "15"],
                ["3", "150", "20", "15"], ["4", "150", "20", "10"], ["5", "200", "20", "10"]]
        return replace_once(text, r"Таблица \(№ сосуда.*", table(rows))
    if key == ("2025-osnov-11-ural-5", 20):
        rows = [["№ сосуда", "1", "2", "3", "4", "5"],
                [r"Давление, \(\text{кПа}\)", "60", "60", "80", "90", "100"],
                [r"Температура, \({}^\circ\text{C}\)", "80", "100", "60", "80", "60"],
                [r"Масса газа, \(\text{г}\)", "10", "10", "5", "15", "5"]]
        return text.rstrip() + "\n\n" + table(rows)
    if key in (("2025-otkryt-11-1", 20), ("2025-dosrok-11-1", 20)):
        values = ([
            ["1", "6", "1,0", "5"], ["2", "9", "0,5", "8"],
            ["3", "8", "1,5", "16"], ["4", "9", "1,5", "8"],
            ["5", "6", "0,5", "16"],
        ] if slug.startswith("2025-otkryt") else [
            ["1", "9", "1", "5"], ["2", "6", "2", "10"],
            ["3", "12", "2", "15"], ["4", "6", "1", "10"],
            ["5", "9", "1", "15"],
        ])
        rows = [["№ цепи", r"ЭДС источника \(\mathcal{E}\), \(\text{В}\)",
                 r"Внутреннее сопротивление \(r\), \(\text{Ом}\)",
                 r"Внешнее сопротивление \(R\), \(\text{Ом}\)"], *values]
        marker = "\n\nЗапишите в ответе номера выбранных цепей."
        if marker in text:
            return text.replace(marker, "\n\n" + table(rows) + marker, 1)
        return text.rstrip() + "\n\n" + table(rows)
    return text


def repair_task(data: dict, slug: str, number: int) -> dict:
    text = restore_tables(data["statement"], slug, number)
    text = re.sub(r"\n\nИсточник:.*$", "", text, flags=re.S)
    # Source uses both split math runs and plain-text Cyrillic suffixes.
    text = re.sub(r"\\\(([^)]*?)\\,\\\)°([СC])", r"\\(\1\\,\\text{°\2}\\)", text)
    text = re.sub(r"\\\(([^)]*?)\\\)°", r"\\(\1{}^\\circ\\)", text)
    text = re.sub(r"\\\(([A-Za-z]+)\\,\\text\{с\}\\\)", r"\\(\1\\) с", text)
    if slug == "2025-osnov-11-7" and number == 15:
        text = text.replace("Физические величины: А) показания амперметра; Б) показания вольтметра.",
                            "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ\nА) показания амперметра\nБ) показания вольтметра")
    if slug == "2025-osnov-11-ural-5" and number == 10:
        text = re.sub(r"\n\nОтвет [12]: \\\(\\underline\{[^}]*\}\\\)", "", text)
        data["answer_table_labels"] = []
    if slug == "2025-osnov-11-ural-5" and number == 22:
        # Botay dropped the exponent; the identical statement prints 2·10^5 Pa
        # in https://onlyege.ru/wp-content/uploads/2026/06/e6-fi-var1-20.pdf .
        text = text.replace(r"\(2\cdot10\,\text{Па}\)", r"\(2\cdot10^5\,\text{Па}\)")
    if slug == "2025-osnov-11-sib-3" and number == 23:
        text = text.replace(r"\(1{,}2\) кг/м\(^3\)", r"\(1{,}2\,\text{кг}/\text{м}^3\)")
    if slug == "2025-osnov-11-sib-3" and number == 25:
        text = text.replace(r"\(KLMN\,\text{с}\)", r"\(KLMN\) с")
    if slug == "2025-osnov-11-sib-3" and number == 26:
        text = text.replace(r"\(AB\,\text{с}\)", r"\(AB\) с")
    if slug == "2025-osnov-11-ural-5" and number == 6:
        text = text.replace(r"\(H\,\text{с}\)", r"\(H\) с")
    if slug == "2025-osnov-11-dv-1" and number == 24:
        text = text.replace(r"C\(_6\)H\(_6\)", r"\(\mathrm{C}_6\mathrm{H}_6\)")
        text = text.replace(r"\(t = 80\,^{\circ}\)C", r"\(t=80{}^\circ\text{C}\)")
    if slug == "2025-osnov-11-sib-3" and number == 2:
        text = text.replace(r"F_{тр}", r"F_{\text{тр}}")
    if slug == "2025-osnov-11-centr-6" and number == 7:
        data["answer_unit"] = r"\(\cdot10^{-3}\,\text{м}^3\)"
    if slug == "2025-osnov-11-sib-3" and number == 7:
        data["answer_unit"] = r"\(\cdot10^5\,\text{Па}\)"
    if slug == "2025-osnov-11-ural-5" and number == 10:
        data["answer_unit"] = ""
    if slug == "2025-osnov-11-7" and number in (21, 26) and data["solution"]:
        data["solution"] = (data["solution"]
            .replace(r"F_{арх}", r"F_{\text{арх}}")
            .replace(r"F_{у1}", r"F_{\text{у}1}")
            .replace(r"F_{у2}", r"F_{\text{у}2}")
            .replace(r"F_{тр1}", r"F_{\text{тр}1}")
            .replace(r"F_{тр2}", r"F_{\text{тр}2}"))
    if slug == "2025-otkryt-11-1":
        if number == 6:
            data["answer_table_labels"] = ["Частота колебаний груза", "Максимальная скорость груза"]
        elif number == 10:
            data["answer_table_labels"] = ["Давление газа", "Внутренняя энергия газа"]
        elif number == 15:
            data["answer_table_labels"] = ["Модуль ускорения иона", "Период обращения иона"]
        elif number == 16:
            text = text.replace(r"\(^{200}_{79}\)Au", r"\({}^{200}_{79}\mathrm{Au}\)")
        elif number == 13:
            text = text.replace(r"(\(1\), \(2\), \(3\) или  4)", r"(\(1\), \(2\), \(3\) или \(4\))")
        elif number == 22:
            text = text.replace(r"\(16\,{}^\circ\)C", r"\(16{}^\circ\text{C}\)")
    if slug == "2025-dosrok-11-1" and number == 6:
        data["answer_table_labels"] = ["Жёсткость пружины", "Скорость груза"]
    if slug == "2025-dosrok-11-1" and number == 22:
        text = text.replace(r"\(20\) \(^\circ\)C", r"\(20{}^\circ\text{C}\)")
    if slug in ("2025-otkryt-11-1", "2025-dosrok-11-1") and number == 21:
        text = text.replace(r"^\circ\,\text{с}\)", r"^\circ\) с")
    data["statement"] = text
    return data


def assessment(slug: str, number: int) -> tuple[str, int, int, str]:
    """Return verdict, topic_match, format_match, reason for same-number 2027 line."""
    if number == 7 and slug != "2025-osnov-11-dv-2":
        return "no", 0, 1, "Газовый закон/давление вместо связи температуры со средней кинетической энергией в позиции 7."
    if number == 10 and slug == "2025-osnov-11-ural-5":
        return "no", 1, 0, "Здесь множественный выбор; позиция 10 КИМ 2027 — соответствие двух величин."
    if number == 21 and slug not in {"2025-osnov-11-dv-1", "2025-osnov-11-dv-2", "2025-osnov-11-sib-3"}:
        return "no", 0, 1, "Качественная задача по механике; позиция 21 КИМ 2027 — электродинамика."
    if number == 22:
        if slug in {"2025-osnov-11-dv-1", "2025-osnov-11-dv-2"}:
            return "partial", 1, 1, "Механический расчёт совпадает по формату и баллам; практическая направленность выражена слабо."
        if slug == "2025-osnov-11-sib-3":
            return "yes", 1, 1, "Практический сюжет с тележкой, расчёт по законам механики, 2 балла."
        return "no", 0, 1, "Расчёт по молекулярной физике; позиция 22 КИМ 2027 — практическая механика."
    if number == 23 and slug not in {"2025-osnov-11-dv-1", "2025-osnov-11-dv-2", "2025-osnov-11-sib-3"}:
        return "no", 0, 1, "Расчёт по оптике; позиция 23 КИМ 2027 — молекулярная физика."
    return "yes", 1, 1, "Тема, формат ответа и баллы соответствуют позиции КИМ 2027."


def source_topic(slug: str, number: int) -> str:
    if number == 21:
        return "electrodynamics" if slug in {"2025-osnov-11-dv-1", "2025-osnov-11-dv-2", "2025-osnov-11-sib-3"} else "mechanics"
    if number == 22:
        return "mechanics" if slug in {"2025-osnov-11-dv-1", "2025-osnov-11-dv-2", "2025-osnov-11-sib-3"} else "molecular"
    if number == 23:
        return "molecular" if slug in {"2025-osnov-11-dv-1", "2025-osnov-11-dv-2", "2025-osnov-11-sib-3"} else "electrodynamics"
    return TOPICS[number]


def add_relevance(con: sqlite3.Connection, pid: str, target: int, verdict: str,
                  topic_match: int, format_match: int, reason: str) -> None:
    con.execute(
        """INSERT INTO relevance
           (problem_id,exam_year,target_problem_number,topic_match,format_match,verdict,reason)
           VALUES (?,2027,?,?,?,?,?)""",
        (pid, target, topic_match, format_match, verdict, reason),
    )


def import_variant(con: sqlite3.Connection, slug: str) -> None:
    directory = ARCHIVE / slug
    page = html.fromstring((directory / "page.html").read_bytes())
    tasks = {
        int(task.get("id")[1:]): repair_task(parse_task(task, int(task.get("id")[1:]), slug), slug, int(task.get("id")[1:]))
        for task in page.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' o-zad ')]")
    }
    if set(tasks) != set(range(1, 27)):
        raise ValueError(f"{slug}: expected 26 unique tasks")
    number, title = VARIANTS[slug]
    variant_id = upsert_variant(con, directory / "usloviya.pdf", 2025, number, title, False)
    for n, data in tasks.items():
        locator = f"https://botay.pro/olimpiady/ege/{slug}/#z{n}; "
        locator += (directory / "usloviya.pdf").relative_to(ROOT).as_posix()
        notes = "Условие и рисунки — из сохранённой страницы Botay; PDF сохранён. Требуется визуальная сверка."
        if data["answer"] is None:
            notes += " Авторский ключ в доступном источнике отсутствует."
        if n >= 21 and data["solution"] is None:
            notes += " Развёрнутое решение отсутствует; подсказку за него не выдаём."
        if slug == "2025-osnov-11-ural-5" and n == 22:
            notes += " Показатель 10^5 восстановлен по идентичному условию: https://onlyege.ru/wp-content/uploads/2026/06/e6-fi-var1-20.pdf ."
        if slug == "2025-osnov-11-dv-2" and n == 17:
            notes += " В исходнике противоречат друг другу описания требуемых переходов; оставлен авторский текст."
        pid = upsert_problem(
            con, variant_id, n, 1, data["statement"], data["answer"], data["solution"], None,
            source_topic(slug, n), locator, notes, status="needs_review", max_points=POINTS[n],
            answer_format="multiple_choice" if slug == "2025-osnov-11-ural-5" and n == 10 else FORMATS[n],
        )
        con.execute(
            "UPDATE problems SET answer_prefix=?,answer_unit=?,answer_table_labels=? WHERE id=?",
            (data["answer_prefix"] or None, data["answer_unit"] or None,
             json.dumps(data["answer_table_labels"], ensure_ascii=False) if data["answer_table_labels"] else None, pid),
        )
        for src in data["figures"]:
            path = directory / "images" / Path(src).name
            aid = store_asset(con, path.read_bytes(), ".png", "image/png")
            source_table = (
                (slug == "2025-osnov-11-ural-5" and n in (5, 14, 20))
                or (slug == "2025-otkryt-11-1" and src.endswith("-tablica.png"))
                or (slug == "2025-dosrok-11-1" and src.endswith("20-tablica.png"))
            )
            # The schema's source_page role retains source-only imagery without
            # rendering it a second time next to the transcribed table/field.
            role = "source_page" if source_table else "statement_figure"
            link_asset(con, pid, aid, role, f"{locator}; {src}")
        con.execute("DELETE FROM relevance WHERE problem_id=? AND exam_year=2027", (pid,))
        verdict, topic_match, format_match, reason = assessment(slug, n)
        add_relevance(con, pid, n, verdict, topic_match, format_match, reason)
        if n == 22 and slug in {"2025-osnov-11-7", "2025-osnov-11-centr-6", "2025-osnov-11-sz-4", "2025-osnov-11-ural-5"}:
            add_relevance(con, pid, 23, "yes", 1, 1,
                          "Задача №22 исходника — расчёт по молекулярной физике на 2 балла; соответствует позиции 23 КИМ 2027.")
    print(f"{slug}: 26 tasks, {sum(bool(x['answer']) for x in tasks.values())} keys, "
          f"{sum(bool(x['solution']) for x in tasks.values())} worked solutions, "
          f"{sum(len(x['figures']) for x in tasks.values())} source images", flush=True)


def main() -> None:
    verify_archive()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        with con:
            for slug in SLUGS:
                import_variant(con, slug)
    finally:
        con.close()
    print(f"Replayed {apply_edits(DB, DEFAULT_LOG)} site-editor text edits")
    from complete_botay_from_duplicates import run as complete_duplicates
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed identical tasks: {complete_duplicates(completion_con, write=True)}")
    from complete_botay_from_sdamgia import run as complete_sdamgia
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed matched Решу ЕГЭ keys: {complete_sdamgia(completion_con, write=True, year_filter=2025)}")
    from curated_botay_open_rubrics import run as complete_open_rubrics
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed open-variant rubrics: {complete_open_rubrics(completion_con, write=True, year_filter=2025)}")
    from complete_botay_2025_pdf import run as complete_published_2025
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed 2025 published keys: {complete_published_2025(completion_con, write=True)}")
    from curated_botay_open_solutions import run as complete_open_solutions
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed open-variant AI solutions: {complete_open_solutions(completion_con, write=True, year_filter=2025)}")
    from complete_botay_2025_dosrok import run as complete_early_2025
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed 2025 early variant: {complete_early_2025(completion_con, write=True)}")
    from complete_botay_2025_full_pdf import run as complete_expanded_2025
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed expanded 2025 published keys: {complete_expanded_2025(completion_con, write=True)}")
    from complete_botay_2025_ai_keys import run as complete_ai_keys
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed 2025 calculated keys: {complete_ai_keys(completion_con, write=True)}")
    from repair_botay_2025_dv1_26 import run as repair_dv1_26
    with sqlite3.connect(DB) as completion_con:
        print(f"Restored Far East task 26 question: {repair_dv1_26(completion_con, write=True)}")
    from complete_botay_2025_ai_solutions import run as complete_ai_solutions
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed 2025 AI TeX solutions: {complete_ai_solutions(completion_con, write=True)}")
    from complete_botay_ai_criteria import run as complete_ai_criteria
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed 2025 AI EGE-style criteria: {complete_ai_criteria(completion_con, write=True, year_filter=2025)}")


if __name__ == "__main__":
    main()

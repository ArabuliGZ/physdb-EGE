"""Import archived 2024 main and open EGE papers from Botay.

Missing keys and worked solutions stay empty. Every source and text correction
is archived or encoded here so a repeated import preserves it.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from lxml import html

from apply_site_text_edits import DEFAULT_LOG, apply_edits
from fetch_botay_2024 import DEST as ARCHIVE, SLUGS
from import_botay_2026 import parse_task, task_siblings
from numbered_figure_choices import split_numbered_choices
from import_examples import (
    DB, FORMATS, POINTS, ROOT, TOPICS, link_asset, store_asset,
    upsert_problem, upsert_variant,
)

VARIANTS = {
    "2024-real-11-24105": ("БОТАЙ-ОСНОВ-1", "ЕГЭ 2024 — Основной 1"),
    "2024-real-11-24107": ("БОТАЙ-ОСНОВ-2", "ЕГЭ 2024 — Основной 2"),
    "2024-real-11-24109": ("БОТАЙ-ОСНОВ-3", "ЕГЭ 2024 — Основной 3"),
    "2024-otkryt-11-1": ("БОТАЙ-ОТКРЫТ-1", "ЕГЭ 2024 — открытый вариант"),
}
SOLUTION_PAGES = {
    "2024-real-11-24107": {21: "9–10", 22: "10–11", 23: "11", 24: "12", 25: "13–14", 26: "14–15"},
    "2024-real-11-24109": {21: "8", 22: "8–9", 23: "9", 24: "10", 25: "10–11", 26: "11"},
    "2024-otkryt-11-1": {21: "10", 22: "10–11", 23: "11", 24: "12", 25: "12–13", 26: "13–14"},
}


def verify_archive() -> None:
    manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
    for relative, record in manifest.items():
        path = ARCHIVE / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Archived source changed: {relative}")


def tex_table(rows: list[list[str]]) -> str:
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("Uneven source table")
    lines = [r"\begin{tabular}{" + "|l" + "|c" * (width - 1) + "|}", r"\hline"]
    for row in rows:
        cells = [(r"\(" + value.replace(",", "{,}") + r"\)" if
                  re.fullmatch(r"-?\d+(?:,\d+)?", value) else value) for value in row]
        lines.extend([" & ".join(cells) + r"\\", r"\hline"])
    return "\n".join(lines + [r"\end{tabular}"])


TABLES = {
    ("2024-real-11-24105", 20): [[
        "№ проводника", r"Длина проводника, \(\text{см}\)",
        r"Диаметр проводника, \(\text{мм}\)", "Материал",
    ], ["1", "200", "1,0", "алюминий"], ["2", "100", "0,5", "сталь"],
        ["3", "100", "1,0", "медь"], ["4", "200", "0,5", "алюминий"],
        ["5", "200", "1,0", "медь"]],
    ("2024-real-11-24107", 20): [[
        "№ сосуда", r"Давление, \(\text{кПа}\)",
        r"Температура газа, \({}^\circ\text{C}\)", r"Масса газа, \(\text{г}\)",
    ], ["1", "60", "80", "10"], ["2", "60", "100", "10"],
        ["3", "80", "60", "5"], ["4", "90", "80", "15"],
        ["5", "100", "60", "5"]],
    ("2024-real-11-24109", 4): [[
        r"\(F_1\), \(\text{Н}\)", r"\(l_1\), \(\text{м}\)",
        r"\(F_2\), \(\text{Н}\)", r"\(l_2\), \(\text{м}\)",
    ], ["40", "0,8", "?", "0,2"]],
    ("2024-otkryt-11-1", 20): [[
        "№ сосуда", r"Объём сосуда, \(\text{л}\)",
        r"Температура газа, \(\text{К}\)", "Газ в сосуде",
    ], ["1", "8", "300", "неон"], ["2", "10", "180", "аргон"],
        ["3", "8", "320", "аргон"], ["4", "12", "300", "неон"],
        ["5", "6", "280", "аргон"]],
}


def repair_task(data: dict, slug: str, number: int) -> dict:
    text = re.sub(r"\n\nИсточник:.*$", "", data["statement"], flags=re.S)
    text = re.sub(r"\\\(([^)]*?)\\,\\\)°([СC])", r"\\(\1\\,\\text{°\2}\\)", text)
    text = re.sub(r"\\\(([^)]*?)\\\)°", r"\\(\1{}^\\circ\\)", text)
    text = re.sub(r"\\\(([A-Za-z]+)\\,\\text\{с\}\\\)", r"\\(\1\\) с", text)
    if (slug, number) in TABLES:
        source = tex_table(TABLES[(slug, number)])
        if slug == "2024-otkryt-11-1":
            text, count = re.subn(r"№ сосудаОбъём сосуда.*?(?=\n\nЗапишите)",
                                  lambda _: source, text, count=1, flags=re.S)
        elif number == 4:
            text, count = re.subn(r"Результаты, которые он получил, представлены в таблице\.",
                                  lambda _: "Результаты, которые он получил, представлены в таблице.\n\n" + source,
                                  text, count=1)
        else:
            text, count = re.subn(r"\(см\. таблицу\)\.",
                                  lambda _: "(см. таблицу).\n\n" + source, text, count=1)
            if not count:
                text, count = re.subn(r"характеристики которых указаны в таблице\.",
                                      lambda _: "характеристики которых указаны в таблице.\n\n" + source,
                                      text, count=1)
        if count != 1:
            raise ValueError(f"Missing source table insertion point: {slug} #{number}")
    if slug == "2024-real-11-24109" and number == 5:
        times = ["0,0", "0,2", "0,4", "0,6", "0,8", "1,0", "1,2", "1,4", "1,6",
                 "1,8", "2,0", "2,2", "2,4", "2,6", "2,8", "3,0", "3,2"]
        positions = ["0", "2", "5", "10", "13", "15", "13", "10", "5",
                     "2", "0", "-2", "-5", "-10", "-13", "-15", "-13"]
        parts = []
        for start, end in ((0, 9), (9, 17)):
            parts.append(tex_table([[r"\(t\), \(\text{с}\)", *times[start:end]],
                                    [r"\(x\), \(\text{мм}\)", *positions[start:end]]]))
        text = text.replace("в различные моменты времени.",
                            "в различные моменты времени.\n\n" + "\n\n".join(parts), 1)
    if slug == "2024-otkryt-11-1":
        if number == 5:
            text = text.replace("(груз \n1) ", r"(груз \(1\)) ")
            text = text.replace("(груз \n2) .", r"(груз \(2\)).")
        labels = {
            6: ["Дальность полёта", "Скорость шарика в момент падения"],
            10: ["КПД тепловой машины", "Работа тепловой машины за цикл"],
            15: ["Частота", "Скорость"],
            17: ["Массовое число ядра", "Заряд ядра"],
        }.get(number)
        if labels:
            text = text.replace("\n\n" + "".join(labels), "")
            data["answer_table_labels"] = labels
    if slug == "2024-real-11-24109":
        labels = {
            10: ["КПД тепловой машины", "Количество теплоты, переданное газу от нагревателя"],
            15: ["Сила тока в цепи", "Напряжение на реостате"],
            17: ["Массовое число ядра", "Число нейтронов в ядре"],
        }.get(number)
        if labels:
            data["answer_table_labels"] = labels
    if slug == "2024-real-11-24105" and number == 17:
        data["answer_table_labels"] = [
            "Длина волны падающего света", "Модуль запирающего напряжения",
        ]
    if slug == "2024-real-11-24107":
        labels = {
            6: ["Высота орбиты спутника", "Период обращения спутника"],
            17: ["Массовое число ядра", "Число протонов в ядре"],
        }.get(number)
        if labels:
            data["answer_table_labels"] = labels
    if slug == "2024-real-11-24107" and number == 4:
        text = text.replace(r"\(3500\) кг/м\(^3\)", r"\(3500\,\text{кг}/\text{м}^3\)")
    if slug == "2024-real-11-24105" and number == 3:
        text = text.replace(r"\(40\,\text{кг}\)\(\cdot\)м/с",
                            r"\(40\,\text{кг}\cdot\text{м}/\text{с}\)")
    if slug == "2024-real-11-24105" and number == 5:
        text = text.replace(r"\(500\) кг/м\(^3\)", r"\(500\,\text{кг}/\text{м}^3\)")
    if slug == "2024-real-11-24109" and number == 22:
        text = text.replace(r"\(\rho_1 = 400\) кг/м\(^3\)",
                            r"\(\rho_1=400\,\text{кг}/\text{м}^3\)")
    if slug == "2024-otkryt-11-1" and number == 25:
        text = text.replace(r"\(t = 10\) мин.", r"\(t=10\,\text{мин}\)")
        text = text.replace(r"\(c = 716\) Дж/(кг·К)",
                            r"\(c=716\,\frac{\text{Дж}}{\text{кг}\cdot\text{К}}\)")
        text = text.replace(r"\(\rho = 1{,}29\) кг/м\(^3\)",
                            r"\(\rho=1{,}29\,\text{кг}/\text{м}^3\)")
    if slug == "2024-otkryt-11-1" and number == 26:
        text = text.replace(r"\(\alpha = 30^\circ\,\text{с}\) горизонтом",
                            r"\(\alpha=30^\circ\) с горизонтом")
    if slug == "2024-real-11-24107" and number == 24 and data["solution"]:
        data["solution"] = data["solution"].replace(
            r"1\text{ моль}\cdot 8{,}31\text{ Дж/(моль·К)}\cdot 265\text{ К}",
            r"1\,\text{моль}\cdot 8{,}31\,\frac{\text{Дж}}{\text{моль}\cdot\text{К}}\cdot 265\,\text{К}",
        )
        data["solution"] = data["solution"].replace(r"3886\text{ Дж}", r"3886\,\text{Дж}")
    if slug == "2024-otkryt-11-1" and number == 25 and data["solution"]:
        solution = data["solution"].replace(r"\(\tau = 10\) мин \(= 600\,\text{с}\)",
                                            r"\(\tau=10\,\text{мин}=600\,\text{с}\)")
        solution = re.sub(
            r"\$\$.*?\$\$",
            lambda _: (r"\[\eta=\frac{c\rho VT_1(p_2-p_1)}{p_1UI\tau},\qquad "
                       r"V=\frac{\eta p_1UI\tau}{c\rho T_1(p_2-p_1)}"
                       r"=\frac{0{,}13\cdot10^5\cdot100\cdot2\cdot600}"
                       r"{716\cdot1{,}29\cdot273\cdot3\cdot10^5}"
                       r"\approx0{,}021\,\text{м}^3.\]"),
            solution, count=1, flags=re.S,
        )
        data["solution"] = solution
    if slug == "2024-otkryt-11-1" and number == 26 and data["solution"]:
        solution = data["solution"]
        for old, new in (
            (r"F_{тр1}", r"F_{\text{тр}1}"),
            (r"F_{тр2}", r"F_{\text{тр}2}"),
            (r"F_{тр}", r"F_{\text{тр}}"),
        ):
            solution = solution.replace(old, new)
        blocks = (
            (r"\[Ox:\quad -N_1\sin\alpha+F_{\text{тр}}\cos\alpha=ma;\qquad "
             r"Oy:\quad N_1\cos\alpha+F_{\text{тр}}\sin\alpha-mg=0.\]"),
            (r"\[a=\frac{g(\mu-\operatorname{tg}\alpha)}{1+\mu\operatorname{tg}\alpha}"
             r"=\frac{10(0{,}6-\operatorname{tg}30^\circ)}{1+0{,}6\operatorname{tg}30^\circ}"
             r"\approx0{,}17\,\text{м}/\text{с}^2.\]"),
        )
        for replacement in blocks:
            solution, count = re.subn(r"\$\$.*?\$\$", lambda _: replacement,
                                      solution, count=1, flags=re.S)
            if count != 1:
                raise ValueError("Missing printed solution formula for 2024 open #26")
        data["solution"] = solution
    data["statement"] = text
    return data


def assessment(slug: str, number: int, statement: str) -> tuple[str, int, int, str]:
    """Assess the actual topic and answer format against the 2027 position."""
    if number == 7 and slug != "2024-real-11-24109":
        return "no", 0, 1, "Задача о газовом законе или давлении; позиция 7 КИМ 2027 требует связи температуры со средней кинетической энергией частиц."
    if number == 21 and slug != "2024-real-11-24107":
        return "no", 0, 1, "Качественная задача не по электродинамике; позиция 21 КИМ 2027 — электродинамика."
    if number == 22:
        if slug == "2024-real-11-24105":
            return "yes", 1, 1, "Практический сюжет с автомобилем и графиком координаты, расчёт по механике, 2 балла."
        return "partial", 1, 1, "Механический расчёт совпадает по формату и баллам, но практическая направленность позиции 22 выражена слабо."
    if number == 23 and slug != "2024-real-11-24107":
        return "no", 0, 1, "Расчёт не по молекулярной физике; позиция 23 КИМ 2027 — молекулярная физика."
    if number == 25 and slug == "2024-otkryt-11-1":
        return "no", 0, 1, "Расчёт о нагревании газа относится к молекулярной физике; позиция 25 КИМ 2027 — электродинамика."
    return "yes", 1, 1, "Тема, формат ответа и баллы соответствуют позиции КИМ 2027."


def source_topic(slug: str, number: int) -> str:
    if number == 25 and slug == "2024-otkryt-11-1":
        return "molecular"
    if number in (21, 23):
        if number == 21:
            return "electrodynamics" if slug == "2024-real-11-24107" else "molecular"
        return "molecular" if slug == "2024-real-11-24107" else "electrodynamics"
    return TOPICS[number]


def solution_figures(task) -> list[str]:
    sources = []
    for node in task_siblings(task):
        if node.tag != "details":
            continue
        label = " ".join(node.xpath("./summary//text()"))
        if "Решение" not in label:
            continue
        sources.extend(node.xpath("./div[contains(concat(' ',normalize-space(@class),' '),' sol ')]//figure/img/@src"))
    return sources


def import_variant(con: sqlite3.Connection, slug: str) -> None:
    directory = ARCHIVE / slug
    page = html.fromstring((directory / "page.html").read_bytes())
    tasks = {}
    for task in page.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' o-zad ')]"):
        n = int(task.get("id")[1:])
        if n in tasks:
            raise ValueError(f"Duplicate task {slug} #{n}")
        data = repair_task(parse_task(task, n, slug), slug, n)
        data["solution_figures"] = solution_figures(task)
        tasks[n] = data
    if set(tasks) != set(range(1, 27)):
        raise ValueError(f"{slug}: expected exactly 26 tasks")
    number, title = VARIANTS[slug]
    variant_id = upsert_variant(con, directory / "usloviya.pdf", 2024, number, title, False)
    for n, data in tasks.items():
        locator = f"https://botay.pro/olimpiady/ege/{slug}/#z{n}; "
        locator += (directory / "usloviya.pdf").relative_to(ROOT).as_posix()
        if data["solution"]:
            locator += f"; {((directory / 'resheniya.pdf').relative_to(ROOT)).as_posix()}, PDF pp. {SOLUTION_PAGES[slug][n]}"
        notes = "Условие и рисунки из сохранённой страницы Botay; требуется сверка с авторским оригиналом."
        if data["answer"] is None:
            notes += " Явный ключ отсутствует в доступном источнике."
        if n >= 21 and data["solution"] is None:
            notes += " Развёрнутое решение отсутствует."
        pid = upsert_problem(
            con, variant_id, n, 1, data["statement"], data["answer"], data["solution"], None,
            source_topic(slug, n), locator, notes, status="needs_review",
            max_points=POINTS[n], answer_format=FORMATS[n],
        )
        con.execute(
            "UPDATE problems SET answer_prefix=?,answer_unit=?,answer_table_labels=? WHERE id=?",
            (data["answer_prefix"] or None, data["answer_unit"] or None,
             json.dumps(data["answer_table_labels"], ensure_ascii=False) if data["answer_table_labels"] else None, pid),
        )
        for src in data["figures"]:
            path = directory / "images" / Path(src).name
            content = path.read_bytes()
            if slug == "2024-real-11-24109" and n == 20:
                for choice, part in enumerate(split_numbered_choices(content), 1):
                    aid = store_asset(con, part, ".png", "image/png")
                    link_asset(con, pid, aid, "statement_figure", f"{locator}; {src}; choice {choice}")
            else:
                aid = store_asset(con, content, ".png", "image/png")
                source_table = (slug, n) in TABLES or (slug == "2024-real-11-24109" and n in (5, 10, 17))
                link_asset(con, pid, aid, "source_page" if source_table else "statement_figure",
                           f"{locator}; {src}")
        for src in data["solution_figures"]:
            path = directory / "images" / Path(src).name
            aid = store_asset(con, path.read_bytes(), ".png", "image/png")
            link_asset(con, pid, aid, "solution_figure", f"{locator}; solution; {src}")
        con.execute("DELETE FROM relevance WHERE problem_id=? AND exam_year=2027", (pid,))
        verdict, topic_match, format_match, reason = assessment(slug, n, data["statement"])
        con.execute(
            """INSERT INTO relevance
               (problem_id,exam_year,target_problem_number,topic_match,format_match,verdict,reason)
               VALUES (?,2027,?,?,?,?,?)""",
            (pid, n, topic_match, format_match, verdict, reason),
        )
    print(f"{slug}: {len(tasks)} tasks, {sum(bool(x['answer']) for x in tasks.values())} keys, "
          f"{sum(bool(x['solution']) for x in tasks.values())} solutions, "
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
    print(f"Replayed {apply_edits(DB, DEFAULT_LOG)} site-editor edits")
    from complete_botay_from_duplicates import run as complete_duplicates
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed identical tasks: {complete_duplicates(completion_con, write=True)}")
    from complete_botay_from_solutions import run as complete_published
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed published keys: {complete_published(completion_con, write=True)}")
    from curated_botay_2024_main1 import run as complete_main1_solutions
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed main variant 1 worked solutions: {complete_main1_solutions(completion_con, write=True)}")
    from curated_botay_2024_main23 import run as complete_main23
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed main variants 2–3 answers and rubrics: {complete_main23(completion_con, write=True)}")
    from complete_botay_from_sdamgia import run as complete_sdamgia
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed matched Решу ЕГЭ keys: {complete_sdamgia(completion_con, write=True, year_filter=2024)}")
    from curated_botay_open_rubrics import run as complete_open_rubrics
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed open-variant rubrics: {complete_open_rubrics(completion_con, write=True, year_filter=2024)}")
    from curated_botay_open_solutions import run as complete_open_solutions
    with sqlite3.connect(DB) as completion_con:
        print(f"Completed open-variant AI solutions: {complete_open_solutions(completion_con, write=True, year_filter=2024)}")


if __name__ == "__main__":
    main()

"""Import the three archived Botay EGE 2026 papers without inventing missing keys.

The archived HTML supplies per-task TeX and image links. The three PDF views
per paper are retained for visual comparison; for two papers their answer view
does not actually contain answers. Re-import is deterministic and replays edits.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from lxml import html

from apply_site_text_edits import DEFAULT_LOG, apply_edits
from answer_units import format_answer_unit_tex
from import_examples import (
    DB, FORMATS, POINTS, ROOT, TOPICS, assess, link_asset, store_asset,
    upsert_problem, upsert_variant,
)
from tex_format import format_quantities

ARCHIVE = ROOT / "Материалы" / "ЕГЭ 2026 Botay"
SLUGS = {
    "2026-osnov-11-dv-1": ("ОСНОВ-ДВ-1", "ЕГЭ 2026 — основная волна, ДВ-1"),
    "2026-otkryt-11-1": ("ОТКРЫТ-1", "ЕГЭ 2026 — открытый вариант"),
    "2026-dosrok-11-1": ("ДОСРОК-1", "ЕГЭ 2026 — досрочный вариант"),
}
MATH_BLANK = re.compile(r"\\underline\{[^{}]*\}")
ANSWER_MARKER = re.compile(r"\bОтветы?:")


def verify_archive() -> None:
    manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
    for relative, record in manifest.items():
        path = ARCHIVE / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Archived source changed: {relative}")


def compact(text: str) -> str:
    return " ".join(text.split()).strip()


def normalize_math(text: str) -> str:
    text = re.sub(
        r"_([А-Яа-яЁё])(?=[^А-Яа-яЁё]|$)",
        lambda match: r"_{\text{" + match.group(1) + "}}", text,
    )
    return text.replace(r"\,^\circ", r"\,{}^\circ")


def render(node) -> str:
    if node.tag in ("ol", "ul"):
        lines = []
        for index, item in enumerate(node.xpath("./li"), 1):
            value = compact(render(item))
            printed = re.match(r"^\[\s*([А-ЯA-Z0-9]+[.)])\s*\]\s*", value)
            lines.append(
                printed.group(1) + " " + value[printed.end():] if printed
                else f"{index}) {value}"
            )
        return "\n".join(lines)
    if node.tag == "br":
        return "\n"
    value = node.text or ""
    for child in node:
        value += ("\n" if child.tag in ("ol", "ul") else "") + render(child)
        value += child.tail or ""
    return value


def clean_lines(value: str) -> str:
    lines = [compact(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def answer_field(text: str, number: int) -> tuple[str, str]:
    """Return source-printed prefix and unit, keeping LaTeX Cyrillic legal."""
    if number not in {1, 2, 3, 4, 7, 8, 11, 12, 13, 16, 19}:
        return "", ""
    marker = ANSWER_MARKER.search(text)
    if not marker:
        return "", ""
    field = text[marker.end():].strip().rstrip(".")
    blank = MATH_BLANK.search(field)
    if blank is None:
        return "", ""
    before = field[:blank.start()]
    after = field[blank.end():]
    before = before.replace(r"\(", "").strip()
    prefix = before if before in {"в", "на"} else ""
    after = MATH_BLANK.sub("", after)
    after = after.replace(r"\)", "").strip()
    # The source sometimes types exponents and multiplication in separate math.
    after = after.replace(r"\(^2", "²").replace(r"\(^3", "³")
    after = after.replace(r"\(\cdot", "·").replace(r"\(", "")
    after = after.replace(r"^{\circ}", "°").replace(r"^\circ", "°")
    if number == 19:
        after = after.replace(r"\pm", "")
        after = after.replace("(", "").replace(")", "").strip()
    if after.startswith("±"):
        after = re.sub(r"^±.*?\s(?=[А-Яа-я])", "", after)
    after = after.strip()
    if not after:
        return prefix, ""
    return prefix, format_answer_unit_tex(after)


def task_siblings(task) -> list:
    siblings = []
    node = task.getnext()
    while node is not None and not (
        node.tag == "div" and "o-zad" in node.get("class", "").split()
    ):
        siblings.append(node)
        node = node.getnext()
    return siblings


def parse_detail(node, label: str) -> str | None:
    summary = compact(" ".join(node.xpath("./summary//text()")))
    if label not in summary:
        return None
    body = node.xpath("./div[contains(concat(' ',normalize-space(@class),' '),' sol ')]")
    if not body:
        return None
    paragraphs = []
    for child in body[0]:
        if "lbl" in child.get("class", "").split() or "o-posle" in child.get("class", "").split():
            continue
        part = clean_lines(render(child))
        if part:
            paragraphs.append(part)
    return normalize_math(format_quantities("\n\n".join(paragraphs))) or None


def repair_statement(text: str, slug: str, number: int) -> str:
    """Restore tables which the source page flattened into prose."""
    if slug != "2026-osnov-11-dv-1":
        return text
    if number == 4:
        table = r"""Результаты, которые он получил, представлены в таблице:
\begin{tabular}{|c|c|c|c|}
\hline
\(F_1\), Н & \(l_1\), м & \(F_2\), Н & \(l_2\), м\\
\hline
40 & 0,4 & ? & 0,8\\
\hline
\end{tabular}
Здесь"""
        text, count = re.subn(
            r"Результаты, которые он получил, представлены в таблице:.*?Здесь",
            lambda _: table, text, flags=re.S,
        )
    elif number == 14:
        table = r"""В таблице приведены значения разности потенциалов на обкладках
конденсатора в последовательные моменты времени:
\begin{tabular}{|c|c|c|c|c|c|c|c|c|c|}
\hline
\(t\), мкс & 0 & 4 & 8 & 12 & 16 & 20 & 24 & 28 & 32\\
\hline
\(U\), В & 0,0 & 5,6 & 8,0 & 5,6 & 0,0 & -5,6 & -8,0 & -5,6 & 0,0\\
\hline
\end{tabular}
Выберите"""
        text, count = re.subn(
            r"В таблице приведены значения разности потенциалов.*?Выберите",
            lambda _: table, text, flags=re.S,
        )
    elif number == 20:
        table = r"""\begin{tabular}{|c|c|c|c|c|c|}
\hline
№ цепи & 1 & 2 & 3 & 4 & 5\\
\hline
ЭДС источника \(\mathcal{E}\), В & 6 & 9 & 8 & 9 & 6\\
\hline
Внутреннее сопротивление \(r\), Ом & 1,0 & 0,5 & 1,5 & 1,5 & 0,5\\
\hline
Внешнее сопротивление \(R\), Ом & 5 & 8 & 16 & 8 & 16\\
\hline
\end{tabular}"""
        text, count = re.subn(r"Таблица:.*", lambda _: table, text, flags=re.S)
    else:
        return text
    if count != 1:
        raise ValueError(f"Could not restore {slug} task {number} table")
    return text


def parse_task(task, number: int, slug: str) -> dict:
    statements = []
    answer = solution = None
    prefix = unit = ""
    figures = []
    table_labels = []
    for node in task_siblings(task):
        if node.tag == "figure":
            figures.extend(node.xpath(".//img/@src"))
            continue
        if node.tag == "details":
            answer = answer or parse_detail(node, "Ответ")
            solution = solution or parse_detail(node, "Решение")
            continue
        if node.tag not in ("p", "ol", "ul") and not (
            node.tag == "div" and "k-center" in node.get("class", "").split()
        ):
            continue
        part = clean_lines(render(node))
        if not part:
            continue
        match = ANSWER_MARKER.search(part)
        if match:
            field = part[match.start():]
            p, u = answer_field(field, number)
            prefix, unit = p or prefix, u or unit
            part = part[:match.start()].strip()
        if not part:
            continue
        if number in (6, 10, 15, 17) and MATH_BLANK.search(part):
            for line in re.split(r"[;\n]", part):
                if not MATH_BLANK.search(line):
                    continue
                label = compact(line.split(":", 1)[0])
                if label and not label.startswith(("Для каждой", "Запишите")):
                    table_labels.append(label)
            # The printed blanks are rendered from answer_table_labels.
            continue
        statements.append(part)
    if not statements:
        raise ValueError(f"Task {number} has no statement")
    if slug != "2026-osnov-11-dv-1" and number in (6, 17):
        table_labels = ["А", "Б"]
    if slug == "2026-dosrok-11-1" and number == 10:
        table_labels = ["Концентрация молекул газа в ходе процесса 1–2", "Объём газа в ходе процесса 2–3"]
    if slug == "2026-dosrok-11-1" and number == 15:
        table_labels = ["Кинетическая энергия", "Период обращения"]
    if number not in (6, 10, 15, 17):
        table_labels = []
    raw_statement = "\n\n".join(statements)
    raw_statement = re.sub(r"(?<![\\\w])([1-5])\)\s*", r"\n\1) ", raw_statement)
    raw_statement = repair_statement(raw_statement, slug, number)
    return {
        "statement": normalize_math(format_quantities(raw_statement)),
        "answer": normalize_math(answer) if answer else None,
        "solution": solution,
        "figures": figures,
        "answer_prefix": prefix,
        "answer_unit": unit,
        "answer_table_labels": table_labels[:2],
    }


def relevance(number: int) -> tuple[str, int, str]:
    if number == 7:
        return "no", 0, (
            "Числовая задача на газовый закон; позиция 7 КИМ 2027 — "
            "связь температуры газа со средней кинетической энергией частиц."
        )
    if number == 21:
        return "no", 0, (
            "Качественная задача по молекулярной физике; позиция 21 КИМ 2027 "
            "отведена электродинамике."
        )
    if number == 23:
        return "no", 0, (
            "Расчёт силы тока в магнитном поле; позиция 23 КИМ 2027 "
            "отведена молекулярной физике."
        )
    return "yes", 1, (
        "Тема, тип ответа и баллы соответствуют позиции КИМ 2027; "
        "источник 2026 года сохранён для постраничной сверки."
    )


def import_variant(con: sqlite3.Connection, slug: str, number: str, title: str) -> None:
    directory = ARCHIVE / slug
    page = html.fromstring((directory / "page.html").read_bytes())
    tasks = {int(task.get("id")[1:]): parse_task(task, int(task.get("id")[1:]), slug)
             for task in page.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' o-zad ')]")}
    if set(tasks) != set(range(1, 27)):
        raise ValueError(f"{slug}: expected 26 unique tasks, got {sorted(tasks)}")
    variant_id = upsert_variant(con, directory / "usloviya.pdf", 2026, number, title, False)
    for task_number, data in tasks.items():
        locator = f"https://botay.pro/olimpiady/ege/{slug}/#z{task_number}; "
        locator += f"{(directory / 'usloviya.pdf').relative_to(ROOT).as_posix()}"
        notes = (
            "Условие и рисунки перенесены из архивной HTML-страницы; PDF — "
            "визуальная копия сайта. Статус needs_review до полной сверки с "
            "независимым исходником. Критериев на странице нет."
        )
        if data["answer"] is None:
            notes += " Ключ ответа в сохранённом источнике отсутствует."
        if task_number >= 21 and data["solution"] is None:
            notes += " Развёрнутое решение в сохранённом источнике отсутствует."
        pid = upsert_problem(
            con, variant_id, task_number, 1, data["statement"], data["answer"],
            data["solution"], None,
            "molecular" if task_number == 21 else
            "electrodynamics" if task_number == 23 else TOPICS[task_number],
            locator, notes,
            status="needs_review", max_points=POINTS[task_number],
            answer_format=FORMATS[task_number],
        )
        con.execute(
            """UPDATE problems SET answer_prefix=?,answer_unit=?,answer_table_labels=?
               WHERE id=?""",
            (
                data["answer_prefix"] or None,
                data["answer_unit"] or None,
                json.dumps(data["answer_table_labels"], ensure_ascii=False)
                if data["answer_table_labels"] else None,
                pid,
            ),
        )
        for src in data["figures"]:
            local = directory / "images" / Path(src).name
            aid = store_asset(con, local.read_bytes(), local.suffix.lower(), "image/png")
            link_asset(con, pid, aid, "statement_figure", f"{locator}; {src}")
        verdict, topic_match, reason = relevance(task_number)
        assess(con, pid, task_number, topic_match, 1, verdict, reason)
    print(f"{slug}: imported 26 tasks; {sum(bool(t['answer']) for t in tasks.values())} explicit answers; "
          f"{sum(bool(t['solution']) for t in tasks.values())} explicit solutions")


def main() -> None:
    verify_archive()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        if "answer_table_labels" not in {
            row[1] for row in con.execute("PRAGMA table_info(problems)")
        }:
            con.execute("ALTER TABLE problems ADD COLUMN answer_table_labels TEXT")
        with con:
            for slug, (number, title) in SLUGS.items():
                import_variant(con, slug, number, title)
    finally:
        con.close()
    print(f"Replayed {apply_edits(DB, DEFAULT_LOG)} site-editor text edits")


if __name__ == "__main__":
    main()

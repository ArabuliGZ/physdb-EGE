"""Import the first three 30-task Demidova 2023 papers from original DOCX.

The OCR/OOXML and MathType transcription is reproducible. Records stay
needs_review until every statement, figure, solution and rubric is visually
checked against the author's document. Source numbers and 2027 positions are
kept separate.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from docx import Document

from import_examples import DB, ROOT, assess, upsert_problem, upsert_variant
from import_2026_remaining import (add_figures, extract_blocks, formula_marker,
                                    normalize_statement, normalized_figure_png,
                                    review_sections, VERIFIED_FORMULAS,
                                    SOURCE_MATHML_FORMULAS)
from mapping_2023_2027 import (EXTENDED_TOPIC, SOURCE_FORMAT, SOURCE_POINTS,
                                SOURCE_TOPIC, assessment)
from migrate_problem_range import allow_thirty_source_numbers
from text_repairs import repair_text


SOURCE_ROOT = ROOT / "Материалы" / "ЕГЭ от Демидовой" / "От Демидовой до 2023 года"
FORMULAS = json.loads((ROOT / "tools" / "2023_formulas.json").read_text(encoding="utf-8"))
DIAGRAM_IN_FORMULA_SLOT = "fa02b004bd83cb76a61df885b0413936ea1ee11e8b85713c59e5f71047affbd0"
MTEF_REPAIRS = {
    r"_{в ы x}": r"_{\text{вых}}", r"_{в ы x .}": r"_{\text{вых}}",
    r"_{з}": r"_{\text{з}}", r"_{o т н}": r"_{\text{отн}}",
    r"_{т p 1}": r"_{\text{тр}1}", r"_{т p \text{2}}": r"_{\text{тр}2}",
    r"_{т p}": r"_{\text{тр}}", r"_{т \text{p}}": r"_{\text{тр}}",
    r"_{у \pi p}": r"_{\text{упр}}", r"_{и н д}": r"_{\text{инд}}",
    r"\left{\right.": r"\left\{\right.",
    " Г ц": r"\,\text{Гц}", " м^{- 3}": r"\,\text{м}^{-3}",
    " 1000 В = 1 к В": r" 1000\,\text{В}=1\,\text{кВ}",
    " = 1 м": r"=1\,\text{м}",
    " %": r"\%",
    r"_{m a x}": r"_{\max}", r"_{m i n}": r"_{\min}",
    r"\left(\right.": r"\left(", r"\left.\right)": r"\right)",
    r"\left|\right.": r"|",
}


def clean_mtef(tex: str) -> str:
    tex = tex.replace(
        r"\left{\right. p V = \nu R T , \\ U = \frac{3}{2} \nu R T .",
        r"pV=\nu RT,\quad U=\frac{3}{2}\nu RT.",
    )
    for old, new in MTEF_REPAIRS.items():
        tex = tex.replace(old, new)
    return tex


def numbered(doc, begin: int, end: int, first: int, last: int) -> dict[int, int]:
    positions: dict[int, int] = {}
    cursor = begin
    for number in range(first, last + 1):
        found = next((i for i in range(cursor, end)
                      if doc.paragraphs[i].text.strip() == str(number)), None)
        if found is None:
            raise ValueError(f"Missing source task {number} after paragraph {cursor}")
        positions[number] = found
        cursor = found + 1
    return positions


def source_key(doc) -> dict[int, str]:
    table = next((table for table in doc.tables
                  if len(table.rows) == 24 and len(table.columns) == 2
                  and table.cell(0, 0).text.strip() == "№ задания"), None)
    if table is None:
        raise ValueError("Expected the 24-row author answer table")
    key = {int(row.cells[0].text.strip()): row.cells[1].text.strip()
           for row in table.rows[1:]}
    if set(key) != set(range(1, 24)) or not all(key.values()):
        raise ValueError("Incomplete 2023 answer key")
    return key


def formula_tex(value: str | None, embedded: list[tuple[bytes, tuple[int, int]]],
                figures: list[bytes]) -> str | None:
    if value is None:
        return None
    for index, (data, _) in enumerate(embedded):
        marker = formula_marker(index)
        if marker not in value:
            continue
        sha = hashlib.sha256(normalized_figure_png(data)).hexdigest()
        if sha == DIAGRAM_IN_FORMULA_SLOT:
            figures.append(data)
            value = value.replace(marker, "")
            continue
        match = FORMULAS.get(sha) or VERIFIED_FORMULAS.get(sha) or SOURCE_MATHML_FORMULAS.get(sha)
        if not match or not match.get("tex"):
            raise ValueError(f"Untranscribed 2023 formula {sha}, image {index + 1}")
        value = value.replace(marker, r"\(" + clean_mtef(match["tex"]) + r"\)")
    if "[[SRCFORMULA" in value or "[[formula:" in value or "[формула в исходном" in value:
        raise ValueError("Formula placeholder survived the 2023 import")
    return value


def tidy_solution(variant: int, task: int, value: str) -> str:
    """Drop duplicated Word drawing labels; the actual diagram stays an asset."""
    prefix, separator, body = value.partition("\n")
    anchors = {
        (2, 24): "Если сила", (2, 27): "Систему отсчёта",
        (3, 27): "Систему отсчёта", (1, 30): "Обоснование",
    }
    anchor = anchors.get((variant, task))
    if anchor:
        if anchor not in body:
            raise ValueError(f"Review text changed before {anchor}: 2023-{variant} task {task}")
        body = body[body.index(anchor):]
    body = body.replace("Обоснование1.", "Обоснование\n1.")
    body = body.replace("Решение1.", "Решение\n1.")
    body = re.sub(r"(?<=[.])(?=[А-ЯЁ])", " ", body)
    body = re.sub(r"\s*Ответ:", "\n\nОтвет:", body)
    return prefix + separator + body


def import_one(con: sqlite3.Connection, number: int) -> None:
    source = SOURCE_ROOT / f"2023 В{number}.docx"
    if not source.is_file():
        raise FileNotFoundError(source)
    doc = Document(source)
    end = next(i for i, paragraph in enumerate(doc.paragraphs)
               if "Ответы к заданиям" in paragraph.text)
    rubric_start = next(i for i, paragraph in enumerate(doc.paragraphs)
                        if "Критерии оценивания заданий с развёрнутым ответом" in paragraph.text)
    starts = numbered(doc, 0, end, 1, 30)
    reviews = numbered(doc, rubric_start + 1, len(doc.paragraphs), 24, 30)
    if number == 1:
        # The printed label 29 is a floating Word box anchored after its prose.
        if starts[29] != 436 or not doc.paragraphs[435].text.startswith("Ион ускоряется"):
            raise ValueError("Source layout for 2023-1 task 29 changed")
        starts[29] = 435
    answers = source_key(doc)
    variant_id = upsert_variant(con, source, 2023, str(number),
                                f"Демидова 2023, вариант {number}", False)
    for task in range(1, 31):
        stop = starts.get(task + 1, end)
        embedded: list[tuple[bytes, tuple[int, int]]] = []
        raw, statement_figures = extract_blocks(doc, starts[task], stop, embedded)
        if number == 2 and task == 24:
            # Original PDF p. 14: Word shapes form a blank graph to the right
            # of the extracted pulley image. Preserve both as one checked crop.
            figure = ROOT / "assets" / "curated" / "figure_repairs" / "2023-2-24-diagram-and-grid.png"
            content = figure.read_bytes()
            if hashlib.sha256(content).hexdigest() != "2c04390df7670eb9bab46a516555b15ea14e86abc1515e5d39b7c64df79d8707":
                raise ValueError("2023-2 task 24 curated figure changed")
            statement_figures = [content]
        statement = formula_tex(normalize_statement(raw), embedded, statement_figures)
        assert statement is not None
        statement = repair_text(f"2023-{number}", task, "statement", statement)
        if task == 24:
            # The general instructions for tasks 25–30 are printed after task 24
            # in the source and must not become part of its statement.
            statement, separator, _ = statement.partition("\nПолное правильное решение")
            if not separator:
                raise ValueError(f"Missing 2023-{number} extended-part instruction boundary")
            if number in (1, 3):
                # Word's two-column layout repeats captions already visible in figures.
                statement = re.sub(r"\n\\begin\{tabular\}\{l\|l\}.*?\\end\{tabular\}",
                                   "", statement, flags=re.S)
            else:
                # Axis labels extracted twice from the sketch are not prose.
                statement, separator, _ = statement.partition("\n\\(0\\)       \\(2\\)")
                if not separator:
                    raise ValueError("Missing 2023-2 task 24 sketch-label boundary")
            statement = statement.rstrip()
        if not statement or len(statement.strip()) < 20:
            raise ValueError(f"Empty or damaged 2023-{number} task {task}")

        solution = criteria = None
        solution_figures: list[bytes] = []
        if task >= 24:
            review_formulas: list[tuple[bytes, tuple[int, int]]] = []
            solution, criteria, solution_figures = review_sections(
                doc, reviews[task], reviews.get(task + 1, len(doc.paragraphs)), review_formulas)
            solution = formula_tex(solution, review_formulas, solution_figures)
            criteria = formula_tex(criteria, review_formulas, solution_figures)
            solution = repair_text(f"2023-{number}", task, "solution", solution)
            criteria = repair_text(f"2023-{number}", task, "criteria", criteria)
            if not solution or not criteria:
                raise ValueError(f"Missing 2023-{number} solution or criteria for task {task}")
            solution = tidy_solution(number, task, solution)

        topic = EXTENDED_TOPIC[number].get(task, SOURCE_TOPIC.get(task, "cross_topic"))
        locator = f"DOCX paragraphs {starts[task]}–{stop - 1}"
        notes = ("Первичная расшифровка DOCX и формул MathType; требуется визуальная "
                 "сверка условия, рисунков, ключа, решения и критериев с исходником.")
        if task >= 24:
            notes += f" Критерии: абзацы {reviews[task]}–{reviews.get(task + 1, len(doc.paragraphs)) - 1}."
        problem_id = upsert_problem(con, variant_id, task, 1, statement, answers.get(task),
                                    solution, criteria, topic, locator, notes, "needs_review",
                                    max_points=SOURCE_POINTS[task],
                                    answer_format=SOURCE_FORMAT[task])
        add_figures(con, problem_id, statement_figures, "statement_figure", locator)
        add_figures(con, problem_id, solution_figures, "solution_figure",
                    f"DOCX rubric paragraphs {reviews[task]}–{reviews.get(task + 1, len(doc.paragraphs)) - 1}"
                    if task >= 24 else locator)
        target, verdict, topic_ok, format_ok, reason = assessment(number, task)
        if task == 30 and (SOURCE_POINTS[task] != 4 or
                           not all((f"Критерий {score}" in criteria or
                                    f"Критерий \\({score}\\)" in criteria)
                                   for score in (1, 2))):
            verdict = "partial"
            reason = ("Механическая расчётная задача близка позиции 26 проекта 2027, "
                      "но авторская шкала баллов или отдельный критерий обоснования модели "
                      "не совпадает с требованиями этой позиции.")
        assess(con, problem_id, target, topic_ok, format_ok, verdict, reason)
    print(f"2023-{number}: 30 tasks; 23 author answers; 7 solutions and rubrics")


def main() -> None:
    con = sqlite3.connect(DB)
    allow_thirty_source_numbers(con)
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    con.execute("PRAGMA foreign_keys=ON")
    with con:
        for number in (1, 2, 3):
            import_one(con, number)
    errors = con.execute("PRAGMA foreign_key_check").fetchall()
    if errors:
        raise ValueError(f"Foreign key errors: {errors[:3]}")
    count = con.execute("""SELECT COUNT(*) FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2023""").fetchone()[0]
    if count != 90:
        raise ValueError(f"Expected 90 source tasks; got {count}")
    print("Imported 2023 tasks:", count)
    con.close()


if __name__ == "__main__":
    main()

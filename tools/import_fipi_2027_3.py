"""Import the visually transcribed third variant of the scanned 2027 book.

All condition/solution text and figure boxes live in fipi_2027_3_* modules.
The downloadable source is a page-for-page excerpt of the scanned book.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from io import BytesIO

import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter

from apply_site_text_edits import DEFAULT_LOG, apply_edits
from fipi_2027_3_figures import (
    RENDER_SCALE, SOLUTION_FIGURES, SOURCE_SHA256, STATEMENT_FIGURES,
)
from fipi_2027_3_solutions import CRITERIA, SOLUTIONS, SOLUTION_PAGES
from fipi_2027_3_transcription import (
    ANSWERS, ANSWER_PREFIX, ANSWER_TABLE_LABELS, ANSWER_UNITS,
    SOURCE_PAGES, STATEMENTS,
)
from import_examples import (
    DB, FORMATS, POINTS, ROOT, TOPICS, assess, link_asset, store_asset,
    upsert_problem, upsert_variant,
)


SOURCE = ROOT / "Материалы" / "ЕГЭ физика 2027 ФИПИ.pdf"
EXCERPT = ROOT / "Материалы" / "ЕГЭ физика 2027 ФИПИ - вариант 3.pdf"
EXCERPT_PAGES = (*range(29, 37), 237, *range(253, 257))


def create_source_excerpt() -> None:
    if EXCERPT.exists():
        return
    reader = PdfReader(str(SOURCE))
    writer = PdfWriter()
    for page_number in EXCERPT_PAGES:
        writer.add_page(reader.pages[page_number - 1])
    writer.add_metadata({
        "/Title": "ЕГЭ физика 2027 ФИПИ — вариант 3, ключ и решения",
        "/SourceSHA256": SOURCE_SHA256,
    })
    with EXCERPT.open("wb") as stream:
        writer.write(stream)


def render_crop(pdf: pdfium.PdfDocument, page_number: int,
                box: tuple[int, int, int, int]) -> bytes:
    page = pdf[page_number - 1]
    image = page.render(scale=RENDER_SCALE).to_pil()
    left, top, right, bottom = box
    if not (0 <= left < right <= image.width and
            0 <= top < bottom <= image.height):
        raise ValueError(f"Crop outside page {page_number}: {box}")
    output = BytesIO()
    image.crop(box).save(output, format="PNG", optimize=True)
    return output.getvalue()


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The scanned source changed; recheck all crops and text")
    expected = set(range(1, 27))
    if set(STATEMENTS) != expected or set(ANSWERS) != expected:
        raise ValueError("Variant 3 needs all 26 conditions and key answers")
    if set(SOLUTIONS) != set(range(21, 27)) or set(CRITERIA) != set(range(21, 27)):
        raise ValueError("Long-answer tasks need solutions and criteria")
    assert len(STATEMENT_FIGURES[14]) == 2 and 20 not in STATEMENT_FIGURES
    create_source_excerpt()

    pdf = pdfium.PdfDocument(str(SOURCE))
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        if "answer_table_labels" not in {
            row[1] for row in con.execute("PRAGMA table_info(problems)")
        }:
            con.execute("ALTER TABLE problems ADD COLUMN answer_table_labels TEXT")
        with con:
            vid = upsert_variant(
                con, EXCERPT, 2027, "3", "Сборник ФИПИ 2027-3", False,
            )
            for number in range(1, 27):
                locator = (
                    f"{SOURCE.relative_to(ROOT).as_posix()}, печатная/PDF "
                    f"стр. {SOURCE_PAGES[number]}; ключ стр. 237, столбец 3"
                )
                if number >= 21:
                    locator += f"; авторское решение стр. {SOLUTION_PAGES[number]}"
                notes = (
                    "Условие, ключ и рисунки сверены визуально со сканом. "
                    "Для заданий 21–26 решение перенабрано в TeX с авторской "
                    "страницы; критерии изложены кратко, поскольку по этому "
                    "варианту нет отдельной авторской таблицы баллов. "
                    "До проверки по официальным критериям статус не повышать."
                )
                pid = upsert_problem(
                    con, vid, number, 1, STATEMENTS[number], ANSWERS[number],
                    SOLUTIONS.get(number), CRITERIA.get(number), TOPICS[number],
                    locator, notes, status="needs_review",
                    max_points=POINTS[number], answer_format=FORMATS[number],
                )
                labels = ANSWER_TABLE_LABELS.get(number)
                con.execute(
                    """UPDATE problems SET answer_prefix=?,answer_unit=?,
                    answer_table_labels=? WHERE id=?""",
                    (
                        ANSWER_PREFIX.get(number), ANSWER_UNITS.get(number),
                        json.dumps(labels, ensure_ascii=False) if labels else None,
                        pid,
                    ),
                )
                for role, figures in (
                    ("statement_figure", STATEMENT_FIGURES),
                    ("solution_figure", SOLUTION_FIGURES),
                ):
                    for index, (page, box) in enumerate(figures.get(number, []), 1):
                        aid = store_asset(
                            con, render_crop(pdf, page, box), ".png", "image/png",
                        )
                        link_asset(
                            con, pid, aid, role,
                            f"{SOURCE.relative_to(ROOT).as_posix()}, "
                            f"стр. {page}, рисунок {index} ({role})",
                        )
                if number == 22:
                    assess(
                        con, pid, number, 1, 0, "partial",
                        "Тема механики и 2 балла совпадают, но задача об "
                        "абстрактных гармонических колебаниях не соответствует "
                        "практическому сюжету позиции 22 в КИМ 2027.",
                    )
                else:
                    assess(
                        con, pid, number, 1, 1, "yes",
                        "Тема, номер, баллы и формат ответа соответствуют "
                        "позиции КИМ 2027; условие сверено со сканом сборника.",
                    )
    finally:
        con.close()
        pdf.close()

    applied = apply_edits(DB, DEFAULT_LOG)
    print(f"Imported book variant 3: 26 tasks; replayed {applied} site text edits")


if __name__ == "__main__":
    main()

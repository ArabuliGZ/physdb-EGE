"""Import visually transcribed odd variants 5–29 of the scanned 2027 book.

Each variant's text, source-page locators and figure boxes are stored in
fipi_2027_<number>_* modules. OCR drafts alone are never importable.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sqlite3
from io import BytesIO

import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter

from apply_site_text_edits import DEFAULT_LOG, apply_edits
from fipi_2027_1_figures import SOURCE_SHA256
from import_examples import (
    DB, FORMATS, POINTS, ROOT, TOPICS, assess, link_asset, store_asset,
    upsert_problem, upsert_variant,
)
from ocr_fipi_2027_odd import SOURCE, STARTS


def source_excerpt(number: int, solution_pages: dict[int, str]) -> object:
    excerpt = ROOT / "Материалы" / f"ЕГЭ физика 2027 ФИПИ - вариант {number}.pdf"
    if not excerpt.exists():
        key_page = 237 + (number - 1) // 10
        pages = list(range(STARTS[number], STARTS[number + 1]))
        pages.append(key_page)
        for locator in solution_pages.values():
            bounds = [int(value) for value in re.findall(r"\d+", locator)]
            pages.extend(range(bounds[0], bounds[-1] + 1))
        reader = PdfReader(str(SOURCE))
        writer = PdfWriter()
        for page_number in sorted(set(pages)):
            writer.add_page(reader.pages[page_number - 1])
        writer.add_metadata({
            "/Title": f"ЕГЭ физика 2027 ФИПИ — вариант {number}, ключ и решения",
            "/SourceSHA256": SOURCE_SHA256,
        })
        with excerpt.open("wb") as stream:
            writer.write(stream)
    return excerpt


def render_crop(pdf: pdfium.PdfDocument, page_number: int,
                box: tuple[int, int, int, int], scale: float) -> bytes:
    page = pdf[page_number - 1]
    image = page.render(scale=scale).to_pil()
    left, top, right, bottom = box
    if not (0 <= left < right <= image.width and
            0 <= top < bottom <= image.height):
        raise ValueError(f"Crop outside page {page_number}: {box}")
    output = BytesIO()
    image.crop(box).save(output, format="PNG", optimize=True)
    return output.getvalue()


def import_variant(con: sqlite3.Connection, pdf: pdfium.PdfDocument,
                   number: int) -> None:
    stem = f"fipi_2027_{number}"
    data = importlib.import_module(f"{stem}_transcription")
    worked = importlib.import_module(f"{stem}_solutions")
    figures = importlib.import_module(f"{stem}_figures")
    expected = set(range(1, 27))
    if set(data.STATEMENTS) != expected or set(data.ANSWERS) != expected:
        raise ValueError(f"Variant {number} lacks conditions or key answers")
    if set(worked.SOLUTIONS) != set(range(21, 27)) or set(worked.CRITERIA) != set(range(21, 27)):
        raise ValueError(f"Variant {number} lacks worked solutions or criteria")
    if set(data.SOURCE_PAGES) != expected:
        raise ValueError(f"Variant {number} lacks condition-page locators")
    excerpt = source_excerpt(number, worked.SOLUTION_PAGES)
    key_page = 237 + (number - 1) // 10
    with con:
        vid = upsert_variant(
            con, excerpt, 2027, str(number), f"Сборник ФИПИ 2027-{number}", False,
        )
        for task in range(1, 27):
            locator = (
                f"{SOURCE.relative_to(ROOT).as_posix()}, печатная/PDF "
                f"стр. {data.SOURCE_PAGES[task]}; ключ стр. {key_page}, "
                f"столбец {number}"
            )
            if task >= 21:
                locator += f"; авторское решение стр. {worked.SOLUTION_PAGES[task]}"
            notes = (
                "Условие, ключ и рисунки сопоставлены с отрисованным сканом. "
                "Решение заданий 21–26 набрано в TeX по авторским страницам. "
                "Критерии изложены кратко: отдельной авторской таблицы баллов "
                "для этого варианта в сборнике нет. До полной независимой "
                "сверки статус не повышать."
            )
            if task in getattr(data, "REVIEW_NOTES", {}):
                notes += " " + data.REVIEW_NOTES[task]
            pid = upsert_problem(
                con, vid, task, 1, data.STATEMENTS[task], data.ANSWERS[task],
                worked.SOLUTIONS.get(task), worked.CRITERIA.get(task),
                TOPICS[task], locator, notes, status="needs_review",
                max_points=POINTS[task], answer_format=FORMATS[task],
            )
            labels = data.ANSWER_TABLE_LABELS.get(task)
            con.execute(
                """UPDATE problems SET answer_prefix=?,answer_unit=?,
                   answer_table_labels=? WHERE id=?""",
                (
                    data.ANSWER_PREFIX.get(task), data.ANSWER_UNITS.get(task),
                    json.dumps(labels, ensure_ascii=False) if labels else None,
                    pid,
                ),
            )
            for role, mapping in (
                ("statement_figure", figures.STATEMENT_FIGURES),
                ("solution_figure", figures.SOLUTION_FIGURES),
            ):
                for index, (page, box) in enumerate(mapping.get(task, []), 1):
                    aid = store_asset(
                        con, render_crop(pdf, page, box, figures.RENDER_SCALE),
                        ".png", "image/png",
                    )
                    link_asset(
                        con, pid, aid, role,
                        f"{SOURCE.relative_to(ROOT).as_posix()}, "
                        f"стр. {page}, рисунок {index} ({role})",
                    )
            verdict, reason = getattr(data, "RELEVANCE", {}).get(
                task,
                ("yes", "Тема, номер, баллы и формат ответа соответствуют "
                 "позиции КИМ 2027; условие сверено со сканом сборника."),
            )
            assess(
                con, pid, task, 1, int(verdict == "yes"), verdict, reason,
            )
    print(f"Imported scanned-book variant {number}: 26 tasks")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variants", nargs="+", type=int)
    args = parser.parse_args()
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The scanned source changed; recheck all text and crops")
    pdf = pdfium.PdfDocument(str(SOURCE))
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        if "answer_table_labels" not in {
            row[1] for row in con.execute("PRAGMA table_info(problems)")
        }:
            con.execute("ALTER TABLE problems ADD COLUMN answer_table_labels TEXT")
        for number in args.variants:
            if number not in range(5, 30, 2):
                raise ValueError("Expected odd variant 5–29")
            import_variant(con, pdf, number)
    finally:
        con.close()
        pdf.close()
    applied = apply_edits(DB, DEFAULT_LOG)
    print(f"Replayed {applied} site-editor text edits")


if __name__ == "__main__":
    main()

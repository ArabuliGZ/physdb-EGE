"""Import the visually transcribed first variant of the scanned 2027 book.

Run from the repository with the bundled Python runtime (pypdfium2 required).
All text and crop coordinates live in the sibling fipi_2027_1_* modules so
rerunning this importer reproduces corrections. The source PDF is not changed.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from io import BytesIO

import pypdfium2 as pdfium

from apply_site_text_edits import DEFAULT_LOG, apply_edits
from fipi_2027_1_figures import (
    RENDER_SCALE, SOLUTION_FIGURES, SOURCE_SHA256, STATEMENT_FIGURES,
)
from fipi_2027_1_solutions import CRITERIA, CRITERIA_PAGES, SOLUTIONS, SOLUTION_PAGES
from fipi_2027_1_transcription import (
    ANSWERS, ANSWER_PREFIX, ANSWER_TABLE_LABELS, ANSWER_UNITS,
    SOURCE_PAGES, STATEMENTS,
)
from import_examples import (
    DB, FORMATS, POINTS, ROOT, TOPICS, assess, link_asset, store_asset,
    upsert_problem, upsert_variant,
)


SOURCE = ROOT / "Материалы" / "ЕГЭ физика 2027 ФИПИ.pdf"


def render_crop(pdf: pdfium.PdfDocument, page_number: int,
                box: tuple[int, int, int, int]) -> bytes:
    page = pdf[page_number - 1]
    bitmap = page.render(scale=RENDER_SCALE)
    image = bitmap.to_pil()
    left, top, right, bottom = box
    if not (0 <= left < right <= image.width and
            0 <= top < bottom <= image.height):
        raise ValueError(f"Crop outside page {page_number}: {box}")
    cropped = image.crop(box)
    output = BytesIO()
    cropped.save(output, format="PNG", optimize=True)
    return output.getvalue()


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The scanned source changed; recheck all crops and text")
    expected = set(range(1, 27))
    if set(STATEMENTS) != expected or set(ANSWERS) != expected:
        raise ValueError("Variant 1 needs all 26 transcribed statements and answers")
    if set(SOLUTIONS) != set(range(21, 27)) or set(CRITERIA) != set(range(21, 27)):
        raise ValueError("Long-answer tasks need solutions and criteria")

    pdf = pdfium.PdfDocument(str(SOURCE))
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        if "answer_table_labels" not in {row[1] for row in con.execute("PRAGMA table_info(problems)")}:
            con.execute("ALTER TABLE problems ADD COLUMN answer_table_labels TEXT")
        with con:
            vid = upsert_variant(con, SOURCE, 2027, "1", "Сборник ФИПИ 2027-1", False)
            for number in range(1, 27):
                locator = (f"{SOURCE.relative_to(ROOT).as_posix()}, печатная/PDF "
                           f"стр. {SOURCE_PAGES[number]}; ключ стр. 237")
                if number >= 21:
                    locator += (f"; решение стр. {SOLUTION_PAGES[number]}; "
                                f"критерии стр. {CRITERIA_PAGES[number]}")
                notes = ("Условие и ключ сверены визуально со сканом. "
                         "Для заданий 21–26 критерии изложены кратко; "
                         "полная авторская таблица доступна в исходном PDF. "
                         "До пословной сверки критериев статус проверки не повышать.")
                if number == 24:
                    notes += (" В авторском критерии есть фраза про массу "
                              "сконденсированного пара, не относящаяся к этой задаче.")
                pid = upsert_problem(
                    con, vid, number, 1, STATEMENTS[number], ANSWERS[number],
                    SOLUTIONS.get(number), CRITERIA.get(number), TOPICS[number],
                    locator, notes, status="needs_review", max_points=POINTS[number],
                    answer_format=FORMATS[number],
                )
                labels = ANSWER_TABLE_LABELS.get(number)
                con.execute("""UPDATE problems SET answer_prefix=?,answer_unit=?,
                    answer_table_labels=? WHERE id=?""",
                    (ANSWER_PREFIX.get(number), ANSWER_UNITS.get(number),
                     json.dumps(labels, ensure_ascii=False) if labels else None, pid))
                for role, figures in (("statement_figure", STATEMENT_FIGURES),
                                      ("solution_figure", SOLUTION_FIGURES)):
                    for index, (page, box) in enumerate(figures.get(number, []), 1):
                        data = render_crop(pdf, page, box)
                        aid = store_asset(con, data, ".png", "image/png")
                        link_asset(con, pid, aid, role,
                                   f"{SOURCE.relative_to(ROOT).as_posix()}, "
                                   f"стр. {page}, рисунок {index} ({role})")
                if number == 22:
                    assess(con, pid, number, 1, 0, "partial",
                           "Механика и 2 балла совпадают, но абстрактное "
                           "равноускоренное движение не отвечает практическому "
                           "сюжету позиции 22 в пояснении к КИМ 2027.")
                else:
                    assess(con, pid, number, 1, 1, "yes",
                           "Тема, номер, баллы и формат ответа соответствуют "
                           "позиции КИМ 2027; условие сверено со сканом сборника.")
    finally:
        con.close()
        pdf.close()

    # The site editor is authoritative for any previously adjusted task text.
    applied = apply_edits(DB, DEFAULT_LOG)
    print(f"Imported book variant 1: 26 tasks; replayed {applied} site text edits")


if __name__ == "__main__":
    main()

"""Compare 2022 statement prose with independently rendered source PDFs.

Requires PyMuPDF (``pip install pymupdf``) and four DOCX-to-PDF exports in
``tmp/2022-review`` named like their source DOCX files. The PDF exports are
review inputs, not part of the published database.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pymupdf
from docx import Document

from import_2022 import (FLOATING_STARTS, SOURCE_ROOT, SOURCES,
                         extract_blocks, numbered)
from import_examples import DB, ROOT


OUTPUT = ROOT / "tmp/2022-review/statement_pdf_audit.csv"


def tokens(value: str) -> list[str]:
    return re.findall(r"[а-яa-z0-9]{3,}", value.lower().replace("ё", "е"))


def ngrams(value: list[str], width: int = 3) -> set[tuple[str, ...]]:
    return set(zip(*(value[offset:] for offset in range(width))))


def prose_ngrams(value: str) -> set[tuple[str, ...]]:
    # Never join words on opposite sides of an equation: the PDF has the
    # original mathematical content between them.
    pieces = re.split(r"\\\(.*?\\\)|\\\[.*?\\\]|\\(?:begin|end)\{tabular\}(?:\{[^}]*\})?|[&\\]",
                      value, flags=re.S)
    return set().union(*(ngrams(tokens(piece)) for piece in pieces))


def main() -> None:
    con = sqlite3.connect(DB)
    report = []
    for variant, name in SOURCES.items():
        doc = Document(SOURCE_ROOT / name)
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs]
        end = next(index for index, line in enumerate(paragraphs)
                   if line.startswith("Система оценивания экзаменационной работы"))
        starts = numbered(doc, 40, end, 1, 30)
        starts.update(FLOATING_STARTS[variant])
        pdf = pymupdf.open(ROOT / "tmp/2022-review" / name.replace(".docx", ".pdf"))
        pages = [tokens(page.get_text()) for page in pdf]
        for number in range(1, 31):
            embedded = []
            raw, _ = extract_blocks(doc, starts[number], starts.get(number + 1, end), embedded)
            lead = ngrams(tokens(raw)[:65])
            first_scores = [len(lead & ngrams(page)) for page in pages]
            page_index = max(range(len(pages)), key=lambda index: first_scores[index])
            statement, assets = con.execute("""SELECT p.statement,
                (SELECT COUNT(*) FROM problem_assets pa WHERE pa.problem_id=p.id
                 AND pa.role='statement_figure') FROM problems p
                JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2022
                AND v.variant_number=? AND p.problem_number=?""",
                (str(variant), number)).fetchone()
            expected = prose_ngrams(statement)
            nearby = list(pages[page_index - 1]) if page_index else []
            nearby += pages[page_index]
            if page_index + 1 < len(pages):
                nearby += pages[page_index + 1]
            actual = ngrams(nearby)
            overlap = len(expected & actual)
            recall = overlap / len(expected) if expected else 1.0
            report.append((variant, number, page_index + 1, len(expected), overlap,
                           round(recall, 4), assets, len(embedded)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("variant", "task", "pdf_page", "prose_trigrams", "matched",
                         "recall", "statement_figures", "embedded_formulas"))
        writer.writerows(report)
    print("Tasks:", len(report), "under 90%:", sum(row[5] < .9 for row in report))
    for row in report:
        if row[5] < .9:
            print("2022-%s #%s PDF p.%s prose recall %.1f%% (%s/%s), figures %s" %
                  (row[0], row[1], row[2], row[5] * 100, row[4], row[3], row[6]))


if __name__ == "__main__":
    main()

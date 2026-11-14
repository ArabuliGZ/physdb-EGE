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
            statement, criteria, assets = con.execute("""SELECT p.statement,p.criteria,
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
            page_text = " ".join(pdf[index].get_text() for index in
                                 range(max(0, page_index - 1), min(len(pdf), page_index + 2)))
            tables = re.findall(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}",
                                statement, flags=re.S)
            table_text = " ".join(tables)
            table_numbers = {value.replace("{,}", ",") for value in re.findall(
                r"\d+(?:\{,\}\d+|,\d+|\.\d+)?", table_text)}
            table_words = {value.lower().replace("ё", "е") for value in re.findall(
                r"[\u0400-\u04FF]{3,}", table_text)}
            normalized_page = page_text.lower().replace("ё", "е")
            missing_values = [value for value in table_numbers
                              if value not in page_text and value.replace(",", ".") not in page_text]
            missing_words = [value for value in table_words if value not in normalized_page]
            criteria_recall = ""
            if criteria:
                expected_criteria = prose_ngrams(criteria)
                page_ngrams = [ngrams(page) for page in pages]
                nearby_scores = [len(expected_criteria & set().union(*(
                    page_ngrams[index] for index in range(max(0, center - 1),
                                                              min(len(pages), center + 2)))))
                    for center in range(len(pages))]
                criteria_recall = round(max(nearby_scores) / len(expected_criteria), 4)
            report.append((variant, number, page_index + 1, len(expected), overlap,
                           round(recall, 4), assets, len(embedded), len(tables),
                           len(table_numbers) + len(table_words), len(missing_values) + len(missing_words),
                           criteria_recall))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("variant", "task", "pdf_page", "prose_trigrams", "matched",
                         "recall", "statement_figures", "embedded_formulas",
                         "tables", "table_tokens", "missing_table_tokens",
                         "criteria_prose_recall"))
        writer.writerows(report)
    print("Tasks:", len(report), "under 90%:", sum(row[5] < .9 for row in report))
    print("Tables:", sum(row[8] for row in report), "missing cell tokens:",
          sum(row[10] for row in report))
    print("Criteria:", sum(bool(row[11] != "") for row in report), "under 90%:",
          sum(row[11] != "" and row[11] < .9 for row in report))
    if any(row[10] for row in report):
        raise ValueError("A table token is absent from the source PDF page")
    if any(row[11] != "" and row[11] < .9 for row in report):
        raise ValueError("Criteria prose is incomplete against the source PDF")
    for row in report:
        if row[5] < .9:
            print("2022-%s #%s PDF p.%s prose recall %.1f%% (%s/%s), figures %s" %
                  (row[0], row[1], row[2], row[5] * 100, row[4], row[3], row[6]))


if __name__ == "__main__":
    main()

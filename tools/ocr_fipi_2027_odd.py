"""Render and OCR odd scanned-book conditions for manual source verification.

OCR output is a draft only. Never import it without visual correction.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pypdfium2 as pdfium

from import_examples import ROOT


SOURCE = ROOT / "Материалы" / "ЕГЭ физика 2027 ФИПИ.pdf"
OUTPUT = ROOT / "tmp" / "pdfs" / "fipi2027_odd_ocr"
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA = ROOT / "tmp" / "pdfs" / "tessdata"
STARTS = {
    1: 13, 2: 21, 3: 29, 4: 37, 5: 45, 6: 53, 7: 61, 8: 69,
    9: 77, 10: 84, 11: 91, 12: 99, 13: 107, 14: 114, 15: 121,
    16: 129, 17: 137, 18: 144, 19: 151, 20: 158, 21: 165,
    22: 172, 23: 179, 24: 186, 25: 193, 26: 200, 27: 207,
    28: 214, 29: 221, 30: 229, 31: 237,
}


def render_variant(pdf: pdfium.PdfDocument, number: int) -> None:
    directory = OUTPUT / f"variant_{number:02}"
    directory.mkdir(parents=True, exist_ok=True)
    pages = list(range(STARTS[number], STARTS[number + 1]))
    for page_number in pages:
        page = pdf[page_number - 1]
        image = page.render(scale=2.1).to_pil()
        png = directory / f"page_{page_number:03}.png"
        image.save(png)
        page.close()
        proc = subprocess.run(
            [
                TESSERACT, str(png), "stdout", "--tessdata-dir", str(TESSDATA),
                "-l", "rus+eng", "--psm", "3",
            ],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False,
        )
        (directory / f"page_{page_number:03}.txt").write_text(
            proc.stdout, encoding="utf-8",
        )
        print(f"Variant {number}: page {page_number} OCR", flush=True)
    (directory / "index.json").write_text(
        json.dumps({"variant": number, "pages": pages}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variants", nargs="+", type=int)
    args = parser.parse_args()
    pdf = pdfium.PdfDocument(str(SOURCE))
    try:
        for number in args.variants:
            if number not in range(5, 30, 2):
                raise ValueError("Expected odd variants 5–29")
            render_variant(pdf, number)
    finally:
        pdf.close()


if __name__ == "__main__":
    main()

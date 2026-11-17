"""OCR the scanned answer section to locate worked solutions for variants.

The OCR output is an index only; formulas must be checked on rendered pages.
"""
from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pypdfium2 as pdfium

from index_fipi_2027_book import SOURCE, TESSDATA, TESSERACT
from import_examples import ROOT

OUTPUT = ROOT / "tmp" / "pdfs" / "fipi2027_solutions_ocr"


def ocr(number: int) -> tuple[int, str]:
    image = OUTPUT / f"page_{number:03}.png"
    result = subprocess.run(
        [TESSERACT, str(image), "stdout", "--tessdata-dir", str(TESSDATA),
         "-l", "rus+eng", "--psm", "6"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    text = result.stdout
    (OUTPUT / f"page_{number:03}.txt").write_text(text, encoding="utf-8")
    return number, text


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(SOURCE))
    pages = range(240, len(pdf) + 1)
    for number in pages:
        path = OUTPUT / f"page_{number:03}.png"
        if path.exists():
            continue
        page = pdf[number - 1]
        page.render(scale=1.8).to_pil().save(path)
        page.close()
    pdf.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = sorted(pool.map(ocr, pages))
    for number, text in entries:
        matches = re.findall(r"ВАРИАНТ\s*(\d{1,2})", text, re.I)
        if matches:
            print(number, ",".join(matches), flush=True)


if __name__ == "__main__":
    main()

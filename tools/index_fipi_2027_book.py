"""Locate each scanned-book variant start and inspect answer/solution sections.

The source is image-only. This index is an OCR aid, not a verified transcription.
"""
from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pypdfium2 as pdfium

from import_examples import ROOT


SOURCE = ROOT / "Материалы" / "ЕГЭ физика 2027 ФИПИ.pdf"
OUTPUT = ROOT / "tmp" / "pdfs" / "fipi2027_index"
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA = ROOT / "tmp" / "pdfs" / "tessdata"


def read_header(page_number: int) -> tuple[int, str]:
    path = OUTPUT / f"header_{page_number:03}.png"
    proc = subprocess.run(
        [
            TESSERACT, str(path), "stdout", "--tessdata-dir", str(TESSDATA),
            "-l", "rus+eng", "--psm", "6",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    return page_number, proc.stdout.strip()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(SOURCE))
    for page_number in range(13, 237):
        page = pdf[page_number - 1]
        image = page.render(scale=1.5).to_pil()
        width, _ = image.size
        image.crop((int(width * 0.08), 120, int(width * 0.92), 320)).save(
            OUTPUT / f"header_{page_number:03}.png"
        )
        page.close()
    pdf.close()
    with ThreadPoolExecutor(max_workers=4) as executor:
        entries = sorted(executor.map(read_header, range(13, 237)))
    starts = {}
    for page_number, header in entries:
        match = re.search(r"ВАРИАНТ\s*(\d{1,2})", header, flags=re.I)
        if match and "Часть 1" in header:
            number = int(match.group(1))
            if 1 <= number <= 30:
                starts.setdefault(number, page_number)
    (OUTPUT / "headers.json").write_text(
        json.dumps(dict(entries), ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUTPUT / "starts.json").write_text(
        json.dumps(starts, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(starts, ensure_ascii=False))


if __name__ == "__main__":
    main()

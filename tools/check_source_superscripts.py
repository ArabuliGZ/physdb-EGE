"""Compare numeric Word superscripts in source task paragraphs with imported TeX."""
from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def parsed_path(year: int, variant: str, source: str) -> Path:
    if year == 2024 and variant.startswith("1-"):
        return ROOT / "tmp" / "normalized-doc" / "2024 - 1" / f"{variant[-1]}.docx"
    if year == 2025 and variant.startswith("1-"):
        return ROOT / "tmp" / "normalized-doc" / "2025 - 1" / f"éáÓ¿á¡Ô {variant[-1]}.docx"
    if year == 2025 and variant.startswith("2-"):
        name = {"1": "110271", "2": "110270", "3": "110269"}[variant[-1]]
        return ROOT / "tmp" / "normalized-doc" / "2025 - 2" / f"{name}.docx"
    return ROOT / source


def superscripts(paragraph) -> Counter[str]:
    runs = []
    for run in paragraph.iter(W + "r"):
        text = "".join(node.text or "" for node in run.iter(W + "t"))
        align = run.find("./" + W + "rPr/" + W + "vertAlign")
        if text:
            runs.append((text, align.get(W + "val") if align is not None else ""))
    found: Counter[str] = Counter()
    for index, (text, align) in enumerate(runs):
        if align != "superscript":
            continue
        exponent = text.replace("–", "-").replace("−", "-").strip()
        prefix = "".join(item[0] for item in runs[max(0, index - 2):index])
        if re.fullmatch(r"-?\d+", exponent) and re.search(r"10[·.\s]*$", prefix):
            found[exponent] += 1
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    con = sqlite3.connect(DB)
    misses = 0
    checked = 0
    for year, variant, source in con.execute(
        "SELECT exam_year, variant_number, source_path FROM variants WHERE exam_year BETWEEN 2022 AND 2026"
    ):
        path = parsed_path(year, variant, source)
        if not path.is_file():
            print(f"Source unavailable: {path}")
            misses += 1
            continue
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = root.find(W + "body").findall(W + "p")
        for number, statement, locator in con.execute(
            """SELECT p.problem_number,p.statement,p.source_locator FROM problems p
            JOIN variants v ON v.id=p.variant_id
            WHERE v.exam_year=? AND v.variant_number=?""", (year, variant)
        ):
            interval = re.search(r"paragraphs (\d+)[–-](\d+)", locator or "")
            if not interval:
                continue
            expected: Counter[str] = Counter()
            for paragraph in paragraphs[int(interval[1]):int(interval[2]) + 1]:
                expected.update(superscripts(paragraph))
            for exponent, count in expected.items():
                tex = "10^{" + exponent + "}"
                actual = statement.count(tex) + statement.count("10^" + exponent)
                checked += count
                if actual < count:
                    print(f"{year}-{variant} task {number}: source has {count} x {tex}; imported text has {actual}")
                    misses += count - actual
    print(f"Source superscripts checked: {checked}; missing: {misses}")
    if misses and args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

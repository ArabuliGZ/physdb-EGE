"""Restore answer-field units from the original DOCX paragraph ranges.

The statement normalizer intentionally removes printed lines such as
``Ответ: ______ см.``.  This command reads those lines from the source Word
documents and stores only their suffix in ``problems.answer_unit``.  It uses
the paragraph locator already saved for every imported problem and never
infers a unit from the answer key.
"""
from __future__ import annotations

import argparse
import collections
import re
import sqlite3
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LOCATOR = re.compile(r"paragraphs\s+(\d+)[–-](\d+)")
ANSWER = re.compile(r"^\s*Ответ\s*:\s*(.*?)\s*$", re.IGNORECASE)
SUPERSCRIPTS = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
SUBSCRIPTS = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")


def source_docx(year: int, variant: str, source_path: str) -> Path | None:
    """Resolve the DOCX whose paragraph numbers were saved by the importer."""
    series, _, number = variant.partition("-")
    if year == 2024 and series == "1":
        return ROOT / "tmp" / "normalized-doc" / "2024 - 1" / f"{number}.docx"
    if year == 2025 and series == "1":
        return ROOT / "tmp" / "normalized-doc" / "2025 - 1" / f"éáÓ¿á¡Ô {number}.docx"
    if year == 2025 and series == "2":
        filename = {"1": "110271", "2": "110270", "3": "110269"}.get(number)
        return (ROOT / "tmp" / "normalized-doc" / "2025 - 2" / f"{filename}.docx"
                if filename else None)
    path = ROOT / Path(source_path.replace("\\", "/"))
    return path if path.suffix.lower() == ".docx" else None


def run_text(run: ET.Element) -> str:
    text = "".join((node.text or "") for node in run.iter(W + "t"))
    vert = run.find(W + "rPr/" + W + "vertAlign")
    value = vert.get(W + "val") if vert is not None else ""
    if value == "superscript":
        return text.translate(SUPERSCRIPTS)
    if value == "subscript":
        return text.translate(SUBSCRIPTS)
    return text


def element_text(element: ET.Element) -> str:
    parts = []
    for node in element.iter():
        if node.tag == W + "r":
            parts.append(run_text(node))
        elif node.tag == W + "tab":
            parts.append(" ")
    return "".join(parts).replace("\u00a0", " ").strip()


def source_blocks(path: Path) -> tuple[list[ET.Element], dict[int, int]]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        raise ValueError(f"Word body missing: {path}")
    blocks = list(body)
    paragraph_to_block = {paragraph: block for paragraph, block in enumerate(
        index for index, element in enumerate(blocks) if element.tag == W + "p")}
    return blocks, paragraph_to_block


def printed_answer_line(blocks: list[ET.Element], paragraph_to_block: dict[int, int],
                        first: int, last: int) -> str | None:
    start = paragraph_to_block.get(first)
    if start is None:
        return None
    next_block = paragraph_to_block.get(last + 1, len(blocks))
    for block in blocks[start:next_block]:
        candidates = [block] if block.tag == W + "p" else list(block.iter(W + "p"))
        for paragraph in candidates:
            text = element_text(paragraph)
            if ANSWER.match(text):
                return text
    return None


def field_parts_from_line(line: str) -> tuple[str, str]:
    payload = ANSWER.match(line).group(1).strip().rstrip(".;")
    blanks = list(re.finditer(r"(?:[_…]{3,}|\s{3,})", payload))
    if not blanks:
        # A Word underline can be a border rather than text.  In that case a
        # short compact payload is the suffix printed after the invisible line.
        prefix, suffix = "", payload
    else:
        prefix = payload[:blanks[0].start()].strip(" (.,;")
        suffix = payload[blanks[-1].end():].strip()
        suffix = re.sub(r"^[),;\s]+", "", suffix)
        suffix = re.sub(r"[.;\s]+$", "", suffix)
    suffix = (suffix.replace("м/c", "м/с").replace("м2", "м²").replace("м3", "м³")
              .replace("см2", "см²").replace("см3", "см³")
              .replace("H/м", "Н/м").replace("oC", "°C"))
    suffix = re.sub(r"\s*[∙⋅·]\s*", "·", suffix)
    if prefix and (len(prefix) > 40 or not re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9\s/()-]+", prefix)):
        raise ValueError(f"Unrecognised answer-field prefix: {line!r}")
    if suffix and (len(suffix) > 32 or not re.fullmatch(
            r"[A-Za-zА-Яа-яЁё°%/·⋅.()²³⁻⁰¹⁴⁵⁶⁷⁸⁹\s-]+", suffix)):
        raise ValueError(f"Unrecognised answer-field suffix: {line!r}")
    return prefix, suffix


def ensure_column(con: sqlite3.Connection) -> None:
    columns = {row[1] for row in con.execute("PRAGMA table_info(problems)")}
    if "answer_prefix" not in columns:
        con.execute("ALTER TABLE problems ADD COLUMN answer_prefix TEXT")
    if "answer_unit" not in columns:
        con.execute("ALTER TABLE problems ADD COLUMN answer_unit TEXT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="update the SQLite database")
    args = parser.parse_args()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    if args.write:
        ensure_column(con)
    rows = con.execute("""SELECT p.id,p.problem_number,p.answer_format,p.source_locator,
        v.exam_year,v.variant_number,v.source_path
        FROM problems p JOIN variants v ON v.id=p.variant_id
        ORDER BY v.exam_year,v.variant_number,p.problem_number,p.alternative_number""").fetchall()
    documents: dict[Path, tuple[list[ET.Element], dict[int, int]]] = {}
    counts: collections.Counter[tuple[int, str]] = collections.Counter()
    lines = missing = 0
    for row in rows:
        locator = LOCATOR.search(row["source_locator"])
        path = source_docx(row["exam_year"], row["variant_number"], row["source_path"])
        if not locator or path is None or not path.is_file():
            continue
        if args.write:
            con.execute("UPDATE problems SET answer_prefix=NULL,answer_unit=NULL WHERE id=?",
                        (row["id"],))
        if path not in documents:
            documents[path] = source_blocks(path)
        line = printed_answer_line(*documents[path], int(locator.group(1)), int(locator.group(2)))
        if line is None:
            if row["answer_format"] not in ("qualitative", "worked_solution", "matching"):
                missing += 1
            continue
        lines += 1
        prefix, unit = field_parts_from_line(line)
        label = " ".join(part for part in (prefix, "___", unit) if part)
        counts[(row["exam_year"], label or "без подписи")] += 1
        if args.write:
            con.execute("UPDATE problems SET answer_prefix=?,answer_unit=? WHERE id=?",
                        (prefix, unit, row["id"]))
    if args.write:
        con.commit()
    print(f"Checked {len(documents)} DOCX files; found {lines} printed answer fields; "
          f"short-answer fields without a paragraph line: {missing}.")
    for (year, unit), count in sorted(counts.items()):
        print(f"{year}: {unit} — {count}")


if __name__ == "__main__":
    main()

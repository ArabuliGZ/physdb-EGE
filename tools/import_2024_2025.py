"""Stage all 2024–2025 Demidova variants from their original source files.

Old .doc sources are read through temporary Word-converted DOCX copies made by
convert_legacy_doc.ps1. The original path/hash is stored in the database.
Every extracted task remains needs_review until a visual source comparison.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from docx import Document

from import_examples import DB, ROOT, TOPICS, upsert_problem, upsert_variant
from import_2026_remaining import (add_figures, answer_key, extract_blocks,
                                    normalize_statement, numbered_paragraphs,
                                    review_sections)


SOURCE_ROOT = ROOT / "Материалы" / "ЕГЭ от Демидовой"
NORMALIZED = ROOT / "tmp" / "normalized-doc"
# The narrow topic changes between editions and even between variants.
EXTENDED_TOPICS = {
    "2024-1-1": {21: "electrodynamics", 22: "mechanics", 23: "molecular"},
    "2024-1-2": {21: "molecular", 22: "mechanics", 23: "electrodynamics"},
    "2024-1-3": {21: "electrodynamics", 22: "mechanics", 23: "molecular"},
    "2024-1-4": {21: "electrodynamics", 22: "mechanics", 23: "molecular"},
    "2024-2-1": {21: "electrodynamics", 22: "mechanics", 23: "molecular"},
    "2024-2-2": {21: "molecular", 22: "mechanics", 23: "electrodynamics"},
    "2024-2-3": {21: "molecular", 22: "mechanics", 23: "electrodynamics"},
    "2024-2-4": {21: "molecular", 22: "mechanics", 23: "electrodynamics"},
    "2025-1-1": {21: "electrodynamics", 22: "mechanics", 23: "molecular"},
    "2025-1-2": {21: "mechanics", 22: "molecular", 23: "electrodynamics"},
    "2025-1-3": {21: "molecular", 22: "mechanics", 23: "electrodynamics"},
    "2025-2-1": {21: "electrodynamics", 22: "mechanics", 23: "molecular"},
    "2025-2-2": {21: "mechanics", 22: "molecular", 23: "electrodynamics"},
    "2025-2-3": {21: "molecular", 22: "mechanics", 23: "electrodynamics"},
}


def sources():
    for year, set_number, count in ((2024, 1, 4), (2024, 2, 4), (2025, 1, 3), (2025, 2, 3)):
        folder = f"{year} - {set_number}"
        for number in range(1, count + 1):
            if year == 2024 and set_number == 1:
                name = str(number)
                original = SOURCE_ROOT / folder / f"{name}.doc"
                parsed = NORMALIZED / folder / f"{name}.docx"
                companions = [("answer_key", SOURCE_ROOT / folder / f"{name}_ключ.doc"),
                              ("criteria", SOURCE_ROOT / folder / f"{name}_крит.doc")]
            elif year == 2024:
                original = SOURCE_ROOT / folder / f"вариант {number}.docx"
                parsed = original
                pdf = original.with_suffix(".pdf")
                companions = [("pdf_copy", pdf)] if pdf.is_file() else []
            elif set_number == 1:
                name = f"éáÓ¿á¡Ô {number}"
                original = SOURCE_ROOT / folder / f"{name}.doc"
                parsed = NORMALIZED / folder / f"{name}.docx"
                companions = []
            else:
                name = {1: "110271", 2: "110270", 3: "110269"}[number]
                original = SOURCE_ROOT / folder / f"{name}.doc"
                parsed = NORMALIZED / folder / f"{name}.docx"
                companions = []
            yield year, set_number, number, original, parsed, companions


def register_companion(con, vid: str, role: str, path: Path) -> None:
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    con.execute("""INSERT INTO variant_sources
        (variant_id,source_role,source_path,source_sha256,source_kind)
        VALUES (?,?,?,?,?) ON CONFLICT(variant_id,source_role,source_path)
        DO UPDATE SET source_sha256=excluded.source_sha256""",
        (vid, role, path.relative_to(ROOT).as_posix(), sha, path.suffix[1:].lower()))


def key_for_2024_1(path: Path) -> dict[int, str]:
    doc = Document(path)
    table = next((t for t in doc.tables if len(t.rows) == 21 and len(t.columns) == 2), None)
    if table is None:
        raise ValueError(f"Answer table missing: {path}")
    answers = {int(row.cells[0].text.strip()): row.cells[1].text.strip() for row in table.rows[1:]}
    if set(answers) != set(range(1, 21)):
        raise ValueError(f"Incomplete answer key: {path}")
    return answers


def repair_floating(doc, starts: dict[int, int], end: int) -> None:
    for n in range(2, 27):
        stop = starts[n + 1] if n < 26 else end
        raw, _ = extract_blocks(doc, starts[n], stop)
        if normalize_statement(raw):
            continue
        preceding_answers = [i for i in range(starts[n - 1] + 1, starts[n])
                             if doc.paragraphs[i].text.strip().startswith("Ответ:")]
        if len(preceding_answers) >= 2:
            starts[n] = preceding_answers[-2] + 1
            continue
        preceding = [i for i in range(starts[n - 1] + 1, starts[n])
                     if doc.paragraphs[i].text.strip()
                     and not doc.paragraphs[i].text.strip().startswith("Ответ:")]
        if not preceding:
            raise ValueError(f"Cannot repair floating task label {n}")
        starts[n] = preceding[-1]


def import_one(con, year: int, set_number: int, number: int,
               original: Path, parsed: Path, companions: list[tuple[str, Path]]) -> None:
    if not original.is_file() or not parsed.is_file():
        raise FileNotFoundError(f"Missing source or normalized copy: {original}")
    label = f"{year}-{set_number}-{number}"
    doc = Document(parsed)
    if year == 2024 and set_number == 1:
        end = len(doc.paragraphs)
        criteria_doc = Document(NORMALIZED / f"{year} - {set_number}" / f"{number}_крит.docx")
        review = numbered_paragraphs(criteria_doc, 0, len(criteria_doc.paragraphs), 21)
        answers = key_for_2024_1(NORMALIZED / f"{year} - {set_number}" / f"{number}_ключ.docx")
    else:
        end = next(i for i, p in enumerate(doc.paragraphs)
                   if "Критерии оценивания выполнения заданий с развёрнутым ответом" in p.text)
        criteria_doc = doc
        review = numbered_paragraphs(doc, end + 1, len(doc.paragraphs), 21)
        answers = answer_key(doc)
    starts = numbered_paragraphs(doc, 0, end)
    repair_floating(doc, starts, end)
    if label == "2024-2-2":
        # Word anchors the floating label 8 before the prose of task 7.
        # The printed PDF confirms that task 7 ends after paragraph 156.
        starts[7] = 145
        starts[8] = 157
    vid = upsert_variant(con, original, year, f"{set_number}-{number}",
                         f"Демидова {year}, серия {set_number}, вариант {number}", False)
    for role, companion in companions:
        register_companion(con, vid, role, companion)
    for n in range(1, 27):
        start = starts[n]
        stop = starts[n + 1] if n < 26 else end
        raw, statement_figures = extract_blocks(doc, start, stop)
        statement = normalize_statement(raw)
        if not statement:
            raise ValueError(f"Empty statement: {label} task {n}")
        solution = criteria = None
        solution_figures = []
        if n >= 21:
            rstop = review[n + 1] if n < 26 else len(criteria_doc.paragraphs)
            solution, criteria, solution_figures = review_sections(criteria_doc, review[n], rstop)
            if not solution or not criteria:
                raise ValueError(f"Missing solution/criteria: {label} task {n}")
        topic = EXTENDED_TOPICS[label].get(n, TOPICS[n])
        locator = f"{'Converted DOC' if parsed != original else 'DOCX'} paragraphs {start}–{stop - 1}"
        notes = "Автоматическая первичная расшифровка; необходима визуальная сверка формул, таблиц, рисунков и ключа."
        if parsed != original:
            notes += " Абзацы указаны по временной DOCX-копии исходного DOC."
        if n >= 21:
            notes += " Решение и критерии — черновая расшифровка; отдельно проверьте по авторскому документу."
        pid = upsert_problem(con, vid, n, 1, statement, answers.get(n), solution,
                             criteria, topic, locator, notes, "needs_review")
        if (year, set_number, number, n) == (2024, 2, 1, 22):
            con.execute("UPDATE problems SET answer_format='qualitative' WHERE id=?", (pid,))
        add_figures(con, pid, statement_figures, "statement_figure", locator)
        add_figures(con, pid, solution_figures, "solution_figure", f"{label} criteria for {n}")
    print(f"{label}: 26 tasks, 20 key answers, 6 solutions and rubrics")


def main() -> None:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    with con:
        for spec in sources():
            import_one(con, *spec)
    print("total tasks", con.execute("SELECT COUNT(*) FROM problems").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()

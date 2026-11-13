"""Import Demidova 2026 training variants 2–4 from their source DOCX files.

This is a source-backed first pass. Embedded equation pictures are marked for
review instead of being silently dropped. No unreviewed task is marked verified.
"""
from __future__ import annotations

import re
import sqlite3
import hashlib
import json
from io import BytesIO
from pathlib import Path

from verified_solutions import VERIFIED_SOLUTIONS

from docx import Document
from PIL import Image

from import_examples import (ASSETS, DB, ROOT, FORMATS, POINTS, TOPICS,
                             key, link_asset, store_asset, upsert_problem,
                             upsert_variant)
from tex_format import format_quantities
from text_repairs import repair_text


SOURCE_DIR = ROOT / "Материалы" / "ЕГЭ от Демидовой" / "2026"
FORMULA_ASSETS = ROOT / "assets" / "formulas"
VERIFIED_FORMULAS = json.loads((ROOT / "tools" / "verified_formulas.json").read_text(encoding="utf-8"))
SOURCE_MATHML_FORMULAS = json.loads((ROOT / "tools" / "source_mathml_formulas.json").read_text(encoding="utf-8"))
# Source decorations, broken Word/OLE previews, and equation images that
# must not be displayed as task diagrams.
NON_FIGURE_PNG_SHA = {
    "6cbc340c9e59623ce9822fe2d3286c105a0017e356ebaeb2d15ac0a5b70b0162",
    "d21e55e0009e99101ea903eae386f861ebf16d3ccc1d0cb45f450ef4160e0c77",
    "e9ef87984372178e0c6ced32bdf3aedaa967006232a8ea7cc7ccf070713561ec",
    "81d4624133ea90aaef1a9fbe398a2f30b002c06e367277f005c01c7283dc760a",
    "683caffaf619d6b84f2c7afe1652ae22ae141ab2e742072a49ed79f461381dd8",
    "ed554e1ca92c02fb8e81dffe7ff3ca06b1be421401f3e115a8f80e0136c1ec27",
    "dce35d55aad3baadb6cccfe1026902bae8b0cf25aef813ba4e0095995e1ac35c",
    "0887b216a4c506a918934b63961472ca3ae615d136f5d29bf66df20533d6174c",
    "27664dddbc01681fcf997e357d6ee413c8760833c056e0bffa87e488d49e12ea",
    "5678efd4462af8d28cec0a09b1956e6b752acecd8f4e0e7e5c9c5a48cb92a252",
    "679e4b465f1af0dbe6e5bf499d243b94832e4a12da13ff3985a965244556c0c3",
    "72b181555f3a6e1e8371dd9ccdf5b3ae9974341547a87e785116f4c7e1fbbadd",
    "80b5d1a444b2bae00cb2a8f67db21fa4848a0c5de4bc453120a8b9588eda8849",
    "9214c0a201cd05a182324cb16a3ef374c40cd3d607db8b4e93093d55145e62f9",
    "b8ac65a4093d06a45a2992bd0b58da410139b35a93784a3f632d149b1e706f45",
}
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MISSING_FORMULA = "[формула в исходном DOCX — требуется сверка]"
GENERAL_END = ("Полное правильное решение каждой из задач 22–26",
               "Проверьте, чтобы каждый ответ был записан рядом",
               "Не забудьте перенести все ответы",
               "Система оценивания экзаменационной работы")
# Transcribed from the embedded WMF pictures and checked against temporary
# Word-rendered PDFs. Order follows the images in each source task.
CURATED_INLINE = {
    (2, 1): [r"\(v\)"],
    (2, 2): [r"\(\frac{r}{2}\)"],
    (2, 16): [r"\({}^{234}_{90}\mathrm{Th}\)"],
    (2, 23): [r"\(v_0=\)"],
    (2, 24): [r"\(\eta=20\%\)", r"\(A_{12}\)", r"\(A'_{31}\)"],
    (2, 26): [r"\(v_0\)", r"\(v_1\)"],
    (3, 1): [r"\(v_x\)", r"\(a_x\)"],
    (3, 4): [r"\(\vec F_1\)", r"\(\vec F_2\)", r"\(\vec F_1\)"],
    (3, 5): [r"\(v_x\)", r"\(F_x\)"],
    (3, 16): [r"\({}^{4}_{2}\mathrm{He}+{}^{7}_{3}\mathrm{Li}\to{}^{A}_{Z}X+{}^{1}_{0}\mathrm{n}\)",
              r"\({}^{A}_{Z}X\)"],
    (3, 22): [r"\(\vec F\),"],
    (3, 23): [r"\(m=1{,}6\cdot10^{-25}\,\text{кг}\)", r"\(B=0{,}5\,\text{Тл}\).",
              r"\(W=8\cdot10^{-14}\,\text{Дж}\)"],
    (3, 24): [r"\(\varphi=60\%\)"],
    (4, 1): [r"\(v_x\)", r"\(a_x\)"],
    (4, 6): [r"\(t=0\)", r"\(\vec v_0\)", r"\(\alpha\)", r"\(y=0\)"],
    (4, 12): [r"\(\vec B\)"],
    (4, 17): [r"\(E_1-E_0\)", r"\(E_2-E_0\)", r"\(E_3-E_0\)", r"\(E_4-E_0\)"],
    (4, 24): [r"\(H=25\)"],
    (4, 25): [r"\(c=2\)", r"\(h=4\)", r"\(F=10\)"],
}


def insert_curated_inline(number: int, task: int, statement: str) -> str:
    replacements = CURATED_INLINE.get((number, task), [])
    count = statement.count(MISSING_FORMULA)
    if count != len(replacements):
        raise ValueError(f"Embedded formula count changed in 2026-{number} task {task}: {count} != {len(replacements)}")
    for replacement in replacements:
        statement = statement.replace(MISSING_FORMULA, replacement, 1)
    statement = statement.replace(r"\text{Дж}\)Дж", r"\text{Дж}\)")
    for symbol, value, unit in (("H", "25", "м"), ("c", "2", "см"),
                                ("h", "4", "см"), ("F", "10", "см")):
        statement = statement.replace(
            rf"\({symbol}={value}\) {unit}",
            rf"\({symbol}={value}\,\text{{{unit}}}\)",
        )
    return statement


def numbered_paragraphs(doc, begin: int, end: int, first_number: int = 1) -> dict[int, int]:
    """Find consecutive numbered task headings in a document interval."""
    positions = {}
    cursor = begin
    for n in range(first_number, 27):
        found = next((i for i in range(cursor, end)
                      if doc.paragraphs[i].text.strip() == str(n)), None)
        if found is None:
            raise ValueError(f"Cannot locate task {n} after paragraph {cursor}")
        positions[n] = found
        cursor = found + 1
    return positions


def paragraph_interval(doc, first: int, last_exclusive: int):
    body = list(doc.element.body)
    paragraphs = [p._element for p in doc.paragraphs]
    start = body.index(paragraphs[first])
    end = body.index(paragraphs[last_exclusive]) if last_exclusive < len(paragraphs) else len(body)
    return body[start:end]


def image_for_blip(doc, blip):
    rid = blip.get(R_NS + "embed") or blip.get(R_NS + "id")
    if not rid or rid not in doc.part.related_parts:
        return None
    part = doc.part.related_parts[rid]
    try:
        im = Image.open(BytesIO(part.blob))
        width, height = im.size
        if im.format == "JPEG" and (width, height) == (108, 108):
            return None  # Shared exclamation-mark instruction icon.
        # The short WMF objects are Equation Editor glyphs. A diagram must
        # occupy a meaningful two-dimensional area in the source.
        is_figure = (width >= 70 and height >= 70) or (width >= 50 and height >= 80)
        return part.blob, is_figure, (width, height)
    except Exception:
        return part.blob, False, (0, 0)


def formula_marker(index: int) -> str:
    letters = ""
    while True:
        letters = chr(65 + index % 26) + letters
        index = index // 26 - 1
        if index < 0:
            return f"[[SRCFORMULA{letters}]]"


def element_text(element, doc, figures: list[bytes],
                 formulas: list[tuple[bytes, tuple[int, int]]] | None = None) -> str:
    out = []
    previous_image: bytes | None = None
    for node in element.iter():
        if node.tag.endswith("}t") and node.text:
            out.append(node.text)
            previous_image = None
        elif node.tag.endswith("}tab"):
            out.append(" ")
            previous_image = None
        elif node.tag.endswith("}blip") or node.tag.endswith("}imagedata"):
            found = image_for_blip(doc, node)
            if found:
                data, is_figure, _ = found
                # Word can include both modern and VML fallback previews of
                # one equation, with no text between them.
                if data == previous_image:
                    continue
                previous_image = data
                if is_figure:
                    figures.append(data)
                else:
                    if formulas is None:
                        out.append(MISSING_FORMULA)
                    else:
                        formulas.append((data, found[2]))
                        out.append(formula_marker(len(formulas) - 1))
    return "".join(out).strip()


def table_text(table, doc, figures: list[bytes],
               formulas: list[tuple[bytes, tuple[int, int]]] | None = None) -> str:
    rows = []
    choice_lines = []
    for row in table.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
        cells = [element_text(cell, doc, figures, formulas).replace("\n", " ").strip()
                 for cell in row.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")]
        for i, cell in enumerate(cells):
            if len(re.findall(r"[1-5]\)", cell)) >= 2:
                parts = [part.strip() for part in re.split(r"(?=[1-5]\))", cell) if part.strip()]
                if all(re.match(r"^[1-5]\)", part) for part in parts):
                    choice_lines.extend(parts)
                    cells[i] = ""
        if any(cells):
            rows.append(cells)
    if rows and rows[0][0].startswith("Ответ:"):
        return ""  # Blank answer grid, not part of the question.
    if not rows:
        return "\n".join(choice_lines)
    def with_choices(value: str) -> str:
        return value + ("\n" + "\n".join(choice_lines) if choice_lines else "")
    # Word also uses tables to position a paragraph beside a figure. A row
    # with one text cell is prose, not a two-column data table.
    if len(rows) == 1 and sum(bool(cell) for cell in rows[0]) == 1:
        return with_choices(next(cell for cell in rows[0] if cell))
    # Matching tasks place the two columns and two lettered prompts in a
    # three-column layout table, leaving the middle and right cells empty.
    # Keep the prompts as prose; the answer options follow this block.
    if (len(rows) == 2 and len(rows[0]) == 3 and not rows[0][1]
            and not rows[1][1] and not rows[1][2]):
        prompts = rows[1][0].strip()
        if re.fullmatch(r"А\)\s*Б\)", prompts):
            return with_choices("Графики А и Б показаны на рисунках.")
        parts = re.split(r"(?=Б\))", prompts, maxsplit=1)
        if len(parts) == 2 and parts[0].startswith("А)"):
            return with_choices("\n\n".join(
                re.sub(r"^([АБ]\))\s*", r"\1 ", part).strip() for part in parts))
    # The five statements of 2026-3 task 18 are laid out in a Word table.
    # Its second row carries a stray fragment of the preceding word before 2).
    if (len(rows) >= 3 and all(len(row) == 2 and row[1] for row in rows)
            and all(re.search(r"[1-5]\)$", row[0]) for row in rows)):
        return with_choices("\n".join(
            re.search(r"([1-5]\))$", row[0]).group(1) + " " + row[1]
            for row in rows))
    # Word often lays out answer choices as a two-column table. These are
    # semantic lists on the site, not mathematical tables.
    if len(rows) >= 2 and all(re.fullmatch(r"\d+\)", row[0]) for row in rows):
        return "\n".join(row[0] + " " + " ".join(row[1:]).strip() for row in rows)
    width = max(map(len, rows))
    escaped = []
    for row in rows:
        row += [""] * (width - len(row))
        escaped.append(" & ".join(cell.replace("&", r"\&").replace("%", r"\%") for cell in row))
    table_latex = "\\begin{tabular}{" + "|".join(["l"] * width) + "}\n" + " \\\\\n".join(escaped) + "\n\\end{tabular}"
    return table_latex + ("\n" + "\n".join(choice_lines) if choice_lines else "")


def extract_blocks(doc, first: int, last_exclusive: int,
                   formulas: list[tuple[bytes, tuple[int, int]]] | None = None) -> tuple[str, list[bytes]]:
    figures: list[bytes] = []
    lines = []
    for element in paragraph_interval(doc, first, last_exclusive):
        if element.tag.endswith("}tbl"):
            value = table_text(element, doc, figures, formulas)
        else:
            value = element_text(element, doc, figures, formulas)
        if value and not re.fullmatch(r"\d{1,2}", value):
            lines.append(value)
    return "\n".join(lines), figures


def normalize_statement(raw: str) -> str:
    raw = "\n".join(line for line in raw.splitlines()
                    if not (len(line.strip()) < 20 and
                            ("&%" in line or line.strip() == "%")))
    raw = re.sub(r"&%\s*(?:end_?|_)?page&%|&%end_page|%end_page&%", "", raw)
    for marker in GENERAL_END:
        if marker in raw:
            # A generic end notice is sometimes wrapped in a one-cell table.
            # Drop that table opener as well so the remaining TeX is balanced.
            table_start = raw.rfind("\\begin{tabular}", 0, raw.index(marker))
            table_end = raw.rfind("\\end{tabular}", 0, raw.index(marker))
            if table_start > table_end:
                raw = raw[:table_start]
                break
            raw = raw.split(marker, 1)[0]
    raw = re.sub(r"(?m)^Ответ\s*:[^\n]*\n?", "", raw)
    raw = re.sub(r"В бланк ответов № 1[^\n]*", "", raw)
    raw = raw.replace("\u00a0", " ")
    raw = re.sub(r"(?<!\d)([1-5]\))(?=\S)", r"\1 ", raw)
    # Some matching choices are compressed into one table cell.
    raw = re.sub(r"(?<=[А-Яа-я])(?=[1-5]\)\s*[А-Яа-я])", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
    return format_quantities(raw)


def answer_key(doc) -> dict[int, str]:
    table = next((t for t in doc.tables
                  if len(t.rows) == 11 and len(t.columns) == 4
                  and t.cell(0, 0).text.strip() == "Номер задания"
                  and t.cell(0, 1).text.strip() == "Правильный ответ"), None)
    if table is None:
        raise ValueError("Answer table missing")
    answers = {}
    for row in table.rows[1:]:
        for col in (0, 2):
            answers[int(row.cells[col].text.strip())] = row.cells[col + 1].text.strip()
    if set(answers) != set(range(1, 21)):
        raise ValueError(f"Incomplete answer key: {sorted(answers)}")
    return answers


def review_sections(doc, first: int, last_exclusive: int,
                    formulas: list[tuple[bytes, tuple[int, int]]] | None = None) -> tuple[str | None, str | None, list[bytes]]:
    """Keep solution and point rubric distinct, retaining embedded equations."""
    figures: list[bytes] = []
    solution_lines = []
    criteria_lines = []
    section = ""
    for block in paragraph_interval(doc, first, last_exclusive):
        if not block.tag.endswith("}tbl"):
            continue
        rows = block.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr")
        for row in rows:
            row_figures: list[bytes] = []
            cells = [element_text(cell, doc, row_figures, formulas).strip() for cell in row.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")]
            if not any(cells):
                continue
            value = " ".join(c for c in cells if c).strip()
            if "Возможное решение" in value:
                section = "solution"
                value = value.replace("Возможное решение", "", 1).strip()
            elif "Критерии оцен" in value and "выполнения задания" in value:
                section = "criteria"
                continue
            if section == "solution":
                figures.extend(row_figures)
                if value:
                    solution_lines.append(value)
            elif section == "criteria" and value:
                if cells[-1] in {"0", "1", "2", "3", "4"}:
                    criteria_lines.append(f"{cells[-1]} балла: " + " ".join(cells[:-1]).strip())
                else:
                    criteria_lines.append(value)
    solution = "\n".join(solution_lines).strip() or None
    criteria = "\n".join(criteria_lines).strip() or None
    if solution:
        solution = "Черновая расшифровка авторского решения; формулы и рисунки сверяйте с исходным DOCX.\n" + format_quantities(solution)
    if criteria:
        criteria = "Краткая расшифровка критериев; полный текст в исходном DOCX.\n" + format_quantities(criteria)
    return solution, criteria, figures


def normalized_figure_png(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as image:
        try:
            image.load(dpi=240)
        except TypeError:
            image.load()
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
    return output.getvalue()


def show_source_formulas(text: str | None,
                         formulas: list[tuple[bytes, tuple[int, int]]]) -> str | None:
    """Replace surviving OOXML equation markers with exact source images."""
    if text is None:
        return None
    for index, (data, (width, height)) in enumerate(formulas):
        marker = formula_marker(index)
        if marker not in text:
            continue
        png = normalized_figure_png(data)
        sha = hashlib.sha256(png).hexdigest()
        path = FORMULA_ASSETS / sha[:2] / (sha + ".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(png)
        formula = VERIFIED_FORMULAS.get(sha) or SOURCE_MATHML_FORMULAS.get(sha)
        replacement = (r"\(" + formula["tex"] + r"\)"
                       if formula else f"[[formula:{sha}:{width}:{height}]]")
        text = text.replace(marker, replacement)
    if "[[SRCFORMULA" in text or MISSING_FORMULA in text:
        raise ValueError("Unresolved source equation image")
    return text


def add_figures(con, pid: str, figures: list[bytes], role: str, locator: str) -> None:
    seen = set()
    for order, data in enumerate(figures, 1):
        if data in seen:
            continue
        seen.add(data)
        png = normalized_figure_png(data)
        if hashlib.sha256(png).hexdigest() in NON_FIGURE_PNG_SHA:
            continue
        aid = store_asset(con, png, ".png", "image/png")
        link_asset(con, pid, aid, role, f"{locator}, figure {order}")


def move_preheading_figure(con, doc, starts: dict[int, int], vid: str,
                           target_number: int, gap: int) -> None:
    """Move a visually checked figure anchored before the next task label."""
    body = list(doc.element.body)
    paragraph = doc.paragraphs[starts[target_number]]._element
    element = body[body.index(paragraph) - gap]
    figures: list[bytes] = []
    if element.tag.endswith("}tbl"):
        table_text(element, doc, figures)
    else:
        element_text(element, doc, figures)
    if not figures:
        raise ValueError(f"Expected preheading figure for task {target_number}")
    previous_id = key("problem", vid, target_number - 1, 1)
    target_id = key("problem", vid, target_number, 1)
    for data in figures:
        aid = key("asset", hashlib.sha256(normalized_figure_png(data)).hexdigest())
        updated = con.execute("""UPDATE problem_assets SET problem_id=?,source_locator=?
            WHERE problem_id=? AND asset_id=? AND role='statement_figure'""",
            (target_id, f"DOCX preheading figure before task {target_number}", previous_id, aid))
        if updated.rowcount != 1:
            raise ValueError(f"Cannot move figure before task {target_number}: {aid}")


def import_variant(con: sqlite3.Connection, number: int) -> None:
    path = SOURCE_DIR / f"Тр_вариант {number}.docx"
    doc = Document(path)
    heading = next(i for i, p in enumerate(doc.paragraphs)
                   if "Критерии оценивания выполнения заданий с развёрнутым ответом" in p.text)
    tasks = numbered_paragraphs(doc, 0, heading)
    reviews = numbered_paragraphs(doc, heading + 1, len(doc.paragraphs), 21)
    # In Word, task numbers may be floating frames anchored *after* the
    # question text in OOXML order. Pull that text from after the preceding
    # answer blank when a numbered span would otherwise be empty.
    for n in range(2, 27):
        next_start = tasks[n + 1] if n < 26 else heading
        candidate, _ = extract_blocks(doc, tasks[n], next_start)
        if normalize_statement(candidate):
            continue
        preceding_text = [i for i in range(tasks[n - 1] + 1, tasks[n])
                          if doc.paragraphs[i].text.strip()
                          and not doc.paragraphs[i].text.strip().startswith("Ответ:")]
        if preceding_text:
            tasks[n] = preceding_text[-1]
    if number == 3:
        # The source anchors label 4 after the lever question and its answer.
        # Paragraph 83 is immediately after task 3's answer box.
        tasks[4] = 83
    answers = answer_key(doc)
    # The source key joins reading and absolute error. These splits were
    # checked against each instrument scale in the embedded source figure.
    measured_answers = {
        2: r"\(755\) и \(1\)",
        3: r"\(136\) и \(2\)",
        4: r"\(3{,}0\) и \(0{,}2\)",
    }
    answers[19] = measured_answers[number]
    vid = upsert_variant(con, path, 2026, str(number), f"Демидова 2026-{number}", False)
    for n in range(1, 27):
        start = tasks[n]
        end = tasks[n + 1] if n < 26 else heading
        raw, statement_figures = extract_blocks(doc, start, end)
        statement = insert_curated_inline(number, n, normalize_statement(raw))
        if not statement:
            raise ValueError(f"Empty statement in variant {number}, task {n}")
        solution = criteria = None
        solution_figures = []
        if n >= 21:
            review_formulas: list[tuple[bytes, tuple[int, int]]] = []
            solution, criteria, solution_figures = review_sections(
                doc, reviews[n], reviews[n + 1] if n < 26 else len(doc.paragraphs),
                review_formulas)
            override = VERIFIED_SOLUTIONS.get((f"2026-{number}", n))
            solution = override[1] if override else show_source_formulas(solution, review_formulas)
            criteria = show_source_formulas(criteria, review_formulas)
        locator = f"DOCX paragraphs {start}–{end - 1}"
        notes = "Автоматическая расшифровка OOXML; требуется визуальная сверка формул, таблиц и рисунков."
        if n == 19:
            notes += " Значение и погрешность разделены по шкале прибора; полный текст задания требует визуальной сверки."
        if n >= 21:
            notes += " Решение и критерии требуют предметной сверки; отдельного авторского ключа ответа нет."
        topic = "molecular" if n == 21 else "electrodynamics" if n == 23 else TOPICS[n]
        statement = repair_text(f"2026-{number}", n, "statement", statement)
        solution = repair_text(f"2026-{number}", n, "solution", solution)
        criteria = repair_text(f"2026-{number}", n, "criteria", criteria)
        pid = upsert_problem(con, vid, n, 1, statement, answers.get(n), solution,
                             criteria, topic, locator, notes, "needs_review")
        add_figures(con, pid, statement_figures, "statement_figure", locator)
        add_figures(con, pid, solution_figures, "solution_figure", f"DOCX review for {n}")
    for target, gap in {2: [(24, 1)], 4: [(11, 1)]}.get(number, []):
        move_preheading_figure(con, doc, tasks, vid, target, gap)
    print(f"variant {number}: 26 tasks, {len(answers)} key answers")


def main() -> None:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    with con:
        for number in (2, 3, 4):
            import_variant(con, number)
        orphaned = [ROOT / row[0] for row in con.execute("""SELECT storage_path FROM assets
            WHERE id NOT IN (SELECT asset_id FROM problem_assets)""")]
        con.execute("DELETE FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)")
    for path in orphaned:
        if path.resolve().is_relative_to(ASSETS.resolve()) and path.is_file():
            path.unlink()
    for number in (2, 3, 4):
        count, answered, solved, rubric = con.execute("""SELECT count(*),
            sum(answer IS NOT NULL),sum(solution IS NOT NULL),sum(criteria IS NOT NULL)
            FROM problems p JOIN variants v ON v.id=p.variant_id
            WHERE v.exam_year=2026 AND v.variant_number=?""", (str(number),)).fetchone()
        if (count, answered, solved, rubric) != (26, 20, 6, 6):
            raise ValueError(f"Incomplete variant {number}: {(count, answered, solved, rubric)}")
    print("total tasks", con.execute("SELECT COUNT(*) FROM problems").fetchone()[0])
    print("new tasks awaiting review", con.execute("""SELECT COUNT(*) FROM problems p
        JOIN variants v ON v.id=p.variant_id WHERE v.exam_year=2026
        AND v.variant_number IN ('2','3','4') AND p.extraction_status='needs_review'""").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()

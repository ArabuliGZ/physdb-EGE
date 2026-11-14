"""Import the 2027 FIPI demo and Demidova 2026 training variant 1.

Run with the bundled Python runtime from the PhysDB README. The import is
idempotent. Original PDFs and DOCX files are never modified.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
import subprocess
from io import BytesIO
from pathlib import Path

import pdfplumber
from docx import Document
from PIL import Image

from demo_2027_transcription import FIGURE_BOXES, SOLUTION_FIGURE_BOXES, STATEMENTS as DEMO_STATEMENTS
from demidova_2026_1_transcription import SOLUTION_FIGURE_INDICES, STATEMENTS as DEMIDOVA_STATEMENTS
from curated_solutions import FIPI as FIPI_SOLUTIONS, DEMIDOVA as DEMIDOVA_SOLUTIONS
from curated_solutions import FIPI_ANSWERS, DEMIDOVA_ANSWERS
from curated_criteria import FIPI as FIPI_CRITERIA, DEMIDOVA as DEMIDOVA_CRITERIA_TEXT
from tex_format import format_quantities, layout_criteria


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
ASSETS = ROOT / "assets" / "objects"
DEMO = ROOT / "Материалы" / "Физика ЕГЭ 2027" / "ФИ-11 ЕГЭ 2027 ДЕМО.pdf"
DEMIDOVA = ROOT / "Материалы" / "ЕГЭ от Демидовой" / "2026" / "Тр_вариант 1.docx"

POINTS = {n: (1 if n in {1, 2, 3, 4, 7, 8, 11, 12, 13, 16, 19, 20} else 2)
          for n in range(1, 21)}
POINTS.update({21: 3, 22: 2, 23: 2, 24: 3, 25: 3, 26: 4})
TOPICS = {**{n: "mechanics" for n in range(1, 7)},
          **{n: "molecular" for n in range(7, 11)},
          **{n: "electrodynamics" for n in range(11, 16)},
          **{n: "quantum" for n in (16, 17)},
          **{n: "cross_topic" for n in (18, 19, 20)},
          21: "electrodynamics", 22: "mechanics", 23: "molecular",
          24: "molecular", 25: "electrodynamics", 26: "mechanics"}
FORMATS = {n: ("number_pair" if n == 19 else
               "number" if n in {1, 2, 3, 4, 7, 8, 11, 12, 13, 16} else
               "multiple_choice" if n in {5, 9, 14, 18, 20} else
               "matching" if n <= 20 else
               "qualitative" if n == 21 else "worked_solution")
           for n in range(1, 27)}

# Suitability for the *position* in the approved 2027 specification. These
# judgments use the narrow content codes in its generalized plan, the answer
# format, and the separate "Пояснения к типам задач" image. Text-extraction
# quality is tracked by problems.extraction_status and does not decide this.
DEMIDOVA_2027_RELEVANCE = {
    1: (1, 1, "yes", "Путь по графику скорости: кинематика 1.1.5–1.1.6; числовой ответ соответствует позиции 1."),
    2: (1, 1, "yes", "Связь силы, массы и ускорения: второй закон Ньютона 1.2.4; числовой ответ соответствует позиции 2."),
    3: (1, 1, "yes", "Кинетическая и потенциальная энергия при движении вверх: 1.4.6–1.4.8; числовой ответ соответствует позиции 3."),
    4: (1, 1, "yes", "Период колебаний груза на пружине: 1.5.2 и закон Гука 1.2.7; числовой ответ соответствует позиции 4."),
    5: (1, 1, "yes", "Анализ графика координаты в механике; множественный выбор соответствует позиции 5. Спектр сюжетов 5 расширен."),
    6: (1, 1, "yes", "Изменение ускорения и кинетической энергии при движении камня: механика; ответ последовательностью цифр соответствует позиции 6."),
    7: (1, 1, "yes", "Объём аргона по графику газового процесса: 2.1.10–2.1.12; числовой ответ соответствует позиции 7."),
    8: (1, 1, "yes", "Работа, внутренняя энергия и теплота: первый закон термодинамики 2.2.7; числовой ответ соответствует позиции 8."),
    9: (1, 1, "yes", "Анализ процесса идеального газа на p–V-диаграмме; множественный выбор соответствует позиции 9."),
    10: (1, 1, "yes", "Давление смеси газов и парциальное давление: закон Дальтона 2.1.11; формат соответствия соответствует позиции 10."),
    11: (1, 1, "yes", "Сила тока по графику заряда: 3.2.1; числовой ответ соответствует позиции 11."),
    12: (1, 1, "yes", "Энергия магнитного поля катушки: 3.4.7; числовой ответ соответствует позиции 12."),
    13: (1, 1, "yes", "Период свободных колебаний контура: 3.5.1; числовой ответ соответствует позиции 13."),
    14: (1, 1, "yes", "Анализ колебаний контура по таблице: электродинамика; множественный выбор соответствует позиции 14."),
    15: (1, 1, "yes", "Частота контура и длина волны при изменении ёмкости: электродинамика; формат соответствия отвечает позиции 15."),
    16: (1, 1, "yes", "Заряд ядра после β-распада: 4.3.1–4.3.2; числовой ответ соответствует позиции 16."),
    17: (1, 1, "yes", "Изменение массового и зарядового чисел при α-распаде: раздел 4; формат соответствия отвечает позиции 17."),
    18: (1, 1, "yes", "Утверждения о законах из разных разделов курса; множественный выбор соответствует позиции 18."),
    19: (1, 1, "yes", "Показание динамометра с абсолютной погрешностью: измерительное умение и ответ двумя числами для позиции 19."),
    20: (1, 1, "yes", "Выбор схем для проверки зависимости силы тока: планирование эксперимента и выбор оборудования для позиции 20."),
    21: (0, 1, "no", "Качественная задача на 3 балла по молекулярной физике; позиция 21 в 2027 году отведена только электродинамике."),
    22: (1, 0, "partial", "Механика и 2 балла совпадают, но абстрактное движение без практического сюжета не отвечает пояснению к позиции 22."),
    23: (0, 1, "no", "Расчётная задача на 2 балла по электрической цепи; позиция 23 в 2027 году отведена молекулярной физике."),
    24: (1, 1, "yes", "Расчёт влажности в комнате: молекулярная физика 2.1.13–2.1.14, высокий уровень и 3 балла для позиции 24."),
    25: (1, 1, "yes", "Тонкая линза и построение изображений: оптика 3.6.7 в разделе электродинамики; 3 балла для позиции 25."),
    26: (1, 1, "yes", "Динамика двух тел с трением, рисунками и обоснованием модели: механика 1.2; 4 балла для позиции 26."),
}
DEMIDOVA_RANGES = {
    1:(39,58), 2:(59,70), 3:(71,85), 4:(86,95), 5:(96,119),
    6:(120,128), 7:(129,142), 8:(143,171), 9:(172,204), 10:(205,215),
    11:(216,233), 12:(234,248), 13:(249,253), 14:(254,267),
    15:(268,282), 16:(283,295), 17:(296,316), 18:(317,330),
    19:(331,356), 20:(357,399), 21:(406,457), 22:(463,467),
    23:(468,496), 24:(497,517), 25:(518,526), 26:(527,536),
}
DEMIDOVA_CRITERIA = {21:(550,579), 22:(580,613), 23:(614,633),
                     24:(634,644), 25:(645,655), 26:(656,663)}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key(*parts: object) -> str:
    return digest("|".join(map(str, parts)).encode())[:24]


def store_asset(con: sqlite3.Connection, data: bytes, suffix: str, media_type: str) -> str:
    sha = digest(data)
    path = ASSETS / sha[:2] / (sha + suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    aid = key("asset", sha)
    con.execute("""INSERT INTO assets VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        media_type=excluded.media_type,storage_path=excluded.storage_path,
        size_bytes=excluded.size_bytes""",
                (aid, media_type, path.relative_to(ROOT).as_posix(), sha, len(data)))
    return aid


def link_asset(con: sqlite3.Connection, pid: str, aid: str, role: str, locator: str) -> None:
    con.execute("INSERT OR IGNORE INTO problem_assets VALUES (?,?,?,?)",
                (pid, aid, role, locator))


def upsert_variant(con: sqlite3.Connection, path: Path, year: int,
                   number: str, title: str, official: bool) -> str:
    vid = key("variant", path.relative_to(ROOT))
    con.execute("""INSERT INTO variants
        (id,title,exam_year,variant_number,source_path,source_sha256,source_kind,is_official_demo)
        VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        source_sha256=excluded.source_sha256, imported_at=CURRENT_TIMESTAMP""",
        (vid, title, year, number, str(path.relative_to(ROOT)), digest(path.read_bytes()),
         path.suffix.lower().lstrip("."), int(official)))
    return vid


def upsert_problem(con: sqlite3.Connection, vid: str, number: int, alternative: int,
                   statement: str, answer: str | None, solution: str | None,
                   criteria: str | None, topic: str, locator: str,
                   notes: str, status: str = "needs_review",
                   max_points: int | None = None, answer_format: str | None = None) -> str:
    pid = key("problem", vid, number, alternative)
    con.execute("""INSERT INTO problems
        (id,variant_id,problem_number,alternative_number,statement,answer,solution,
         criteria,max_points,answer_format,topic,extraction_status,review_notes,source_locator)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        statement=excluded.statement,answer=excluded.answer,solution=excluded.solution,
        criteria=excluded.criteria,max_points=excluded.max_points,
        answer_format=excluded.answer_format,topic=excluded.topic,extraction_status=excluded.extraction_status,
        review_notes=excluded.review_notes,source_locator=excluded.source_locator""",
        (pid, vid, number, alternative, statement.strip(), format_quantities(answer) if answer else None,
         solution, layout_criteria(criteria) if criteria else None,
         max_points if max_points is not None else POINTS[number],
         answer_format if answer_format is not None else FORMATS[number],
         topic, status, notes, locator))
    con.execute("DELETE FROM problem_assets WHERE problem_id=?", (pid,))
    return pid


def assess(con: sqlite3.Connection, pid: str, source_number: int,
           topic_match: int, format_match: int, verdict: str, reason: str) -> None:
    con.execute("""INSERT INTO relevance
        (problem_id,exam_year,target_problem_number,topic_match,format_match,verdict,reason)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(problem_id,exam_year,target_problem_number)
        DO UPDATE SET topic_match=excluded.topic_match,format_match=excluded.format_match,
        verdict=excluded.verdict,reason=excluded.reason,assessed_at=CURRENT_TIMESTAMP""",
        (pid, 2027, source_number, topic_match, format_match, verdict, reason))


def page_text(page: pdfplumber.page.Page, side: int) -> str:
    x0 = 0 if side == 1 else page.width / 2
    x1 = page.width / 2 if side == 1 else page.width
    return page.crop((x0, 0, x1, page.height)).extract_text() or ""


def demo_crop_bounds(pdf) -> dict[tuple[int, int], tuple[int, float, float]]:
    """Map each printed problem to its vertical bounds in the source PDF."""
    bounds = {}
    for printed in range(6, 18):
        page = pdf.pages[(printed - 1) // 2]
        x0 = 0 if printed % 2 else page.width / 2
        x1 = page.width / 2 if printed % 2 else page.width
        words = page.crop((x0, 0, x1, page.height)).extract_words()
        labels = []
        for word in words:
            if word["text"].isdigit() and word["x0"] - x0 < 46:
                number = int(word["text"])
                if 1 <= number <= 26 and 50 < word["top"] < page.height - 30:
                    labels.append((number, word["top"]))
        labels.sort(key=lambda item: item[1])
        for index, (number, top) in enumerate(labels):
            bottom = labels[index + 1][1] - 7 if index + 1 < len(labels) else page.height - 39
            bounds[(number, 1)] = (printed, max(42, top - 8), bottom)
        if printed == 17:
            alternatives = sorted(word["top"] for word in words if word["text"] == "ИЛИ")
            if len(alternatives) != 2:
                raise ValueError("Could not locate FIPI position 26 alternatives")
            first_top = bounds[(26, 1)][1]
            bounds[(26, 1)] = (17, first_top, alternatives[0] - 6)
            bounds[(26, 2)] = (17, alternatives[0] + 13, alternatives[1] - 6)
            bounds[(26, 3)] = (17, alternatives[1] + 13, page.height - 80)
    if set(range(1, 27)) != {number for number, _ in bounds}:
        raise ValueError("Not all FIPI problems received source crop bounds")
    return bounds


def extract_demo(con: sqlite3.Connection) -> None:
    if len(DEMO_STATEMENTS) != 28:
        raise ValueError("FIPI demo transcription must cover all 28 problem examples")
    vid = upsert_variant(con, DEMO, 2027, "ДЕМО", "Демо 2027", True)
    with pdfplumber.open(DEMO) as pdf:
        logical = {i * 2 + side: page_text(page, side)
                   for i, page in enumerate(pdf.pages) for side in (1, 2)}
        crop_bounds = demo_crop_bounds(pdf)
    # The print edition lays out two numbered pages on each PDF page.
    body = "\n".join(f"\n@@PAGE {p}@@\n{logical[p]}" for p in range(6, 18))
    starts = []
    cursor = 0
    for n in range(1, 27):
        pattern = (rf"(?m)^{n}[ \t]+(?=[А-ЯЁA-Z])|^{n}[ \t]*$"
                   if n in {13, 15, 17} else
                   rf"(?m)^{n}[ \t]+(?=[А-ЯЁA-Z])")
        match = re.search(pattern, body[cursor:])
        if not match:
            raise ValueError(f"Cannot locate FIPI problem {n}")
        cursor += match.start()
        starts.append(cursor)
        cursor += len(str(n))
    starts.append(len(body))
    answer_page = logical[18]
    answer_key: dict[int, str] = {}
    for line in answer_page.splitlines():
        m = re.match(r"^(\d{1,2})\s+(\S+)\s+(\d{1,2})\s+(\S+)", line)
        if m:
            answer_key[int(m[1])] = m[2]
            answer_key[int(m[3])] = m[4]
    if len(answer_key) != 20:
        raise ValueError(f"Incomplete FIPI answer key: {len(answer_key)}")
    assessment = "\n".join(f"\n@@PAGE {p}@@\n{logical[p]}" for p in range(19, 43))
    criterion_starts = []
    cursor = 0
    for n in range(21, 27):
        m = re.search(rf"(?m)^{n}\s+(?=[А-ЯЁA-Z])", assessment[cursor:])
        if not m:
            raise ValueError(f"Cannot locate FIPI criteria for {n}")
        cursor += m.start()
        criterion_starts.append(cursor)
        cursor += len(str(n))
    criterion_starts.append(len(assessment))
    render = Path(shutil.which("pdfinfo") or "").with_name("pdftoppm.exe")
    if not render.exists():
        raise RuntimeError("Bundled Poppler pdftoppm.exe is required for source-page images")
    tmp = ROOT / "tmp" / "import-demo-170"
    tmp.mkdir(parents=True, exist_ok=True)
    for n in range(1, 27):
        chunk = body[starts[n - 1]:starts[n]]
        # The demo offers three mutually exclusive examples for position 26.
        alternatives = re.split(r"(?m)^ИЛИ\s*$", chunk) if n == 26 else [chunk]
        for alt, _raw in enumerate(alternatives, 1):
            print_page, crop_top, crop_bottom = crop_bounds[(n, alt)]
            statement = format_quantities(DEMO_STATEMENTS[(n, alt)])
            answer = answer_key.get(n)
            solution = criteria = None
            if n >= 21:
                section_start = criterion_starts[n - 21]
                section_end = criterion_starts[n - 20]
                section = assessment[section_start:section_end]
                if n == 26:
                    boundaries = [0]
                    for heading in ("Брусок массой М", "К концам невесомого рычага"):
                        found = section.find(heading)
                        if found < 0:
                            raise ValueError(f"Missing FIPI 26 alternative: {heading}")
                        boundaries.append(found)
                    boundaries.append(len(section))
                    section = section[boundaries[alt - 1]:boundaries[alt]]
                split = re.split(r"Критерии оценивания выполнения задания", section, maxsplit=1)
                solution = format_quantities(FIPI_SOLUTIONS[(n, alt)])
                if len(split) < 2:
                    raise ValueError(f"Cannot locate FIPI criteria for problem {n}, alternative {alt}")
                criteria = format_quantities(FIPI_CRITERIA[(n, alt)])
                answer = FIPI_ANSWERS[(n, alt)]
            locator = f"print page {print_page}, position {n}" + (f", alternative {alt}" if n == 26 else "")
            notes = ("Statement transcribed from the rendered FIPI image and visually checked."
                     if n <= 20 else
                     "Statement visually checked; extracted solution and criteria need verification.")
            pid = upsert_problem(con, vid, n, alt, statement, answer, solution,
                                 criteria, TOPICS[n], locator, notes,
                                 "verified" if n <= 20 else "needs_review")
            # Official demo examples fit their own positions even while text extraction awaits QA.
            assess(con, pid, n, 1, 1, "yes", "Официальный пример ФИПИ 2027 для этой позиции: тема и формат совпадают.")
            # Render a temporary task crop only to isolate its diagrams.
            pdf_page = (print_page + 1) // 2
            path = tmp / f"pdf-{pdf_page:02d}.png"
            if not path.exists():
                subprocess.run([str(render), "-f", str(pdf_page), "-l", str(pdf_page),
                                "-r", "170", "-png", "-singlefile", str(DEMO),
                                str(path.with_suffix(""))], check=True, capture_output=True)
            with Image.open(path) as im:
                x0 = 0 if print_page % 2 else im.width // 2
                x1 = im.width // 2 if print_page % 2 else im.width
                scale = im.height / 595.22
                half = im.crop((x0, round(crop_top * scale), x1, round(crop_bottom * scale)))
                output = BytesIO()
                half.save(output, format="PNG")
            with Image.open(BytesIO(output.getvalue())) as source_image:
                for figure_number, box in enumerate(FIGURE_BOXES.get((n, alt), []), 1):
                    figure = source_image.crop(box)
                    figure_data = BytesIO()
                    figure.save(figure_data, format="PNG")
                    figure_id = store_asset(con, figure_data.getvalue(), ".png", "image/png")
                    link_asset(con, pid, figure_id, "statement_figure",
                               f"{locator}, figure {figure_number}")


def xml_text(element) -> str:
    # Word stores displayed formula glyphs in m:t, omitted by python-docx .text.
    out = []
    for node in element.iter():
        if node.tag.endswith("}t") and node.text:
            out.append(node.text)
        elif node.tag.endswith("}tab"):
            out.append("\t")
    return "".join(out).strip()


def latex_escape(text: str) -> str:
    for before, after in [("\\", r"\textbackslash{}"), ("&", r"\&"),
                          ("%", r"\%"), ("_", r"\_"), ("#", r"\#")]:
        text = text.replace(before, after)
    return text.replace("\n", " ").strip()


def table_latex(element) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    rows = element.findall("./w:tr", ns)
    cells = [[latex_escape(xml_text(cell)) for cell in row.findall("./w:tc", ns)]
             for row in rows]
    if not cells or not any(value for row in cells for value in row):
        return ""
    width = max(map(len, cells))
    lines = [" & ".join(row + [""] * (width - len(row))) for row in cells]
    row_sep = " " + "\\" * 2 + "\n"
    return "\\begin{tabular}{" + "|".join(["l"] * width) + "}\n" + \
           row_sep.join(lines) + "\n\\end{tabular}"


def docx_range(doc: Document, first: int, last: int) -> tuple[str, list[bytes]]:
    para_elements = [p._element for p in doc.paragraphs]
    body = list(doc.element.body)
    begin = body.index(para_elements[first])
    end = body.index(para_elements[last])
    texts = []
    image_bytes = []
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    for element in body[begin:end + 1]:
        if element.tag.endswith("}tbl"):
            value = table_latex(element)
        else:
            value = xml_text(element)
        if value and value not in {str(i) for i in range(1, 27)}:
            texts.append(value)
        for blip in element.findall(".//a:blip", ns):
            rid = blip.get("{" + ns["r"] + "}embed")
            if rid and rid in doc.part.related_parts:
                image_bytes.append(doc.part.related_parts[rid].blob)
    return "\n".join(texts), image_bytes


def extract_demidova(con: sqlite3.Connection) -> None:
    if set(DEMIDOVA_STATEMENTS) != set(range(1, 27)):
        raise ValueError("Demidova transcription must cover problems 1–26")
    vid = upsert_variant(con, DEMIDOVA, 2026, "1", "Демидова 2026-1", False)
    doc = Document(DEMIDOVA)
    answer_table = next((table for table in doc.tables
                         if len(table.rows) == 11 and len(table.columns) == 4
                         and xml_text(table.cell(0, 0)._element) == "Номер задания"
                         and xml_text(table.cell(0, 1)._element) == "Правильный ответ"), None)
    if answer_table is None:
        raise ValueError("Demidova answer table on page 13 not found")
    answer_key: dict[int, str] = {}
    for row in answer_table.rows[1:]:
        for number_col in (0, 2):
            number = int(xml_text(row.cells[number_col]._element))
            answer_key[number] = xml_text(row.cells[number_col + 1]._element)
    if set(answer_key) != set(range(1, 21)) or answer_key[19] != "2,70,1":
        raise ValueError("Demidova answer key is incomplete or unexpected")
    answer_key[19] = "2,7 ± 0,1"  # The key concatenates the two answer-box numbers.
    for n in range(1, 27):
        statement = format_quantities(DEMIDOVA_STATEMENTS[n])
        criteria = solution = None
        answer = answer_key.get(n)
        if n >= 21:
            review_text, _ = docx_range(doc, *DEMIDOVA_CRITERIA[n])
            if "Возможное решение" in review_text and "Критерии оценивания выполнения задания" in review_text:
                criteria = format_quantities(DEMIDOVA_CRITERIA_TEXT[n])
            else:
                raise ValueError(f"Cannot locate Demidova criteria for problem {n}")
            solution = format_quantities(DEMIDOVA_SOLUTIONS[n])
            answer = DEMIDOVA_ANSWERS[n]
        # 2026 positions 21 and 23 have different topics than 2027.
        topic = "molecular" if n == 21 else "electrodynamics" if n == 23 else TOPICS[n]
        notes = ("Statement visually checked against rendered source; answers 1–20 from page 13."
                 if n <= 20 else "Statement checked; extracted solution and criteria need review.")
        if n in (21, 23):
            notes += " Topic differs from 2027 position."
        pid = upsert_problem(con, vid, n, 1, statement, answer, solution, criteria,
                             topic, f"DOCX paragraphs {DEMIDOVA_RANGES[n][0]}–{DEMIDOVA_RANGES[n][1]}",
                             notes, "verified" if n <= 20 else "needs_review")
        assess(con, pid, n, *DEMIDOVA_2027_RELEVANCE[n])
        figure = ROOT / "assets" / "curated" / "demidova_2026_1" / f"{n:02}.png"
        if figure.exists():
            aid = store_asset(con, figure.read_bytes(), ".png", "image/png")
            link_asset(con, pid, aid, "statement_figure", f"DOCX figure for problem {n}")


def add_solution_figures(con: sqlite3.Connection) -> None:
    """Attach only diagrams that appear inside the worked solutions."""
    demo_vid = key("variant", DEMO.relative_to(ROOT))
    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise RuntimeError("Poppler pdftoppm is required for solution diagrams")
    scratch = ROOT / "tmp" / "pdfs" / "solution-300"
    scratch.mkdir(parents=True, exist_ok=True)
    for (number, alternative), (printed_page, box) in SOLUTION_FIGURE_BOXES.items():
        pdf_page = (printed_page + 1) // 2
        page_image = scratch / f"pdf-{pdf_page:02}.png"
        subprocess.run([renderer, "-f", str(pdf_page), "-l", str(pdf_page),
                        "-r", "300", "-png", "-singlefile", str(DEMO),
                        str(page_image.with_suffix(""))], check=True, capture_output=True)
        with Image.open(page_image) as image:
            half = image.crop((0 if printed_page % 2 else image.width // 2, 0,
                               image.width // 2 if printed_page % 2 else image.width,
                               image.height))
            scale_x = half.width / (994 if printed_page % 2 else 995)
            scale_y = half.height / 1406
            bounds = tuple(round(value * (scale_x if index % 2 == 0 else scale_y))
                           for index, value in enumerate(box))
            figure = half.crop(bounds)
            output = BytesIO()
            figure.save(output, format="PNG")
        pid = key("problem", demo_vid, number, alternative)
        con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='solution_figure'", (pid,))
        aid = store_asset(con, output.getvalue(), ".png", "image/png")
        link_asset(con, pid, aid, "solution_figure",
                   f"print page {printed_page}, solution diagram")

    demidova_vid = key("variant", DEMIDOVA.relative_to(ROOT))
    doc = Document(DEMIDOVA)
    for number, indices in SOLUTION_FIGURE_INDICES.items():
        _, images = docx_range(doc, *DEMIDOVA_CRITERIA[number])
        pid = key("problem", demidova_vid, number, 1)
        con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='solution_figure'", (pid,))
        for order, index in enumerate(indices, 1):
            if index >= len(images):
                raise ValueError(f"Missing DOCX solution diagram for problem {number}")
            with Image.open(BytesIO(images[index])) as image:
                image.load(dpi=216)
                figure = image.convert("RGB")
                output = BytesIO()
                figure.save(output, format="PNG")
            aid = store_asset(con, output.getvalue(), ".png", "image/png")
            link_asset(con, pid, aid, "solution_figure",
                       f"DOCX solution diagram {order} for problem {number}")


def migrate_relevance_table(con: sqlite3.Connection) -> None:
    """Upgrade the old verdict constraint without changing assessments."""
    row = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='relevance'").fetchone()
    if not row or "'partial'" in row[0]:
        return
    pending = con.execute("SELECT COUNT(*) FROM relevance WHERE verdict='needs_review'").fetchone()[0]
    if pending:
        raise ValueError("Resolve existing unassessed relevance rows before migrating to partial")
    con.execute("""CREATE TABLE relevance_new (
        problem_id TEXT NOT NULL REFERENCES problems(id),
        exam_year INTEGER NOT NULL,
        target_problem_number INTEGER NOT NULL,
        topic_match INTEGER NOT NULL,
        format_match INTEGER NOT NULL,
        verdict TEXT NOT NULL CHECK (verdict IN ('yes','no','partial')),
        reason TEXT NOT NULL,
        assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (problem_id, exam_year, target_problem_number),
        FOREIGN KEY (exam_year, target_problem_number) REFERENCES exam_positions(exam_year, problem_number)
    )""")
    con.execute("""INSERT INTO relevance_new
        (problem_id,exam_year,target_problem_number,topic_match,format_match,verdict,reason,assessed_at)
        SELECT problem_id,exam_year,target_problem_number,topic_match,format_match,verdict,reason,assessed_at
        FROM relevance""")
    con.execute("DROP TABLE relevance")
    con.execute("ALTER TABLE relevance_new RENAME TO relevance")
    con.execute("CREATE INDEX relevance_target_idx ON relevance(exam_year, target_problem_number, verdict)")


def main() -> None:
    if set(DEMIDOVA_2027_RELEVANCE) != set(range(1, 27)):
        raise ValueError("Every Demidova problem needs an individual 2027 assessment")
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    with con:
        migrate_relevance_table(con)
    with con:
        for n in range(1, 27):
            con.execute("""INSERT OR REPLACE INTO exam_positions VALUES (?,?,?,?,?,?)""",
                        (2027, n, TOPICS[n], FORMATS[n], POINTS[n], "approved"))
        extract_demo(con)
        extract_demidova(con)
        add_solution_figures(con)
        orphaned = con.execute("""SELECT storage_path FROM assets
            WHERE id NOT IN (SELECT asset_id FROM problem_assets)""").fetchall()
        con.execute("DELETE FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)")
        for (relative,) in orphaned:
            path = (ROOT / relative).resolve()
            if path.is_relative_to(ASSETS.resolve()) and path.is_file():
                path.unlink()
    # Previous importer versions removed orphan rows but left generated files.
    referenced = {(ROOT / row[0]).resolve()
                  for row in con.execute("SELECT storage_path FROM assets")}
    for path in ASSETS.rglob("*"):
        if (path.is_file() and path.resolve().is_relative_to(ASSETS.resolve())
                and re.fullmatch(r"[0-9a-f]{64}\.(?:png|jpg|jpeg|bin)", path.name)
                and path.resolve() not in referenced):
            path.unlink()
    for table in ("variants", "problems", "assets", "problem_assets", "relevance"):
        print(table, con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    print("database", DB)
    con.close()


if __name__ == "__main__":
    main()

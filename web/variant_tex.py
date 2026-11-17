"""Compose exam sheets and companion materials from reusable XeLaTeX templates."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

if __package__:
    from .answer_units import format_answer_unit_tex
else:
    from answer_units import format_answer_unit_tex


TEX_DIR = Path(__file__).with_name("tex")
MATH = re.compile(r"(\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\[\[formula:[0-9a-f]{64}:\d+:\d+\]\])")
TABLE = re.compile(r"\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}")
FORMULA = re.compile(r"\[\[formula:([0-9a-f]{64}):\d+:\d+\]\]")
ORDERED_RESPONSE = re.compile(
    r"Запишите выбранные цифры в порядке:\s*(.+?)\s*;\s*(.+?)\.\s*Цифры могут повторяться",
    re.IGNORECASE | re.DOTALL,
)
RESPONSE_POSITIONS = {6, 10, 15, 17}
ANSWER_UNIT_WORDS = {
    "метрах": "м", "сантиметрах": "см", "миллиметрах": "мм",
    "километрах": "км", "секундах": "с", "миллисекундах": "мс",
    "микросекундах": "мкс", "килограммах": "кг", "граммах": "г",
    "литрах": "л", "миллилитрах": "мл", "молях": "моль",
    "миллимолях": "ммоль", "микромолях": "мкмоль", "мкмолях": "мкмоль",
    "ньютонах": "Н", "джоулях": "Дж", "килоджоулях": "кДж",
    "ваттах": "Вт", "паскалях": "Па", "килопаскалях": "кПа",
    "вольтах": "В", "амперах": "А", "миллиамперах": "мА",
    "омах": "Ом", "герцах": "Гц", "килогерцах": "кГц",
    "мегагерцах": "МГц", "теслах": "Тл", "веберах": "Вб",
    "кулонах": "Кл", "градусах": "°", "процентах": "%",
}
SCORE = re.compile(r"^\\\((\d+)\\\)\s+балл[аов]*[.:]\s*(.*)$")
ROMAN = re.compile(r"^(IV|III|II|I|V)\)\s*(.*)$")
ALTERNATIVE = re.compile(r"^(И\s*\(ИЛИ\)|ИЛИ)\s*(.*)$")
SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
CONDITION_FIGURE_CAPTIONS = {
    (2027, "7", 21): ("Рис. а", "Рис. б"),
    (2022, "1", 19): ("Рис. 1", "Рис. 2"),
}
# These trailing images are answer choices, not illustrations of the question.
# Keep this list in sync with graphFigures in static/matching-layouts.js.
GRAPH_CHOICE_FIGURES = {
    (2027, "1", 6): 2, (2027, "11", 15): 2, (2027, "15", 6): 2,
    (2027, "ДЕМО", 15): 1, (2026, "4", 6): 2,
    (2025, "1-2", 15): 2, (2025, "2-2", 15): 2,
    (2024, "1-1", 6): 2, (2024, "1-3", 15): 2,
    (2024, "1-4", 6): 2, (2024, "2-2", 6): 2,
    (2024, "2-3", 6): 2, (2024, "2-4", 6): 2,
    (2023, "1", 6): 2, (2023, "2", 6): 2, (2023, "3", 19): 1,
    (2022, "3", 19): 2, (2022, "4", 8): 2,
}
# Titles checked against the printed matching columns; some are absent from
# extracted text but already restored in the website's matching layouts.
MATCHING_HEADINGS = {
    (2027, "1", 6): ("ГРАФИКИ", "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ"),
    (2027, "3", 17): ("ПРОЦЕССЫ", "ЭНЕРГИЯ ФОТОНА"),
    (2027, "9", 17): ("ПРОЦЕССЫ", "ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ"),
    (2027, "11", 15): ("ГРАФИКИ", "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ"),
    (2027, "13", 17): ("ПРОЦЕСС", "ЭНЕРГИЯ ФОТОНА"),
    (2027, "15", 6): ("ГРАФИКИ", "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ"),
    (2026, "4", 17): ("ПРОЦЕСС", "ЭНЕРГИЯ ФОТОНА"),
    (2025, "1-1", 17): ("ПРОЦЕСС", "ЭНЕРГИЯ ФОТОНА"),
    (2025, "2-1", 17): ("ПРОЦЕСС", "ЭНЕРГИЯ ФОТОНА"),
    (2024, "1-3", 17): ("ПРОЦЕСС", "ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ"),
    (2023, "1", 11): ("ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ", "ФОРМУЛЫ"),
    (2023, "1", 17): ("ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ", "ФОРМУЛЫ"),
    (2023, "1", 19): ("ПРОЦЕССЫ", "ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ"),
    (2023, "2", 11): ("ПРОЦЕССЫ", "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ"),
    (2023, "2", 17): ("ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ", "ФОРМУЛЫ"),
    (2023, "3", 11): ("ХАРАКТЕРИСТИКИ ПРОЦЕССОВ", "НОМЕРА ПРОЦЕССОВ"),
    (2023, "3", 17): ("ФОРМУЛЫ", "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ"),
    (2022, "1", 8): ("ФОРМУЛЫ", "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ"),
    (2022, "1", 19): ("ДВИЖЕНИЕ ЧАСТИЦЫ", "ТРАЕКТОРИЯ"),
    (2022, "2", 8): ("ФИЗИЧЕСКАЯ ВЕЛИЧИНА", "ФОРМУЛА"),
    (2022, "2", 21): ("ПРОЦЕССЫ", "ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ"),
    (2022, "3", 8): ("ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ", "ФОРМУЛЫ"),
    (2022, "3", 13): ("УЧАСТКИ ГРАФИКА", "ПРОЦЕССЫ"),
}
# The second stored figure of this task duplicates the next task's graph.
MISASSIGNED_STATEMENT_FIGURES = {(2023, "3", 14): 1}


def escape(value: str) -> str:
    return "".join(SPECIAL.get(ch, ch) if ch != "\\" else r"\textbackslash{}" for ch in value)


def hybrid(value: str, figures: dict[str, Path]) -> str:
    """Escape prose while retaining imported inline/display math and formula crops."""
    pieces = []
    for part in MATH.split(value):
        if not part:
            continue
        formula = FORMULA.fullmatch(part)
        if formula:
            sha = formula.group(1)
            source = figures.get(f"formula/{sha}")
            if source and source.is_file():
                pieces.append(r"\includegraphics[height=1.7em,keepaspectratio]{figures/" + source.name + "}")
            else:
                pieces.append(r"\textit{[формула]}")
        elif part.startswith((r"\(", r"\[")):
            pieces.append(part)
        else:
            pieces.append(escape(part.replace(r"\&", "&").replace(r"\%", "%")))
    return "".join(pieces)


def prose(value: str, figures: dict[str, Path]) -> str:
    output = []
    for paragraph in re.split(r"\n\s*\n", value.strip()):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        current = []
        for line in lines:
            if re.match(r"^\d+[.)]\s+", line):
                if current:
                    output.append(hybrid(" ".join(current), figures) + "\n" + r"\par")
                    current = []
                output.append(r"\noindent " + hybrid(line, figures) + r"\par")
            else:
                current.append(line)
        if current:
            output.append(hybrid(" ".join(current), figures) + "\n" + r"\par")
    return "\n".join(output)


def table_cells(value: str) -> list[list[str]]:
    rows = table_rows(value)
    return [[cell.strip() for cell in re.split(r"(?<!\\)&", row)] for row in rows]


def table_rows(value: str) -> list[str]:
    """Read data cells, not TeX rules, from an imported tabular."""
    without_rules = re.sub(r"\\hline\b", "", value)
    return [row.strip() for row in re.split(r"\\\\\s*(?:\n|$)", without_rules)
            if row.strip()]


def matching_instruction_before_choices(value: str) -> str:
    """Keep the matching instruction as the last prose line before choices."""
    instruction = re.search(r"К каждой позиции первого столбца[^\n.!?]*\.", value, re.I)
    if not instruction:
        return value
    rest = (value[:instruction.start()] + value[instruction.end():]).strip()
    rest = re.sub(r"[ \t]+\n", "\n", rest)
    rest = re.sub(r"\n{3,}", "\n\n", rest)
    lines = rest.splitlines()
    choice = next((index for index, line in enumerate(lines) if re.match(
        r"^[ \t]*(?:[АA][.)][ \t]+|1[.)][ \t]+|\\begin\{tabular\}|"
        r"[А-ЯЁ][А-ЯЁ \t]{4,}:?[ \t]*$)", line)), len(lines))
    return "\n\n".join(part for part in (
        "\n".join(lines[:choice]).strip(), instruction.group(0),
        "\n".join(lines[choice:]).strip()) if part)


def response_labels(problem: dict) -> tuple[str, str] | None:
    """Return the two author response columns for current matching positions."""
    if problem.get("answer_format") != "matching":
        return None
    positions = {int(problem.get("problem_number") or 0),
                 int(problem.get("target_problem_number") or 0)}
    if not positions.intersection(RESPONSE_POSITIONS):
        return None
    statement = problem.get("statement") or ""
    for match in reversed(list(TABLE.finditer(statement))):
        cells = table_cells(match.group(1))
        if len(cells) == 1 and len(cells[0]) == 2:
            return cells[0][0], cells[0][1]
    ordered = ORDERED_RESPONSE.search(statement)
    if ordered:
        return ordered.group(1).strip(), ordered.group(2).strip()
    return "А", "Б"


def remove_response_header(value: str, labels: tuple[str, str] | None) -> str:
    if labels is None:
        return value

    def replace(match: re.Match) -> str:
        cells = table_cells(match.group(1))
        return "" if len(cells) == 1 and len(cells[0]) == 2 else match.group(0)

    return TABLE.sub(replace, value).strip()


def response_table_tex(labels: tuple[str, str], figures: dict[str, Path]) -> str:
    if labels == ("А", "Б"):
        return r"\MatchingAnswer"
    left, right = (hybrid(label, figures) for label in labels)
    return (r"\par\smallskip\noindent\textbf{Ответ:}\par\smallskip"
            r"\begingroup\small\renewcommand{\arraystretch}{1.15}"
            r"\begin{tabularx}{\linewidth}{|X|X|}\hline " + left + " & " + right +
            r"\\\hline\rule{0pt}{8mm} & \\\hline\end{tabularx}\endgroup\par\smallskip")


def normalize_answer_unit(value: str) -> str:
    """Turn an author-written unit phrase into the compact label after the blank."""
    unit = value.strip().rstrip(" .;,")
    unit = (unit.replace(r"\(^2\)", "²").replace(r"\(^3\)", "³")
            .replace(r"\,", "").replace("−", "-")
            .replace(r"\text{", "").replace("}", ""))
    unit = re.sub(r"^\(?\s*", "", unit)
    unit = re.sub(r"\s*\)?$", "", unit)
    lowered = unit.casefold().replace("ё", "е")
    word_map = {key.replace("ё", "е"): result for key, result in ANSWER_UNIT_WORDS.items()}
    if lowered in word_map:
        return format_answer_unit_tex(word_map[lowered])
    direct = unit.replace("^2", "²").replace("^3", "³")
    # Preserve already compact author notation such as Н/м, мДж or м/с².
    if len(direct) <= 18 and not re.search(r"\s", direct) and re.fullmatch(
            r"[A-Za-zА-Яа-яЁё°%/·⋅²³0-9-]+", direct):
        return format_answer_unit_tex(direct)
    return ""


def answer_unit(problem: dict) -> str:
    """Extract only an explicitly stated unit; never infer it from the answer."""
    # Imported Word variants retain the exact suffix printed after the blank.
    # NULL means that the source has not supplied metadata, while an empty
    # string means that the printed answer field was checked and has no unit.
    if problem.get("answer_unit") is not None:
        return format_answer_unit_tex(problem["answer_unit"])
    statement = " ".join((problem.get("statement") or "").split())
    compact = statement.replace(r"\(^2\)", "²").replace(r"\(^3\)", "³")
    pair = re.search(
        r"Ответ\s+запишите\s+в\s+виде\s+\\\([\s\S]{0,140}?"
        r"(?:\\text\{([^}]+)\}|\\,\s*([A-Za-zА-Яа-яЁё°%/²³]+))\\\)",
        compact, re.IGNORECASE,
    )
    if pair:
        return normalize_answer_unit(pair.group(1) or pair.group(2))
    parenthetical = re.search(
        r"Ответ\s+(?:дайте|выразите|запишите)[^.]{0,120}?\(в\s+([^)]+)\)\s*\.",
        compact, re.IGNORECASE,
    )
    if parenthetical:
        return normalize_answer_unit(parenthetical.group(1))
    direct = re.search(
        r"Ответ\s+(?:дайте|выразите)\s+в\s+([^.]+)\.",
        compact, re.IGNORECASE,
    )
    if direct:
        return normalize_answer_unit(direct.group(1))
    # Some KIMs put the unit directly into the question instead of a separate
    # answer instruction (for example, «Сколько моль ...?»).
    question_unit = re.search(r"(?:^|[.!?]\s+)Сколько\s+(моль)\b", compact, re.IGNORECASE)
    return normalize_answer_unit(question_unit.group(1)) if question_unit else ""


def answer_prefix(problem: dict) -> str:
    """Return author text printed between «Ответ:» and the first blank."""
    return problem.get("answer_prefix") or ""


def answer_field(problem: dict) -> dict | None:
    """Describe the short-answer blank shared by the website and generated TeX."""
    kind = problem.get("answer_format")
    if kind in ("qualitative", "worked_solution"):
        return None
    labels = response_labels(problem)
    if labels:
        return {"kind": "table", "labels": list(labels)}
    if kind == "matching":
        number = int(problem.get("problem_number") or 0)
        columns = 3 if (problem.get("exam_year") == 2023 and number == 21 or
                        problem.get("exam_year") == 2022 and number == 2) else 2
        return {"kind": "table", "labels": list("АБВ"[:columns])}
    if kind == "number_pair":
        return {"kind": "pair", "prefix": answer_prefix(problem), "unit": answer_unit(problem)}
    if kind == "multiple_choice":
        return {"kind": "line", "prefix": answer_prefix(problem), "unit": answer_unit(problem)}
    return {"kind": "line", "prefix": answer_prefix(problem), "unit": answer_unit(problem)}


def statement_tex(value: str, figures: dict[str, Path]) -> str:
    output = []
    cursor = 0
    for match in TABLE.finditer(value):
        output.append(prose(value[cursor:match.start()], figures))
        raw_rows = table_rows(match.group(1))
        cells = [re.split(r"(?<!\\)&", row) for row in raw_rows]
        width = max((len(row) for row in cells), default=1)
        if width >= 12:
            spec = "|l|" + "c|" * (width - 1)
            output.append(r"\par\smallskip\noindent\begingroup\scriptsize"
                          r"\resizebox{\linewidth}{!}{\begin{tabular}{" + spec + r"}\hline")
            for row in cells:
                output.append(" & ".join(hybrid(cell.strip(), figures) for cell in row) + r"\\\hline")
            output.append(r"\end{tabular}}\endgroup\par\smallskip")
            cursor = match.end()
            continue
        wide = width >= 8
        first = r">{\raggedright\arraybackslash}p{.14\linewidth}" if wide else "X"
        spec = "|" + "|".join([first] + ["X"] * (width - 1)) + "|"
        size = r"\footnotesize\setlength{\tabcolsep}{2pt}\renewcommand{\arraystretch}{1.2}" if wide else r"\small"
        output.append(r"\par\smallskip\noindent\begingroup" + size + r"\begin{tabularx}{\linewidth}{" + spec + r"}\hline")
        for row in cells:
            output.append(" & ".join(hybrid(cell.strip(), figures) for cell in row) + r"\\\hline")
        output.append(r"\end{tabularx}\endgroup\par\smallskip")
        cursor = match.end()
    output.append(prose(value[cursor:], figures))
    return "\n".join(part for part in output if part)


def answer_macro(problem: dict, figures: dict[str, Path]) -> str:
    field = answer_field(problem)
    if not field:
        return ""
    if field["kind"] == "pair":
        prefix = hybrid(field["prefix"], figures) if field["prefix"] else ""
        unit = hybrid(field["unit"], figures) if field["unit"] else ""
        return r"\PairAnswerWithAffixes{" + prefix + "}{" + unit + "}"
    if field["kind"] == "table":
        labels = field["labels"]
        if labels == ["А", "Б"]:
            return r"\MatchingAnswer"
        if labels == ["А", "Б", "В"]:
            return r"\MatchingAnswerThree"
        return response_table_tex(tuple(labels), figures)
    if field["kind"] == "boxes":
        return r"\AnswerBoxes{" + str(field["count"]) + "}"
    prefix = hybrid(field["prefix"], figures) if field["prefix"] else ""
    unit = hybrid(field["unit"], figures) if field["unit"] else ""
    return r"\AnswerLineWithAffixes{" + prefix + "}{" + unit + "}"


def condition_figure_row(paths: list[Path], captions: tuple[str, ...] = ()) -> str:
    """Place two or three condition images at one height in a single row."""
    if len(paths) not in (2, 3):
        raise ValueError("A condition figure row needs two or three images")
    gap = r"@{\hspace{3mm}}"
    columns = "@{}" + gap.join("c" for _ in paths) + "@{}"
    height = "48mm" if len(paths) == 2 else "43mm"
    images = " & ".join(
        r"\includegraphics[height=" + height + r",keepaspectratio]{figures/" + path.name + "}"
        for path in paths
    )
    rows = [r"\begin{tabular}{" + columns + "}", images + r"\\"]
    if captions:
        if len(captions) != len(paths):
            raise ValueError("Each condition image needs its own caption")
        rows.append(" & ".join(r"\scriptsize " + escape(caption) for caption in captions) + r"\\")
    rows.append(r"\end{tabular}")
    return (r"\par\smallskip\begin{center}\adjustbox{max width=\linewidth}{%" +
            "\n" + "\n".join(rows) + "\n" + r"}\end{center}\smallskip")


def matching_choice_parts(problem: dict, body: str, graph_count: int
                          ) -> tuple[str, list[str], list[str], tuple[str, str]] | None:
    """Separate the prose and the two printed choice columns of a matching task."""
    if problem.get("answer_format") != "matching":
        return None

    def flatten_choice_table(match: re.Match[str]) -> str:
        cells = table_cells(match.group(1))
        if not any(re.match(r"^[АAБB][.)]\s+", cell) for row in cells for cell in row):
            return match.group(0)
        return "\n" + "\n".join(cell for row in cells for cell in row if cell) + "\n"

    source = TABLE.sub(flatten_choice_table, body)
    lines = source.splitlines()

    def is_heading(line: str) -> bool:
        value = line.strip().rstrip(":").strip()
        return bool(re.search(r"[А-ЯЁ]", value) and value.isupper()
                    and not re.match(r"^[АAБB][.)]", value))

    first_choice = next((index for index, line in enumerate(lines) if
                         is_heading(line) or re.match(r"^\s*(?:[АAБB][.)]|1[.)])\s+", line)), -1)
    if first_choice < 0:
        return None
    intro = "\n".join(lines[:first_choice]).strip()
    left: list[str] = []
    right: list[str] = []
    headings: list[str] = []
    active: list[str] | None = None
    for raw in lines[first_choice:]:
        line = raw.strip()
        if not line:
            continue
        if is_heading(line):
            headings.append(line.rstrip(":"))
            active = None
        elif re.match(r"^[АAБB][.)]\s+", line):
            left.append(line)
            active = left
        elif re.match(r"^\d+[.)]\s+", line):
            right.append(line)
            active = right
        elif active:
            active[-1] += " " + line
        else:
            intro = (intro + "\n" + line).strip()
    if len(right) < 3 or not (left or graph_count):
        return None
    instruction = re.search(r"К каждой позиции первого столбца[^\n.!?]*\.", intro, re.I)
    if instruction:
        prose_before = (intro[:instruction.start()] + intro[instruction.end():]).strip()
        intro = prose_before + "\n\n" + instruction.group(0)
    key = (int(problem.get("exam_year") or 0), str(problem.get("variant_number") or ""),
           int(problem.get("problem_number") or 0))
    if key in MATCHING_HEADINGS:
        titles = MATCHING_HEADINGS[key]
    elif graph_count:
        titles = ("ГРАФИКИ", headings[-1] if headings else "ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ")
    else:
        titles = (headings[0] if headings else "", headings[1] if len(headings) > 1 else "")
    return intro, left, right, titles


def matching_column_tex(items: list[str], heading: str, graphs: list[Path],
                        figures: dict[str, Path]) -> str:
    """Fill one borderless matching column, including graphical choices."""
    output = []
    if heading:
        output.append(r"{\centering " + hybrid(heading, figures) + r"\par}\vspace{2mm}")

    def graph_tex(index: int, path: Path) -> str:
        if len(graphs) == 1:
            return (r"\noindent\includegraphics[width=.95\linewidth,height=60mm,keepaspectratio]{figures/" +
                    path.name + r"}\par\smallskip")
        return (r"\noindent\begin{minipage}[t]{5mm}\vspace{0pt}" + "АБ"[index] +
                r")\end{minipage}\begin{minipage}[t]{.82\linewidth}\vspace{0pt}" +
                r"\includegraphics[width=\linewidth,height=31mm,keepaspectratio]{figures/" +
                path.name + r"}\end{minipage}\par\smallskip")

    shown: set[int] = set()
    for item in items:
        placeholder = re.fullmatch(r"([АAБB])[.)]\s*график\s*[АAБB]\s*", item, re.I)
        if placeholder and len(graphs) == 2:
            index = 0 if placeholder.group(1) in "АA" else 1
            output.append(graph_tex(index, graphs[index]))
            shown.add(index)
        else:
            output.append(r"\noindent " + hybrid(item, figures) + r"\par\smallskip")
    for index, path in enumerate(graphs):
        if index not in shown:
            output.append(graph_tex(index, path))
    return "\n".join(output)


def render_problem(problem: dict, figures: dict[str, Path]) -> str:
    number = int(problem["problem_number"])
    body = re.sub(r"(?im)^\s*Ответ\s*:\s*[_ .]*$", "", problem["statement"] or "").strip()
    body = matching_instruction_before_choices(body)
    labels = response_labels(problem)
    body = remove_response_header(body, labels)
    image_paths: list[Path] = []
    for asset in problem.get("assets", []):
        if asset["role"] == "statement_figure" and asset["media_type"].startswith("image/"):
            source = figures.get(asset["id"])
            if source and source.is_file():
                image_paths.append(source)
    figure_key = (int(problem.get("exam_year") or 0), str(problem.get("variant_number") or ""), number)
    if figure_key in MISASSIGNED_STATEMENT_FIGURES:
        image_paths = image_paths[:MISASSIGNED_STATEMENT_FIGURES[figure_key]]
    graph_count = GRAPH_CHOICE_FIGURES.get(figure_key, 0)
    if graph_count > len(image_paths):
        graph_count = 0
    condition_count = len(image_paths) - graph_count
    if len(image_paths) == 5:
        # The old DOCX stores only (1)…(5) in this empty table; the figures
        # themselves now carry those labels directly below the five crops.
        def discard_placeholder(match: re.Match[str]) -> str:
            cells = re.sub(r"\s+", "", match.group(1))
            expected = "&".join(f"(\\({index}\\))" for index in range(1, 6))
            return "" if cells == expected else match.group(0)

        body = re.sub(r"\\begin\{tabular\}\{l\|l\|l\|l\|l\}([\s\S]*?)\\end\{tabular\}",
                      discard_placeholder, body)
    matching = (matching_choice_parts(problem, body, graph_count)
                if condition_count <= 3 else None)
    if matching:
        intro, left_choices, right_choices, headings = matching
        if figure_key == (2022, "1", 19):
            # This two-cell tabular repeats the captions of the condition
            # figures; it is not another matching-choice table.
            intro = TABLE.sub(lambda match: "" if "Рис." in match.group(1) else match.group(0), intro)
        parts = [r"\begin{ExamTask}"]
        if condition_count == 1:
            parts.append(r"\TaskWithRightFigure{" + str(number) + "}{" +
                         statement_tex(intro, figures) + "}{figures/" + image_paths[0].name + "}")
        else:
            parts.extend((r"\TaskStart{" + str(number) + "}", statement_tex(intro, figures)))
        if condition_count in (2, 3):
            captions = CONDITION_FIGURE_CAPTIONS.get(figure_key, ())
            if condition_count == 3 and re.search(r"рис\.\s*\\\(1\\\)", intro, re.I) and not captions:
                captions = tuple(f"Рис. {index}" for index in range(1, 4))
            parts.append(condition_figure_row(image_paths[:condition_count], captions))
        left = matching_column_tex(left_choices, headings[0], image_paths[condition_count:], figures)
        right = matching_column_tex(right_choices, headings[1], [], figures)
        parts.append(r"\MatchingChoices{" + left + "}{" + right + "}")
        parts.append(response_table_tex(labels, figures) if labels else answer_macro(problem, figures))
        parts.append(r"\end{ExamTask}")
        return "\n".join(part for part in parts if part)
    parts = [r"\begin{ExamTask}"]
    if len(image_paths) == 1:
        parts.append(r"\TaskWithRightFigure{" + str(number) + "}{" +
                     statement_tex(body, figures) + "}{figures/" + image_paths[0].name + "}")
    else:
        parts.extend((r"\TaskStart{" + str(number) + "}", statement_tex(body, figures)))
    numbered_photos = (condition_count == 3 and
                       re.search(r"рис\.\s*\\\(1\\\)", body, re.IGNORECASE))
    if condition_count in (2, 3):
        captions = CONDITION_FIGURE_CAPTIONS.get(figure_key, ())
        if numbered_photos and not captions:
            captions = tuple(f"Рис. {index}" for index in range(1, condition_count + 1))
        parts.append(condition_figure_row(image_paths[:condition_count], captions))
        image_paths = image_paths[condition_count:]
    if len(image_paths) == 5:
        parts.append(r"\par\smallskip\begin{center}")
        for index, source in enumerate(image_paths, 1):
            parts.append(r"\begin{minipage}[t]{.19\linewidth}\centering"
                         r"\includegraphics[width=\linewidth,height=39mm,keepaspectratio]{figures/"
                         + source.name + r"}\par\scriptsize " + str(index) + r")\end{minipage}")
            if index < 5:
                parts.append(r"\hfill")
        parts.append(r"\end{center}")
    elif len(image_paths) >= 3:
        # Multi-figure matching tasks need compact rows to keep every graph
        # visible with its statement on one page.
        parts.append(r"\par\smallskip\begin{center}")
        for index in range(0, len(image_paths), 2):
            row = image_paths[index:index + 2]
            for offset, source in enumerate(row):
                caption = (r"\par\scriptsize(" + str(index + offset + 1) + ")"
                           if len(image_paths) >= 5 else "")
                parts.append(r"\begin{minipage}{.46\linewidth}\centering"
                             r"\includegraphics[width=\linewidth,height=37mm,keepaspectratio]{figures/"
                             + source.name + "}" + caption + r"\end{minipage}")
                if offset == 0 and len(row) == 2:
                    parts.append(r"\hfill")
            parts.append(r"\par\smallskip")
        parts.append(r"\end{center}")
    elif len(image_paths) == 2:
        for source in image_paths:
            parts.append(r"\TaskFigure{figures/" + source.name + "}")
    elif len(image_paths) == 1 and condition_count in (2, 3):
        parts.append(r"\TaskFigure{figures/" + image_paths[0].name + "}")
    parts.append(response_table_tex(labels, figures) if labels else answer_macro(problem, figures))
    parts.append(r"\end{ExamTask}")
    return "\n".join(part for part in parts if part)


def criteria_tex(value: str, figures: dict[str, Path]) -> str:
    """Keep each score and criterion heading on its own line."""
    output = []
    for raw in value.splitlines():
        line = raw.strip()
        if not line:
            continue
        score = SCORE.match(line)
        if score:
            points, description = score.groups()
            if re.fullmatch(r"Максимальный балл\.?", description):
                output.append(r"\CriterionMaximum{Максимум: " + points + " " +
                              ("балл" if points == "1" else "балла" if points in ("2", "3", "4") else "баллов") + "}")
            else:
                output.append(r"\CriterionScore{" + points + " " +
                              ("балл" if points == "1" else "балла" if points in ("2", "3", "4") else "баллов") + "}")
                if description:
                    output.append(r"\CriterionText{" + statement_tex(description, figures) + "}")
            continue
        if line.startswith("Критерий"):
            output.append(r"\CriterionHeading{" + hybrid(line, figures) + "}")
            continue
        if line.startswith("Максимум"):
            output.append(r"\CriterionMaximum{" + hybrid(line, figures) + "}")
            continue
        roman = ROMAN.match(line)
        alternative = ALTERNATIVE.match(line)
        if roman or alternative:
            marker, description = (roman or alternative).groups()
            output.append(r"\CriterionElement{" + escape(marker) + "}{" +
                          statement_tex(description, figures) + "}")
        else:
            output.append(r"\CriterionText{" + statement_tex(line, figures) + "}")
    return "\n".join(output)


def render_material_problem(problem: dict, document: str, figures: dict[str, Path]) -> str:
    number = str(problem["problem_number"])
    value = (problem[{"answers": "answer", "solutions": "solution", "criteria": "criteria"}[document]] or "").strip()
    if not value and document != "answers":
        return ""
    parts = ([r"\MaterialTask{" + number + "}"] if document == "answers" else
             [r"\begin{MaterialTaskBlock}", r"\MaterialTaskStart{" + number + "}"])
    if document == "criteria":
        parts.append(r"\par" + "\n" + criteria_tex(value, figures))
    else:
        parts.append(statement_tex(value, figures) if value else r"\emph{Ответ в базе не указан.}\par")
    if document == "solutions":
        for asset in problem.get("assets", []):
            if asset["role"] == "solution_figure" and asset["media_type"].startswith("image/"):
                source = figures.get(asset["id"])
                if source and source.is_file():
                    parts.append(r"\MaterialFigure{figures/" + source.name + "}")
    parts.append(r"\par" if document == "answers" else r"\end{MaterialTaskBlock}")
    return "\n".join(parts)


def compose(problems: list[dict], title: str, year: int, assets_root: Path,
            formulas_root: Path, document: str = "conditions") -> tuple[str, dict[str, Path]]:
    numbers = [int(problem["problem_number"]) for problem in problems]
    if numbers not in (list(range(1, 27)), list(range(1, 31))):
        raise ValueError("Нужны задания с последовательными номерами 1–26 или 1–30")
    if document not in ("conditions", "answers", "solutions", "criteria"):
        raise ValueError("Неизвестный вид печатного материала")
    field = {"conditions": "statement", "answers": "answer", "solutions": "solution",
             "criteria": "criteria"}[document]
    figure_role = "statement_figure" if document == "conditions" else "solution_figure" if document == "solutions" else None
    figures: dict[str, Path] = {}
    for problem in problems:
        for asset in problem.get("assets", []):
            if asset["role"] != figure_role or not asset["media_type"].startswith("image/"):
                continue
            relative = Path(asset["storage_path"].replace("\\", "/"))
            if len(relative.parts) >= 4 and relative.parts[:2] == ("assets", "objects"):
                source = assets_root / Path(*relative.parts[2:])
                if source.is_file():
                    figures[asset["id"]] = source
        for sha in re.findall(r"\[\[formula:([0-9a-f]{64}):\d+:\d+\]\]", problem[field] or ""):
            source = formulas_root / sha[:2] / (sha + ".png")
            if source.is_file():
                figures[f"formula/{sha}"] = source
    if document == "conditions":
        template = (TEX_DIR / "variant.tex").read_text(encoding="utf-8")
        if len(problems) == 30:
            template = (template.replace("26 заданий", "30 заданий")
                        .replace("1--20", "1--23").replace("21--26", "24--30"))
        reference = (TEX_DIR / "reference.tex").read_text(encoding="utf-8")
        rendered = [render_problem(problem, figures) for problem in problems]
        content = (template.replace("%<PHYS_EGE_META>",
                                    r"\renewcommand{\VariantTitle}{" + escape(title) + "}\n" +
                                    r"\renewcommand{\VariantYear}{" + str(year) + "}")
                   .replace(r"\input{reference.tex}", reference)
                   .replace("%<PHYS_EGE_PART_ONE>", "\n".join(rendered[:23 if len(problems) == 30 else 20]))
                   .replace("%<PHYS_EGE_PART_TWO>", "\n".join(rendered[23 if len(problems) == 30 else 20:])))
    else:
        template = (TEX_DIR / (document + ".tex")).read_text(encoding="utf-8")
        base = (TEX_DIR / "materials_base.tex").read_text(encoding="utf-8")
        rendered = [render_material_problem(problem, document, figures) for problem in problems]
        content = (template.replace(r"\input{materials_base.tex}", base)
                   .replace("%<PHYS_EGE_META>", r"\renewcommand{\VariantTitle}{" + escape(title) + "}")
                   .replace("%<PHYS_EGE_CONTENT>", "\n".join(part for part in rendered if part)))
    return content, figures


def project_zip(content: str, figures: dict[str, Path], filename: str = "variant.tex") -> bytes:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content)
        for source in set(figures.values()):
            archive.write(source, "figures/" + source.name)
    return memory.getvalue()


def compile_pdf(content: str, figures: dict[str, Path]) -> bytes:
    engine = shutil.which("xelatex")
    if not engine:
        raise RuntimeError("На сервере не установлен XeLaTeX")
    with tempfile.TemporaryDirectory(prefix="physege-tex-") as name:
        root = Path(name)
        (root / "figures").mkdir()
        (root / "variant.tex").write_text(content, encoding="utf-8")
        for source in set(figures.values()):
            shutil.copy2(source, root / "figures" / source.name)
        result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error",
                                 "-no-shell-escape", "variant.tex"], cwd=root,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=90, check=False)
        pdf = root / "variant.pdf"
        if result.returncode or not pdf.is_file():
            message = result.stdout.decode("utf-8", "replace")[-2500:]
            raise RuntimeError("Ошибка компиляции TeX: " + message)
        return pdf.read_bytes()

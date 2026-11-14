"""Compose exam sheets and companion materials from reusable XeLaTeX templates."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


TEX_DIR = Path(__file__).with_name("tex")
MATH = re.compile(r"(\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\[\[formula:[0-9a-f]{64}:\d+:\d+\]\])")
TABLE = re.compile(r"\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}")
FORMULA = re.compile(r"\[\[formula:([0-9a-f]{64}):\d+:\d+\]\]")
ORDERED_RESPONSE = re.compile(
    r"Запишите выбранные цифры в порядке:\s*(.+?)\s*;\s*(.+?)\.\s*Цифры могут повторяться",
    re.IGNORECASE | re.DOTALL,
)
RESPONSE_POSITIONS = {6, 10, 15, 17}
SCORE = re.compile(r"^\\\((\d+)\\\)\s+балл[аов]*[.:]\s*(.*)$")
ROMAN = re.compile(r"^(IV|III|II|I|V)\)\s*(.*)$")
ALTERNATIVE = re.compile(r"^(И\s*\(ИЛИ\)|ИЛИ)\s*(.*)$")
SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


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
    rows = [row.strip() for row in re.split(r"\\\\\s*(?:\n|$)", value) if row.strip()]
    return [[cell.strip() for cell in re.split(r"(?<!\\)&", row)] for row in rows]


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


def statement_tex(value: str, figures: dict[str, Path]) -> str:
    output = []
    cursor = 0
    for match in TABLE.finditer(value):
        output.append(prose(value[cursor:match.start()], figures))
        raw_rows = [row.strip() for row in re.split(r"\\\\\s*(?:\n|$)", match.group(1)) if row.strip()]
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


def answer_macro(problem: dict) -> str:
    number = int(problem["problem_number"])
    kind = problem["answer_format"]
    if kind in ("qualitative", "worked_solution"):
        return ""
    if kind == "number_pair":
        return r"\PairAnswer"
    if kind == "matching":
        if (problem.get("exam_year") == 2023 and number == 21 or
                problem.get("exam_year") == 2022 and number == 2):
            return r"\MatchingAnswerThree"
        return r"\MatchingAnswer"
    if kind == "multiple_choice":
        return r"\AnswerBoxes{2}" if (number == 20 and problem.get("exam_year") != 2022 or
                                       number == 23 and problem.get("exam_year") == 2022) else r"\AnswerLine"
    return r"\AnswerLine"


def render_problem(problem: dict, figures: dict[str, Path]) -> str:
    number = int(problem["problem_number"])
    body = re.sub(r"(?im)^\s*Ответ\s*:\s*[_ .]*$", "", problem["statement"] or "").strip()
    labels = response_labels(problem)
    body = remove_response_header(body, labels)
    parts = [r"\begin{ExamTask}", r"\TaskStart{" + str(number) + "}", statement_tex(body, figures)]
    image_paths: list[Path] = []
    for asset in problem.get("assets", []):
        if asset["role"] == "statement_figure" and asset["media_type"].startswith("image/"):
            source = figures.get(asset["id"])
            if source and source.is_file():
                image_paths.append(source)
    numbered_photos = (len(image_paths) == 3 and
                       re.search(r"рис\.\s*\\\(1\\\)", body, re.IGNORECASE))
    if numbered_photos:
        parts.append(r"\par\smallskip\begin{center}")
        source = image_paths[0]
        parts.append(r"\includegraphics[width=.75\linewidth,height=48mm,keepaspectratio]{figures/"
                     + source.name + r"}\par\scriptsize Рис. 1\par\smallskip")
        for index, source in enumerate(image_paths[1:], 2):
            parts.append(r"\begin{minipage}{.46\linewidth}\centering"
                         r"\includegraphics[width=\linewidth,height=38mm,keepaspectratio]{figures/"
                         + source.name + r"}\par\scriptsize Рис. " + str(index) + r"\end{minipage}")
            if index == 2:
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
    else:
        for source in image_paths:
            parts.append(r"\TaskFigure{figures/" + source.name + "}")
    parts.append(response_table_tex(labels, figures) if labels else answer_macro(problem))
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

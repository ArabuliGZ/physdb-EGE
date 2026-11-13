"""Compose exam condition sheets from database problems and one XeLaTeX template."""
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


def statement_tex(value: str, figures: dict[str, Path]) -> str:
    output = []
    cursor = 0
    for match in TABLE.finditer(value):
        output.append(prose(value[cursor:match.start()], figures))
        raw_rows = [row.strip() for row in re.split(r"\\\\\s*(?:\n|$)", match.group(1)) if row.strip()]
        cells = [re.split(r"(?<!\\)&", row) for row in raw_rows]
        width = max((len(row) for row in cells), default=1)
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
    if number >= 21:
        return ""
    kind = problem["answer_format"]
    if kind == "number_pair":
        return r"\PairAnswer"
    if kind == "matching":
        return r"\MatchingAnswer"
    if kind == "multiple_choice":
        return r"\AnswerBoxes{2}" if number == 20 else r"\AnswerLine"
    return r"\AnswerLine"


def render_problem(problem: dict, figures: dict[str, Path]) -> str:
    number = int(problem["problem_number"])
    body = re.sub(r"(?im)^\s*Ответ\s*:\s*[_ .]*$", "", problem["statement"] or "").strip()
    parts = [r"\TaskStart{" + str(number) + "}", statement_tex(body, figures)]
    for asset in problem.get("assets", []):
        if asset["role"] == "statement_figure" and asset["media_type"].startswith("image/"):
            source = figures.get(asset["id"])
            if source and source.is_file():
                parts.append(r"\TaskFigure{figures/" + source.name + "}")
    parts.append(answer_macro(problem))
    return "\n".join(part for part in parts if part)


def compose(problems: list[dict], title: str, year: int, assets_root: Path,
            formulas_root: Path) -> tuple[str, dict[str, Path]]:
    numbers = [int(problem["problem_number"]) for problem in problems]
    if numbers != list(range(1, 27)):
        raise ValueError("Нужны ровно 26 заданий: по одному на каждый номер от 1 до 26")
    figures: dict[str, Path] = {}
    for problem in problems:
        for asset in problem.get("assets", []):
            if asset["role"] != "statement_figure" or not asset["media_type"].startswith("image/"):
                continue
            relative = Path(asset["storage_path"].replace("\\", "/"))
            if len(relative.parts) >= 4 and relative.parts[:2] == ("assets", "objects"):
                source = assets_root / Path(*relative.parts[2:])
                if source.is_file():
                    figures[asset["id"]] = source
        for sha in re.findall(r"\[\[formula:([0-9a-f]{64}):\d+:\d+\]\]", problem["statement"]):
            source = formulas_root / sha[:2] / (sha + ".png")
            if source.is_file():
                figures[f"formula/{sha}"] = source
    template = (TEX_DIR / "variant.tex").read_text(encoding="utf-8")
    reference = (TEX_DIR / "reference.tex").read_text(encoding="utf-8")
    rendered = [render_problem(problem, figures) for problem in problems]
    content = (template.replace("%%VARIANT_TITLE%%", escape(title))
               .replace("%%YEAR%%", str(year))
               .replace("%%REFERENCE%%", reference)
               .replace("%%PART_ONE%%", "\n".join(rendered[:20]))
               .replace("%%PART_TWO%%", "\n".join(rendered[20:])))
    return content, figures


def project_zip(content: str, figures: dict[str, Path]) -> bytes:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("variant.tex", content)
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

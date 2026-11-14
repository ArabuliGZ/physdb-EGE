"""Import four original Demidova 2022 DOCX papers with source number 1–30.

No record is marked verified until its complete original page has been
checked visually. The MathType dictionary is a transcription draft.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

from docx import Document

from import_examples import DB, ROOT, assess, upsert_problem, upsert_variant
from curated_answers_2022 import EXTENDED_ANSWERS
from import_2023 import clean_mtef, numbered
from import_2026_remaining import (add_figures, extract_blocks, formula_marker,
                                    normalize_statement, normalized_figure_png,
                                    review_sections, VERIFIED_FORMULAS,
                                    SOURCE_MATHML_FORMULAS)
from mapping_2022_2027 import SOURCE_FORMAT, SOURCE_TOPIC, assessment, source_points
from migrate_problem_range import allow_thirty_source_numbers
from text_repairs import repair_text
from verified_solutions import VERIFIED_SOLUTIONS


SOURCE_ROOT = ROOT / "Материалы" / "ЕГЭ от Демидовой" / "От Демидовой до 2023 года"
SOURCES = {
    1: "2022 B1.docx", 2: "2022 В2.docx",
    3: "2022 B3.docx", 4: "2022 B4.docx",
}
FORMULAS = json.loads((ROOT / "tools" / "2022_formulas.json").read_text(encoding="utf-8"))
DIAGRAM_FORMULAS = {
    "f60dae7a2048085fb69c0beae6ff33e5ec2bedfb935d91c1c48ec79682044e25", # 1/25 vessel
    "71784ad6b46323b2f55b0140f73da8f17cb0c0b0c131755a26d04f8bdf6135e5", # 3/24 electroscope
}
CURATED_STATEMENT_FIGURES = {
    (1, 13): ("2022-1-13-gas-graph.png", "9bd0f47f4576952c0559cbcd3cfca9ac461775f85303906a8b8335f0a66f99d6"),
    (2, 3): ("2022-2-3-velocity-graph.png", "582cac98718e3681f2f686c119c849f1397a45184adfffba6535f4872f58b0f3"),
    (3, 3): ("2022-3-3-force-grid.png", "80fffed187a008e96e5aaecaf5f21e6e9296b103eb3179cf3d41c61a5b86f9be"),
    (3, 12): ("2022-3-12-gas-graph.png", "e3bb1e23517ffe9ffe833b4a9b93a3117253a05e605b8ab65155a55b12615dc2"),
    (3, 16): ("2022-3-16-current-graph.png", "910730943e55bfbcd0839a1e5c45b04456941eb3788872647df1304d4db58dcf"),
}
MISPLACED_STATEMENT_FIGURES = {
    (1, 12): {"8149be83c2ee0975c535a00c49d7a8f325f5e047cd8c41fcdfaa9bac93f9a049"},  # labels of task 13
    (1, 22): {"6dd51cb08fac6f157a25bd969bc1d6abe0ff6713693cae26e6b84dad744c7642"},  # task 23 circuit
    (1, 23): {"f0114b5d5b6e1c480e82b74c07df3981b1b0926a7fc00d240672e6648173ae1d"},  # exam notice
    (2, 2): {"568cb087039638376a042bd5348d972949b81b2279fc7f31a22d053df668abdf"},  # task 3 graph
    (2, 23): {"f0114b5d5b6e1c480e82b74c07df3981b1b0926a7fc00d240672e6648173ae1d"},
    (3, 2): {"65acfa56fb7baec7a6242be8b8092b3964899e6b46e108385f990a321350e0ea"},  # task 3 grid
    (3, 15): {"f31c3844fe433ab1894146742d14a37a105e4746300adb632493689b24608935"},  # task 16 graph
    (3, 23): {"f0114b5d5b6e1c480e82b74c07df3981b1b0926a7fc00d240672e6648173ae1d"},
    (4, 23): {"f0114b5d5b6e1c480e82b74c07df3981b1b0926a7fc00d240672e6648173ae1d"},
}
ORDERED_STATEMENT_FIGURES = {
    (2, 2): (
        "e3afbb3d8764d271283f4dddfa8e776f64f6eff9155e45fdb39260ba0f903afe",
        "87907fcd746be2acd6e32cf488bdd7a4e900f0bd6cd170c014c5d4e0cfad193a",
        "f92eec3d4498c6b60336ce0700a3a622d55441462d4f8ca626037c5be5abaf41",
        "e2d178946eb37089e69a4278c93df0336a93ff0a94bbe44cb19faabcfeeded01",
        "b6436a40fd91cdc3cff2dcbec988215e8d837460cdf81a505564fda920be6889",
    ),  # source PDF p. 5, graphs 1–5
}
FLOATING_STARTS = {
    1: {3: 60}, 2: {3: 72, 9: 158},
    3: {3: 68, 9: 133}, 4: {3: 57, 9: 117},
}
PAIRED_KEYS = {
    1: ("0,800,05", r"\(0{,}80\pm0{,}05\)"),
    2: ("0,40,1", r"\(0{,}4\pm0{,}1\)"),
    3: ("451", r"\(45\pm1\)"),
    4: ("3,80,1", r"\(3{,}8\pm0{,}1\)"),
}


def source_key(doc) -> dict[int, str]:
    table = next((t for t in doc.tables
                  if len(t.rows) == 13 and len(t.columns) == 4
                  and t.cell(0, 0).text.strip() == "Номер задания"), None)
    if table is None:
        raise ValueError("Missing 2022 printed answer key")
    key: dict[int, str] = {}
    for row in table.rows[1:]:
        for col in (0, 2):
            number = row.cells[col].text.strip()
            answer = row.cells[col + 1].text.strip()
            if number:
                key[int(number)] = answer
    if set(key) != set(range(1, 24)) or not all(key.values()):
        raise ValueError("Incomplete 2022 author key")
    return key


def clean_2022_mtef(tex: str) -> str:
    tex = clean_mtef(tex)
    tex = tex.replace(r"\_", r"{}_")
    tex = tex.replace(r"\left[\right.", r"\left[")
    tex = tex.replace(r"\left]\right.", r"\right]")
    tex = tex.replace(r"\left.\right}", "")
    tex = tex.replace(r"\left.\right]", r"\right]")
    tex = tex.replace(r"\left.\right|", r"\right|")
    tex = tex.replace("s i n", r"\sin").replace("c o s", r"\cos")
    tex = tex.replace(r"\text{s} \text{i} \text{n}", r"\sin")
    tex = tex.replace(r"\text{c} \text{o} \text{s}", r"\cos")
    tex = re.sub(r"(?<![A-Za-zА-Яа-я])(?:\d\s){1,}\d", lambda m: m.group().replace(" ", ""), tex)
    tex = re.sub(r"(?<=\d)\s*,\s*(?=\d)", "{,}", tex)
    tex = tex.replace("{к p}", r"{\text{кр}}")
    tex = tex.replace("{н a ч}", r"{\text{нач}}")
    tex = tex.replace("{к o н}", r"{\text{кон}}")
    tex = tex.replace("{н}", r"{\text{н}}")
    tex = tex.replace("{н \\text{1}}", r"{\text{н}1}")
    tex = tex.replace("{н \\text{2}}", r"{\text{н}2}")
    tex = tex.replace("{А p x}", r"{\text{Арх}}")
    tex = tex.replace("{э л}", r"{\text{эл}}")
    tex = tex.replace("{ц}", r"{\text{ц}}")
    tex = tex.replace("{к}", r"{\text{к}}")
    tex = tex.replace(r"{\phi o т}", r"{\text{фот}}")
    tex = tex.replace(" К", r"\,\text{К}").replace(r"\circ С", r"^\circ\text{С}")
    tex = tex.replace(" с м", r"\,\text{см}")
    tex = tex.replace(r"\text{c} м^{\text{2}}", r"\,\text{см}^{2}")
    tex = re.sub(r"\s+([КНмсВАФГцДж])\s*/\s*([КНмсВАФГцДж])",
                 lambda m: rf"\,\text{{{m.group(1)}/{m.group(2)}}}", tex)
    return tex


def formula_tex(value: str | None, embedded: list[tuple[bytes, tuple[int, int]]],
                figures: list[bytes]) -> str | None:
    if value is None:
        return None
    for index, (data, _) in enumerate(embedded):
        marker = formula_marker(index)
        if marker not in value:
            continue
        sha = hashlib.sha256(normalized_figure_png(data)).hexdigest()
        if sha in DIAGRAM_FORMULAS:
            figures.append(data)
            value = value.replace(marker, "")
            continue
        match = FORMULAS.get(sha) or VERIFIED_FORMULAS.get(sha) or SOURCE_MATHML_FORMULAS.get(sha)
        if not match or not match.get("tex"):
            raise ValueError(f"Untranscribed 2022 formula: {sha}")
        value = value.replace(marker, r"\(" + clean_2022_mtef(match["tex"]) + r"\)")
    if "[[SRCFORMULA" in value or "[[formula:" in value or "[формула в исходном" in value:
        raise ValueError("Unresolved 2022 formula marker")
    return value


def format_2022_criteria(value: str) -> str:
    """Preserve every source rubric row as a separate score or heading block."""
    value = value.removeprefix("Краткая расшифровка критериев; полный текст в исходном DOCX.\n")
    value = value.replace("недостатков.В ", "недостатков.\nВ ")
    value = re.sub(r"(?<!\n)(?=И \(ИЛИ\) )", "\n", value)
    value = re.sub(r"(?<!\n)(?=ИЛИ )", "\n", value)
    value = value.replace(r"\(1\) балла:", r"\(1\) балл:")
    value = value.replace(r"\(0\) балла:", r"\(0\) баллов:")
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def import_one(con: sqlite3.Connection, variant: int) -> None:
    source = SOURCE_ROOT / SOURCES[variant]
    doc = Document(source)
    text = [paragraph.text.strip() for paragraph in doc.paragraphs]
    end = next(i for i, line in enumerate(text)
               if line.startswith("Система оценивания экзаменационной работы"))
    rubric_start = next(i for i, line in enumerate(text)
                        if line.startswith("Критерии оценивания выполнения заданий"))
    starts = numbered(doc, 40, end, 1, 30)
    reviews = numbered(doc, rubric_start + 1, len(text), 24, 30)
    for task, index in FLOATING_STARTS[variant].items():
        if not text[index] or text[index].isdigit():
            raise ValueError(f"Floating task {variant}-{task} source moved")
        starts[task] = index
    key = source_key(doc)
    raw_pair, formatted_pair = PAIRED_KEYS[variant]
    if key[22] != raw_pair:
        raise ValueError(f"Task 22 answer changed for 2022-{variant}")
    vid = upsert_variant(con, source, 2022, str(variant),
                         f"Демидова 2022, вариант {variant}", False)
    moved_circuit: bytes | None = None
    for task in range(1, 31):
        stop = starts.get(task + 1, end)
        embedded: list[tuple[bytes, tuple[int, int]]] = []
        raw, statement_figures = extract_blocks(doc, starts[task], stop, embedded)
        cleaned_figures: list[bytes] = []
        for figure in statement_figures:
            sha = hashlib.sha256(normalized_figure_png(figure)).hexdigest()
            if sha in MISPLACED_STATEMENT_FIGURES.get((variant, task), set()):
                if (variant, task) == (1, 22):
                    moved_circuit = figure
                continue
            cleaned_figures.append(figure)
        statement_figures = cleaned_figures
        if (variant, task) in ORDERED_STATEMENT_FIGURES:
            by_sha = {hashlib.sha256(normalized_figure_png(figure)).hexdigest(): figure
                      for figure in statement_figures}
            order = ORDERED_STATEMENT_FIGURES[(variant, task)]
            if set(by_sha) != set(order):
                raise ValueError(f"2022-{variant} task {task} figure set changed")
            statement_figures = [by_sha[sha] for sha in order]
        if (variant, task) == (1, 23):
            if moved_circuit is None:
                raise ValueError("2022-1 task 23 circuit was not found before task 22")
            statement_figures.append(moved_circuit)
        if (variant, task) in CURATED_STATEMENT_FIGURES:
            filename, expected_sha = CURATED_STATEMENT_FIGURES[(variant, task)]
            path = ROOT / "assets" / "curated" / "figure_repairs" / filename
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != expected_sha:
                raise ValueError(f"2022-{variant} task {task} curated figure changed")
            if statement_figures:
                raise ValueError(f"Unexpected extra figure in 2022-{variant} task {task}")
            statement_figures = [content]
        statement = formula_tex(normalize_statement(raw), embedded, statement_figures)
        assert statement is not None
        statement = repair_text(f"2022-{variant}", task, "statement", statement)
        if task == 24:
            statement, separator, _ = statement.partition("\nПолное правильное решение")
            if not separator:
                raise ValueError(f"Missing 2022-{variant} task 24 instruction boundary")
            statement = statement.rstrip()
        if len(statement.strip()) < 20:
            raise ValueError(f"Damaged 2022-{variant} task {task}")

        solution = criteria = None
        solution_figures: list[bytes] = []
        if task >= 24:
            review_formulas: list[tuple[bytes, tuple[int, int]]] = []
            solution, criteria, solution_figures = review_sections(
                doc, reviews[task], reviews.get(task + 1, len(text)), review_formulas)
            solution = formula_tex(solution, review_formulas, solution_figures)
            criteria = formula_tex(criteria, review_formulas, solution_figures)
            solution = repair_text(f"2022-{variant}", task, "solution", solution)
            criteria = repair_text(f"2022-{variant}", task, "criteria", criteria)
            if not solution or not criteria:
                raise ValueError(f"Missing solution or criteria for 2022-{variant} #{task}")
            checked_solution = VERIFIED_SOLUTIONS.get((f"2022-{variant}", task))
            if checked_solution:
                solution = checked_solution[1]
            criteria = format_2022_criteria(criteria)

        locator = f"DOCX paragraphs {starts[task]}–{stop - 1}"
        review_notes = ("Первичная расшифровка исходного DOCX и объектов MathType; "
                        "визуальная проверка полного текста, формул, рисунков и решения не завершена.")
        if task >= 24:
            review_notes += (f" Решение и критерии: абзацы {reviews[task]}–"
                             f"{reviews.get(task + 1, len(text)) - 1}.")
        answer = (EXTENDED_ANSWERS[(variant, task)] if task >= 24 else
                  formatted_pair if task == 22 else key[task])
        pid = upsert_problem(con, vid, task, 1, statement, answer, solution, criteria,
                             SOURCE_TOPIC[task], locator, review_notes, "needs_review",
                             max_points=source_points(variant, task), answer_format=SOURCE_FORMAT[task])
        con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role IN ('statement_figure','solution_figure')", (pid,))
        add_figures(con, pid, statement_figures, "statement_figure", locator)
        add_figures(con, pid, solution_figures, "solution_figure",
                    f"DOCX rubric paragraphs {reviews[task]}–{reviews.get(task + 1, len(text)) - 1}"
                    if task >= 24 else locator)
        con.execute("DELETE FROM relevance WHERE problem_id=? AND exam_year=2027", (pid,))
        target, verdict, topic_ok, format_ok, reason = assessment(variant, task)
        assess(con, pid, target, topic_ok, format_ok, verdict, reason)
    print(f"2022-{variant}: 30 tasks, 23 printed answers, 7 solutions and criteria")


def main() -> None:
    con = sqlite3.connect(DB)
    allow_thirty_source_numbers(con)
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    con.execute("PRAGMA foreign_keys=ON")
    with con:
        for variant in SOURCES:
            import_one(con, variant)
        # A corrected figure assignment may leave an unused asset record from
        # a previous import. The image file can stay for source traceability.
        con.execute("DELETE FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)")
    if con.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Foreign key errors after 2022 import")
    count = con.execute("""SELECT COUNT(*) FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2022""").fetchone()[0]
    if count != 120:
        raise ValueError(f"Expected 120 2022 tasks; got {count}")
    print("Imported 2022 tasks:", count)
    con.close()


if __name__ == "__main__":
    main()

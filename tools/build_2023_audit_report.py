"""Write a reviewable 2023-to-2027 decision table from the local database."""
from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
OUTPUT = ROOT / "AUDIT_2023_2027.md"


def cell(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("|", r"\|").replace("\n", " ").strip()


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT v.variant_number,p.problem_number,p.answer,p.extraction_status,
               r.target_problem_number,r.verdict,r.reason
        FROM variants v JOIN problems p ON p.variant_id=v.id
        JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027
        WHERE v.exam_year=2023
        ORDER BY CAST(v.variant_number AS INTEGER),p.problem_number
    """).fetchall()
    assert len(rows) == 90
    counts = Counter(row["verdict"] for row in rows)
    by_source = {(int(row["variant_number"]), row["problem_number"]): row for row in rows}
    lines = [
        "# Сверка вариантов Демидовой 2023 с проектом ЕГЭ 2027",
        "",
        "Проверены все 90 условий: основной текст каждого задания сопоставлен с "
        "абзацами авторского DOCX. Все 69 коротких ответов сопоставлены с "
        "напечатанными ключами; для №22 отдельно проверены шкалы приборов и "
        "разделены показание и погрешность. Итоги 21 развёрнутой задачи "
        "перенесены из авторских решений. Для каждого упоминания рисунка, "
        "графика или диаграммы проверено наличие отдельного изображения.",
        "",
        f"По проектной спецификации 2027 года: **{counts['yes']} полностью**, "
        f"**{counts['partial']} частично**, **{counts['no']} не подходят**. "
        "Исходные номера 1–30 сохраняются в цельных вариантах. В каталог "
        "2027 года попадают только yes и partial под целевыми номерами 1–26.",
        "Для строк «Нет» в столбце 2027 указан ближайший проверенный кандидат, "
        "а не допустимая позиция этой задачи.",
        "",
        "Сверка текста и ответов не означает завершённой визуальной проверки "
        "каждого объекта MathType и полного решения. Поэтому статус записей "
        "needs_review; оценка пригодности от него независима. Основа "
        "вердиктов — проектные документы ФИПИ 2027 и "
        "[таблица правил](YEAR_POSITION_MAPPING.md).",
    ]
    labels = {"yes": "Да", "partial": "Частично", "no": "Нет"}
    lines.extend([
        "",
        "## Сводная таблица соответствия",
        "",
        "В ячейке сначала указан номер позиции 2027 года, затем вердикт. "
        "Для «Нет» это проверенный кандидат, а не допустимая позиция.",
        "",
        "| № 2023 | Вариант 1 | Вариант 2 | Вариант 3 |",
        "| ---: | --- | --- | --- |",
    ])
    for number in range(1, 31):
        cells = []
        for variant in (1, 2, 3):
            row = by_source[(variant, number)]
            cells.append(f"{row['target_problem_number']} · {labels[row['verdict']]}")
        lines.append(f"| {number} | " + " | ".join(cells) + " |")
    for variant in (1, 2, 3):
        lines.extend([
            "",
            f"## Вариант {variant}",
            "",
            "| № 2023 | Ответ | Кандидат № 2027 | Вердикт | Причина ограничения |",
            "| ---: | --- | ---: | --- | --- |",
        ])
        for row in rows:
            if int(row["variant_number"]) != variant:
                continue
            reason = row["reason"] if row["verdict"] != "yes" else "—"
            lines.append(
                f"| {row['problem_number']} | {cell(row['answer'])} | "
                f"{row['target_problem_number']} | {labels[row['verdict']]} | "
                f"{cell(reason)} |"
            )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT, dict(counts))


if __name__ == "__main__":
    main()

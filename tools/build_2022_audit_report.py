"""Write the per-task 2022 to 2027 suitability review from the database."""
from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/phyege.sqlite3"
OUTPUT = ROOT / "AUDIT_2022_2027.md"
LABELS = {"yes": "Да", "partial": "Частично", "no": "Нет"}


def cell(value: str | None) -> str:
    return (value or "—").replace("|", r"\|").replace("\n", " ").strip()


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT v.variant_number,p.problem_number,p.answer,p.extraction_status,
               r.target_problem_number,r.verdict,r.reason
        FROM variants v JOIN problems p ON p.variant_id=v.id
        JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027
        WHERE v.exam_year=2022
        ORDER BY CAST(v.variant_number AS INTEGER),p.problem_number
    """).fetchall()
    assert len(rows) == 120
    assert all(row["extraction_status"] == "needs_review" for row in rows)
    counts = Counter(row["verdict"] for row in rows)
    by_source = {(int(row["variant_number"]), row["problem_number"]): row for row in rows}
    lines = [
        "# Сверка вариантов Демидовой 2022 с ЕГЭ 2027",
        "",
        "Импортированы четыре авторских DOCX: по 30 заданий, из них 23 с кратким "
        "ответом и 7 с развёрнутым. Все 92 коротких ответа сверены с печатными "
        "ключами, в №22 отдельно разделены показание и погрешность. Итоги 28 "
        "развёрнутых задач перенесены из авторских решений. Полные решения "
        "переписаны в TeX и проверены по страницам исходного PDF. Критерии "
        "хранятся отдельно, по строкам авторской таблицы.",
        "",
        f"Пригодность к спецификации 2027: **{counts['yes']} полностью**, "
        f"**{counts['partial']} частично**, **{counts['no']} не подходят**. "
        "Вердикт для каждой задачи учитывает тему, формат ответа и баллы. "
        "В №26 варианта 4 авторская шкала даёт 3 балла, тогда как в других "
        "вариантах 2022 года — 2; это учтено отдельно.",
        "",
        "В цельных вариантах сохраняются исходные номера 1–30. В каталоге задач "
        "2027 года показываются только оценки «Да» и «Частично» под целевыми "
        "номерами 1–26. Для «Нет» указан проверенный ближайший кандидат, "
        "а не допустимая позиция.",
        "",
        "Все 120 записей пока имеют статус `needs_review`: полная визуальная "
        "сверка каждого условия, объекта MathType, рисунка и критерия не "
        "завершена. Оценка пригодности не является отметкой о завершённой "
        "сверке расшифровки. Основа перехода номеров — "
        "[таблица соответствия](YEAR_POSITION_MAPPING.md); документы 2027 "
        "утверждены ФИПИ 13.11.2026.",
        "",
        "Удалённый LLM-аудит не запускался по ранее высказанному пожеланию "
        "пользователя. Локальные строгие проверки формул, TeX, степеней, "
        "таблиц и связей изображений проведены отдельно.",
        "",
        "## Дополнительная сверка с отрисованными источниками",
        "",
        "- Текст всех 120 условий сопоставлен с независимо созданными PDF из четырёх "
        "исходных DOCX (`tools/audit_2022_pages.py`): у всех задач совпало не менее "
        "90% словесных триграмм. Автоматический контроль не заменяет визуальную "
        "проверку математической записи.",
        "- Порядок пяти графиков в задании 2 каждого варианта и три фотографии "
        "в задании 24 варианта 2 сверены с исходными страницами. У задания 15 "
        "варианта 3 удалён чужой график: он относится к заданию 16.",
        "- Последовательности баллов во всех 28 авторских таблицах критериев "
        "независимо переписаны и закреплены в `tools/check_2022_import.py`.",
        "- Собраны 16 PDF: условия, ответы, решения и критерии каждого варианта. "
        "Шесть автоматически собранных вариантов проверены на неповторение задач.",
        "",
        "Статус `needs_review` остаётся у всех 120 задач до завершения "
        "постраничной визуальной проверки каждой формулы, таблицы и фигуры.",
        "",
        "## Сводная таблица соответствия",
        "",
        "| № 2022 | Вариант 1 | Вариант 2 | Вариант 3 | Вариант 4 |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for number in range(1, 31):
        values = []
        for variant in range(1, 5):
            row = by_source[(variant, number)]
            values.append(f"{row['target_problem_number']} · {LABELS[row['verdict']]}")
        lines.append(f"| {number} | " + " | ".join(values) + " |")
    for variant in range(1, 5):
        lines.extend([
            "",
            f"## Вариант {variant}",
            "",
            "| № 2022 | Авторский ответ | Кандидат № 2027 | Вердикт | Причина ограничения |",
            "| ---: | --- | ---: | --- | --- |",
        ])
        for number in range(1, 31):
            row = by_source[(variant, number)]
            reason = row["reason"] if row["verdict"] != "yes" else "—"
            lines.append(
                f"| {number} | {cell(row['answer'])} | "
                f"{row['target_problem_number']} | {LABELS[row['verdict']]} | "
                f"{cell(reason)} |"
            )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT, dict(counts))


if __name__ == "__main__":
    main()

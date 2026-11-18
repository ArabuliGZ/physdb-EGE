"""AI-edited EGE-style scoring rubrics for matched open exam variants."""
from __future__ import annotations

import sqlite3

from complete_botay_from_solutions import DB
from curated_botay_2024_main1 import rubric
from curated_botay_2024_main23 import criterion_four
from site_edit_guard import edited_fields


# Each long task was matched with a published Решу ЕГЭ card in the same order.
LAWS = {
    (2024, "БОТАЙ-ОТКРЫТ-1"): {
        21: ("знаки теплоты на обоих участках", "первый закон термодинамики, уравнение состояния и связь внутренней энергии с температурой"),
        22: (None, "кинематика движения в поле тяжести и условие нулевой вертикальной скорости в верхней точке"),
        23: (None, "ЭДС движения проводника, закон Ома и энергия магнитного поля катушки"),
        24: (None, "равновесие поршня и уравнение состояния идеального газа"),
        25: (None, "изохорный закон, тепловой баланс и КПД нагревателя"),
        26: (None, "второй закон Ньютона для бруска и клина, закон трения скольжения"),
    },
    (2025, "БОТАЙ-ОТКРЫТ-1"): {
        21: ("рисунок всех сил и направление ускорения шарика", "второй закон Ньютона, центростремительное и касательное ускорение маятника"),
        22: (None, "уравнение состояния насыщенного водяного пара и отношение испарившейся массы к исходной"),
        23: (None, "формула тонкой линзы для мнимого изображения и линейное увеличение"),
        24: (None, "первый закон термодинамики, работа газа по диаграмме и КПД цикла"),
        25: (None, "закон электромагнитной индукции и связь прошедшего заряда с изменением магнитного потока"),
        26: (None, "условия равновесия бруска и второго тела, моменты сил относительно края стола"),
    },
    (2026, "ОТКРЫТ-1"): {
        21: ("график цикла в координатах \\(p\\)–\\(V\\) и сравнение двух работ", "уравнение состояния, характер изохорного, изотермического и изобарного процессов"),
        22: (None, "закон сохранения импульса для дроби и саней с охотником"),
        23: (None, "условие равновесия проводника и сила Ампера"),
        24: (None, "сила Архимеда, условие равновесия зонда и уравнение состояния газа"),
        25: (None, "формула тонкой линзы и геометрия предельных лучей через оправу"),
        26: (None, "второй закон Ньютона для трёх тел, закон Гука и сила трения"),
    },
}


def qualitative_rubric(result: str, laws: str) -> str:
    return (
        "Краткая редакция ИИ по опубликованным критериям; требуется проверка.\n"
        f"\\(3\\) балла: Получены {result}; объяснение полностью опирается на {laws}.\n"
        "\\(2\\) балла: Ответ верен, но в объяснении пропущен один необходимый закон или есть один логический недочёт.\n"
        "\\(1\\) балл: Верна существенная часть результата либо приведены необходимые законы, но объяснение не доведено до ответа.\n"
        "\\(0\\) баллов: Результат и объяснение не соответствуют условиям получения балла.\n"
        "\\(3\\) балла: Максимальный балл."
    )


def run(con: sqlite3.Connection, *, write: bool = False, year_filter: int | None = None) -> int:
    count = 0
    for (year, variant), entries in LAWS.items():
        if year_filter is not None and year != year_filter:
            continue
        rows = list(con.execute("""SELECT p.id,p.problem_number,p.max_points,p.criteria,p.review_notes
            FROM problems p JOIN variants v ON p.variant_id=v.id
            WHERE v.exam_year=? AND v.variant_number=? AND p.alternative_number=1
            AND p.problem_number BETWEEN 21 AND 26 ORDER BY p.problem_number""",
            (year, variant)))
        if [r[1] for r in rows] != list(range(21, 27)):
            raise ValueError(f"Unexpected long task set in {year}-{variant}")
        for pid, number, points, current, notes in rows:
            if "criteria" in edited_fields(pid):
                continue
            result, laws = entries[number]
            value = (qualitative_rubric(result, laws) if result else
                     criterion_four(laws) if points == 4 else rubric(points, laws))
            owned = "criteria: редакция ИИ по опубликованным критериям" in (notes or "")
            if current and not owned:
                continue
            count += 1
            if write:
                if owned:
                    con.execute("UPDATE problems SET criteria=? WHERE id=?", (value, pid))
                else:
                    source_id = ({2024: 38203, 2025: 42649, 2026: 49641}[year]
                                 + number - 21)
                    url = f"https://phys-ege.sdamgia.ru/problem?id={source_id}"
                    note = f" criteria: редакция ИИ по опубликованным критериям {url}; требуется проверка."
                    con.execute("""UPDATE problems SET criteria=?,
                        review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                        WHERE id=? AND (criteria IS NULL OR trim(criteria)='')""",
                        (value, note, pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Completed open-variant rubrics: {run(connection, write=True)}")

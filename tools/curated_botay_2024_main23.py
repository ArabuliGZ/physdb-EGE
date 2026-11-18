"""Published answers and AI-edited EGE rubrics for 2024 main variants 2–3."""
from __future__ import annotations

import sqlite3

from complete_botay_from_solutions import ARCHIVE, DB, ROOT
from curated_botay_2024_main1 import rubric
from site_edit_guard import edited_fields


def qualitative_rubric(laws: str) -> str:
    return (
        "Краткая редакция ИИ по опубликованным критериям; требуется проверка.\n"
        f"\\(3\\) балла: Верно указаны итоговое движение и его направление; объяснение полностью опирается на {laws}.\n"
        "\\(2\\) балла: Итоговый вывод верен, но в объяснении пропущен один необходимый закон или есть один логический недочёт.\n"
        "\\(1\\) балл: Приведён существенный верный вывод или необходимые законы, но объяснение не доведено до результата.\n"
        "\\(0\\) баллов: Решение не соответствует условиям получения балла."
    )


# Answer, source PDF pages, laws expected in the published scoring rubric.
DATA = {
    "БОТАЙ-ОСНОВ-2": {
        21: ("Рамка повернётся по часовой стрелке; после затухания колебаний "
             "встанет перпендикулярно оси магнита, контакт «+» окажется внизу.",
             "14–15", "направление силы Ампера и момент сил", True),
        22: ("Сила натяжения уменьшится на \\(\\rho Vg\\): \\(\\Delta T=-\\rho Vg\\).",
             "16–17", "второй закон Ньютона и сила Архимеда", False),
        23: ("\\(\\approx15\\,\\text{мин}\\)", "17–18",
             "тепловой баланс, нагревание, парообразование и мощность", False),
        24: ("\\(\\approx3{,}89\\,\\text{кДж}\\)", "19–20",
             "первый закон термодинамики, КПД и внутренняя энергия одноатомного газа", False),
        25: ("\\(R_1=20\\,\\text{Ом},\\quad R_2=10\\,\\text{Ом}\\)", "21–22",
             "закон Ома, мощность тока и проводимость ветвей с диодом", False),
        26: ("\\(\\tau=\\dfrac{v_0\\sin\\alpha}{2g}(1+\\sqrt3)\\)", "23–25",
             "кинематика свободного падения и закон сохранения импульса при столкновении", False),
    },
    "БОТАЙ-ОСНОВ-3": {
        21: ("Поршень начнёт двигаться влево; затем будет совершать свободные "
             "колебания, постепенно затухающие из-за сопротивления воздуха.",
             "15–16", "условие равновесия поршня, изменение давления и закон Гука", True),
        22: ("\\(700\\,\\text{кг}/\\text{м}^3\\)", "17–18",
             "условие плавания тела и сила Архимеда в двух жидкостях", False),
        23: ("\\(120\\,\\text{мкФ}\\)", "19–20",
             "ЭДС движения проводника и энергия заряженного конденсатора", False),
        24: ("\\(40\\%\\)", "20–22",
             "закон сохранения массы водяного пара и определение относительной влажности", False),
        25: ("\\(300\\,\\text{В}\\)", "23–24",
             "закон сохранения энергии при перераспределении зарядов конденсаторов", False),
        26: ("\\(0{,}13\\,\\text{м}\\)", "25–27",
             "второй закон Ньютона, закон Гука и сила трения скольжения", False),
    },
}


def criterion_four(laws: str) -> str:
    return (
        "Краткая редакция ИИ по опубликованным критериям; требуется проверка.\n"
        "Критерий 1. Обоснование\n"
        "\\(1\\) балл: Верно обоснованы выбор ИСО, применимость используемых моделей и законов.\n"
        "\\(0\\) баллов: Обоснование отсутствует или содержит существенную ошибку.\n"
        "Критерий 2. Решение\n"
        f"\\(3\\) балла: Записаны {laws}; обозначения пояснены; преобразования и вычисления доведены до правильного ответа с единицей измерения.\n"
        "\\(2\\) балла: Законы и ход решения верны, но допущен один недочёт в обозначениях, преобразовании либо ответе.\n"
        "\\(1\\) балл: Записаны основные законы без завершённого решения либо пропущено одно исходное соотношение при верных дальнейших шагах.\n"
        "\\(0\\) баллов: Решение не соответствует условиям получения более высокого балла.\n"
        "\\(4\\) балла: Максимальный балл."
    )


def run(con: sqlite3.Connection, *, write: bool = False) -> dict[str, int]:
    counts = {"answer": 0, "criteria": 0}
    for variant, entries in DATA.items():
        pdf_number = 1 if variant.endswith("2") else 2
        source = ARCHIVE / f"variant_{pdf_number}_fizika-ege-2024-0205_solutions.pdf"
        if not source.is_file():
            raise FileNotFoundError(source)
        rows = list(con.execute("""SELECT p.id,p.problem_number,p.answer,p.criteria,p.max_points,
            p.review_notes FROM problems p JOIN variants v ON v.id=p.variant_id
            WHERE v.exam_year=2024 AND v.variant_number=?
            AND p.problem_number BETWEEN 21 AND 26 AND p.alternative_number=1
            ORDER BY p.problem_number""", (variant,)))
        if [r[1] for r in rows] != list(range(21, 27)):
            raise ValueError(f"Unexpected task set in {variant}")
        for pid, number, answer, criteria, points, notes in rows:
            manual_fields = edited_fields(pid)
            found, pages, laws, qualitative = entries[number]
            fields = {
                "answer": found,
                "criteria": criterion_four(laws) if points == 4 else
                qualitative_rubric(laws) if qualitative else rubric(points, laws),
            }
            for field, current in (("answer", answer), ("criteria", criteria)):
                if field in manual_fields:
                    continue
                owned = f"{field}: редакция ИИ по " in (notes or "")
                if current and not owned:
                    continue
                counts[field] += 1
                if write:
                    if owned:
                        con.execute(f"UPDATE problems SET {field}=? WHERE id=?", (fields[field], pid))
                    else:
                        origin = "редакция ИИ по" if field == "criteria" else "из"
                        note = (f" {field}: {origin} {source.relative_to(ROOT).as_posix()}, "
                                f"PDF с. {pages}; требуется проверка.")
                        con.execute(f"""UPDATE problems SET {field}=?,
                            review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                            WHERE id=? AND ({field} IS NULL OR trim({field})='')""",
                            (fields[field], note, pid))
    return counts


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(run(connection, write=True))

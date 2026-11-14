"""Assess the imported 2024–2026 tasks against the FIPI 2027 approved plan.

The assessment describes content/answer format; transcription QA remains in
problems.extraction_status. Re-run only after checking the current FIPI plan.
"""
from __future__ import annotations

import re
import sqlite3

from import_examples import DB, FORMATS, POINTS, ROOT, assess


TOPIC_NAME = {
    "mechanics": "механика", "molecular": "молекулярная физика и термодинамика",
    "electrodynamics": "электродинамика", "quantum": "квантовая физика",
    "cross_topic": "межпредметные закономерности и эксперимент",
}
FORMAT_NAME = {
    "number": "числовой краткий ответ", "number_pair": "два измеренных числа",
    "multiple_choice": "множественный выбор", "matching": "соответствие",
    "qualitative": "качественное объяснение", "worked_solution": "расчётное решение",
}

# Individual source judgments for line 22. For the others, topic and score
# were read from each source statement and the numbered key/rubric.
LINE_22 = {
    (2024, "1-1"): ("yes", "Прикладной расчёт плавания цилиндра в воде; механика, численный ответ и 2 балла."),
    (2024, "1-2"): ("partial", "Абстрактное равноускоренное движение: механика и 2 балла совпадают, практический сюжет отсутствует."),
    (2024, "1-3"): ("partial", "Стержень и шар в идеализированном ящике: механика и 2 балла совпадают, практический сюжет отсутствует."),
    (2024, "1-4"): ("partial", "Идеализированные грузы и нить: механика и 2 балла совпадают, практический сюжет отсутствует."),
    (2024, "2-1"): ("no", "Вопрос об изменении силы натяжения качественный; позиция 22 спецификации 2027 требует расчётный ответ."),
    (2024, "2-2"): ("yes", "Расчёт плотности шарика на границе жидкостей: прикладная механика и 2 балла."),
    (2024, "2-3"): ("yes", "Определение энергии автомобиля по графику движения: прикладная механика и 2 балла."),
    (2024, "2-4"): ("yes", "Расчёт времени торможения поезда: прикладная механика и 2 балла."),
    (2025, "1-1"): ("partial", "Идеализированные грузы и нить: механика и 2 балла совпадают, практический сюжет отсутствует."),
    (2025, "1-2"): ("no", "Нагревание гелия — молекулярная физика, тогда как позиция 22 спецификации 2027 отведена механике."),
    (2025, "1-3"): ("yes", "Мальчик запрыгивает на тележку: прикладная задача на импульс, численный ответ и 2 балла."),
    (2025, "2-1"): ("partial", "Идеализированные грузы и нить: механика и 2 балла совпадают, практический сюжет отсутствует."),
    (2025, "2-2"): ("no", "Нагревание гелия — молекулярная физика, тогда как позиция 22 спецификации 2027 отведена механике."),
    (2025, "2-3"): ("yes", "Мальчик запрыгивает на тележку: прикладная задача на импульс, численный ответ и 2 балла."),
    (2026, "2"): ("yes", "Плавание шара в воде и керосине: прикладная механика, численный ответ и 2 балла."),
    (2026, "3"): ("partial", "Идеализированная система грузов и блока: механика и 2 балла совпадают, практический сюжет отсутствует."),
    (2026, "4"): ("partial", "Идеализированные колебания тележки и пружины: механика и 2 балла совпадают, практический сюжет отсутствует."),
}


def assess_row(con, row) -> None:
    n = row["problem_number"]
    year = row["exam_year"]
    variant = row["variant_number"]
    topic = row["topic"]
    answer_format = row["answer_format"]
    assert row["max_points"] == POINTS[n]
    if n <= 20 or n >= 24:
        # These source items were checked by their statements and keys/rubrics
        # against the section and response type in the 2027 generalized plan.
        assert answer_format == FORMATS[n]
        if n == 26:
            assert "обосн" in row["statement"].lower(), (year, variant, n)
        excerpt = re.sub(r"\s+", " ", row["statement"])
        excerpt = re.sub(r"\\\([^)]*\\\)", "…", excerpt)
        excerpt = re.sub(r"\[\[formula:[0-9a-f]{64}:\d+:\d+\]\]", "…", excerpt)[:95].rstrip(" ,.;")
        reason = (f"По условию и ключу: {TOPIC_NAME[topic]}, {FORMAT_NAME[answer_format]}, "
                  f"{row['max_points']} балл(а); соответствует позиции {n} спецификации 2027. "
                  f"Сюжет: {excerpt}.")
        assess(con, row["id"], n, 1, 1, "yes", reason)
        return
    if n == 21:
        yes = topic == "electrodynamics" and answer_format == "qualitative"
        reason = ("Качественная задача по электродинамике на 3 балла соответствует позиции 21 спецификации 2027."
                  if yes else f"Качественная задача на 3 балла: {TOPIC_NAME[topic]}; позиция 21 спецификации 2027 допускает только электродинамику.")
        assess(con, row["id"], n, int(topic == "electrodynamics"),
               int(answer_format == "qualitative"), "yes" if yes else "no", reason)
        return
    if n == 22:
        verdict, reason = LINE_22[(year, variant)]
        topic_ok = topic == "mechanics"
        format_ok = answer_format == "worked_solution" and (year, variant) != (2024, "2-1")
        assert verdict != "yes" or (topic_ok and format_ok)
        assess(con, row["id"], n, int(topic_ok), int(format_ok), verdict, reason)
        if (year, variant) in {(2025, "1-2"), (2025, "2-2")}:
            assess(con, row["id"], 23, 1, 1, "yes",
                   "Изохорное нагревание гелия: молекулярная физика, расчётное решение и 2 балла соответствуют позиции 23 спецификации 2027.")
        return
    if n == 23:
        yes = topic == "molecular" and answer_format == "worked_solution"
        reason = ("Расчётная задача по молекулярной физике на 2 балла соответствует позиции 23 спецификации 2027."
                  if yes else f"Расчётная задача на 2 балла: {TOPIC_NAME[topic]}; позиция 23 спецификации 2027 отведена молекулярной физике.")
        assess(con, row["id"], n, int(topic == "molecular"),
               int(answer_format == "worked_solution"), "yes" if yes else "no", reason)


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    selected = con.execute("""SELECT p.*,v.exam_year,v.variant_number FROM problems p
        JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year IN (2024,2025) OR (v.exam_year=2026 AND v.variant_number IN ('2','3','4'))
        ORDER BY v.exam_year,v.variant_number,p.problem_number""").fetchall()
    assert len(selected) == 442, len(selected)
    with con:
        for row in selected:
            assess_row(con, row)
    own = con.execute("""SELECT count(*) FROM problems p JOIN relevance r ON r.problem_id=p.id
        JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year>=2024 AND r.exam_year=2027
        AND r.target_problem_number=p.problem_number""").fetchone()[0]
    assert own == 496, own
    print("assessed", len(selected), "new tasks against FIPI approved 2027")
    counts = con.execute("""SELECT verdict,count(*) FROM relevance
        WHERE exam_year=2027 GROUP BY verdict""").fetchall()
    print("own-position assessments", own, "all verdicts", [tuple(row) for row in counts])
    con.close()


if __name__ == "__main__":
    main()

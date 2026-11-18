"""Source-backed repair of the contradictory 2026 Far East task 21.

The Botay PDF shows a V–E_k chart with points 1, 2, 3, but its caption asks
for an unrelated p–T four-state cycle. The original solved card is 50855.
"""
from __future__ import annotations

import hashlib
import sqlite3

from complete_botay_from_solutions import DB
from site_edit_guard import edited_fields

OLD_HASH = "79d7ba462eead79b"
SOURCE = "https://phys-ege.sdamgia.ru/problem?id=50855"
STATEMENT = (
    "На графике представлена зависимость объёма постоянного количества одноатомного идеального газа "
    "от средней кинетической энергии теплового движения его молекул. Опишите, как изменяются "
    "давление и абсолютная температура газа в процессах \\(1\\)–\\(2\\) и \\(2\\)–\\(3\\). "
    "Укажите закономерности, которыми вы пользовались при объяснении."
)
ANSWER = (
    "В процессе \\(1\\)–\\(2\\) температура не изменяется, давление уменьшается; "
    "в процессе \\(2\\)–\\(3\\) температура уменьшается, давление остаётся постоянным."
)
CRITERIA = (
    "Краткая редакция ИИ по опубликованным критериям; требуется проверка.\n"
    "\\(3\\) балла: Верно указаны изменения давления и температуры на обоих участках; "
    "объяснение опирается на связь средней кинетической энергии с температурой и уравнение состояния.\n"
    "\\(2\\) балла: Все изменения указаны верно, но в объяснении есть один недочёт или не записана одна закономерность.\n"
    "\\(1\\) балл: Верно описан один участок либо приведены необходимые закономерности без полного ответа.\n"
    "\\(0\\) баллов: Ответ не соответствует условиям получения балла."
)


def run(con: sqlite3.Connection, *, write: bool = False) -> int:
    row = con.execute("""SELECT p.id,p.statement,p.answer,p.criteria,p.review_notes
        FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2026 AND v.variant_number='ОСНОВ-ДВ-1'
        AND p.problem_number=21 AND p.alternative_number=1""").fetchone()
    if not row:
        raise ValueError("Missing 2026 Far East task 21")
    pid, statement, answer, criteria, notes = row
    current_hash = hashlib.sha256(statement.encode()).hexdigest()[:16]
    edited = edited_fields(pid)
    count = 0
    if current_hash == OLD_HASH and "statement" not in edited:
        count += 1
        if write:
            con.execute("""UPDATE problems SET statement=?,
                review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                WHERE id=?""", (STATEMENT, f" statement: исправлено по рисунку PDF с. 8 и {SOURCE}; ", pid))
    elif statement != STATEMENT:
        print("Skip 2026 Far East №21: editor changed condition")
        return count
    if not answer and "answer" not in edited:
        count += 1
        if write:
            con.execute("UPDATE problems SET answer=? WHERE id=?", (ANSWER, pid))
    owned = "criteria: редакция ИИ по опубликованным критериям" in (notes or "")
    if "criteria" not in edited and (not criteria or owned):
        if criteria != CRITERIA:
            count += 1
            if write:
                if owned:
                    con.execute("UPDATE problems SET criteria=? WHERE id=?", (CRITERIA, pid))
                else:
                    con.execute("""UPDATE problems SET criteria=?,
                        review_notes=COALESCE(review_notes,'') || ?,extraction_status='needs_review'
                        WHERE id=?""", (CRITERIA, f" criteria: редакция ИИ по опубликованным критериям {SOURCE}; требуется проверка.", pid))
    return count


if __name__ == "__main__":
    with sqlite3.connect(DB) as connection:
        print(f"Repaired 2026 Far East task 21 fields: {run(connection, write=True)}")

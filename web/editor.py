"""Durable local text edits for problem statements and solutions."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .answer_units import format_answer_unit_tex
else:
    from answer_units import format_answer_unit_tex


EDITABLE_FIELDS = {"statement", "answer", "solution"}
MAX_TEXT_LENGTH = 200_000
ANSWER_BLANK = re.compile(r"_{3,}|…{3,}")


def read_edit_log(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "problems": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("problems"), dict):
        raise ValueError("Неверный формат журнала правок")
    return data


def write_edit_log(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_answer_field(value: str, pair: bool = False) -> tuple[str, str]:
    """Split ``Ответ: prefix _____ unit`` into its stored affixes."""
    if not isinstance(value, str):
        raise ValueError("Поле ответа должно быть строкой")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "\n" in value:
        raise ValueError("Печатное поле ответа должно занимать одну строку")
    payload = re.sub(r"^\s*Ответ\s*:?\s*", "", value, flags=re.IGNORECASE)
    blanks = list(ANSWER_BLANK.finditer(payload))
    if not blanks:
        raise ValueError("Оставьте в строке место для ответа: _____")
    if pair and (len(blanks) < 2 or not re.search(r"±|\\pm|\+-", payload)):
        raise ValueError("Для парного ответа нужны два поля и знак ±")
    prefix = payload[:blanks[0].start()].strip()
    unit = format_answer_unit_tex(payload[blanks[-1].end():].strip().rstrip(".;"))
    if len(prefix) > 500 or len(unit) > 500:
        raise ValueError("Подпись поля ответа слишком длинная")
    return prefix, unit


def save_text_edit(db: Path, log_path: Path, problem_id: str,
                   field: str, value: str) -> dict:
    if field not in EDITABLE_FIELDS | {"answer_field"}:
        raise ValueError("Можно редактировать только условие, ответ, поле ответа или решение")
    if not isinstance(value, str):
        raise ValueError("Текст правки должен быть строкой")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        raise ValueError("Пустой текст сохранить нельзя")
    if len(value) > MAX_TEXT_LENGTH:
        raise ValueError("Текст слишком длинный")

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("""SELECT p.id,p.variant_id,p.problem_number,p.alternative_number,
            p.statement,p.answer,p.solution,p.answer_prefix,p.answer_unit,p.answer_format,
            v.exam_year,v.variant_number
            FROM problems p JOIN variants v ON v.id=p.variant_id WHERE p.id=?""",
                          (problem_id,)).fetchone()
        if row is None:
            raise LookupError("Задача не найдена")
        if field == "answer_field":
            prefix, unit = parse_answer_field(value, row["answer_format"] == "number_pair")
            changed_fields = {"answer_prefix": prefix, "answer_unit": unit}
            if all((row[name] or "").strip() == content for name, content in changed_fields.items()):
                return {"changed": False, "problem_id": problem_id, "field": field}
        else:
            changed_fields = {field: value}
            if (row[field] or "").strip() == value:
                return {"changed": False, "problem_id": problem_id, "field": field}

        data = read_edit_log(log_path)
        problem = data["problems"].setdefault(problem_id, {
            "variant_id": row["variant_id"],
            "exam_year": row["exam_year"],
            "variant_number": row["variant_number"],
            "problem_number": row["problem_number"],
            "alternative_number": row["alternative_number"],
            "fields": {},
        })
        problem["fields"].update(changed_fields)
        problem["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        write_edit_log(log_path, data)

        for name, content in changed_fields.items():
            con.execute(f"UPDATE problems SET {name}=? WHERE id=?", (content, problem_id))
        con.commit()
        return {"changed": True, "problem_id": problem_id, "field": field}
    finally:
        con.close()

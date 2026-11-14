"""Check website and TeX short-answer field metadata for every imported task."""
from __future__ import annotations

import collections
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from variant_tex import answer_field  # noqa: E402


def main() -> None:
    con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT p.*,v.exam_year,v.variant_number
        FROM problems p JOIN variants v ON v.id=p.variant_id
        ORDER BY v.exam_year DESC,v.variant_number,p.problem_number,p.alternative_number""").fetchall()
    counts: collections.Counter[str] = collections.Counter()
    units: collections.Counter[str] = collections.Counter()
    for row in rows:
        problem = dict(row)
        field = answer_field(problem)
        if problem["answer_format"] in ("qualitative", "worked_solution"):
            if field is not None:
                raise ValueError(f"Unexpected short-answer field for {problem['id']}")
            counts["detailed"] += 1
            continue
        if field is None:
            raise ValueError(f"Missing short-answer field for {problem['id']}")
        kind = field.get("kind")
        if kind not in ("line", "pair", "table"):
            raise ValueError(f"Unknown field kind {kind!r} for {problem['id']}")
        if kind == "table":
            labels = field.get("labels")
            if not isinstance(labels, list) or len(labels) < 2 or any(not label.strip() for label in labels):
                raise ValueError(f"Invalid response table for {problem['id']}")
        if problem["answer_format"] == "number_pair" and kind != "pair":
            raise ValueError(f"Measurement field is not a pair for {problem['id']}")
        if problem["answer_format"] == "matching" and kind != "table":
            raise ValueError(f"Matching field is not a table for {problem['id']}")
        unit = field.get("unit", "")
        if len(unit) > 18 or " " in unit:
            raise ValueError(f"Suspicious unit {unit!r} for {problem['id']}")
        counts[kind] += 1
        if unit:
            units[unit] += 1

    demo = {row["problem_number"]: answer_field(dict(row)) for row in rows
            if row["exam_year"] == 2027 and row["alternative_number"] == 1}
    expected_units = {1: "м/с²", 2: "м/с²", 3: "м", 4: "см", 8: "кг",
                      11: "В", 13: "°", 16: "мкмоль", 19: "В"}
    for number, expected in expected_units.items():
        if not demo.get(number) or demo[number].get("unit") != expected:
            raise ValueError(f"Demo 2027 task {number}: expected unit {expected!r}, got {demo.get(number)}")

    print("Checked answer fields: " + ", ".join(
        f"{kind} — {count}" for kind, count in sorted(counts.items())))
    print("Explicit units: " + ", ".join(
        f"{unit} — {count}" for unit, count in units.most_common()))


if __name__ == "__main__":
    main()

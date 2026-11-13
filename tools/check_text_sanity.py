"""Catch notation damaged by flattening Word superscripts and subscripts.

This is a gate for new imports. Suspects require source inspection; the checker
does not guess whether a hyphen means subtraction or a negative exponent.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from tex_format import INDEXED_SYMBOL, MATH


DB = Path(__file__).resolve().parents[1] / "data" / "phyege.sqlite3"
FLAT_POWER = re.compile(r"\\\((?:\d+(?:\{,\}\d+)?){0,2}10[-−–]\d{1,2}(?:\\,\\text\{[^}]+\})?\\\)")
SCI_UNIT = re.compile(r"\\\(10[-−–]\d{1,2}\\,\\text\{")
PLACEHOLDER = re.compile(r"\[\[formula:|\[формула в исходном", re.I)


def findings(text: str) -> list[tuple[str, str]]:
    issues = [("flattened_power", m.group()) for m in FLAT_POWER.finditer(text)]
    issues += [("power_with_unit", m.group()) for m in SCI_UNIT.finditer(text)]
    issues += [("placeholder", m.group()) for m in PLACEHOLDER.finditer(text)]
    pieces = MATH.split(text)
    issues += [("bare_index", m.group()) for i, piece in enumerate(pieces) if i % 2 == 0
               for m in INDEXED_SYMBOL.finditer(piece)]
    return issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    con = sqlite3.connect(DB)
    count = 0
    for year, variant, number, field, value in (
        (year, variant, number, field, value)
        for year, variant, number, statement, solution, criteria in con.execute(
            """SELECT v.exam_year,v.variant_number,p.problem_number,p.statement,p.solution,p.criteria
            FROM problems p JOIN variants v ON v.id=p.variant_id""")
        for field, value in (("statement", statement), ("solution", solution), ("criteria", criteria))
        if value
    ):
        for kind, fragment in findings(value):
            print(f"{year}-{variant} task {number} {field}: {kind}: {fragment[:100]}")
            count += 1
    print(f"Suspicious notation: {count}")
    if count and args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

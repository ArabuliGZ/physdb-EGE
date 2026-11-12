"""Report image equations left in solutions; --strict is the completion gate."""
from __future__ import annotations

import argparse
import collections
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\[\[formula:([0-9a-f]{64}):\d+:\d+\]\]")
PLACEHOLDERS = ("[формула в исходном DOCX", "[[SRCFORMULA")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail if any solution still contains image equations")
    args = parser.parse_args()

    con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
    rows = con.execute("""SELECT v.exam_year, v.variant_number, p.problem_number, p.solution
        FROM problems AS p JOIN variants AS v ON v.id = p.variant_id
        WHERE p.solution IS NOT NULL ORDER BY v.exam_year, v.variant_number, p.problem_number""")
    by_variant: collections.Counter[str] = collections.Counter()
    by_task: list[tuple[str, int, int]] = []
    hashes: set[str] = set()
    invalid: list[tuple[str, int]] = []
    for year, variant, number, solution in rows:
        label = f"{year}-{variant}"
        found = TOKEN.findall(solution)
        if found:
            by_variant[label] += len(found)
            by_task.append((label, number, len(found)))
            hashes.update(found)
        if any(marker in solution for marker in PLACEHOLDERS):
            invalid.append((label, number))

    print(f"Осталось изображений формул: {sum(by_variant.values())}; "
          f"уникальных: {len(hashes)}; задач: {len(by_task)}")
    for label, count in sorted(by_variant.items()):
        tasks = ", ".join(f"№{number}: {amount}" for variant, number, amount in by_task
                          if variant == label)
        print(f"{label}: {count} ({tasks})")
    if invalid:
        print(f"Неразобранные маркеры: {invalid}")
    return 1 if invalid or (args.strict and by_task) else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify stored auto variants are complete, suitable, and globally disjoint."""
from __future__ import annotations

import sqlite3
from collections import defaultdict

from build_automatic_variants import DB, load_plan, load_tasks, task_families


def main() -> None:
    plan = load_plan()
    year = plan["target_exam_year"]
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    tasks = load_tasks(con, year)
    by_id = {task["id"]: task for task in tasks}
    families = task_families(con, tasks)
    available: dict[int, set[str]] = defaultdict(set)
    for task in tasks:
        if task["verdict"] == "yes":
            available[task["problem_number"]].add(families[task["id"]])
    maximum = min(len(available[number]) for number in range(1, 27))
    variants = con.execute("""SELECT a.id,a.title,v.exam_year,v.variant_number
        FROM automatic_variants a JOIN variants v ON v.id=a.base_variant_id
        WHERE a.target_exam_year=? ORDER BY a.title""", (year,)).fetchall()
    if len(variants) != len(plan["variants"]) or len(variants) > maximum:
        raise ValueError(f"Stored {len(variants)} variants, plan has {len(plan['variants'])}, maximum is {maximum}")
    seen: dict[str, str] = {}
    for variant in variants:
        rows = con.execute("""SELECT problem_number,problem_id
            FROM automatic_variant_problems WHERE automatic_variant_id=?
            ORDER BY problem_number""", (variant["id"],)).fetchall()
        if [row["problem_number"] for row in rows] != list(range(1, 27)):
            raise ValueError(f"Incomplete variant: {variant['title']}")
        base = f"{variant['exam_year']}-{variant['variant_number']}"
        original = {task["problem_number"]: task for task in tasks if task["label"] == base}
        changed = 0
        for row in rows:
            task = by_id[row["problem_id"]]
            number = row["problem_number"]
            if task["problem_number"] != number or task["verdict"] != "yes":
                raise ValueError(f"Unsuitable task {number} in {variant['title']}")
            family = families[task["id"]]
            if family in seen:
                raise ValueError(f"Duplicate task {number}: {seen[family]} and {variant['title']}")
            seen[family] = variant["title"]
            changed += family != families[original[number]["id"]]
        if not changed:
            raise ValueError(f"{variant['title']} is a copy of its base")
        print(f"{variant['title']}: 26 unique suitable tasks, base {base}, {changed} changed")
    print(f"Checked {len(variants)} disjoint variants; available maximum: {maximum}")


if __name__ == "__main__":
    main()

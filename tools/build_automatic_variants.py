"""Build disjoint 2027 variants from a small, admin-editable plan.

Each source task (including a duplicate from another file) may occur in only
one automatic variant. A maximum-weight matching keeps as much of each base
variant as possible, then fills its gaps with suitable tasks from the pool.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
PLAN = ROOT / "tools" / "automatic_variant_plan.json"
RULE = "disjoint_2027_v2"
OLD_RULE = "fill_2027_gaps_v1"


def load_plan() -> dict:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    entries = plan["variants"]
    if not entries or len({entry["key"] for entry in entries}) != len(entries):
        raise ValueError("Plan needs distinct automatic variant keys")
    if len({entry["base"] for entry in entries}) != len(entries):
        raise ValueError("Each automatic variant needs a different base")
    return plan


def load_tasks(con: sqlite3.Connection, target_year: int) -> list[dict]:
    tasks = [dict(row) for row in con.execute("""SELECT p.id,p.variant_id,
        CASE WHEN v.exam_year=2023 THEN r.target_problem_number ELSE p.problem_number END AS problem_number,
        p.problem_number AS source_problem_number,
        p.statement,p.extraction_status,v.exam_year,v.variant_number,
        v.is_official_demo,r.verdict
        FROM problems p JOIN variants v ON v.id=p.variant_id
        LEFT JOIN relevance r ON r.problem_id=p.id AND r.exam_year=?
            AND (v.exam_year=2023 OR r.target_problem_number=p.problem_number)
        WHERE p.alternative_number=1 ORDER BY v.exam_year DESC,v.variant_number,p.problem_number""",
        (target_year,))]
    for task in tasks:
        task["label"] = f"{task['exam_year']}-{task['variant_number']}"
    return tasks


def task_families(con: sqlite3.Connection, tasks: list[dict]) -> dict[str, str]:
    """Union identical condition+figure pairs and known duplicate 2025 files."""
    figures: dict[str, list[str]] = defaultdict(list)
    for problem_id, sha in con.execute("""SELECT pa.problem_id,a.sha256 FROM problem_assets pa
        JOIN assets a ON a.id=pa.asset_id WHERE pa.role='statement_figure'
        ORDER BY a.sha256"""):
        figures[problem_id].append(sha)
    parent = {task["id"]: task["id"] for task in tasks}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    seen: dict[tuple, str] = {}
    for task in tasks:
        normalized = re.sub(r"\s+", " ", task["statement"]).strip()
        keys = [("condition", normalized, tuple(figures[task["id"]]))]
        if task["exam_year"] == 2025 and re.fullmatch(r"[12]-[123]", task["variant_number"]):
            # Series 2 repeats the corresponding series-1 task, even when
            # conversion from DOC introduces minor textual differences.
            keys.append(("2025-copy", task["variant_number"][-1], task["problem_number"]))
        for key in keys:
            if key in seen:
                union(task["id"], seen[key])
            else:
                seen[key] = task["id"]
    return {task["id"]: find(task["id"]) for task in tasks}


def choose_for_number(number: int, bases: list[dict], base_tasks: list[dict[int, dict]],
                      tasks: list[dict], families: dict[str, str]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for task in tasks:
        if task["problem_number"] == number and task["verdict"] == "yes":
            groups[families[task["id"]]].append(task)
    if len(groups) < len(bases):
        raise ValueError(f"Task {number}: only {len(groups)} different suitable tasks for {len(bases)} variants")

    def candidate(members: list[dict], slot: int) -> tuple[dict, int] | None:
        base = bases[slot]
        override = base["overrides"].get(str(number))
        if (base_tasks[slot][number]["verdict"] != "yes" and
                families[members[0]["id"]] == families[base_tasks[slot][number]["id"]]):
            return None  # A duplicate of an unsuitable base task is not a replacement.
        allowed = [task for task in members if override is None or task["label"] == override]
        if not allowed:
            return None
        def weight(task: dict) -> int:
            return (100000 if task["id"] == base_tasks[slot][number]["id"] else 0) + \
                (200 if task["exam_year"] == base["year"] else 0) + \
                (40 if not task["is_official_demo"] else 0) + \
                (10 if task["extraction_status"] == "verified" else 0) + \
                max(0, 5 - abs(task["exam_year"] - base["year"]))
        chosen = max(allowed, key=weight)
        return chosen, weight(chosen)

    # Dynamic programming over the six output slots solves the assignment
    # exactly for this task number. Each duplicate family is used at most once.
    empty: tuple[dict | None, ...] = (None,) * len(bases)
    states: dict[int, tuple[int, tuple[dict | None, ...]]] = {0: (0, empty)}
    for family in sorted(groups):
        next_states = states.copy()
        for mask, (score, picks) in states.items():
            for slot in range(len(bases)):
                if mask & (1 << slot):
                    continue
                selected = candidate(groups[family], slot)
                if selected is None:
                    continue
                task, weight = selected
                new_mask = mask | (1 << slot)
                new_score = score + weight
                if new_mask not in next_states or new_score > next_states[new_mask][0]:
                    updated = list(picks)
                    updated[slot] = task
                    next_states[new_mask] = (new_score, tuple(updated))
        states = next_states
    full = (1 << len(bases)) - 1
    if full not in states:
        raise ValueError(f"Task {number}: overrides prevent a disjoint assignment")
    return list(states[full][1])


def build(con: sqlite3.Connection, plan: dict) -> list[tuple[str, str, int]]:
    target_year = plan["target_exam_year"]
    tasks = load_tasks(con, target_year)
    families = task_families(con, tasks)
    by_label: dict[str, dict[int, dict]] = defaultdict(dict)
    for task in tasks:
        by_label[task["label"]][task["problem_number"]] = task
    bases = []
    base_tasks = []
    for entry in plan["variants"]:
        source = by_label.get(entry["base"])
        if not source or set(source) != set(range(1, 27)):
            raise ValueError(f"Base variant missing 26 tasks: {entry['base']}")
        bases.append({**entry, "year": source[1]["exam_year"], "variant_id": source[1]["variant_id"]})
        base_tasks.append(source)

    picks: list[dict[int, dict]] = [dict() for _ in bases]
    for number in range(1, 27):
        chosen = choose_for_number(number, bases, base_tasks, tasks, families)
        for slot, task in enumerate(chosen):
            picks[slot][number] = task

    used: dict[str, tuple[int, int]] = {}
    for slot, selected in enumerate(picks):
        for number, task in selected.items():
            family = families[task["id"]]
            if family in used:
                raise ValueError(f"Duplicate task family in {used[family]} and {(slot, number)}")
            used[family] = slot, number
            if task["verdict"] != "yes" or task["problem_number"] != number:
                raise ValueError(f"Unsuitable replacement in variant {slot + 1}, task {number}")
        if all(families[selected[n]["id"]] == families[base_tasks[slot][n]["id"]]
               for n in range(1, 27)):
            raise ValueError(f"Automatic variant {slot + 1} duplicates its base exactly")

    expected = {
        hashlib.sha256(f"automatic:{target_year}:{entry['key']}".encode()).hexdigest()[:24]: entry["variant_id"]
        for entry in bases
    }
    result = []
    with con:
        # Remove the previous overlapping generation and stale/changed plan
        # entries before inserting new ones (base_variant_id is unique).
        for row in list(con.execute("SELECT id,base_variant_id,generation_rule FROM automatic_variants")):
            if row["generation_rule"] == OLD_RULE or (
                row["generation_rule"] == RULE and (
                    row["id"] not in expected or
                    row["base_variant_id"] != expected[row["id"]]
                )
            ):
                con.execute("DELETE FROM automatic_variant_problems WHERE automatic_variant_id=?", (row["id"],))
                con.execute("DELETE FROM automatic_variants WHERE id=?", (row["id"],))
        for slot, entry in enumerate(bases):
            auto_id = hashlib.sha256(f"automatic:{target_year}:{entry['key']}".encode()).hexdigest()[:24]
            old = con.execute("SELECT title,target_exam_year FROM automatic_variants WHERE id=?", (auto_id,)).fetchone()
            if old is None:
                con.execute("""INSERT INTO automatic_variants
                    (id,title,target_exam_year,base_variant_id,generation_rule)
                    VALUES (?,?,?,?,?)""",
                    (auto_id, entry["title"], target_year, entry["variant_id"], RULE))
            elif old["title"] != entry["title"] or old["target_exam_year"] != target_year:
                con.execute("""UPDATE automatic_variants SET title=?,target_exam_year=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (entry["title"], target_year, auto_id))
            selected = {number: picks[slot][number]["id"] for number in range(1, 27)}
            current = dict(con.execute("""SELECT problem_number,problem_id
                FROM automatic_variant_problems WHERE automatic_variant_id=?""", (auto_id,)))
            if current != selected:
                con.execute("DELETE FROM automatic_variant_problems WHERE automatic_variant_id=?", (auto_id,))
                con.executemany("""INSERT INTO automatic_variant_problems
                    (automatic_variant_id,problem_number,problem_id) VALUES (?,?,?)""",
                    ((auto_id, number, selected[number]) for number in range(1, 27)))
                con.execute("UPDATE automatic_variants SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (auto_id,))
            changed = sum(families[selected[n]] != families[base_tasks[slot][n]["id"]]
                          for n in range(1, 27))
            result.append((entry["title"], entry["base"], changed))
    return result


def main() -> None:
    plan = load_plan()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    result = build(con, plan)
    for title, base, changed in result:
        print(f"{title}: base {base}, changed {changed} tasks")
    print(f"Stored {len(result)} disjoint automatic variants")


if __name__ == "__main__":
    main()

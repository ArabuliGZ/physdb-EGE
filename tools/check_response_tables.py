"""Check response-table metadata for the four current matching positions."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from variant_tex import RESPONSE_POSITIONS, response_labels  # noqa: E402


def main() -> None:
    con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT p.*,r.target_problem_number
        FROM relevance r JOIN problems p ON p.id=r.problem_id
        WHERE r.exam_year=2027 AND r.target_problem_number IN (6,10,15,17)
            AND r.verdict IN ('yes','partial')
        ORDER BY r.target_problem_number,p.id""").fetchall()
    counts = {number: 0 for number in RESPONSE_POSITIONS}
    for row in rows:
        problem = dict(row)
        labels = response_labels(problem)
        if labels is None or len(labels) != 2 or any(not label.strip() for label in labels):
            raise ValueError(f"Missing response table for problem {problem['id']}")
        counts[problem["target_problem_number"]] += 1
    missing = sorted(RESPONSE_POSITIONS.difference(number for number, count in counts.items() if count))
    if missing:
        raise ValueError(f"No checked tasks for positions: {missing}")
    source_rows = con.execute("""SELECT p.* FROM problems p
        WHERE p.problem_number IN (6,10,15,17) AND p.answer_format='matching'
        ORDER BY p.problem_number,p.id""").fetchall()
    for row in source_rows:
        problem = dict(row)
        labels = response_labels(problem)
        if labels is None or len(labels) != 2 or any(not label.strip() for label in labels):
            raise ValueError(f"Missing source-position response table for problem {problem['id']}")
    print("Checked response tables: " + ", ".join(
        f"№{number} — {counts[number]}" for number in sorted(counts)) +
        f"; source positions — {len(source_rows)}")


if __name__ == "__main__":
    main()

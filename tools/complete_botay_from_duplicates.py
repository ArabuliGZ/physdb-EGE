"""Fill missing Botay fields from identical problems already in the local bank.

The condition and every displayed condition figure must match. This is deliberately
conservative: a similar problem with changed numbers or a different graph is not a
source for its answer. Run after a Botay import and after site-editor replay.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
FIELDS = ("answer", "solution", "criteria")
# These three conditions differ only in TeX spacing/punctuation; the numerical
# values and every physical detail were compared by hand before whitelisting.
APPROVED_EQUIVALENTS = {
    (2025, "БОТАЙ-СЗ-4", 12): (2025, "1-2", 12),
    (2024, "БОТАЙ-ОСНОВ-2", 4): (2024, "2-1", 4),
    (2024, "БОТАЙ-ОСНОВ-2", 16): (2024, "2-1", 16),
}


def normalize(statement: str) -> str:
    return re.sub(r"\s+", " ", statement).strip()


def is_botay(year: int, number: str) -> bool:
    return number.startswith("БОТАЙ-") or (
        year == 2026 and number in {"ДОСРОК-1", "ОСНОВ-ДВ-1", "ОТКРЫТ-1"}
    )


def run(con: sqlite3.Connection, *, write: bool = False) -> dict[str, int]:
    con.row_factory = sqlite3.Row
    rows = list(con.execute("""SELECT p.id,p.problem_number,p.statement,p.answer,
        p.solution,p.criteria,v.exam_year,v.variant_number
        FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE p.alternative_number=1"""))
    figures: dict[str, list[str]] = defaultdict(list)
    for pid, sha in con.execute("""SELECT pa.problem_id,a.sha256 FROM problem_assets pa
        JOIN assets a ON a.id=pa.asset_id WHERE pa.role='statement_figure'"""):
        figures[pid].append(sha)
    groups: dict[tuple[str, tuple[str, ...]], list[sqlite3.Row]] = defaultdict(list)
    by_label = {(r["exam_year"], r["variant_number"], r["problem_number"]): r
                for r in rows}
    for row in rows:
        key = (normalize(row["statement"] or ""), tuple(sorted(figures[row["id"]])))
        groups[key].append(row)
    counts = defaultdict(int)
    for row in rows:
        if not is_botay(row["exam_year"], row["variant_number"]):
            continue
        key = (normalize(row["statement"] or ""), tuple(sorted(figures[row["id"]])))
        for field in FIELDS:
            if field != "answer" and row["problem_number"] < 21:
                continue
            if row[field]:
                continue
            candidates = [item for item in groups[key]
                          if item["id"] != row["id"] and item[field]]
            approved = APPROVED_EQUIVALENTS.get(
                (row["exam_year"], row["variant_number"], row["problem_number"]))
            if approved:
                source = by_label[approved]
                if tuple(sorted(figures[source["id"]])) == key[1] and source[field]:
                    candidates.append(source)
            values = {item[field].strip() for item in candidates}
            if len(values) != 1:
                if len(values) > 1:
                    counts["conflicts"] += 1
                continue
            source = candidates[0]
            source_label = (f"{source['exam_year']}-{source['variant_number']} "
                            f"№{source['problem_number']}")
            print(f"{row['exam_year']}-{row['variant_number']} "
                  f"№{row['problem_number']} {field} <- {source_label}")
            counts[field] += 1
            if write:
                con.execute(f"""UPDATE problems SET {field}=?,
                    review_notes=COALESCE(review_notes,'') || ?
                    WHERE id=? AND ({field} IS NULL OR trim({field})='')""",
                    (next(iter(values)), f" {field}: совпадение условия и рисунков с {source_label}.",
                     row["id"]))
    return dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    con = sqlite3.connect(DB)
    try:
        with con:
            counts = run(con, write=args.write)
        print(counts)
    finally:
        con.close()


if __name__ == "__main__":
    main()

"""Allow historical source numbers 27–30 without changing the 2027 plan."""
from __future__ import annotations

import sqlite3


def allow_thirty_source_numbers(con: sqlite3.Connection) -> None:
    original = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='problems'"
    ).fetchone()
    if original is None or "BETWEEN 1 AND 30" in original[0]:
        return
    if "BETWEEN 1 AND 26" not in original[0]:
        raise ValueError("Unknown problems table schema; refusing automatic migration")
    if con.in_transaction:
        raise ValueError("Run schema migration before opening an import transaction")
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        con.execute("BEGIN")
        con.execute(original[0].replace("CREATE TABLE problems", "CREATE TABLE problems_new", 1)
                    .replace("BETWEEN 1 AND 26", "BETWEEN 1 AND 30", 1))
        con.execute("INSERT INTO problems_new SELECT * FROM problems")
        con.execute("DROP TABLE problems")
        con.execute("ALTER TABLE problems_new RENAME TO problems")
        con.execute("CREATE INDEX IF NOT EXISTS problems_variant_idx ON problems(variant_id, problem_number)")
        if con.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign key check failed after problems migration")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")

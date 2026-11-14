"""Replace obsolete draft wording in stored 2027 relevance explanations.

The source assessment scripts use the approved FIPI specification. This
metadata-only migration also updates records that need no source reimport.
"""
from __future__ import annotations

import sqlite3

from import_examples import DB


def main() -> None:
    con = sqlite3.connect(DB)
    with con:
        con.execute("""UPDATE relevance SET reason=replace(reason,
            'проекта 2027', 'спецификации 2027')
            WHERE exam_year=2027 AND reason LIKE '%проекта 2027%'""")
    pending = con.execute("""SELECT COUNT(*) FROM relevance WHERE exam_year=2027
        AND reason LIKE '%проекта 2027%'""").fetchone()[0]
    if pending:
        raise ValueError(f"Obsolete 2027 relevance labels: {pending}")
    print("2027 relevance explanations use the approved specification")
    con.close()


if __name__ == "__main__":
    main()

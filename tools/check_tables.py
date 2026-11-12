"""Guard against Word layout tables leaking into published problem statements."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
tabular = re.compile(r"\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}")
table_count = 0
for year, variant, number, statement in con.execute("""SELECT v.exam_year,v.variant_number,
        p.problem_number,p.statement FROM problems p JOIN variants v ON v.id=p.variant_id"""):
    key = (year, variant, number)
    assert "Не забудьте перенести все ответы" not in statement, key
    assert "Для записи ответов на задания" not in statement, key
    for body in tabular.findall(statement):
        table_count += 1
        rows = [re.split(r"(?<!\\)&", row) for row in re.split(r"\\\\\s*\n", body)
                if row.strip()]
        widths = {len(row) for row in rows}
        assert len(widths) == 1, (key, widths)
        assert sum(bool(cell.strip()) for row in rows for cell in row) >= 2, key
        assert not (len(rows) == 2 and len(rows[0]) == 3
                    and not rows[0][1] and not rows[1][1] and not rows[1][2]), key
assert table_count > 0
checked = con.execute("""SELECT p.statement FROM problems p JOIN variants v ON v.id=p.variant_id
    WHERE v.exam_year=2026 AND v.variant_number='3' AND p.problem_number=18""").fetchone()[0]
assert [int(n) for n in re.findall(r"(?m)^(\d)\) ", checked)] == [1, 2, 3, 4, 5]
for variant in ("1-2", "2-2"):
    checked = con.execute("""SELECT p.statement FROM problems p JOIN variants v ON v.id=p.variant_id
        WHERE v.exam_year=2025 AND v.variant_number=? AND p.problem_number=7""",
                          (variant,)).fetchone()[0]
    assert r"10^5" in checked and r"10^{-3}" in checked
print(f"{table_count} structured tables checked; no Word layout or exam notices")

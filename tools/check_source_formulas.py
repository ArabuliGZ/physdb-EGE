"""Validate every embedded equation reference in the published database."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from verified_solutions import VERIFIED_SOLUTIONS


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\[\[formula:([0-9a-f]{64}):(\d+):(\d+)\]\]")
con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
files: set[Path] = set()
total = 0
for row in con.execute("SELECT statement,answer,solution,criteria FROM problems"):
    assert not TOKEN.search(row[0] or ""), "Untranscribed formula in a problem statement"
    for value in row:
        if not value:
            continue
        assert "[формула в исходном DOCX" not in value, value[:100]
        assert "[[SRCFORMULA" not in value, value[:100]
        for sha, width, height in TOKEN.findall(value):
            assert int(width) > 0 and int(height) > 0
            files.add(ROOT / "assets" / "formulas" / sha[:2] / f"{sha}.png")
            total += 1
assert total > 0, total
for path in files:
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == path.stem, path
verified = json.loads((ROOT / "tools" / "verified_formulas.json").read_text(encoding="utf-8"))
source_mathml = json.loads((ROOT / "tools" / "source_mathml_formulas.json").read_text(encoding="utf-8"))
assert not set(verified) & set(source_mathml)
assert all((ROOT / Path(value["source"].replace("\\", "/"))).is_file() and value["ole"]
           for value in source_mathml.values())
verified_files = {ROOT / "assets" / "formulas" / sha[:2] / f"{sha}.png"
                  for sha in set(verified) | set(source_mathml)}
assert all(path.is_file() for path in verified_files)
orphaned = set((ROOT / "assets" / "formulas").rglob("*.png")) - (files | verified_files)
assert not orphaned, sorted(orphaned)
for (variant, number), (source, solution) in VERIFIED_SOLUTIONS.items():
    assert source and solution and not TOKEN.search(solution), (variant, number)
    assert solution.count(r"\(") == solution.count(r"\)"), (variant, number)
print(f"{total} inline source formulas; {len(files)} distinct PNGs; no placeholders or missing files")

"""Validate every embedded equation reference in the published database."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\[\[formula:([0-9a-f]{64}):(\d+):(\d+)\]\]")
con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
files: set[Path] = set()
total = 0
for row in con.execute("SELECT statement,answer,solution,criteria FROM problems"):
    for value in row:
        if not value:
            continue
        assert "[формула в исходном DOCX" not in value, value[:100]
        assert "[[SRCFORMULA" not in value, value[:100]
        for sha, width, height in TOKEN.findall(value):
            assert int(width) > 0 and int(height) > 0
            files.add(ROOT / "assets" / "formulas" / sha[:2] / f"{sha}.png")
            total += 1
assert total >= 900, total
for path in files:
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == path.stem, path
assert files == set((ROOT / "assets" / "formulas").rglob("*.png"))
print(f"{total} inline source formulas; {len(files)} distinct PNGs; no placeholders or missing files")

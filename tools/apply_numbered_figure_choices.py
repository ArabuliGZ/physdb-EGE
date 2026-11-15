"""Replace five-choice composite links with five cropped statement figures.

Only problem_assets and newly generated assets change. Site text edits are not touched.
The operation is idempotent and checks the source SHA before changing a link.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from import_examples import DB, ROOT, link_asset, store_asset
from numbered_figure_choices import split_numbered_choices


TARGETS = {
    (2027, "ДЕМО", 20): "eeb8e40c011340c8458157ef7ba3d6d397bb3959fbc34a9e4a772ce7f5e5ac2c",
    (2026, "1", 20): "a16c1726094157a3b63250bf69e257f426bddca41d47d142f8c7c0f2743b0a72",
    (2025, "1-2", 20): "eba09f250af76bb8dee66351f38dd6c21989194f5b4f13e9310b04f68c0b0e28",
    (2025, "2-2", 20): "eba09f250af76bb8dee66351f38dd6c21989194f5b4f13e9310b04f68c0b0e28",
    (2024, "1-4", 20): "6deb5bf63fc2cf9f9959265e4f90bfadcbf0e635e741ecf74b4107c65e5ea558",
    (2024, "2-2", 20): "cef46af407c88939eb27ace83141f9a96ee44f3150a007e97b91b9ca6755024f",
}


def main() -> None:
    con = sqlite3.connect(DB)
    prepared = []
    for (year, variant, number), expected_sha in TARGETS.items():
        problem = con.execute("""SELECT p.id FROM problems p JOIN variants v ON v.id=p.variant_id
            WHERE v.exam_year=? AND v.variant_number=? AND p.problem_number=?
            AND p.alternative_number=1""", (year, variant, number)).fetchone()
        if problem is None:
            raise ValueError(f"Missing task {year}-{variant}-{number}")
        problem_id = problem[0]
        figures = con.execute("""SELECT a.sha256,a.storage_path,pa.source_locator
            FROM problem_assets pa JOIN assets a ON a.id=pa.asset_id
            WHERE pa.problem_id=? AND pa.role='statement_figure' ORDER BY pa.rowid""",
            (problem_id,)).fetchall()
        if len(figures) == 5 and all("choice " in (row[2] or "") for row in figures):
            print(f"Already split: {year}-{variant}-{number}")
            continue
        if len(figures) != 1 or figures[0][0] != expected_sha:
            raise ValueError(f"Unexpected source figures for {year}-{variant}-{number}: {figures}")
        source_path = (ROOT / figures[0][1]).resolve()
        if not source_path.is_relative_to((ROOT / "assets" / "objects").resolve()):
            raise ValueError(f"Unexpected asset path: {source_path}")
        prepared.append((problem_id, year, variant, number, figures[0][2] or "source figure",
                         split_numbered_choices(source_path.read_bytes())))

    with con:
        for problem_id, year, variant, number, locator, parts in prepared:
            con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                        (problem_id,))
            for index, content in enumerate(parts, 1):
                asset_id = store_asset(con, content, ".png", "image/png")
                link_asset(con, problem_id, asset_id, "statement_figure",
                           f"{locator}; choice {index} of 5")
            print(f"Split: {year}-{variant}-{number}: 5 images")
        con.execute("DELETE FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)")
    con.close()


if __name__ == "__main__":
    main()

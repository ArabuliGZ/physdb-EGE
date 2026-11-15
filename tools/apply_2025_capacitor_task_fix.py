"""Apply the visually checked 2025 capacitor task repair without a full reimport."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "tools"))

from editor import read_edit_log, write_edit_log  # noqa: E402
from import_examples import DB, link_asset, store_asset  # noqa: E402
from import_2024_2025 import (CAPACITOR_DISTANCE_STATEMENT, CURATED_FIGURES,
                              RENDERED_FIGURES)  # noqa: E402
from numbered_figure_choices import split_numbered_choices  # noqa: E402


TARGETS = (("1-2", "2025-1-2"), ("2-2", "2025-2-2"))
EDIT_LOG = ROOT / "tools" / "site_edits" / "problem_text_edits.json"


def main() -> None:
    con = sqlite3.connect(DB)
    orphaned: list[Path] = []
    repaired_ids: list[str] = []
    with con:
        for variant_number, label in TARGETS:
            row = con.execute("""SELECT p.id,p.review_notes FROM problems p
                JOIN variants v ON v.id=p.variant_id
                WHERE v.exam_year=2025 AND v.variant_number=?
                AND p.problem_number=20 AND p.alternative_number=1""",
                              (variant_number,)).fetchone()
            if row is None:
                raise ValueError(f"Missing 2025-{variant_number} task 20")
            problem_id, notes = row
            checked_note = ("Условие и пять схем задания 20 визуально сверены по "
                            "отрисованной странице 12 исходного Word-документа.")
            if checked_note not in (notes or ""):
                notes = ((notes or "").rstrip() + " " + checked_note).strip()
            con.execute("UPDATE problems SET statement=?,review_notes=? WHERE id=?",
                        (CAPACITOR_DISTANCE_STATEMENT, notes, problem_id))
            con.execute("DELETE FROM problem_assets WHERE problem_id=? AND role='statement_figure'",
                        (problem_id,))
            filename = RENDERED_FIGURES[(label, 20)]
            content = (CURATED_FIGURES / filename).read_bytes()
            for choice_number, part in enumerate(split_numbered_choices(content), 1):
                asset_id = store_asset(con, part, ".png", "image/png")
                link_asset(con, problem_id, asset_id, "statement_figure",
                           f"visually checked source-page crop: {filename}; "
                           f"source page 12; choice {choice_number}")
            repaired_ids.append(problem_id)

        orphaned = [ROOT / path for (path,) in con.execute("""SELECT storage_path FROM assets
            WHERE id NOT IN (SELECT asset_id FROM problem_assets)""")]
        con.execute("DELETE FROM assets WHERE id NOT IN (SELECT asset_id FROM problem_assets)")
    con.close()

    for path in orphaned:
        if path.resolve().is_relative_to((ROOT / "assets" / "objects").resolve()) and path.is_file():
            path.unlink()

    data = read_edit_log(EDIT_LOG)
    log_changes = 0
    for problem_id in repaired_ids:
        edit = data["problems"].get(problem_id)
        if edit and "statement" in edit.get("fields", {}):
            edit["fields"]["statement"] = CAPACITOR_DISTANCE_STATEMENT
            edit["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            log_changes += 1
    if log_changes:
        write_edit_log(EDIT_LOG, data)
    print(f"Repaired capacitor task 20 in {len(repaired_ids)} variants; "
          f"updated {log_changes} saved site edit(s)")


if __name__ == "__main__":
    main()

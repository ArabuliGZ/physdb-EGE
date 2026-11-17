"""Create a contact sheet of a scanned odd variant's imported figures for QA."""
from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw

from import_examples import DB, ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", type=int)
    args = parser.parse_args()
    con = sqlite3.connect(DB)
    rows = con.execute(
        """SELECT p.problem_number,pa.role,a.storage_path FROM problems p
           JOIN variants v ON v.id=p.variant_id
           JOIN problem_assets pa ON pa.problem_id=p.id
           JOIN assets a ON a.id=pa.asset_id
           WHERE v.exam_year=2027 AND v.variant_number=?
           ORDER BY p.problem_number,pa.rowid""",
        (str(args.variant),),
    ).fetchall()
    width, height, columns = 330, 250, 3
    sheet = Image.new(
        "RGB", (columns * width, math.ceil(len(rows) / columns) * height), "white"
    )
    draw = ImageDraw.Draw(sheet)
    for index, (number, role, storage) in enumerate(rows):
        x, y = (index % columns) * width, (index // columns) * height
        image = Image.open(ROOT / storage).convert("RGB")
        image.thumbnail((width - 20, height - 40))
        sheet.paste(image, (x + (width - image.width) // 2, y + 30))
        draw.text((x + 8, y + 8), f"{number} {role}", fill="black")
    output = ROOT / "tmp" / "pdfs" / f"fipi_v{args.variant}_figures_contact.jpg"
    sheet.save(output, quality=88)
    print(output)


if __name__ == "__main__":
    main()

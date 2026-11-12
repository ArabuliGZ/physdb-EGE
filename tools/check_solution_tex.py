"""Check every TeX expression in solutions with the site's bundled KaTeX."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPRESSION = re.compile(r"(?<!\\)\\\((.*?)\\\)|(?<!\\)\\\[(.*?)\\\]", re.DOTALL)
DELIMITERS = ((r"(?<!\\)\\\(", r"(?<!\\)\\\)"),
              (r"(?<!\\)\\\[", r"(?<!\\)\\\]"))
NODE_SCRIPT = r"""
const fs = require('fs');
const katex = require(process.argv[1]);
const expressions = JSON.parse(fs.readFileSync(0, 'utf8'));
const errors = [];
for (let i = 0; i < expressions.length; i++) {
  try {
    katex.renderToString(expressions[i].tex, {throwOnError: true, strict: 'error'});
  } catch (error) {
    errors.push({index: i, message: error.message});
  }
}
process.stdout.write(JSON.stringify(errors));
"""


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("Node.js is required to check TeX with the site's KaTeX")
        return 2

    con = sqlite3.connect(ROOT / "data" / "phyege.sqlite3")
    rows = con.execute("""SELECT v.exam_year, v.variant_number, p.problem_number, p.solution
        FROM problems AS p JOIN variants AS v ON v.id = p.variant_id
        WHERE p.solution IS NOT NULL ORDER BY v.exam_year, v.variant_number, p.problem_number""")
    expressions = []
    delimiters = []
    for year, variant, number, solution in rows:
        label = f"{year}-{variant} №{number}"
        for opening, closing in DELIMITERS:
            starts = len(re.findall(opening, solution))
            ends = len(re.findall(closing, solution))
            if starts != ends:
                delimiters.append(f"{label}: {starts} openings, {ends} closings")
        for match in EXPRESSION.finditer(solution):
            expressions.append({"task": label, "tex": match.group(1) or match.group(2)})

    result = subprocess.run(
        [node, "-e", NODE_SCRIPT, str(ROOT / "web" / "static" / "katex.min.js")],
        input=json.dumps(expressions, ensure_ascii=False), text=True, encoding="utf-8",
        capture_output=True, check=False,
    )
    if result.returncode:
        print(result.stderr.strip())
        return result.returncode
    errors = json.loads(result.stdout)
    for label in sorted(set(delimiters)):
        print(f"Непарные границы TeX: {label}")
    for error in errors:
        item = expressions[error["index"]]
        print(f'{item["task"]}: {item["tex"]!r}: {error["message"]}')
    print(f"Проверено формул TeX: {len(expressions)}; ошибок: {len(errors) + len(set(delimiters))}")
    return 1 if errors or delimiters else 0


if __name__ == "__main__":
    raise SystemExit(main())

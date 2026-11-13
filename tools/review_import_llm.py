"""Read-only LLM plausibility review of imported physics text.

Run after deterministic checks. The reviewer reports suspects, never changes
SQLite. Every finding must be checked against the source DOCX/PDF before a fix.
Uses the authenticated Codex CLI; no API key is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "phyege.sqlite3"
REPORT = ROOT / "tmp" / "llm_text_review.json"
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "reviewed_ids": {"type": "array", "items": {"type": "string"}},
        "issues": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                "field": {"type": "string", "enum": ["statement", "solution"]},
                "fragment": {"type": "string"},
                "reason": {"type": "string"},
                "suggested_tex": {"type": "string"},
            },
            "required": ["id", "field", "fragment", "reason", "suggested_tex"],
        }},
    },
    "required": ["reviewed_ids", "issues"],
}


def records() -> list[dict[str, str]]:
    con = sqlite3.connect(DB)
    return [{"id": f"{year}-{variant}:{number}", "statement": statement,
             "solution": solution or ""}
            for year, variant, number, statement, solution in con.execute(
                """SELECT v.exam_year,v.variant_number,p.problem_number,p.statement,p.solution
                FROM problems p JOIN variants v ON v.id=p.variant_id
                ORDER BY v.exam_year,v.variant_number,p.problem_number""")]


def review_batch(batch: list[dict[str, str]]) -> dict:
    prompt = (
        "Ты проверяешь извлечённые условия и решения ЕГЭ по физике. "
        "Только прочитай переданный JSON; не вызывай инструменты и не меняй файлы. "
        "Найди вероятно потерянные степени 10, нижние индексы, знаки, единицы, "
        "физически невозможные порядки величин, распавшиеся формулы и арифметические "
        "противоречия между условием и решением. Обычное вычитание не считай степенью. "
        "Сообщай лишь конкретные подозрения; если источник недоступен, не утверждай, "
        "что предлагаемая формула точно авторская. В reviewed_ids перечисли ВСЕ id "
        "из входного массива. suggested_tex оставь пустым, если исправление нельзя "
        "обосновать по данным. Ответь строго по JSON-схеме.\n\n"
        + json.dumps(batch, ensure_ascii=False)
    )
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as directory:
        schema = Path(directory) / "schema.json"
        output = Path(directory) / "result.json"
        schema.write_text(json.dumps(SCHEMA, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            ["codex", "exec", "--sandbox", "read-only", "--ephemeral",
             "--output-schema", str(schema), "-o", str(output), "-"],
            input=prompt, text=True, encoding="utf-8", capture_output=True,
            cwd=ROOT, timeout=240,
        )
        if result.returncode:
            raise RuntimeError(f"Codex review failed: {result.stderr[-1500:]}")
        data = json.loads(output.read_text(encoding="utf-8"))
    expected = {item["id"] for item in batch}
    if set(data["reviewed_ids"]) != expected:
        raise ValueError(f"Incomplete LLM review: {expected - set(data['reviewed_ids'])}")
    if any(issue["id"] not in expected for issue in data["issues"]):
        raise ValueError("LLM returned an issue for an unknown task")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Trial size; omit to review all tasks")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--allow-remote", action="store_true",
                        help="Confirm permission to send task text to the Codex service")
    args = parser.parse_args()
    if not args.allow_remote:
        parser.error("Remote review sends task text to Codex; pass --allow-remote only after approval")
    data = records()[:args.limit] if args.limit else records()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"database_sha256": hashlib.sha256(DB.read_bytes()).hexdigest(),
              "reviewed_ids": [], "issues": []}
    for start in range(0, len(data), args.batch_size):
        result = review_batch(data[start:start + args.batch_size])
        report["reviewed_ids"].extend(result["reviewed_ids"])
        report["issues"].extend(result["issues"])
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reviewed {len(report['reviewed_ids'])}/{len(data)} tasks; "
              f"issues: {len(report['issues'])}", flush=True)


if __name__ == "__main__":
    main()

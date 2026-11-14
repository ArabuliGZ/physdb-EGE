"""Local PhysEGE catalogue and exam sheet generator."""
from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

if __package__:
    from .variant_tex import answer_field, compose, compile_pdf, project_zip, response_labels
else:
    from variant_tex import answer_field, compose, compile_pdf, project_zip, response_labels


ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
DB = Path(os.environ.get("PHYSEGE_DB", ROOT / "data" / "phyege.sqlite3"))
ASSETS = Path(os.environ.get("PHYSEGE_ASSETS", ROOT / "assets" / "objects"))
FORMULAS = Path(os.environ.get("PHYSEGE_FORMULAS", ROOT / "assets" / "formulas"))
MATERIALS = Path(os.environ.get("PHYSEGE_MATERIALS", ROOT / "Материалы"))


def rows(query: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(query, params)]
    finally:
        con.close()


def variants() -> list[dict]:
    items = rows("""SELECT v.id,v.title,v.exam_year,v.variant_number,v.is_official_demo,
        COUNT(DISTINCT p.id) AS problem_count,
        COUNT(DISTINCT p.problem_number) AS position_count,
        COUNT(DISTINCT CASE WHEN p.alternative_number=1 AND r.verdict='yes'
            THEN p.id END) AS suitable_count,
        COUNT(DISTINCT CASE WHEN p.alternative_number=1 AND r.verdict='partial'
            THEN p.id END) AS partially_suitable_count
        FROM variants v LEFT JOIN problems p ON p.variant_id=v.id
        LEFT JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027
        GROUP BY v.id ORDER BY v.exam_year DESC,v.variant_number""")
    for item in items:
        item["download_url"] = "/api/variants/" + item["id"] + "/source"
        item["companions"] = []
    by_id = {item["id"]: item for item in items}
    for companion in rows("SELECT variant_id,source_role FROM variant_sources ORDER BY source_role"):
        by_id[companion["variant_id"]]["companions"].append({
            "role": companion["source_role"],
            "download_url": "/api/variants/" + companion["variant_id"] + "/sources/" + companion["source_role"],
        })
    return items


def automatic_variants() -> list[dict]:
    return rows("""SELECT a.id,a.title,a.target_exam_year,a.base_variant_id,
        v.title AS base_title,v.exam_year AS base_year,
        v.variant_number AS base_variant_number,v.is_official_demo AS base_is_official_demo,
        COUNT(ap.problem_id) AS problem_count,
        SUM(CASE WHEN r.verdict='yes' THEN 1 ELSE 0 END) AS suitable_count,
        SUM(CASE WHEN p.variant_id<>a.base_variant_id THEN 1 ELSE 0 END) AS replacement_count
        FROM automatic_variants a JOIN variants v ON v.id=a.base_variant_id
        JOIN automatic_variant_problems ap ON ap.automatic_variant_id=a.id
        JOIN problems p ON p.id=ap.problem_id
        LEFT JOIN relevance r ON r.problem_id=p.id AND r.exam_year=a.target_exam_year
            AND r.target_problem_number=ap.problem_number
        GROUP BY a.id
        ORDER BY CAST(TRIM(SUBSTR(a.title, INSTR(a.title, '№') + 1)) AS INTEGER),a.title""")


def list_problems(query: dict[str, list[str]]) -> list[dict]:
    conditions = []
    params = []
    if query.get("variant_id"):
        conditions.append("p.variant_id=?")
        params.append(query["variant_id"][0])
    if query.get("number"):
        try:
            number = int(query["number"][0])
        except ValueError:
            return []
        if not 1 <= number <= 26:
            return []
        conditions.append("r.target_problem_number=? AND r.verdict IN ('yes','partial')")
        params.append(number)
        relevance_join = "JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027"
    else:
        relevance_join = """LEFT JOIN relevance r ON r.rowid=(
            SELECT candidate.rowid FROM relevance candidate
            WHERE candidate.problem_id=p.id AND candidate.exam_year=2027
            ORDER BY CASE candidate.verdict WHEN 'yes' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END,
                candidate.target_problem_number LIMIT 1)"""
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    items = rows(f"""SELECT p.*,v.title AS variant_title,v.exam_year,v.variant_number,v.is_official_demo,
        v.source_path,r.verdict,r.reason AS relevance_reason,r.topic_match,r.format_match,
        r.target_problem_number
        FROM problems p JOIN variants v ON v.id=p.variant_id
        {relevance_join}
        {where} ORDER BY v.exam_year DESC,v.variant_number,p.problem_number,p.alternative_number""",
                tuple(params))
    if items:
        assets = rows("""SELECT pa.problem_id,a.id,a.media_type,a.storage_path,a.size_bytes,
            pa.role,pa.source_locator
            FROM problem_assets pa JOIN assets a ON a.id=pa.asset_id
            ORDER BY pa.rowid""")
        by_problem: dict[str, list[dict]] = {}
        for asset in assets:
            asset["url"] = "/assets/" + Path(asset["storage_path"]).name[:2] + "/" + Path(asset["storage_path"]).name
            by_problem.setdefault(asset.pop("problem_id"), []).append(asset)
        for item in items:
            item["assets"] = by_problem.get(item["id"], [])
            item["response_labels"] = list(response_labels(item) or ())
            item["answer_field"] = answer_field(item)
    return items


def get_problem(problem_id: str) -> dict | None:
    result = rows("""SELECT p.*,v.title AS variant_title,v.exam_year,v.variant_number,v.is_official_demo,
        v.source_path,r.verdict,r.reason AS relevance_reason,r.topic_match,r.format_match,
        r.target_problem_number
        FROM problems p JOIN variants v ON v.id=p.variant_id
        LEFT JOIN relevance r ON r.rowid=(
            SELECT candidate.rowid FROM relevance candidate
            WHERE candidate.problem_id=p.id AND candidate.exam_year=2027
            ORDER BY CASE candidate.verdict WHEN 'yes' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END,
                candidate.target_problem_number LIMIT 1)
        WHERE p.id=?""", (problem_id,))
    if not result:
        return None
    item = result[0]
    item["assets"] = rows("""SELECT a.id,a.media_type,a.storage_path,pa.role,pa.source_locator
        FROM problem_assets pa JOIN assets a ON a.id=pa.asset_id
        WHERE pa.problem_id=? ORDER BY pa.role,pa.rowid""", (problem_id,))
    for asset in item["assets"]:
        asset["url"] = "/assets/" + Path(asset["storage_path"]).name[:2] + "/" + Path(asset["storage_path"]).name
    item["response_labels"] = list(response_labels(item) or ())
    item["answer_field"] = answer_field(item)
    return item


def variant_options() -> list[dict]:
    return rows("""SELECT p.id,p.variant_id,r.target_problem_number AS problem_number,
        p.problem_number AS source_problem_number,p.alternative_number,
        v.title AS variant_title,v.exam_year,v.variant_number,v.is_official_demo,
        r.verdict,r.reason AS relevance_reason
        FROM problems p JOIN variants v ON v.id=p.variant_id
        JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027
            AND r.verdict IN ('yes','partial')
        ORDER BY r.target_problem_number,v.exam_year DESC,v.variant_number,p.alternative_number""")


def selected_problems(variant_id: str | None, ids: list[str] | None) -> list[dict]:
    if variant_id:
        candidates = list_problems({"variant_id": [variant_id]})
        by_number = {}
        for problem in candidates:
            by_number.setdefault(problem["problem_number"], problem)
        count = len(by_number)
        return [by_number[n] for n in range(1, count + 1)] if count in (26, 30) and \
            set(by_number) == set(range(1, count + 1)) else []
    if not ids or len(ids) != 26 or len(set(ids)) != 26:
        return []
    found = {problem["id"]: problem for problem in list_problems({}) if problem["id"] in ids}
    if len(found) != 26:
        return []
    allowed = {(row["problem_id"], row["target_problem_number"]) for row in rows("""SELECT
        problem_id,target_problem_number FROM relevance WHERE exam_year=2027
        AND verdict IN ('yes','partial')""")}
    if any((problem_id, number) not in allowed for number, problem_id in enumerate(ids, 1)):
        return []
    return [{**found[problem_id], "source_problem_number": found[problem_id]["problem_number"],
             "problem_number": number} for number, problem_id in enumerate(ids, 1)]


def automatic_problem_ids(automatic_id: str) -> list[str]:
    return [item["problem_id"] for item in rows("""SELECT problem_id
        FROM automatic_variant_problems WHERE automatic_variant_id=?
        ORDER BY problem_number""", (automatic_id,))]


def automatic_problems(automatic_id: str) -> list[dict]:
    return selected_problems(None, automatic_problem_ids(automatic_id))


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, payload: bytes, content_type: str, filename: str,
                   download: bool = True) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        disposition = "attachment" if download else "inline"
        self.send_header("Content-Disposition", disposition + "; filename*=UTF-8''" + quote(filename))
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_exam(self, variant_id: str | None, query: dict[str, list[str]],
                  kind: str, document: str = "conditions", automatic_id: str | None = None) -> None:
        if automatic_id:
            automatic = rows("SELECT title,target_exam_year FROM automatic_variants WHERE id=?", (automatic_id,))
            if not automatic:
                self.send_error(404)
                return
            title, year = automatic[0]["title"], automatic[0]["target_exam_year"]
            filename = "automatic-variant-" + automatic_id
            ids = automatic_problem_ids(automatic_id)
        elif variant_id:
            variant = rows("SELECT title,exam_year FROM variants WHERE id=?", (variant_id,))
            if not variant:
                self.send_error(404)
                return
            title, year = variant[0]["title"], variant[0]["exam_year"]
            filename = "variant-" + variant_id
            ids = None
        else:
            title, year = "Тренировочный вариант по физике", 2027
            filename = "physege-custom-2027"
            ids = query.get("ids", [""])[0].split(",")
        problems = selected_problems(variant_id, ids)
        expected = 30 if variant_id and year in (2022, 2023) else 26
        if len(problems) != expected or [p["problem_number"] for p in problems] != list(range(1, expected + 1)):
            self.send_json({"error": f"Нужны задания с номерами 1–{expected}"}, 400)
            return
        try:
            content, figures = compose(problems, title, year, ASSETS, FORMULAS, document)
            if document != "conditions":
                filename += "-" + document
            if kind == "tex":
                self.send_bytes(content.encode("utf-8"), "application/x-tex; charset=utf-8", filename + ".tex")
            elif kind == "zip":
                self.send_bytes(project_zip(content, figures, filename + ".tex"), "application/zip", filename + ".zip")
            else:
                self.send_bytes(compile_pdf(content, figures), "application/pdf", filename + ".pdf", False)
        except (ValueError, RuntimeError) as exc:
            self.send_json({"error": str(exc)}, 500)

    def send_json(self, data: object, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, path: Path, cache: bool = False, download: bool = False) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        if download:
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(path.name))
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "public, max-age=86400" if cache else "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        route = url.path
        if route == "/api/health":
            self.send_json({"ok": DB.is_file()})
        elif route == "/api/variants":
            self.send_json(variants())
        elif route == "/api/automatic-variants":
            self.send_json(automatic_variants())
        elif route == "/api/variant-options":
            self.send_json(variant_options())
        elif route.startswith("/api/automatic-variants/"):
            parts = route.removeprefix("/api/automatic-variants/").split("/")
            if len(parts) == 2 and parts[1] == "problems":
                found = rows("SELECT id FROM automatic_variants WHERE id=?", (parts[0],))
                self.send_json(automatic_problems(parts[0])) if found else self.send_error(404)
            elif len(parts) == 2 and parts[1] in ("tex", "pdf", "zip"):
                self.send_exam(None, {}, parts[1], automatic_id=parts[0])
            elif len(parts) == 3 and parts[1] in ("answers", "solutions", "criteria") \
                    and parts[2] in ("tex", "pdf", "zip"):
                self.send_exam(None, {}, parts[2], parts[1], automatic_id=parts[0])
            else:
                self.send_error(404)
        elif route.startswith("/api/variants/") and route.rsplit("/", 1)[-1] in ("tex", "pdf", "zip"):
            parts = route.removeprefix("/api/variants/").split("/")
            if len(parts) == 2:
                variant_id, kind = parts
                document = "conditions"
            elif len(parts) == 3 and parts[1] in ("answers", "solutions", "criteria"):
                variant_id, document, kind = parts
            else:
                self.send_error(404)
                return
            self.send_exam(variant_id, {}, kind, document)
        elif route == "/api/assemble" and parse_qs(url.query).get("format", [""])[0] in ("tex", "pdf", "zip"):
            query = parse_qs(url.query)
            document = query.get("document", ["conditions"])[0]
            if document not in ("conditions", "answers", "solutions", "criteria"):
                self.send_error(400)
                return
            self.send_exam(None, query, query["format"][0], document)
        elif route.startswith("/api/variants/") and route.endswith("/source"):
            variant_id = route.removeprefix("/api/variants/").removesuffix("/source")
            found = rows("SELECT source_path FROM variants WHERE id=?", (variant_id,))
            if not found:
                self.send_error(404)
                return
            # The database is imported on Windows and may contain backslashes.
            relative = Path(found[0]["source_path"].replace("\\", "/"))
            if relative.parts[0] != "Материалы":
                self.send_error(403)
                return
            path = (MATERIALS / Path(*relative.parts[1:])).resolve()
            if not path.is_relative_to(MATERIALS.resolve()):
                self.send_error(403)
                return
            self.send_file(path, download=True)
        elif route.startswith("/api/variants/") and "/sources/" in route:
            rest = route.removeprefix("/api/variants/")
            variant_id, role = rest.split("/sources/", 1)
            found = rows("SELECT source_path FROM variant_sources WHERE variant_id=? AND source_role=?",
                         (variant_id, role))
            if not found:
                self.send_error(404)
                return
            relative = Path(found[0]["source_path"].replace("\\", "/"))
            if relative.parts[0] != "Материалы":
                self.send_error(403)
                return
            path = (MATERIALS / Path(*relative.parts[1:])).resolve()
            if not path.is_relative_to(MATERIALS.resolve()):
                self.send_error(403)
                return
            self.send_file(path, download=True)
        elif route == "/api/problems":
            self.send_json(list_problems(parse_qs(url.query)))
        elif route.startswith("/api/problems/"):
            item = get_problem(route.removeprefix("/api/problems/"))
            self.send_json(item, 200) if item else self.send_json({"error": "not found"}, 404)
        elif route.startswith("/formulas/"):
            path = (FORMULAS / route.removeprefix("/formulas/")).resolve()
            if path.is_relative_to(FORMULAS.resolve()):
                self.send_file(path, cache=True)
            else:
                self.send_error(403)
        elif route.startswith("/assets/"):
            path = (ASSETS / route.removeprefix("/assets/")).resolve()
            if path.is_relative_to(ASSETS.resolve()):
                self.send_file(path, cache=True)
            else:
                self.send_error(403)
        else:
            name = route.removeprefix("/static/") if route.startswith("/static/") else "index.html"
            path = (STATIC / name).resolve()
            if path.is_relative_to(STATIC.resolve()):
                self.send_file(path)
            else:
                self.send_error(403)


if __name__ == "__main__":
    host = os.environ.get("PHYSEGE_HOST", "127.0.0.1")
    port = int(os.environ.get("PHYSEGE_PORT", "8001"))
    if not DB.is_file():
        raise SystemExit(f"Database not found: {DB}")
    print(f"PhysEGE: http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()

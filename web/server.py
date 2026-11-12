"""Read-only local browser for the PhysEGE SQLite database."""
from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
DB = Path(os.environ.get("PHYSEGE_DB", ROOT / "data" / "phyege.sqlite3"))
ASSETS = Path(os.environ.get("PHYSEGE_ASSETS", ROOT / "assets" / "objects"))
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
        COUNT(p.id) AS problem_count,COUNT(DISTINCT p.problem_number) AS position_count
        FROM variants v LEFT JOIN problems p ON p.variant_id=v.id
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
        conditions.append("p.problem_number=?")
        params.append(number)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    items = rows(f"""SELECT p.*,v.title AS variant_title,v.exam_year,v.variant_number,v.is_official_demo,
        v.source_path,r.verdict,r.reason AS relevance_reason,r.topic_match,r.format_match
        FROM problems p JOIN variants v ON v.id=p.variant_id
        LEFT JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027
            AND r.target_problem_number=p.problem_number
        {where} ORDER BY v.exam_year DESC,v.variant_number,p.problem_number,p.alternative_number""",
                tuple(params))
    if items:
        assets = rows("""SELECT pa.problem_id,a.id,a.media_type,a.storage_path,a.size_bytes,
            pa.role,pa.source_locator
            FROM problem_assets pa JOIN assets a ON a.id=pa.asset_id""")
        by_problem: dict[str, list[dict]] = {}
        for asset in assets:
            asset["url"] = "/assets/" + Path(asset["storage_path"]).name[:2] + "/" + Path(asset["storage_path"]).name
            by_problem.setdefault(asset.pop("problem_id"), []).append(asset)
        for item in items:
            item["assets"] = by_problem.get(item["id"], [])
    return items


def get_problem(problem_id: str) -> dict | None:
    result = rows("""SELECT p.*,v.title AS variant_title,v.exam_year,v.variant_number,v.is_official_demo,
        v.source_path,r.verdict,r.reason AS relevance_reason,r.topic_match,r.format_match
        FROM problems p JOIN variants v ON v.id=p.variant_id
        LEFT JOIN relevance r ON r.problem_id=p.id AND r.exam_year=2027
            AND r.target_problem_number=p.problem_number
        WHERE p.id=?""", (problem_id,))
    if not result:
        return None
    item = result[0]
    item["assets"] = rows("""SELECT a.id,a.media_type,a.storage_path,pa.role,pa.source_locator
        FROM problem_assets pa JOIN assets a ON a.id=pa.asset_id
        WHERE pa.problem_id=? ORDER BY pa.role,a.storage_path""", (problem_id,))
    for asset in item["assets"]:
        asset["url"] = "/assets/" + Path(asset["storage_path"]).name[:2] + "/" + Path(asset["storage_path"]).name
    return item


class Handler(BaseHTTPRequestHandler):
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

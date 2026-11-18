"""Archive the 2024 main and open EGE papers from Botay."""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "Материалы" / "ЕГЭ 2024 Botay"
BASE = "https://botay.pro/olimpiady/ege"
SLUGS = (
    "2024-real-11-24105",
    "2024-real-11-24107",
    "2024-real-11-24109",
    "2024-otkryt-11-1",
)


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (PhysEGE import)"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(4 * (attempt + 1))
    raise AssertionError("unreachable")


def archive(item: tuple[str, str]) -> tuple[str, dict]:
    relative, url = item
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        content = fetch(url)
        if relative.endswith(".pdf") and not content.startswith(b"%PDF"):
            raise ValueError(f"Not a PDF: {url}")
        if relative.endswith(".png") and not content.startswith(b"\x89PNG"):
            raise ValueError(f"Not a PNG: {url}")
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(target)
    content = target.read_bytes()
    record = {"url": url, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    print(f"{relative}: {len(content)} bytes", flush=True)
    return relative, record


def run_batch(items: list[tuple[str, str]]) -> dict:
    records = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed(pool.submit(archive, item) for item in items):
            relative, record = future.result()
            records[relative] = record
    return records


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    first = []
    for slug in SLUGS:
        first.append((f"{slug}/page.html", f"{BASE}/{slug}/"))
        for suffix in ("usloviya", "otvety", "resheniya"):
            first.append((f"{slug}/{suffix}.pdf", f"{BASE}/{slug}/ege-{slug}-{suffix}.pdf"))
    records = run_batch(first)
    figures = []
    for slug in SLUGS:
        page = html.fromstring((DEST / slug / "page.html").read_bytes())
        tasks = page.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' o-zad ')]")
        if len(tasks) != 26:
            raise ValueError(f"{slug}: expected 26 task blocks, found {len(tasks)}")
        for src in dict.fromkeys(page.xpath("//figure/img/@src")):
            relative = f"{slug}/images/{Path(src).name}"
            figures.append((relative, urljoin(BASE, src)))
        print(f"{slug}: {len(tasks)} tasks, {len(page.xpath('//figure/img/@src'))} figure links", flush=True)
    records.update(run_batch(figures))
    (DEST / "manifest.json").write_text(
        json.dumps(dict(sorted(records.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Archived {len(SLUGS)} papers and {len(records)} files", flush=True)


if __name__ == "__main__":
    main()

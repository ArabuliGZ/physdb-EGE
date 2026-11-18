"""Archive the three 2026 Botay variant pages and their PDF views."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "Материалы" / "ЕГЭ 2026 Botay"
BASE = "https://botay.pro/olimpiady/ege"
SLUGS = ("2026-osnov-11-dv-1", "2026-otkryt-11-1", "2026-dosrok-11-1")


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (PhysEGE import)"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for slug in SLUGS:
        files = {"page.html": f"{BASE}/{slug}/"}
        for suffix in ("usloviya", "otvety", "resheniya"):
            files[f"{suffix}.pdf"] = f"{BASE}/{slug}/ege-{slug}-{suffix}.pdf"
        for name, url in files.items():
            target = DEST / slug / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(fetch(url))
            content = target.read_bytes()
            manifest[f"{slug}/{name}"] = {
                "url": url, "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
            print(f"{slug}/{name}: {len(content)} bytes", flush=True)
        page = html.fromstring((DEST / slug / "page.html").read_text(encoding="utf-8"))
        for src in dict.fromkeys(page.xpath("//figure/img/@src")):
            url = urljoin(BASE, src)
            target = DEST / slug / "images" / Path(src).name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(fetch(url))
            content = target.read_bytes()
            manifest[f"{slug}/images/{target.name}"] = {
                "url": url, "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        print(f"{slug}: archived {len(page.xpath('//figure/img/@src'))} figure links", flush=True)
    (DEST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

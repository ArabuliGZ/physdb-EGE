"""Check the switchable MathJax/STIX renderer and its local assets."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "static"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    adapter = (STATIC / "math-renderer.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    site_css = (STATIC / "site.css").read_text(encoding="utf-8")
    font_css = (STATIC / "stix-two-text.css").read_text(encoding="utf-8")

    require('/static/math-renderer.js' in index, "Renderer adapter is not loaded")
    require('/static/stix-two-text.css' in index, "STIX Two Text CSS is not loaded")
    require('/static/katex.min.js' not in index, "KaTeX must be loaded only by the adapter")
    require("const DEFAULT_RENDERER = 'mathjax'" in adapter,
            "MathJax is not the default renderer")
    require("requestedRenderer" in adapter and "?math=katex" in adapter,
            "Per-page KaTeX rollback is not documented in the adapter")
    require("mtextInheritFont: true" in adapter,
            "Cyrillic text in formulas does not inherit the surrounding font")
    require("font: 'mathjax-stix2'" in adapter, "STIX Two math font is not selected")
    require("load: ['input/tex', 'output/chtml']" in adapter,
            "MathJax must use the modular TeX/CHTML build without menu or speech")
    require("window.MathJax.typesetPromise([target])" in adapter,
            "Dynamic formulas are not typeset through MathJax's document pipeline")
    require("PhysEgeMath.render" in app, "Application does not use the renderer adapter")
    require("window.katex.render" not in app, "Application still calls KaTeX directly")
    require('"STIX Two Text"' in site_css, "Content does not use STIX Two Text")

    mathjax_package = json.loads(
        (STATIC / "vendor" / "mathjax" / "package.json").read_text(encoding="utf-8")
    )
    stix_math_package = json.loads(
        (STATIC / "vendor" / "mathjax-stix2-font" / "package.json").read_text(encoding="utf-8")
    )
    stix_text_package = json.loads(
        (STATIC / "fonts" / "stix-two-text" / "package.json").read_text(encoding="utf-8")
    )
    require(mathjax_package["version"] == "4.1.3", "Unexpected MathJax version")
    require(stix_math_package["version"] == "4.1.3", "Unexpected STIX math version")
    require(stix_text_package["version"] == "5.3.0", "Unexpected STIX text package version")

    required_assets = [
        STATIC / "vendor" / "mathjax" / "startup.js",
        STATIC / "vendor" / "mathjax" / "core.js",
        STATIC / "vendor" / "mathjax" / "input" / "tex.js",
        STATIC / "vendor" / "mathjax" / "input" / "tex" / "extensions" / "textmacros.js",
        STATIC / "vendor" / "mathjax" / "output" / "chtml.js",
        STATIC / "vendor" / "mathjax-stix2-font" / "chtml.js",
        STATIC / "vendor" / "mathjax-stix2-font" / "chtml" / "dynamic" / "cyrillic.js",
        STATIC / "vendor" / "mathjax-stix2-font" / "chtml" / "woff2" / "mjx-stx-cy.woff2",
    ]
    for weight in (400, 600, 700):
        for style in ("normal", "italic"):
            for subset in ("cyrillic", "latin"):
                filename = f"stix-two-text-{subset}-{weight}-{style}.woff2"
                required_assets.append(STATIC / "fonts" / "stix-two-text" / filename)
                require(filename in font_css, f"Missing @font-face for {filename}")
    missing = [str(path.relative_to(ROOT)) for path in required_assets if not path.is_file()]
    require(not missing, "Missing local renderer assets: " + ", ".join(missing))

    print("Checked switchable MathJax 4 / KaTeX renderer and local STIX Two assets")


if __name__ == "__main__":
    main()

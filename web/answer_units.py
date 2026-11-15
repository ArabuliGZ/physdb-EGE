"""Canonical TeX formatting for labels printed after answer blanks."""
from __future__ import annotations

import re


INLINE_MATH = re.compile(r"^\\\(([\s\S]*)\\\)$")
TEXT_GROUP = re.compile(r"\\text\{[^{}]*\}")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
OPERATORS = re.compile(r"([/·⋅]|[²³])")
TEXT_SPECIAL = {"%": r"\%", "&": r"\&", "#": r"\#", "_": r"\_",
                "{": r"\{", "}": r"\}"}


def _text(value: str) -> str:
    escaped = "".join(TEXT_SPECIAL.get(char, char) for char in value)
    return r"\text{" + escaped + "}"


def has_cyrillic_outside_text(value: str) -> bool:
    match = INLINE_MATH.fullmatch(value.strip())
    if not match:
        return bool(CYRILLIC.search(value))
    return bool(CYRILLIC.search(TEXT_GROUP.sub("", match.group(1))))


def format_answer_unit_tex(value: str | None) -> str:
    """Return an idempotent inline-TeX label with Cyrillic only in ``\text``."""
    unit = (value or "").strip()
    if not unit:
        return ""
    if INLINE_MATH.fullmatch(unit):
        if has_cyrillic_outside_text(unit):
            raise ValueError(f"Cyrillic outside \\text in answer unit: {unit!r}")
        return unit
    if unit.startswith(r"\text{") and unit.endswith("}"):
        wrapped = r"\(" + unit + r"\)"
        if has_cyrillic_outside_text(wrapped):
            raise ValueError(f"Cyrillic outside \\text in answer unit: {unit!r}")
        return wrapped
    if "\\" in unit:
        raise ValueError(f"Answer unit TeX must be enclosed in \\( ... \\): {unit!r}")

    exact = {
        "%": r"\(\%\)",
        "°": r"\({}^\circ\)",
        "°C": r"\({}^\circ\text{C}\)",
        "°С": r"\({}^\circ\text{С}\)",
        "Дж/(кгК)": r"\(\text{Дж}/(\text{кг}\cdot\text{К})\)",
    }
    if unit in exact:
        return exact[unit]

    if not re.search(r"[/·⋅²³]", unit):
        return r"\(" + _text(unit) + r"\)"

    parts: list[str] = []
    for token in OPERATORS.split(unit):
        if not token:
            continue
        if token == "/":
            parts.append("/")
        elif token in ("·", "⋅"):
            parts.append(r"\cdot")
        elif token == "²":
            parts.append("^2")
        elif token == "³":
            parts.append("^3")
        else:
            parts.append(_text(token))
    return r"\(" + "".join(parts) + r"\)"

"""Conservative TeX formatting for visually transcribed physics prose.

Only text outside existing TeX delimiters is changed. This keeps curated
equations intact while putting quantities and bare numerals into math mode.
"""
from __future__ import annotations

import re

MATH = re.compile(r"(\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])")
UNIT = re.compile(
    r"(?:г/см\^?3|км/с|м/с\^?2|м/с²|м/с|Н/м|В/м|"
    r"мм\^?3|мм\^?2|см\^?3|см\^?2|м\^?3|м\^?2|мм²|см³|м²|м³|л/ч|Ом·м|"
    r"мкмоль|моль|мкФ|мГн|мДж|мкДж|мкс|кГц|кДж|кПа|дптр|нКл|мкКл|"
    r"мВб|мА|пН|кг|км|мм|см|Гц|Гн|Дж|Па|Тл|Ом|Вт|Вб|Н|В|Ф|А|Кл|"
    r"К|л|м|г|с|ч|%|°C|°С)"
)
NUMBER = re.compile(r"(?<![\w\\])\d+(?:[ \u00a0]\d{3})*(?:,\d+)?(?:[–−-]\d+)*(?!\w)")


def latex_unit(unit: str) -> str:
    def component(value: str) -> str:
        power = re.fullmatch(r"(.+?)\^?([23])", value)
        if power:
            return r"\text{" + power[1] + "}^{" + power[2] + "}"
        return r"\text{" + value + "}"

    if unit == "%":
        return r"\%"
    if unit == "Ом·м":
        return r"\text{Ом}\cdot\text{м}"
    if "/" in unit:
        numerator, denominator = unit.split("/", 1)
        return component(numerator) + "/" + component(denominator)
    return component(unit)


def format_quantities(text: str) -> str:
    """Wrap measured quantities and remaining numbers in inline TeX."""
    pieces = MATH.split(text)
    for index in range(0, len(pieces), 2):
        piece = pieces[index]
        matches = list(NUMBER.finditer(piece))
        for match in reversed(matches):
            start, end = match.span()
            if end < len(piece) and piece[end] == ")" and (start == 0 or piece[start - 1] == "\n"):
                continue  # Numbered-list marker.
            number = match.group().replace(",", "{,}").replace(" ", r"\,").replace("–", "-").replace("−", "-")
            suffix = piece[end:]
            unit = re.match(r"\s*(" + UNIT.pattern + r")(?![\w/])", suffix)
            if unit:
                end += unit.end()
                number += r"\," + latex_unit(unit.group(1))
            piece = piece[:start] + r"\(" + number + r"\)" + piece[end:]
        pieces[index] = piece
    result = "".join(pieces)
    # Curated statements often place a unit immediately after an existing
    # formula, e.g. \(F=48\) Н or \(10^{-6}\) с.
    result = re.sub(
        r"\\\(([^\n]*?)\\\)\s+(" + UNIT.pattern + r")(?![\w/])",
        lambda m: r"\(" + m.group(1) + r"\," + latex_unit(m.group(2)) + r"\)",
        result,
    )
    result = re.sub(r"\\\(([^\n]*?)\\\)\\\(\^([23])\\\)",
                    lambda m: r"\(" + m.group(1) + "^" + m.group(2) + r"\)", result)
    result = re.sub(r"([−-])\\\((\d[^\n]*?)\\\)",
                    lambda m: r"\(" + ("-" if m.group(1) == "−" else m.group(1)) + m.group(2) + r"\)", result)
    return result


def layout_criteria(text: str) -> str:
    """Keep score rows, Roman elements, and alternative cases on separate lines."""
    blocks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Word tables often concatenate their enumerated requirements.
        line = re.sub(r"(?<=[;:])\s*(?=(?:IV|III|II|I|V)\))", "\n", line)
        # The source uses ИЛИ as a separator, sometimes without any spaces.
        line = re.sub(r"([.)])\s*(?=(?:И\s*\(ИЛИ\)|ИЛИ)(?:\s|[А-ЯЁ]))", r"\1\n", line)
        line = re.sub(r"(?<=\S)\s+(?=(?:И\s*\(ИЛИ\)|ИЛИ)\s+[А-ЯЁ])", "\n", line)
        line = re.sub(r"(И\s*\(ИЛИ\)|ИЛИ)\s*(?=[А-ЯЁ])", r"\1 ", line)
        blocks.append(line)
    return "\n\n".join(blocks)

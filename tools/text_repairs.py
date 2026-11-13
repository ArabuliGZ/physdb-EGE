"""Source-backed repairs for Word superscripts lost by flat OOXML extraction.

Each entry is tied to a printed task and source paragraph. Keep these repairs in
the import path so rebuilding SQLite cannot restore the broken notation.
"""
from __future__ import annotations

from tex_format import format_indexed_symbols


REPAIRS: dict[tuple[str, int, str], tuple[tuple[str, str], ...]] = {
    ("2024-1-1", 3, "statement"): (
        (r"\(103\,\text{кг}\)", r"\(10^3\,\text{кг}\)"),  # normalized DOCX ¶73
    ),
    ("2024-1-1", 22, "statement"): (
        (r"\(4\)·\(10-4\,\text{м}^{3}\)", r"\(4\cdot10^{-4}\,\text{м}^3\)"),  # ¶347
    ),
    ("2024-1-2", 11, "statement"): (
        (r"\(210-8\,\text{Кл}\)", r"\(2\cdot10^{-8}\,\text{Кл}\)"),  # ¶181
    ),
    ("2024-1-2", 12, "statement"): (
        ("q1 = 2q и q2 = 3q", r"\(q_1=2q\) и \(q_2=3q\)"),  # ¶192
    ),
    ("2024-1-2", 25, "statement"): (
        (r"\(5{,}4410-18\,\text{Кл}\)", r"\(5{,}44\cdot10^{-18}\,\text{Кл}\)"),  # ¶396
        (r"\(210-18\,\text{м}^{3}\)", r"\(2\cdot10^{-18}\,\text{м}^3\)"),
    ),
    ("2024-2-4", 23, "statement"): (
        (r"\(16{,}7\).\(10-27\,\text{кг}\)", r"\(16{,}7\cdot10^{-27}\,\text{кг}\)"),  # DOCX ¶412
        (r"\(3{,}2\).\(10-19\,\text{Кл}\)", r"\(3{,}2\cdot10^{-19}\,\text{Кл}\)"),
        (r"\(4\).\(10-20\) W=\(100\,\text{Дж}\)", r"\(4\cdot10^{-20}\,\text{Дж}\)"),
    ),
    ("2024-2-4", 24, "solution"): (
        (r"p0 = \(105\,\text{Па}\)", r"\(p_0=10^5\,\text{Па}\)"),  # same solution later uses 10^5
    ),
    ("2025-1-2", 12, "statement"): (
        (r"\(10-3\,\text{м}^{2}\)", r"\(10^{-3}\,\text{м}^2\)"),  # normalized DOCX ¶206
    ),
    ("2025-1-2", 16, "statement"): (
        (r"\(81020\) ядер", r"\(8\cdot10^{20}\) ядер"),  # OOXML superscript in task 16
    ),
    ("2025-2-2", 12, "statement"): (
        (r"\(10-3\,\text{м}^{2}\)", r"\(10^{-3}\,\text{м}^2\)"),  # normalized DOCX ¶206
    ),
    ("2025-2-2", 16, "statement"): (
        (r"\(81020\) ядер", r"\(8\cdot10^{20}\) ядер"),  # OOXML superscript in task 16
    ),
    ("2025-1-2", 23, "statement"): (
        (r"\(8\)∙\(10-7\,\text{м}\)", r"\(8\cdot10^{-7}\,\text{м}\)"),  # ¶372
        (r"\(4\)∙\(10-7\,\text{м}\)", r"\(4\cdot10^{-7}\,\text{м}\)"),
    ),
    ("2025-2-2", 23, "statement"): (
        (r"\(8\)∙\(10-7\,\text{м}\)", r"\(8\cdot10^{-7}\,\text{м}\)"),  # ¶372
        (r"\(4\)∙\(10-7\,\text{м}\)", r"\(4\cdot10^{-7}\,\text{м}\)"),
    ),
    ("2026-4", 23, "statement"): (
        ("q1  = –\\(2{,}5\\,\\text{нКл}\\) и q2 = \\(2{,}5\\,\\text{нКл}\\)",
         r"\(q_1=-2{,}5\,\text{нКл}\) и \(q_2=2{,}5\,\text{нКл}\)"),  # DOCX ¶511
    ),
}

RECONSTRUCTED_SOLUTION_2024_2_4_23 = (
    "Сила Лоренца сообщает иону центростремительное ускорение: "
    r"\(|q|vB=mv^2/R\). Кинетическая энергия равна \(W=mv^2/2\). "
    "Исключая скорость, получаем\n\n"
    r"\[R=\frac{\sqrt{2mW}}{|q|B}="
    r"\frac{\sqrt{2\cdot16{,}7\cdot10^{-27}\cdot4\cdot10^{-20}}}"
    r"{3{,}2\cdot10^{-19}\cdot0{,}1}\approx1{,}14\,\text{мм}.\]"
    "\n\nОтвет: " + r"\(1{,}14\,\text{мм}\)."
)
RECONSTRUCTED_SOLUTION_2026_3_22 = (
    "Для первого груза запишем второй закон Ньютона вдоль движения: "
    r"\(m_1a=F-T-\mu m_1g\). "
    "Для второго груза, движущегося вверх: "
    r"\(m_2a=T-m_2g\). Исключая натяжение нити, получаем\n\n"
    r"\[m_2=\frac{F-m_1(a+\mu g)}{g+a}="
    r"\frac{10-1(2+0{,}2\cdot10)}{10+2}=0{,}5\,\text{кг}.\]"
    "\n\nОтвет: " + r"\(0{,}5\,\text{кг}\)."
)


def repair_text(label: str, number: int, field: str, text: str | None) -> str | None:
    if text is None:
        return None
    if (label, number, field) == ("2024-2-4", 23, "solution"):
        if "Fл=maц" in text:
            text = RECONSTRUCTED_SOLUTION_2024_2_4_23
        elif text != RECONSTRUCTED_SOLUTION_2024_2_4_23:
            raise ValueError("Unexpected source solution for 2024-2-4 task 23")
    if (label, number, field) == ("2026-3", 22, "solution"):
        if "Грузы связаны нерастяжимой" in text:
            text = RECONSTRUCTED_SOLUTION_2026_3_22
        elif text != RECONSTRUCTED_SOLUTION_2026_3_22:
            raise ValueError("Unexpected source solution for 2026-3 task 22")
    for old, new in REPAIRS.get((label, number, field), ()):
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text:
            raise ValueError(f"Source-backed repair no longer matches {label} task {number} {field}: {old}")
    return format_indexed_symbols(text)

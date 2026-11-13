"""Source-backed repairs for Word superscripts lost by flat OOXML extraction.

Each entry is tied to a printed task and source paragraph. Keep these repairs in
the import path so rebuilding SQLite cannot restore the broken notation.
"""
from __future__ import annotations

from tex_format import format_indexed_symbols


REPAIRS: dict[tuple[str, int, str], tuple[tuple[str, str], ...]] = {
    ("2023-1", 17, "statement"): (
        ("Частота световой волны – ; скорость света в воздухе – с;",
         r"Частота световой волны – \(\nu\); скорость света в воздухе – \(c\);"),  # source PDF p. 10
    ),
    ("2023-2", 1, "statement"): (
        ("скоростью  по окружности радиусом R",
         r"скоростью \(\upsilon\) по окружности радиусом \(R\)"),  # PDF p. 4
    ),
    ("2023-2", 9, "statement"): (
        ("Газв этом процессе", "Газ в этом процессе"),  # PDF p. 7
    ),
    ("2023-2", 24, "statement"): (
        ("Сделайте рисунокс указанием", "Сделайте рисунок с указанием"),  # PDF p. 14
    ),
    ("2023-2", 29, "statement"): (
        ("Авых = \\(1{,}89\\) эВ", r"\(A_{\text{вых}}=1{,}89\,\text{эВ}\)"),  # PDF p. 15
    ),
    ("2023-3", 6, "statement"): (
        ("А)модуль работы силы трения, действующей на автобусБ)время, необходимое для полной остановки автобуса &  &  ",
         "А) модуль работы силы трения, действующей на автобус &  &  "
         + r"\\" + "\n"
         + "Б) время, необходимое для полной остановки автобуса &  &  "),  # PDF p. 6
    ),
    ("2023-3", 7, "statement"): (
        ("при температуре 3T0 и давлении 3p0", r"при температуре \(3T_0\) и давлении \(3p_0\)"),
        (r"объём \(1\),5V0 при температуре 2T0 и давлении \(p_{0}\)",
         r"объём \(1{,}5V_0\) при температуре \(2T_0\) и давлении \(p_0\)"),  # PDF p. 6
    ),
    ("2023-3", 13, "statement"): (
        (r"со скоростями \(1\) = \(6\) и \(2\) = \(3\) соответственно",
         r"со скоростями \(\upsilon_1=6\upsilon\) и \(\upsilon_2=3\upsilon\) соответственно"),  # PDF p. 8
    ),
    ("2023-3", 18, "statement"): (
        (r"\(N = N_{0} \cdot 2^{- \lambda t} ,\) где  = \(0{,}05\,\text{с}\)–\(1\)",
         r"\(N=N_0\cdot2^{-\lambda t}\), где \(\lambda=0{,}05\,\text{с}^{-1}\)"),  # PDF p. 10
    ),
    ("2023-3", 21, "statement"): (
        ("пружинного маятника массой груза m от жёсткостью пружины",
         r"пружинного маятника при массе груза \(m\) от жёсткости пружины"),  # source typo, PDF p. 12
        ("площадью поперечного сечения  S|", r"площадью поперечного сечения \(S\)"),
    ),
    ("2023-1", 15, "statement"): (
        (r"t, \(10-6\) c", r"\(t,\ 10^{-6}\,\text{с}\)"),  # original PDF p. 9
        (r"q, \(10-9\,\text{Кл}\)", r"\(q,\ 10^{-9}\,\text{Кл}\)"),
        (r"\(1610-6\,\text{с}\)", r"\(16\cdot10^{-6}\,\text{с}\)"),
        (r"\(810-6\,\text{с}\)", r"\(8\cdot10^{-6}\,\text{с}\)"),
        (r"\(1210-6\,\text{с}\)", r"\(12\cdot10^{-6}\,\text{с}\)"),
        (r"\(410-6\,\text{с}\)", r"\(4\cdot10^{-6}\,\text{с}\)"),
    ),
    ("2023-2", 7, "statement"): (
        (r"р, \(105\,\text{Па}\)", r"\(p,\ 10^5\,\text{Па}\)"),  # original PDF p. 6
        (r"V, \(10-3\,\text{м}^{3}\)", r"\(V,\ 10^{-3}\,\text{м}^3\)"),
    ),
    ("2023-2", 26, "statement"): (
        (r"\(5{,}4410-18\,\text{Кл}\)", r"\(5{,}44\cdot10^{-18}\,\text{Кл}\)"),  # original PDF p. 15
        (r"\(210-18\,\text{м}^{3}\)", r"\(2\cdot10^{-18}\,\text{м}^3\)"),
    ),
    ("2023-2", 27, "statement"): (
        ("kp0p0LSkp0p0LS\n", ""),  # stray labels of its diagram, PDF p. 15
    ),
    ("2023-3", 26, "statement"): (
        ("sinφ  tgφ.\nhHРис. \\(1\\)                      Рис. 2p0p0p0M, S  hHРис. \\(1\\)                      Рис. 2p0p0p0M, S",
         r"\(\sin\varphi\approx\tan\varphi\)."),  # original PDF p. 14
    ),
    ("2023-3", 29, "statement"): (
        (r"с длиной волны  = \(1{,}1\)·\(10-10\,\text{м}\)",
         r"с длиной волны \(\lambda=1{,}1\cdot10^{-10}\,\text{м}\)"),  # PDF p. 15
        (r"Р = \(1{,}26\)·\(10-6\,\text{Па}\)",
         r"\(P=1{,}26\cdot10^{-6}\,\text{Па}\)"),
        ("фотоныв пучке", "фотоны в пучке"),
    ),
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
RECONSTRUCTED_SOLUTION_2023_3_25 = (
    "Максимальная потенциальная энергия пружины равна максимальной "
    "кинетической энергии тележки:\n\n"
    r"\[\frac{kA^2}{2}=\frac{mv_{\max}^2}{2},\qquad "
    r"v_{\max}=A\sqrt{\frac{k}{m}}="
    r"0{,}1\sqrt{\frac{200}{2}}=1\,\text{м}/\text{с}.\]"
    "\n\nОтвет: " + r"\(1\,\text{м}/\text{с}\)."
)
RECONSTRUCTED_SOLUTION_2023_3_26 = (
    r"Для главного максимума порядка \(k\) при нормальном падении "
    r"света на решётку периода \(d\): "
    r"\(d\sin\varphi=k\lambda\). При малых углах "
    r"\(\sin\varphi\approx\tan\varphi=x/F\), где \(F\) — фокусное "
    r"расстояние линзы, \(x\) — расстояние от нулевого максимума. "
    "Следовательно, "
    r"\(x_2-x_1=\lambda F(k_2-k_1)/d\). Подставляем данные:\n\n"
    r"\[\lambda=\frac{d(x_2-x_1)}{F(k_2-k_1)}="
    r"\frac{5\cdot10^{-6}\cdot18\cdot10^{-3}}{0{,}2\cdot(2-1)}="
    r"450\,\text{нм}.\]"
    "\n\nОтвет: " + r"\(450\,\text{нм}\)."
)
RECONSTRUCTED_SOLUTION_2023_2_30 = (
    "Обоснование. Выбираем инерциальную систему отсчёта, связанную с Землёй. "
    "Стержень с шарами рассматриваем как твёрдое тело в равновесии. "
    "Сумма внешних сил и сумма их моментов равны нулю. "
    r"На систему действуют силы тяжести \(m_1g\) и \(m_2g\), а также "
    r"реакции опор \(N_1\) и \(N_2\). По условию и третьему закону Ньютона "
    r"\(N_2=2N_1\)." "\n\n"
    r"Решение. Пусть \(x=AC=0{,}2\,\text{м}\), расстояние между опорами "
    r"\(l=0{,}6\,\text{м}\). Равновесие сил по вертикали и моментов "
    r"относительно точки \(A\) даёт" "\n\n"
    r"\[N_1+N_2-m_1g-m_2g=0,\qquad "
    r"N_1x+N_2(l+x)-m_2gL=0.\]"
    "\n" r"С учётом \(N_2=2N_1\):" "\n\n"
    r"\[3N_1=(m_1+m_2)g,\qquad (3x+2l)N_1=m_2gL.\]"
    "\n" r"Исключая \(N_1\), получаем" "\n\n"
    r"\[L=\left(1+\frac{m_1}{m_2}\right)\left(x+\frac{2l}{3}\right)="
    r"\left(1+\frac{0{,}2}{0{,}3}\right)"
    r"\left(0{,}2+\frac{2\cdot0{,}6}{3}\right)=1\,\text{м}.\]"
    "\n\nОтвет: " + r"\(1\,\text{м}\)."
)


def repair_text(label: str, number: int, field: str, text: str | None) -> str | None:
    if text is None:
        return None
    if (label, number, field) == ("2023-3", 25, "solution"):
        if "В случае гармонических колебаний" in text:
            text = RECONSTRUCTED_SOLUTION_2023_3_25
        elif text != RECONSTRUCTED_SOLUTION_2023_3_25:
            raise ValueError("Unexpected 2023-3 task 25 solution")
    if (label, number, field) == ("2023-3", 26, "solution"):
        if "В соответствии с условием наблюдения" in text:
            text = RECONSTRUCTED_SOLUTION_2023_3_26
        elif text != RECONSTRUCTED_SOLUTION_2023_3_26:
            raise ValueError("Unexpected 2023-3 task 26 solution")
    if (label, number, field) == ("2023-2", 30, "solution"):
        if "Выберем систему отсчёта" in text:
            text = RECONSTRUCTED_SOLUTION_2023_2_30
        elif text != RECONSTRUCTED_SOLUTION_2023_2_30:
            raise ValueError("Unexpected 2023-2 task 30 solution")
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

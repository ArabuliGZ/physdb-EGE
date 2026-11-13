"""Answers checked against the author solutions in the three 2023 DOCX/PDFs.

The printed key covers only tasks 1–23. These concise results are taken from
the worked solutions and keep task 24's qualitative or graphical form.
"""

EXTENDED_ANSWERS: dict[tuple[int, int], str] = {
    (1, 24): ("При зелёном свете начало графика сдвигается влево, "
              "а ток насыщения уменьшается."),
    (1, 25): r"\(200\,\text{с}\)",
    (1, 26): r"\(1\,\text{м}\)",
    (1, 27): r"\(3886\,\text{Дж}\)",
    (1, 28): r"\(2\,\text{м}/\text{с}\)",
    (1, 29): r"\(0{,}5\,\text{Тл}\)",
    (1, 30): r"\(0{,}9\,\text{Н}\)",
    (2, 24): (r"\(N(F)=4\,\text{Н}-F\) при \(0\leq F\leq4\,\text{Н}\); "
              r"\(N=0\) при \(4\leq F\leq10\,\text{Н}\)."),
    (2, 25): r"\(0{,}05\,\text{кг}\)",
    (2, 26): r"\(1\,\text{кВ}\)",
    (2, 27): r"\(k=\dfrac{2Q-5p_0Sb}{3bL+4b^2}\)",
    (2, 28): r"\(4\,\text{м}/\text{с}\)",
    (2, 29): r"\(6{,}7\cdot10^{14}\,\text{Гц}\)",
    (2, 30): r"\(1\,\text{м}\)",
    (3, 24): "Результирующая сила на проводник 1 направлена вертикально вниз.",
    (3, 25): r"\(1\,\text{м}/\text{с}\)",
    (3, 26): r"\(450\,\text{нм}\)",
    (3, 27): r"\(Q=\dfrac32Mgh+\dfrac52(Mg+p_0S)(H-h)\)",
    (3, 28): r"\(1{,}6\,\text{мкФ}\)",
    (3, 29): r"\(5\cdot10^8\,\text{м}^{-3}\)",
    (3, 30): r"\(4\cdot10^{-3}\,\text{Н}\)",
}

assert set(EXTENDED_ANSWERS) == {(variant, task)
                                 for variant in (1, 2, 3)
                                 for task in range(24, 31)}

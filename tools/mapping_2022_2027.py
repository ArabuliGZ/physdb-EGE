"""Candidate 2027 positions for the four 30-task Demidova 2022 papers.

The 2022-to-2023 line permutation is a starting point. Each exception below
uses the actual task topic, response type, and score in the 2027 approved plan.
"""
from __future__ import annotations


TARGET = {
    1: 18, 2: 18, 3: 1, 4: 2, 5: 4, 6: 5, 7: 6, 8: 6,
    9: 7, 10: 7, 11: 8, 12: 9, 13: 10, 14: 11, 15: 12,
    16: 13, 17: 14, 18: 15, 19: 15, 20: 16, 21: 17,
    22: 19, 23: 20, 24: 21, 25: 22, 26: 23, 27: 24,
    28: 25, 29: 25, 30: 26,
}

from mapping_2023_2027 import SOURCE_FORMAT as NEW_FORMAT, SOURCE_POINTS as NEW_POINTS


def moved(number: int) -> int:
    """Source 2022 line to the equivalent 2023 format line."""
    return 20 if number == 1 else 21 if number == 2 else number - 2 if number <= 21 else number


SOURCE_POINTS = {number: NEW_POINTS[moved(number)] for number in range(1, 31)}
SOURCE_FORMAT = {number: NEW_FORMAT[moved(number)] for number in range(1, 31)}


def source_points(variant: int, number: int) -> int:
    # The author rubric for 2022 B4 task 26 gives 3 points, unlike B1–B3.
    return 3 if (variant, number) == (4, 26) else SOURCE_POINTS[number]

SOURCE_TOPIC = {
    **{n: "mechanics" for n in range(3, 9)},
    **{n: "molecular" for n in range(9, 14)},
    **{n: "electrodynamics" for n in range(14, 20)},
    **{n: "quantum" for n in (20, 21, 26, 29)},
    **{n: "cross_topic" for n in (1, 2, 22, 23)},
    24: "electrodynamics", 25: "mechanics", 27: "molecular",
    28: "electrodynamics", 30: "mechanics",
}


def assessment(variant: int, number: int) -> tuple[int, str, int, int, str]:
    target = TARGET[number]
    if number == 3 and variant in (3, 4):
        target = 2
    if number == 4 and variant in (2, 3, 4):
        target = 3
    if number == 10 and variant == 3:
        target = 8
    if number == 2:
        return target, "no", 1, 0, (
            "Общекурсовое соответствие трёх зависимостей графикам не совпадает "
            "с форматом множественного выбора позиции 18 спецификации 2027.")
    if number == 9 and variant != 3:
        return target, "no", 0, 1, (
            "Числовая задача об уравнении состояния газа не проверяет связь "
            "температуры со средней кинетической энергией, заданную для позиции 7.")
    if number == 10 and variant != 3:
        return target, "no", 0, 1, (
            "Числовая задача о влажности либо газовом законе не соответствует "
            "узкой теме позиции 7 и тепловой теме позиции 8 спецификации 2027.")
    if number == 18 and variant == 2:
        return target, "partial", 1, 1, (
            "Соответствие по преломлению света совпадает по формату и баллам, "
            "но оптика не выделена среди элементов позиции 15 спецификации 2027.")
    if number == 25 and variant in (3, 4):
        return target, "partial", 1, 1, (
            "Механическая задача с развёрнутым решением на 2 балла совпадает "
            "по теме и формату с позицией 22, но не имеет практического сюжета.")
    if number == 26:
        return target, "no", 0, 1, (
            f"Задача с развёрнутым решением на {source_points(variant, number)} балла "
            "относится к фотоэффекту или фотонам; позиции 22–23 спецификации 2027 "
            "отведены механике и молекулярной физике.")
    if number == 29:
        return target, "no", 0, 1, (
            "Высокоуровневая расчётная задача по геометрической оптике не входит "
            "в перечень содержания позиции 25 спецификации 2027.")
    if number == 30:
        return target, "yes", 1, 1, (
            "Механическая задача на 4 балла с отдельным обоснованием модели "
            "соответствует позиции 26 спецификации 2027 при сохранении двух критериев.")
    return target, "yes", 1, 1, (
        f"Исходная позиция 2022 №{number}: тема {SOURCE_TOPIC[number]}, "
        f"формат {SOURCE_FORMAT[number]}, {SOURCE_POINTS[number]} балл(а); "
        f"соответствует позиции {target} спецификации 2027.")


assert set(TARGET) == set(SOURCE_POINTS) == set(SOURCE_FORMAT) == set(SOURCE_TOPIC) == set(range(1, 31))
assert sum(SOURCE_POINTS.values()) == 54

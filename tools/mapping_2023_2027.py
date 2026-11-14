"""Source lines of the 30-task 2023 paper versus the 26-task FIPI 2027 approved specification.

This is a candidate-position table, not a claim that source numbers are 2027
numbers. Topic, response type and source score are checked again per problem.
"""
from __future__ import annotations


TARGET = {
    1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 6,
    7: 7, 8: 8, 9: 8, 10: 9, 11: 10,
    12: 11, 13: 12, 14: 13, 15: 14, 16: 15, 17: 15,
    18: 16, 19: 17, 20: 18, 21: 18, 22: 19, 23: 20,
    24: 21, 25: 22, 26: 25, 27: 24, 28: 25, 29: 25, 30: 26,
}

SOURCE_POINTS = {n: 1 for n in (1, 2, 3, 7, 8, 9, 12, 13, 14, 18, 22, 23)}
SOURCE_POINTS.update({n: 2 for n in (4, 5, 6, 10, 11, 15, 16, 17, 19, 20, 21, 25, 26)})
SOURCE_POINTS.update({24: 3, 27: 3, 28: 3, 29: 3, 30: 4})

SOURCE_FORMAT = {n: "number" for n in (1, 2, 3, 7, 8, 9, 12, 13, 14, 18)}
SOURCE_FORMAT.update({n: "multiple_choice" for n in (4, 10, 15, 20, 23)})
SOURCE_FORMAT.update({n: "matching" for n in (5, 6, 11, 16, 17, 19, 21)})
SOURCE_FORMAT.update({22: "number_pair", 24: "qualitative"})
SOURCE_FORMAT.update({n: "worked_solution" for n in range(25, 31)})

SOURCE_TOPIC = {n: "mechanics" for n in range(1, 7)}
SOURCE_TOPIC.update({n: "molecular" for n in range(7, 12)})
SOURCE_TOPIC.update({n: "electrodynamics" for n in range(12, 18)})
SOURCE_TOPIC.update({18: "quantum", 19: "quantum"})
SOURCE_TOPIC.update({n: "cross_topic" for n in range(20, 24)})
SOURCE_TOPIC.update({27: "molecular", 28: "electrodynamics", 29: "quantum", 30: "mechanics"})
EXTENDED_TOPIC = {
    1: {24: "quantum", 25: "mechanics", 26: "electrodynamics"},
    2: {24: "mechanics", 25: "molecular", 26: "electrodynamics"},
    3: {24: "electrodynamics", 25: "mechanics", 26: "electrodynamics"},
}


def assessment(variant: int, number: int) -> tuple[int, str, int, int, str]:
    """Return target, verdict, topic match, format match, source-specific reason."""
    target = TARGET[number]
    topic = EXTENDED_TOPIC[variant].get(number, SOURCE_TOPIC.get(number, ""))
    kind = SOURCE_FORMAT[number]
    points = SOURCE_POINTS[number]
    if number == 25 and variant == 2:
        target = 23  # Calorimetry, not mechanics.
    if number == 7:
        return target, "no", 0, 1, (
            "Задача 2023 года требует уравнения состояния или изопроцесса; "
            "числовая позиция 7 спецификации 2027 проверяет связь температуры газа "
            "со средней кинетической энергией молекул.")
    if number == 8 and variant in (1, 3):
        target = 7
        return target, "no", 0, 1, (
            "Числовая задача о влажности или насыщенном водяном паре не входит "
            "в узкую тему позиции 7 спецификации 2027; позиция 8 отведена теплоте "
            "и первому закону термодинамики.")
    if number == 18 and variant == 2:
        target = 17
        return target, "no", 1, 0, (
            "Вычисление импульса фотона относится к теме квантовой позиции 17, "
            "но требует числового ответа вместо соответствия с ответом из цифр.")
    if (number == 17 and variant == 1) or (number == 16 and variant == 3):
        return target, "partial", 1, 1, (
            "Соответствие по свойствам световой волны имеет нужные формат и баллы, "
            "но оптическое преломление не указано отдельно среди элементов "
            "содержания позиции 15 спецификации 2027.")
    if number == 21:
        return target, "no", 1, 0, (
            "Источник: соответствие трёх зависимостей графикам; позиция 18 спецификации 2027 "
            "требует множественный выбор, поэтому формат не совпадает.")
    if number == 24 and variant != 3:
        topic_name = {"quantum": "квантовой физике", "mechanics": "механике"}[topic]
        return target, "no", 0, 1, (
            f"Качественная задача на 3 балла по {topic_name}; позиция 21 спецификации 2027 "
            "отведена электродинамике.")
    if number == 26:
        if variant == 2:
            return target, "partial", 1, 1, (
                "Расчётная задача по электростатике соответствует теме и развёрнутому "
                "формату позиции 25 спецификации 2027, но в источнике оценивалась в 2 балла "
                "вместо 3; для полного соответствия нужна другая шкала оценивания.")
        return target, "no", 0, 1, (
            "Расчётная задача по оптике оценивалась в 2 балла; позиция 25 "
            "спецификации 2027 посвящена электрическому и магнитному полям, постоянному "
            "току, электромагнитной индукции и колебаниям и оценивается в 3 балла.")
    if number == 29:
        return target, "no", 0, 1, (
            "Задача высокого уровня по квантовой физике; позиция 25 спецификации 2027 "
            "отведена электродинамике.")
    if number == 30:
        return target, "yes", 1, 1, (
            "Механика, расчёт на 4 балла; в авторских критериях есть отдельные "
            "критерии обоснования модели и решения, как в позиции 26 спецификации 2027.")
    if number == 24:
        return target, "yes", 1, 1, (
            "Качественное объяснение по электродинамике на 3 балла соответствует "
            "позиции 21 спецификации 2027.")
    if number == 25:
        return target, "yes", 1, 1, (
            "Расчётная задача на 2 балла по " +
            ("молекулярной физике соответствует позиции 23" if variant == 2 else
             "механике с прикладным сюжетом соответствует позиции 22") + " спецификации 2027.")
    if number in (27, 28):
        return target, "yes", 1, 1, (
            f"Расчётная задача высокого уровня: {topic}, {points} балла; "
            f"соответствует позиции {target} спецификации 2027.")
    return target, "yes", 1, 1, (
        f"Исходная позиция 2023 №{number}: {topic}, формат {kind}, "
        f"{points} балл(а); соответствует позиции {target} спецификации 2027.")


assert set(TARGET) == set(SOURCE_POINTS) == set(SOURCE_FORMAT) == set(range(1, 31))

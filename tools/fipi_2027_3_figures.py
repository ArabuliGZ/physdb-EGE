"""Figure crops for scanned book variant 3, in PDFium pixels at scale 2.1.

Boxes are fixed against the whole-book SHA.  They exclude answer blanks and
question prose.  Task 14 has two independent condition figures; task 20 has
no figures, only five textual equipment choices.
"""

from fipi_2027_1_figures import SOURCE_SHA256, RENDER_SCALE

STATEMENT_FIGURES = {
    1: [(29, (355, 640, 955, 890))],
    5: [(30, (890, 195, 1180, 425))],
    9: [(31, (435, 375, 900, 615))],
    10: [(31, (925, 875, 1165, 1095))],
    11: [(31, (935, 1410, 1125, 1605))],
    12: [(32, (875, 190, 1180, 400))],
    13: [(32, (965, 535, 1180, 775))],
    14: [(32, (840, 875, 1180, 1090)),
         (32, (800, 1120, 1185, 1420))],
    17: [(33, (930, 985, 1165, 1260))],
    19: [(34, (275, 680, 1095, 925))],
    21: [(35, (410, 560, 905, 740))],
    22: [(35, (795, 910, 1170, 1085))],
    25: [(35, (815, 1300, 1180, 1580))],
    26: [(36, (915, 180, 1190, 500))],
}
SOLUTION_FIGURES = {
    21: [(253, (245, 335, 605, 505)),
         (253, (680, 345, 1045, 505))],
    25: [(255, (950, 235, 1165, 445))],
    26: [(255, (945, 1150, 1175, 1455))],
}

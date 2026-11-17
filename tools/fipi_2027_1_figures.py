"""Source-page figure crops for book variant 1, at PDFium scale 2.1.

Each box is (left, top, right, bottom) in pixels.  Crops are fixed against
the SHA-256 of the scanned source; no whole-question screenshots are attached.
"""

SOURCE_SHA256 = "c51ed501ca80886b44b895d522060664a26fdf7ebeb4c5b3d4dfa2e4619173cf"
RENDER_SCALE = 2.1

# Inserted in printed reading order.  Task 6 has one condition graph followed
# by answer graphs А/Б.  Task 20 has choices 1–5, not one composite picture.
STATEMENT_FIGURES = {
    1: [(13, (450, 595, 970, 780))],
    6: [(14, (925, 610, 1170, 795)),
        (14, (220, 955, 455, 1135)),
        (14, (220, 1140, 455, 1295))],
    9: [(15, (775, 300, 1180, 625))],
    13: [(16, (500, 325, 850, 515))],
    14: [(16, (295, 925, 620, 1115)),
         (16, (675, 855, 1055, 1210))],
    20: [(18, (215, 660, 395, 815)),
         (18, (215, 830, 395, 990)),
         (18, (215, 1000, 395, 1165)),
         (18, (700, 660, 880, 815)),
         (18, (700, 830, 880, 990))],
    21: [(19, (905, 380, 1150, 555))],
    24: [(19, (950, 1010, 1160, 1200))],
    25: [(19, (920, 1290, 1170, 1500))],
}

SOLUTION_FIGURES = {
    21: [(240, (865, 480, 1165, 665))],
    24: [(243, (910, 1275, 1175, 1460)),
         (244, (900, 195, 1165, 370))],
    25: [(245, (920, 1255, 1170, 1500)),
         (246, (920, 190, 1180, 390))],
}

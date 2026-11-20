"""Scenes of the example story "El farero" (fiction, 3 shots). Each @cena draws one whole frame.

Image rules the kit follows: something moves from frame 0, 3–5 parallax layers, far layers lighter,
dark blurred foreground, rim light on silhouettes, text only between y=150 and y=1500.
Replace these functions with your own shots (same ids as in historia.json).
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter

from silueta_studio import (R, addglow, ave, barco, card, cena, disco, fg, fin, full, haze, pessoa, push, sky, terr)

INK = (8, 8, 12)
RIM = (255, 176, 96)


def faro(f, C, x, y, s=1.0, luz=1.0, t=0.0, beam=True):
    """Original lighthouse drawn in code; base at world (x, y). Returns the lamp position on screen."""
    X, Y, zl = C.ts(x, y, 1.0); s *= zl
    r = R(f, X - 140 * s, Y - 640 * s, X + 140 * s, Y + 30 * s)
    m = r.poly([(X - 70 * s, Y + 20 * s), (X + 70 * s, Y + 20 * s), (X + 40 * s, Y - 470 * s), (X - 40 * s, Y - 470 * s)], INK)
    r.poly([(X - 62 * s, Y - 470 * s), (X + 62 * s, Y - 470 * s), (X + 62 * s, Y - 488 * s), (X - 62 * s, Y - 488 * s)], INK)
    r.poly([(X - 34 * s, Y - 488 * s), (X + 34 * s, Y - 488 * s), (X + 34 * s, Y - 560 * s), (X - 34 * s, Y - 560 * s)], INK)
    r.poly([(X - 46 * s, Y - 560 * s), (X + 46 * s, Y - 560 * s), (X, Y - 610 * s)], INK)
    if r.ok: r.rim(m, RIM, 1.1, 5)
    lx, ly = X, Y - 524 * s
    if luz > 0:
        if beam:
            a = t * 1.1; L = 1500; w = 0.11
            p1 = (lx + L * math.cos(a - w), ly + L * 0.35 * math.sin(a - w)); p2 = (lx + L * math.cos(a + w), ly + L * 0.35 * math.sin(a + w))
            fr = full(f); bm = fr._m(lambda d: d.polygon(fr.P([(lx, ly), p1, p2]), fill=255))
            yy, xx = np.ogrid[0:bm.shape[0], 0:bm.shape[1]]
            bm = gaussian_filter(bm, 6) * np.exp(-np.hypot(xx - lx, yy - ly) / 700)   # soft beam that fades with distance
            fr.add(bm,(255, 226, 160), 0.28 * luz * (0.55 + 0.45 * abs(math.cos(a))))
        addglow(f, lx, ly, 26 * s, (255, 236, 180), 1.6 * luz)
        addglow(f, lx, ly, 90 * s, (255, 200, 120), 0.35 * luz)
    return lx, ly


def mar(f, C, y, col, brilho=None, t=0.0):
    yr = terr(f, C, 0.6, 21, y, 4, col, freq=5)
    if brilho:
        for i in range(14):
            x = 540 + (i - 7) * 70 + 20 * math.sin(t * 1.3 + i)
            addglow(f, x, y + 18 + (i % 3) * 14, 8, brilho, 0.5 + 0.3 * math.sin(t * 3 + i * 1.7))
    return yr


def estrelas(f, t, n=70, seed=4):
    rr = np.random.default_rng(seed)
    for _ in range(n):
        x, y, ph = rr.uniform(0, 1080), rr.uniform(160, 1000), rr.uniform(0, 6.3)
        addglow(f, x, y, rr.uniform(1.2, 2.6), (220, 230, 255), 0.9 + 0.5 * math.sin(t * 2.2 + ph))


@cena("S01", cap=1290, subj=[(200, 700, 400, 1180)], prova=0.55, escala="plano geral")
def s01(f, tl, d, c):
    C = push(tl, 0.07, 0.5, pan=6)
    sky(f, "poente", [(0, (40, 30, 60)), (0.45, (214, 110, 70)), (0.62, (255, 190, 120)), (1, (30, 20, 30))])
    disco(f, *C.ts(720, 930, 0.2)[:2], 70)
    terr(f, C, 0.3, 3, 1060, 60, (120, 70, 80))
    mar(f, C, 1120, (70, 40, 60), brilho=(255, 200, 130), t=tl)
    yc = terr(f, C, 0.9, 7, 1260, 50, (14, 10, 16), peak=(300, 120, 260))
    faro(f, C, 300, yc(300) + 10, 1.0, luz=0.4 + 0.6 * min(1, tl / 2.0), t=tl + 2.0)
    for i in range(3):
        ave(f, 620 + tl * 60 + i * 60, 600 + 20 * math.sin(tl * 0.9 + i), 1.0 + 0.2 * i, tl * 9 + i)
    fg(f, C, 11, y=1660, blades=10)
    fin(f)
    card(f, "40 AÑOS", (540, 340), 120, tl, c["tw"]("cuarenta", 0.4))


@cena("S02", cap=1290, subj=[(420, 600, 660, 1180)], prova=0.6, escala="plano médio")
def s02(f, tl, d, c):
    C = push(tl, 0.05, 0.6, pan=-5)
    sky(f, "noite", [(0, (6, 8, 22)), (0.6, (20, 30, 60)), (1, (6, 6, 12))])
    estrelas(f, tl)
    mar(f, C, 1150, (12, 16, 30), brilho=(160, 180, 220), t=tl)
    yc = terr(f, C, 0.9, 9, 1240, 40, (6, 6, 10), peak=(540, 90, 300))
    faro(f, C, 540, yc(540) + 10, 0.9, luz=1.0, t=tl * 1.4)
    px = 220 + tl * 55
    X, Y, zl = C.ts(px, yc(px), 0.9)
    pessoa(f, X, Y, 0.8 * zl, walk=tl * 7, rimcol=(170, 190, 255), rimk=0.8)
    fg(f, C, 13, y=1680, blades=6, rimcol=(150, 170, 230))
    fin(f, bloom=0.4)
    card(f, "CADA NOCHE", (540, 340), 110, tl, c["tw"]("nunca", 0.3))


@cena("S03", cap=1290, subj=[(380, 960, 900, 1180)], prova=0.6, escala="plano geral")
def s03(f, tl, d, c):
    C = push(tl, 0.06, 0.5)
    sky(f, "amanhecer", [(0, (60, 70, 110)), (0.5, (230, 150, 120)), (0.62, (255, 210, 160)), (1, (40, 30, 40))])
    disco(f, *C.ts(400, 1080, 0.2)[:2], 60, k=0.8)
    haze(f, 1070, 80, (255, 200, 160), 0.35)
    mar(f, C, 1110, (90, 60, 80), brilho=(255, 210, 150), t=tl)
    bx, by, zl = C.ts(980 - tl * 70, 1112, 0.6)
    barco(f, bx, by, 0.9 * zl, bob=3 * math.sin(tl * 2))
    yc = terr(f, C, 1.0, 5, 1300, 30, (14, 10, 16), peak=(120, 160, 200))
    faro(f, C, 140, yc(140) + 10, 1.0, luz=max(0.0, 0.6 - tl * 0.12), t=tl, beam=False)
    for i in range(4):
        ave(f, 300 + tl * 80 + i * 70, 520 + 30 * math.sin(tl + i), 1.1, tl * 8 + i * 2)
    fg(f, C, 17, y=1670, blades=8)
    fin(f)
    card(f, "GRACIAS", (540, 340), 130, tl, c["tw"]("gracias", 3.5))

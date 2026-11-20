"""Cartões de texto na imagem (com mola) e registo das caixas para o QA da zona segura."""
from __future__ import annotations

import numpy as np

from .canvas import R, font, spring
from .config import MARGIN, S, W

# Caixas de texto desenhadas no fotograma atual: (texto, y0, y1, x0, x1). A montagem limpa e verifica.
TXT: list[tuple] = []
NOCARD = False   # True durante transições: o plano que sai não mostra cartões


def fit(txt, sz, stroke=7, maxw=W - 2 * MARGIN - 8):
    """Reduz o tamanho para o texto caber na largura útil."""
    w = font(sz).getlength(txt) / S + 2 * stroke
    return sz if w <= maxw else sz * maxw / w


def hud(f, txt, xy, sz, col=(255, 244, 225), tl=0.0, t0=0.0, a=1.0, stroke=7, pop=True):
    u = tl - t0
    if u < 0: return
    k = spring(u / 0.45) if pop else 1.0
    r = R(f, xy[0] - 520, xy[1] - sz * 1.1, xy[0] + 520, xy[1] + sz * 1.1)
    if r.ok:
        r.text(xy, txt, sz * max(k, 0.05), (0, 0, 0), stroke=stroke, a=a)
        r.text(xy, txt, sz * max(k, 0.05), col, a=a)


def card(f, txt, xy, sz, tl, t0, col=(255, 244, 225), stroke=7, pop=True, a=1.0):
    """Cartão grande (número, data, lugar) que entra com mola no instante local t0."""
    if tl < t0 or NOCARD: return
    sz = fit(txt, sz, stroke); hw = font(sz).getlength(txt) / S / 2 + stroke
    TXT.append((txt, xy[1] - sz * 0.62, xy[1] + sz * 0.62, xy[0] - hw, xy[0] + hw))
    hud(f, txt, xy, sz, col, tl, t0, a=a, stroke=stroke, pop=pop)


def label(f, txt, x, y, sz, col=(255, 240, 210), stroke=4, a=1.0):
    """Etiqueta pequena e fixa."""
    if NOCARD: return
    hw = font(sz).getlength(txt) / S / 2 + stroke
    TXT.append((txt, y - sz * 0.62, y + sz * 0.62, x - hw, x + hw))
    r = R(f, x - 500, y - sz, x + 500, y + sz)
    if r.ok:
        r.text((x, y), txt, sz, (0, 0, 0), stroke=stroke, a=a); r.text((x, y), txt, sz, col, a=a)


def topband(f, k=0.45, y1=520):
    """Escurece o topo para os cartões lerem bem."""
    H = f.shape[0]
    y = np.arange(H, dtype=np.float32)[:, None, None]
    f *= 1 - k * np.clip(1 - (y - 150) / (y1 - 150), 0, 1) ** 1.2

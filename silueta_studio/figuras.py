"""Silhuetas genéricas (originais, desenhadas em código): pessoa, ave, barco e composição de sprites RGBA."""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import gaussian_filter

from .canvas import R
from .config import H, W
from .efeitos import sombra

INK = (8, 8, 12)
RIM = (255, 168, 84)


def pessoa(f, x, y, s=1.0, col=INK, walk=0.0, bob=0.0, rimcol=(255, 190, 110), rimk=1.0, shadow=True):
    """Figura humana simples com os pés em (x, y). walk = fase da passada (radianos)."""
    r = R(f, x - 90 * s, y - 280 * s, x + 90 * s, y + 60 * s)
    if not r.ok: return
    if shadow: sombra(f, x, y + 4 * s, 50 * s, 8 * s, 0.5)
    y = y + bob
    m = r.ell(x, y - 200 * s, 26 * s, 30 * s, col)
    r.poly([(x - 34 * s, y - 165 * s), (x + 34 * s, y - 165 * s), (x + 28 * s, y - 50 * s), (x - 28 * s, y - 50 * s)], col)
    sw = math.sin(walk) * 14 * s
    r.line([(x - 14 * s, y - 60 * s), (x - 16 * s + sw, y)], col, 20 * s)
    r.line([(x + 14 * s, y - 60 * s), (x + 16 * s - sw, y)], col, 20 * s)
    r.line([(x - 30 * s, y - 155 * s), (x - 40 * s - sw * 0.6, y - 80 * s)], col, 14 * s)
    r.line([(x + 30 * s, y - 155 * s), (x + 40 * s + sw * 0.6, y - 80 * s)], col, 14 * s)
    if rimk: r.rim(m, rimcol, rimk, 4)


def ave(f, x, y, s, ph, col=(10, 10, 14)):
    """Ave em voo; ph = fase do bater de asas."""
    r = R(f, x - 40 * s, y - 30 * s, x + 40 * s, y + 30 * s)
    if r.ok:
        w = math.sin(ph) * 10 * s
        r.line([(x - 30 * s, y + w), (x, y - 4 * s), (x + 30 * s, y + w)], col, 3 * s)


def barco(f, x, y, s=1.0, bob=0.0, col=(10, 12, 18)):
    """Navio simples (casco, superstrutura, mastro) com a linha de água em y."""
    r = R(f, x - 260 * s, y - 220 * s, x + 260 * s, y + 80 * s)
    if not r.ok: return
    y = y + bob
    r.poly([(x - 220 * s, y - 20 * s), (x + 240 * s, y - 20 * s), (x + 190 * s, y + 30 * s), (x - 180 * s, y + 30 * s)], col)
    r.poly([(x - 60 * s, y - 20 * s), (x - 60 * s, y - 70 * s), (x + 60 * s, y - 70 * s), (x + 60 * s, y - 20 * s)], col)
    r.poly([(x - 30 * s, y - 70 * s), (x - 30 * s, y - 110 * s), (x + 30 * s, y - 110 * s), (x + 30 * s, y - 70 * s)], col)
    r.line([(x + 120 * s, y - 20 * s), (x + 120 * s, y - 150 * s), (x + 30 * s, y - 190 * s)], col, 5 * s)


def put(f, img, x, y, rimk=1.4, rimcol=RIM, light=(0.85, -0.5), sh=7, a=1.0):
    """Compõe um sprite RGBA (PIL) com img.info['pes'] = (px, py) em (x, y), mais luz de recorte direcional."""
    px, py = img.info.get("pes", (img.width / 2, img.height))
    ox, oy = int(round(x - px)), int(round(y - py))
    A = np.asarray(img, np.float32); h, w = A.shape[:2]
    x0, y0, x1, y1 = max(0, ox), max(0, oy), min(W, ox + w), min(H, oy + h)
    if x1 <= x0 or y1 <= y0 or a <= 0: return ox, oy
    B = A[y0 - oy:y1 - oy, x0 - ox:x1 - ox]; al = B[..., 3] / 255.0 * a; reg = f[y0:y1, x0:x1]
    reg[...] = reg * (1 - al[..., None]) + B[..., :3] * al[..., None]
    if rimk:
        dx = int(round(-light[0] * sh)); dy = int(round(-light[1] * sh))
        e = np.clip(al - np.roll(np.roll(al, dy, 0), dx, 1), 0, 1)
        reg += gaussian_filter(e, 1.3)[..., None] * np.array(rimcol, np.float32) * rimk
    return ox, oy

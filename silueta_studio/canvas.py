"""Desenho por regiões sobre um fotograma float32 (H, W, 3).

Cada primitiva desenha só numa região R (rápido) com máscaras super-amostradas (S×) para bordas suaves.
Origin: the engine of a true-stories channel, rewritten to be independent of any single video.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

from .config import FONT, H, S, W

_FC: dict[int, ImageFont.FreeTypeFont] = {}


def font(sz: float, scale: int = S):
    """Fonte negrita no tamanho sz (em píxeis finais); cache por tamanho."""
    px = max(1, int(round(sz * scale)))
    if px not in _FC:
        _FC[px] = ImageFont.truetype(FONT, px) if FONT else ImageFont.load_default(px)
    return _FC[px]


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def spring(u: float) -> float:
    """Mola com ligeiro ressalto (entrada de cartões)."""
    return 1 - math.exp(-5 * u) * math.cos(9 * u) if u > 0 else 0.0


def blank() -> np.ndarray:
    return np.zeros((H, W, 3), np.float32)


class R:
    """Região retangular do fotograma f onde se pinta (coordenadas absolutas)."""

    def __init__(s, f, x0, y0, x1, y1):
        s.x0 = int(max(0, x0)); s.y0 = int(max(0, y0)); s.x1 = int(min(W, x1)); s.y1 = int(min(H, y1))
        s.ok = s.x1 > s.x0 + 1 and s.y1 > s.y0 + 1
        if s.ok:
            s.v = f[s.y0:s.y1, s.x0:s.x1]; s.w = s.x1 - s.x0; s.h = s.y1 - s.y0

    def _m(s, fn):
        im = Image.new("L", (s.w * S, s.h * S), 0); fn(ImageDraw.Draw(im))
        return np.asarray(im.resize((s.w, s.h), Image.LANCZOS), np.float32) / 255

    def paint(s, m, col, a=1.0):
        if not s.ok: return m
        mm = (m * a)[..., None]; s.v[...] = s.v * (1 - mm) + np.array(col, np.float32) * mm
        return m

    def add(s, m, col, k=1.0):
        if s.ok: s.v += m[..., None] * np.array(col, np.float32) * k

    def P(s, pts):
        return [((x - s.x0) * S, (y - s.y0) * S) for x, y in pts]

    def poly(s, pts, col, a=1.0):
        if not s.ok: return 0
        return s.paint(s._m(lambda d: d.polygon(s.P(pts), fill=255)), col, a)

    def ell(s, cx, cy, rx, ry, col, a=1.0):
        if not s.ok: return 0
        box = [(cx - rx - s.x0) * S, (cy - ry - s.y0) * S, (cx + rx - s.x0) * S, (cy + ry - s.y0) * S]
        return s.paint(s._m(lambda d: d.ellipse(box, fill=255)), col, a)

    def line(s, pts, col, w, a=1.0):
        if not s.ok: return 0
        return s.paint(s._m(lambda d: d.line(s.P(pts), fill=255, width=max(1, int(w * S)), joint="curve")), col, a)

    def pie(s, cx, cy, rx, ry, a0, a1, col, a=1.0):
        if not s.ok: return 0
        box = [(cx - rx - s.x0) * S, (cy - ry - s.y0) * S, (cx + rx - s.x0) * S, (cy + ry - s.y0) * S]
        return s.paint(s._m(lambda d: d.pieslice(box, a0, a1, fill=255)), col, a)

    def text(s, xy, t, sz, col, stroke=0, a=1.0, anchor="mm"):
        if not s.ok: return 0
        pos = ((xy[0] - s.x0) * S, (xy[1] - s.y0) * S)
        return s.paint(s._m(lambda d: d.text(pos, t, font=font(sz), fill=255, anchor=anchor, stroke_width=stroke * S)), col, a)

    def glow(s, cx, cy, r, col, k=1.0):
        if not s.ok: return
        yy, xx = np.mgrid[s.y0:s.y1, s.x0:s.x1]
        g = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)))
        s.v += g[..., None] * np.array(col, np.float32) * k

    def ring(s, cx, cy, rad, w, col, k=1.0):
        if not s.ok: return
        yy, xx = np.mgrid[s.y0:s.y1, s.x0:s.x1]; r = np.hypot(xx - cx, yy - cy)
        s.v += (np.exp(-((r - rad) / w) ** 2))[..., None] * np.array(col, np.float32) * k

    def rim(s, m, col=(255, 170, 90), k=1.4, sh=6):
        """Luz de recorte: realça a borda superior da máscara m (the visual signature of the style)."""
        if not s.ok: return
        r = np.clip(m - np.roll(m, sh, axis=0), 0, 1); r = gaussian_filter(r, 1.2); s.add(r, col, k)


def full(f) -> R:
    return R(f, 0, 0, W, H)


def addglow(f, x, y, rad, col, k=1.0, ext=2.6):
    r = R(f, x - rad * ext, y - rad * ext, x + rad * ext, y + rad * ext)
    if r.ok: r.glow(x, y, rad, col, k)


def mask_full(fn) -> np.ndarray:
    im = Image.new("L", (W * S, H * S), 0); fn(ImageDraw.Draw(im))
    return np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255


def vgrad(stops) -> np.ndarray:
    """Degradé vertical: stops = [(0..1, (r, g, b)), ...]."""
    y = np.linspace(0, 1, H); out = np.zeros((H, 3), np.float32); ys = [p[0] for p in stops]
    for c in range(3): out[:, c] = np.interp(y, ys, [p[1][c] for p in stops])
    return np.repeat(out[:, None, :], W, 1)


def smooth_noise(seed, sc, res=8) -> np.ndarray:
    r = np.random.default_rng(seed).random((H // res, W // res)).astype(np.float32)
    n = gaussian_filter(r, sc); n = (n - n.min()) / (n.max() - n.min() + 1e-9)
    return np.array(Image.fromarray((n * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255


def grade(f, sat=1.0, mul=(1, 1, 1), add=(0, 0, 0)):
    g = f.mean(2, keepdims=True)
    f[...] = (g + (f - g) * sat) * np.array(mul, np.float32) + np.array(add, np.float32)


def xf(pts, cx, cy, sc, ang=0, flip=False, ox=0, oy=0):
    """Transforma uma silhueta (lista de pontos) para posição, escala, rotação e espelho."""
    a = math.radians(ang); out = []
    for x, y in pts:
        x = (x - ox) * (-1 if flip else 1) * sc; y = (y - oy) * sc
        out.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    return out

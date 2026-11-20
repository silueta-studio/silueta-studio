"""Câmara com paralaxe e camadas de cenário (céu, cristas de terreno, primeiro plano desfocado).

Style rule: 3–5 camadas, o longe mais claro, o primeiro plano escuro e desfocado, personagens ENTRE camadas.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

from .canvas import full, vgrad
from .config import H, W


class Cam:
    """Push-in por camadas: cada camada aproxima (z-1)*par e desloca pan*par. Âncora vertical em ay."""

    def __init__(s, z=1.0, pan=0.0, ay=1230):
        s.z, s.pan, s.ay = z, pan, ay

    def ts(s, x, y, par=1.0):
        zl = 1 + (s.z - 1) * par
        return 540 + (x - 540) * zl - s.pan * par, s.ay + (y - s.ay) * zl, zl


def push(tl, z1=0.06, rate=0.6, pan=0.0, ay=1230) -> Cam:
    """Câmara que se aproxima suavemente ao longo do plano (tl = tempo local)."""
    return Cam(1 + z1 * (1 - math.exp(-rate * tl)), pan * tl, ay)


_SK: dict = {}


def sky(f, key, stops):
    """Céu em degradé (em cache por chave)."""
    if key not in _SK: _SK[key] = vgrad(stops)
    f[...] = _SK[key]


def ridge(seed, x, base, amp, freq=1.0):
    rr = np.random.default_rng(seed); ph = rr.uniform(0, 6.3, 4)
    return base - amp * (0.5 * np.sin(x * 0.0021 * freq + ph[0]) + 0.3 * np.sin(x * 0.0057 * freq + ph[1])
                         + 0.14 * np.sin(x * 0.013 * freq + ph[2]) + 0.06 * np.sin(x * 0.041 * freq + ph[3]))


def terr(f, C: Cam, par, seed, base, amp, col, freq=1.0, peak=None, a=1.0):
    """Camada de terreno com crista de ruído; peak=(x, altura, largura) ou lista. Devolve a crista y(x)."""
    xs = np.arange(-700, W + 1500, 12, dtype=np.float32); ys = ridge(seed, xs, base, amp, freq)
    for pk in ([peak] if peak and not isinstance(peak, list) else (peak or [])):
        ys = ys - pk[1] * np.exp(-((xs - pk[0]) / pk[2]) ** 2)
    pts = [C.ts(x, y, par)[:2] for x, y in zip(xs, ys)]
    full(f).poly(pts + [(W + 1600, H + 300), (-800, H + 300)], col, a)
    return lambda x: float(np.interp(x, xs, ys))


def fg(f, C: Cam, seed, y=1640, amp=40, blades=0, col=(5, 4, 6), rimk=0.28, rimcol=(255, 168, 84), par=1.7, blur=3.5):
    """Primeiro plano escuro e desfocado que passa à frente de tudo, com um fio de luz de recorte."""
    im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im); P = lambda a, b: C.ts(a, b, par)[:2]
    xs = np.arange(-600, W + 1400, 20); ys = ridge(seed, xs.astype(np.float32), y, amp, 3.0)
    d.polygon([P(a, b) for a, b in zip(xs, ys)] + [(W + 2000, H + 400), (-800, H + 400)], fill=255)
    rr = np.random.default_rng(seed + 50)
    for _ in range(blades):
        x = rr.uniform(-300, W + 500); hh = rr.uniform(70, 190); ln = rr.uniform(-0.35, 0.35); a = P(x, y + 16)
        d.line([a, (a[0] + ln * hh * 0.5, a[1] - hh * 0.6), (a[0] + ln * hh * 1.3, a[1] - hh)],
               fill=255, width=int(rr.uniform(5, 10)), joint="curve")
    m = gaussian_filter(np.asarray(im, np.float32) / 255, blur)
    f[...] = f * (1 - m[..., None]) + np.array(col, np.float32) * m[..., None]
    if rimk:
        e = np.clip(m - np.roll(np.roll(m, 5, 0), -4, 1), 0, 1)
        f += gaussian_filter(e, 2.0)[..., None] * np.array(rimcol, np.float32) * rimk

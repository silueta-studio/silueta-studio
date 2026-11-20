"""Efeitos de imagem: acabamento (bloom, cor, grão, vinheta), luz, partículas e câmara."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.ndimage import gaussian_filter

from .canvas import R, addglow, smooth_noise
from .config import H, W


@lru_cache(maxsize=1)
def _grids():
    YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
    r2 = ((XX - 540) / 760) ** 2 + ((YY - 930) / 1180) ** 2
    vig = (1 - 0.30 * np.clip(r2, 0, 1.6) ** 1.6)[..., None].astype(np.float32)
    return YY, XX, vig, smooth_noise(803, 2, 4)


def fin(f, vig=True, bloom=0.34, sat=1.12, con=1.06):
    """Finishing grade: brilho nas altas luzes, contraste, saturação, textura e vinheta."""
    _, _, VIG, N3 = _grids()
    if bloom:
        q = f[::4, ::4]
        m = np.clip((q.min(2) * 0.35 + q.max(2) * 0.65 - 214) / 36.0, 0, 1)[..., None] * q
        b = gaussian_filter(m, (7, 7, 0)); f += np.repeat(np.repeat(b, 4, 0), 4, 1)[:H, :W] * bloom
    g = f.mean(2, keepdims=True); f[...] = ((g + (f - g) * sat) - 118) * con + 118
    f *= (0.94 + 0.12 * N3[..., None])
    if vig: f *= VIG


_GRAIN: list[np.ndarray] = []


def grain(f, t, fps=30, a=2.5):
    """Grão de filme que muda a cada fotograma (4 padrões em ciclo)."""
    if not _GRAIN:
        _GRAIN.extend(np.random.default_rng(i).normal(0, a, (H, W, 1)).astype(np.float32) for i in range(4))
    f += _GRAIN[int(t * fps) % 4]


def haze(f, y, h, col, k):
    """Faixa de névoa horizontal centrada em y."""
    YY = _grids()[0]
    m = (np.clip(1 - np.abs(YY - y) / h, 0, 1) ** 1.5 * k)[..., None]
    f[...] = f * (1 - m) + np.array(col, np.float32) * m


def softblob(f, x, y, rad, col, a=1.0):
    r = R(f, x - rad * 1.6, y - rad * 1.6, x + rad * 1.6, y + rad * 1.6)
    if not r.ok: return
    yy, xx = np.mgrid[r.y0:r.y1, r.x0:r.x1]; m = np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / (rad * rad))) * a
    r.v[...] = r.v * (1 - m[..., None]) + np.array(col, np.float32) * m[..., None]


def sombra(f, x, y, rx, ry, k=0.6):
    """Sombra de contacto (pés no chão)."""
    r = R(f, x - rx * 1.5, y - ry * 2.5, x + rx * 1.5, y + ry * 2.5)
    if r.ok:
        yy, xx = np.mgrid[r.y0:r.y1, r.x0:r.x1]; m = np.exp(-(((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2)) * k
        r.v[...] = r.v * (1 - m[..., None])


def disco(f, x, y, r, col=(255, 224, 164), k=1.0, halo=2.4):
    """Sol ou lua: disco nítido + halo (a silhueta recorta-se contra ele)."""
    addglow(f, x, y, r * halo, col, 0.30 * k, ext=2.0)
    rg = R(f, x - r - 6, y - r - 6, x + r + 6, y + r + 6)
    if rg.ok: rg.ell(x, y, r, r, col, min(1.0, k))


@lru_cache(maxsize=1)
def _half():
    return np.mgrid[0:H:2, 0:W:2].astype(np.float32)


def rayos(f, x, y, t, col=(255, 226, 170), k=0.22, n=7, r0=90, r1=1500, seed=0):
    """Raios de luz a partir de (x, y), a rodar devagar (meia resolução)."""
    YH, XH = _half()
    ang = np.arctan2(YH - y, XH - x); rad = np.hypot(XH - x, YH - y)
    m = (np.sin(ang * n + seed + t * 0.11) + 0.7 * np.sin(ang * (n * 2 + 3) + seed * 1.7 - t * 0.07)
         + 0.5 * np.sin(ang * (n * 3 + 2) + seed * 0.6 + t * 0.05))
    m = np.clip(m / 1.6, 0, 1) ** 1.6 * np.clip((rad - r0) / 260.0, 0, 1) * np.clip(1 - rad / r1, 0, 1) ** 1.3
    f += np.repeat(np.repeat(m, 2, 0), 2, 1)[:H, :W, None] * np.array(col, np.float32) * k


def brasas(f, t, n=26, seed=0, col=(255, 170, 84), k=1.0, y0=260, y1=1560, vx=46.0, sube=0.11, big=0.3):
    """Brasas ou pó em suspensão: pontos nítidos + alguns grandes desfocados que derivam e piscam."""
    rr = np.random.default_rng(700 + seed)
    for _ in range(n):
        x0 = rr.uniform(-100, W + 100); yb = rr.uniform(0, 1); sp = rr.uniform(0.5, 1.5); ph = rr.uniform(0, 6.3)
        sz = rr.uniform(2.0, 4.6); b = rr.random() < big
        life = (yb + t * sp * sube) % 1.0; y = y1 + (y0 - y1) * life
        x = (x0 + vx * t * sp + 34 * math.sin(t * 1.5 * sp + ph) + 100) % (W + 200) - 100
        a = math.sin(math.pi * life) ** 0.7 * (0.62 + 0.38 * math.sin(t * 8.0 * sp + ph))
        addglow(f, x, y, sz * 7.5 if b else sz, col, (0.20 if b else 1.5) * k * a)


def chispas(f, x, y, t, n=16, seed=0, col=(255, 190, 100), h=420.0, k=1.0):
    """Faúlhas a subir de uma fogueira em (x, y)."""
    rr = np.random.default_rng(800 + seed)
    for _ in range(n):
        ph = rr.uniform(0, 1); sp = rr.uniform(0.5, 1.2); dx = rr.uniform(-50, 50); w = rr.uniform(0, 6.3)
        q = (ph + t * sp * 0.42) % 1.0
        addglow(f, x + dx * q + 26 * math.sin(q * 7 + w), y - h * q ** 0.8, 2.6, col, 1.8 * k * (1 - q) ** 1.2)


def temblor(f, t, times, amp=11.0, rate=8.0):
    """Tremor de câmara nos impactos (as margens repetem-se, sem dar a volta)."""
    dx = dy = 0.0
    for t0 in times:
        dt = t - t0
        if 0 <= dt < 0.7:
            e = amp * math.exp(-dt * rate); dx += e * math.sin(dt * 61); dy += e * math.cos(dt * 47) * 0.8
    dx, dy = int(round(dx)), int(round(dy))
    if dx:
        f[...] = np.roll(f, dx, 1)
        if dx > 0: f[:, :dx] = f[:, dx:dx + 1]
        else: f[:, dx:] = f[:, dx - 1:dx]
    if dy:
        f[...] = np.roll(f, dy, 0)
        if dy > 0: f[:dy] = f[dy:dy + 1]
        else: f[dy:] = f[dy - 1:dy]


def flashk(t, times, dur=0.45, rate=7.0) -> float:
    """Intensidade 0..1 de um clarão que decai depois de cada instante em times."""
    best = 0.0
    for t0 in times:
        dt = t - t0
        if -0.03 <= dt < dur: best = max(best, math.exp(-max(dt, 0) * rate))
    return best

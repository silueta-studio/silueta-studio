"""Legendas karaoke: maiúsculas, palavra ativa amarela com «pop», páginas de até 2 linhas.

words = {plano_id: [[palavra, t_ini, t_fim], ...]} em tempo absoluto.
"""
from __future__ import annotations

import math
import re

from PIL import Image, ImageDraw, ImageFont

from .config import FONT, H, MARGIN, W

SZ = 78; GAP = 30; LH = 100; MAXW = 930; KGAP = 0.7
ATIVA = (255, 210, 63); DITA = (236, 196, 80); FUTURA = (255, 255, 255)


def _font(sz):
    return ImageFont.truetype(FONT, int(round(sz))) if FONT else ImageFont.load_default(int(round(sz)))


class Karaoke:
    def __init__(self, words: dict, cap_y: dict, sz=SZ):
        """cap_y = {plano_id: y do topo da legenda, ou None = sem karaoke nesse plano}."""
        self.sz = sz; self.KF = _font(sz); self._F = {}
        self.pages = []
        for sid, ws in words.items():
            cy = cap_y.get(sid)
            if cy is None or not ws: continue
            for pg in self._paginate(ws):
                pos, box, sz = self._layout(pg, cy)
                self.pages.append([pg[0][1] - 0.05, pg[-1][2] + 0.35, pg, pos, box, sid, sz])
        self.pages.sort(key=lambda z: z[0])
        P = self.pages
        for i in range(len(P) - 1):
            if P[i + 1][5] == P[i][5] and P[i + 1][0] - P[i][1] < 1.0: P[i][1] = P[i + 1][0] - 0.01
            else: P[i][1] = min(P[i][1], P[i + 1][0] - 0.01)
        for i, k in enumerate(P):
            k.append(0.0 if i > 0 and k[0] - P[i - 1][1] < KGAP else 0.08)
            k.append(0.0 if i + 1 < len(P) and P[i + 1][0] - k[1] < KGAP else 0.12)

    def _w(self, w): return self.KF.getlength(w[0].upper())

    def _split(self, pg):
        return min(max(sum(self._w(w) + GAP for w in pg[:k]), sum(self._w(w) + GAP for w in pg[k:])) for k in range(1, len(pg) + 1))

    def _paginate(self, words, maxw=5):
        pg, cur = [], []
        for w in words:
            if cur and (self._split(cur + [w]) > MAXW or len(cur) >= maxw or re.search(r"[.?!…:]$", cur[-1][0])):
                pg.append(cur); cur = []
            cur.append(w)
        if cur: pg.append(cur)
        return pg

    def _layout(self, pg, y0):
        """Posições das palavras em 1 ou 2 linhas centradas; se uma linha não cabe em W-2*MARGIN, a página encolhe."""
        lw = lambda L, k=1.0: (sum(self._w(w) for w in L) + GAP * (len(L) - 1)) * k
        best = None
        for k in range(1, len(pg) + 1):
            m = max(lw(pg[:k]), lw(pg[k:]))
            if best is None or m < best[0]: best = (m, k)
        k = best[1]; lines = [pg[:k], pg[k:]] if pg[k:] else [pg]
        esc = min(1.0, (W - 2 * MARGIN - 4) / max(lw(L) for L in lines)); sz = self.sz * esc; pos = {}
        for li, L in enumerate(lines):
            x = (W - lw(L, esc)) / 2
            for w in L: pos[id(w)] = (x, y0 + li * LH * max(esc, 0.8)); x += (self._w(w) + GAP) * esc
        box = (min(p[0] for p in pos.values()), y0,
               max(pos[id(w)][0] + self._w(w) * esc for w in pg), y0 + (len(lines) - 1) * LH * max(esc, 0.8) + 86 * esc)
        return pos, box, sz

    def _kf(self, sz):
        sz = int(round(sz))
        if sz not in self._F: self._F[sz] = _font(sz)
        return self._F[sz]

    def layer(self, t):
        """Camada RGBA do karaoke no instante t (ou None) e as caixas ativas (para o QA)."""
        act = [k for k in self.pages if k[0] <= t <= k[1]]
        if not act: return None, []
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for t0, t1, pg, pos, box, sid, psz, fi, fo in act:
            F0 = self._kf(psz)
            fade = min(1.0, (t - t0) / fi if fi else 9, (t1 - t) / fo if fo else 9); a = int(255 * max(0, min(1, fade)))
            for w in pg:
                txt = w[0].upper(); x, y = pos[id(w)]; f = F0; off = (0, 0)
                if t < w[1]: col = FUTURA + (a,)
                elif t <= w[2] + 0.02:
                    pop = 1 + 0.06 * math.exp(-(t - w[1]) * 14); col = ATIVA + (a,); f = self._kf(psz * pop)
                    off = (-(f.getlength(txt) - F0.getlength(txt)) / 2, -(psz * (pop - 1)) / 2)
                else: col = DITA + (a,)
                d.text((x + off[0], y + off[1]), txt, font=f, fill=col, stroke_width=8, stroke_fill=(0, 0, 0, a))
        return lay, [k[4] for k in act]

"""Scene registry. In each story's cenas.py:

    from silueta_studio import cena

    @cena("S01", cap=1300, subj=[(300, 700, 800, 1280)], prova=0.6)
    def s01(f, tl, d, c):
        ...  # draw the whole frame into f (float32 H×W×3); tl = local time in the shot, d = shot duration

c = dict(tw=fn(prefix, default) -> local time of the first spoken word starting with prefix, wl=[(word, t0, t1)], sid=id, d=dur).
cap  = y of the top of the captions (None = no captions in this shot); subj = subject boxes the captions must not cover;
prova = fraction of the shot used for the contact sheet.
"""
from __future__ import annotations

REGISTO: dict[str, dict] = {}


def cena(sid: str, cap: int | None = 1300, subj=None, prova: float = 0.6, escala: str = ""):
    def deco(fn):
        REGISTO[sid] = dict(fn=fn, cap=cap, subj=subj or [], prova=prova, escala=escala)
        return fn
    return deco

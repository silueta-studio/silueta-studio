"""A story = a folder with historia.json (shots, transitions) + cenas.py (the drawing of each shot).

historia.json:
{
  "titulo": "...", "idioma": "es",
  "planos": [{"id": "S01", "dur": 4.6, "voz": "caption text", "fala": "spoken form (optional)", "texto": "CARD",
              "cola": 0.3, "golpe": 0.0, "karaoke": true}, ...],
  "transicoes": {"S03": ["whip", 0.25], "S08": ["fadeblack", 0.3]},     # dissolve | fadeblack | whitedis | whip
  "alias": {"heard_spelling": "script_spelling"}, "musica": {...}, "sfx": [...]   # see audio.py
}
Timings come from timing.json and words.json (written by `silueta align`); without them they are estimated from the text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TIPOS_TRANSICAO = {"dissolve", "fadeblack", "whitedis", "whip"}


class Historia:
    def __init__(self, pasta: str | Path):
        self.pasta = Path(pasta).resolve()
        cfg = json.loads((self.pasta / "historia.json").read_text(encoding="utf-8-sig"))
        self.titulo = cfg.get("titulo", self.pasta.name)
        self.planos = cfg["planos"]
        self.byid = {p["id"]: p for p in self.planos}
        self.trans = {k: tuple(v) for k, v in cfg.get("transicoes", {}).items()}
        self.fade_floor = cfg.get("fade_floor", 0.15)
        self.white_max = cfg.get("white_max", 0.70)
        self._valida()

    def _valida(self):
        ids = [p["id"] for p in self.planos]
        if len(ids) != len(set(ids)): raise ValueError("repeated shot ids in historia.json")
        for sid, (kind, d) in self.trans.items():
            if sid not in self.byid: raise ValueError(f"transition for a shot that does not exist: {sid}")
            if kind not in TIPOS_TRANSICAO: raise ValueError(f"unknown transition {kind!r} (use one of {sorted(TIPOS_TRANSICAO)})")

    # ---------------------------------------------------------------- tempos
    def timing(self):
        """([{id, start, dur, voice}], 'real'|'estimated')."""
        p = self.pasta / "timing.json"
        if p.exists():
            T = json.loads(p.read_text(encoding="utf-8-sig"))
            falta = [q["id"] for q in self.planos if q["id"] not in {x["id"] for x in T}]
            if falta: raise ValueError(f"timing.json is missing shots {falta}")
            return T, "real"
        T, t = [], 0.0
        for q in self.planos:
            T.append(dict(id=q["id"], start=round(t, 3), dur=q["dur"], voice=q.get("voz", ""))); t += q["dur"]
        return T, "estimated"

    def words(self, T):
        """({plano_id: [[palavra, t0, t1], ...]}, 'real'|'estimated')."""
        p = self.pasta / "words.json"
        if p.exists(): return json.loads(p.read_text(encoding="utf-8-sig")), "real"
        return self._estimate_words(T), "estimated"

    def _estimate_words(self, T):
        """Reparte o texto pelo plano proporcionalmente ao tamanho das palavras, com pausas na pontuação."""
        out = {}
        for x in T:
            q = self.byid[x["id"]]; ws = (x.get("voice") or "").split()
            if not ws: out[x["id"]] = []; continue
            t0 = x["start"] + 0.15 + q.get("golpe", 0.0); t1 = x["start"] + x["dur"] - 0.30 - q.get("cola", 0.0)
            wt = [len(re.sub(r"\W", "", w)) + 1.5 for w in ws]
            pz = [0.42 if re.search(r"(\.\.\.|…)", w) else 0.30 if re.search(r"[.:?!»]$", w) else 0.15 if w.endswith(",") else 0.0 for w in ws]
            pz[-1] = 0.0
            k = max(0.05, (t1 - t0 - sum(pz)) / sum(wt)); t = t0; L = []
            for w, a, pause in zip(ws, wt, pz):
                L.append([w, round(t, 3), round(t + a * k, 3)]); t += a * k + pause
            out[x["id"]] = L
        return out

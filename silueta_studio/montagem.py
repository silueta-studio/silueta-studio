"""Montagem: junta planos, transições, grão e karaoke; folha de prova com QA; render por partes retomável."""
from __future__ import annotations

import importlib.util
import math
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import uniform_filter1d

from . import texto
from .canvas import ease
from .cenas import REGISTO
from .config import FONT, FPS, H, MARGIN, SAFE_Y0, SAFE_Y1, W
from .efeitos import grain
from .historia import Historia
from .karaoke import Karaoke


def _f(sz):
    return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default(sz)


def carregar_cenas(pasta: Path) -> dict:
    """Importa <pasta>/cenas.py; os @cena registam-se em REGISTO."""
    REGISTO.clear()
    p = pasta / "cenas.py"
    if not p.exists(): raise SystemExit(f"missing {p}")
    spec = importlib.util.spec_from_file_location(f"cenas_{abs(hash(str(p)))}", p)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return dict(REGISTO)


class Montagem:
    def __init__(self, pasta):
        self.h = Historia(pasta); self.pasta = self.h.pasta
        self.SC = carregar_cenas(self.pasta)
        falta = [p["id"] for p in self.h.planos if p["id"] not in self.SC]
        if falta: raise SystemExit(f"cenas.py has no @cena for: {', '.join(falta)}")
        self.T, self.tsrc = self.h.timing()
        self.WD, self.wsrc = self.h.words(self.T)
        self.TOT = self.T[-1]["start"] + self.T[-1]["dur"]
        cap = {x["id"]: (self.SC[x["id"]]["cap"] if self.h.byid[x["id"]].get("karaoke", True) else None) for x in self.T}
        self.K = Karaoke(self.WD, cap)

    # ------------------------------------------------------------ fotograma
    def scene_f(self, t, x):
        """Fotograma float (sem grão nem karaoke) do plano x no instante absoluto t (pode passar do fim)."""
        sid = x["id"]; tl = t - x["start"]; d = x["dur"]
        wl = [(w, a - x["start"], b - x["start"]) for w, a, b in self.WD.get(sid, [])]

        def tw(pref, default):
            pref = pref.lower()
            for q in wl:
                if re.sub(r"\W", "", q[0].lower()).startswith(pref): return q[1]
            return default

        f = np.zeros((H, W, 3), np.float32); texto.TXT.clear()
        self.SC[sid]["fn"](f, tl, d, dict(tw=tw, wl=wl, sid=sid, d=d))
        return f

    def _idx(self, t):
        return max(j for j, x in enumerate(self.T) if x["start"] <= t + 1e-6)

    def blend(self, t, i):
        T = self.T; x = T[i]; sid = x["id"]; tl = t - x["start"]; d = x["dur"]
        f = self.scene_f(t, x); txt_in = list(texto.TXT)
        tr = self.h.trans.get(sid)
        if tr and tl < tr[1] and i > 0:
            kind, D = tr; p = T[i - 1]; k = ease(tl / D)
            if kind == "fadeblack":
                f *= self.h.fade_floor + (1 - self.h.fade_floor) * k
            else:
                texto.NOCARD = True
                try: g = self.scene_f(min(t, p["start"] + p["dur"] + 0.8), p)   # o plano que sai continua, sem cartões
                finally: texto.NOCARD = False
                if kind == "dissolve":
                    wo = 1 - ease(tl / (0.6 * D)); wi = k; f = (g * wo + f * wi) / (wo + wi + 1e-6)
                elif kind == "whitedis":
                    WM = self.h.white_max
                    if tl < D / 2: e = ease(tl / (D / 2)); f = g * (1 - WM * e) + 255 * WM * e
                    else: e = 1 - ease((tl - D / 2) / (D / 2)); f = 255 * WM * e + f * (1 - WM * e)
                elif kind == "whip":
                    sh = int(W * k); c = np.empty_like(f)
                    if sh <= 0: c = g
                    elif sh >= W: c = f
                    else: c[:, :W - sh] = g[:, sh:]; c[:, W - sh:] = f[:, :sh]
                    f = uniform_filter1d(c, int(2 + 90 * math.sin(math.pi * k)), axis=1, mode="nearest")
        texto.TXT[:] = txt_in                     # o QA de texto olha para o plano que entra
        nx = self.h.trans.get(T[i + 1]["id"]) if i + 1 < len(T) else None
        if nx and nx[0] == "fadeblack" and tl > d - nx[1]:
            f = f * (self.h.fade_floor + (1 - self.h.fade_floor) * ease((d - tl) / nx[1]))
        return f

    def frame(self, t, qa=None):
        i = self._idx(t); x = self.T[i]; sid = x["id"]; sc = self.SC[sid]
        f = self.blend(t, i); grain(f, t, FPS)
        img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)); k, boxes = self.K.layer(t)
        if k is not None: img = img.convert("RGBA"); img.alpha_composite(k); img = img.convert("RGB")
        if qa is not None: self._qa(sid, sc, boxes, qa)
        return np.asarray(img)

    def _qa(self, sid, sc, boxes, qa):
        tx = texto.TXT
        for txt, y0, y1, x0, x1 in tx:
            if y0 < SAFE_Y0 or y1 > SAFE_Y1: qa.append(f'{sid}: text "{txt}" outside the safe zone (y {y0:.0f}-{y1:.0f})')
            if x0 < MARGIN - 1 or x1 > W - MARGIN + 1: qa.append(f'{sid}: text "{txt}" closer than {MARGIN} px to the side')
        for a in range(len(tx)):
            for b in range(a + 1, len(tx)):
                A, B = tx[a], tx[b]
                if min(A[2], B[2]) > max(A[1], B[1]) and min(A[4], B[4]) > max(A[3], B[3]):
                    qa.append(f'{sid}: overlapping texts "{A[0]}" / "{B[0]}"')
        for bx in boxes:
            if bx[1] < SAFE_Y0 or bx[3] > SAFE_Y1: qa.append(f"{sid}: captions outside the safe zone (y {bx[1]:.0f}-{bx[3]:.0f})")
            for sb in sc["subj"]:
                ix = max(0, min(bx[2], sb[2]) - max(bx[0], sb[0])); iy = max(0, min(bx[3], sb[3]) - max(bx[1], sb[1]))
                if ix * iy > 0.10 * (sb[2] - sb[0]) * (sb[3] - sb[1]): qa.append(f"{sid}: captions cover the subject {sb}")
            if bx[0] < MARGIN - 1 or bx[2] > W - MARGIN + 1: qa.append(f"{sid}: captions closer than the side margin")
            for txt, y0, y1, _, _ in tx:
                if not (y1 < bx[1] or y0 > bx[3]): qa.append(f'{sid}: captions overlap "{txt}"')

    # ------------------------------------------------------------ folha de prova
    def prova(self) -> list[str]:
        t0 = time.time(); out = self.pasta / "prova"; out.mkdir(exist_ok=True)
        tw_, th_ = 300, 533; cols = min(6, len(self.T)); rows = (len(self.T) + cols - 1) // cols; head = 70; lab = 40
        sheet = Image.new("RGB", (cols * tw_, head + rows * (th_ + lab)), (18, 18, 22)); d = ImageDraw.Draw(sheet)
        d.text((14, 12), f"{self.h.titulo} - timings: {self.tsrc}, words: {self.wsrc}, total {self.TOT:.1f} s", font=_f(22), fill=(235, 235, 235))
        d.text((14, 42), f"QA: text between y={SAFE_Y0} and y={SAFE_Y1}, {MARGIN} px side margin, captions never cover the subject.", font=_f(16), fill=(170, 170, 170))
        QA = []
        for i, x in enumerate(self.T):
            sc = self.SC[x["id"]]; t = x["start"] + x["dur"] * sc["prova"]; q = []
            try: im = Image.fromarray(self.frame(t, q))
            except Exception:
                traceback.print_exc(); im = Image.new("RGB", (W, H), (255, 0, 255)); q.append(x["id"] + ": ERROR while drawing")
            im.save(out / f"{x['id']}.png"); QA += q
            cx, cy = (i % cols) * tw_, head + (i // cols) * (th_ + lab)
            sheet.paste(im.resize((tw_, th_), Image.LANCZOS), (cx, cy))
            d.rectangle([cx, cy + th_, cx + tw_ - 1, cy + th_ + lab - 1], fill=(150, 30, 30) if q else (28, 28, 34))
            d.text((cx + 8, cy + th_ + 9), f"{x['id']}  {x['start']:.1f}s  {sc.get('escala', '')}"[:34], font=_f(18), fill=(235, 235, 235))
            print(x["id"], "ok" if not q else q, flush=True)
        dest = self.pasta / "prova.png"; sheet.save(dest)
        print("QA:", "no warnings" if not QA else "\n  " + "\n  ".join(dict.fromkeys(QA)))
        print(f"contact sheet: {dest}  ({time.time() - t0:.1f} s, {len(self.T)} shots, {self.TOT:.2f} s, timings {self.tsrc})")
        return QA

    # ------------------------------------------------------------ render
    def render_parte(self, a0, a1, dest: Path, crf=17):
        """Fotogramas [a0, a1) → dest (H.264 High, GOP 60). Escreve para .tmp e só renomeia no fim (retomável)."""
        work = dest.with_suffix(".tmp.mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-profile:v", "high", "-crf", str(crf), "-preset", "medium",
                               "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-pix_fmt", "yuv420p", "-f", "mp4", str(work)],
                              stdin=subprocess.PIPE)
        for n in range(a0, a1): ff.stdin.write(self.frame(n / FPS).tobytes())
        ff.stdin.close(); ff.wait()
        if ff.returncode: raise SystemExit(f"ffmpeg failed on part {a0}")
        work.replace(dest)

    def render(self, force=False, parte=60, crf=17, vagas=None, uma_vaga=False, leve=True):
        """Render em paralelo (`vagas` processos) por partes de `parte` fotogramas. Retomável: as partes feitas ficam.
        uma_vaga=True: renderiza só uma vaga de partes e sai (para sessões que podem ser interrompidas)."""
        if self.tsrc != "real" and not force:
            raise SystemExit("Timings are ESTIMATED (no voice alignment yet: run `silueta align`). Use --force for tests only.")
        if not shutil.which("ffmpeg"): raise SystemExit("ffmpeg not found on PATH")
        vagas = vagas or _vagas_por_defeito()
        tmp = self.pasta / "render_partes"; tmp.mkdir(exist_ok=True)
        N = int(round(self.TOT * FPS)); bounds = [(a, min(a + parte, N)) for a in range(0, N, parte)]
        part = lambda a: tmp / f"p{a:06d}.mp4"
        falta = [b for b in bounds if not part(b[0]).exists()]
        if uma_vaga: falta = falta[:vagas]
        t0 = time.time(); feitos = len(bounds) - len([b for b in bounds if not part(b[0]).exists()])
        print(f"{N} frames, {len(bounds)} parts ({feitos} already done), {vagas} processes", flush=True)

        env = None   # testado 20 nov: forçar 1 thread por processo ficou 2× mais lento

        def um(b):
            log = tmp / f"p{b[0]:06d}.log"
            with open(log, "wb") as sink:
                r = subprocess.run([sys.executable, "-m", "silueta_studio.cli", "_part", str(self.pasta), str(b[0]), str(b[1]), str(crf)],
                                   stdout=sink, stderr=subprocess.STDOUT, env=env)
            if r.returncode or not part(b[0]).exists():
                raise SystemExit(f"part {b[0]} failed; see {log}")
            log.unlink(missing_ok=True); return b

        if falta:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=vagas) as pool:
                for b in pool.map(um, falta):
                    feitos += 1; el = time.time() - t0
                    print(f"  part {b[0]}-{b[1]} ok | {feitos}/{len(bounds)} | {el:.0f} s", flush=True)
        if not all(part(b[0]).exists() for b in bounds):
            print(f"{sum(not part(b[0]).exists() for b in bounds)} parts left: run the same command again to resume"); return None
        return self._juntar([part(b[0]) for b in bounds], tmp, leve)

    def _juntar(self, partes, tmp, leve):
        dur = self.TOT; lst = tmp / "lista.txt"; video = tmp / "video.mp4"
        lst.write_text("".join(f"file '{p.name}'\n" for p in partes), encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video))
        audio = next((self.pasta / a for a in ("mistura.wav", "mistura.flac", "voz.wav", "voz.mp3") if (self.pasta / a).exists()), None)
        dest = self.pasta / "final.mp4"
        if audio:
            _ff("-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.3f}", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(dest))
        else:
            _ff("-i", str(video), "-c", "copy", "-movflags", "+faststart", str(dest))
            print("warning: no audio (add mistura.wav, or run `silueta align` to create voz.wav)")
        print(f"master: {dest} ({dest.stat().st_size / 2**20:.1f} MiB)")
        if leve:                                                     # versão de revisão ≤ 30 MB (WhatsApp/telemóvel)
            kb = max(600, min(8000, int(28 * 8 * 1024 / dur) - 128)); lv = self.pasta / "final_revisao.mp4"
            _ff("-i", str(dest), "-c:v", "libx264", "-preset", "medium", "-b:v", f"{kb}k", "-maxrate", f"{int(kb * 1.5)}k",
                "-bufsize", f"{kb * 2}k", "-pix_fmt", "yuv420p", "-g", "60", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(lv))
            print(f"review copy: {lv} ({lv.stat().st_size / 2**20:.1f} MiB)")
        shutil.rmtree(tmp, ignore_errors=True)
        return dest


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def _vagas_por_defeito():
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
    except ImportError:
        n = (os.cpu_count() or 4) // 2
    return max(1, (n or 2) - 1)

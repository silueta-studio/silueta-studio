"""Mix: voice (voz.wav from `silueta align`) + music and sound effects YOU PROVIDE (with a licence) -> mistura.wav at -14 LUFS.

The kit ships no music or effects. Declare them in historia.json (paths relative to the story folder):
  "musica": {"faixa": "som/my_track.mp3", "entra": "S02", "alinhar": "fim", "gain_db": 0,
             "cortes": [["S06", "inicio"]]}          # hard 0.35 s silence right before shot S06 starts
  "sfx": [{"ficheiro": "som/impact.wav", "plano": "S01", "palavra": "cuarenta", "gain_db": -3},
          {"ficheiro": "som/wind.wav", "plano": "S02", "t": 0.0, "gain_db": -12}]
"entra" = shot id or seconds; "alinhar": "fim" uses the end of the track (its ending lands on the video's end), "inicio" its start.
Levels: voice -20 dBFS RMS per shot; music ~20 dB under the voice and +5 dB in pauses; effects ducked -8 dB under
the voice; two-pass loudnorm to -14 LUFS, true peak <= -1.5 dBTP. One long track, never looped.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
LN = "loudnorm=I=-13.7:TP=-1.5:LRA=11"


def ler(path, n=None) -> np.ndarray:
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"])
    x = np.frombuffer(raw, np.float32).copy()
    return x if n is None else np.pad(x, (0, max(0, n - len(x))))[:n]


def _rms_db(x):
    act = x[np.abs(x) > 0.01 * max(1e-6, np.abs(x).max())]
    return 20 * np.log10(np.sqrt((act ** 2).mean()) + 1e-9) if len(act) else -120.0


def _env(x, att, rel, step=48):
    """Envolvente 0..1 de presença com ataque/libertação (segundos)."""
    n = len(x); h = int(0.02 * SR); e = np.sqrt(np.convolve(x ** 2, np.ones(h) / h, "same")); pres = (e > 0.01).astype(np.float32)
    ka = 1 - np.exp(-step / (att * SR)); kr = 1 - np.exp(-step / (rel * SR)); y = np.zeros(n, np.float32); v = 0.0
    for i in range(0, n, step):
        p = float(pres[i:i + step].max()); v += (ka if p > v else kr) * (p - v); y[i:i + step] = v
    return y


def misturar(pasta) -> Path:
    pasta = Path(pasta).resolve(); cfg = json.loads((pasta / "historia.json").read_text(encoding="utf-8-sig"))
    tp = pasta / "timing.json"; vp = pasta / "voz.wav"
    if not (tp.exists() and vp.exists()): raise SystemExit("missing timing.json/voz.wav: run `silueta align` first")
    T = json.loads(tp.read_text(encoding="utf-8")); S = {x["id"]: x for x in T}
    W = json.loads((pasta / "words_whisperx.json").read_text(encoding="utf-8")) if (pasta / "words_whisperx.json").exists() else {}
    TOT = T[-1]["start"] + T[-1]["dur"]; n = int(round(TOT * SR)); tt = np.arange(n) / SR

    # voz: −20 dBFS RMS por plano + passa-altos 70 Hz
    voz = ler(vp, n)
    for x in T:
        i, j = int(x["start"] * SR), min(n, int((x["start"] + x["dur"]) * SR)); c = voz[i:j]
        if len(c): voz[i:j] = c * 10 ** ((-20 - _rms_db(c)) / 20)
    voz = sosfilt(butter(2, 70, "highpass", fs=SR, output="sos"), voz).astype(np.float32)
    pres = _env(voz, 0.08, 0.4)

    def t_de(plano, palavra=None, t=0.0):
        if plano not in S: raise SystemExit(f"unknown shot in historia.json: {plano}")
        if palavra:
            pref = re.sub(r"\W", "", palavra.lower())
            for w, a, _ in W.get(plano, []):
                if re.sub(r"\W", "", w.lower()).startswith(pref): return a + t
            print(f"warning: word {palavra!r} not found in {plano}; using the start of the shot")
        return S[plano]["start"] + t

    # efeitos: colocados por plano/palavra, ducking −8 dB sob a voz
    sfx = np.zeros(n, np.float32)
    for e in cfg.get("sfx", []):
        x = ler(pasta / e["ficheiro"]) * 10 ** (e.get("gain_db", 0) / 20); i = int(t_de(e["plano"], e.get("palavra"), e.get("t", 0.0)) * SR)
        if i < n: sfx[i:i + len(x)] += x[:n - i]
    duck = 1 - (1 - 10 ** (-8 / 20)) * pres

    # música: uma faixa longa, RMS ativo −40 dBFS (≈20 dB sob a voz), +5 dB nas pausas, entrada e saída suaves
    mus = np.zeros(n, np.float32); m = cfg.get("musica")
    if m:
        base = ler(pasta / m["faixa"]); ent = m.get("entra", 0.0)
        t_in = max(0.0, (S[ent]["start"] - 0.3) if isinstance(ent, str) else float(ent)); t_out = TOT - 0.05
        need = int((t_out - t_in) * SR)
        if len(base) < need: raise SystemExit("the music track is shorter than the video: pick a longer one (never loop it)")
        seg = base[len(base) - need:] if m.get("alinhar", "fim") == "fim" else base[:need]
        i0 = int(t_in * SR); mus[i0:i0 + need] = seg * 10 ** ((-40 + m.get("gain_db", 0) - _rms_db(seg)) / 20)
        kf = lambda pts: np.interp(tt, [p[0] for p in pts], [p[1] for p in pts])
        g = 5.0 * (1 - pres) + kf([(0, -60), (t_in, -60), (t_in + 1.6, 0), (t_out - 1.6, 0), (t_out, -60), (TOT + 0.01, -60)])
        for plano, onde in m.get("cortes", []):
            tc = S[plano]["start"] if onde == "inicio" else S[plano]["start"] + S[plano]["dur"]
            g += kf([(0, 0), (tc - 0.45, 0), (tc - 0.35, -60), (tc + 0.05, -60), (tc + 0.4, 0), (TOT + 0.01, 0)])
        mus = (mus * 10 ** (g / 20)).astype(np.float32); mus[g < -59] = 0.0

    mix = voz + sfx * duck + mus
    raw = pasta / "mistura_bruta.wav"; wavfile.write(raw, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    meas = _loud(raw)
    af = (f"{LN}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
          f":measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true,volume=-0.5dB,aresample={SR}")
    dst = pasta / "mistura.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", af, "-ar", str(SR), str(dst)], check=True); raw.unlink()
    c = _loud(dst)
    print(f"mix: {dst}  {TOT:.2f} s | {c['input_i']} LUFS | true peak {c['input_tp']} dBTP | music: {'yes' if m else 'no'} | sfx: {len(cfg.get('sfx', []))}")
    return dst


def _loud(path) -> dict:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", LN + ":print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return json.loads(re.findall(r"\{[^{}]*\}", out)[-1])


def remux(video: Path, audio: Path, dur: float):
    """Troca só o áudio de um vídeo já renderizado (vídeo copiado, sem novo render)."""
    tmp = video.with_suffix(".audio_tmp.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.3f}",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)

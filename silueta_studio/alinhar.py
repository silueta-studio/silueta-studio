"""Forced alignment of the voice-over with WhisperX (wav2vec2, NO transcription): real timings per shot and per word.

STANDALONE script (stdlib + numpy + whisperx + ffmpeg only), run with the Python of the venv where WhisperX is installed:
    <python-with-whisperx> alinhar.py <story-folder>
`silueta align <folder> --python <...>` calls it this way and then maps the spoken words onto the caption text.

Input:  historia.json + voz/s01.mp3 (or .wav), voz/s02.mp3, ... (one file per shot, name = lower-case shot id).
        Spoken text = shot["fala"] if present (e.g. "GTA seis"), otherwise shot["voz"].
Output: timing.json [{id,start,dur,voice}], words_whisperx.json {id: [[word, t0, t1], ...]} (absolute time),
        voz.wav (trimmed and joined voice, 48 kHz), alinhamento.txt (report).
Trim:   0.12 s before the first word and 0.30 s after the last; shot["golpe"] = silence before, shot["cola"] = silence after.
"""
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

SR = 48000; ASR = 16000; PAD_IN, PAD_OUT = 0.12, 0.30


def load(path, sr):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"])
    return np.frombuffer(raw, np.float32).copy()


def norm(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def voz_de(pasta, sid):
    for ext in (".mp3", ".wav", ".m4a", ".flac"):
        p = pasta / "voz" / (sid.lower() + ext)
        if p.exists(): return p
    raise SystemExit(f"missing voice file for shot {sid}: {pasta / 'voz' / (sid.lower() + '.mp3')}")


def main(pasta):
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8")
        except Exception: pass
    pasta = Path(pasta).resolve()
    cfg = json.loads((pasta / "historia.json").read_text(encoding="utf-8-sig")); planos = cfg["planos"]
    fontes = {q["id"]: voz_de(pasta, q["id"]) for q in planos}          # falha cedo, antes de carregar o modelo
    import torch
    import whisperx
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model, meta = whisperx.load_align_model(language_code=cfg.get("idioma", "es"), device=dev)
    tracks, timing, spoken, rep = [], [], {}, []; t = 0.0
    for q in planos:
        sid = q["id"]; a = load(fontes[sid], SR); a16 = load(fontes[sid], ASR); ftxt = " ".join((q.get("fala") or q["voz"]).split())
        res = whisperx.align([{"start": 0.0, "end": len(a16) / ASR, "text": ftxt}], model, meta, a16, dev, return_char_alignments=False)
        ws = [w for s in res["segments"] for w in s.get("words", [])]
        if not ws: raise SystemExit(f"{sid}: alignment returned no words (does the voice match the text?)")
        for i, w in enumerate(ws):                                       # palavras sem tempo: interpolar
            if w.get("start") is None:
                pv = next((ws[j]["end"] for j in range(i - 1, -1, -1) if ws[j].get("end") is not None), 0.0)
                nx = next((ws[j]["start"] for j in range(i + 1, len(ws)) if ws[j].get("start") is not None), pv + 0.2)
                w["start"], w["end"] = pv, max(pv, nx)
            elif w.get("end") is None: w["end"] = w["start"] + 0.15
        lead = float(q.get("golpe", 0.0)); cola = float(q.get("cola", 0.0))
        c0 = max(0.0, ws[0]["start"] - PAD_IN); c1 = min(len(a) / SR, ws[-1]["end"] + PAD_OUT)
        clip = np.concatenate([np.zeros(int(lead * SR), np.float32), a[int(c0 * SR):int(c1 * SR)], np.zeros(int(cola * SR), np.float32)])
        dur = round(len(clip) / SR, 3); sh = lead - c0
        timing.append(dict(id=sid, start=round(t, 3), dur=dur, voice=q["voz"]))
        spoken[sid] = [[w["word"], round(t + w["start"] + sh, 3), round(t + w["end"] + sh, 3)] for w in ws]
        heard = " ".join(w["word"] for w in ws); ratio = difflib.SequenceMatcher(None, norm(ftxt), norm(heard)).ratio()
        rep.append(f"{sid} {t:7.2f}s dur {dur:5.2f}s  {len(ws)} words ({len(ws) / dur:.2f}/s)  match {ratio:.2f}\n   {ftxt}")
        print(rep[-1], flush=True); tracks.append(clip); t += dur
    (pasta / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "words_whisperx.json").write_text(json.dumps(spoken, ensure_ascii=False), encoding="utf-8")
    pcm = (np.clip(np.concatenate(tracks), -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", str(pasta / "voz.wav")], input=pcm, check=True)
    rep.append(f"TOTAL {t:.2f} s"); (pasta / "alinhamento.txt").write_text("\n".join(rep), encoding="utf-8"); print(f"TOTAL {t:.2f} s")


if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("usage: python alinhar.py <story-folder>")
    main(sys.argv[1])

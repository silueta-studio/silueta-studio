"""Quality gates (original implementation for this kit).

Before render
  determinism  static scan of the story's .py files (AST: unseeded randomness, clocks, uuid) + a dynamic check that
               re-renders sample frames in a different order and compares them pixel by pixel. Parallel render
               parts only join seamlessly if every frame depends on t alone.
  glyphs       every character of the captions/cards exists in the font (a missing one renders as a box).
  pace         spoken words per second per shot (≤ 3.5) and the pause before each shot.
After render (final.mp4)
  rhythm       no still stretch longer than 2 s, no shot shorter than 0.3 s, at most 3 flashes in any second
               (photosensitivity threshold of WCAG 2.3.1).
  loudness     integrated −14 LUFS ±1, true peak ≤ −1.5 dBTP, where the loudest moment falls and the silence before it.
A warning is not a verdict: open the frames and decide (impact flashes and dramatic pauses can be intentional).
The pace and loudness checks follow ideas from the NARRATION/SOUND review in cth9191/animate (MIT); see THIRD_PARTY.md.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import unicodedata
from pathlib import Path

import numpy as np
from PIL import ImageFont

from .config import FONT

# ------------------------------------------------------------------ determinism
_NP_OK = {"default_rng", "Generator", "SeedSequence", "PCG64", "Philox", "SFC64", "MT19937", "BitGenerator"}
_RANDOM_FUNCS = {"random", "randint", "uniform", "choice", "choices", "shuffle", "gauss", "sample", "randrange",
                 "normalvariate", "triangular", "betavariate", "expovariate", "getrandbits"}
_CLOCKS = {"time.time", "time.time_ns", "time.perf_counter", "time.perf_counter_ns", "time.monotonic", "time.process_time"}


def _dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute): parts.append(node.attr); node = node.value
    if isinstance(node, ast.Name): parts.append(node.id)
    return ".".join(reversed(parts))


def _problem(call: ast.Call) -> str | None:
    name = _dotted(call.func); last = name.rsplit(".", 1)[-1]; no_args = not call.args and not call.keywords
    if re.match(r"(np|numpy)\.random\.", name) and last not in _NP_OK: return "global NumPy RNG (no seed)"
    if last == "default_rng" and no_args: return "default_rng() without a seed"
    if name.startswith("random.") and last in _RANDOM_FUNCS: return "global random module (no seed)"
    if name == "random.Random" and no_args: return "random.Random() without a seed"
    if name in _CLOCKS: return "wall clock"
    if re.search(r"datetime\.(now|today|utcnow)$", name): return "wall clock (datetime)"
    if re.match(r"uuid\.uuid[14]$", name): return "uuid"
    return None


def static_determinism(folder: Path):
    found = []
    for f in sorted(Path(folder).glob("*.py")):
        try: tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), str(f))
        except SyntaxError as e: found.append(f"{f.name}:{e.lineno} syntax error: {e.msg}"); continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (why := _problem(node)):
                found.append(f"{f.name}:{node.lineno}  {why}  |  {ast.unparse(node)[:60]}")
    return not found, found or ["no unseeded randomness or clocks in the scene code"]


def dynamic_determinism(m):
    """Render sample frames forward, then in reverse after other frames: any pixel difference = hidden state."""
    T = m.T; times = sorted({round(T[0]["start"] + T[0]["dur"] * 0.5, 3), round(m.TOT * 0.5, 3), round(T[-1]["start"] + T[-1]["dur"] * 0.5, 3)})
    first = {t: m.frame(t) for t in times}; bad = []
    for t in reversed(times):
        m.frame(min(m.TOT - 0.01, t + 0.37))                                  # disturb any hidden state
        if not np.array_equal(first[t], m.frame(t)): bad.append(f"frame at {t:.2f}s changes between renders (shot {m.T[m._idx(t)]['id']})")
    return not bad, bad or [f"{len(times)} sample frames identical when re-rendered in another order"]


# ------------------------------------------------------------------ glyphs
def glyphs(texts: list[str], font_path=FONT):
    """Compare each character's bitmap with the font's 'missing glyph' bitmap (no extra dependency)."""
    f = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default(40)
    sig = lambda ch: (lambda mk: (mk.size, bytes(mk)))(f.getmask(ch))
    missing_sig = sig("\U0010FFFD")                                              # private-use code point: never in a font
    chars = {ch for t in texts for ch in t if not ch.isspace() and unicodedata.category(ch) not in ("Cf", "Zs", "Mn")}
    missing = sorted(ch for ch in chars if sig(ch) == missing_sig)
    name = Path(font_path).name if font_path else "Pillow default font"
    return not missing, [f"U+{ord(c):04X} {c!r} is not in {name}" for c in missing] or [f"{name} covers all {len(chars)} characters"]


# ------------------------------------------------------------------ pace
def pace(T, words, max_wps=3.5, min_pause=0.15):
    lines, fast, prev_end = [], [], None
    for shot in T:
        ws = [w for w in words.get(shot["id"], []) if w[1] is not None]
        if not ws: continue
        start, end = ws[0][1], ws[-1][2]; wps = len(ws) / max(end - start, 1e-3)
        gap = None if prev_end is None else start - prev_end; prev_end = end
        note = (" <- too fast" if wps > max_wps else "") + (" <- no pause before" if gap is not None and gap < min_pause else "")
        if wps > max_wps: fast.append(shot["id"])
        lines.append(f"{shot['id']:<6} {start:6.2f}s  {len(ws):3d} words  {wps:4.2f}/s  pause {'  -  ' if gap is None else f'{gap:4.2f}s'}{note}")
    lines.append(f"{len(fast)} shot(s) above {max_wps} words/s" + (": " + ", ".join(fast) if fast else ""))
    return not fast, lines


# ------------------------------------------------------------------ rhythm (rendered video)
def _gray(video, fps, width):
    meta = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                               "stream=width,height:format=duration", "-of", "json", str(video)]))
    st = meta["streams"][0]; h = 2 * round(width * st["height"] / st["width"] / 2)
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={width}:{h},format=gray",
                                   "-f", "rawvideo", "-"])
    n = len(raw) // (width * h)
    return np.frombuffer(raw[:n * width * h], np.uint8).reshape(n, h, width).astype(np.int16), float(meta["format"]["duration"])


def _runs(mask):
    """[(start, end)) index ranges where mask is True."""
    out, s = [], None
    for i, v in enumerate(list(mask) + [False]):
        if v and s is None: s = i
        elif not v and s is not None: out.append((s, i)); s = None
    return out


def rhythm(video: Path, max_still=2.0, min_shot=0.3, max_flashes=3):
    g10, dur = _gray(video, 10, 180)
    act = np.percentile(np.abs(np.diff(g10, axis=0)), 99.5, axis=(1, 2)) >= 12          # something visibly moved
    still = [(a / 10, b / 10) for a, b in _runs(~act) if (b - a) / 10 > max_still]
    g30, _ = _gray(video, 30, 120)
    luma = g30.mean(axis=(1, 2)); jump = np.abs(np.diff(g30, axis=0)).mean(axis=(1, 2))
    flashes = []
    for i in range(1, len(luma)):
        if luma[i] > 100 and luma[i] - luma[max(0, i - 4):i].min() >= 45 and (not flashes or i / 30 - flashes[-1] > 0.15):
            flashes.append(i / 30)
    risky = [t for t in flashes if sum(t <= u < t + 1 for u in flashes) > max_flashes]
    near_flash = lambda t: any(f - 0.15 <= t <= f + 0.5 for f in flashes)
    cuts = [(a + 1) / 30 for a, _ in _runs(jump > 35)]                                    # consecutive cut frames = one cut
    edges = [0.0] + [c for c in cuts if not near_flash(c)] + [dur]
    short = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] - edges[i] < min_shot]
    lines = [f"{len(cuts)} hard cuts, {len(flashes)} flashes, longest still stretch "
             f"{max([b - a for a, b in _runs(~act)] or [0]) / 10:.1f}s (limit {max_still}s)"]
    lines += [f"FAIL nothing moves from {a:.1f}s to {b:.1f}s" for a, b in still]
    lines += [f"FAIL shot {a:.2f}–{b:.2f}s is shorter than {min_shot}s" for a, b in short]
    lines += [f"FAIL more than {max_flashes} flashes within 1 s from {t:.2f}s (photosensitivity)" for t in risky[:1]]
    if flashes and not risky: lines.append("flashes (intentional?): " + ", ".join(f"{t:.2f}s" for t in flashes))
    return not (still or short or risky), lines


# ------------------------------------------------------------------ loudness
def has_audio(media: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(media)],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def loudness(media: Path, T=None, target=-14.0, peak_max=-1.5):
    SR = 48000
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(media), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32) if r.returncode == 0 else np.zeros(0, np.float32)
    n = len(x) // (SR // 10)
    if n < 10: return False, ["no audio track (run `silueta mix`, or add voz.wav/mistura.wav and render again)"]
    db = 20 * np.log10(np.sqrt((x[:n * (SR // 10)].reshape(n, -1) ** 2).mean(axis=1)) + 1e-9)
    k = int(np.argmax(db)); before = db[max(0, k - 20):k] <= -40
    silence = max([b - a for a, b in _runs(before)] or [0]) / 10
    shot = next((s["id"] for s in (T or []) if s["start"] <= k / 10 < s["start"] + s["dur"]), "-")
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(media), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    grab = lambda rx: (lambda mt: float(mt.group(1)) if mt else None)(re.search(rx, log))
    I = grab(r"Integrated loudness:[\s\S]*?I:\s+(-?[\d.]+) LUFS"); TP = grab(r"True peak:[\s\S]*?Peak:\s+(-?[\d.]+) dBFS")
    ok_i = I is not None and abs(I - target) <= 1.0; ok_p = TP is not None and TP <= peak_max + 0.05
    return ok_i and ok_p, [f"loudest moment {k / 10:.1f}s ({db[k]:.1f} dBFS) in shot {shot}; silence before it {silence:.1f}s",
                           f"integrated {I} LUFS (target {target}±1) {'ok' if ok_i else 'OUT'} | true peak {TP} dBTP (max {peak_max}) {'ok' if ok_p else 'OUT'}"]


# ------------------------------------------------------------------ runner
def run(folder, dynamic=True) -> bool:
    """Run every gate that applies to the story folder; True if all passed."""
    folder = Path(folder).resolve(); cfg = json.loads((folder / "historia.json").read_text(encoding="utf-8-sig"))
    texts = [p.get("voz", "") for p in cfg["planos"]] + [p.get("texto", "") for p in cfg["planos"]]
    tp = folder / "timing.json"; wp = folder / "words_whisperx.json"; final = folder / "final.mp4"
    T = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else None
    gates = [("determinism (code)", lambda: static_determinism(folder))]
    if dynamic:
        def _dyn():
            from .montagem import Montagem
            return dynamic_determinism(Montagem(folder))
        gates.append(("determinism (frames)", _dyn))
    gates.append(("glyphs", lambda: glyphs(texts)))
    if T and wp.exists(): gates.append(("pace", lambda: pace(T, json.loads(wp.read_text(encoding="utf-8")))))
    skipped = []
    if final.exists():
        gates.append(("rhythm", lambda: rhythm(final)))
        if T is None and not has_audio(final):      # no voice recorded yet: nothing to measure, not a failure
            skipped.append(("loudness", "no voice yet (timings are estimated): record voz/s01.mp3..., then `silueta align` and `silueta mix`"))
        else:
            gates.append(("loudness", lambda: loudness(final, T)))
    failed = 0
    for name, fn in gates:
        ok, lines = fn(); failed += not ok
        print(f"\n  {name.upper()}: {'ok' if ok else 'FAILED'}")
        for line in lines: print("     " + line)
    for name, why in skipped: print(f"\n  {name.upper()}: skipped\n     {why}")
    if not final.exists(): print("\n  (rhythm and loudness run after `silueta render`)")
    print(f"\n  {'ALL GATES PASSED' if not failed else f'{failed} GATE(S) FAILED'}\n")
    return not failed

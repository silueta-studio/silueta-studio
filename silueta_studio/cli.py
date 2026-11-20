"""Command line: silueta new | sheet | frame | align | mix | render | qa   (silueta <command> -h for help).

Portuguese aliases are kept for the original channel's scripts: novo, prova, fotograma, alinhar, misturar.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

MODELO = Path(__file__).parent / "modelo"


def cmd_new(a):
    dest = Path(a.folder)
    if dest.exists() and any(dest.iterdir()): raise SystemExit(f"{dest} already exists and is not empty")
    dest.mkdir(parents=True, exist_ok=True)
    for n in ("historia.json", "cenas.py"): shutil.copyfile(MODELO / n, dest / n)
    if a.title:
        p = dest / "historia.json"; cfg = json.loads(p.read_text(encoding="utf-8")); cfg["titulo"] = a.title
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"story created in {dest.resolve()}\n  1) edit historia.json (shots and voice-over text)\n  2) draw each shot in cenas.py\n"
          f"  3) silueta sheet {a.folder}")


def cmd_sheet(a):
    from .montagem import Montagem
    warnings = Montagem(a.folder).prova()
    raise SystemExit(1 if (warnings and a.strict) else 0)


def cmd_frame(a):
    from PIL import Image
    from .montagem import Montagem
    m = Montagem(a.folder); q = []; out = Path(a.folder) / f"fotograma_{a.t:.2f}.png"
    Image.fromarray(m.frame(a.t, q)).save(out); print(out, *(q or ["QA ok"]), sep="\n  ")


def cmd_align(a):
    import os
    import subprocess
    from . import palavras
    folder = Path(a.folder).resolve(); py = a.python or os.environ.get("SILUETA_WHISPERX_PY") or sys.executable
    script = Path(__file__).parent / "alinhar.py"
    r = subprocess.run([py, "-I", str(script), str(folder)])          # -I: isolated, the package folder is not on sys.path
    if r.returncode: raise SystemExit("alignment failed (is WhisperX installed in that Python? pass --python <venv>/Scripts/python)")
    cfg = json.loads((folder / "historia.json").read_text(encoding="utf-8-sig"))
    spoken = json.loads((folder / "words_whisperx.json").read_text(encoding="utf-8"))
    out = palavras.mapear(cfg["planos"], spoken, cfg.get("idioma", "es"), cfg.get("alias"))
    (folder / "words.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"words.json: {len(out)} shots with script words -> next: silueta sheet {a.folder}")


def cmd_mix(a):
    from . import audio
    from .historia import Historia
    dst = audio.misturar(a.folder); final = Path(a.folder) / "final.mp4"
    if final.exists():
        T, _ = Historia(a.folder).timing(); audio.remux(final, dst, T[-1]["start"] + T[-1]["dur"])
        print(f"audio replaced in {final} (video stream copied, no re-render); run `silueta render` to refresh the review copy")


def cmd_render(a):
    from .montagem import Montagem
    Montagem(a.folder).render(force=a.force, parte=a.part, crf=a.crf, vagas=a.jobs, uma_vaga=a.one_wave, leve=not a.no_review)


def cmd_qa(a):
    from . import qa
    raise SystemExit(0 if qa.run(a.folder, dynamic=not a.fast) else 1)


def cmd_part(a):
    """Internal: one render process per part (called by the parallel render)."""
    from .montagem import Montagem
    m = Montagem(a.folder); m.render_parte(a.a0, a.a1, m.pasta / "render_partes" / f"p{a.a0:06d}.mp4", a.crf)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
        except Exception: pass
    ap = argparse.ArgumentParser(prog="silueta", description="Vertical story videos with 2D silhouettes and karaoke captions.")
    sp = ap.add_subparsers(dest="cmd", required=True, metavar="{new,sheet,frame,align,mix,render,qa}")

    def sub(name, alias, help_, fn, folder_optional=True):
        p = sp.add_parser(name, aliases=[alias], help=help_)
        if folder_optional: p.add_argument("folder", nargs="?", default=".")
        else: p.add_argument("folder")
        p.set_defaults(fn=fn); return p

    p = sub("new", "novo", "create a story folder from the example", cmd_new, False); p.add_argument("--title", default="")
    p = sub("sheet", "prova", "contact sheet (1 frame per shot) + safe-zone QA -> prova.png", cmd_sheet)
    p.add_argument("--strict", action="store_true", help="exit with an error if there are QA warnings")
    p = sub("frame", "fotograma", "save the frame at time t", cmd_frame, False); p.add_argument("t", type=float)
    p = sub("align", "alinhar", "real voice timings with WhisperX (voz/s01.mp3...) -> timing.json, words.json, voz.wav", cmd_align)
    p.add_argument("--python", default="", help="Python of a venv where WhisperX is installed")
    sub("mix", "misturar", "voice + your licensed music/SFX (historia.json) with ducking -> mistura.wav at -14 LUFS", cmd_mix)
    p = sub("render", "renderizar", "parallel, resumable render -> final.mp4 + final_revisao.mp4", cmd_render)
    p.add_argument("--force", action="store_true", help="accept estimated timings (tests only)")
    p.add_argument("--part", type=int, default=60, help="frames per part"); p.add_argument("--crf", type=int, default=17)
    p.add_argument("--jobs", type=int, default=0, help="parallel processes (default: physical cores - 1)")
    p.add_argument("--one-wave", action="store_true", help="render one wave of parts and exit (run again to resume)")
    p.add_argument("--no-review", action="store_true", help="skip the light review copy")
    p = sub("qa", "verificar", "quality gates (determinism, glyphs, pace; rhythm and loudness on final.mp4)", cmd_qa)
    p.add_argument("--fast", action="store_true", help="skip the dynamic determinism check (re-rendering sample frames)")
    p = sp.add_parser("_part"); p.add_argument("folder"); p.add_argument("a0", type=int); p.add_argument("a1", type=int)
    p.add_argument("crf", type=int); p.set_defaults(fn=cmd_part)
    a = ap.parse_args(argv); a.fn(a)


if __name__ == "__main__":
    main()

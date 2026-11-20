"""Configuração global: formato do vídeo e procura da fonte em qualquer sistema."""
from __future__ import annotations

import os
import sys
from pathlib import Path

W, H = 1080, 1920   # vertical 9:16
FPS = 30
S = 2               # super-amostragem das máscaras (antialias)

# Zona segura do texto (as apps tapam o topo e o fundo)
SAFE_Y0, SAFE_Y1 = 150, 1500
MARGIN = 60

_CANDIDATAS = [
    os.environ.get("SILUETA_FONT", ""),
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def _matplotlib_font() -> str:
    try:
        import matplotlib  # opcional
        p = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
        return str(p) if p.exists() else ""
    except Exception:
        return ""


def find_font() -> str:
    """Devolve o caminho de uma fonte negrita TrueType; '' = usar a fonte embutida do Pillow."""
    for c in _CANDIDATAS + [_matplotlib_font()]:
        if c and Path(c).exists():
            return c
    return ""


FONT = find_font()

if not FONT and sys.flags.dev_mode:
    print("[silueta] warning: no TrueType font found; using Pillow's default (set SILUETA_FONT).")

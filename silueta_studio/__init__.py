"""Silueta Studio — vertical story videos with 2D silhouettes, rim light and karaoke captions.

Use in a story (cenas.py):
    from silueta_studio import cena, push, sky, terr, fg, fin, pessoa, card
"""
__version__ = "0.1.1"

from .camara import Cam, fg, push, ridge, sky, terr
from .canvas import R, addglow, blank, ease, font, full, grade, mask_full, smooth_noise, spring, vgrad, xf
from .cenas import cena
from .config import FPS, H, MARGIN, SAFE_Y0, SAFE_Y1, W
from .efeitos import brasas, chispas, disco, fin, flashk, grain, haze, rayos, softblob, sombra, temblor
from .figuras import ave, barco, pessoa, put
from .texto import card, fit, hud, label, topband

__all__ = [n for n in dir() if not n.startswith("_")]

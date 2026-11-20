"""Palavras faladas (WhisperX) → palavras do karaoke (texto do guião, com cifras e pontuação).

O alinhamento devolve o que a voz DIZ («mil novecientos sesenta y dos»); o karaoke mostra o guião («1962.»).
Cada token do guião é expandido à forma falada esperada, alinhado com difflib (tolera erros) e recebe o início da
primeira palavra falada correspondente e o fim da última; tokens sem par são interpolados entre os vizinhos.
Números por extenso: espanhol (idioma "es"); outros idiomas usam só o alinhamento de texto.
Aliases por história em historia.json: "alias": {"grafia_ouvida": "grafia_canonica"}.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
      "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidos",
      "veintitres", "veinticuatro", "veinticinco", "veintiseis", "veintisiete", "veintiocho", "veintinueve"]
_D = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_C = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
      7: "setecientos", 8: "ochocientos", 9: "novecientos"}
SYMB = {"%": ["por", "ciento"], "°c": ["grados"], "+": ["mas", "de"]}


def num_es(n: int) -> str:
    """Inteiro 0..999 999 999 → palavras em espanhol (sem acentos)."""
    if n < 30: return _U[n]
    if n < 100: return _D[n // 10] + ("" if n % 10 == 0 else " y " + _U[n % 10])
    if n < 1000: return "cien" if n == 100 else _C[n // 100] + ("" if n % 100 == 0 else " " + num_es(n % 100))
    if n < 1_000_000:
        k, r = divmod(n, 1000); kw = num_es(k)
        head = "mil" if k == 1 else (kw[:-3] + "un" if kw.endswith("uno") else kw) + " mil"
        return head + ("" if r == 0 else " " + num_es(r))
    m, r = divmod(n, 1_000_000); mw = num_es(m)
    head = "un millon" if m == 1 else (mw[:-3] + "un" if mw.endswith("uno") else mw) + " millones"
    return head + ("" if r == 0 else " " + num_es(r))


def _sem_acentos(s): return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def falado(tok: str, idioma="es", alias=None) -> list[str]:
    """Token → lista de palavras faladas normalizadas (minúsculas, sem acentos nem pontuação)."""
    t = _sem_acentos(tok.lower())
    t = re.sub(r"(\d)\.(\d{3})", r"\1\2", t)                     # 5.500 → 5500
    t = re.sub(r"[«»\"“”()¿?¡!.,;:…~·]", " ", t)
    out = []
    for part in t.split():
        if part in SYMB: out += SYMB[part]; continue
        for piece in re.split(r"(\d+)", part.replace("-", " ")):
            for w in piece.split():
                if w.isdigit(): out += num_es(int(w)).split() if idioma == "es" and int(w) < 10**9 else [w]
                elif w: out.append(w)
    alias = alias or {}
    return [alias.get(w, w) for w in out]


def mapear_plano(texto: str, faladas: list, idioma="es", alias=None) -> list:
    toks = texto.split(); exp, dono = [], []
    for i, tk in enumerate(toks):
        for w in falado(tk, idioma, alias): exp.append(w); dono.append(i)
    act, aidx = [], []
    for j, (w, _, _) in enumerate(faladas):
        for x in falado(str(w), idioma, alias): act.append(x); aidx.append(j)
    t0 = [None] * len(toks); t1 = [None] * len(toks)

    def put(k, b):
        ti = dono[k]; sw = faladas[aidx[b]]
        t0[ti] = sw[1] if t0[ti] is None else min(t0[ti], sw[1]); t1[ti] = sw[2] if t1[ti] is None else max(t1[ti], sw[2])

    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, exp, act, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(a2 - a1): put(a1 + k, b1 + k)
        elif op == "replace":                                        # palavra mal ouvida: reparte o troço falado
            for k in range(a1, a2):
                q0 = b1 + (k - a1) * (b2 - b1) // (a2 - a1); q1 = max(q0, b1 + (k - a1 + 1) * (b2 - b1) // (a2 - a1) - 1)
                for q in range(q0, q1 + 1): put(k, q)
    n = len(toks); i = 0
    beg = faladas[0][1] if faladas else 0.0; end = faladas[-1][2] if faladas else 0.0
    while i < n:
        if t0[i] is not None: i += 1; continue
        j = i
        while j < n and t0[j] is None: j += 1
        a = t1[i - 1] if i > 0 else beg; b = t0[j] if j < n else end; step = (b - a) / (j - i)
        for k in range(i, j): t0[k] = a + step * (k - i); t1[k] = a + step * (k - i + 1)
        i = j
    return [[tk, round(a, 3), round(b, 3)] for tk, a, b in zip(toks, t0, t1)]


def mapear(planos: list, faladas: dict, idioma="es", alias=None) -> dict:
    return {p["id"]: mapear_plano(p["voz"], faladas[p["id"]], idioma, alias) for p in planos if p["id"] in faladas}

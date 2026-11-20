"""Testes do kit: `python -m pytest` dentro de kit_video (os de render precisam de ffmpeg no PATH)."""
import json
import shutil
import subprocess

import numpy as np
import pytest

from silueta_studio import cli, palavras, qa
from silueta_studio.historia import Historia
from silueta_studio.karaoke import Karaoke
from silueta_studio.config import MARGIN, W

MODELO = cli.MODELO
FFMPEG = shutil.which("ffmpeg") is not None


@pytest.fixture
def historia(tmp_path):
    d = tmp_path / "h"; cli.main(["new", str(d)]); return d


# ------------------------------------------------------------------ palavras
def test_numeros_em_espanhol():
    assert palavras.num_es(1962) == "mil novecientos sesenta y dos"
    assert palavras.num_es(21000) == "veintiun mil"
    assert palavras.num_es(100) == "cien"
    assert palavras.num_es(6_300_000) == "seis millones trescientos mil"


def test_mapear_cifra_e_palavra_mal_ouvida():
    faladas = [["Hoy", 0.0, 0.2], ["sale", 0.3, 0.5], ["GTA", 0.6, 0.9], ["seis.", 1.0, 1.3], ["Báinans", 1.5, 2.0]]
    out = palavras.mapear_plano("Hoy sale GTA 6. Binance", faladas, alias={"bainans": "binance"})
    assert [w[0] for w in out] == ["Hoy", "sale", "GTA", "6.", "Binance"]
    assert out[3][1:] == [1.0, 1.3] and out[4][1:] == [1.5, 2.0]
    out = palavras.mapear_plano("uno dos tres", [["uno", 0, 0.2], ["xxx", 0.3, 0.5], ["tres", 0.6, 0.8]])
    assert out[1][1] >= out[0][2] and out[1][2] <= out[2][1]          # palavra sem par: fica entre os vizinhos


# ------------------------------------------------------------------ história e karaoke
def test_historia_modelo_e_palavras_estimadas(historia):
    h = Historia(historia); T, src = h.timing(); W_, wsrc = h.words(T)
    assert src == wsrc == "estimated" and [x["id"] for x in T] == ["S01", "S02", "S03"]
    for x in T:
        ws = W_[x["id"]]; assert ws
        assert all(a < b for _, a, b in ws) and all(ws[i][2] <= ws[i + 1][1] for i in range(len(ws) - 1))
        assert x["start"] <= ws[0][1] and ws[-1][2] <= x["start"] + x["dur"]


def test_historia_rejeita_transicao_invalida(historia):
    p = historia / "historia.json"; d = json.loads(p.read_text(encoding="utf-8"))
    d["transicoes"]["S02"] = ["explosao", 0.3]; p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        Historia(historia)


def test_karaoke_paginas_dentro_da_margem():
    ws = [[w, i * 0.4, i * 0.4 + 0.3] for i, w in enumerate("Extraordinariamente incomprensiblemente la historia más rara jamás contada".split())]
    K = Karaoke({"S01": ws}, {"S01": 1290})
    assert all(len(p[2]) <= 5 for p in K.pages)
    for p in K.pages:
        x0, y0, x1, y1 = p[4]; assert x0 >= MARGIN - 1 and x1 <= W - MARGIN + 1 and y1 <= 1500
    lay, boxes = K.layer(0.1); assert lay is not None and boxes


# ------------------------------------------------------------------ montagem
def test_prova_do_modelo_sem_avisos_e_fotogramas_deterministas(historia):
    from silueta_studio.montagem import Montagem
    m = Montagem(historia)
    assert m.prova() == [] and (historia / "prova.png").exists()
    a = m.frame(2.0); b = m.frame(2.0)
    assert a.shape == (1920, 1080, 3) and a.dtype == np.uint8 and np.array_equal(a, b)
    assert m.frame(m.T[1]["start"] + 0.2).mean() > 5                  # a meio de uma transição não fica preto


def test_cli_novo_recusa_pasta_com_ficheiros(historia):
    with pytest.raises(SystemExit):
        cli.main(["new", str(historia)])


# ------------------------------------------------------------------ qa
def test_qa_apanha_aleatoriedade_glifos_e_ritmo_de_leitura(tmp_path):
    (tmp_path / "cenas.py").write_text("import numpy as np\nx = np.random.rand()\nr = np.random.default_rng(3)\n", encoding="utf-8")
    ok, linhas = qa.static_determinism(tmp_path); assert not ok and len(linhas) == 1
    ok, linhas = qa.glyphs(["¿Qué año? ¡Sí! «ñ» …", "★"]); assert not ok and "U+2605" in linhas[0]
    ok, _ = qa.glyphs(["¿Qué año? ¡Sí! «ñ» … ÁÉÍÓÚü — 6.300 €"]); assert ok
    T = [{"id": "S01", "start": 0, "dur": 2}]; ws = {"S01": [[f"p{i}", i * 0.2, i * 0.2 + 0.15] for i in range(10)]}
    ok, _ = qa.pace(T, ws); assert not ok


def test_qa_dinamico_apanha_estado_escondido(historia):
    from silueta_studio.montagem import Montagem
    assert qa.dynamic_determinism(Montagem(historia))[0]
    p = historia / "cenas.py"
    src = p.read_text(encoding="utf-8"); alvo = '    fin(f)\n    card(f, "40 AÑOS"'
    assert alvo in src
    p.write_text(src.replace(alvo, "    f += np.random.rand() * 40\n" + alvo), encoding="utf-8")
    assert not qa.dynamic_determinism(Montagem(historia))[0]


@pytest.mark.skipif(not FFMPEG, reason="precisa de ffmpeg")
def test_qa_ritmo_clarões_e_imagem_parada(tmp_path):
    def mk(name, frames):
        p = tmp_path / name
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "108x192", "-r", "30",
                               "-i", "-", "-pix_fmt", "yuv420p", str(p)], stdin=subprocess.PIPE)
        for fr in frames: ff.stdin.write(fr.astype(np.uint8).tobytes())
        ff.stdin.close(); ff.wait(); return p
    flash = [np.full((192, 108), 230 if i % 6 < 2 else 20) for i in range(90)]
    assert not qa.rhythm(mk("flash.mp4", flash))[0]
    still = [np.full((192, 108), 60) for _ in range(120)]
    assert not qa.rhythm(mk("still.mp4", still))[0]
    calm = [np.clip(np.full((192, 108), 60) + np.roll(np.arange(108), i)[None, :], 0, 255) for i in range(120)]
    assert qa.rhythm(mk("calm.mp4", calm))[0]


# ------------------------------------------------------------------ render (integração)
@pytest.mark.skipif(not FFMPEG, reason="precisa de ffmpeg")
def test_render_paralelo_curto(tmp_path):
    d = tmp_path / "curta"; d.mkdir()
    (d / "historia.json").write_text(json.dumps({"titulo": "t", "planos": [
        {"id": "S01", "dur": 0.6, "voz": "Uno dos."}, {"id": "S02", "dur": 0.6, "voz": "Tres cuatro."}],
        "transicoes": {"S02": ["whip", 0.2]}}), encoding="utf-8")
    (d / "cenas.py").write_text(
        "from silueta_studio import cena, sky, fin, card\n"
        "@cena('S01')\ndef a(f, tl, d, c):\n    sky(f, 'a', [(0, (40, 60, 120)), (1, (200, 120, 60))]); f += tl * 40; fin(f)\n"
        "@cena('S02')\ndef b(f, tl, d, c):\n    sky(f, 'b', [(0, (10, 10, 30)), (1, (60, 30, 30))]); fin(f); card(f, 'FIM', (540, 400), 100, tl, 0.1)\n",
        encoding="utf-8")
    cli.main(["render", str(d), "--force", "--part", "10", "--jobs", "2", "--no-review"])
    out = d / "final.mp4"; assert out.exists() and not (d / "render_partes").exists()
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
                                               "-of", "json", str(out)]))
    assert abs(float(info["format"]["duration"]) - 1.2) < 0.1 and info["streams"][0]["width"] == 1080

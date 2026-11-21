# Contributing

Thanks for helping! Small, focused pull requests are easiest to review.

1. Fork, then `python -m venv .venv`, activate it and `pip install -e ".[dev]"` (needs ffmpeg on your PATH).
2. Make your change and run `python -m pytest -q` — all tests must pass.
3. If you touch drawing code, run `silueta sheet <example>` and attach the contact sheet (`prova.png`) to the PR.

**House rules**
- Everything visual is drawn in code: no photos, logos, film stills or third-party characters.
- Never commit music, sound effects or voice files — the kit ships none.
- Randomness only with a fixed seed (`np.random.default_rng(seed)`), never clocks: parallel render parts must match.
- Example stories that state real facts need two independent sources in the PR description.

By contributing you agree that your contribution is licensed under the MIT licence of this project.

---
**Español:** los PR pequeños y con un solo objetivo son bienvenidos. Instala con `pip install -e ".[dev]"`, pasa `python -m pytest -q`
y, si tocas el dibujo, adjunta la hoja de prueba (`silueta sheet`). Nada de fotos, logos, música ni voces en el repositorio.

# Third-party code and ideas

| Part of the kit | Origin | Licence |
|---|---|---|
| `silueta_studio/qa.py` — pace and loudness gates | ideas from the NARRATION/SOUND review in `tools/review.mjs` of *cth9191/animate* (words per second, pause before each shot, loudest moment and the silence before it); re-implemented in Python, no code copied | MIT |
| `silueta_studio/qa.py` — flash limit | the "three flashes in any one-second period" threshold of WCAG 2.1, success criterion 2.3.1 (W3C) | W3C standard (idea only) |
| `silueta_studio/alinhar.py` — forced alignment | calls *WhisperX* (m-bain/whisperX) and its wav2vec2 alignment models; not bundled, the user installs it | BSD-2-Clause (WhisperX); model licences per model |

All other code (drawing engine, camera, effects, karaoke, timing, mix, render, determinism/glyph/rhythm gates) was written for this project.

Runtime dependencies (installed by pip, not bundled): numpy (BSD-3-Clause), Pillow (MIT-CMU), SciPy (BSD-3-Clause).
`ffmpeg` is required on PATH and is not bundled.

The kit ships **no music, sound effects, photographs, logos or fonts**. Everything visual is drawn in code. Bring your own licensed audio.

## Notices

**cth9191/animate** — MIT License, Copyright (c) 2026 cth9191. The MIT text is the same as `LICENSE` in this repository.

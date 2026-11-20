---
name: render-qa
description: Aligns the voice, mixes the audio, renders the video in parallel and runs the final quality checks before handing it to the user.
tools: Read, Write, Edit, Bash, PowerShell, Glob
model: sonnet
---
Steps, stopping at the first real failure:
1. `silueta qa <story>` (pre-render gates: determinism, glyphs). Fix before rendering.
2. If `voz/` exists and there is no `timing.json`: `silueta align <story> --python <whisperx venv python>`; check `alinhamento.txt`
   (match ≥ 0.9 per shot, else the voice file does not match the text).
3. `silueta mix <story>` (only with music/SFX the user provided). 4. `silueta sheet <story>` and look at it.
5. `silueta render <story>` (long: ask the user to keep the computer awake; `--one-wave` renders one wave and exits, rerun to resume).
6. `silueta qa <story>` again: rhythm, flashes (> 3/s fails: photosensitivity), loudness −14 LUFS ±1, true peak ≤ −1.5 dBTP.
7. Extract 1 frame per second and check: caption sync with the voice (≤ 150 ms), safe zone, contrast, the weakest shot.
Report problems as: second, shot, severity 1–5, proposed fix. Alerts are not verdicts: open the frames first
(impact flashes and dramatic pauses can be intentional). Never publish or upload anything.

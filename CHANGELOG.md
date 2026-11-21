# Changelog

## 0.1.1 — unreleased
- `silueta qa`: the loudness gate is **skipped** (not failed) while a story has no voice yet, so the example finishes green
  on a fresh install. With real timings and no audio track it still fails.
- CI on Ubuntu, Windows and macOS (Python 3.10 and 3.12).

## 0.1.0 — 2026-11-20
First public version: engine (silhouettes, parallax camera, rim light, karaoke, transitions, grain), `new`, `sheet`, `frame`,
`align` (WhisperX forced alignment), `mix` (voice levelling, music/SFX ducking, −14 LUFS), parallel resumable `render`,
`qa` gates, Claude Code `CLAUDE.md` and 4 agents, example story "El farero".

# Gaming Content Factory

Automated gaming content pipeline: OBS capture, a PySide6 desktop GUI, and a Blender 5.3
Geometry Nodes ASCII renderer.

## What is here

- `gcf/` — capture, project, preset, tone-mapping and render pipeline.
- `ascii/presets/` — approved Blender presets, including `ASCII_Cinematic_Balanced_v2_96x54.blend`.
- `docs/` — design notes and validation reports, including the ASCII spatial tone-mapping gate.
- `tests/` — pipeline tests.
- `assets/` — fonts, music placeholders and preset data.

Large outputs are intentionally not versioned: `projects/`, `_discovery/`, `ascii/render/`
and `ascii/experiments/`.

## Requirements

- Python 3.13 (the local virtualenv uses it).
- `ffmpeg` and `ffprobe` available in `PATH`.
- Blender 5.3 at the default path, or set `BLENDER_PATH`.
- OBS WebSocket settings in `config/obs_ws.json` (created by the capture setup; not committed).

## Run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m gcf gui
```

`GamingContentFactory.vbs` is the Windows launcher used on the original machine; it assumes
the repository is at `G:\VDGP`. Use the `python -m gcf gui` command elsewhere.

## Documentation

Start with `docs/STATUS.md`. The ASCII renderer notes are in `docs/ASCII_*.md`; the latest
spatial tone-mapping validation is `docs/ASCII_SPATIAL_MOTION_VALIDATION.md`.

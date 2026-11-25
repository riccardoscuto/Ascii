from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from gcf.ascii import media, preset
from gcf.ascii import render as ascii_render
from gcf.ascii.project import AsciiProject
from gcf.config import ffmpeg_bin

MODES = {
    "adaptive": ("glyph-library", "adaptive"),
    "highlight": ("glyph-library", "compress"),
    "decoupled": ("glyph-library-decoupled", "compress"),
}
MODE_LABELS = {
    "adaptive": "Adaptive",
    "highlight": "Highlight Compression",
    "decoupled": "Decoupled",
}
COLORS = {
    "original": (0.0, 0.0),
    "amber": (1.0, 0.0),
    "steel": (1.0, 1.0),
}
COLOR_LABELS = {
    "original": "Original RGB",
    "amber": "Cinematic Amber",
    "steel": "Steel Blue",
}
DEFAULT_SETTINGS = {
    "mode": "adaptive",
    "density": 81,
    "color": "original",
    "gamma": 0.82,
    "shadow": 0.31,
    "contrast_high": 0.85,
    "start": None,
    "duration": 2.0,
    "overrides": {},
}


def _sha1(path: str | Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def normalize_settings(settings: dict | None = None) -> dict:
    data = {**DEFAULT_SETTINGS, **(settings or {})}
    mode = data.get("mode", "adaptive")
    if mode not in MODES:
        raise ValueError(f"Modalità ASCII non valida: {mode}")
    color = data.get("color", "original")
    if color not in COLORS:
        raise ValueError(f"Colore ASCII non valido: {color}")
    data["mode"] = mode
    data["color"] = color
    data["density"] = max(32, min(160, int(data.get("density", 81))))
    data["duration"] = max(0.5, min(20.0, float(data.get("duration", 2.0))))
    data["gamma"] = max(0.5, min(1.5, float(data.get("gamma", 0.82))))
    data["shadow"] = max(0.1, min(0.6, float(data.get("shadow", 0.31))))
    data["contrast_high"] = max(0.5, min(1.0, float(data.get("contrast_high", 0.85))))
    data["overrides"] = dict(data.get("overrides") or {})
    if data.get("start") is not None:
        data["start"] = max(0.0, float(data["start"]))
    return data


def clip_source(project, game, slot: int) -> Path | None:
    return project.clip_mp4(game, slot)


def _settings_params(settings: dict) -> tuple[float, float, dict]:
    color_mode, palette = COLORS[settings["color"]]
    params = {
        "density": int(settings["density"]),
        "gamma": float(settings["gamma"]),
        "shadow": float(settings["shadow"]),
        "contrast_high": float(settings["contrast_high"]),
        "color_mode": color_mode,
        "palette": palette,
        "youtube_mbps": 18,
    }
    return color_mode, palette, params


def _segment(settings: dict, info: dict) -> tuple[float, float]:
    duration = min(float(settings["duration"]), max(0.5, float(info["duration"])))
    start = settings.get("start")
    if start is None:
        start = max(0.0, (float(info["duration"]) - duration) / 2.0)
    start = min(max(0.0, float(start)), max(0.0, float(info["duration"]) - duration))
    return round(start, 3), round(duration, 3)


def fingerprint(project, game, slot: int, settings: dict | None = None,
                source: Path | None = None) -> str:
    settings = normalize_settings(settings)
    source = Path(source) if source else clip_source(project, game, slot)
    if not source or not source.exists():
        raise FileNotFoundError("Clip originale mancante.")
    info = media.probe(source)
    start, duration = _segment(settings, info)
    _, _, params = _settings_params(settings)
    payload = {
        "source": _sha1(source),
        "renderer": MODES[settings["mode"]],
        "renderer_version": preset.RENDERER_VERSIONS[MODES[settings["mode"]][0]],
        "format": "vertical",
        "start": start,
        "duration": duration,
        "params": params,
        "overrides": settings["overrides"],
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_project(project, game, slot: int, settings: dict | None = None,
                  source: Path | None = None) -> AsciiProject:
    settings = normalize_settings(settings)
    source = Path(source) if source else clip_source(project, game, slot)
    if not source or not source.exists():
        raise FileNotFoundError(f"Nessuna clip originale per {game.title}, indizio {slot + 1}.")
    info = media.probe(source)
    start, duration = _segment(settings, info)
    _, _, params = _settings_params(settings)
    renderer, variant = MODES[settings["mode"]]
    path = project.ascii_project_path(game, slot)
    if (path / "project.json").exists():
        ascii_project = AsciiProject.load(path)
        ascii_project.source = str(source)
        ascii_project.title = f"{game.title} — Indizio {slot + 1}"
        ascii_project.format = "vertical"
        ascii_project.interval_start = start
        ascii_project.interval_duration = duration
        ascii_project.params = {**ascii_project.params, **params}
        ascii_project.ascii_mode = "spatial"
        ascii_project.renderer = renderer
        ascii_project.spatial_variant = variant
        ascii_project.overrides = settings["overrides"]
        ascii_project.save()
        return ascii_project
    return AsciiProject.create(
        str(source), "vertical", start, duration, params,
        title=f"{game.title} — Indizio {slot + 1}",
        ascii_mode="spatial", renderer=renderer, spatial_variant=variant,
        overrides=settings["overrides"], path=path,
    )


def convert(project, game, slot: int, settings: dict | None = None,
            progress=None, cancel=None, force: bool = False) -> dict:
    if slot >= 3:
        raise ValueError("Il reveal resta la registrazione originale.")
    settings = normalize_settings(settings)
    source = clip_source(project, game, slot)
    if not source:
        raise FileNotFoundError(f"Registra o importa prima l'indizio {slot + 1}.")
    fp = fingerprint(project, game, slot, settings, source)
    current = game.clips[slot].ascii or {}
    existing = project.ascii_mp4(game, slot)
    if not force and current.get("fingerprint") == fp and existing:
        recorded = current.get("output_sha1")
        if not recorded or recorded == _sha1(existing):
            current = {**current, "dirty": False, "output": str(existing)}
            project.set_ascii(game, slot, current)
            return {**current, "cached": True}

    ascii_project = build_project(project, game, slot, settings, source)
    outputs = ascii_render.ensure_render(ascii_project, progress, cancel)
    data = {
        **settings,
        "renderer": ascii_project.renderer,
        "variant": ascii_project.spatial_variant,
        "output": outputs.get("master", str(ascii_project.master_path)),
        "youtube": outputs.get("youtube", str(ascii_project.youtube_path)),
        "output_sha1": _sha1(outputs.get("master", ascii_project.master_path)),
        "status": "converted",
        "dirty": False,
        "fingerprint": fp,
        "cache_signature": ascii_project.render_key,
        "renderer_version": ascii_project.renderer_version,
        "project": str(ascii_project.path),
        "segment": {
            "start": ascii_project.interval_start,
            "duration": ascii_project.interval_duration,
            "source_duration": media.probe(source)["duration"],
        },
        "params": dict(ascii_project.params),
        "cached": False,
    }
    project.set_ascii(game, slot, data)
    return data


def approve(project, game, slot: int) -> None:
    if not project.ascii_mp4(game, slot):
        raise RuntimeError("Genera la conversione ASCII prima di approvarla.")
    project.approve_ascii(game, slot)


def preview(project, game, slot: int, settings: dict | None = None,
            progress=None, cancel=None) -> Path:
    if slot >= 3:
        raise ValueError("Il reveal resta la registrazione originale.")
    settings = normalize_settings(settings)
    ascii_project = build_project(project, game, slot, settings)
    out = ascii_render.preview(ascii_project, progress, cancel)
    data = {**settings, "preview": str(out),
            "preview_fingerprint": fingerprint(project, game, slot, settings)}
    project.set_ascii(game, slot, data)
    return out


def compare(project, game, slot: int, settings: dict | None = None,
            at: float = 1.0) -> Path:
    """Render the three modes as stills and compose one comparison sheet."""
    if slot >= 3:
        raise ValueError("Il reveal resta la registrazione originale.")
    settings = normalize_settings(settings)
    source = clip_source(project, game, slot)
    if not source:
        raise FileNotFoundError(f"Registra o importa prima l'indizio {slot + 1}.")
    info = media.probe(source)
    start, duration = _segment(settings, info)
    _, _, params = _settings_params(settings)
    root = project.ascii_dir(game, slot) / "compare"
    images = []
    for mode in MODES:
        path = root / mode
        ascii_project = AsciiProject.create(
            str(source), "vertical", start, duration, params,
            title=f"{game.title} {mode}", ascii_mode="spatial",
            renderer=MODES[mode][0], spatial_variant=MODES[mode][1], path=path,
        )
        images.append(ascii_render.still(ascii_project, at))
    frames = [Image.open(path).convert("RGB") for path in images]
    width, height = frames[0].size
    sheet = Image.new("RGB", (width * 3, height), (8, 10, 14))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * width, 0))
    out = root / "compare.png"
    sheet.save(out)
    project.set_ascii(game, slot, {**settings, "compare": str(out)})
    return out


def _vertical_preview(source: Path, out: Path, at: float = 1.0) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{max(0.0, at):.3f}",
        "-i", str(source), "-frames:v", "1",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
        str(out),
    ], check=True)


def import_video(project, game, slot: int, source: str | Path) -> str:
    """Copy an existing video into the take slot without touching the source."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(str(source))
    info = media.probe(source)
    take = project.take_dir(game, "import_" + hashlib.sha1(
        f"{slot}:{source}:{source.stat().st_mtime_ns}".encode("utf-8")).hexdigest()[:12])
    take.mkdir(parents=True, exist_ok=True)
    target = take / "take.mp4"
    if slot == 3:
        subprocess.run([
            ffmpeg_bin(), "-y", "-v", "error", "-i", str(source),
            "-map", "0:v:0", "-an", "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
        ], check=True)
    elif source.resolve() != target.resolve():
        shutil.copy2(source, target)
    _vertical_preview(target, take / "verify_vertical.png", at=min(1.0, info["duration"] / 2))
    (take / "take.json").write_text(json.dumps({
        "game": game.title, "take_id": take.name, "slot": slot,
        "selected": True, "capture": "import", "source": str(source),
        "video": media.probe(target), "paths": {"mp4": str(target)},
    }, indent=2), encoding="utf-8")
    project.set_clip(game, slot, take.name, {
        "x": 0, "y": 0, "w": info["width"], "h": info["height"], "imported": True,
    })
    return take.name

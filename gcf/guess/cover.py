from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from gcf.capture.takes import frame_at, media_duration, probe, sha256
from gcf.config import ROOT, ffmpeg_bin, video_encode_args
from gcf.guess.round import (
    FPS,
    H,
    MUSIC,
    W,
    InsufficientMaterial,
    _font,
    _rel,
    ensure_music,
    load_preset,
)
from gcf.gui.project import Project


def _media_stamp(path: Path) -> list:
    return [str(path), path.stat().st_mtime_ns, path.stat().st_size]


def _gradient_background() -> Image.Image:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    top = (10, 22, 34)
    bottom = (4, 74, 92)
    for y in range(H):
        t = y / max(1, H - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=color)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for radius in range(700, 0, -40):
        alpha = int(8 + 28 * (1 - radius / 700))
        gd.ellipse(
            [W // 2 - radius, 380 - radius, W // 2 + radius, 380 + radius],
            fill=(0, 183, 255, alpha),
        )
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=(0, 183, 255, 10), width=1)
    return img


def _cover_background_image(image: Path) -> Image.Image:
    with Image.open(image) as source:
        source = source.convert("RGB")
        scale = max(W / source.width, H / source.height)
        size = (round(source.width * scale), round(source.height * scale))
        source = source.resize(size, Image.Resampling.LANCZOS)
        left = (size[0] - W) // 2
        top = (size[1] - H) // 2
        return source.crop((left, top, left + W, top + H))


def _highlight_indices(tokens: list[str], phrases: list[str]) -> set[int]:
    marked: set[int] = set()
    lowered = [t.lower() for t in tokens]
    for phrase in phrases:
        words = phrase.split()
        if not words:
            continue
        needle = [w.lower() for w in words]
        for start in range(len(lowered) - len(needle) + 1):
            if lowered[start:start + len(needle)] == needle:
                marked.update(range(start, start + len(needle)))
    return marked


def _text_chunks(tokens: list[str], phrases: list[str]) -> list[list[tuple[int, str]]]:
    """Keep highlighted phrases on one line when possible."""
    lowered = [t.lower() for t in tokens]
    starts: dict[int, int] = {}
    for phrase in phrases:
        words = phrase.split()
        if not words:
            continue
        needle = [w.lower() for w in words]
        for start in range(len(lowered) - len(needle) + 1):
            if lowered[start:start + len(needle)] == needle:
                starts[start] = max(starts.get(start, 0), len(needle))
    chunks: list[list[tuple[int, str]]] = []
    i = 0
    while i < len(tokens):
        size = starts.get(i, 1)
        chunks.append([(i + offset, tokens[i + offset]) for offset in range(size)])
        i += size
    return chunks


def render_cover_text(text: str, preset: dict | None = None) -> Image.Image:
    preset = preset or load_preset()
    cfg = preset["cover"]
    tokens = text.split()
    font = _font(int(cfg["font_size"]), preset.get("font"))
    space = font.getlength(" ")
    max_width = int(cfg["max_width"])
    chunks = _text_chunks(tokens, cfg.get("highlight_phrases", []))
    lines: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    width = 0.0
    for chunk in chunks:
        chunk_text = " ".join(word for _, word in chunk)
        chunk_w = font.getlength(chunk_text)
        extra = chunk_w if not current else space + chunk_w
        if current and width + extra > max_width:
            lines.append(current)
            current = list(chunk)
            width = chunk_w
        else:
            current.extend(chunk)
            width += extra
    if current:
        lines.append(current)

    highlighted = _highlight_indices(tokens, cfg.get("highlight_phrases", []))
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + int(cfg.get("line_gap", 0))
    total_height = max(0, len(lines) * line_height - int(cfg.get("line_gap", 0)))
    y = int(cfg["center_y"]) - total_height // 2

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for line in lines:
        line_width = sum(font.getlength(word) for _, word in line) + space * (len(line) - 1)
        x = (W - line_width) / 2
        for index, word in line:
            fill = tuple(cfg["highlight_color"]) if index in highlighted else tuple(cfg["color"])
            draw.text(
                (x, y), word, font=font, anchor="lt", fill=fill,
                stroke_width=int(cfg["stroke"]), stroke_fill=tuple(cfg["outline"]),
            )
            x += font.getlength(word) + space
        y += line_height
    return img


def render_cover_still(text: str, background: Path | None, preset: dict | None = None) -> Image.Image:
    preset = preset or load_preset()
    base = _cover_background_image(background) if background else _gradient_background()
    return Image.alpha_composite(base.convert("RGBA"), render_cover_text(text, preset))


def _find_clip(project: Project, game_title: str, slot: int) -> Path | None:
    game = next((g for g in project.games if g.title == game_title), None)
    if not game or slot < 0 or slot >= len(game.clips):
        return None
    return project.clip_mp4(game, slot)


def _resolve_background(project: Project, background: dict | None) -> dict:
    bg = background or project.cover_background or {"type": "auto"}
    kind = bg.get("type", "auto")
    if kind == "clip":
        path = _find_clip(project, bg.get("game", ""), int(bg.get("slot", 0)))
        if path:
            return {"type": "clip", "path": path, "game": bg.get("game"), "slot": bg.get("slot")}
    if kind == "cover":
        path = project.cover_mp4()
        if path:
            return {"type": "clip", "path": path, "game": "Copertina", "slot": 0, "source": "cover"}
    if kind == "image":
        path = Path(bg.get("path", ""))
        if path.exists():
            return {"type": "image", "path": path}
    if kind == "auto" or kind not in ("clip", "cover", "image"):
        cover_path = project.cover_mp4()
        if cover_path:
            return {
                "type": "clip", "path": cover_path, "game": "Copertina",
                "slot": 0, "source": "cover",
            }
        for game in project.games:
            for slot in range(len(game.clips)):
                path = project.clip_mp4(game, slot)
                if path:
                    return {"type": "clip", "path": path, "game": game.title, "slot": slot}
    return {"type": "gradient"}


def _preview_frame(background: dict, outdir: Path) -> Path:
    if background["type"] == "image":
        return background["path"]
    if background["type"] == "clip":
        verify = background["path"].parent / "verify_vertical.png"
        if verify.exists():
            return verify
        out = outdir / "background_preview.png"
        frame_at(background["path"], out, at=min(1.0, probe(background["path"])["duration"] / 2))
        return out
    return outdir / "background_gradient.png"


def build_cover(
    project: Project,
    outdir: Path | None = None,
    title: str | None = None,
    background: dict | None = None,
    duration: float | None = None,
    preset_path: str | Path | None = None,
    music_path: Path | None = None,
) -> dict:
    ensure_music()
    preset = load_preset(preset_path or project.graphics_preset or None)
    text = (title if title is not None else project.challenge_title).strip() or "GUESS THE GAME"
    cover_duration = max(1.0, min(float(duration if duration is not None else project.cover_duration), 10.0))
    music = Path(music_path) if music_path else MUSIC
    if media_duration(music) < cover_duration:
        raise InsufficientMaterial(f"Musica troppo corta per la copertina da {cover_duration:.1f}s.")

    outdir = Path(outdir).resolve() if outdir else (project.path / "cover")
    outdir.mkdir(parents=True, exist_ok=True)
    background = _resolve_background(project, background)
    out = outdir / "cover.mp4"
    preview = outdir / "cover_preview.png"
    still = outdir / "cover_still.png"
    manifest_path = outdir / "manifest.json"
    fingerprint = {
        "title": text,
        "duration": cover_duration,
        "category": project.challenge_category,
        "preset": preset,
        "background": (
            "gradient" if background["type"] == "gradient"
            else _media_stamp(background["path"])
        ),
        "music": _media_stamp(music),
    }
    if out.exists() and preview.exists() and still.exists() and manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") == fingerprint:
            return existing

    text_png = outdir / "cover_text.png"
    render_cover_text(text, preset).save(text_png)

    if background["type"] == "gradient":
        gradient = outdir / "background_gradient.png"
        _gradient_background().save(gradient)
        background = {"type": "image", "path": gradient}

    fade = float(preset["cover"].get("fade_in", 0.35))
    slide = int(preset["cover"].get("slide_px", 28))
    if background["type"] == "clip":
        clip_path = background["path"]
        clip_duration = probe(clip_path)["duration"]
        start = max(0.0, (clip_duration - cover_duration) / 2)
        bg_filter = (
            f"[0:v]trim=start={start:.3f}:duration={cover_duration:.3f},"
            f"setpts=PTS-STARTPTS,fps={FPS},"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fade=t=in:st=0:d=0.25[bg]"
        )
        background_input = ["-stream_loop", "-1", "-i", str(clip_path)]
    else:
        bg_filter = (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS},fade=t=in:st=0:d=0.25[bg]"
        )
        background_input = ["-loop", "1", "-i", str(background["path"])]

    filters = (
        f"{bg_filter};"
        f"[1:v]format=rgba,fade=in:st=0:d={fade}:alpha=1[text];"
        f"[bg][text]overlay=x=0:y='{slide}*(1-min(t/{fade},1))':format=auto[v];"
        f"[v]setsar=1[vout]"
    )
    cmd = [
        ffmpeg_bin(), "-y", "-v", "error",
        *background_input,
        "-loop", "1", "-i", str(text_png),
        "-i", str(music),
        "-filter_complex", filters,
        "-map", "[vout]", "-map", "2:a",
        "-t", f"{cover_duration}", "-r", str(FPS),
        *video_encode_args(18), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True)

    frame_at(out, preview, at=min(1.0, cover_duration / 2))
    still_bg = _preview_frame(background, outdir)
    render_cover_still(text, still_bg, preset).convert("RGB").save(still)

    manifest = {
        "project": project.id,
        "title": text,
        "category": project.challenge_category,
        "duration": cover_duration,
        "fps": FPS,
        "resolution": [W, H],
        "background": (
            {**background, "path": _rel(background["path"])}
            if "path" in background else background
        ),
        "preset": preset.get("name", "guess_default"),
        "fingerprint": fingerprint,
        "events": {"text_in": 0.0, "fade_in": fade, "slide_px": slide},
        "output": _rel(out),
        "preview": _rel(preview),
        "still": _rel(still),
        "music": _rel(music),
        "sha256": {"mp4": sha256(out), "text": sha256(text_png)},
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from gcf.ascii import luma, preset, spatial
from gcf.config import ROOT, ffmpeg_bin

ATLAS = ROOT / "gcf" / "ascii" / "glyphs" / "branch_atlas.png"
RAMP = " .,:;+HW@"


def load_atlas(path: str | Path = ATLAS, ramp: str = RAMP) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Atlante glifi assente: {path}. Esegui tools/make_glyph_atlas.py con Blender.")
    im = Image.open(path).convert("L")
    tile = im.height
    if im.width != tile * len(ramp):
        raise RuntimeError(f"Atlante inatteso: {im.size} per {len(ramp)} glifi")
    tiles = np.zeros((len(ramp), tile, tile), dtype=np.float32)
    raw = np.asarray(im, dtype=np.float32) / 255.0
    for i in range(len(ramp)):
        tiles[i] = raw[:, i * tile:(i + 1) * tile]
    return {
        "ramp": ramp,
        "tiles": tiles,
        "coverage": tiles.reshape(len(ramp), -1).mean(axis=1).astype(np.float32),
        "tile": tile,
        "path": str(path),
    }


def _scaled(atlas: dict, cell_px: int) -> np.ndarray:
    tile = atlas["tile"]
    out = np.zeros((len(atlas["ramp"]), cell_px, cell_px), dtype=np.float32)
    for i, mask in enumerate(atlas["tiles"]):
        im = Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), mode="L")
        out[i] = np.asarray(im.resize((cell_px, cell_px), Image.Resampling.LANCZOS),
                            dtype=np.float32) / 255.0
    return np.clip(out, 0.0, 1.0)


def raster_array(indices: np.ndarray, colors: np.ndarray, atlas: dict,
                 cell_px: int = 12) -> np.ndarray:
    rows, cols = indices.shape
    tiles = _scaled(atlas, cell_px)
    idx = np.clip(indices.astype(np.int16), 0, len(tiles) - 1)
    masks = tiles[idx]
    rgb = np.clip(colors, 0.0, 1.0).astype(np.float32)
    image = masks[..., None] * rgb[:, :, None, None, :]
    image = image.transpose(0, 2, 1, 3, 4).reshape(rows * cell_px, cols * cell_px, 3)
    return np.clip(image * 255.0, 0, 255).astype(np.uint8)


def rasterize(indices: np.ndarray, colors: np.ndarray, atlas: dict,
              cell_px: int = 12, size: tuple[int, int] | None = None) -> Image.Image:
    out = Image.fromarray(raster_array(indices, colors, atlas, cell_px), mode="RGB")
    if size and out.size != size:
        out = out.resize(size, Image.Resampling.LANCZOS)
    return out


def _chroma(rgb: np.ndarray) -> np.ndarray:
    peak = np.max(rgb, axis=-1, keepdims=True)
    return rgb / np.maximum(peak, 1e-5)


def _patterns(source: Image.Image, cols: int, rows: int, cell_px: int):
    img = source.convert("L").resize((cols * cell_px, rows * cell_px),
                                      Image.Resampling.LANCZOS)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = arr.reshape(rows, cell_px, cols, cell_px).transpose(0, 2, 1, 3)
    mean = arr.mean(axis=(-2, -1), keepdims=True)
    pat = arr - mean
    std = pat.std(axis=(-2, -1), keepdims=True)
    return pat / np.maximum(std, 0.02), std[..., 0, 0]


def decoupled(indices: np.ndarray, desired: np.ndarray, source_rgb: np.ndarray,
              atlas: dict, source: Image.Image, cols: int, rows: int,
              cell_px: int = 12, max_intensity: float = 0.98):
    """Separate glyph shape, cell luminance and glyph intensity.

    Textured cells choose the glyph whose raster matches the source patch;
    flat cells keep the tone-derived glyph.  Flat cells scale intensity so
    coverage*intensity tracks the desired cell luma; textured cells keep the
    desired stroke luminance and let shape carry the structure.
    """
    coverage = atlas["coverage"]
    tiles = _scaled(atlas, cell_px)
    flat_tiles = tiles.reshape(len(tiles), -1)
    glyph_mean = flat_tiles.mean(axis=1, keepdims=True)
    glyph_std = flat_tiles.std(axis=1, keepdims=True)
    glyph_norm = (flat_tiles - glyph_mean) / np.maximum(glyph_std, 0.02)
    pat, std = _patterns(source, cols, rows, cell_px)
    corr = np.einsum("rcij,gij->rcg", pat, glyph_norm.reshape(len(tiles), cell_px, cell_px))
    corr /= float(cell_px * cell_px)
    levels = np.arange(len(tiles), dtype=np.float32)[None, None, :]
    allowed = levels <= (indices[:, :, None].astype(np.float32) + 2.0)
    corr = np.where(allowed, corr - 0.02 * levels, -1.0)
    pattern_glyph = np.argmax(corr, axis=-1).astype(np.int16)
    best = np.max(corr, axis=-1)
    flat = (std < 0.018) | (best < 0.18)
    chosen = np.where(flat, indices, pattern_glyph).astype(np.int16)
    desired = np.clip(desired, 0.0, 1.0) ** 0.80
    cov = coverage[chosen]
    intensity_flat = np.clip(desired / np.maximum(cov, 0.06), 0.05, max_intensity)
    intensity_text = np.clip(desired, 0.05, max_intensity)
    intensity = np.where(flat, intensity_flat, intensity_text).astype(np.float32)
    colors = _chroma(source_rgb) * intensity[:, :, None]
    return chosen, intensity, colors


def read_maps(project, frame: int) -> tuple[np.ndarray, np.ndarray]:
    maps = getattr(project, "spatial", {}) or {}
    if not maps.get("dir"):
        raise RuntimeError("Mappe spaziali assenti.")
    root = Path(maps["dir"])
    idx = np.asarray(Image.open(root / "idx" / f"i_{frame:04d}.png").convert("L"),
                     dtype=np.float32)
    tone = np.asarray(Image.open(root / "tone" / f"t_{frame:04d}.png").convert("L"),
                      dtype=np.float32)
    return idx, tone


def extract_frame(source: str | Path, t: float, out: Path,
                  size: tuple[int, int] = (1920, 1080)) -> Image.Image:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{max(0.0, t):.5f}",
                    "-i", str(source), "-frames:v", "1",
                    "-vf", f"scale={size[0]}:{size[1]},setsar=1", str(out)],
                   check=True)
    return Image.open(out).convert("RGB")


def cell_colors(source: Image.Image, cols: int, rows: int) -> np.ndarray:
    small = source.convert("RGB").resize((cols, rows), Image.Resampling.BOX)
    return np.asarray(small, dtype=np.float32) / 255.0


def render_video(project, mode: str, out: Path, start_frame: int = 1,
                 end_frame: int | None = None, atlas: dict | None = None,
                 cell_px: int = 12, progress=None) -> Path:
    """Reference raster video; diagnostic only, never a production renderer."""
    atlas = atlas or load_atlas()
    data = preset.resolve(project)
    cols, rows = data["grid"]["cols"], data["grid"]["rows"]
    size = tuple(data["resolution"])
    total = int(round(project.working_info["duration"] * 30))
    end_frame = min(total, int(end_frame or total))
    count = max(0, end_frame - start_frame + 1)
    if count <= 0:
        raise ValueError("Intervallo video vuoto.")
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = (start_frame - 1) / 30.0
    read_cmd = [ffmpeg_bin(), "-v", "error", "-ss", f"{t0:.5f}",
                "-i", str(project.working_source), "-t", f"{count / 30.0:.5f}",
                "-vf", f"fps=30,scale={size[0]}:{size[1]},setsar=1",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    frame_bytes = size[0] * size[1] * 3
    write_cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "rawvideo",
                 "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", "30",
                 "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium",
                 "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                 str(out)]
    reader = subprocess.Popen(read_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    writer = subprocess.Popen(write_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(count):
            buf = reader.stdout.read(frame_bytes)
            if len(buf) != frame_bytes:
                raise RuntimeError(f"Sorgente esaurita al frame {start_frame + i}.")
            frame_index = start_frame + i
            idx, tone = read_maps(project, frame_index)
            source = Image.frombytes("RGB", size, buf)
            colors = cell_colors(source, cols, rows)
            indices = np.rint(idx / 32.0).astype(np.int16)
            if mode == "decoupled":
                cells = luma.linear_cells(source, cols, rows)
                lo, hi = np.percentile(cells, [2, 98])
                desired = np.clip((cells - lo) / max(1e-6, hi - lo), 0.0, 1.0)
                indices, _, colors = decoupled(indices, desired, colors, atlas,
                                               source, cols, rows, cell_px)
            frame = raster_array(indices, colors, atlas, cell_px)
            image = Image.fromarray(frame, mode="RGB")
            if image.size != size:
                image = image.resize(size, Image.Resampling.LANCZOS)
            writer.stdin.write(np.asarray(image, dtype=np.uint8).tobytes())
            if progress and (i + 1) % 30 == 0:
                progress(i + 1, count)
    finally:
        try:
            reader.terminate()
        except Exception:
            pass
        try:
            writer.stdin.close()
        except Exception:
            pass
        writer.wait()
    if writer.returncode != 0:
        raise RuntimeError(writer.stderr.read().decode("utf-8", errors="ignore")[-800:])
    return out


def frame_for_project(project, frame: int, atlas: dict | None = None,
                      mode: str = "pipeline", palette_rgb: np.ndarray | None = None,
                      source: Image.Image | None = None,
                      cell_px: int = 12, size: tuple[int, int] = (1920, 1080)) -> dict:
    """Render one frame from the project's index/tone maps."""
    atlas = atlas or load_atlas()
    idx, tone = read_maps(project, frame)
    data = preset.resolve(project)
    cols, rows = data["grid"]["cols"], data["grid"]["rows"]
    if source is None:
        t = (frame - 1) / 30.0
        tmp = project.path / "temp" / f"ref_src_{frame:04d}.png"
        source = extract_frame(project.working_source, t, tmp, data["resolution"])
    indices = np.rint(idx / 32.0).astype(np.int16)
    rgb = palette_rgb if palette_rgb is not None else cell_colors(source, cols, rows)
    if mode == "decoupled":
        cells = luma.linear_cells(source, cols, rows)
        lo, hi = np.percentile(cells, [2, 98])
        desired = np.clip((cells - lo) / max(1e-6, hi - lo), 0.0, 1.0)
        indices, intensity, rgb = decoupled(indices, desired,
                                            cell_colors(source, cols, rows), atlas,
                                            source, cols, rows, cell_px)
    else:
        intensity = None
    image = rasterize(indices, rgb, atlas, cell_px=cell_px, size=size)
    return {"image": image, "indices": indices, "tone": tone, "colors": rgb,
            "source": source, "atlas": atlas}

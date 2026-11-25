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


def _scaled_coverage(atlas: dict, cell_px: int) -> np.ndarray:
    return _scaled(atlas, cell_px).reshape(len(atlas["tiles"]), -1).mean(axis=1)


def shot_normalisation(project, start_frame: int, end_frame: int,
                       step: int = 3) -> dict:
    """Tone-map percentiles over a shot, robust to flashes and short spikes."""
    lows, highs, means = [], [], []
    flash = []
    for frame in range(max(1, start_frame), max(1, end_frame) + 1, max(1, step)):
        try:
            _, tone = read_maps(project, frame)
        except Exception:
            continue
        values = tone.astype(np.float32) / 255.0
        lows.append(float(np.percentile(values, 2)))
        highs.append(float(np.percentile(values, 98)))
        means.append(float(values.mean()))
    if not lows:
        return {"lo": 0.0, "hi": 1.0, "flashes": [], "frames": 0}
    median_mean = float(np.median(means))
    keep = [i for i, value in enumerate(means) if value <= median_mean + 0.18]
    if not keep:
        keep = list(range(len(means)))
    flash = [i for i, value in enumerate(means) if value > median_mean + 0.18]
    lo = float(np.median([lows[i] for i in keep]))
    hi = float(np.median([highs[i] for i in keep]))
    if hi - lo < 0.08:
        hi = min(1.0, lo + 0.08)
    return {"lo": lo, "hi": hi, "flashes": flash, "frames": len(lows)}


def shot_source_normalisation(project, start_frame: int, end_frame: int) -> dict:
    """Source luminance range for the shot, from the 10 fps analysis frames."""
    frames = sorted((project.path / "analysis").glob("f_*.png"))
    if not frames:
        return {"lo": 0.0, "hi": 1.0}
    data = preset.resolve(project)
    cols, rows = data["grid"]["cols"], data["grid"]["rows"]
    start_t, end_t = (start_frame - 1) / 30.0, (end_frame - 1) / 30.0 + 1 / 30.0
    selected = [p for p in frames if start_t - 0.5 <= (int(p.stem.split("_")[1]) - 1) / 10.0 <= end_t + 0.5]
    if not selected:
        selected = frames
    lows, highs, means = [], [], []
    for path in selected:
        im = Image.open(path).convert("RGB")
        cells = luma.linear_cells(im, cols, rows)
        lows.append(float(np.percentile(cells, 2)))
        highs.append(float(np.percentile(cells, 98)))
        means.append(float(cells.mean()))
    if not lows:
        return {"lo": 0.0, "hi": 1.0}
    median = float(np.median(means))
    keep = [i for i, value in enumerate(means) if value <= median + 0.20]
    if not keep:
        keep = list(range(len(means)))
    lo = float(np.median([lows[i] for i in keep]))
    hi = float(np.median([highs[i] for i in keep]))
    if hi - lo < 0.03:
        hi = min(1.0, lo + 0.03)
    return {"lo": lo, "hi": hi}


def decoupled(indices: np.ndarray, desired: np.ndarray, source_rgb: np.ndarray,
              atlas: dict, source: Image.Image, cols: int, rows: int,
              cell_px: int = 12, max_intensity: float = 0.98):
    """Joint glyph/intensity reconstruction with final-resolution coverage.

    Textured cells choose the glyph whose raster best matches the source patch;
    flat cells keep the tone-derived glyph.  Intensity is solved from the
    desired cell luminance and the real coverage of that glyph at render size.
    """
    coverage = _scaled_coverage(atlas, cell_px)
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
    desired = np.clip(desired, 0.0, 1.0)
    cov = coverage[chosen]
    intensity_flat = np.clip(desired / np.maximum(cov, 0.06), 0.05, max_intensity)
    intensity_text = np.clip(desired, 0.05, max_intensity)
    intensity = np.where(flat, intensity_flat, intensity_text).astype(np.float32)
    lum = (0.2126 * source_rgb[..., 0] + 0.7152 * source_rgb[..., 1]
           + 0.0722 * source_rgb[..., 2])
    chroma = source_rgb / np.maximum(lum[..., None], 0.02)
    colors = np.clip(chroma * intensity[..., None], 0.0, 1.0)
    return chosen, intensity, colors


def write_decoupled_maps(project, start_frame: int, end_frame: int,
                        outdir: Path) -> dict:
    """Write separate index, colour and intensity maps for the Blender graph."""
    atlas = load_atlas()
    data = preset.resolve(project)
    cols, rows = data["grid"]["cols"], data["grid"]["rows"]
    size = tuple(data["resolution"])
    norm = shot_normalisation(project, start_frame, end_frame, step=max(1, (end_frame - start_frame) // 30 + 1))
    src_norm = shot_source_normalisation(project, start_frame, end_frame)
    idx_dir = outdir / "idx"
    col_dir = outdir / "color"
    int_dir = outdir / "intensity"
    for folder in (idx_dir, col_dir, int_dir):
        folder.mkdir(parents=True, exist_ok=True)
    for frame in range(start_frame, end_frame + 1):
        idx, tone = read_maps(project, frame)
        t = (frame - 1) / 30.0
        source = extract_frame(project.working_source, t,
                               project.path / "temp" / f"dec_src_{frame:04d}.png", size)
        cells = luma.linear_cells(source, cols, rows)
        cell_rgb = cell_colors(source, cols, rows)
        raw = tone.astype(np.float32) / 255.0
        tone_n = np.clip((raw - norm["lo"]) / max(1e-6, norm["hi"] - norm["lo"]), 0, 1)
        source_n = np.clip((cells - src_norm["lo"]) / max(1e-6, src_norm["hi"] - src_norm["lo"]), 0, 1)
        desired = np.clip(0.55 * tone_n + 0.45 * source_n, 0, 1) ** 0.80
        chosen, intensity, _ = decoupled(np.rint(idx / 32.0).astype(np.int16),
                                         desired, cell_rgb, atlas, source, cols, rows, 12)
        lum = (0.2126 * cell_rgb[..., 0] + 0.7152 * cell_rgb[..., 1]
               + 0.0722 * cell_rgb[..., 2])
        chroma = np.clip(cell_rgb / np.maximum(lum[..., None], 0.02), 0, 1)
        spatial.encode_index(chosen, data["ramp"]).save(idx_dir / f"i_{frame:04d}.png")
        Image.fromarray(np.clip(chroma * 255, 0, 255).astype(np.uint8), mode="RGB").save(
            col_dir / f"c_{frame:04d}.png")
        Image.fromarray(np.clip(intensity * 255, 0, 255).astype(np.uint8), mode="L").save(
            int_dir / f"t_{frame:04d}.png")
    return {"idx": str(idx_dir), "color": str(col_dir),
            "intensity": str(int_dir), "frames": end_frame - start_frame + 1}


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
    norm = shot_normalisation(project, start_frame, end_frame, step=max(1, count // 30))
    src_norm = shot_source_normalisation(project, start_frame, end_frame)
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
                raw = tone.astype(np.float32) / 255.0
                tone_n = np.clip((raw - norm["lo"]) /
                                 max(1e-6, norm["hi"] - norm["lo"]), 0.0, 1.0)
                cells = luma.linear_cells(source, cols, rows)
                source_n = np.clip((cells - src_norm["lo"]) /
                                   max(1e-6, src_norm["hi"] - src_norm["lo"]), 0.0, 1.0)
                desired = np.clip(0.55 * tone_n + 0.45 * source_n, 0.0, 1.0) ** 0.80
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
        norm = shot_normalisation(project, max(1, frame - 15), frame + 15, step=5)
        src_norm = shot_source_normalisation(project, max(1, frame - 40), frame + 40)
        raw = tone.astype(np.float32) / 255.0
        tone_n = np.clip((raw - norm["lo"]) /
                         max(1e-6, norm["hi"] - norm["lo"]), 0.0, 1.0)
        cells = luma.linear_cells(source, cols, rows)
        source_n = np.clip((cells - src_norm["lo"]) /
                           max(1e-6, src_norm["hi"] - src_norm["lo"]), 0.0, 1.0)
        desired = np.clip(0.55 * tone_n + 0.45 * source_n, 0.0, 1.0) ** 0.80
        indices, intensity, rgb = decoupled(indices, desired,
                                            cell_colors(source, cols, rows), atlas,
                                            source, cols, rows, cell_px)
    else:
        intensity = None
    image = rasterize(indices, rgb, atlas, cell_px=cell_px, size=size)
    return {"image": image, "indices": indices, "tone": tone, "colors": rgb,
            "source": source, "atlas": atlas}

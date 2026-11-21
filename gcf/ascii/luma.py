from __future__ import annotations

import numpy as np
from PIL import Image

# sRGB 8-bit -> linear-light 0..1, matching the Blender shader luma.
_LUT = np.array([
    c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    for c in (np.arange(256, dtype=np.float32) / 255.0)
], dtype=np.float32)
_COEFF = (0.2126, 0.7152, 0.0722)


def srgb_to_linear(value: float) -> float:
    """Scalar sRGB (0..1) to linear light."""
    c = max(0.0, min(1.0, float(value)))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_luma_array(image: Image.Image) -> np.ndarray:
    """Float32 linear luminance (0..1) from an RGB PIL image."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    lin = _LUT[rgb]
    return (lin[..., 0] * _COEFF[0] + lin[..., 1] * _COEFF[1]
            + lin[..., 2] * _COEFF[2]).astype(np.float32)


def linear_luma_cell_samples(image: Image.Image, cols: int, rows: int):
    """Four-sample linear luma per cell plus the centre sample.

    Mirrors the samples used by the ASCII Cell Sample nodes, so the analysis
    and the renderer see the same cells.
    """
    lum = linear_luma_array(image)
    h, w = lum.shape
    cw, ch = w / cols, h / rows
    dx, dy = cw / 4.0, ch / 4.0
    xs = (np.arange(cols, dtype=np.float32) + 0.5) * cw
    ys = (np.arange(rows, dtype=np.float32) + 0.5) * ch
    x0 = np.clip((xs - dx).astype(int), 0, w - 1)
    x1 = np.clip((xs + dx).astype(int), 0, w - 1)
    y0 = np.clip((ys - dy).astype(int), 0, h - 1)
    y1 = np.clip((ys + dy).astype(int), 0, h - 1)
    top = (lum[np.ix_(y0, x0)] + lum[np.ix_(y0, x1)]) * 0.5
    bottom = (lum[np.ix_(y1, x0)] + lum[np.ix_(y1, x1)]) * 0.5
    cells = ((top + bottom) * 0.5).astype(np.float32)
    centre = lum[np.ix_(np.clip(ys.astype(int), 0, h - 1),
                       np.clip(xs.astype(int), 0, w - 1))].astype(np.float32)
    return cells, centre


def linear_cells(image: Image.Image, cols: int, rows: int) -> np.ndarray:
    """Box-averaged linear luma for analysis grids."""
    lum = linear_luma_array(image)
    small = Image.fromarray(lum, mode="F").resize((cols, rows), Image.Resampling.BOX)
    return np.asarray(small, dtype=np.float32)


def local_range(lum: np.ndarray, radius: int = 1) -> np.ndarray:
    pad = np.pad(lum, radius, mode="edge")
    h, w = lum.shape
    hi = None
    lo = None
    for yy in range(2 * radius + 1):
        for xx in range(2 * radius + 1):
            window = pad[yy:yy + h, xx:xx + w]
            hi = window.copy() if hi is None else np.maximum(hi, window)
            lo = window.copy() if lo is None else np.minimum(lo, window)
    return (hi - lo).astype(np.float32)


def box_mean(lum: np.ndarray, radius: int) -> np.ndarray:
    pad = np.pad(lum, radius, mode="edge")
    h, w = lum.shape
    acc = np.zeros_like(lum, dtype=np.float32)
    for yy in range(2 * radius + 1):
        for xx in range(2 * radius + 1):
            acc += pad[yy:yy + h, xx:xx + w]
    return acc / float((2 * radius + 1) ** 2)


def local_std(lum: np.ndarray, radius: int = 2) -> np.ndarray:
    mean = box_mean(lum, radius)
    mean_sq = box_mean(lum * lum, radius)
    return np.sqrt(np.maximum(0.0, mean_sq - mean * mean)).astype(np.float32)

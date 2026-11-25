from __future__ import annotations

import numpy as np
from PIL import Image

from gcf.ascii import luma


def common_grid(fmt: str) -> tuple[int, int]:
    """Grid used to compare all candidates; higher than the old 64x36."""
    return (54, 96) if fmt == "vertical" else (96, 54)


def detail_grid(fmt: str) -> tuple[int, int]:
    """Grid used for UI/text and fine-detail checks."""
    return (81, 144) if fmt == "vertical" else (144, 81)


def _fimage(arr: np.ndarray, cols: int, rows: int) -> np.ndarray:
    im = Image.fromarray(arr.astype(np.float32), mode="F")
    return np.asarray(im.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32)


def _rgbimage(arr: np.ndarray, cols: int, rows: int) -> np.ndarray:
    im = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    return np.asarray(im.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0


def _resize_map(arr: np.ndarray, cols: int, rows: int) -> np.ndarray:
    im = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L")
    return np.asarray(im.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0


def _norm(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((arr - lo) / max(1e-6, hi - lo), 0.0, 1.0)


def _norm_own(arr: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
    """Robust normalisation using the map's own percentiles."""
    lo, hi = np.percentile(arr, [low, high])
    return _norm(arr, float(lo), float(hi))


def _box(x: np.ndarray, radius: int) -> np.ndarray:
    p = np.pad(x, radius, mode="reflect")
    h, w = x.shape
    acc = np.zeros_like(x, dtype=np.float32)
    for y in range(2 * radius + 1):
        for xx in range(2 * radius + 1):
            acc += p[y:y + h, xx:xx + w]
    return acc / float((2 * radius + 1) ** 2)


def ssim(a: np.ndarray, b: np.ndarray, radius: int = 3) -> float:
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    if a.shape != b.shape or a.size < 4:
        return 0.0
    mu_a, mu_b = _box(a, radius), _box(b, radius)
    va = np.maximum(0.0, _box(a * a, radius) - mu_a * mu_a)
    vb = np.maximum(0.0, _box(b * b, radius) - mu_b * mu_b)
    cov = _box(a * b, radius) - mu_a * mu_b
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    value = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)
             / ((mu_a * mu_a + mu_b * mu_b + c1) * (va + vb + c2)))
    return float(np.mean(value))


def ms_ssim(a: np.ndarray, b: np.ndarray) -> float:
    values = []
    weights = [0.5, 0.3, 0.2]
    ca, cb = a.copy(), b.copy()
    for i in range(3):
        values.append(ssim(ca, cb))
        if i < 2:
            ca = _resize_map(ca, max(8, ca.shape[1] // 2), max(8, ca.shape[0] // 2))
            cb = _resize_map(cb, max(8, cb.shape[1] // 2), max(8, cb.shape[0] // 2))
    return float(sum(w * v for w, v in zip(weights, values)))


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.ravel().astype(np.float32), b.ravel().astype(np.float32)
    if a.size < 4 or a.std() < 1e-8 or b.std() < 1e-8:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _chroma(rgb: np.ndarray) -> np.ndarray:
    peak = np.max(rgb, axis=-1, keepdims=True)
    return rgb / np.maximum(peak, 1e-5)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return float(max(low, min(high, value)))


def metrics(source: Image.Image, rendered: Image.Image, fmt: str, shadow: float) -> dict:
    cols, rows = common_grid(fmt)
    dcols, drows = detail_grid(fmt)
    src = source.convert("RGB")
    ren = rendered.convert("RGB")
    src_l = luma.linear_luma_array(src)
    src_rgb = np.asarray(src, dtype=np.float32) / 255.0
    src_edge_full = luma.local_range(src_l, 1)
    ren_l = luma.linear_luma_array(ren)
    ren_rgb = np.asarray(ren, dtype=np.float32) / 255.0
    mask = (ren_l > 0.012).astype(np.float32)

    src_cells = _fimage(src_l, cols, rows)
    src_edge = _fimage(src_edge_full, cols, rows)
    src_rgb_c = _rgbimage(src_rgb, cols, rows)
    coverage = _resize_map(mask, cols, rows)
    glyph_energy = _resize_map(ren_l * mask, cols, rows)
    glyph_luma = glyph_energy / np.maximum(coverage, 1e-5)
    cell_luma = _fimage(ren_l, cols, rows)
    glyph_rgb = np.dstack([
        _resize_map(ren_l * mask * ren_rgb[..., c], cols, rows)
        / np.maximum(glyph_energy, 1e-5) for c in range(3)
    ])

    # Each representation is normalised on its own scale; coverage is a
    # separate map rather than being folded into the luma comparison.
    src_n = _norm_own(src_cells)
    cell_n = _norm_own(cell_luma)
    glyph_n = _norm_own(glyph_luma)
    cov_n = _norm_own(coverage)
    ssim_cell = ms_ssim(src_n, cell_n)
    ssim_glyph = ms_ssim(src_n, glyph_n)
    ssim_cov = ms_ssim(src_n, cov_n)
    coverage_corr = _pearson(src_n, cov_n)

    edge_src_n = _norm_own(src_edge)
    edge_ren = _fimage(luma.local_range(cell_luma, 1), cols, rows)
    edge_ren_n = _norm_own(edge_ren)
    ssim_edge = ms_ssim(edge_src_n, edge_ren_n)
    edge_corr = _pearson(edge_src_n, edge_ren_n)
    contrast_src = _fimage(luma.local_range(src_cells, 1), cols, rows)
    contrast_ren = _fimage(luma.local_range(cell_luma, 1), cols, rows)
    contrast_corr = _pearson(contrast_src, contrast_ren)

    # Shadow detail: local structure inside dark cells, not raw brightness.
    dark_source = src_cells < shadow
    dark_edge = contrast_src >= np.percentile(contrast_src, 45)
    dark = dark_source & dark_edge
    if np.any(dark):
        ratio = np.clip(contrast_ren[dark] / np.maximum(contrast_src[dark], 0.004), 0, 1.2)
        shadow_detail = 0.55 * float(np.mean(ratio)) + 0.45 * max(
            0.0, _pearson(contrast_ren[dark], contrast_src[dark]))
    else:
        shadow_detail = 0.0

    # Highlight detail: internal variation and non-saturation of bright cells.
    bright = src_cells >= np.percentile(src_cells, 85)
    if np.any(bright):
        src_local = contrast_src[bright]
        ren_local = contrast_ren[bright]
        detail_ratio = float(np.mean(np.clip(ren_local / np.maximum(src_local, 0.004), 0, 1.5)))
        detail_corr = _pearson(ren_local, src_local)
        src_span = float(np.percentile(src_n[bright], 90) - np.percentile(src_n[bright], 10))
        ren_span = float(np.percentile(cell_n[bright], 90) - np.percentile(cell_n[bright], 10))
        span_ratio = _clip(ren_span / max(src_span, 0.01), 0, 1)
        max_cov = float(np.percentile(coverage, 99))
        max_cell = float(np.percentile(cell_luma, 99))
        clipped = ((coverage[bright] >= 0.90 * max_cov)
                   & (cell_luma[bright] >= 0.80 * max_cell))
        highlight = (0.35 * _clip(detail_ratio)
                     + 0.25 * max(0.0, detail_corr)
                     + 0.20 * span_ratio
                     + 0.20 * (1.0 - float(np.mean(clipped))))
    else:
        highlight = 0.0

    uniform = src_edge <= np.percentile(src_edge, 30)
    uniform_density = float(1.0 - np.mean(coverage[uniform])) if np.any(uniform) else 1.0

    # Colour: compare chromaticity only, ignoring intensity and black ground.
    visible = (coverage > 0.05) & (src_cells > 0.01)
    if np.any(visible):
        src_chroma = _chroma(src_rgb_c[visible])
        ren_chroma = _chroma(glyph_rgb[visible])
        chroma_diff = float(np.mean(np.abs(src_chroma - ren_chroma)))
        src_sat = float(np.mean(np.max(src_chroma, axis=-1) - np.min(src_chroma, axis=-1)))
        ren_sat = float(np.mean(np.max(ren_chroma, axis=-1) - np.min(ren_chroma, axis=-1)))
        color = _clip(1.0 - 1.6 * chroma_diff - 0.35 * abs(src_sat - ren_sat))
    else:
        color = 0.0

    # UI/text at the detail grid: edge preservation, local contrast and
    # saturation, not coverage correlation alone.
    src_edge_d = _fimage(src_edge_full, dcols, drows)
    ren_edge_d = _fimage(luma.local_range(ren_l, 1), dcols, drows)
    src_local_d = src_edge_d
    ren_local_d = ren_edge_d
    coverage_d = _resize_map(mask, dcols, drows)
    glyph_energy_d = _resize_map(ren_l * mask, dcols, drows)
    glyph_luma_d = glyph_energy_d / np.maximum(coverage_d, 1e-5)
    ui_mask = (src_edge_d >= np.percentile(src_edge_d, 90)) & (src_edge_d > 0.008)
    if np.any(ui_mask):
        ui_corr = _pearson(src_edge_d[ui_mask], ren_edge_d[ui_mask])
        ui_contrast = float(np.mean(np.clip(
            ren_local_d[ui_mask] / np.maximum(src_local_d[ui_mask], 0.006), 0, 1.5)))
        ui_stroke = float(np.mean(ren_local_d[ui_mask] > 0.18 * src_local_d[ui_mask]))
        ui_clip = float(np.mean((coverage_d[ui_mask] >= 0.92 * np.percentile(coverage_d, 99))
                                & (glyph_luma_d[ui_mask] >= 0.90)))
        ui = (0.30 * max(0.0, ui_corr) + 0.25 * _clip(ui_contrast)
              + 0.25 * ui_stroke + 0.20 * (1.0 - ui_clip))
    else:
        ui = 0.0

    structure = (0.35 * ssim_cell + 0.25 * ssim_cov + 0.20 * ssim_glyph
                 + 0.20 * max(0.0, coverage_corr))
    return {
        "ssim": round(ssim_cell, 4), "ssim_cov": round(ssim_cov, 4),
        "ssim_glyph": round(ssim_glyph, 4), "edge_ssim": round(ssim_edge, 4),
        "edge_corr": round(edge_corr, 4), "contrast": round(contrast_corr, 4),
        "structure": round(structure, 4), "shadow": round(shadow_detail, 4),
        "highlight": round(highlight, 4), "uniform": round(uniform_density, 4),
        "color": round(color, 4), "ui": round(ui, 4),
        "coverage": round(float(np.mean(coverage)), 4),
        "coverage_std": round(float(np.std(coverage)), 4),
        "glyph_luma": round(float(np.mean(glyph_luma)), 4),
        "detail_grid": [int(dcols), int(drows)],
    }


def temporal_flicker(sources: list[Image.Image], renders: list[Image.Image],
                     fmt: str) -> dict:
    """Separate static-cell flicker from motion that follows the source."""
    cols, rows = common_grid(fmt)
    if len(sources) < 2 or len(renders) < 2:
        return {"flicker": 1.0, "motion_corr": 0.0, "static_motion": 0.0}
    src_cells = [_fimage(luma.linear_luma_array(im.convert("RGB")), cols, rows)
                 for im in sources]
    ren_l = [luma.linear_luma_array(im.convert("RGB")) for im in renders]
    ren_cov = [_resize_map((lum > 0.012).astype(np.float32), cols, rows) for lum in ren_l]
    flickers, correlations, static_motion = [], [], []
    for i in range(1, len(src_cells)):
        sm = np.abs(src_cells[i] - src_cells[i - 1])
        rm = np.abs(ren_cov[i] - ren_cov[i - 1])
        static = sm <= max(0.003, float(np.median(sm)) * 0.5)
        if np.any(static):
            flickers.append(float(np.mean(np.maximum(0.0, rm[static] - 2.0 * sm[static]))))
            static_motion.append(float(np.mean(rm[static])))
        if sm.std() > 1e-6 and rm.std() > 1e-6:
            correlations.append(_pearson(rm, sm))
    return {
        "flicker": round(float(np.mean(flickers)) if flickers else 0.0, 4),
        "motion_corr": round(float(np.mean(correlations)) if correlations else 0.0, 4),
        "static_motion": round(float(np.mean(static_motion)) if static_motion else 0.0, 4),
    }

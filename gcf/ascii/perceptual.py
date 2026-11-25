from __future__ import annotations

import numpy as np
from PIL import Image

from gcf.ascii import luma


def common_grid(fmt: str) -> tuple[int, int]:
    return (36, 64) if fmt == "vertical" else (64, 36)


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
    if a.std() < 1e-8 or b.std() < 1e-8:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def metrics(source: Image.Image, rendered: Image.Image, fmt: str, shadow: float) -> dict:
    cols, rows = common_grid(fmt)
    src = source.convert("RGB")
    ren = rendered.convert("RGB")
    src_l = luma.linear_luma_array(src)
    src_rgb = np.asarray(src, dtype=np.float32) / 255.0
    src_edge_full = luma.local_range(src_l, 1)
    ren_l = luma.linear_luma_array(ren)
    mask = (ren_l > 0.012).astype(np.float32)
    src_cells = _fimage(src_l, cols, rows)
    src_edge = _fimage(src_edge_full, cols, rows)
    src_rgb_c = _rgbimage(src_rgb, cols, rows)
    coverage = _resize_map(mask, cols, rows)
    glyph_energy = _resize_map(ren_l * mask, cols, rows)
    glyph_luma = glyph_energy / np.maximum(coverage, 1e-5)
    cell_luma = _fimage(ren_l, cols, rows)
    glyph_rgb = np.dstack([
        _resize_map(ren_l * mask * (np.asarray(ren, dtype=np.float32)[..., c] / 255.0), cols, rows)
        / np.maximum(glyph_energy, 1e-5) for c in range(3)
    ])
    lo, hi = np.percentile(src_cells, [2, 98])
    src_n = _norm(src_cells, lo, hi)
    cell_n = _norm(cell_luma, lo, hi)
    glyph_n = _norm(glyph_luma, lo, hi)
    edge_src_n = _norm(src_edge, 0, max(1e-4, np.percentile(src_edge, 98)))
    edge_ren = _fimage(luma.local_range(cell_luma, 1), cols, rows)
    edge_ren_n = _norm(edge_ren, 0, max(1e-4, np.percentile(edge_ren, 98)))
    ssim_cell = ms_ssim(src_n, cell_n)
    ssim_edge = ms_ssim(edge_src_n, edge_ren_n)
    edge_corr = _pearson(edge_src_n, edge_ren_n)
    contrast_src = _fimage(luma.local_range(src_cells, 1), cols, rows)
    contrast_ren = _fimage(luma.local_range(cell_luma, 1), cols, rows)
    contrast_corr = _pearson(contrast_src, contrast_ren)
    edge_q70 = float(np.percentile(src_edge, 70))
    dark = (src_cells < shadow) & (src_edge >= edge_q70)
    if np.any(dark):
        shadow_detail = float(np.mean(np.clip((glyph_n * coverage)[dark] / np.maximum(src_n[dark], 1e-3), 0, 1)))
    else:
        shadow_detail = 0.0
    bright = src_cells >= np.percentile(src_cells, 90)
    if np.any(bright):
        ratio = np.clip(cell_n[bright] / np.maximum(src_n[bright], 1e-3), 0, 1.5)
        highlight = float(np.mean(np.clip(ratio, 0, 1)))
    else:
        highlight = 0.0
    uniform = src_edge <= np.percentile(src_edge, 30)
    uniform_density = float(1.0 - np.mean(coverage[uniform])) if np.any(uniform) else 1.0
    visible = coverage > 0.05
    color = 1.0
    if np.any(visible):
        diff = np.abs(src_rgb_c[visible] - glyph_rgb[visible])
        color = float(max(0.0, 1.0 - np.mean(diff) * 2.5))
    ui = src_edge >= np.percentile(src_edge, 90)
    if np.any(ui):
        ui_corr = _pearson(src_edge[ui], coverage[ui])
        ui_score = max(0.0, 0.5 * (ui_corr + 1.0))
        ui_vis = float(np.mean(np.clip(glyph_n[ui] * coverage[ui], 0, 1)))
        ui = 0.5 * ui_score + 0.5 * ui_vis
    else:
        ui = 0.0
    structure = 0.5 * ssim_cell + 0.5 * max(0.0, edge_corr)
    return {
        "ssim": round(ssim_cell, 4), "edge_ssim": round(ssim_edge, 4),
        "edge_corr": round(edge_corr, 4), "contrast": round(contrast_corr, 4),
        "structure": round(structure, 4), "shadow": round(shadow_detail, 4),
        "highlight": round(highlight, 4), "uniform": round(uniform_density, 4),
        "color": round(color, 4), "ui": round(ui, 4),
        "coverage": round(float(np.mean(coverage)), 4),
        "coverage_std": round(float(np.std(coverage)), 4),
        "glyph_luma": round(float(np.mean(glyph_luma)), 4),
    }

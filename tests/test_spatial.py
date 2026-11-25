from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from gcf.ascii import correction, luma, perceptual, preset, reference, selector, spatial
from gcf.ascii import render as render_mod


class SpatialUnitTests(unittest.TestCase):
    def test_144x81_grid(self):
        g = preset.grid_for("horizontal", 81)
        self.assertEqual((g["cols"], g["rows"]), (144, 81))
        self.assertAlmostEqual(g["glyph"], 0.01111, places=5)

    def test_linear_luma(self):
        white = Image.new("RGB", (4, 4), (255, 255, 255))
        black = Image.new("RGB", (4, 4), (0, 0, 0))
        self.assertAlmostEqual(float(luma.linear_luma_array(white).mean()), 1.0, places=5)
        self.assertAlmostEqual(float(luma.linear_luma_array(black).mean()), 0.0, places=5)
        self.assertAlmostEqual(luma.srgb_to_linear(0.5), 0.214041, places=5)

    def test_index_encoding_is_0_255(self):
        idx = np.array([[0, 1, 2, 3, 4], [5, 6, 7, 8, 0]], dtype=np.uint8)
        im = spatial.encode_index(idx)
        self.assertEqual(im.size, (5, 2))
        self.assertEqual(set(im.getdata()), set(spatial.encoded_levels()))
        self.assertGreater(max(im.getdata()), 8)

    def test_raw_0_8_maps_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "idx").mkdir()
            Image.fromarray(np.tile(np.arange(9, dtype=np.uint8), (81, 16))[:, :144]).save(
                root / "idx" / "i_0001.png")
            with self.assertRaises(RuntimeError):
                spatial.validate_index_maps(root, 1, 144, 81)

    def test_conservative_clears_flat_background_keeps_edge(self):
        cells = np.full((20, 30), 0.25, dtype=np.float32)
        cells[8:12, 12:18] = 0.9
        base = spatial.bilateral(cells)
        stats = {"target": 0.2, "edge_p50": 0.01, "edge_p85": 0.05,
                 "std_p50": 0.002, "std_p85": 0.02}
        d, _ = spatial.spatial_index(cells, base, stats["target"], conservative=False, stats=stats)
        c, _ = spatial.spatial_index(cells, base, stats["target"], conservative=True, stats=stats)
        self.assertEqual(int(c[1, 1]), 0)
        self.assertGreater(int(c[10, 15]), 0)
        self.assertGreaterEqual(int(np.sum(c == 0)), int(np.sum(d == 0)))

    def test_correction_stats_accept_144_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f_0001.png"
            Image.linear_gradient("L").resize((144, 81)).convert("RGB").save(path)
            stats = correction._frame_stats(path, 144, 81)
            self.assertEqual(len(stats["cells"]), 144 * 81)
            self.assertTrue(0.0 <= stats["p50"] <= stats["p95"] <= 1.0)

    def test_adaptive_curve_ignores_brief_flash(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "analysis").mkdir()
            for i in range(20):
                value = 20 if i != 5 else 255
                Image.new("RGB", (320, 180), (value, value, value)).save(
                    root / "analysis" / f"f_{i + 1:04d}.png")
            project = SimpleNamespace(path=root, format="horizontal",
                                      params={"density": 81, "gamma": 0.82,
                                              "shadow": 0.31, "color_mode": 1.0})
            data = preset.resolve(project)
            plan = {"total_frames": 60, "cuts": [], "keyframes": []}
            stats = spatial.adaptive_stats(project, data, plan, "conservative", True)
            self.assertEqual(len(stats["target_curve"]), 60)
            self.assertTrue(stats["flashes"])
            self.assertLess(max(stats["target_curve"]), 0.25)
            self.assertLess(stats["shots"][0]["target"], 0.1)

    def test_selector_score_prefers_negative_space_and_rejects_blank(self):
        base = {"structure": 0.8, "edge_ssim": 0.8, "shadow": 0.8,
                "highlight": 0.8, "uniform": 0.9, "color": 0.8, "ui": 0.8,
                "render_mean": 20.0, "render_max": 200}
        temporal = {"flicker": 0.02, "motion_corr": 1.0}
        good = selector._score(base, temporal)
        dense = selector._score({**base, "uniform": 0.4}, temporal)
        self.assertGreater(good, dense)
        self.assertEqual(selector._score({**base, "render_mean": 0.1}, temporal), -1.0)

    def test_perceptual_common_grid_and_metrics(self):
        self.assertEqual(perceptual.common_grid("horizontal"), (96, 54))
        self.assertEqual(perceptual.common_grid("vertical"), (54, 96))
        source = Image.new("RGB", (1920, 1080), (180, 180, 180))
        rendered = Image.new("RGB", (1920, 1080), (0, 0, 0))
        m = perceptual.metrics(source, rendered, "horizontal", 0.31)
        for key in ("ssim", "edge_ssim", "edge_corr", "shadow", "highlight",
                    "uniform", "color", "ui", "coverage"):
            self.assertIn(key, m)
            self.assertTrue(0.0 <= m[key] <= 1.0)

    def test_highlight_and_ui_reject_flat_white(self):
        from PIL import ImageDraw
        size = (960, 540)
        source = Image.new("RGB", size, (8, 8, 8))
        draw = ImageDraw.Draw(source)
        for y in range(80, 460, 20):
            for x in range(120, 840, 20):
                value = 180 + ((x // 20 + y // 20) % 3) * 18
                draw.rectangle([x, y, x + 18, y + 18], fill=(value, value, value))
        varied = Image.new("RGB", size, (0, 0, 0))
        vdraw = ImageDraw.Draw(varied)
        for y in range(80, 460, 20):
            for x in range(120, 840, 20):
                value = 110 + ((x // 20 + y // 20) % 3) * 55
                vdraw.rectangle([x, y, x + 18, y + 18], fill=(value, value, value))
        flat = Image.new("RGB", size, (0, 0, 0))
        ImageDraw.Draw(flat).rectangle([120, 80, 840, 460], fill=(255, 255, 255))
        good = perceptual.metrics(source, varied, "horizontal", 0.31)
        bad = perceptual.metrics(source, flat, "horizontal", 0.31)
        self.assertGreater(good["highlight"], bad["highlight"])
        self.assertGreater(good["ui"], bad["ui"])

    def test_adaptive_range_maps_scene_percentiles_to_full_index_range(self):
        cells = np.array([[0.10, 0.50, 0.90]], dtype=np.float32)
        base = cells.copy()
        stats = {"v_p02": 0.10, "v_p98": 0.90}
        idx, _ = spatial.spatial_index(cells, base, 0.5, variant="range", stats=stats)
        self.assertEqual(idx[0, 0], 0)
        self.assertEqual(idx[0, 2], 8)
        idx_c, _ = spatial.spatial_index(cells, base, 0.5, variant="compress", stats=stats)
        self.assertEqual(idx_c[0, 0], 0)
        self.assertEqual(idx_c[0, 2], 8)

    def test_reference_rasterizer_places_glyph_in_its_cell(self):
        tiles = np.zeros((2, 8, 8), dtype=np.float32)
        tiles[1] = 1.0
        atlas = {"ramp": " @", "tiles": tiles, "tile": 8,
                 "coverage": np.array([0.0, 1.0], dtype=np.float32)}
        indices = np.array([[0, 1]], dtype=np.int16)
        colors = np.full((1, 2, 3), 0.5, dtype=np.float32)
        out = reference.raster_array(indices, colors, atlas, cell_px=4)
        self.assertEqual(out.shape, (4, 8, 3))
        self.assertTrue(np.all(out[:, :4] == 0))
        self.assertTrue(np.all(out[:, 4:] == 127))

    def test_shot_normalisation_reads_tone_maps(self):
        import tempfile
        from types import SimpleNamespace
        from PIL import Image as _Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "idx").mkdir()
            (root / "tone").mkdir()
            for i, value in enumerate((40, 80, 120), 1):
                _Image.new("L", (8, 8), value).save(root / "idx" / f"i_{i:04d}.png")
                _Image.new("L", (8, 8), value).save(root / "tone" / f"t_{i:04d}.png")
            project = SimpleNamespace(spatial={"dir": str(root)})
            norm = reference.shot_normalisation(project, 1, 3, step=1)
            self.assertLessEqual(norm["lo"], norm["hi"])
            self.assertEqual(norm["frames"], 3)
            self.assertTrue(0.0 <= norm["lo"] <= 1.0)

    def test_temporal_flicker_separates_static_from_source_motion(self):
        black = Image.new("RGB", (320, 180), (0, 0, 0))
        white = Image.new("RGB", (320, 180), (255, 255, 255))
        gray = Image.new("RGB", (320, 180), (120, 120, 120))
        static = perceptual.temporal_flicker([gray, gray], [black, white], "horizontal")
        moving = perceptual.temporal_flicker([black, white], [black, white], "horizontal")
        self.assertGreater(static["flicker"], moving["flicker"])
        self.assertLess(static["motion_corr"], 0.5)

    def test_source_stats_distinguishes_intentional_black(self):
        import tempfile
        from pathlib import Path as _Path
        from PIL import Image as _Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            black = root / "b.png"
            gray = root / "g.png"
            _Image.new("RGB", (64, 36), (0, 0, 0)).save(black)
            _Image.new("RGB", (64, 36), (120, 120, 120)).save(gray)
            self.assertTrue(selector._source_stats([black])["black"])
            self.assertFalse(selector._source_stats([gray])["black"])
            self.assertGreater(selector._source_stats([gray])["p50"], 0.1)

    def test_renderer_selection_and_decoupled_cell_size(self):
        from types import SimpleNamespace
        for name, version in (("v2", "v2-1"),
                              ("glyph-library", "glyph-library-2"),
                              ("glyph-library-decoupled", "glyph-library-decoupled-2")):
            project = SimpleNamespace(format="horizontal", params={"density": 81},
                                      renderer=name)
            data = preset.resolve(project)
            self.assertEqual(data["renderer"], name)
            self.assertEqual(data["renderer_version"], version)
            self.assertTrue(Path(data["preset_blend"]).exists())
            self.assertEqual(preset.renderer_version(project), version)
        project = SimpleNamespace(format="horizontal", params={"density": 81},
                                  renderer="glyph-library-decoupled")
        self.assertEqual(reference.cell_px_for(project), 13)

    def test_selector_vertical_resolution(self):
        self.assertEqual(selector._resolution("horizontal"), (1920, 1080))
        self.assertEqual(selector._resolution("vertical"), (1080, 1920))

    def test_auto_mode_is_rejected(self):
        project = SimpleNamespace(ascii_mode="auto")
        with self.assertRaises(RuntimeError):
            render_mod._mode(project)


class SignatureTests(unittest.TestCase):
    def _project(self, source: Path):
        return SimpleNamespace(
            ascii_mode="spatial", spatial_variant="d",
            spatial={"key": "maps-a", "index_root": "root-a"},
            source="source.mp4", working_source=str(source),
            format="horizontal", interval_start=0.0, interval_duration=2.0,
            params={"density": 81, "youtube_mbps": 8, "gamma": 0.82},
        )

    def test_bitrate_does_not_invalidate_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "working.mp4"
            source.write_bytes(b"source-hash")
            project = self._project(source)
            plan = {"total_frames": 60, "frame_scale": 2.0, "frame_offset": -1.0,
                    "cuts": [], "keyframes": [{"frame": 1, "shadow": 0.3, "white": 0.9}]}
            params = {"Grid X": 144, "Grid Y": 81}
            first = render_mod._signature(project, params, plan)
            project.params["youtube_mbps"] = 20
            self.assertEqual(first, render_mod._signature(project, params, plan))

    def test_maps_and_variant_invalidate_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "working.mp4"
            source.write_bytes(b"source-hash")
            project = self._project(source)
            plan = {"total_frames": 60, "frame_scale": 2.0, "frame_offset": -1.0,
                    "cuts": [], "keyframes": [{"frame": 1, "shadow": 0.3, "white": 0.9}]}
            params = {"Grid X": 144, "Grid Y": 81}
            first = render_mod._signature(project, params, plan)
            project.spatial["index_root"] = "root-b"
            self.assertNotEqual(first, render_mod._signature(project, params, plan))
            project.spatial["index_root"] = "root-a"
            project.spatial_variant = "conservative"
            self.assertNotEqual(first, render_mod._signature(project, params, plan))


if __name__ == "__main__":
    unittest.main()

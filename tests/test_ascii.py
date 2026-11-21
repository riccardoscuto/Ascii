import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from gcf.ascii import preset
from gcf.ascii.media import _crop_rect, _fps_arg
from gcf.ascii.render import _next_frame
from gcf.ascii.tone import build_plan


class GridTests(unittest.TestCase):
    def test_horizontal_v2_grid(self):
        g = preset.grid_for("horizontal", 54)
        self.assertEqual((g["cols"], g["rows"]), (96, 54))
        self.assertEqual(g["resolution"], (1920, 1080))
        self.assertAlmostEqual(g["glyph"], 0.01666, places=5)

    def test_vertical_swaps_plane(self):
        g = preset.grid_for("vertical", 54)
        self.assertEqual((g["cols"], g["rows"]), (54, 96))
        self.assertEqual(g["resolution"], (1080, 1920))
        self.assertEqual((g["plane_x"], g["plane_y"]), (preset.PLANE_Y, preset.PLANE_X))


class CropTests(unittest.TestCase):
    def test_vertical_crop_from_16_9(self):
        self.assertEqual(_crop_rect(1920, 1080, "vertical"), (608, 1080, 656, 0))

    def test_already_matching_is_untouched(self):
        self.assertEqual(_crop_rect(1080, 1920, "vertical"), (1080, 1920, 0, 0))
        self.assertEqual(_crop_rect(1920, 1080, "horizontal"), (1920, 1080, 0, 0))

    def test_fractional_fps_survives(self):
        self.assertEqual(_fps_arg(23.976024), "24000/1001")
        self.assertEqual(_fps_arg(30), "30.000000")


class ResumeTests(unittest.TestCase):
    def test_continues_after_valid_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in (1, 2):
                Image.new("RGB", (8, 8)).save(root / f"f_{i:04d}.png")
            self.assertEqual(_next_frame(root, 10), 3)

    def test_drops_truncated_last_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (8, 8)).save(root / "f_0001.png")
            (root / "f_0002.png").write_bytes(b"truncated")
            self.assertEqual(_next_frame(root, 10), 2)
            self.assertFalse((root / "f_0002.png").exists())


class PlanTests(unittest.TestCase):
    def test_generic_plan_for_new_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            analysis = root / "analysis"
            analysis.mkdir()
            (root / "temp").mkdir()
            for i in range(12):
                im = Image.new("L", (320, 180), (i * 20) % 256)
                im.save(analysis / f"f_{i + 1:04d}.png")
            project = SimpleNamespace(
                path=root,
                working_info={"duration": 1.2, "fps": 60.0},
                plan_path="",
                save=lambda: None,
            )
            plan = build_plan(project, fps=60.0, base_shadow=0.31, base_white=0.95)
            self.assertEqual(plan["total_frames"], 36)
            self.assertAlmostEqual(plan["frame_scale"], 2.0)
            self.assertAlmostEqual(plan["frame_offset"], -1.0)
            self.assertTrue(1 <= plan["keyframes"][0]["frame"])
            self.assertLessEqual(plan["keyframes"][-1]["frame"], 36)
            for key in plan["keyframes"]:
                self.assertLessEqual(key["shadow"], key["white"])
            self.assertIn("no Nier overrides", plan["note"])
            self.assertTrue((root / "temp" / "plan.json").exists())


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from gcf.ascii import correction
from gcf.ascii.correction import PARAMS, _flashes, _mapped_index, build_auto_plan


def base_plan(frames=60):
    return {
        "total_frames": frames,
        "cuts": [],
        "keyframes": [
            {"frame": 1, "shadow": 0.234, "white": 0.91},
            {"frame": frames, "shadow": 0.234, "white": 0.91},
        ],
    }


class MappingTests(unittest.TestCase):
    def test_index_monotonic_and_clamped(self):
        params = dict(correction.BASE)
        values = [_mapped_index(v / 100.0, params) for v in range(101)]
        self.assertEqual(values[0], 0)
        self.assertEqual(values[-1], correction.INDEX_MAX)
        self.assertEqual(values, sorted(values))

    def test_low_contrast_maps_more_cells(self):
        dark = dict(correction.BASE, shadow=0.02, white=0.30, gamma=0.93,
                    contrast_low=0.03, local_contrast=0.34)
        cell = 0.06
        self.assertGreater(_mapped_index(cell, dark), _mapped_index(cell, correction.BASE))


class FlashTests(unittest.TestCase):
    def test_single_frame_flash_is_flagged(self):
        samples = [{"mean": m} for m in (0.05, 0.05, 0.9, 0.05, 0.05)]
        self.assertIn(2, _flashes(samples))

    def test_cut_is_not_a_flash(self):
        samples = [{"mean": m} for m in (0.6, 0.6, 0.06, 0.06, 0.06)]
        self.assertEqual(_flashes(samples), set())


class AutoPlanTests(unittest.TestCase):
    def _project(self, root, make_image):
        (root / "analysis").mkdir(parents=True)
        (root / "temp").mkdir()
        for i in range(20):
            make_image().save(root / "analysis" / f"f_{i + 1:04d}.png")
        return SimpleNamespace(path=root, source="x.mp4", working_info={"duration": 2.0},
                               plan_path="", save=lambda: None)

    @staticmethod
    def _dark():
        return Image.linear_gradient("L").resize((320, 180)).point(
            lambda v: v // 4).convert("RGB")

    @staticmethod
    def _bright():
        return Image.linear_gradient("L").resize((320, 180)).point(
            lambda v: 120 + v // 2).convert("RGB")

    def test_dark_source_gets_adaptive_values_and_full_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(Path(tmp), self._dark)
            plan = build_auto_plan(project, 30.0, base_plan())
            first = plan["keyframes"][0]
            self.assertEqual(plan["mode"], "auto")
            self.assertEqual(set(first), {"frame", *PARAMS})
            self.assertLess(first["shadow"], 0.234)
            self.assertLess(first["contrast_low"], 0.18)
            self.assertTrue((Path(tmp) / "temp" / "plan.json").exists())
            second = build_auto_plan(project, 30.0, base_plan())
            self.assertEqual(plan["keyframes"], second["keyframes"])

    def test_bright_source_keeps_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(Path(tmp), self._bright)
            plan = build_auto_plan(project, 30.0, base_plan())
            first = plan["keyframes"][0]
            self.assertAlmostEqual(first["shadow"], 0.234, places=4)
            self.assertAlmostEqual(first["white"], 0.91, places=4)
            self.assertAlmostEqual(first["contrast_low"], 0.18, places=4)


    def test_manual_override_is_applied_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(Path(tmp), self._dark)
            plan = build_auto_plan(project, 30.0, base_plan(),
                                   overrides=[{"start": 0.0, "end": 1.0,
                                               "params": {"shadow": 0.1}}])
            self.assertEqual(plan["overrides"][0]["params"]["shadow"], 0.1)
            self.assertAlmostEqual(plan["keyframes"][0]["shadow"], 0.1, places=4)

    def test_fine_detail_is_flagged_resolution_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(
                Path(tmp), lambda: Image.effect_noise((320, 180), 128).convert("RGB"))
            plan = build_auto_plan(project, 30.0, base_plan())
            self.assertGreater(plan["quality"]["resolution_limited_samples"], 0)
            self.assertTrue(any(row["kind"] == "resolution_limited"
                                for row in plan["limitations"]))


if __name__ == "__main__":
    unittest.main()

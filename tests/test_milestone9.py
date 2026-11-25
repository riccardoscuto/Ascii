from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from gcf.ascii import preset, reference, spatial
from gcf.ascii import render as render_mod
from gcf.guess import ascii_clip
from gcf.guess.round import RoundTiming
from gcf.guess.short import _clip_rows, short_metadata, short_outro_duration
from gcf.gui.project import ClipEntry, GameEntry, Project


def _maps(root: Path, start: int, end: int, value: int) -> None:
    (root / "idx").mkdir(parents=True, exist_ok=True)
    (root / "tone").mkdir(parents=True, exist_ok=True)
    for frame in range(start, end + 1):
        Image.new("L", (8, 6), 0).save(root / "idx" / f"i_{frame:04d}.png")
        Image.new("L", (8, 6), value).save(root / "tone" / f"t_{frame:04d}.png")


def _analysis(root: Path, frames: int) -> None:
    (root / "analysis").mkdir(parents=True, exist_ok=True)
    for frame in range(1, frames + 1):
        Image.new("RGB", (64, 36), (120, 120, 120)).save(
            root / "analysis" / f"f_{frame:04d}.png"
        )


class Milestone9Tests(unittest.TestCase):
    def _shot_project(self, root: Path, coverage: int, cut_plan: bool = True) -> SimpleNamespace:
        maps = root / "maps"
        _maps(maps, 1, coverage, 30)
        _analysis(root, 40)
        plan = {"cuts": [2.0] if cut_plan else [], "keyframes": []}
        plan_path = root / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return SimpleNamespace(
            path=root, working_info={"duration": 4.0, "fps": 30.0},
            plan_path=str(plan_path), format="horizontal",
            params={"density": 81}, spatial={"dir": str(maps), "frames": coverage,
                                             "key": f"k{coverage}"},
        )

    def test_shot_context_is_per_shot_and_persistent_only_when_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._shot_project(root, coverage=120)
            first = reference.shot_context(project, 10)
            self.assertEqual((first["start"], first["end"]), (1, 60))
            self.assertLess(first["tone"]["hi"], 0.2)
            second = reference.shot_context(project, 70)
            self.assertEqual((second["start"], second["end"]), (61, 120))
            cache = root / "temp" / "decoupled" / "shot_context.json"
            self.assertTrue(cache.exists())
            entries = json.loads(cache.read_text(encoding="utf-8"))["entries"]
            self.assertEqual(len(entries), 2)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._shot_project(root, coverage=30)
            partial = reference.shot_context(project, 10)
            self.assertEqual(partial["coverage"], 30)
            cache = root / "temp" / "decoupled" / "shot_context.json"
            self.assertFalse(cache.exists())

    def test_frame_time_uses_output_timeline_for_high_fps_source(self):
        project = SimpleNamespace(working_info={"duration": 2.0, "fps": 60.0})
        self.assertAlmostEqual(reference.frame_time(project, 1), 0.0, places=4)
        self.assertAlmostEqual(reference.frame_time(project, 31), 1.0, places=4)
        self.assertLess(reference.frame_time(project, 999), 2.0)

    def test_palette_and_color_mode_are_used(self):
        amber = reference.palette_color(np.array([0.5, 0.8]), 0.0)
        steel = reference.palette_color(np.array([0.5, 0.8]), 1.0)
        self.assertGreater(float(np.abs(amber - steel).max()), 0.1)
        rgb = np.array([[[200, 100, 50]]], dtype=np.float32) / 255.0
        intensity = np.array([[0.6]], dtype=np.float32)
        original = reference.decoupled_color(rgb, intensity, 0.0, 0.0)
        paletted = reference.decoupled_color(rgb, intensity, 1.0, 0.0)
        self.assertFalse(np.array_equal(original, paletted))

    def test_preset_exposes_palette_mix(self):
        project = SimpleNamespace(format="horizontal", renderer="glyph-library",
                                  working_info={"fps": 30.0, "duration": 2.0},
                                  params={"density": 81, "palette": 1.0,
                                          "color_mode": 1.0})
        data = preset.resolve(project)
        self.assertEqual(data["palette"], 1.0)
        self.assertEqual(data["sockets"]["Palette Mix"], 1.0)
        self.assertEqual(preset.expected(project)["palette_mix"], 1.0)

    def test_map_content_hash_is_content_not_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _maps(root, 1, 2, 30)
            first = spatial.map_content_hash(root, 2)
            _maps(root, 1, 2, 120)
            self.assertNotEqual(first, spatial.map_content_hash(root, 2))

    def test_project_ascii_states_and_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = GameEntry(id="g1", title="Balatro")
            project = Project(id="p", path=root, title="Guess", games=[game])
            for slot in range(4):
                take = project.take_dir(game, f"take_{slot}")
                take.mkdir(parents=True)
                (take / "take.mp4").write_bytes(b"x")
                game.clips[slot] = ClipEntry(take_id=f"take_{slot}", status="recorded")
            self.assertEqual(project.ascii_state(game, 0), "recorded")
            self.assertFalse(project.ascii_ready_for_game(game))
            for slot in range(3):
                out = project.ascii_dir(game, slot) / "output" / "master.mp4"
                out.parent.mkdir(parents=True)
                out.write_bytes(b"ascii")
                project.set_ascii(game, slot, {"output": str(out), "status": "converted"})
            self.assertEqual(project.ascii_state(game, 0), "converted")
            for slot in range(3):
                project.approve_ascii(game, slot)
            self.assertTrue(project.ascii_ready_for_game(game))

    def test_clip_rows_require_ascii_for_clues_but_not_reveal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = GameEntry(id="g1", title="Balatro")
            project = Project(id="p", path=root, title="Guess", games=[game])
            for slot in range(4):
                take = project.take_dir(game, f"take_{slot}")
                take.mkdir(parents=True)
                (take / "take.mp4").write_bytes(b"x")
                game.clips[slot] = ClipEntry(take_id=f"take_{slot}", status="recorded")
            from gcf.guess.round import InsufficientMaterial
            with self.assertRaises(InsufficientMaterial):
                _clip_rows(project, 0)
            for slot in range(3):
                out = project.ascii_dir(game, slot) / "output" / "master.mp4"
                out.parent.mkdir(parents=True)
                out.write_bytes(b"ascii")
                project.set_ascii(game, slot, {"output": str(out), "status": "approved"})
            rows = _clip_rows(project, 0)
            self.assertEqual([row["kind"] for row in rows],
                             ["ascii", "ascii", "ascii", "original"])

    def test_three_rounds_are_exactly_810_frames(self):
        timing = RoundTiming((2.0, 2.0, 2.0, 3.0))
        self.assertEqual(timing.total, 9.0)
        self.assertEqual(int(timing.total * 30 * 3), 810)
        self.assertEqual(short_outro_duration(2.0, 9.0), 4.0)

    def test_public_metadata_does_not_contain_game_titles(self):
        game = GameEntry(id="g1", title="Secret Game")
        project = Project(id="p", path=Path("."), title="Guess", games=[game])
        text = json.dumps(short_metadata(project))
        self.assertNotIn("Secret Game", text)
        self.assertIn("games_count", text)

    def test_ascii_settings_map_color_and_fingerprint_inputs(self):
        settings = ascii_clip.normalize_settings({"mode": "highlight", "color": "steel"})
        self.assertEqual(settings["mode"], "highlight")
        self.assertEqual(settings["color"], "steel")
        color_mode, palette, params = ascii_clip._settings_params(settings)
        self.assertEqual((color_mode, palette), (1.0, 1.0))
        self.assertEqual(params["color_mode"], 1.0)
        self.assertEqual(params["palette"], 1.0)

    def test_dirty_ascii_revokes_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = GameEntry(id="g1", title="Balatro")
            project = Project(id="p", path=root, title="Guess", games=[game])
            for slot in range(4):
                take = project.take_dir(game, f"take_{slot}")
                take.mkdir(parents=True)
                (take / "take.mp4").write_bytes(b"x")
                game.clips[slot] = ClipEntry(take_id=f"take_{slot}", status="recorded")
            for slot in range(3):
                out = project.ascii_dir(game, slot) / "output" / "master.mp4"
                out.parent.mkdir(parents=True)
                out.write_bytes(b"ascii")
                project.set_ascii(game, slot, {"output": str(out), "status": "approved",
                                               "dirty": False})
            self.assertTrue(project.ascii_ready_for_game(game))
            project.set_ascii(game, 1, {"dirty": True})
            self.assertEqual(project.ascii_state(game, 1), "dirty")
            self.assertFalse(project.ascii_ready_for_game(game))

    def test_tone_controls_are_identity_at_defaults_and_used_otherwise(self):
        idx = np.array([[0, 2, 4, 8]], dtype=np.uint8)
        tone = np.array([[0, 64, 128, 255]], dtype=np.uint8)
        same_idx, same_tone = spatial.adjust_levels(idx, tone, {
            "gamma": 0.82, "shadow": 0.31, "contrast_high": 0.85})
        self.assertTrue(np.array_equal(same_idx, idx))
        self.assertTrue(np.array_equal(same_tone, tone))
        dark_idx, dark_tone = spatial.adjust_levels(idx, tone, {
            "gamma": 1.20, "shadow": 0.31, "contrast_high": 0.85})
        self.assertFalse(np.array_equal(dark_idx, idx))
        self.assertFalse(np.array_equal(dark_tone, tone))

    def test_render_signature_hashes_map_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "working.mp4"
            source.write_bytes(b"source")
            maps = root / "maps"
            _maps(maps, 1, 2, 30)
            project = SimpleNamespace(
                ascii_mode="spatial", spatial_variant="d", renderer="glyph-library",
                spatial={"key": "k", "dir": str(maps), "index_root": "root"},
                decoupled={}, source=str(source), working_source=str(source),
                format="horizontal", interval_start=0.0, interval_duration=1.0,
                params={"density": 81, "palette": 0.0},
            )
            plan = {"total_frames": 2, "frame_scale": 2.0, "frame_offset": -1.0,
                    "cuts": [], "keyframes": [{"frame": 1, "shadow": 0.3, "white": 0.9}]}
            first = render_mod._signature(project, {"Grid X": 144, "Grid Y": 81}, plan)
            _maps(maps, 2, 2, 120)
            second = render_mod._signature(project, {"Grid X": 144, "Grid Y": 81}, plan)
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()

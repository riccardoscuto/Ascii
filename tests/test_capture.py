import json
import unittest
from pathlib import Path

from gcf.capture.takes import crop_rect, list_takes, probe, slug
from gcf.config import ROOT
from gcf.guess.round import (
    BEATMAP,
    ClipTooShort,
    beat_time,
    make_round_timing,
    segment_window,
)
from gcf.gui.project import CLIP_COUNT, ClipEntry, GameEntry, Project


class CropTests(unittest.TestCase):
    def test_1920x1080_center(self):
        self.assertEqual(crop_rect(1920, 1080), {"x": 656, "y": 0, "w": 608, "h": 1080})

    def test_1920x1080_offset_clamped(self):
        left = crop_rect(1920, 1080, -5000)
        right = crop_rect(1920, 1080, 5000)
        self.assertEqual(left["x"], 0)
        self.assertEqual(right["x"] + right["w"], 1920)

    def test_vertical_input_is_untouched(self):
        self.assertEqual(crop_rect(1080, 1920), {"x": 0, "y": 0, "w": 1080, "h": 1920})

    def test_960x540(self):
        self.assertEqual(crop_rect(960, 540), {"x": 328, "y": 0, "w": 304, "h": 540})

    def test_2560x1440(self):
        self.assertEqual(crop_rect(2560, 1440), {"x": 875, "y": 0, "w": 810, "h": 1440})

    def test_slug(self):
        self.assertEqual(slug("Stellar Blade / Test"), "Stellar_Blade_Test")


class TakeIntegrationTests(unittest.TestCase):
    def test_selected_take_is_vertical(self):
        project = ROOT / "projects" / "test_a"
        rows = list_takes(project, "test_window")
        if not rows:
            self.skipTest("nessun take di test disponibile")
        selected = next((r for r in rows if r["selected"]), None)
        if selected is None:
            self.skipTest("nessun take selezionato")
        path = ROOT / selected["mp4"]
        if not path.exists():
            self.skipTest("take selezionato non trovato")
        info = probe(path)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertEqual(info["fps"], 60.0)
        self.assertFalse(info["has_audio"])


class GraphicsPresetTests(unittest.TestCase):
    def test_number_position_and_size_come_from_preset(self):
        import tempfile

        from PIL import Image

        from gcf.guess.round import load_preset, make_overlays

        preset = load_preset()
        preset["number"].update({"x": 240, "y": 420, "font_size": 80})
        with tempfile.TemporaryDirectory() as tmp:
            number, _title = make_overlays(Path(tmp), "1.", "BALATRO", preset)
            with Image.open(number) as image:
                box = image.getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[0], 228)
        self.assertGreaterEqual(box[1], 410)
        self.assertLess(box[3] - box[1], 120)


class ShortLayoutTests(unittest.TestCase):
    def test_cover_and_outro_keep_sixty_seconds(self):
        from gcf.guess.short import short_outro_duration

        self.assertEqual(short_outro_duration(2.0, 9.0), 4.0)
        self.assertEqual(short_outro_duration(3.0, 9.0), 3.0)
        self.assertEqual(short_outro_duration(5.0, 9.0), 1.0)

    def test_no_space_for_outro_is_blocked(self):
        from gcf.guess.round import InsufficientMaterial
        from gcf.guess.short import short_outro_duration

        with self.assertRaises(InsufficientMaterial):
            short_outro_duration(6.0, 9.0)


class CoverTextTests(unittest.TestCase):
    def test_highlight_phrase_is_kept_on_one_chunk(self):
        from gcf.guess.cover import _text_chunks

        tokens = "GUESS THE GAME FROM ITS TITLE SCREEN".split()
        chunks = _text_chunks(tokens, ["THE GAME"])
        self.assertIn([(1, "THE"), (2, "GAME")], chunks)
        self.assertEqual(len(chunks), 6)


class ProjectClipTests(unittest.TestCase):
    def _project(self, path: Path) -> Project:
        return Project(
            id="p", path=path, title="Test",
            games=[GameEntry(f"game_{i}", t) for i, t in enumerate("abcdef")],
        )

    def test_four_clips_per_game_and_navigation(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p"
            p = self._project(path)
            self.assertEqual(len(p.games[0].clips), CLIP_COUNT)
            self.assertFalse(p.all_recorded())
            p.set_clip(p.games[0], 0, "take_a", {"x": 0, "y": 0, "w": 2, "h": 2})
            self.assertTrue(p.next_clip())
            self.assertEqual(p.current_clip, 1)
            self.assertTrue(p.previous_clip())
            self.assertEqual(p.current_clip, 0)
            for slot in range(CLIP_COUNT):
                take_id = f"take_{slot}"
                take_dir = p.take_dir(p.games[0], take_id)
                take_dir.mkdir(parents=True, exist_ok=True)
                (take_dir / "take.mp4").write_bytes(b"x")
                p.games[0].clips[slot].take_id = take_id
            self.assertTrue(p.game_complete(p.games[0]))
            p.challenge_title = "GUESS THE GAME FROM ITS HUD"
            p.cover_duration = 3.0
            p.cover_background = {"type": "image", "path": "cover.png"}
            p.save()
            loaded = Project.load(path)
            self.assertEqual(len(loaded.games[0].clips), CLIP_COUNT)
            self.assertEqual(loaded.games[0].clips[3].take_id, "take_3")
            self.assertEqual(loaded.current_clip, 0)
            self.assertEqual(loaded.challenge_title, "GUESS THE GAME FROM ITS HUD")
            self.assertEqual(loaded.cover_duration, 3.0)
            self.assertEqual(loaded.cover_background["type"], "image")

    def test_cover_clip_is_separate_and_preferred(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p"
            p = self._project(path)
            take_dir = p.cover_take_dir("cover_take")
            take_dir.mkdir(parents=True)
            (take_dir / "take.mp4").write_bytes(b"x")
            p.set_cover_clip("cover_take", {"x": 0, "y": 0, "w": 10, "h": 10})
            self.assertEqual(p.completed_clips(), 0)
            self.assertIsNotNone(p.cover_mp4())
            self.assertEqual(p.cover_background, {"type": "cover"})

            from gcf.guess.cover import _resolve_background

            p.cover_background = {"type": "auto"}
            resolved = _resolve_background(p, None)
            self.assertEqual(resolved["type"], "clip")
            self.assertEqual(resolved["source"], "cover")

            p.save()
            loaded = Project.load(path)
            self.assertEqual(loaded.cover_clip.take_id, "cover_take")
            self.assertIsNotNone(loaded.cover_mp4())

    def test_legacy_single_take_migrates_to_clue_1(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p"
            path.mkdir()
            games = [
                {
                    "id": f"g{i}", "title": f"G{i}", "take_id": f"old{i}",
                    "crop": {"x": 0, "y": 0, "w": 2, "h": 2},
                    "status": "recorded",
                }
                for i in range(6)
            ]
            (path / "project.json").write_text(json.dumps({
                "id": "p", "title": "T", "current_index": 0, "games": games,
            }), encoding="utf-8")
            p = Project.load(path)
            self.assertEqual(len(p.games[0].clips), CLIP_COUNT)
            self.assertEqual(p.games[0].clips[0].take_id, "old0")
            self.assertEqual(p.games[0].clips[1].take_id, None)


class RoundTimingTests(unittest.TestCase):
    def test_default_timing_matches_120_bpm(self):
        timing = make_round_timing()
        self.assertEqual(timing.clip_durations, (2.0, 2.0, 2.0, 3.0))
        self.assertEqual(timing.total, 9.0)
        self.assertEqual(timing.reveal_at, 6.0)

    def test_windows_trim_without_speeding(self):
        self.assertEqual(segment_window(4.8, 2.0, reveal=False), (1.4, 3.4))
        self.assertEqual(segment_window(4.8, 3.0, reveal=True), (1.8, 4.8))

    def test_short_clip_is_reported(self):
        with self.assertRaises(ClipTooShort):
            segment_window(1.5, 2.0, reveal=False)


class ShortTests(unittest.TestCase):
    def test_short_rejects_missing_takes(self):
        import tempfile
        from unittest import mock

        from gcf.guess.short import InsufficientMaterial, build_short
        from gcf.gui.project import GameEntry, Project

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p"
            path.mkdir()
            Project(
                id="p", path=path, title="Test",
                games=[GameEntry(f"game_{i}", t) for i, t in enumerate("abcdef")],
            ).save()
            with mock.patch("gcf.guess.short.project_dir", return_value=path):
                with self.assertRaises(InsufficientMaterial):
                    build_short("p")


class RoundTests(unittest.TestCase):
    def test_placeholder_beat_events(self):
        if not BEATMAP.exists():
            self.skipTest("beatmap placeholder non presente")
        self.assertEqual(beat_time(1), 0.5)
        self.assertEqual(beat_time(8), 4.0)

    def test_round_is_vertical_ten_seconds(self):
        path = ROOT / "projects" / "test_a" / "rounds" / "balatro_20261119_160135" / "round_01.mp4"
        if not path.exists():
            self.skipTest("round di test non presente")
        info = probe(path)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertEqual(info["fps"], 30.0)
        self.assertEqual(info["duration"], 10.0)
        self.assertEqual(info["frames"], 300)
        self.assertTrue(info["has_audio"])

    def test_four_clip_round_is_nine_seconds(self):
        outdir = ROOT / "projects" / "round4_test" / "rounds" / "test1"
        path = outdir / "round_01.mp4"
        if not path.exists():
            self.skipTest("round a quattro clip non presente")
        info = probe(path)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertEqual(info["fps"], 30.0)
        self.assertEqual(info["duration"], 9.0)
        self.assertEqual(info["frames"], 270)
        self.assertTrue(info["has_audio"])
        manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["clips"]), 4)
        self.assertEqual(manifest["events"]["reveal_at"], 6.0)
        self.assertEqual(manifest["events"]["number_at"], 0.0)

    def test_overlay_crop_mapping(self):
        from PySide6.QtCore import QRect
        from gcf.gui.capture import GuiCaptureSession
        crop = GuiCaptureSession.crop_from_overlay(
            QRect(500, 0, 608, 1080), QRect(0, 0, 1920, 1080), 1920, 1080
        )
        self.assertEqual(crop, {"x": 500, "y": 0, "w": 608, "h": 1080})
        frame = GuiCaptureSession.frame_from_crop(
            crop, QRect(0, 0, 1920, 1080), 1920, 1080
        )
        self.assertEqual(frame, QRect(500, 0, 608, 1080))


if __name__ == "__main__":
    unittest.main()

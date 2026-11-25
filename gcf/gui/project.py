from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from gcf.capture.takes import SLOT_KEYS, SLOT_LABELS, slug

CLIP_COUNT = len(SLOT_KEYS)
CLIP_KEYS = SLOT_KEYS
CLIP_LABELS = SLOT_LABELS


@dataclass
class ClipEntry:
    take_id: str | None = None
    status: str = "pending"  # pending | recorded | accepted
    crop: dict | None = None
    capture: str = "screen"  # screen | window | game
    window: str = ""
    monitor: int | None = None
    monitor_name: str = ""
    monitor_ffmpeg: bool = False
    ascii: dict = field(default_factory=dict)


def _new_clips() -> list[ClipEntry]:
    return [ClipEntry() for _ in range(CLIP_COUNT)]


@dataclass
class GameEntry:
    id: str
    title: str
    clips: list[ClipEntry] = field(default_factory=_new_clips)
    status: str = "pending"  # pending | recorded | accepted
    # Legacy single-take fields, kept so old project.json files still load.
    take_id: str | None = None
    crop: dict | None = None
    capture: str = "screen"
    window: str = ""
    monitor: int | None = None
    monitor_name: str = ""
    monitor_ffmpeg: bool = False


@dataclass
class Project:
    id: str
    path: Path
    title: str
    games: list[GameEntry] = field(default_factory=list)
    current_index: int = 0
    current_clip: int = 0
    challenge_title: str = "GUESS THE GAME IN ASCII"
    challenge_category: str = "ASCII"
    cover_background: dict = field(default_factory=lambda: {"type": "auto"})
    cover_duration: float = 2.0
    cover_clip: ClipEntry = field(default_factory=ClipEntry)
    graphics_preset: str = ""
    created_at: str = ""

    @property
    def data_path(self) -> Path:
        return self.path / "project.json"

    @classmethod
    def create(
        cls,
        titles: list[str],
        title: str = "Guess the Game",
        challenge_title: str = "GUESS THE GAME IN ASCII",
        challenge_category: str = "ASCII",
        cover_background: dict | None = None,
        cover_duration: float = 2.0,
        graphics_preset: str = "",
    ) -> "Project":
        if len(titles) != 6 or any(not t.strip() for t in titles):
            raise ValueError("Servono esattamente sei titoli non vuoti.")
        base = "short_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        root = Path(__file__).resolve().parents[2] / "projects"
        candidate = base
        n = 1
        while (root / candidate).exists():
            candidate = f"{base}_{n:02d}"
            n += 1
        path = root / candidate
        path.mkdir(parents=True, exist_ok=True)
        p = cls(
            id=candidate,
            path=path,
            title=title,
            games=[GameEntry(id=f"game_{i+1}", title=t.strip()) for i, t in enumerate(titles)],
            challenge_title=challenge_title.strip() or "GUESS THE GAME",
            challenge_category=challenge_category.strip(),
            cover_background=cover_background or {"type": "auto"},
            cover_duration=cover_duration,
            graphics_preset=graphics_preset,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        p.save()
        return p

    @classmethod
    def load(cls, path: Path) -> "Project":
        data = json.loads((path / "project.json").read_text(encoding="utf-8"))
        games = []
        for row in data.get("games", []):
            row = dict(row)
            clips_data = row.pop("clips", None)
            clips = [ClipEntry(**c) for c in (clips_data or [])]
            while len(clips) < CLIP_COUNT:
                clips.append(ClipEntry())
            game = GameEntry(**row)
            game.clips = clips[:CLIP_COUNT]
            if not clips_data and game.take_id:
                # Migrate the old one-take model: the take becomes Indizio 1.
                clip = game.clips[0]
                clip.take_id = game.take_id
                clip.status = game.status
                clip.crop = game.crop
                clip.capture = game.capture
                clip.window = game.window
                clip.monitor = game.monitor
                clip.monitor_name = game.monitor_name
                clip.monitor_ffmpeg = game.monitor_ffmpeg
            games.append(game)
        p = cls(
            id=data["id"],
            path=path,
            title=data.get("title", "Guess the Game"),
            games=games,
            current_index=int(data.get("current_index", 0)),
            current_clip=int(data.get("current_clip", 0)),
            challenge_title=data.get("challenge_title", "GUESS THE GAME IN ASCII"),
            challenge_category=data.get("challenge_category", "ASCII"),
            cover_background=data.get("cover_background", {"type": "auto"}),
            cover_duration=float(data.get("cover_duration", 2.0)),
            cover_clip=ClipEntry(**(data.get("cover_clip") or {})),
            graphics_preset=data.get("graphics_preset", ""),
            created_at=data.get("created_at", ""),
        )
        p.current_index = max(0, min(p.current_index, max(0, len(p.games) - 1)))
        p.current_clip = max(0, min(p.current_clip, CLIP_COUNT - 1))
        return p

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        data = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "current_index": self.current_index,
            "current_clip": self.current_clip,
            "challenge_title": self.challenge_title,
            "challenge_category": self.challenge_category,
            "cover_background": self.cover_background,
            "cover_duration": self.cover_duration,
            "cover_clip": asdict(self.cover_clip),
            "graphics_preset": self.graphics_preset,
            "games": [asdict(g) for g in self.games],
        }
        self.data_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @property
    def current_game(self) -> GameEntry:
        return self.games[self.current_index]

    @property
    def current_clip_entry(self) -> ClipEntry:
        return self.current_game.clips[self.current_clip]

    def take_dir(self, game: GameEntry, take_id: str) -> Path:
        return self.path / "takes" / slug(game.title) / take_id

    def cover_take_dir(self, take_id: str) -> Path:
        return self.path / "takes" / "_cover" / take_id

    def cover_mp4(self) -> Path | None:
        if not self.cover_clip.take_id:
            return None
        path = self.cover_take_dir(self.cover_clip.take_id) / "take.mp4"
        return path if path.exists() else None

    def set_cover_clip(self, take_id: str, crop: dict) -> None:
        self.cover_clip.take_id = take_id
        self.cover_clip.crop = crop
        self.cover_clip.status = "recorded"
        self.cover_background = {"type": "cover"}
        self.save()

    def clip_mp4(self, game: GameEntry, slot: int) -> Path | None:
        clip = game.clips[slot]
        if not clip.take_id:
            return None
        path = self.take_dir(game, clip.take_id) / "take.mp4"
        return path if path.exists() else None

    def set_clip(self, game: GameEntry, slot: int, take_id: str, crop: dict) -> None:
        clip = game.clips[slot]
        clip.take_id = take_id
        clip.crop = crop
        clip.status = "recorded"
        game.status = "recorded"
        self.save()

    def ascii_dir(self, game: GameEntry, slot: int) -> Path:
        return self.path / "ascii" / slug(game.title) / f"clue_{slot + 1}"

    def ascii_project_path(self, game: GameEntry, slot: int) -> Path:
        return self.ascii_dir(game, slot)

    def ascii_mp4(self, game: GameEntry, slot: int) -> Path | None:
        data = game.clips[slot].ascii or {}
        path = Path(data.get("output", "")) if data.get("output") else None
        if path and path.exists():
            return path
        candidate = self.ascii_project_path(game, slot) / "output" / "master.mp4"
        return candidate if candidate.exists() else None

    def set_ascii(self, game: GameEntry, slot: int, data: dict) -> None:
        clip = game.clips[slot]
        clip.ascii = {**(clip.ascii or {}), **data,
                      "updated_at": datetime.now().isoformat(timespec="seconds")}
        self.save()

    def approve_ascii(self, game: GameEntry, slot: int) -> None:
        data = dict(game.clips[slot].ascii or {})
        data["status"] = "approved"
        self.set_ascii(game, slot, data)

    def ascii_state(self, game: GameEntry, slot: int) -> str:
        if slot >= 3:
            return "original" if self.clip_mp4(game, slot) else "missing"
        clip = game.clips[slot]
        if not clip.take_id or not self.clip_mp4(game, slot):
            return "missing"
        data = clip.ascii or {}
        if data.get("dirty"):
            return "dirty"
        if not self.ascii_mp4(game, slot):
            return "recorded"
        return "approved" if data.get("status") == "approved" else "converted"

    def ascii_ready_for_game(self, game: GameEntry) -> bool:
        return (self.clip_mp4(game, 3) is not None
                and all(self.ascii_state(game, slot) == "approved" for slot in range(3)))

    def ascii_ready(self) -> bool:
        return all(self.ascii_ready_for_game(g) for g in self.games)

    def accept_clip(self, game: GameEntry, slot: int) -> None:
        game.clips[slot].status = "accepted"
        if self.game_complete(game):
            game.status = "accepted"
        self.save()

    def completed_clips(self, game: GameEntry | None = None) -> int:
        games = [game] if game else self.games
        return sum(
            1 for g in games for c in g.clips
            if c.take_id and (self.take_dir(g, c.take_id) / "take.mp4").exists()
        )

    def game_complete(self, game: GameEntry) -> bool:
        return all(
            c.take_id and (self.take_dir(game, c.take_id) / "take.mp4").exists()
            for c in game.clips
        )

    def set_clip_index(self, index: int) -> None:
        self.current_clip = max(0, min(index, CLIP_COUNT - 1))
        self.save()

    def next_clip(self) -> bool:
        if self.current_clip + 1 >= CLIP_COUNT:
            return False
        self.current_clip += 1
        self.save()
        return True

    def previous_clip(self) -> bool:
        if self.current_clip <= 0:
            return False
        self.current_clip -= 1
        self.save()
        return True

    def next_game(self) -> bool:
        if self.current_index + 1 >= len(self.games):
            return False
        self.current_index += 1
        self.current_clip = 0
        self.save()
        return True

    def previous_game(self) -> bool:
        if self.current_index <= 0:
            return False
        self.current_index -= 1
        self.current_clip = 0
        self.save()
        return True

    def all_recorded(self) -> bool:
        return all(self.game_complete(g) for g in self.games)

    def all_accepted(self) -> bool:
        return all(g.status == "accepted" for g in self.games)


def recent_projects() -> list[Project]:
    root = Path(__file__).resolve().parents[2] / "projects"
    out = []
    if root.exists():
        for p in sorted(root.glob("*/project.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if p.parent.name.startswith("ascii_"):
                continue
            try:
                out.append(Project.load(p.parent))
            except Exception:
                continue
    return out

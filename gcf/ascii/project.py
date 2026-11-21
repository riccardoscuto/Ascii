from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from gcf.config import ROOT


DEFAULT_PARAMS = {
    "gamma": 0.82,
    "shadow": 0.31,
    "contrast_high": 0.85,
    "density": 54,
    "color_mode": 1.0,
    "youtube_mbps": 8,
}


@dataclass
class AsciiProject:
    id: str
    path: Path
    source: str
    title: str = "ASCII Video"
    format: str = "horizontal"  # horizontal | vertical
    interval_start: float = 0.0
    interval_duration: float | None = None  # None = full source
    preset: str = "ASCII_Cinematic_Balanced_v2_96x54"
    params: dict = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    source_info: dict = field(default_factory=dict)
    working_info: dict = field(default_factory=dict)
    working_source: str = ""
    plan_path: str = ""
    verification: dict = field(default_factory=dict)
    preview: str = ""
    outputs: dict = field(default_factory=dict)
    status: str = "new"
    created_at: str = ""
    error: str = ""
    render_key: str = ""

    @property
    def data_path(self) -> Path:
        return self.path / "project.json"

    def ensure_dirs(self) -> None:
        for name in ("source", "preview", "frames", "preview_frames", "analysis", "output", "temp"):
            (self.path / name).mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, source: str, fmt: str, start: float, duration: float | None,
               params: dict | None = None, title: str = "ASCII Video") -> "AsciiProject":
        root = ROOT / "projects"
        root.mkdir(parents=True, exist_ok=True)
        base = "ascii_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = base
        n = 1
        while (root / candidate).exists():
            candidate = f"{base}_{n:02d}"
            n += 1
        path = root / candidate
        p = cls(
            id=candidate,
            path=path,
            source=str(source),
            title=title,
            format=fmt,
            interval_start=max(0.0, float(start)),
            interval_duration=duration,
            params={**DEFAULT_PARAMS, **(params or {})},
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        p.ensure_dirs()
        p.save()
        return p

    @classmethod
    def load(cls, path: Path) -> "AsciiProject":
        data = json.loads((path / "project.json").read_text(encoding="utf-8"))
        data["path"] = path
        data["params"] = {**DEFAULT_PARAMS, **data.get("params", {})}
        return cls(**data)

    def save(self) -> None:
        self.ensure_dirs()
        data = asdict(self)
        data["path"] = str(self.path)
        self.data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def frames_dir(self) -> Path:
        return self.path / "frames"

    @property
    def preview_frames_dir(self) -> Path:
        return self.path / "preview_frames"

    @property
    def output_dir(self) -> Path:
        return self.path / "output"

    @property
    def master_path(self) -> Path:
        return self.output_dir / "master.mp4"

    @property
    def youtube_path(self) -> Path:
        return self.output_dir / "youtube.mp4"


def recent_ascii_projects(limit: int = 10) -> list[Path]:
    root = ROOT / "projects"
    if not root.exists():
        return []
    rows = [p for p in root.glob("ascii_*") if (p / "project.json").exists()]
    rows.sort(key=lambda p: (p / "project.json").stat().st_mtime, reverse=True)
    return rows[:limit]

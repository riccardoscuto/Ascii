from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
OBS_CONFIG = CONFIG_DIR / "obs_ws.json"


def load_obs_config() -> dict:
    if not OBS_CONFIG.exists():
        raise SystemExit(f"Missing {OBS_CONFIG}. Run the capture setup first.")
    data = json.loads(OBS_CONFIG.read_text(encoding="utf-8"))
    for key in ("host", "port", "password", "obs_exe", "obs_workdir"):
        if key not in data:
            raise SystemExit(f"OBS config missing key: {key}")
    return data


def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise SystemExit("ffmpeg non trovato nel PATH.")
    return path


def ffprobe_bin() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise SystemExit("ffprobe non trovato nel PATH.")
    return path


def blender_bin() -> str:
    candidates = []
    env = os.environ.get("BLENDER_PATH")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"))
    for path in candidates:
        if path.exists():
            return str(path)
    raise SystemExit("Blender non trovato. Imposta BLENDER_PATH.")


@lru_cache(maxsize=1)
def has_nvenc() -> bool:
    try:
        proc = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-encoders"],
            capture_output=True, text=True, check=False,
        )
        return "h264_nvenc" in proc.stdout
    except Exception:
        return False


def video_encode_args(crf: int = 18) -> list[str]:
    """Hardware encode when available, libx264 veryfast as fallback."""
    if has_nvenc():
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(crf + 1), "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf)]


def project_dir(project: str) -> Path:
    path = ROOT / "projects" / project
    path.mkdir(parents=True, exist_ok=True)
    return path

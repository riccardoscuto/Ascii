from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from gcf.ascii import media, preset, tone
from gcf.config import ROOT, blender_bin


BLENDER_JOB = ROOT / "gcf" / "ascii" / "blender_job.py"
JOB_SCRIPT_TIMEOUT = 6 * 60 * 60


class AsciiCanceled(Exception):
    pass


def _progress(cb, done, total, elapsed, stage):
    if cb:
        eta = None
        if done and elapsed and total:
            eta = elapsed * (total - done) / done
        cb(int(done), int(total), float(elapsed), eta, stage)


def _frames_dir(project, mode):
    return project.preview_frames_dir if mode == "preview" else project.frames_dir


def _count_frames(folder: Path) -> int:
    return len(list(folder.glob("f_*.png"))) if folder.exists() else 0


def _next_frame(folder: Path, total: int) -> int:
    """First frame not yet rendered; drops a truncated last PNG after a cancel."""
    frame = 1
    while frame <= total and (folder / f"f_{frame:04d}.png").exists():
        frame += 1
    if frame > 1:
        last = folder / f"f_{frame - 1:04d}.png"
        try:
            from PIL import Image
            with Image.open(last) as im:
                im.verify()
        except Exception:
            try:
                last.unlink()
            except OSError:
                pass
            frame -= 1
    return frame


def _signature(project, params: dict, plan: dict) -> str:
    payload = {
        "source": project.source,
        "format": project.format,
        "start": project.interval_start,
        "duration": project.interval_duration,
        "params": {k: v for k, v in project.params.items() if k != "youtube_mbps"},
        "grid": params.get("Grid X"),
        "plan": plan.get("keyframes"),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def prepare(project, progress=None) -> dict:
    project.ensure_dirs()
    _progress(progress, 0, 0, 0, "Preparazione sorgente")
    media.prepare_working(project)
    _progress(progress, 0, 0, 0, "Analisi frame")
    media.extract_analysis(project)
    data = preset.resolve(project)
    plan = tone.build_plan(project, project.working_info["fps"], data["shadow"], data["white"],
                           auto=bool(project.params.get("auto_correction", False)),
                           overrides=project.params.get("correction_overrides"))
    project.plan_path = str(project.path / "temp" / "plan.json")
    project.save()
    return {"params": data, "plan": plan}


def _job_payload(project, data: dict, plan: dict, mode: str, total: int,
                 frames_dir: Path, verification: Path, preview_frames: int = 0,
                 still_frame: int = 1, still_path: str = "", start_frame: int = 1) -> dict:
    by_name = {k: v for k, v in data["sockets"].items()
               if k not in ("Source Frame Scale", "Source Frame Offset")}
    expected = preset.expected(project, plan)
    return {
        "mode": mode,
        "source": project.working_source,
        "plane": [data["grid"]["plane_x"], data["grid"]["plane_y"]],
        "resolution": list(data["resolution"]),
        "params": by_name,
        "expected": expected,
        "source_frame_scale": round(project.working_info["fps"] / 30.0, 6),
        "source_frame_offset": round(1.0 - project.working_info["fps"] / 30.0, 6),
        "plan": plan,
        "total_frames": total,
        "preview_frames": preview_frames,
        "frames_dir": str(frames_dir),
        "verification": str(verification),
        "still_frame": still_frame,
        "still_path": still_path,
        "start_frame": start_frame,
    }


def _run_blender(project, payload: dict, total: int, frames_dir: Path,
                 progress=None, cancel=None, stage="Rendering") -> None:
    job_path = project.path / "temp" / f"job_{payload['mode']}.json"
    job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    preset_copy = project.path / "temp" / "preset_work.blend"
    shutil.copy2(preset.PRESET_BLEND, preset_copy)
    log_path = project.path / "render.log"
    cmd = [blender_bin(), "-b", "--factory-startup", str(preset_copy),
           "--python", str(BLENDER_JOB), "--", str(job_path)]
    started = time.time()
    with open(log_path, "a", encoding="utf-8") as log:
        log.write("\n=== " + time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
        log.write(" ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise AsciiCanceled("Rendering interrotto.")
                done = _count_frames(frames_dir)
                _progress(progress, done, total, time.time() - started, stage)
                time.sleep(0.6)
        finally:
            if proc.poll() is None:
                proc.kill()
    if proc.returncode != 0:
        tail = "\n".join(log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-30:])
        raise RuntimeError(f"Blender ha fallito (codice {proc.returncode}).\n{tail}")
    done = _count_frames(frames_dir)
    _progress(progress, done, total, time.time() - started, stage)


def _read_verification(project, path: Path) -> dict:
    if not path.exists():
        raise RuntimeError("Verifica parametri Blender assente.")
    data = json.loads(path.read_text(encoding="utf-8"))
    project.verification = data
    if data.get("frame_range", [1, 1])[0] != 1:
        raise RuntimeError("Frame range inatteso nella verifica.")
    return data


def preview(project, progress=None, cancel=None) -> Path:
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    total = plan["total_frames"]
    preview_frames = max(1, min(120, int(round(min(4.0, project.working_info["duration"]) * 30))))
    frames = project.preview_frames_dir
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)
    verification = project.path / "temp" / "verification_preview.json"
    payload = _job_payload(project, data, plan, "preview", total, frames, verification,
                           preview_frames=preview_frames)
    _run_blender(project, payload, preview_frames, frames, progress, cancel, "Anteprima")
    _read_verification(project, verification)
    out = project.path / "preview" / "preview.mp4"
    _progress(progress, preview_frames, preview_frames, 0, "Codifica anteprima")
    media.encode_frames(project, frames, out, kind="preview")
    project.preview = str(out)
    project.status = "preview"
    project.save()
    return out


def still(project, at: float, progress=None, cancel=None) -> Path:
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    total = plan["total_frames"]
    frame = max(1, min(total, int(round(float(at) * 30)) + 1))
    out = project.path / "preview" / f"still_{frame:04d}.png"
    verification = project.path / "temp" / "verification_still.json"
    payload = _job_payload(project, data, plan, "still", total, project.path / "preview",
                           verification, still_frame=frame, still_path=str(out))
    _run_blender(project, payload, 1, project.path / "preview", progress, cancel, "Frame singolo")
    _read_verification(project, verification)
    project.preview = str(out)
    project.status = "still"
    project.save()
    return out


def render(project, progress=None, cancel=None) -> dict:
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    signature = _signature(project, data["sockets"], plan)
    frames = project.frames_dir
    if project.render_key and project.render_key != signature and frames.exists():
        shutil.rmtree(frames)
    project.render_key = signature
    frames.mkdir(parents=True, exist_ok=True)
    total = plan["total_frames"]
    start = _next_frame(frames, total)
    verification = project.path / "temp" / "verification_full.json"
    payload = _job_payload(project, data, plan, "full", total, frames, verification,
                           start_frame=start)
    if start <= total:
        _run_blender(project, payload, total, frames, progress, cancel, "Rendering completo")
    _read_verification(project, verification)
    if _count_frames(frames) < total:
        raise RuntimeError(f"Frame mancanti: {_count_frames(frames)}/{total}.")
    _progress(progress, total, total, 0, "Codifica master")
    master = media.encode_frames(project, frames, project.master_path, kind="master")
    _progress(progress, total, total, 0, "Codifica YouTube")
    youtube = media.encode_frames(project, frames, project.youtube_path, kind="youtube")
    master_info = media.probe(master)
    youtube_info = media.probe(youtube)
    expected_duration = project.working_info["duration"]
    if abs(master_info["duration"] - expected_duration) > 0.2:
        raise RuntimeError(f"Durata master inattesa: {master_info['duration']} vs {expected_duration}")
    project.outputs = {
        "master": str(master), "youtube": str(youtube),
        "master_info": master_info, "youtube_info": youtube_info,
    }
    project.status = "done"
    project.save()
    _progress(progress, total, total, 0, "Completato")
    return project.outputs
